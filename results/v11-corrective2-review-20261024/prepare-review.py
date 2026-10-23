"""Bind the second corrective revision and verify preservation; no provider I/O."""
from pathlib import Path
import json
import hashlib
import zipfile
import difflib
import subprocess
import sys
sys.path[:0]=['src','scripts']
from run_replay import source_manifest, COMMON, IMAGE
from lab.study import digest, plan
import run_expanded_study_v11 as runner

root=Path.cwd();out=Path(__file__).resolve().parent
before=json.loads((root/'.local/v11-corrective2-20261024/before.json').read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(name,value):(out/name).write_text(json.dumps(value,indent=2,sort_keys=True)+'\n',encoding='utf-8')
expected={'src/lab/study_journal.py','scripts/run_expanded_study_v11.py',
    'tests/test_study_v11.py','tests/test_study_v11_corrective.py',
    'experiments/expanded-study-v1.1.md','docs/expanded-study-v1.1-runbook.md'}
added={'src/lab/study_timeout.py','tests/study_timeout_helpers.py',
       'tests/study_integrity_crash.py','tests/test_study_v11_second_corrective.py'}
changed={p for p,h in before['inputs'].items() if sha(root/p)!=h}
assert changed==expected,changed
damaged=[p for p,h in before['evidence'].items() if not (root/p).is_file() or sha(root/p)!=h]
assert not damaged,'Historical evidence changed'
head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();assert head==before['head']
sources=source_manifest();frozen=runner.frozen_plan()
previous=json.loads((root/'results/v11-corrective-review-20261023T182927Z/plan.json').read_text())
plan_changes={k for k in frozen.keys()|previous.keys() if frozen.get(k)!=previous.get(k)}
assert plan_changes=={'source_sha256','protocol_sha256','plan_sha256','execution_rules'}
assert all(frozen[k]==v for k,v in plan('main').items() if k not in ('version','request_timeout_seconds'))
checks=max(root.glob('results/checks-*/metadata.json'),key=lambda p:p.stat().st_mtime).parent
metadata=json.loads((checks/'metadata.json').read_text())
assert metadata['source_sha256']==sources and metadata['exit_code']==0
assert '549 passed' in (checks/'stdout.txt').read_text()
assert '111 passed' in (out/'targeted-final.txt').read_text()
repro_before=json.loads((out/'reproduce-before-stdout.txt').read_text())
repro_after=json.loads((out/'reproduce-after-final-stdout.txt').read_text())
assert all(before['inputs'][p]==h for p,h in repro_before['source_sha256'].items())
assert all(sources[p]==h for p,h in repro_after['source_sha256'].items())
image=subprocess.check_output(['docker','image','inspect',IMAGE,'--format','{{.Id}}'],text=True).strip()
assert metadata['image_id']==image
copied={p:h for p,h in sources.items() if p not in ('Dockerfile','.dockerignore')}
probe="import json,hashlib;from pathlib import Path;print(json.dumps({p:hashlib.sha256(Path('/app',p).read_bytes()).hexdigest() for p in "+repr(list(copied))+"}))"
assert json.loads(subprocess.check_output(['docker','run','--rm',*COMMON,IMAGE,'python','-c',probe],text=True))==copied
assert not subprocess.check_output(['docker','ps','-a','--filter','name=asb-','--format','{{.Names}}'],text=True).strip()
assert not subprocess.check_output(['docker','volume','ls','--filter','label=asb.disposable=true','--format','{{.Name}}'],text=True).strip()
save('plan.json',frozen);save('source-manifest.json',sources)
files=sorted(set(sources)|{'docs/expanded-study-v1.1-runbook.md','experiments/expanded-study-v1.1.md',
                         'experiments/expanded-study-v1.md','docs/controlled-recovery-proposal.md'})
with zipfile.ZipFile(out/'source-snapshot.zip','w',zipfile.ZIP_DEFLATED) as z:
    for name in files:z.write(root/name,name)
delta=[]
with zipfile.ZipFile(out/'before-source.zip') as z:
    for name in sorted(expected|added):
        old=z.read(name).decode().replace('\r\n','\n').splitlines(keepends=True) if name in z.namelist() else []
        delta.extend(difflib.unified_diff(old,(root/name).read_text().splitlines(keepends=True),fromfile='before/'+name,tofile='after/'+name))
(out/'corrective-only.patch').write_text(''.join(delta),encoding='utf-8')
save('verification.json',{'kind':'implementer_engineering_evidence_not_independent_attestation',
    'independent_review_passed':False,'baseline_commit':head,'actual_provider_calls':0,
    'experiment_launches':0,'new_tests':41,'targeted_passed':111,'full_suite_passed':549,
    'full_suite_directory':checks.relative_to(root).as_posix(),
    'source_manifest_digest':digest(sources),'plan_sha256':frozen['plan_sha256'],
    'source_snapshot_sha256':sha(out/'source-snapshot.zip'),'image_id':image,
    'source_files':len(sources),'copied_source_files_verified':len(copied),
    'test_container_isolation':COMMON,'preserved_historical_files':len(before['evidence']),
    'changed_historical_files':0,'changed_existing_inputs':sorted(changed),'new_inputs':sorted(added),
    'unchanged_existing_inputs':len(before['inputs'])-len(changed),
    'planned_positions':56,'planned_pairs':28,'scientific_design_unchanged':True,
    'manifest_sha256':frozen['manifest_sha256'],'schedule_sha256':frozen['schedule_sha256'],
    'changed_plan_fields':sorted(plan_changes),'fresh_production_controls_executed':False,
    'new_review_or_paid_authorization_created':False,'remaining_experiment_resources':0})
print(json.dumps({'source_manifest_digest':digest(sources),'plan_sha256':frozen['plan_sha256'],
    'image_id':image,'historical_files_preserved':len(before['evidence']),
    'full_suite_directory':checks.relative_to(root).as_posix()},indent=2))
