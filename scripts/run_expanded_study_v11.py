"""Offline-default v1.1 Main runner: immutable positions and authorized resume."""

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
import uuid

from run_replay import ROOT, command, source_manifest
import run_expanded_study as v1
from run_controlled_pair import verified_runtime
from backends.base import BackendError
from backends.openai import OpenAIBackend
from lab.controlled_recovery import API_BUDGET, MODEL
from lab.study import catalog, digest, plan, seal_plan, FrozenStudy, validate_plan
from lab.study_fake import StudyFakeBackend
from lab.study_journal import (Journal, JournalError, RunLock, atomic_json,
                               artifact_hashes, file_hash)

PROTOCOL = ROOT / 'experiments/expanded-study-v1.1.md'


def frozen_plan():
    base = v1.frozen_plan('main')
    return seal_plan({**base, 'version': 'expanded-study-v1.1', 'request_timeout_seconds': 30,
        'base_protocol_sha256': base['protocol_sha256'], 'protocol_sha256': file_hash(PROTOCOL),
        'execution_rules': {'isolated_timeouts_allowed': 2, 'stop_consecutive_timeouts': 2,
                            'stop_total_timeouts': 3, 'request_retries': 0, 'episode_retries': 0,
                            'resume_unstarted_only': True, 'new_paid_segment_authorization': True,
                            'authorization_before_preflight': True, 'unique_segment_metadata': True,
                            'independent_timeout_health': True, 'sticky_integrity_stop': True,
                            'timeout_semantic_consistency': True, 'durable_verification_intent': True,
                            'batch_seconds_scope': 'per_authorized_segment', 'journal_format': 1}})


def capture(frozen):
    validate_plan(frozen)
    expected = plan('main')
    for key, value in expected.items():
        if key not in ('version', 'request_timeout_seconds') and frozen.get(key) != value:
            raise JournalError('Scientific/configuration inputs changed')
    if frozen['version'] != 'expanded-study-v1.1' or frozen['request_timeout_seconds'] != 30:
        raise JournalError('Invalid execution version')
    return FrozenStudy(json.dumps(frozen, sort_keys=True), json.dumps(catalog(), sort_keys=True))


def verify_inputs(snapshot, task=None):
    try:
        snapshot.verify(task)
    except ValueError:
        raise JournalError('Approved task inputs changed') from None
    if json.loads(snapshot.plan_json) != frozen_plan():
        raise JournalError('Approved source, plan or protocol mismatch')


def environment_check(frozen, image_id=None):
    if command(['docker', 'ps', '-a', '--filter', 'name=asb-', '--format', '{{.Names}}']).stdout.strip():
        raise JournalError('Preserve and resolve orphan containers before proceeding')
    if command(['docker', 'volume', 'ls', '--filter', 'label=asb.disposable=true', '--format', '{{.Name}}']).stdout.strip():
        raise JournalError('Preserve and resolve orphan volumes before proceeding')
    runtime = verified_runtime()
    if runtime['source_sha256'] != frozen['source_sha256'] or (image_id and runtime['image_id'] != image_id):
        raise JournalError('Runtime changed')
    return runtime


def require_authorization(path, *, run_id, frozen, segment, head):
    authorization = json.loads(Path(path).read_text(encoding='utf-8'))
    expected = {'run_id': run_id, 'plan_sha256': frozen['plan_sha256'],
                'segment': segment, 'checkpoint_head': head, 'allow_paid_api': True}
    if (any(authorization.get(k) != v for k, v in expected.items())
            or not isinstance(authorization.get('author'), str) or not authorization['author'].strip()
            or not isinstance(authorization.get('authorization_id'), str) or not authorization['authorization_id'].strip()):
        raise JournalError('Fresh explicit author authorization required for this exact segment')
    return authorization


