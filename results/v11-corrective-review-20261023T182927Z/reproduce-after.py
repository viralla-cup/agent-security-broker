"""Repeat the same P1/P2 counterexamples against the corrected image, offline."""
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import hashlib

# Reuse the exact pre-correction fault injection without its old-behavior asserts.
namespace={}
source=(Path(__file__).parent/'reproduce-before.py').read_text()
exec(compile(source.split('\nwith TemporaryDirectory() as temp:')[0], 'reproduce-before.py', 'exec'), namespace)
with TemporaryDirectory() as temp:
    root=Path(temp);rows=[]
    for case in ('healthy','worker','service_save'):
        path=root/case;path.mkdir();rows.append(namespace['p1'](path,case))
    path=root/'head';path.mkdir()
    try:
        namespace['p2'](path)
        raise AssertionError('Previously reproduced unsafe resume remains possible')
    except namespace['t'].JournalError:
        assert (path/'private/RESUME_BLOCKED').is_dir()
    assert [r['timeout_continuation_accepted'] for r in rows]==[True,False,False]
    result={'kind':'offline_engineering_reproduction','actual_provider_calls':0,'P1':rows,
        'P2':{'reload_rejected':True,'out_of_chain_block_persisted':True,
              'resumed_schedule_index':None,'api_attempts':0},
        'source_sha256':{name:hashlib.sha256(Path('/app',name).read_bytes()).hexdigest()
            for name in ('scripts/run_expanded_study.py','scripts/run_expanded_study_v11.py','src/lab/study_journal.py')}}
    print(json.dumps(result,indent=2))
