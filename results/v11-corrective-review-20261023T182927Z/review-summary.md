# v1.1 corrective engineering review package — P1 / P2

Status: **ready for independent corrective verification, not independently passed
and not authorized for paid execution**. Baseline commit remains
`3be02741ad3a8f0edf298e5b0cf80266fd07f0d8`; existing uncommitted v1.1 work was retained.
This package is engineering evidence prepared by the implementing agent. No
independent attestation or human authorization has been created.

## Reproduction before corrections

`reproduce-before.py` ran in the previous image with its real local Core, broker,
filesystem executor, receipts, Agent Loop and deterministic fault injection.
Container networking was disabled. P1 used the actual shared episode exporter:
worker health false and service-evidence save failure each still produced a timeout
row accepted by the old continuation predicate. The positive healthy-timeout
control was accepted too. P2 rolled an active writer's HEAD back to an earlier
valid anchor: the reservation failed, `run_stop` also failed, reload returned a
nonterminal run, and a synthetic paid-ledger segment could consume position 2.
No transport or actual authorization was involved. Source hashes in the output
match the pre-edit snapshot.

Evidence: `reproduce-before-stdout.txt`, `reproduce-before-command.json`,
`before-source.zip`. The private baseline inventory is retained locally; public
verification reports counts/hashes and does not export private experimental data.

## Corrections

**P1.** `execute_episode` retains separate worker-return, worker-health,
execution, broker-execution, observation, service-collection and service-save
signals. The save signal is set only after reading back the saved file. Public
exports contain booleans; private episode evidence additionally binds the actual
service bytes by SHA-256. A timeout can continue only when all required positive
signals, existing setup/receipt/state/origin criteria, private/public agreement,
service digest, existing timeout allowances and fresh runtime check pass.
The journal revalidates the private binding when committing/loading a continued
timeout. A healthy runtime after the episode cannot erase an earlier failure.
Scientific oracle/classification criteria are unchanged.

**P2.** Detected HEAD/tail or loaded checkpoint integrity failure persists
`RESUME_BLOCKED/` outside the normal chain. This is checked before loading state
or appending events. Directory existence alone blocks resume; failure writing
`reason.json` cannot reopen it. The runner uses this block for a detected journal
or approved-input error without relying on a successful `run_stop` append.
Restoring HEAD does not remove the block. A valid chain ahead of a lagging HEAD
without a previously detected violation still recovers after an ordinary crash;
the same non-replay/reservation accounting remains in effect.

## Exact corrective scope

Changed since this task started:

- `scripts/run_expanded_study.py`: independent operational evidence only; retain
  the pre-existing control snapshot injection change.
- `src/lab/study_journal.py`: timeout evidence validation and sticky integrity stop.
- `scripts/run_expanded_study_v11.py`: use verified health/private evidence and
  out-of-chain stop; identify both corrections in frozen execution rules.
- `tests/test_study_v11.py`: update timeout doubles with explicit health evidence
  and the expected permanent-stop assertion.
- `tests/test_study_v11_corrective.py`: 22 new focused cases.
- `experiments/expanded-study-v1.1.md`: explicit corrective clarification; preserve
  the original scientific definitions and prospective 56-position Main design.
- `docs/expanded-study-v1.1-runbook.md`: failed-review status, marker and health
  behavior, including the write-on-detected-corruption status caveat.

`corrective-only.patch` compares the task-start snapshot to the current sources,
including previously untracked files; ordinary Git diff alone omits those files.
`source-manifest.json`, `plan.json`, `source-snapshot.zip` and `verification.json`
bind the current review revision. No old result or review package was rewritten.

## Executed offline verification

- Targeted suite in the restricted Docker test container:
  `python -m pytest -q -p no:cacheprovider tests/test_study_v11.py tests/test_study_v11_corrective.py`
  — **70 passed**. Includes healthy isolated timeout continuation, unhealthy
  worker, evidence collection/save errors, checkpoint/execution/observation
  errors, missing/contradictory evidence, timeout limits, budget/resume rules,
  outdated-valid/missing HEAD, changed tail, repaired HEAD, failed marker-detail
  write, paid entry blocked before credentials/preflight, and ordinary tail recovery.
- Full suite: `python -B scripts/run_checks.py` — **508 passed**, including
  Security Core and existing agent/first-live/paired/replay/study tests.
  Actual output is in `../checks-20261023T183528Z-2e2990/`.
- `reproduce-after.py` repeated the same original fault injection: healthy timeout
  accepted, worker and save collisions rejected; P2 reload rejected with a durable
  out-of-chain block. See the before/after stdout files and exact command records.
- `python -B results/v11-corrective-review-20261023T182927Z/verify-native-integrity.py`
  also checked marker persistence, restored-HEAD rejection and ordinary recovery
  on the actual Windows filesystem: all assertions passed.
- `prepare-review.py` checked previous evidence bytes, unchanged scientific
  configuration, current source/image identity, restricted container settings and
  absence of leftover experiment resources. Exact digests/counts are in
  `verification.json`.

Intermediate unsuccessful checks are retained: the first `--network=none` build
could not use the cached pip layer and failed resolving dependencies; the next
attempted focused invocation therefore had no new test file and ran no tests.
The default-cache build then succeeded with its dependency layer cached. The first
actual focused run had 69 passes and one test-double failure (`COLUMNS` was treated
as a credential); only that environment test double needed correction. Final
build/focused/full/reproduction outputs identify the successful revision.

## Invariants, limitations and next review

No live/paid request, credential access, experiment launch, commit or push occurred.
All test send markers and authorizations are synthetic and never represent real
LLM data or author approval. There was no new full fake Main, control-series or
real pilot launch. Prior fake/real results remain historical evidence, not fresh
attestation of the corrective revision. The full unit suite executes real local
Core/receipt/filesystem paths inside Docker; P1 worker failure is injected, not a
new full Docker worker experiment.

All 56 scheduled positions, task prompts/fixtures/labels, order, model and budgets,
policy/Core, oracle, analysis definitions and existing authorization gates remain
unchanged. Only source/protocol/plan hashes and two explicit operational rule flags
change. Timeout collisions remain invalid infrastructure observations, retained
without replay; no favorable outcomes are selected or retried.

The marker depends on writable trusted local storage. If even directory creation
cannot persist, or the host owner deletes/rolls back all evidence, software cannot
guarantee durability. That is not a permitted recovery path. File fsync/rename on
Windows is not a universal power-loss guarantee. An intact lagging HEAD observed
for the first time remains indistinguishable from an ordinary interrupted update;
this correction preserves a violation once detected, not external anti-rollback
attestation. Socket timeout still does not prove cancellation or non-billing.

Independent review must repeat P1/P2 and both positive controls, inspect the exact
new digests and assess these storage limits. Before any paid launch, obtain fresh
matching offline controls for the new source/image binding, a genuine independent
PASS and separate explicit author authorization for the exact run/plan/segment.
Existing approval files cannot authorize the new digest. This task stops here for
independent verification; it does not manufacture those prerequisites.
