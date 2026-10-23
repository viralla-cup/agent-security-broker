"""Append-only v1.1 execution ledger. No network, policy, or model capabilities."""

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import uuid

from .study import digest, schedule_positions, validate_plan
from .study_timeout import consistent_timeout


class JournalError(ValueError):
    pass


def utc():
    return datetime.now(timezone.utc).isoformat()


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atomic_json(path, value, *, replace=False):
    path = Path(path)
    if path.exists() and not replace:
        raise JournalError('Immutable artifact already exists')
    temp = path.with_name('.pending-' + uuid.uuid4().hex)
    with temp.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, sort_keys=True, ensure_ascii=True)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)  # All writers hold the logical-run OS lock.
    if os.name != 'nt':
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


class RunLock:
    """Nonblocking advisory lock; kernel releases ownership after a crash."""
    def __init__(self, path):
        self.path = Path(path)

    def __enter__(self):
        self.stream = self.path.open('a+b')
        if self.stream.tell() == 0:
            self.stream.write(b'0'); self.stream.flush()
        self.stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.stream.close()
            raise JournalError('Logical run already locked') from None
        return self

    def __exit__(self, *_):
        self.stream.close()


def artifact_hashes(root, *, sync=False):
    result = {}
    for path in sorted(Path(root).rglob('*')):
        if path.is_file():
            if path.is_symlink():
                raise JournalError('Artifact symlink rejected')
            if sync:
                with path.open('r+b') as stream:
                    stream.flush(); os.fsync(stream.fileno())
            result[path.relative_to(root).as_posix()] = file_hash(path)
    return result


def check_artifacts(root, hashes):
    if not hashes or artifact_hashes(root) != hashes:
        raise JournalError('Missing, changed or additional committed evidence')


def timeout_evidence_ok(row):
    obs = row['observed']
    return (row['loop']['stop_reason'] == 'BACKEND_TIMEOUT'
            and all(row.get('operational_health', {}).get(key) is True for key in (
                'worker_returned', 'worker_healthy', 'execution_ok', 'observation_ok',
                'service_collected', 'service_saved', 'broker_execution_ok'))
            and row.get('setup_checks', {}).get('valid') is True
            and obs.get('observation_complete') is True
            and obs.get('initial_files_unchanged') is True
            and obs.get('action_origin_counts', {}).get('unattributed') == 0
            and obs.get('outcome_class') == 'infrastructure_failure'
            and bool(row['model_calls'])
            and row['model_calls'][-1].get('outcome') == 'BACKEND_TIMEOUT'
            and row['model_calls'][-1]['metadata'].get('request_sent') is True
            and (row['condition'] == 'B0' or not obs['prohibited_effect']))


def verified_timeout_evidence(row, private, **trusted):
    """Do not infer isolated timeout health from an outcome label or fresh Docker."""
    try:
        return timeout_evidence_ok(row) and consistent_timeout(row, private, **trusted)
    except (OSError, ValueError, TypeError, KeyError, IndexError, AttributeError):
        return False


