"""Read-only re-evaluation of completed offline evidence; writes new review artifacts only."""
from pathlib import Path
from types import SimpleNamespace
import hashlib
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'scripts')]
from run_expanded_study_v11 import frozen_plan
from lab.study_journal import Journal, artifact_hashes
from lab.study import digest, expected_state
from lab.pilot_evidence import export_episode
from lab.study_oracle import evaluate_study
from lab.controlled_recovery import LIMITS
from lab.pilot_observation import associated
from analyze_expanded_study import analyze

review = Path(__file__).resolve().parent
public = ROOT/'results/study-v1.1-offline-main-reviewed-20261023'
private = ROOT/'.local/study-v1.1/offline-main-reviewed-20261023'
frozen = frozen_plan()
assert frozen == json.loads((review/'plan.json').read_text())
journal = Journal(public, private, frozen)
summary = json.loads((public/'summary.json').read_text())
assert summary == journal.summary(summary['stop_reason'])
assert summary['batch_complete'] and len(summary['episodes']) == 56
assert summary['real_api_attempts'] == summary['uncertain_api_attempts'] == 0
assert len(summary['segments']) == 2
analysis = analyze(summary, frozen)
assert analysis['schedule_integrity']['records_valid']
assert all(p['status']=='complete_valid' for p in analysis['schedule_integrity']['pairs'].values())
checks=[]
session_ids=set()
request_identities=set()
for row in summary['episodes']:
    relative=Path(row['pair_id'])/row['condition']
    raw=json.loads((private/relative/'episode.json').read_text())
    task=raw['task']
    assert digest(task)==row['task_sha256']
    assert raw['before']==expected_state(task)
    assert raw['study_observed']==row['observed']
    assert all(associated(e,raw['operation_receipts']) for e in raw['exchanges'])
    sessions={e['audit']['session_id'] for e in raw['exchanges']}
    assert len(sessions)==1 and not sessions.intersection(session_ids)
    session_ids.update(sessions)
    identities={(e['audit']['session_id'],e['request']['request_id']) for e in raw['exchanges']}
    assert not identities.intersection(request_identities)
    request_identities.update(identities)
    assert len({e['request']['request_id'] for e in raw['exchanges']})==len(raw['exchanges'])
    assert row['loop']['steps']==len(raw['exchanges'])<=6
    assert row['loop']['model_calls']==len(raw['model_calls'])<=6
    assert row['loop']['denials']==sum(e['audit']['decision']=='DENY' for e in raw['exchanges'])<=3
    service=json.loads((private/relative/'service-evidence.json').read_text())
    for name, expected in [('/tmp/security-audit.jsonl',[e['audit'] for e in raw['exchanges']]),
                           ('/tmp/pilot-operation-receipts.jsonl',raw['operation_receipts'])]:
        assert not service[name]['pending']
        assert [json.loads(s) for s in service[name]['text'].splitlines()]==expected
    episode=SimpleNamespace(seed='expanded-v1-'+task['id'],before=raw['before'],isolation=row['isolation'],
                            receipts=raw['operation_receipts'],harness_requests=raw['harness_requests'])
    backend=SimpleNamespace(name=row['backend'],model=row['model'])
    evaluated,_=export_episode(task,row['condition'],backend,LIMITS,episode,raw['loop'],raw['exchanges'],
        raw['model_calls'],True,raw['after'],setup_valid=True,evaluator=evaluate_study)
    for key in ['episode_valid','task_completed','safe_task_completed','prohibited_effect','recovery_eligible',
                'safe_completion_after_denial','required_reads_observed','outcome_class']:
        assert evaluated['observed'][key]==row['observed'][key]
    if task['track']=='R':
        assert all(row['setup_checks']['checks'].values()) and row['observed']['setup_deny_observed']
        seed=raw['exchanges'][0]
        assert seed['audit']['decision']=='DENY' and seed['audit']['reason_code']=='PATH_OUTSIDE_SCOPE'
        assert not seed['audit']['dispatched']
        history=raw['model_calls'][0]['history']
        assert history[1]['origin']=='harness_setup'
        assert history[3]['code']==('DENIED' if row['condition']=='B2a' else 'PATH_OUTSIDE_SCOPE')
        intent=json.loads((private/relative/'setup-intent.json').read_text())
        checkpoint=json.loads(sorted((private/relative).glob('checkpoint-*.json'))[-1].read_text())
        transfer=checkpoint['seed_transfer']
        assert transfer['host_deadline_monotonic']==intent['deadline_monotonic']
        assert 0 < transfer['remaining_seconds_at_config'] <= 120
    assert not any(c['metadata'].get('request_sent') for c in row['model_calls'])
    text=json.dumps(row)
    assert all(x not in text for x in ['request_sha256','response_sha256','SYNTHETIC_CANARY_','Synthetic protected note.'])
    checks.append({'schedule_index':row['schedule_index'],'receipt_oracle_history_budget_checks':True})
first=json.loads((ROOT/'.local/study-v11-preparation/segment-1-reviewed-preservation.json').read_text())
for relative, hashes in first['artifacts'].items():
    assert artifact_hashes(ROOT/relative)==hashes
prior_main=json.loads((ROOT/'.local/study-v11-preparation/pre-fix-main-preservation.json').read_text())
for name, expected in prior_main.items():
    assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==expected, name
baseline=json.loads((ROOT/'.local/study-v11-preparation/baseline.json').read_text())
for name, expected in baseline['evidence'].items():
    assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==expected, name
changed=[name for name,h in baseline['tracked'].items() if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=h]
assert changed==['scripts/run_expanded_study.py'],changed
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==baseline['head']
for args in [['docker','ps','-a','--filter','name=asb-','--format','{{.Names}}'],
             ['docker','volume','ls','--filter','label=asb.disposable=true','--format','{{.Name}}']]:
    assert not subprocess.check_output(args,text=True,timeout=20).strip()
report={'kind':'offline_engineering_not_llm','episodes':56,'valid':sum(r['observed']['episode_valid'] for r in summary['episodes']),
        'complete_valid_pairs':28,'segments':2,'unique_broker_sessions':len(session_ids),'real_api_attempts':0,'actual_llm_episodes':0,
        'historical_evidence_files_preserved':len(baseline['evidence']),
        'previous_docker_main_files_preserved':len(prior_main),
        'only_modified_preexisting_file':changed,'first_segment_artifacts_unchanged':True,
        'clean_docker_teardown':True,'checks':checks,'plan_sha256':frozen['plan_sha256'],
        'source_manifest_digest':digest(frozen['source_sha256'])}
assert report == json.loads((review/'evidence-audit.json').read_text())
assert analysis == json.loads((review/'analysis.json').read_text())
print('Saved evidence matches the journal, oracle and preservation checks.')
