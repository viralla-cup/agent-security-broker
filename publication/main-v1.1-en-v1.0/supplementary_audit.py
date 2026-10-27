"""Additional read-only checks; writes one new aggregate result without private data."""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import sys

p = argparse.ArgumentParser()
for k in ('repo', 'public', 'private', 'output'):
    p.add_argument('--' + k, type=Path, required=True)
a = p.parse_args()
sys.path[:0] = [str(a.repo.resolve() / 'scripts'), str(a.repo.resolve() / 'src')]
from agent_loop import SeededState
from lab.pilot_observation import proposal_of

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

s = read(a.public / 'summary.json')
checked_calls = 0
stops = Counter()
for row in s['episodes']:
    raw = read(a.private / row['pair_id'] / row['condition'] / 'episode.json')
    xs, calls, seeds = raw['exchanges'], raw['model_calls'], raw['harness_requests']
    prefix = [{'kind': 'task', 'text': raw['task']['prompt']}]
    if seeds:
        prefix = SeededState(seeds[0]['request'], xs[0]['response'], 0).history(raw['task']['prompt'])
    seen = len(seeds)
    for call in calls:
        expected = prefix + [item for x in xs[len(seeds):seen] for item in (
            {'kind': 'proposal', **proposal_of(x['request'])}, {'kind': 'tool_result', **x['response']})]
        assert call['history'] == expected
        assert len(call['observed_tool_event_ids']) == seen
        checked_calls += 1
        if call.get('executed_event_id'):
            assert call['executed_event_id'] == xs[seen]['audit']['event_id']
            seen += 1
    assert seen == len(xs)
    if row['loop']['stop_reason'] == 'RETRY_LIMIT':
        last = calls[-1]
        duplicate = last.get('proposal') in [proposal_of(x['request']) for x in xs]
        assert duplicate or last['outcome'] == 'INVALID_PROPOSAL'
        stops['duplicate_proposal' if duplicate else 'invalid_proposal'] += 1
    if row['loop']['stop_reason'] == 'STEP_LIMIT':
        assert len(xs) == row['limits']['max_steps'] == 6
    if row['loop']['stop_reason'] == 'COMPLETE_CLAIM':
        assert calls[-1]['proposal'] == {'stop': 'complete'}
    if row['loop']['stop_reason'] == 'NO_SAFE_CONTINUATION':
        assert calls[-1]['proposal'] == {'stop': 'no_safe_continuation'}
root_meta = read(a.public / 'metadata.json')
first_seg = s['segments'][0]
seg_meta = read(a.public / 'segments/0001' / first_seg['metadata_file'])
assert root_meta == {k: v for k, v in seg_meta.items() if k not in ('preflight_id', 'controls_sha256')}
for seg in s['segments']:
    meta = read(a.public / 'segments' / f"{seg['number']:04d}" / seg['metadata_file'])
    pre = a.private / meta['preflight_id']
    assert read(pre / 'runtime.json') == {k: v for k, v in meta.items() if k not in ('preflight_id', 'controls_sha256')}
    assert read(pre / 'plan.json') == read(a.public / 'plan.json')
result = dict(status='CHECKS_PASSED_PENDING_INDEPENDENT_REVIEW', exact_histories_checked=checked_calls,
    task_and_setup_prefixes_equal=True, all_operations_accounted_for=True,
    retry_limit_causes=dict(stops), root_and_segment_metadata_consistent=True,
    preflight_plan_runtime_consistent=True, observed_process_exit_code='not independently captured by this audit',
    original_records_modified=False)
with a.output.open('x', encoding='utf-8', newline='\n') as f:
    json.dump(result, f, indent=2); f.write('\n')
print(json.dumps(result))
