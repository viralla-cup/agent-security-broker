# Security audit log

Updated 20 October 2026. This change improves observation without modifying YAML,
authorization order, path checks, execution, budgets, or agent denial feedback.
No dependency, dashboard, database, authentication service, or model backend is added.

## Starting implementation review

Commit `0300686` had a useful audit foundation: request/task identity, principal,
policy version and SHA-256, condition, step, status/code, dispatch flag, operation,
unkeyed truncated resource hash, and elapsed nanoseconds. The harness exported
these inside JSONL records alongside synthetic requests and responses. Tests covered
many gate behaviors and checked canary absence in audit records.

The missing pieces were wall-clock timestamps, unique episode/event correlation,
safe explanations, explicit authorization versus execution fields, a read-only
viewer, and focused audit tests. One subtlety was that `status=denied` could mean
either a gate denial or an executor rejection after dispatch. Another was that
the socket carried the complete internal response/audit envelope: B2a's nested
response was generic, but its reason was visible in the adjacent audit object.
No model backend had yet consumed that transport. The full synthetic research
trace was not suitable as a content-free user-facing security log.

## Schema version 3

Commit `178eb72` introduced schema 2. The v1.2 reconciliation changes the audit
classification of caught pre-dispatch evaluation errors from `ERROR` to `DENY`
with `evaluation_status=FAILED` and `reason_code=EVALUATION_ERROR`. This implements
the author-confirmed binary decision vocabulary. No authorization check, executor
call, agent response, retryability, or denial counter is changed. Schema 2 exports
and their verified results are retained as historical evidence.

One final audit event is generated for each request handled by `Broker.handle`.
It describes the observed completion of that call, not a durable pre-dispatch
commitment. The internal method still returns an envelope to trusted callers; only
`response` may cross the agent-facing transport.

| Field | Meaning |
| --- | --- |
| `schema_version` | Integer `3` for new events; historical input keeps version `1` or `2`. |
| `timestamp` | UTC completion time with microseconds and `Z`; wall clocks can move. |
| `session_id`, `step`, `event_id` | Random broker-instance ID, call sequence, and their unique combination. Use sequence for ordering within an instance. |
| `request_id` | Keyed pseudonym of the validated request ID; null if parsing never produced a valid Action. |
| `task_id` | Keyed pseudonym of the trusted task context, never the request's claimed identity. |
| `operation` | Validated `read_text` or `write_new`, otherwise null. |
| `principal`, `condition` | Trusted `lab-agent` identity and B0/B2/B2a condition. |
| `policy_version`, `policy_sha256` | Public policy label and exact loaded-policy digest. Version/hash identify applicable configuration; no fabricated per-rule ID is added. |
| `resource_id` | Session-local keyed resource reference, without the path. |
| `decision`, `reason_code`, `explanation` | Gate decision and static public explanation. |
| `evaluation_status` | `COMPLETED` for ordinary allow/deny checks; `FAILED` for a caught pre-dispatch evaluation error. This is separate from authorization and execution. |
| `dispatched` | Whether `FileExecutor.execute` was invoked. |
| `execution_status`, `execution_code`, `execution_explanation` | Separate observed executor result; no raw exception string. |
| `elapsed_ns` | Existing broker measurement through execution, before event construction, JSONL persistence, and host observation. Not total request latency. |

The reason `PATH_OUTSIDE_SCOPE` intentionally does not distinguish protected-root
membership from absence of a grant. That distinction is not exposed by existing
authorization code; changing policy decisions or revealing protected roots is not
needed for this audit task. The version and digest identify the configuration.

Gate decision `ALLOW` means dispatch was permitted, not that execution succeeded.
`DENY/NOT_STARTED` means no executor call occurred. `ALLOW/FAILED` covers caught
I/O, decoding, or value errors; a file may have been partially created.
`ALLOW/REJECTED` covers an executor guard rejection, such as `READ_LIMIT` or
`UNSUPPORTED_OBJECT`. The existing agent status and denial counter are preserved
even for those post-dispatch rejections. `DENY/NOT_STARTED` with failed evaluation
distinguishes a fail-closed error from an ordinary policy denial; do not count this
error as successful policy blocking. `SUCCEEDED` means the executor
returned normally, not that the agent's task or every security objective is proven.
An executor error has `evaluation_status=COMPLETED` and `execution_status=FAILED`.
There is no runtime `ASK`, approval path, or authority expansion. The unchanged
agent response can still say `status=error` with `code=EXECUTION_ERROR` for a caught
pre-dispatch error; this is legacy transport status, not a third authorization
decision. The proposed richer adapter Result in v1.2 is not yet the wire contract.

## Separate channels and privacy

