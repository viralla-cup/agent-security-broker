"""Child-process fault boundaries. No transport, model, or actual authorization."""
import sys
from pathlib import Path
sys.path[:0]=['src','scripts','tests']
import os
import json
import test_study_v11 as t
import lab.study_journal as module

root=Path(sys.argv[1]);stage=sys.argv[2]
j=t.create(root,'openai');old=j.head.copy()
j.append('authorization_reserved',number=1,approved_head=j.head.copy(),
    authorization_sha256='synthetic-1',authorization_id_sha256='synthetic-1',review_sha256='synthetic-only')
(root/'head-before.json').write_text(json.dumps(j.head))
def die():os._exit(37)
real_mkdir,real_rmdir,real_read=Path.mkdir,Path.rmdir,Path.read_text
real_atomic=module.atomic_json
if stage in ('detected_before_block','block_creation_failure','load_detected_before_block'):
    module.atomic_json(j.directory/'HEAD.json',old if stage!='load_detected_before_block' else {},replace=True)
if stage in ('detected_before_block','load_detected_before_block'):
    module.Journal.block_resume=lambda self:die()
def mkdir(path,*a,**k):
    if path.name=='VERIFYING' and stage=='before_arm':die()
    if path.name=='RESUME_BLOCKED' and stage=='block_creation_failure':raise OSError('injected marker failure')
    result=real_mkdir(path,*a,**k)
    if path.name=='VERIFYING' and stage in ('arm_created','load_arm_created'):die()
    return result
def read(path,*a,**k):
    if path.name=='HEAD.json' and stage in ('during_check','load_during_check'):die()
    return real_read(path,*a,**k)
def rmdir(path,*a,**k):
    if path.name=='VERIFYING' and stage in ('before_clear','load_before_clear'):die()
    result=real_rmdir(path,*a,**k)
    if path.name=='VERIFYING' and stage in ('after_clear','load_after_clear'):die()
    return result
def atomic(path,*a,**k):
    if Path(path).stem.isdigit() and stage=='before_event':die()
    result=real_atomic(path,*a,**k)
    if Path(path).stem.isdigit() and stage=='committed_tail':die()
    if Path(path).name=='HEAD.json' and stage=='after_head':die()
    return result
Path.mkdir,Path.rmdir,Path.read_text=mkdir,rmdir,read
module.atomic_json=atomic
try:
    if stage.startswith('load_'):
        t.reload(j)
    else:
        j.append('authorization_reserved',number=1,approved_head=j.head.copy(),
            authorization_sha256='synthetic-2',authorization_id_sha256='synthetic-2',review_sha256='synthetic-only')
except OSError:
    if stage!='block_creation_failure':raise
die()
