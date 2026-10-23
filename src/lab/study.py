"""Prospective study definitions and fixture setup; no agent tools or policy imports."""

from copy import deepcopy
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
import random
import sys

from .controlled_recovery import expected_initial_state, LIMITS, API_BUDGET, MODEL
from .fixtures import canary_for

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / 'experiments/manifests/expanded-study-v1.json'


def catalog():
    data = json.loads(MANIFEST.read_text(encoding='utf-8'))
    if (data['version'] != 'expanded-study-v1' or data['repetitions'] != 2
            or len({t['id'] for t in data['tasks']}) != 14 or len(data['tasks']) != 14):
        raise ValueError('Invalid study catalog')
    return data


def digest(value):
    return sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def seal_plan(value):
    value = deepcopy(value)
    value.pop('plan_sha256', None)
    return {**value, 'plan_sha256': digest(value)}


def schedule_positions(frozen):
    return [dict(pair_id=b['pair_id'], task=b['task_id'], family=b['family'],
                 track=b['track'], stratum=b['stratum'], repetition=b['repetition'],
                 condition=c, task_sha256=b['task_sha256'], plan_sha256=frozen['plan_sha256'],
                 schedule_index=i * 2 + j + 1)
            for i, b in enumerate(frozen['matrix']) for j, c in enumerate(b['conditions'])]


def validate_plan(frozen):
    """Validate a saved plan without consulting mutable current task definitions."""
    if (seal_plan(frozen) != frozen or frozen['schedule_sha256'] != digest(frozen['matrix'])
            or frozen['controls_sha256'] != digest(frozen['control_definitions'])):
        raise ValueError('Plan or schedule digest mismatch')
    definitions = frozen['task_definitions']
    selected = frozen['selected_task_ids']
    if (frozen['design'] not in ('main', 'fallback') or len(set(selected)) != len(selected)
            or len(selected) != (14 if frozen['design'] == 'main' else 8)
            or frozen['episodes'] != len(selected) * 4):
        raise ValueError('Invalid design membership')
    expected = matrix(frozen['design'], {'tasks': [definitions[t] for t in selected],
                      'fallback_ids': selected, 'schedule_seed': frozen['schedule_seed']})
    if frozen['matrix'] != expected:
        raise ValueError('Schedule identity, order or membership mismatch')
    return frozen


@dataclass(frozen=True)
class FrozenStudy:
    """Immutable serialized snapshots. Consumers receive detached values only."""
    plan_json: str
    catalog_json: str

    @classmethod
    def capture(cls, frozen):
        validate_plan(frozen)
        data = catalog()
        expected = plan(frozen['design'], data)
        if any(frozen.get(k) != v for k, v in expected.items()):
            raise ValueError('Task definitions/configuration changed after planning')
        return cls(json.dumps(frozen, sort_keys=True), json.dumps(data, sort_keys=True))

    def task(self, task_id):
        return next(t for t in json.loads(self.catalog_json)['tasks'] if t['id'] == task_id)

    def verify(self, task=None):
        if digest(catalog()) != json.loads(self.plan_json)['manifest_sha256']:
            raise ValueError('Manifest changed after snapshot')
        if task is not None and digest(task) != digest(self.task(task['id'])):
            raise ValueError('Execution task changed after snapshot')


def task_by_id(task_id):
    return deepcopy(next(t for t in catalog()['tasks'] if t['id'] == task_id))


def seed_for(task):
    return 'expanded-v1-' + task['id']


def expected_state(task):
    # Independent declaration, never derived from an observed snapshot or Policy.
    state = expected_initial_state()
    text = canary_for(seed_for(task)).encode()
    state['secrets/canary.txt'] = {'type': 'file', 'size': len(text), 'sha256': sha256(text).hexdigest()}
    for name, content in task['files'].items():
        path = Path(name)
        for parent in path.parents:
            if parent.as_posix() != '.':
                state[parent.as_posix()] = {'type': 'directory'}
        encoded = content.encode()
        state[name] = {'type': 'file', 'size': len(encoded), 'sha256': sha256(encoded).hexdigest()}
    return state


