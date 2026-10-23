"""Create content-free verification metadata; never read credentials or call a model."""
from pathlib import Path
import sys
import json
import hashlib
import subprocess
import zipfile
import difflib
sys.path[:0]=['src','scripts']
import run_expanded_study_v11 as runner
from lab.study import digest, plan
from run_replay import source_manifest, COMMON, IMAGE

root=Path.cwd();out=Path(__file__).resolve().parent
location=json.loads((root/'.local/v11-corrective-current.json').read_text())
before=json.loads((Path(location['private'])/'before.json').read_text())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(name,value):(out/name).write_text(json.dumps(value,indent=2,sort_keys=True)+'\n',encoding='utf-8')

changed=[name for name,h in before['inputs'].items() if sha(root/name)!=h]
expected={'scripts/run_expanded_study.py','scripts/run_expanded_study_v11.py','src/lab/study_journal.py',
          'tests/test_study_v11.py','experiments/expanded-study-v1.1.md','docs/expanded-study-v1.1-runbook.md'}
assert set(changed)==expected,changed
damaged=[name for name,h in before['evidence'].items() if not (root/name).is_file() or sha(root/name)!=h]
assert not damaged, 'Historical evidence changed'
tracked_changed=[name for name,h in before['tracked'].items() if not (root/name).is_file() or sha(root/name)!=h]
assert set(tracked_changed)=={'scripts/run_expanded_study.py'},tracked_changed
head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
assert head==before['head']
before_repro=json.loads((out/'reproduce-before-stdout.txt').read_text())
assert all(before['inputs'][n]==h for n,h in before_repro['source_sha256'].items())
sources=source_manifest();frozen=runner.frozen_plan()
assert frozen['source_sha256']==sources
after_repro=json.loads((out/'reproduce-after-stdout.txt').read_text())
assert all(sources[n]==h for n,h in after_repro['source_sha256'].items())
old=json.loads((root/'results/v11-review-20261023T171100Z/plan.json').read_text())
changed_plan=[k for k in old.keys()|frozen.keys() if old.get(k)!=frozen.get(k)]
assert set(changed_plan)=={'execution_rules','source_sha256','protocol_sha256','plan_sha256'},changed_plan
scientific=plan('main')
assert all(frozen[k]==v for k,v in scientific.items() if k not in ('version','request_timeout_seconds'))
save('plan.json',frozen);save('source-manifest.json',sources)
checks=root/'results/checks-20261023T183528Z-2e2990'
metadata=json.loads((checks/'metadata.json').read_text())
assert metadata['source_sha256']==sources and metadata['exit_code']==0
assert '508 passed' in (checks/'stdout.txt').read_text()
assert '70 passed' in (out/'focused-final-stdout.txt').read_text()
image=subprocess.check_output(['docker','image','inspect',IMAGE,'--format','{{.Id}}'],text=True).strip()
assert metadata['image_id']==image
# Validate copied image bytes against this working tree without launching any
# experiment, constructing fixtures, reading credentials or contacting providers.
copied={n:h for n,h in sources.items() if n not in ('Dockerfile','.dockerignore')}
probe="import json,hashlib;from pathlib import Path;print(json.dumps({n:hashlib.sha256(Path('/app',n).read_bytes()).hexdigest() for n in "+repr(list(copied))+"}))"
cmd=['docker','run','--rm',*COMMON,IMAGE,'python','-c',probe]
actual=json.loads(subprocess.check_output(cmd,text=True))
assert actual==copied
containers=subprocess.check_output(['docker','ps','-a','--filter','name=asb-','--format','{{.Names}}'],text=True).strip()
volumes=subprocess.check_output(['docker','volume','ls','--filter','label=asb.disposable=true','--format','{{.Name}}'],text=True).strip()
assert not containers and not volumes
files=sorted(set(sources)|{'docs/expanded-study-v1.1-runbook.md','experiments/expanded-study-v1.1.md',
                         'experiments/expanded-study-v1.md','docs/controlled-recovery-proposal.md'})
with zipfile.ZipFile(out/'source-snapshot.zip','w',zipfile.ZIP_DEFLATED) as z:
    for name in files:z.write(root/name,name)
delta=[]
with zipfile.ZipFile(out/'before-source.zip') as z:
    for name in sorted(expected|{'tests/test_study_v11_corrective.py'}):
        original=z.read(name).decode().replace('\r\n','\n').splitlines(keepends=True) if name in z.namelist() else []
        current=(root/name).read_text().splitlines(keepends=True)
        delta.extend(difflib.unified_diff(original,current,fromfile='before/'+name,tofile='after/'+name))
(out/'corrective-only.patch').write_text(''.join(delta),encoding='utf-8')
save('verification.json',{
    'kind':'author_agent_engineering_evidence_not_independent_attestation','independent_review_passed':False,
    'baseline_commit':head,'actual_provider_calls':0,'experiment_launches':0,
    'new_tests':22,'targeted_tests_passed':70,'full_suite_passed':508,
    'full_suite_directory':checks.relative_to(root).as_posix(),
    'source_manifest_digest':digest(sources),'plan_sha256':frozen['plan_sha256'],
    'snapshot_sha256':sha(out/'source-snapshot.zip'),'source_files':len(sources),
    'image_id':image,'copied_source_files_verified':len(copied),'test_isolation':COMMON,
    'docker_engine':subprocess.check_output(['docker','version','--format','{{.Server.Version}}'],text=True).strip(),
    'remaining_asb_containers':0,'remaining_disposable_volumes':0,
    'preserved_historical_evidence_files':len(before['evidence']),'changed_historical_evidence_files':0,
    'unchanged_existing_input_files':len(before['inputs'])-len(changed),
    'changed_existing_inputs':sorted(changed),'new_input_files':['tests/test_study_v11_corrective.py'],
    'tracked_changes_since_task_start':tracked_changed,'changed_plan_fields':sorted(changed_plan),
    'scientific_design_unchanged':True,'planned_episodes':56,'prior_plan_sha256':old['plan_sha256'],
    'new_live_approval_record_created':False,'fresh_production_controls_executed':False,
    'full_fake_main_launched':False})
print(json.dumps({'source_manifest_digest':digest(sources),'plan_sha256':frozen['plan_sha256'],
    'image_id':image,'historical_evidence_files_unchanged':len(before['evidence']),
    'copied_source_files_verified':len(copied)},indent=2))
