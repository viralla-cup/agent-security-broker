# Expanded Study v1: pre-execution blocker corrections

23 October 2026. Corrective work on the existing uncommitted study, following the
author-supplied independent PASS WITH BLOCKERS review. No scientific task, label,
condition, sample size, ordering rule, resource limit, Core policy or agent tool
is changed. Main remains 56 episodes; fallback remains 32. No paid execution,
independent approval record, commit or push is part of this correction.

## Corrections

1. The runner formerly reread task definitions by ID after computing the plan
   digest. It now captures immutable serialized plan/catalog snapshots, supplies
   detached task values, and binds prompt, authority, fixtures and evaluation
   inputs through task/manifest hashes. It verifies disk/source/configuration
   integrity before each episode and each backend request. The trusted fixture
   entry point checks the exact task digest inside Docker. Evaluation uses the
   original definition even if a faulty dependency changes its working copy;
   such an episode is infrastructure-invalid. Pair members share the same task
   digest and the saved schedule includes condition, repetition and position.
2. Analysis formerly grouped only by pair ID and overwrote duplicate conditions.
   It now requires the frozen plan, validates complete identity and ordering,
   reports rejected records and incomplete/invalid pairs, and excludes corrupted
   pairs from estimates. It preserves valid unsuccessful/refused/budget-limited
   outcomes and the existing feasibility, effect and infrastructure distinctions.
3. The review gate formerly trusted `all_passed` and a digest string. It now
   verifies the entire saved plan and all 16 expected control memberships, task
   and probe digests, explicit checks, decisions/effects, unique sessions/events,
   source metadata and the approved control artifact digest. Fresh Docker source
   and containment preflight checks remain mandatory on actual execution.

The blank review template gains digest fields; it remains unapproved. Tests use
ephemeral synthetic review inputs clearly labeled as unit-test data, never an
independent human attestation. Editable files/hashes do not authenticate a human
or protect against a malicious trusted host. Explicit author authorization of
any paid batch is a separate requirement, even if the technical gate passes.

## Independently reproducible negative cases

After building `agent-security-broker:mvp`, the complete engineering command is
`python scripts/run_checks.py`. Focused test names in `tests/test_expanded_study.py`:

- `test_manifest_changed_after_planning_stops_before_backend`: mutate prompt,
  fixture, expected output, required read or feasibility after planning; zero
  backend invocations and `BATCH_INPUT_INTEGRITY_FAILURE`.
- `test_manifest_changed_between_paired_conditions_stops_second`: mutate the
  manifest after condition one; condition two never starts, first evidence kept.
- `test_reviewer_false_positive_100pp_pair_is_quarantined`: reproduce mixed
  tasks/repetitions and overwritten duplicate conditions; no complete pair and
  no treatment-difference estimate, rather than a false +100 percentage points.
- `test_analyzer_frozen_schedule_counterexamples`: both main and fallback,
  complete and missing pairs, duplicates, identity conflicts and misplaced rows.
- `test_review_gate_requires_exact_complete_controls`: empty/missing/duplicate,
  contradictory/stale/mismatched controls and changed designs cannot pass.

Frozen plans and records now include stronger bindings. Earlier experimental
files and their analyses remain unchanged; they are not rewritten or silently
migrated to this schema. Checks are finite engineering evidence and cannot
establish autonomous model recovery, treatment superiority or general security.

## Executed offline verification

All results below are new executions on the corrected candidate, not reused
historical reports. No real model requests occurred.

| Check | Result | Evidence |
| --- | --- | --- |
| Focused `tests/test_expanded_study.py` in isolated Docker | 109 passed | [stdout and exact command metadata](../results/study-blocker-focused-20261023T062204Z-d691aa/) |
| `python scripts/run_checks.py` | 438 passed (329 existing + 109 study tests) | [stdout](../results/checks-20261023T062231Z-501564/stdout.txt) |
| `python scripts/run_expanded_study.py --design main --backend fake` | 56/56 valid episodes, 28/28 valid pairs, 16/16 controls | [summary](../results/study-20261023T062307Z-230ebd/summary.json), [analysis](../results/study-20261023T062307Z-230ebd/analysis.json) |
| `python scripts/run_expanded_study.py --design fallback --controls-only` | 16/16 controls | [controls](../results/study-20261023T062324Z-686ffa/controls.json) |
| `python scripts/run_agent_pilot.py --condition all --task all` | 6/6 engineering episodes passed | [summary](../results/pilot-20261023T062438Z-0daf1c/summary.json) |
| `python scripts/run_replay.py` | 15/15 cases passed | [summary](../results/dev-20261023T062322Z-7fe331/summary.json) |
| Corrected analyzer on valid/corrupted main and fallback datasets | 10 synthetic cases passed | [validation](../results/study-blocker-review-20261023T062411Z-bc4735/synthetic-analysis-validation.json) |

