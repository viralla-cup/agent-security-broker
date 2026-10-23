"""Recheck isolated-timeout evidence against trusted plan/ledger and service data."""
from types import SimpleNamespace
import json
from hashlib import sha256
from pathlib import Path

from agent_loop import SeededState
from .controlled_recovery import LIMITS
from .pilot_evidence import export_episode
from .pilot_observation import history_event_ids, proposal_of, validate_controlled_setup
from .study import digest, expected_state, seed_for
from .study_oracle import evaluate_study


def consistent_timeout(row, private, *, frozen, position, reservations, public, backend):
    """Hashes bind identities; recomputation checks whether bound evidence agrees.

    The caller supplies the validated frozen plan and reservation journal, never
    values taken from the episode itself. No policy decisions or model calls occur.
    """
    def require(value):
        if not value:
            raise ValueError('Inconsistent timeout evidence')

    try:
        private = Path(private)
        raw = json.loads((private / 'episode.json').read_text())
        require(json.loads((Path(public) / 'episode.json').read_text()) == row)
        require(row['backend'] == ('openai-responses' if backend == 'openai' else 'deterministic-fake'))
        if backend == 'openai':
            require(row['model'] == frozen['model'])
        task, calls, exchanges = raw['task'], raw['model_calls'], raw['exchanges']
        receipts, seeds = raw['operation_receipts'], raw['harness_requests']
        require(raw['planned_position'] == position
                and all(row.get(k) == v for k, v in position.items()))
        require(task['id'] == position['task'] and digest(task) == position['task_sha256']
                == frozen['task_definitions'][task['id']]['task_sha256'])
        require(raw['before'] == expected_state(task) and raw['loop'] == row['loop'])
        require(raw['operational_health'] == row['operational_health'])
        service_bytes = (private / 'service-evidence.json').read_bytes()
        require(raw['service_evidence_sha256'] == sha256(service_bytes).hexdigest())
        service = json.loads(service_bytes)
        # Independently collected broker logs must contain exactly the retained
        # audits/receipts, in order, with no unfinished service append.
        for name, expected in (('/tmp/security-audit.jsonl', [e['audit'] for e in exchanges]),
                               ('/tmp/pilot-operation-receipts.jsonl', receipts)):
            entry = service[name]
            require(entry['pending'] is False and isinstance(entry['text'], str))
            require([json.loads(line) for line in entry['text'].splitlines()] == expected)
        require(len(calls) == len(reservations) and 1 <= len(calls) <= LIMITS.max_model_calls)
        for number, (call, reservation) in enumerate(zip(calls, reservations), 1):
            result = reservation['result']
            require(call['number'] == reservation['number'] == result['number'] == number
                    and reservation['index'] == result['index'] == position['schedule_index']
                    and reservation['segment'] == result['segment']
                    and call['metadata'] == result['metadata'] and call['outcome'] == result['outcome'])
        require(calls[-1]['outcome'] == 'BACKEND_TIMEOUT'
                and calls[-1]['metadata']['request_sent'] is True
                and not calls[-1]['metadata'].get('response_received', False)
                and all(c['outcome'] == 'PROPOSAL' for c in calls[:-1]))
        require(all(e['audit']['condition'] == position['condition']
                    and e['audit']['evaluation_status'] == 'COMPLETED'
                    and ((e['audit']['decision'] == 'DENY' and e['audit']['execution_status'] == 'NOT_STARTED'
                          and e['audit']['dispatched'] is False)
                         or (e['audit']['decision'] == 'ALLOW' and e['audit']['execution_status'] == 'SUCCEEDED'
                             and e['audit']['dispatched'] is True)) for e in exchanges))
        prefix = [{'kind':'task', 'text':task['prompt']}]
        if task['track'] == 'R':
            require(len(seeds) == 1 and seeds[0]['event_id'] == exchanges[0]['audit']['event_id'])
            require(validate_controlled_setup(exchanges[0], receipts, seeds[0]['request'],
                    raw['before'], raw['before'], position['condition'])['valid'])
            prefix = SeededState(seeds[0]['request'], exchanges[0]['response'], 0).history(task['prompt'])
        else:
            require(seeds == [])
        seen = len(seeds)
        for call in calls:
            expected_history = prefix + [item for e in exchanges[len(seeds):seen] for item in (
                {'kind':'proposal', **proposal_of(e['request'])}, {'kind':'tool_result', **e['response']})]
            require(call['history'] == expected_history)
            require(history_event_ids(call['history'], exchanges[:seen]) == call['observed_tool_event_ids'])
            if call['outcome'] == 'PROPOSAL':
                require(call['executed_event_id'] == exchanges[seen]['audit']['event_id']
                        and call['proposal'] == proposal_of(exchanges[seen]['request']))
                seen += 1
            else:
                require('executed_event_id' not in call and 'proposal' not in call)
        require(seen == len(exchanges))
        # Reuse the established independent oracle and reporting definitions.
        episode = SimpleNamespace(seed=seed_for(task), before=raw['before'], isolation=row['isolation'],
                                  receipts=receipts, harness_requests=seeds)
        expected, checked = export_episode(task, position['condition'],
            SimpleNamespace(name=row['backend'], model=row['model']), LIMITS, episode,
            raw['loop'], exchanges, calls, True, raw['after'],
            setup_valid=True, observation_complete=True, evaluator=evaluate_study)
        require(raw['observed'] == checked['observed'])
        obs = expected['observed']
        obs.update(setup_deny_observed=task['track'] == 'R',
                   model_origin_deny_count=obs['deny_origin_counts']['model_selected'], correct_refusal=False)
        # Resource pseudonyms are deliberately random. Check their complete
        # before/after/change relationships, without exporting a private path map.
        require(len(set(row['observed']['changed_resources'])) == len(row['observed']['changed_resources']))
        def states(before, after, changed):
            require(set(changed) <= before.keys() | after.keys())
            return sorted(json.dumps([before.get(k), after.get(k), k in changed], sort_keys=True)
                          for k in before.keys() | after.keys())
        require(states(row['before'], row['after'], row['observed']['changed_resources'])
                == states(raw['before'], raw['after'], checked['observed']['changed_paths']))
        require({k:v for k,v in obs.items() if k != 'changed_resources'}
                == {k:v for k,v in row['observed'].items() if k != 'changed_resources'})
        require(raw['study_observed'] == row['observed'])
        require(all(row[k] == value for k,value in expected.items() if k not in ('before','after','observed')))
        require(row['observed_steps'] == raw['loop']['steps'] == len(exchanges)
                and raw['loop']['model_calls'] == len(calls)
                and raw['loop']['denials'] == sum(e['audit']['decision']=='DENY' for e in exchanges)
                and raw['loop']['retries'] == 0)
        return True
    except (OSError, ValueError, TypeError, KeyError, IndexError, AttributeError):
        return False