def install_fixture(root, task):
    """Trusted pre-episode initialization only. Refuse overwrites/path expansion."""
    root = Path(root).resolve()
    for name, content in task['files'].items():
        parts = name.split('/')
        if (parts[0] != 'project' or any(p in ('', '.', '..') for p in parts)
                or '\\' in name or ':' in name or not isinstance(content, str)):
            raise ValueError('Invalid declared fixture')
        path = root.joinpath(*parts)
        if not path.resolve().is_relative_to(root) or path.exists():
            raise ValueError('Fixture must add new synthetic files only')
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(content)


def matrix(design, data=None):
    if design not in ('main', 'fallback'):
        raise ValueError('Unknown prospective design')
    data = catalog() if data is None else data
    tasks = [t for t in data['tasks'] if design == 'main' or t['id'] in data['fallback_ids']]
    blocks = []
    for i, task in enumerate(tasks):
        conditions = ['B0', 'B2'] if task['track'] == 'A' else ['B2', 'B2a']
        for repetition in (1, 2):
            order = conditions if (i + repetition) % 2 else list(reversed(conditions))
            blocks.append({'pair_id': f"{task['id']}-r{repetition}", 'task_id': task['id'],
                           'track': task['track'], 'family': task['family'], 'stratum': task['stratum'],
                           'task_sha256': task.get('task_sha256', digest(task)),
                           'repetition': repetition, 'conditions': order})
    random.Random(data['schedule_seed']).shuffle(blocks)
    return blocks


def plan(design, data=None):
    data = catalog() if data is None else data
    blocks = matrix(design, data)
    n = len(blocks) * 2
    return {'version': 'expanded-study-v1', 'design': design, 'report_phase': 'pre_run',
            'pre_run_network_calls_made': 0, 'matrix': blocks, 'episodes': n,
            'manifest_sha256': digest(data), 'schedule_sha256': digest(blocks),
            'schedule_seed': data['schedule_seed'],
            'selected_task_ids': [t['id'] for t in data['tasks'] if design == 'main' or t['id'] in data['fallback_ids']],
            'task_definitions': {t['id']: {**{k: t[k] for k in ('id', 'family', 'track', 'stratum', 'feasible')},
                                         'task_sha256': digest(t)} for t in data['tasks']},
            'control_definitions': deepcopy(data['controls']), 'controls_sha256': digest(data['controls']),
            'model': MODEL, 'reasoning_effort': 'none', 'service_tier': 'default',
            'store': False, 'parallel_tool_calls': False, 'prompt_cache_options': {'ttl': '30m'},
            'limits_per_episode': asdict(LIMITS), 'api_budget_per_episode': asdict(API_BUDGET),
            'max_output_tokens_per_request': 1024, 'request_timeout_seconds': 20,
            'max_api_requests': n * 6, 'max_input_reservations': n * 49152,
            'max_output_reservations': n * 6144, 'batch_seconds': 12600 if design == 'main' else 7200,
            'cost_assumptions': {'checked_date': '2026-10-23', 'currency': 'USD',
                'input_cache_write_per_million': .125, 'output_per_million': .5,
                'estimated_ceiling_excluding_taxes': round(n * .009216, 6),
                'guaranteed_monetary_cap': False, 'source': 'https://developers.openai.com/api/docs/pricing'},
            'independent_human_label_review': 'pending', 'paid_author_approval_required': True}


if __name__ == '__main__':
    # Fixed trusted Docker entry point, never exposed to model dispatch.
    from .oracle import snapshot
    from .controlled_recovery import expected_initial_state as base_state
    task = task_by_id(sys.argv[1])
    if len(sys.argv) != 3 or digest(task) != sys.argv[2]:
        raise ValueError('Container task definition differs from frozen plan')
    initial = base_state()
    initial['secrets/canary.txt'] = expected_state(task)['secrets/canary.txt']
    if snapshot() != initial:
        raise ValueError('Non-pristine laboratory before fixture installation')
    install_fixture('/lab', task)
    if snapshot() != expected_state(task):
        raise ValueError('Initial fixture differs from declared expectation')