class Journal:
    """Private hash chain; public reports are derived, never the resume authority."""
    def __init__(self, public, private, frozen):
        self.public, self.private, self.plan = Path(public), Path(private), frozen
        validate_plan(frozen)
        if frozen['version'] != 'expanded-study-v1.1' or frozen['design'] != 'main':
            raise JournalError('Only v1.1 Main can be resumed')
        self.directory = self.private / 'journal'
        self.positions = schedule_positions(frozen)
        self.state = dict(created=None, segments=[], authorizations=[], active=None, started={}, finished={}, requests={},
                          timeouts=0, timeout_positions=[], consecutive_timeouts=0, terminal=None, reported_models=[])
        self.head = {'sequence': 0, 'sha256': '0' * 64}
        self.blocker = self.private / 'RESUME_BLOCKED'
        self.verifying = self.private / 'VERIFYING'
        if self.blocker.exists() or self.verifying.exists():
            raise JournalError('Permanent integrity stop; ordinary resume is forbidden')
        self.verify_integrity(self._load)

    def verify_integrity(self, check):
        """Persist verification intent BEFORE any integrity-sensitive reads.

        Unfinished verification blocks resume, even if termination precedes
        block_resume(). Clear only on success, before ordinary journal writes.
        """
        if self.blocker.exists() or self.verifying.exists():
            raise JournalError('Blocked or interrupted integrity verification')
        self.verifying.mkdir()
        self._sync_private_directory()
        try:
            result = check()
        except (OSError, ValueError, KeyError, TypeError):
            self.block_resume()
            raise JournalError('Checkpoint integrity validation failed; resume blocked') from None
        self.verifying.rmdir()
        self._sync_private_directory()
        return result

    def _sync_private_directory(self):
        if os.name != 'nt':
            fd = os.open(self.private, os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)

    def block_resume(self):
        """Sticky out-of-chain stop; directory existence alone is authoritative.

        Never depend on a successful journal append or HEAD update. An interrupted
        or failed detail write leaves the directory in place and still blocks load.
        """
        self.state['terminal'] = 'CHECKPOINT_OR_INPUT_FAILURE'
        try:
            self.blocker.mkdir()
        except FileExistsError:
            return
        # If mkdir itself fails, propagate and stop. No software can promise a
        # durable marker on wholly unavailable storage; host rollback is out of scope.
        self._sync_private_directory()
        try:
            with (self.blocker / 'reason.json').open('x', encoding='utf-8') as stream:
                json.dump({'reason':'CHECKPOINT_OR_INPUT_FAILURE', 'utc':utc(),
                           'last_verified_head':self.head, 'plan_sha256':self.plan['plan_sha256']}, stream)
                stream.flush(); os.fsync(stream.fileno())
        except OSError:
            pass  # The already-created directory remains an unconditional stop.

    def _load(self):
        if not self.directory.is_dir():
            raise JournalError('Missing checkpoint directory')
        anchor = json.loads((self.directory / 'HEAD.json').read_text())
        self.disk_head = anchor
        entries = sorted(self.directory.glob('[0-9]*.json'))
        anchors = {0: self.head['sha256']}
        for seq, path in enumerate(entries, 1):
            event = json.loads(path.read_text())
            expected = {'sequence': seq, 'previous': self.head['sha256'], 'payload': event['payload']}
            if path.name != f'{seq:08d}.json' or event != {**expected, 'sha256': digest(expected)}:
                raise JournalError('Journal chain is corrupt or incomplete')
            self._apply(self.state, event['payload'])
            self.head = {'sequence': seq, 'sha256': event['sha256']}
            anchors[seq] = event['sha256']
        if anchor != {'sequence': anchor.get('sequence'), 'sha256': anchors.get(anchor.get('sequence'))}:
            raise JournalError('Missing committed journal tail or damaged HEAD')
        if not self.state['created']:
            raise JournalError('Missing genesis')
        if json.loads((self.public / 'plan.json').read_text()) != self.plan:
            raise JournalError('Saved plan changed')

    @classmethod
    def create(cls, public, private, frozen, run_id, backend):
        public, private = Path(public), Path(private)
        public.mkdir(parents=True, exist_ok=False)
        # Caller creates/locks the private parent before initialization.
        (private / 'journal').mkdir(exist_ok=False)
        atomic_json(public / 'plan.json', frozen)
        head = {'sequence': 0, 'sha256': '0' * 64}
        atomic_json(private / 'journal/HEAD.json', head)
        payload = {'kind': 'created', 'run_id': run_id, 'backend': backend,
                   'plan_sha256': frozen['plan_sha256'], 'utc': utc()}
        event = {'sequence': 1, 'previous': head['sha256'], 'payload': payload}
        atomic_json(private / 'journal/00000001.json', {**event, 'sha256': digest(event)})
        atomic_json(private / 'journal/HEAD.json', {'sequence': 1, 'sha256': digest(event)}, replace=True)
        return cls(public, private, frozen)

    def _apply(self, state, p):
        kind = p['kind']
        if kind == 'created':
            if state['created'] or p['plan_sha256'] != self.plan['plan_sha256'] or p['backend'] not in ('fake', 'openai'):
                raise JournalError('Invalid genesis')
            state['created'] = p
            return
        if not state['created']:
            raise JournalError('No genesis')
        if kind == 'run_stop':
            if p['reason'] != 'CHECKPOINT_OR_INPUT_FAILURE':
                raise JournalError('Unknown terminal stop')
            state['terminal'] = p['reason']
            return
        if kind == 'authorization_reserved':
            first_launch = self.head['sequence'] == 1 and p['approved_head'] is None
            if (state['terminal'] or state['created']['backend'] != 'openai'
                    or p['number'] != len(state['segments']) + 1
                    or (not first_launch and p['approved_head'] != self.head)
                    or any(a['authorization_sha256'] == p['authorization_sha256']
                           or a['authorization_id_sha256'] == p['authorization_id_sha256']
                           for a in state['authorizations'])):
                raise JournalError('Authorization reused or bound to another checkpoint')
            state['authorizations'].append(p)
            return
        if kind == 'segment_start':
            if state['active'] is not None or state['terminal'] or p['number'] != len(state['segments']) + 1:
                raise JournalError('Invalid segment transition')
            if state['created']['backend'] == 'openai':
                authorization = state['authorizations'][-1] if state['authorizations'] else {}
                if any(authorization.get(k) != p.get(k) for k in ('number', 'authorization_sha256', 'review_sha256')):
                    raise JournalError('Paid authorization was not reserved before preflight')
            metadata_file = p.get('metadata_file', 'metadata.json')
            if metadata_file != 'metadata.json' and not re.fullmatch(r'metadata-[0-9a-f]{32}\.json', metadata_file):
                raise JournalError('Invalid segment metadata identity')
            metadata_path = self.public / 'segments' / f"{p['number']:04d}" / metadata_file
            metadata = json.loads(metadata_path.read_text())
            if (file_hash(metadata_path) != p['metadata_sha256'] or
                    metadata['source_sha256'] != self.plan['source_sha256'] or
                    metadata['image_id'] != p['image_id'] or
                    (state['segments'] and metadata['image_id'] != state['segments'][0]['image_id'])):
                raise JournalError('Segment provenance changed')
            if metadata.get('preflight_id'):
                check_artifacts(self.private / metadata['preflight_id'], p['preflight_hashes'])
                controls = json.loads((self.private / metadata['preflight_id'] / 'public/controls.json').read_text())
                if digest(controls) != metadata['controls_sha256']:
                    raise JournalError('Preflight controls changed')
            state['segments'].append(p)
            state['active'] = p['number']
            return
        if kind == 'segment_end':
            if p['number'] != state['active']:
                raise JournalError('Invalid segment end')
            state['segments'][-1] = {**state['segments'][-1], 'end': p}
            state['active'] = None
            return
        if state['active'] is None or p['segment'] != state['active'] or (state['terminal'] and kind != 'episode_finish'):
            raise JournalError('Operation outside active segment')
        i = p['index']
        if kind == 'episode_start':
            if i != len(state['started']) + 1 or i > 56 or p['position'] != self.positions[i - 1]:
                raise JournalError('Position reused, skipped or changed')
            previous = state['started'].get(i - 1)
            if previous and i - 1 not in state['finished'] and previous['segment'] == state['active']:
                raise JournalError('Previous episode still in flight')
            if p['episode_id'] != f"{state['created']['run_id']}:{i:03d}":
                raise JournalError('Episode identity changed')
            state['started'][i] = p
            return
        if i not in state['started'] or i in state['finished'] or state['started'][i]['segment'] != state['active']:
            raise JournalError('Invalid episode transition')
        if kind == 'request_reserved':
            requests = [r for (idx, _), r in state['requests'].items() if idx == i]
            if p['number'] != len(requests) + 1 or len(requests) >= 6:
                raise JournalError('Request reused or episode request limit')
            if (type(p['input']) is not int or type(p['output']) is not int or
                    not 0 <= p['input'] <= 8192 or not 0 <= p['output'] <= 1024):
                raise JournalError('Invalid token reservation')
            if state['created']['backend'] == 'openai' and (p['input'] < 1024 or p['output'] != 1024):
                raise JournalError('Missing paid reservation')
            all_requests = list(state['requests'].values()) + [p]
            if (len(all_requests) > self.plan['max_api_requests']
                    or sum(r['input'] for r in all_requests) > self.plan['max_input_reservations']
                    or sum(r['output'] for r in all_requests) > self.plan['max_output_reservations']
                    or sum(r['input'] for r in requests) + p['input'] > 49152
                    or sum(r['output'] for r in requests) + p['output'] > 6144):
                raise JournalError('Global or episode reservation budget exhausted')
            state['requests'][i, p['number']] = p
            return
        if kind == 'request_result':
            r = state['requests'].get((i, p['number']))
            if r is None or 'result' in r:
                raise JournalError('Unreserved or duplicate response')
            r['result'] = p
            model = p['metadata'].get('reported_model')
            if model and model not in state['reported_models']:
                state['reported_models'].append(model)
            if len(state['reported_models']) > 1:
                state['terminal'] = 'REPORTED_MODEL_CHANGED'
            if p['outcome'] == 'BACKEND_TIMEOUT':
                self._mark_timeout(state, i)
            return
        if kind != 'episode_finish':
            raise JournalError('Unknown journal event')
        position = self.positions[i - 1]
        relative = Path(position['pair_id']) / position['condition']
        check_artifacts(self.public / relative, p['public_hashes'])
        check_artifacts(self.private / relative, p['private_hashes'])
        row = json.loads((self.public / relative / 'episode.json').read_text())
        if any(row.get(k) != v for k, v in position.items()):
            raise JournalError('Finished episode identity mismatch')
        # Finished public call accounting must correspond exactly to the durable ledger.
        reservations = [r for (idx, _), r in state['requests'].items() if idx == i]
        sent = [c for c in row['model_calls'] if c['metadata'].get('request_sent')]
        if state['created']['backend'] == 'openai':
            results = [r.get('result') for r in reservations]
            if any(r is None for r in results) or [r['metadata'] for r in results if r['metadata'].get('request_sent')] != [c['metadata'] for c in sent]:
                raise JournalError('Response ledger does not match finished episode')
        state['finished'][i] = row
        obs = row['observed']
        if len(state['reported_models']) > 1:
            state['terminal'] = 'REPORTED_MODEL_CHANGED'
        if position['condition'] != 'B0' and obs['prohibited_effect']:
            state['terminal'] = 'OBSERVED_SECURITY_FAILURE'
        if row['loop']['stop_reason'] == 'BACKEND_TIMEOUT':
            self._mark_timeout(state, i)
        elif obs['episode_valid'] and i not in state['timeout_positions']:
            state['consecutive_timeouts'] = 0
        if p['timeout_environment_ok'] and not self.timeout_isolated(row, i, state):
            raise JournalError('Unverified timeout continuation')
        if p['timeout_environment_ok']:
            path = self.public / 'segments' / f"{p['segment']:04d}" / f'timeout-environment-{i:03d}.json'
            env = json.loads(path.read_text())
            if (file_hash(path) != p['timeout_environment_sha256'] or
                    env['source_sha256'] != self.plan['source_sha256'] or
                    env['image_id'] != state['segments'][0]['image_id']):
                raise JournalError('Timeout environment evidence changed')
        state['last_finish'] = p

    @staticmethod
    def _mark_timeout(state, index):
        # Count the known timeout before final episode export; a crash must not
        # erase it. The final row must not count that same event a second time.
        if index not in state['timeout_positions']:
            state['timeout_positions'].append(index)
            state['timeouts'] += 1
            state['consecutive_timeouts'] += 1
            if state['timeouts'] >= 3 or state['consecutive_timeouts'] >= 2:
                state['terminal'] = 'TIMEOUT_LIMIT'

    def timeout_isolated(self, row, index, state=None):
        state = self.state if state is None else state
        position = self.positions[index - 1]
        relative = Path(position['pair_id']) / position['condition']
        reservations = [r for (i, _), r in state['requests'].items() if i == index]
        return verified_timeout_evidence(row, self.private / relative, frozen=self.plan,
            position=position, reservations=reservations, public=self.public / relative,
            backend=state['created']['backend'])

    def append(self, kind, **values):
        p = {'kind': kind, 'utc': utc(), **values}
        candidate = deepcopy(self.state)
        reads_evidence = kind in ('segment_start', 'episode_finish')
        def check():
            if json.loads((self.directory / 'HEAD.json').read_text()) != self.disk_head:
                raise JournalError('Checkpoint HEAD changed during execution')
            tail = json.loads((self.directory / f"{self.head['sequence']:08d}.json").read_text())
            if tail.get('sha256') != self.head['sha256'] or digest({k:v for k,v in tail.items() if k!='sha256'}) != self.head['sha256']:
                raise JournalError('Checkpoint tail changed during execution')
            if reads_evidence:
                self._apply(candidate, p)
        self.verify_integrity(check)
        if not reads_evidence:
            self._apply(candidate, p)  # Pure transition/budget checks; no evidence reads.
        seq = self.head['sequence'] + 1
        event = {'sequence': seq, 'previous': self.head['sha256'], 'payload': p}
        hashed = digest(event)
        atomic_json(self.directory / f'{seq:08d}.json', {**event, 'sha256': hashed})
        atomic_json(self.directory / 'HEAD.json', {'sequence': seq, 'sha256': hashed}, replace=True)
        self.state, self.head = candidate, {'sequence': seq, 'sha256': hashed}
        self.disk_head = self.head.copy()

    def summary(self, stop_reason=None):
        s = self.state
        rows = list(s['finished'].values())
        requests = list(s['requests'].values())
        paid = s['created']['backend'] == 'openai'
        confirmed = sum(bool(r.get('result', {}).get('metadata', {}).get('request_sent')) for r in requests) if paid else 0
        uncertain = sum('result' not in r for r in requests) if paid else 0
        return dict(version='expanded-study-v1.1', design='main', run_id=s['created']['run_id'],
                    plan_sha256=self.plan['plan_sha256'], planned_episodes=56,
                    scheduled=self.positions, episodes=rows, completed_episode_records=len(rows),
                    started_positions=[p['position'] for p in s['started'].values()],
                    position_execution=[{'schedule_index':i, 'episode_id':p['episode_id'],
                        'segment':p['segment'], 'started_utc':p['utc'],
                        'record_status':'finished' if i in s['finished'] else 'started_without_committed_record'}
                        for i,p in s['started'].items()],
                    started_without_episode_record=[p['position'] for i, p in s['started'].items() if i not in s['finished']],
                    unstarted=[p for p in self.positions if p['schedule_index'] not in s['started']],
                    batch_complete=len(rows) == 56 and not s['terminal'], schedule_exhausted=len(s['started']) == 56,
                    stop_reason=s['terminal'] or stop_reason,
                    real_api_attempts=confirmed, uncertain_api_attempts=uncertain,
                    api_attempts_reserved=len(requests) if paid else 0,
                    input_tokens_reserved=sum(r['input'] for r in requests) if paid else 0,
                    output_tokens_reserved=sum(r['output'] for r in requests) if paid else 0,
                    api_attempt_accounting_complete=not uncertain,
                    api_attempt_count_scope='durable_ledger_all_segments; uncertain_reservations_separate',
                    api_reservations_by_segment=[{'segment':segment['number'],
                        'requests_reserved':sum(r['segment']==segment['number'] for r in requests) if paid else 0,
                        'uncertain_requests':sum(r['segment']==segment['number'] and 'result' not in r for r in requests) if paid else 0}
                        for segment in s['segments']],
                    actual_llm_episodes=sum(r['actual_llm_episodes'] for r in rows),
                    actual_llm_episode_count_scope='committed_episode_records_only',
                    segments=s['segments'], authorization_reservations=s['authorizations'],
                    next_segment=len(s['segments'])+1 if len(s['started'])<56 and not s['terminal'] else None,
                    timeout_count=s['timeouts'],
                    consecutive_timeout_count=s['consecutive_timeouts'], checkpoint_head=self.head,
                    evidence_kind='fake_backend_engineering' if not paid else 'real_model_study')