The archived implementation's three defects were independently reproduced with
offline doubles, then checked against the correction: changed prompts executed
under stale digests before the fix, mixed/duplicated pairs yielded false +100 pp,
and empty controls passed the old gate. The corrected outcomes are rejection
before backend invocation, no paired estimate, and review-gate rejection.
See [counterexample results](../results/study-blocker-review-20261023T062411Z-bc4735/counterexamples.json)
and [the runnable reproducer](../results/study-blocker-review-20261023T062411Z-bc4735/reproduce_counterexamples.py).
Run the reproducer from the repository root; it creates a new evidence directory
and uses memory-only synthetic review inputs, not a human approval record.

The final fake audit checks all 56 saved private episodes against actual receipts,
task hashes, prompts, seeded history, counters and original deadlines. Initial
files/containment match within every pair. Expected outcomes: 44 task completions,
40 safe completions, 8 correct scripted refusals and 8 prohibited effects in B0.
All 24 R setups contain a genuine harness DENY; the 16 feasible R episodes complete
safely afterward. These are deterministic engineering outcomes, not LLM recovery
or evidence of superiority. [Full evidence audit](../results/study-blocker-review-20261023T062411Z-bc4735/evidence-audit.json).

Both dry-run CLI plans were executed with `--backend openai --plan`, without
credentials or API I/O, and match the saved snapshots. Main/fallback membership,
ordering and pre-existing configuration are unchanged:

- [Main plan](../results/study-blocker-review-20261023T062411Z-bc4735/main-plan.json):
  `01b04036f40a3a26cf82522b20a7bab9cc5db45a0735cad398078a7954c89f5f`.
- [Fallback plan](../results/study-blocker-review-20261023T062411Z-bc4735/fallback-plan.json):
  `2677ef069b199cfc3836f4b58e511632d886807a0dbea69b862ea12e8cedb70c`.
- [Schedule/configuration comparisons](../results/study-blocker-review-20261023T062411Z-bc4735/plan-integrity.json),
  [main matrix](../results/study-blocker-review-20261023T062411Z-bc4735/main-matrix.csv),
  [fallback matrix](../results/study-blocker-review-20261023T062411Z-bc4735/fallback-matrix.csv),
  [source archive](../results/study-blocker-review-20261023T062411Z-bc4735/source_snapshot.zip).

The fallback's separate 32-episode Docker batch was not run. Its full schedule is
covered by regression/synthetic analysis tests; its task-condition cells are in
the complete main matrix, and its own 16 Docker controls passed.

The preliminary 104-test pass is retained with its source snapshot; five further
integrity tests and final guards preceded the 109/438-test checks and full matrix.
An additional invocation of the legacy pilot's default single clean-B2 fake case
also passed and is retained at [its own directory](../results/pilot-20261023T062322Z-9c9b8a/summary.json).
The required six-case pilot was then executed in full, not selected by outcome.
All earlier unsuccessful preparation records remain unchanged.

## Preservation, inventory and review status

[Consolidated verification](../results/study-blocker-review-20261023T062411Z-bc4735/verification.json)
records source/image digests, exact control artifact bindings, zero remaining
experiment containers/disposable volumes and unchanged hashes for all 752 prior
result files and all 452 tracked files as found at correction start. The scientific
manifest, README, Core, policy, executor, earlier hooks and both real pilots are
preserved. No new independent approval record was created.

Correction-specific edits: `src/lab/study.py`, `scripts/run_expanded_study.py`,
`scripts/analyze_expanded_study.py`, `tests/test_expanded_study.py`,
`experiments/study-review-template.json`, the technical revision appendix in
`experiments/expanded-study-v1.md`, `docs/expanded-study-runbook.md`, and this new
note. The [complete pending commit inventory](../results/study-blocker-review-20261023T062411Z-bc4735/commit-inventory.json)
includes all 13 source/documentation files from the preserved study worktree,
their hashes and the new evidence directories. Nothing has been staged, committed
or pushed by this correction.

Ready for final independent implementation review. Hashes and editable review
records provide consistency checks, not cryptographic authentication of a reviewer
or a malicious trusted host. The analyzer verifies recorded identity, not the
authenticity of arbitrary fabricated datasets. Scientific limitations remain as
declared in the prospective protocol. Paid execution remains blocked pending final
review and separate explicit author approval.