`security_audit.events` generates metadata without reading files or making policy
decisions. Static explanations contain no arguments, file contents, credentials,
protected paths, hints, or exception messages. Request, task, and resource references
use HMAC-SHA256 with a random, in-memory key per broker instance, truncated to 24 hex
characters. Identical request IDs within one instance have the same pseudonym, but
duplicate calls have distinct event IDs and steps. References are not comparable
across instances. The HMAC key is never logged or sent to the agent.

This also prevents an agent from copying a secret into a syntactically valid request
ID and having it appear literally in the audit. The original request ID remains in
the existing tool response for protocol compatibility. Public policy labels are
trusted deployment metadata; administrators must not store secrets in them.

The service writes audit-only JSONL to `/tmp/security-audit.jsonl` with mode 0600
inside the broker container. The client's separate `/tmp` does not contain it;
the channel volume contains only the socket. No audit-read tool is registered.
The fixed trusted host observer reads the private log through Docker exec after a
call, verifies event count/session/step, and reconstructs the research envelope.
Only the original six response fields cross the agent socket. B0, B2, and B2a all
use this separation; B2a retains generic agent feedback while its audit is detailed.

The host exports `audit.jsonl` for inspection and preserves the fuller synthetic
`trace.jsonl` for research. The latter retains fixture paths and permitted content;
replacing a known canary does not make arbitrary production traces safe to publish.
The CLI projects only allowlisted audit fields, regenerates explanations from known
codes, and ignores raw request/response and arbitrary text even in historical traces.

## Read-only CLI

From the repository root, after `python scripts/run_replay.py`, use PowerShell:

```powershell
$auditLog = Get-ChildItem results/dev-*/audit.jsonl | Sort-Object LastWriteTime | Select-Object -Last 1
python scripts/inspect_audit.py $auditLog.FullName --condition B2a --decision DENY
python scripts/inspect_audit.py $auditLog.FullName --execution FAILED
python scripts/inspect_audit.py $auditLog.FullName --evaluation FAILED
python scripts/inspect_audit.py $auditLog.FullName --jsonl
```

On any supported host, supply the literal file path instead of `$auditLog.FullName`.
The CLI needs no PyYAML, pytest, running Docker, model credentials, or write access
to the log. Filters select condition, decision, evaluation status, and execution status.
The current five-case replay does not induce execution errors, so `--execution FAILED`
normally returns no events; real executor failure paths are exercised by the tests.

Legacy example, retained unchanged:

```sh
python scripts/inspect_audit.py results/dev-20261019T104349Z-7e16ab/trace.jsonl --condition B2a --decision DENY
```

Legacy timestamps and session IDs are unknown. The viewer prints `TIME_NOT_RECORDED`
and uses `legacy:<line>` for location. Legacy raw identifiers are pseudonymized with
a fresh viewer key on each invocation; their reuse across episodes is ambiguous and
does not establish episode identity. The original files are never rewritten.
Schema 1/2 evaluation errors retain `decision=ERROR` in the read-only projection;
`evaluation_status` is derived from those historical fields, not a new observation.
`--decision ERROR` selects these historical errors only. Schema 3 rejects `ERROR`,
`ASK`, absent evaluation status, and contradictory evaluation/outcome fields.

Malformed, duplicate-key, contradictory, oversized, or incomplete input produces
a nonzero exit status and a line number without echoing private input. The viewer
is intended for completed exports or observation after a completed call, not a
transactionally consistent concurrent tail. Some prior valid lines may already have
been printed when a later malformed line is found; check the exit status.

## Persistence and limits

The writer creates a private `.pending` marker before appending, flushes using
`fsync`, and removes the marker only after success. An append/fsync failure stops
further appends and leaves evidence marked incomplete. The reader refuses a pending
log, and the harness also rejects a missing event or sequence mismatch. A safe
fixed warning goes to service stderr. Agent feedback and actual authorization remain
unchanged; an audit failure never retroactively denies or rolls back an operation.

The log is on disposable tmpfs, not durable storage. This is not a write-ahead log,
transaction with filesystem execution, cryptographic signature, or tamper-evident
history. A crash between the effect and log persistence can lose the final event;
the pending marker only covers the append phase, not that earlier crash window.
Unhandled process failures, compromised trusted components, administrator rewriting,
clock accuracy, and cross-session identifier matching are not solved. Docker's
current `log-driver=none` means the stderr warning alone is not retained by Docker;
the private marker and observer checks are the machine-readable failure signals.

Any future pre-dispatch fail-closed audit requirement would change availability and
potentially experimental behavior. It is intentionally not introduced here. The
filesystem oracle remains necessary, and a finite test suite is not a security proof.
