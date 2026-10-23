# Expanded Study v1.1 Main: prospective execution amendment

Prepared 23 October 2026 against reviewed commit `3be02741`. Pending independent
review and separate author authorization. No new paid data is authorized by this
document. The three interrupted v1 attempts remain immutable, separate datasets;
none is imported, completed, relabeled, or resumed here.

## Scientific invariants

The [v1 protocol](expanded-study-v1.md) supplies all scientific definitions,
estimands, labels, oracle criteria, analysis and limitations. The literal
`manifests/expanded-study-v1.json` is unchanged. Main retains exactly its 14 cells,
56 positions, 28 pairs, two counterbalanced repetitions and original order.
No fallback, task adaptation, favorable replacement, or new capability is added.
Core, executor, immutable policy, B0/B2/B2a semantics and receipt/origin checks
remain unchanged. Valid unsuccessful/budget outcomes remain scientific data.

## Prospective operational changes

Use the same gpt-6-luna Responses configuration, six requests, six actions and
three denials (including the R seed), zero retries, 120 seconds from episode/setup
start, 1,024 output tokens/request, 6,144 output and 49,152 estimated input tokens
per episode. Raise the socket timeout from 20 to 30 seconds, capped by remaining
episode time. urllib has no independent hard cancellation watchdog here; deadline
checks before/after I/O do not guarantee an absolute wall-clock cap. Timeout does
not prove non-delivery, cancellation, non-billing, or provider fault.

Automatically continue only after a BACKEND_TIMEOUT with a sent-request marker,
verified setup, complete independent observation, intact receipts and immutable
inputs, no prohibited B2/B2a effect, stable reported model, and a fresh successful
Docker/image/source/clean-resource check. Allow at most two such isolated timeouts
across the entire logical run. Two consecutive timeouts or the third cumulative
timeout permanently stops this logical run. Only a valid episode resets the
consecutive counter; a crash or another infrastructure failure does not reset it.
Every timeout remains an invalid observation, never a model failure or a success.
Run the next original schedule position, including the counterpart, without
replaying the failed position. Incomplete/invalid pairs cannot enter paired estimates.

Setup failures and incomplete observation stop the segment immediately. After
repair of the environment without changing approved inputs, explicit new author
authorization and fresh controls may permit the next *unstarted* position.
Uncertain in-flight positions are consumed, retained and never replayed.
Safety failures, changed reported model, exhausted timeout allowance, corrupted
state, or changed approved inputs cannot be bypassed with ordinary resume.
No automatic retry of a request, episode, pair, or execution segment is allowed.

## Durable logical run and authorization

Each logical run has an immutable run ID, plan, backend and 56 schedule identities.
An exclusive OS file lock excludes concurrent launch/resume; the OS releases it
after process termination. A numbered hash-chained journal is authoritative.
Each event is written to a temporary file, flushed/fsynced, atomically renamed,
then anchored by an atomically replaced HEAD. A committed tail beyond HEAD is
recoverable; missing committed entries, damaged HEAD, or inconsistent contents
fail closed. Abandoned temporary files are not committed events. File fsync and
rename are not protection against malicious host rollback or all storage failure.

Persist episode-start BEFORE provisioning and request reservation BEFORE provider
I/O. Never reuse a started position, including one with an uncommitted final result.
Finished events bind both public and private artifact bytes. Keep partial files
and uncertain requests; never infer zero cost from missing usage. Requests with a
durable reservation but no result remain uncertain even if the process may have
stopped before transmission. Reservations are never refunded.

Global limits remain 336 requests, 2,752,512 estimated input and 344,064 output
tokens over ALL segments. Per-position limits also persist; positions are never
re-entered. Fake reservations are labeled engineering-only and make no API calls.
The 3.5-hour allowance is a *planning limit per authorized segment*, not a new
episode deadline or a hard total elapsed-time cap. Review/offline interruption time
is excluded by starting another segment; spending limits never reset. This is an
explicit operational amendment to v1's single-batch planning allowance.

Every paid segment needs a newly supplied author authorization bound to run ID,
exact plan, next segment number and current journal head, plus a matching actual
independent review. A stale authorization cannot start another segment. These
records are consistency gates, not cryptographic proof of human identity. The
assistant must not fabricate either attestation. A completed run performs no more
inference. Resume never loads historical v1 state.

Reserve each paid authorization in the journal before preflight. Even a preflight
failure consumes its authorization ID and advances the head; another invocation
requires fresh author approval. Uncommitted segment metadata files are preserved
under unique names. A crash before segment-start does not block a newly authorized
attempt or consume a schedule position; no inference can precede segment-start.

## Measurement, missingness and prerequisites