class LedgerMixin:
    def attach(self, journal, index):
        self.journal, self.index = journal, index
        self.ledger_number = 0
        return self

    def next_action(self, history, schema):
        self.last_call = {'request_sent': False}
        reserved = self.preflight(history, schema)[1] if isinstance(self, OpenAIBackend) else 0
        self.ledger_number += 1
        number = self.ledger_number
        segment = self.journal.state['active']
        self.journal.append('request_reserved', segment=segment, index=self.index, number=number,
                            input=reserved, output=self.max_output_tokens if isinstance(self, OpenAIBackend) else 0)
        outcome = 'PROPOSAL'
        try:
            proposal = super().next_action(history, schema)
        except BackendError as exc:
            outcome = exc.code
            raise
        finally:
            # BaseException/process death must leave a reservation uncertain. Only
            # a returned proposal or a handled BackendError commits a result below.
            if sys.exc_info()[0] is None or isinstance(sys.exc_info()[1], BackendError):
                self.journal.append('request_result', segment=segment, index=self.index, number=number,
                                    metadata=deepcopy(self.last_call), outcome=outcome)
        if self.journal.state['terminal'] == 'REPORTED_MODEL_CHANGED':
            raise BackendError('BACKEND_ERROR')  # Do not deliver a changed model's tool proposal.
        return proposal


class LedgerOpenAI(LedgerMixin, OpenAIBackend):
    pass


class LedgerFake(LedgerMixin, StudyFakeBackend):
    pass


