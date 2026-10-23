"""Native filesystem reproduction; synthetic ledger only, no provider or Docker."""
from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import json
import os
sys.path.insert(0, str(Path.cwd()/'src'))
from lab.study import plan, seal_plan
from lab.study_journal import Journal, JournalError, atomic_json

p=seal_plan({**plan('main'),'version':'expanded-study-v1.1','request_timeout_seconds':30,
             'source_sha256':{},'protocol_sha256':'synthetic-native-engineering-check'})
def create(root):
    raw=root/'private';raw.mkdir(parents=True)
    j=Journal.create(root/'public',raw,p,'native-offline-check','openai')
    old=j.head.copy()
    j.append('authorization_reserved',number=1,approved_head=old,authorization_sha256='synthetic',
             authorization_id_sha256='synthetic',review_sha256='synthetic-not-attestation')
    return j,old
def load(j):return Journal(j.public,j.private,p)
def blocked(j):
    try:load(j)
    except JournalError:return True
    return False
with TemporaryDirectory(prefix='v11-native-') as name:
    root=Path(name);j,old=create(root/'detected');current=j.head.copy()
    atomic_json(j.directory/'HEAD.json',old,replace=True)
    try:j.append('run_stop',reason='CHECKPOINT_OR_INPUT_FAILURE')
    except JournalError:pass
    before=blocked(j)
    atomic_json(j.directory/'HEAD.json',current,replace=True)
    after=blocked(j)
    other,old=create(root/'ordinary-crash')
    atomic_json(other.directory/'HEAD.json',old,replace=True)
    recovered=load(other)
    result={'kind':'offline_engineering','platform':sys.platform,'actual_provider_calls':0,
        'detected_rollback_blocks_reload':before,'restored_head_still_blocked':after,
        'marker_persisted':j.blocker.is_dir(),'ordinary_tail_recovers':len(recovered.state['authorizations'])==1,
        'ordinary_tail_not_quarantined':not recovered.blocker.exists()}
    assert all(result[k] for k in ('detected_rollback_blocks_reload','restored_head_still_blocked',
        'marker_persisted','ordinary_tail_recovers','ordinary_tail_not_quarantined'))
    print(json.dumps(result,indent=2))
