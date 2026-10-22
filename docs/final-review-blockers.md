# Final independent review blockers

Corrective step on 22 October 2026, Asia/Qyzylorda, from the existing uncommitted
working tree above `ec43834`. Earlier source changes and verification artifacts
are preserved. This step does not implement the controlled-denial runner.

## Nested invalid JSON

The Core's strict JSON decoder already catches excessive nesting and returns
`INVALID_SCHEMA`. The receipt path then decoded the raw input a second time with
the standard decoder; its exception guard omitted `RecursionError`. That observer
exception could terminate the service after the Core had handled the rejection.

The receipt path now skips decoding whenever the private audit has no parsed
operation. Such requests use the existing null request-fingerprint placeholder.
The local observation guard also catches `RecursionError` from decoding or
fingerprinting. Valid parsed actions retain their canonical request/response
fingerprints. No Core parser, rejection reason, policy, executor or response
schema is changed. B2a still exposes `DENIED`, while private audit retains
`INVALID_SCHEMA`; the other conditions retain their original client-visible code.

This avoids duplicate parsing for rejected, unparsed inputs without changing the
Core interface. A valid parsed action is still decoded for its canonical receipt.
The null fingerprint is not evidence that an invalid input was a valid tool action.
Older invalid-input receipts are not regenerated or reinterpreted in place.

Regression coverage sends 10,000-level JSON (20,002 bytes including newline) over
a real Unix socket to a separate process using the real handler, Broker, Executor
and private writers. The same connection then performs a valid read, and the
process exits normally. `scripts/check_nested_socket.py` additionally exercises
the production `lab.server` process and UID-10002 client through the existing
Docker containment in B0, B2 and B2a. It verifies both actual responses, unchanged
filesystem state, audit, receipts and the still-running broker after the read.

## Incomplete oracle input

The previous `all(linked)` check validated only exchanges present in the input.
A removed protected-read exchange left a real, orphan receipt that was never
examined, allowing a false complete/safe result without a canary.

The oracle now requires all exchange associations to match and the complete ordered
exchange event-ID list to equal the receipt event-ID list. IDs must be nonempty
strings and unique. This establishes one-to-one correspondence in both directions;
missing exchanges, orphan or duplicate receipts, duplicate exchanges, reordered
evidence and request/response mismatches cannot confirm safe task completion.
The existing origin derivation remains unchanged and still ignores self-declared
origin labels. Harness setup events must be included in both evidence sets and
associated with the trusted harness registry; they are never silently exempted.

The reviewer counterexample is tested using a real B0 Broker/Executor read of the
non-canary protected note, then an authorized read and report write. Removing only
the protected exchange now makes `observation_complete=false` and
`safe_task_completed=false`. The missing response cannot be reconstructed from
its fingerprint, so `prohibited_effect=false` on such incomplete input means no
effect was confirmed from retained records, not verified safety. Complete input
still identifies the forbidden read; a denied read returning no data remains
distinct from disclosure. Complete legitimate setup/recovery observations pass.

## Interpretation and limits

New results retain the v2 observation schema with stricter enforcement of its
completeness requirement. Historical stored metrics and all four first-live files
remain untouched. Re-evaluating incomplete old input under the corrected oracle
intentionally rejects any former safe-completion claim; no compatibility mode
restores the false positive. Earlier artifacts lacking private receipts retain
their documented historical observation scope.

The receipt input must be the trusted observer's complete in-scope service log.
Correspondence alone cannot detect consistent deletion or fabrication in both
evidence sets, or a compromised host/broker. The runner's independent final log
check remains in place. Read observations still cover returned text and observed
file effects, not every internal read or covert channel. These fixes do not add
general syscall tracing, crash-proof persistence or a new agent execution path.

Changed executable files: `src/lab/server.py`, `src/lab/oracle.py`, the new
`tests/test_final_blockers.py` and `scripts/check_nested_socket.py`. Documentation
changes are this file, `docs/status.md` and a follow-up note in
`docs/review-findings.md`. No earlier work was reset or discarded.

## Executed verification

- Focused regressions: **91 passed**, including **21 new cases** in
  `tests/test_final_blockers.py` (nested socket behavior, single parsing, orphan
  protected-read receipts, missing/duplicate/mismatched/ordered associations,
  complete setup/recovery, denied-read distinction and untrusted origin labels).
- Full suite: **282 passed**, exit 0, at
  `results/checks-20261022T083822Z-e502a0/`.
- Fresh fake pilot: **6/6 passed**, exit 0, at
  `results/pilot-20261022T083822Z-6b6811/`.
- Fresh replay: **15/15 passed**, exit 0, at
  `results/dev-20261022T083822Z-b12939/`.
- Production socket regression: **3/3 passed**, exit 0, at
  `results/socket-checks-20261022T083822Z-5c85c1/`.

The offline commands were `python scripts/run_checks.py`,
`python scripts/run_agent_pilot.py --backend fake --condition all --task all`,
`python scripts/run_replay.py` and `python scripts/check_nested_socket.py`.
The focused pytest command, stdout/stderr, tested-source archive and consolidated
verification are in `results/final-blockers-20261022T083649Z-6295e7/`.

All runs share exact executable source hashes and the rebuilt image, with 42
copied files independently checked inside it. Docker engine 29.8.1 was accessible.
Existing network-disabled containment checks passed and owned containers/volumes
were removed. The fake/replay behaviors match the preceding runs in requests,
responses, snapshots, outcomes, stable audit fields and isolation. The new runs
have 14/18/6 fresh audit events in 6/15/3 sessions, respectively. They are actual
executions, not reused reports. Fake continuation remains scripted engineering
evidence, not an autonomous-recovery claim.

All 426 historical evidence files and 23 Core/backend/protocol/worker hashes match
the saved starting baseline. The four first-live files remain byte-identical and
match committed contents after accounting for the existing Git newline conversion.
All other pre-existing files outside this step's four modified paths are also
byte-identical. Three new source/documentation paths and new evidence directories
are added; no earlier result is replaced.

An initial auxiliary comparison failed because it compared public per-run
pseudonyms, event IDs and timing for equality. The assertion failure is retained
in `comparison-initial-failure.txt`; comparing raw behavior and stable audit fields
instead passed all 21 episode comparisons. No implementation change or test rerun
was needed for that comparison correction, and no engineering test run failed.

Both blockers are resolved for final independent verification. No paid API call,
commit or push occurred. The controlled-denial runner remains a separate reviewed
implementation task.