def run_segment(journal, runtime, authorization_digest=None, review_digest=None, *,
                backend_factory=None, execute=v1.execute_episode, input_check=verify_inputs,
                check_environment=environment_check, clock=time.monotonic, stop_after=None):
    """Caller holds the run lock and has verified fresh approval/controls."""
    frozen, state = journal.plan, journal.state
    external_check = input_check
    def input_check(snapshot, task=None):
        return journal.verify_integrity(lambda: external_check(snapshot, task))
    snapshot = journal.verify_integrity(lambda: capture(frozen))
    input_check(snapshot)
    if state['terminal']:
        raise JournalError('Terminal logical-run stop cannot be resumed')
    if len(state['started']) == 56:
        return journal.summary('SCHEDULE_EXHAUSTED')
    number = len(state['segments']) + 1
    if state['created']['backend'] == 'openai' and (not authorization_digest or not review_digest):
        raise JournalError('Paid segment authorization and independent review required')
    if state['active'] is not None:
        journal.append('segment_end', number=state['active'], reason='PROCESS_INTERRUPTED',
                       elapsed_seconds=None)
    folder = journal.public / 'segments' / f'{number:04d}'
    folder.mkdir(parents=True, exist_ok=True)
    # Preserve metadata left by a crash before segment_start. No episode or API
    # call can precede that event, so a new attempt may use a fresh metadata file.
    metadata_file = 'metadata-' + uuid.uuid4().hex + '.json'
    atomic_json(folder / metadata_file, runtime)
    journal.append('segment_start', number=number, metadata_file=metadata_file,
                   metadata_sha256=file_hash(folder / metadata_file),
                   image_id=runtime['image_id'], authorization_sha256=authorization_digest,
                   review_sha256=review_digest,
                   preflight_hashes=artifact_hashes(journal.private / runtime['preflight_id'], sync=True)
                       if runtime.get('preflight_id') else {})
    start = clock()
    stop = None
    done = 0
    try:
        for position in journal.positions[len(journal.state['started']):]:
            if position['schedule_index'] % 2 == 1 and clock() - start > frozen['batch_seconds'] - 360:
                stop = 'SEGMENT_TIME_LIMIT'; break
            input_check(snapshot)
            index = position['schedule_index']
            task = snapshot.task(position['task'])
            journal.append('episode_start', segment=number, index=index, position=position,
                           episode_id=f"{journal.state['created']['run_id']}:{index:03d}")
            relative = Path(position['pair_id']) / position['condition']
            factory = backend_factory or (lambda task: LedgerFake(task))
            backend = factory(task).attach(journal, index)
            row, _ = execute(task, position['condition'], backend, journal.public / relative,
                             journal.private / relative, position=position,
                             integrity_check=lambda: input_check(snapshot, task))
            input_check(snapshot, task)
            # Across segments each fresh episode must still equal literal fixtures
            # (checked by execute_episode) and the first recorded containment.
            previous = next((r for r in journal.state['finished'].values() if r.get('isolation')), None)
            if previous is not None and row.get('isolation') and row['isolation'] != previous['isolation']:
                raise JournalError('Containment changed across positions/segments')
            if any(idx == index and 'result' not in request for (idx, _), request in journal.state['requests'].items()):
                # A saved but uncommitted report is not proof that uncertain I/O
                # completed. Retain it, consume this position and stop the segment.
                stop = 'UNCERTAIN_REQUEST'; break
            environment_ok = False
            environment_hash = None
            if journal.timeout_isolated(row, index) and not journal.state['terminal']:
                try:
                    checked = check_environment(frozen, runtime['image_id'])
                    atomic_json(folder / f'timeout-environment-{index:03d}.json', checked)
                    environment_hash = file_hash(folder / f'timeout-environment-{index:03d}.json')
                    environment_ok = checked['image_id'] == runtime['image_id'] and checked['source_sha256'] == frozen['source_sha256']
                except Exception:
                    environment_ok = False
            journal.append('episode_finish', segment=number, index=index,
                           public_hashes=artifact_hashes(journal.public / relative, sync=True),
                           private_hashes=artifact_hashes(journal.private / relative, sync=True),
                           timeout_environment_ok=environment_ok, timeout_environment_sha256=environment_hash)
            done += 1
            atomic_json(journal.public / f'progress-{index:03d}.json', {
                'run_id':journal.state['created']['run_id'], 'schedule_index':index,
                'checkpoint_head':journal.head, 'public_episode_sha256':file_hash(journal.public / relative / 'episode.json'),
                'committed_records':len(journal.state['finished']), 'timeout_count':journal.state['timeouts']})
            state = journal.state
            if state['terminal']:
                stop = state['terminal']; break
            if not row['observed']['episode_valid'] and not environment_ok:
                stop = 'INVALID_EPISODE'; break
            if stop_after is not None and done >= stop_after:
                stop = 'OFFLINE_PLANNED_INTERRUPTION'; break
    except BaseException as exc:
        # Durable starts/reservations survive even if this write also fails.
        if isinstance(exc, JournalError):
            journal.block_resume()
            raise  # The out-of-chain stop survives even when HEAD cannot be appended.
        journal.append('segment_end', number=number, reason='SEGMENT_INTERRUPTED', elapsed_seconds=clock()-start)
        summary = journal.summary('SEGMENT_INTERRUPTED')
        atomic_json(folder / 'summary.json', summary)
        raise
    if stop is None and len(journal.state['finished']) != 56:
        stop = 'SCHEDULE_EXHAUSTED_WITH_MISSING_RECORDS'
    journal.append('segment_end', number=number, reason=stop or 'SCHEDULE_EXHAUSTED', elapsed_seconds=clock()-start)
    summary = journal.summary(stop)
    atomic_json(folder / 'summary.json', summary)
    atomic_json(journal.public / 'summary.json', summary, replace=True)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', action='store_true')
    parser.add_argument('--run-id')
    parser.add_argument('--backend', choices=('fake', 'openai'), default='fake')
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--status', action='store_true')
    parser.add_argument('--controls-only', action='store_true')
    parser.add_argument('--review-record', type=Path)
    parser.add_argument('--authorization', type=Path)
    parser.add_argument('--allow-paid-api', action='store_true')
    parser.add_argument('--stop-after', type=int, help='Offline-only interruption after N finished positions')
    args = parser.parse_args(argv)
    frozen = frozen_plan()
    if args.plan:
        print(json.dumps(frozen, indent=2)); return
    if not args.run_id or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}', args.run_id):
        parser.error('An explicit unique run-id (letters/digits/hyphen/underscore) is required')
    if args.stop_after is not None and (args.backend != 'fake' or args.stop_after < 1):
        parser.error('Planned interruption is available only for offline fake execution')
    out = ROOT / 'results' / ('study-v1.1-' + args.run_id)
    raw = ROOT / '.local/study-v1.1' / args.run_id
    if args.status:
        with RunLock(raw / 'run.lock'):
            journal = Journal(out, raw, frozen)
            print(json.dumps(journal.summary('STATUS_SNAPSHOT'), indent=2)); return
    paid = args.backend == 'openai' and not args.controls_only
    # Check explicit flags before touching credentials or starting Docker.
    if paid and not (args.allow_paid_api and args.review_record and args.authorization):
        parser.error('Separate author authorization and independent review are required')
    if args.resume and not raw.is_dir():
        parser.error('Resume requires an existing v1.1 logical run')
    raw.mkdir(parents=True, exist_ok=args.resume)
    with RunLock(raw / 'run.lock'):
        journal = Journal(out, raw, frozen) if args.resume else None
        if journal and journal.state['created']['backend'] != args.backend:
            raise JournalError('Backend changed on resume')
        if journal and (journal.state['terminal'] or len(journal.state['started']) == 56):
            print(json.dumps({'run_id':args.run_id,'stop_reason':journal.state['terminal'] or 'SCHEDULE_EXHAUSTED',
                              'additional_api_attempts':0}))
            if journal.state['terminal'] or len(journal.state['finished']) != 56:
                raise SystemExit(2)
            return
        head = journal.head if journal else None
        number = len(journal.state['segments']) + 1 if journal else 1
        authorization = review = None
        if paid:
            review = v1.require_review(args.review_record, frozen)
            authorization = require_authorization(args.authorization, run_id=args.run_id, frozen=frozen, segment=number, head=head)
        if journal is None:
            # Preserve the logical run/plan even if the very first Docker
            # preflight fails. Resume still needs fresh head-bound approval.
            journal = Journal.create(out, raw, frozen, args.run_id, args.backend)
        if paid:
            # Consume approval durably even if Docker/preflight/metadata fails.
            # Another invocation must present a fresh ID and updated head binding.
            journal.append('authorization_reserved', number=number, approved_head=head,
                           authorization_sha256=digest(authorization), review_sha256=digest(review),
                           authorization_id_sha256=hashlib.sha256(authorization['authorization_id'].encode()).hexdigest())
        runtime = environment_check(frozen, journal.state['segments'][0]['image_id'] if journal and journal.state['segments'] else None)
        runtime.update(backend=args.backend, git_base_commit=command(['git','rev-parse','HEAD']).stdout.strip())
        # Controls run before every segment; partial preflight directories are
        # immutable and unique, so a failed preflight cannot overwrite evidence.
        preflight = raw / ('preflight-' + uuid.uuid4().hex)
        controls_raw = preflight / 'private'; controls_out = preflight / 'public'
        controls_raw.mkdir(parents=True); controls_out.mkdir()
        atomic_json(preflight / 'plan.json', frozen)
        atomic_json(preflight / 'runtime.json', runtime)
        if paid:
            atomic_json(preflight / 'author-authorization.json', authorization)
            atomic_json(preflight / 'independent-review.json', review)
        controls = v1.run_controls(controls_out, controls_raw, frozen, input_check=verify_inputs, snapshot_factory=capture)
        v1.validate_controls(controls, frozen)
        if not (out / 'metadata.json').exists():
            atomic_json(out / 'metadata.json', runtime)
        if not (out / 'controls.json').exists():
            atomic_json(out / 'controls.json', controls)
        # Segment provenance includes its exact fresh control binding.
        runtime['controls_sha256'] = digest(controls)
        runtime['preflight_id'] = preflight.name
        if args.controls_only:
            print('Offline controls passed:', out); return
        factory = None
        if paid:
            # This is the only credential access path; never reached in offline modes.
            key = os.environ['OPENAI_API_KEY']
            factory = lambda task: LedgerOpenAI(MODEL, key, budget=API_BUDGET,
                max_output_tokens=1024, timeout=30, reasoning_effort='none')
        summary = run_segment(journal, runtime, digest(authorization) if authorization else None,
                              digest(review) if review else None, backend_factory=factory, stop_after=args.stop_after)
        print(json.dumps({k:summary[k] for k in ('run_id','completed_episode_records','schedule_exhausted',
                         'stop_reason','real_api_attempts','uncertain_api_attempts')}, indent=2))
        if not summary['batch_complete'] and summary['stop_reason'] != 'OFFLINE_PLANNED_INTERRUPTION':
            raise SystemExit(2)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        raise SystemExit('v1.1 stopped safely; retained local evidence. No automatic retry. Details omitted.') from None
