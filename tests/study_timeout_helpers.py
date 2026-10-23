"""Consistent offline timeout fixtures: real local broker, normal ledger interface."""
import run_expanded_study_v11 as runner
from backends.base import BackendError
from lab.study import install_fixture, seed_for
from lab.oracle import snapshot
from test_controlled_pair import LocalEpisode
from test_expanded_study import local_worker


class TimeoutBackend:
    name = 'deterministic-fake'
    model = 'offline-timeout-injection'
    def __init__(self, task, actions=()):
        self.actions = list(actions)
    def next_action(self, *args):
        self.last_call = {'request_sent': True}  # Synthetic; no network implementation.
        if self.actions:
            return self.actions.pop(0)
        raise BackendError('BACKEND_TIMEOUT')


class LedgerTimeout(runner.LedgerMixin, TimeoutBackend):
    pass


def service_copy(ep):
    return {name: {'text':path.read_text(), 'pending':False} for name,path in (
        ('/tmp/security-audit.jsonl',ep.audit_path),
        ('/tmp/pilot-operation-receipts.jsonl',ep.receipt_path))}


def local_timeout_episode(task, condition, backend, out, raw, *, actions=(), **kwargs):
    def factory(condition,task):
        ep=LocalEpisode(raw/'fixture',condition,seed_for(task))
        install_fixture(ep.root,task);ep.before=snapshot(ep.root);return ep
    timeout=LedgerTimeout(task,actions).attach(backend.journal,backend.index)
    return runner.v1.execute_episode(task,condition,timeout,out,raw,
        episode_factory=factory,worker=local_worker,collect_service=service_copy,
        credential_check=lambda ep:None,clock=lambda:0,**kwargs)
