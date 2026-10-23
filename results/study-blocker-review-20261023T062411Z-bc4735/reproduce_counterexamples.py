"""Offline counterexamples against archived candidate and current corrected code."""
from pathlib import Path
import sys,json,zipfile,types,tempfile,copy,datetime,uuid,hashlib
sys.path[:0]=['scripts','src']
import lab.study as study
import run_expanded_study as new
import analyze_expanded_study as analysis
from run_replay import write_json,ROOT
old_zip=ROOT/'results/study-review-20261022T204654Z/source_snapshot.zip'
def old_module(name, filename):
 with zipfile.ZipFile(old_zip) as z: code=z.read(filename)
 m=types.ModuleType(name); m.__file__=filename;sys.modules[name]=m;exec(compile(code,filename,'exec'),m.__dict__);return m
old=old_module('archived_runner','scripts/run_expanded_study.py')
old_analysis=old_module('archived_analysis','scripts/analyze_expanded_study.py')
results={'kind':'synthetic_offline_counterexamples_not_llm','archived_source_zip':old_zip.relative_to(ROOT).as_posix(),'archived_source_sha256':hashlib.sha256(old_zip.read_bytes()).hexdigest(),'real_api_attempts':0,'approval_records_created':False}
frozen=new.frozen_plan('main')
with tempfile.TemporaryDirectory(prefix='asb-counterexample-') as temp:
 base=Path(temp); manifest=base/'manifest.json';manifest.write_bytes(study.MANIFEST.read_bytes());original=study.MANIFEST
 try:
  study.MANIFEST=manifest
  planned=new.frozen_plan('main')
  data=json.loads(manifest.read_text());target=planned['matrix'][0]['task_id'];t=next(t for t in data['tasks'] if t['id']==target);t['prompt']+=' REVIEWER MUTATION';manifest.write_text(json.dumps(data))
  received=[]
  def execute(task,condition,backend,*args,**kw):
   received.append(task['prompt'])
   return {'task':task['id'],'condition':condition,'model_calls':[],'observed':{'episode_valid':False,'prohibited_effect':False},'real_api_attempts':0,'actual_llm_episodes':0},None
  a=base/'old';b=base/'new';a.mkdir();b.mkdir()
  before=old.run_batch(planned,a,a,lambda task:None,execute=execute)
  after=new.run_batch(planned,b,b,lambda task:(_ for _ in ()).throw(AssertionError('No backend')),execute=execute)
  results['manifest_after_plan']={'old_executed_changed_prompt_under_original_digest':len(received)==1 and received[0].endswith('REVIEWER MUTATION'),'new_stop':after['stop_reason'],'new_started_positions':len(after['started_positions'])}
 finally: study.MANIFEST=original
positions=study.schedule_positions(frozen)
def row(p,success):
 o={k:False for k in ('prohibited_effect','task_completed','safe_task_completed','recovery_eligible','safe_completion_after_denial','correct_refusal','targeted_attack_effect')}
 o.update(episode_valid=True,observation_complete=True,task_feasible=True,recovery_eligible=True,safe_completion_after_denial=success,model_origin_targeted_proposals=0)
 return {**p,'observed':o,'model_calls':[],'observed_model_calls':0,'loop':{'stop_reason':'MODEL_STOP'},'elapsed_seconds':0,'evidence_kind':'synthetic_counterexample','real_api_attempts':0,'actual_llm_episodes':0}
def summarize(rows):
 return {'episodes':rows,'design':'main','plan_sha256':frozen['plan_sha256'],'planned_episodes':56,'scheduled':positions,'unstarted':positions[2:],'real_api_attempts':0}
for defect in ['mixed_task_repetition','duplicate_condition']:
 rows=[row(positions[0],True),row(positions[1],False)]
 if defect=='mixed_task_repetition':rows[0].update(task='R02',family='R02',repetition=2)
 else:rows.insert(0,row(positions[0],False))
 before=old_analysis.paired(rows,'safe_completion_after_denial',['B2a','B2'])
 after=analysis.analyze(summarize(rows),frozen)
 results[defect]={'old_paired_difference_pp':before['paired_difference_pp'],'new_paired_difference_pp':after['R_feasible_combined']['paired_difference_pp'],'new_complete_pairs':after['R_feasible_combined']['complete_pairs'],'new_integrity':after['schedule_integrity']}
class MemoryPath:
 def __init__(self,p):self.p=str(p)
 def __truediv__(self,p):return MemoryPath(self.p+'/'+p)
 def read_text(self,*a,**kw):return json.dumps(memory[self.p])
controls={'all_passed':True,'rows':[]}
review={'independent_labels_reviewed':True,'reviewer':'SYNTHETIC MEMORY-ONLY COUNTEREXAMPLE','approved_plan_sha256':frozen['plan_sha256'],'approved_binding':new.control_binding(frozen),'approved_controls_sha256':study.digest(controls),'offline_evidence_directory':'memory'}
memory={'review':review,'memory/plan.json':frozen,'memory/controls.json':controls,'memory/metadata.json':{'source_sha256':frozen['source_sha256'],'image_id':'sha256:synthetic','copied_source_files_verified':len(frozen['source_sha256'])-2}}
a,b=old.Path,new.Path
try:
 old.Path=new.Path=MemoryPath
 old_accept=old.require_review('review',frozen)==review
 try:new.require_review('review',frozen);new_accept=True
 except ValueError:new_accept=False
 results['empty_controls']={'old_accepted':old_accept,'new_accepted':new_accept,'filesystem_review_record_created':False}
finally:old.Path=a;new.Path=b
assert results['manifest_after_plan']['old_executed_changed_prompt_under_original_digest']
assert results['manifest_after_plan']['new_started_positions']==0
assert all(results[k]['old_paired_difference_pp']==100 and results[k]['new_paired_difference_pp'] is None for k in ['mixed_task_repetition','duplicate_condition'])
assert results['empty_controls']['old_accepted'] and not results['empty_controls']['new_accepted']
out=ROOT/'results'/('study-blocker-review-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:6]);out.mkdir()
write_json(out/'counterexamples.json',results)
(out/'reproduce_counterexamples.py').write_text(Path(__file__).read_text(encoding='utf-8-sig'),encoding='utf-8')
for design in ['main','fallback']:write_json(out/(design+'-plan.json'),new.frozen_plan(design))
print(out)
print(json.dumps({k:v for k,v in results.items() if k not in ['mixed_task_repetition','duplicate_condition']},indent=2))
(ROOT/'.local/study-blocker-correction-20261023/review-dir.txt').write_text(str(out))
