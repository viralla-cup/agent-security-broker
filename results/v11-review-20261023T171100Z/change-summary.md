# v1 versus v1.1: independent review scope

Status: implementation agent preparation only. Independent review and paid author authorization are PENDING. No paid requests or credential access were performed.

## Unchanged scientific inputs

All 14 task definitions, all 56 Main positions and 28 planned pairs, condition ordering, B0/B2/B2a meanings, immutable policy, trusted executor, Security Core, independent oracle, origin attribution and outcome definitions remain unchanged. The three v1 paid attempts are separate preserved evidence. Valid unsuccessful results and incomplete/invalid pairs are never replaced or relabeled.

## Execution changes

The dedicated v1.1 runner uses a 30-second request timeout capped by the remaining 120-second episode deadline; the urllib timeout is not a hard cancellation watchdog. It never retries API requests, episodes or pairs. Up to two isolated, fully verified BACKEND_TIMEOUT observations may be followed by the next original position. Consecutive or third cumulative timeouts terminate the logical run. Source/integrity, model and B2/B2a safety failures are terminal; setup/incomplete-observation failures stop the segment. A later segment may execute only unstarted positions after new author approval and fresh controls.

A private hash-chained journal durably records starts before provisioning, reservations before provider I/O, response metadata, final artifact hashes, and segment provenance. Uncertain reservations remain charged. An OS lock excludes concurrent writers. Completed, invalid and uncertain started positions are never replayed. Known timeout counters survive crashes even before final export. A committed chain tail beyond HEAD is recoverable; missing or corrupt committed data fails closed.

Paid authorization is consumed before preflight. Failed preflight therefore requires a fresh authorization ID and current-head binding. A crash after segment metadata but before segment-start preserves the orphan metadata; another attempt writes a uniquely named file. Public metadata/control copies can recover independently after an interrupted copy. These windows have deterministic regression coverage.

Global ceilings remain 336 requests, 2,752,512 estimated input reservations and 344,064 output reservations across all segments. The 3.5-hour planning allowance is explicitly per separately authorized segment. Neither schedule completion nor resume guarantees 28 valid pairs.

## Source changes

Modified existing file:

- `scripts/run_expanded_study.py`: optional snapshot factory for shared controls; existing default behavior remains unchanged.

Added files:

- `scripts/run_expanded_study_v11.py`: isolated Main runner and authorization/resume flow.
- `src/lab/study_journal.py`: durable journal, locking, budget and transition checks.
- `tests/test_study_v11.py`: deterministic crash, uncertainty, timeout, authorization, integrity and integration regressions.
- `tests/conftest.py`: release pytest-owned temporary directories after each test, keeping the original 8 MiB test tmpfs limit.
- `experiments/expanded-study-v1.1.md`: prospective execution amendment.
- `experiments/study-v11-authorization-template.json`: blank, false-by-default author record.
- `docs/expanded-study-v1.1-runbook.md`: offline, launch, status and authorized-resume instructions.

## Review decisions required

Review the exact source snapshot and plan digest, unchanged matrix/labels/oracle, durability ordering, all resume/crash transitions, uncertainty accounting, authorization before preflight, current controls and source/image provenance. Approve or reject the operational amendment explicitly, including the per-segment planning allowance and timeout-related missingness. Review public/private separation and limitations before completing an actual attestation. A separate explicit author authorization is still required for the first paid segment and every subsequent paid invocation.

See `limitations-and-review.md`, the frozen `plan.json`, `main-matrix.csv`, source archive and final verification artifacts in this directory. Engineering fake behavior does not provide evidence of autonomous LLM recovery or B2 superiority.