Save each segment's authorization/review digests, start/end time, source/image
identity and stop reason. Every original position is unstarted, started without a
committed final record, or finished (valid/invalid). Report reserved requests,
confirmed send markers, uncertain reservations and provider-reported usage
separately. Preserve orphan final files as uncommitted evidence for independent
inspection, without promoting them to verified results or re-executing them.
Existing complete-pair analysis is conditional on validity. Differential missingness,
segment/time effects and interruptions may bias it; report all planned denominators
and segment provenance. Neither 56 planned positions nor resume guarantees 28
valid comparisons. Do not pool v1 and v1.1 as a single completed experiment.

Before each segment verify sources, image, no leftover experiment resources and
all 16 unchanged deterministic controls. Before automatic timeout continuation,
repeat the runtime/clean-resource check. Any orphan resources require offline
evidence collection and deliberate cleanup before resume; do not silently delete
them. Prevent Windows sleep/Modern Standby and Docker restart during execution.

Cost assumptions remain those documented in v1 (not newly checked prices): charge
input reservations at $0.125/M and output at $0.50/M, giving $0.516096 before tax
for the full logical run. This is not a provider-enforced monetary cap. Previously
incurred and uncertain v1 charges are separate. Exact credit expiration is unknown.

Offline failure injection must cover normal 56-position completion, between-episode
and in-flight crashes, duplicate/concurrent resumes, missing/corrupt journal and
artifacts, timeout thresholds across segments, invalid observation/setup, global
budgets and changed source/plan. Real Docker fake execution verifies integration.
New digests, controls, independent implementation review and separate explicit
paid authorization are required before any real launch or resume.

## Corrective engineering clarification after failed review (23 October)

The first v1.1 implementation failed independent review on timeout/failure
collisions and persistence of a detected HEAD integrity violation. Its historical
offline evidence is retained, not upgraded to acceptance. These corrections enforce
the operational rules above without changing tasks, labels, schedule or estimands.

An isolated timeout requires separately recorded positive worker-return/health,
execution, broker execution, observation, service collection and service persistence
signals. Public reports contain booleans only; private evidence retains the same
signals and the saved service file digest. Continuation verifies both records and
the actual service file before the fresh runtime check. Missing or contradictory
signals, failed worker exit, evidence collection/save failure, or execution failure
stop the segment even when the last backend outcome is BACKEND_TIMEOUT. Timeout
classification remains infrastructure-invalid; neither counters nor retries change.

A detected checkpoint integrity violation creates a permanent `RESUME_BLOCKED`
directory outside the hash chain before attempting any further journal activity.
Its presence alone forbids resume, including if writing its reason detail fails.
Restoring HEAD does not remove the stop. Journal loading also preserves detected
corruption this way; inspection of corrupt state is therefore not purely read-only.
An intact chain with a lagging valid HEAD and no prior detected violation remains
recoverable after an ordinary interrupted HEAD update. Do not remove the marker or
edit a run to reopen it. Complete storage unavailability or malicious trusted-host
rollback cannot be solved by a local marker; preserve evidence and require external
review in such a case. New source/plan hashes, independent corrective review, fresh
matching offline controls and separate author approval remain mandatory for paid use.

## Second corrective clarification (24 October)

The subsequent review found contradictory private evidence accepted by the timeout
gate, and process death between detecting HEAD corruption and creating the block.
The first corrective evidence remains historical; it does not attest this revision.

Before timeout continuation, validate the private task against the frozen task hash,
the saved public record against the returned row, all private/public call metadata
against the reservation/result journal, and each call history against the common
prompt and preceding broker feedback. Reconcile service audit/receipt logs with
retained exchanges and receipts, including pending-write status. Recompute the
existing oracle and report from these inputs; require agreement with both saved
observation records, public outcomes and anonymized snapshot relationships. Missing,
unreadable, incomplete or contradictory evidence stops automatic continuation even
if its bytes have a hash. This validation does not alter scientific outcome rules.

Integrity-sensitive reads now follow durable creation of `VERIFYING/` under the
private run root. Only successful verification removes it; journal persistence
then occurs as a separate phase. Any interrupted verification blocks ordinary
resume, whether or not `RESUME_BLOCKED/` could be written. This deliberately also
blocks crashes during an ultimately valid but unfinished check. It is not possible
to infer success from a missing error record. Status inspection uses the run lock
and the same write-capable verification protocol. Never delete either marker to
reopen a run. Crashes before verification is armed perform no integrity-sensitive
reads; crashes after successful verification while writing a journal event/HEAD
can still recover a fully valid unanchored tail without replaying a position.

The protocol covers process termination and local I/O boundaries under the trusted
host assumption. It does not guarantee power-loss durability on every filesystem,
or protection against unrestricted host modification, marker deletion or total
storage rollback. New review/source/plan bindings and separate paid authorization
are still required. All 56 positions, 28 planned pairs, budgets and scientific
definitions remain unchanged.
