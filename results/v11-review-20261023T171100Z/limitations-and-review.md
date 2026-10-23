# Review boundaries and unresolved limitations

Independent review and author approval are PENDING. No attestation was completed
by the implementation agent. Synthetic authorization values in unit tests are
explicit engineering fixtures, not a reviewer or author statement.

The frozen Main matrix remains 56 positions and 28 planned pairs. A completed
schedule can still contain invalid, missing or unsuccessful observations. Those
positions are never replaced; valid-pair estimates remain conditional on validity.
Report missingness by task, condition and execution segment. Do not pool earlier
v1 attempts with v1.1 or infer B2 superiority from engineering behavior.

`real_api_attempts` counts durable local `request_sent` markers, not confirmed
provider receipt or billing. `uncertain_api_attempts` counts reservations WITHOUT
a committed request result (for example, process death during I/O). A completed
BACKEND_TIMEOUT/BACKEND_ERROR result can also have uncertain delivery/billing;
it is already counted as a local attempted request and is not counted again in
that unresolved-reservation field. Its absent provider usage remains UNKNOWN.
All reservations, including uncertain and conservatively over-reserved requests,
remain charged against the logical-run ceilings and are never refunded.

The existing analyzer's per-condition token/attempt totals cover committed episode
records only. The journal-derived summary supplies whole-run reservations and
unresolved attempts, including started positions with no committed episode row.
Report both scopes; do not interpret a missing episode record as zero spending.
A future billing reconciliation must remain separate from scientific outcomes.

The 30-second urllib timeout is capped by remaining 120-second episode time but
is not a process-level cancellation watchdog. Provisioning/collection and Windows
sleep can exceed planning allowances. Prevent Modern Standby and Docker restart
operationally. The 3.5-hour allowance now applies to each separately authorized
segment; API/token limits apply across ALL segments. This time-planning amendment
requires explicit reviewer/author acceptance.

Known timeouts are journaled before final episode export, survive crashes, and
are counted once per position. Consecutive or third cumulative timeouts, model
drift and safety failures cannot be cleared by ordinary resume. Setup/observation
failures stop the segment; fresh controls and new human authorization may allow
only previously unstarted positions. A crash cannot be used to replay a completed
or in-flight position, regain its budget, or clear the prior timeout count.

OS locks, file fsync, atomic rename and a hash chain provide crash detection and
conservative recovery under the trusted-host assumption. They do not authenticate
a human signer, defeat whole-directory rollback by a malicious host, or guarantee
survival of every storage/power failure. Full chain and committed-artifact integrity
are checked on load/resume; the active writer also checks HEAD and its chain tail.
Never edit or delete checkpoints to make a run continue.

The review must cover both the unchanged scientific definitions and the new
execution state machine: authorization binding, locking, before-I/O durability,
artifact integrity, uncertainty, timeout counters, terminal states, global budgets,
source/image binding, partial evidence and privacy. Review the prospective protocol,
runbook, exact source snapshot, matrix, current tests and Docker integration evidence.
No claim of readiness for paid execution follows until this independent review and
a separate explicit paid authorization are supplied.

Paid approval is now consumed before preflight, including failed preflight attempts. A new authorization ID and checkpoint-head binding are required afterward. Uncommitted segment metadata is retained under unique filenames; it cannot block a later authorized attempt. These crash-window corrections require review with the final source snapshot.
