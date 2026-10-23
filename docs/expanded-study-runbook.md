# Expanded study preparation and review

Prepared 23 October 2026, Asia/Qyzylorda. This runbook accompanies the separate
[prospective protocol](../experiments/expanded-study-v1.md) and
[literal task/label manifest](../experiments/manifests/expanded-study-v1.json).
It does not authorize paid execution or change earlier experimental evidence.
The author reports independent agreement on all 14 labels, with three blocking
implementation defects. See [the corrective review note](expanded-study-blocker-corrections.md).
Final independent implementation review and explicit author approval remain pending.

The source context is the complete 20 October handover v1.2, reconciled with
the newer reviewed repository decisions, the [original protocol](../experiments/protocol.md),
[controlled-denial proposal](controlled-recovery-proposal.md), and the preserved
[first real pair](../results/controlled-pair-20261022T100129Z-f2b59f/summary.json).
The handover's broader grid and second-backend portability objective remain
future work. This time-limited extension does not replace those goals or change
the article title. The existing README was already committed at `da4c079` and
is preserved byte-for-byte.

## Fixed designs

| Design | A security/utility | R controlled continuation | Total | Max API requests | Estimated reserved-token cost |
| --- | ---: | ---: | ---: | ---: | ---: |
| Main | 32 | 24 | 56 | 336 | $0.516096 |
| Fallback | 16 | 16 | 32 | 192 | $0.294912 |

Both use two counterbalanced repetitions, gpt-6-luna, six calls and 120 seconds
per episode. Prices, reservation assumptions and limitations are in the protocol.
Choose the design before any paid batch, based on time/access only. The fallback
retains read/write attacks, explicit/discoverable destinations and both infeasible
tasks. It is not a selection of favorable results from the main design.

| Stratum | Main episodes per condition | Fallback episodes per condition |
| --- | ---: | ---: |
| A clean utility | 8 | 4 |
| A attacked utility/security | 8 | 4 |
| R explicit destination | 4 | 2 |
| R discoverable destination | 4 | 2 |
| R infeasible task | 4 | 4 |

These are repeated observations on a small fixed corpus, not independent draws
from a general task population. Main and fallback are alternative designs; their
results must not be pooled as two independent studies. A zero difference between
B2 and B2a, or no model-selected attack in B0, is an admissible result.

The main design needs approximately 3.5 hours of execution allowance; fallback
needs 2 hours, excluding independent review and build time. These are planning
allowances, not guaranteed wall-clock caps. Exact credit expiry and account rate
limits are unknown. Prefer an approved run on 23 October rather than assuming
access until the end of 24 October.

## Offline preparation

From the repository with a running Docker Linux engine:

```powershell
docker build --tag agent-security-broker:mvp .
python scripts/run_checks.py
python scripts/run_expanded_study.py --design main --backend fake
python scripts/run_expanded_study.py --design fallback --controls-only
python scripts/run_expanded_study.py --design main --backend openai --plan
python scripts/run_expanded_study.py --design fallback --backend openai --plan
```

No credentials or provider requests are needed for these commands. Plan mode
also needs no Docker. Each executable run first performs all 16 deterministic
B0/B2 controls. The main fake run then exercises all 56 episode positions using
scripted engineering backends. These outputs must never be described as LLM
recovery or measured feedback benefit. The fallback uses a strict subset of the
same cells and unchanged per-episode settings, with its own frozen matrix.

`plan_sha256` covers the selected matrix, configuration, source manifest and
prospective protocol. The Docker image's copied source hashes must match the host.
Changing source, labels or protocol invalidates previous plan approval and control
evidence; rebuild and review the new version before paid execution.

## Independent review and proposed paid commands

Review the task prompts and literal outcomes, particularly R05/R06 infeasibility,
R03/R04 discoverability, clean/attack pairing and the exact allowed resource roots.
Review the oracle's receipt-bound required reads, model-origin delivery and failure
classification. A successful fake run does not substitute for independent labels.

Copy [the pending review template](../experiments/study-review-template.json) to an
ignored local file, for example `.local/study-review-main.json`. An actual reviewer
must fill their identity, confirm `independent_labels_reviewed`, record the approved
plan digest, `approved_binding` (copied from the matching controls' `binding`),
the canonical JSON digest of `controls.json` as `approved_controls_sha256`, and the
matching offline evidence directory containing `controls.json`, `plan.json` and
`metadata.json`. The gate verifies the entire saved plan and all 16 controls,
including unique identities, decisions, effects and source association. A reviewer
name is a statement, not cryptographic identity proof. Do not fill a review
attestation on the reviewer's behalf. Old candidate evidence cannot approve a
changed plan or switch between main and fallback.

Only after that review and separate explicit author approval of the selected
batch, synthetic-data transfer and bounded budget, the proposed commands are:

```powershell
python scripts/run_expanded_study.py --design main --backend openai --review-record .local/study-review-main.json --allow-paid-api
```

Or, if the fallback was selected before execution:

```powershell
python scripts/run_expanded_study.py --design fallback --backend openai --review-record .local/study-review-fallback.json --allow-paid-api
```

Configure `OPENAI_API_KEY` only in the trusted host process using the secure local
method in [the first-live runbook](first-live-pilot.md); never paste it into chat,
Git, a command argument or a container. Model configuration cannot be overridden
by CLI or `OPENAI_MODEL`. The review record and CLI flag are guards, not permission
to spend without author approval. There is no automatic resume/retry facility.

## Artifacts and analysis

Public: `results/study-<UTC-id>/` contains the plan, image/source metadata,
deterministic controls, a separate `<pair-id>/<condition>/episode.json`, incremental
progress files and final summary with invalid/unstarted positions. Private:
`.local/study/<UTC-id>/` contains fixture snapshots, exact exchanges, histories,
receipts, setup intent, checkpoints and service evidence. Historical directories
are never reused. A killed host can still leave incomplete final accounting;
private checkpoints are not durable proof of API delivery or billing.

Analyze a saved summary without Docker or API access:

```powershell
python scripts/analyze_expanded_study.py results/study-<UTC-id>/summary.json --output results/study-<UTC-id>/analysis.json
```

The output path must be new. The analysis distinguishes planned/valid/invalid
counts, empty denominators, explicit/discoverable recovery, infeasible refusal,
clean/attack utility and targeted effects. It computes paired differences and
exploratory cluster intervals only where at least four complete base families
exist. Fake evidence retains its label. No p-value, population-security guarantee,
B2-superiority or portability conclusion is generated.

Analysis now requires the adjacent frozen `plan.json` (or an explicit `--plan`).
It verifies full episode identity and unique schedule positions. Corrupted pairs
are reported as invalid and excluded from paired estimates, missing partners as
incomplete; valid unsuccessful episodes remain. Historical pre-correction summaries
lack this binding and are not automatically reinterpreted by the corrected analyzer.

Started positions without a final episode record are distinct from unstarted
positions; their request accounting is incomplete. Invalid records with complete
observation retain a separate prohibited-effect count. Provider usage absent from
responses remains unknown, not zero. Complete-pair comparisons are conditional
on validity: unequal infrastructure failure rates may bias them and must be
discussed alongside all planned denominators. No unsuccessful row is replaced.
Detected reported-model drift withholds paired comparisons for the entire batch;
descriptive records remain available with the configuration-failure flag.

Targeted-proposal counts concern the four predeclared attack probes. They are not
a universal classifier of every possible unsafe model proposal; the broader
prohibited-effect flag comes from the independent actual-effect oracle.

## Implementation boundary

New study modules implement declared fixtures, scheduling, a task-specific oracle
and fake controls. `StudyEpisode` uses the existing containment and real broker;
fixture additions occur through trusted initialization before the measured task,
not through an agent capability. Core, policy, tool schema, original oracle and
receipt validation are unchanged. The two existing integration hooks are optional:
private history recording for unseeded episodes and an injected task evaluator in
the exporter. Default first-live and controlled-pair behavior remains unchanged.

This small study can support a narrowly framed descriptive article with auditable
positive, negative or inconclusive observations. It is not evidence of production
coverage, general attack resistance or scientific novelty, nor a guarantee of
publication. The broader handover plan and current article title remain preserved.

## Offline evidence and review package

This section preserves the previous review candidate's evidence. Its hashes are
historical and must not be used for the corrected implementation. Current hashes
and newly executed checks are linked in the [corrective review note](expanded-study-blocker-corrections.md).

The review candidate passed **387 tests** (329 existing plus 58 new) using
`python scripts/run_checks.py` after a fresh Docker build:
[test output](../results/checks-20261022T204532Z-a8b58a/stdout.txt).
The Docker engine was 29.8.1. Tests include real Linux Core/filesystem/receipt
operations with local transport, offline HTTP doubles, setup and budget transfer,
all 28 task-condition cells, invalid/partial records, uncertain timeouts, model-ID
drift and comparison withholding, oracle attribution, privacy and approval guards.

The existing `python scripts/run_agent_pilot.py` fake run passed 6/6 episodes at
[the new pilot result](../results/pilot-20261022T200230Z-e9e5e4/summary.json);
`python scripts/run_replay.py` passed 15/15 checks at
[the new replay result](../results/dev-20261022T200229Z-3d9158/summary.json).
These ran before the final new-study refinements; hashes confirm all existing
pilot/replay implementation files are identical to the final candidate.

All 16 actual-Docker direct controls passed for each current review plan:
[main controls](../results/study-20261022T204553Z-34d5f2/controls.json) and
[fallback controls](../results/study-20261022T204553Z-fda20c/controls.json).
The fallback command exercised controls only; no claim of a separate 32-episode
Docker batch is made. Its selected cells and scheduling are covered by the main
matrix and focused tests.

The complete actual-Docker fake matrix passed **56/56 valid episodes, 28/28 pairs**:
[summary](../results/study-20261022T202535Z-c5b8f8/summary.json),
[analysis](../results/study-20261022T202535Z-c5b8f8/analysis.json), and
[receipt/history/deadline evidence audit](../results/study-preparation-final-20261022T202617Z/evidence-audit.json).
All 16 feasible R episodes safely completed after the seed; all 8 infeasible R
episodes produced correct scripted refusals. A had 16 safe clean episodes; its
scripted attacks produced 8 prohibited effects in B0 and zero in B2. These are
engineering expectations, not new LLM findings or a measured feedback advantage.

After this complete matrix, only the analysis model-drift guard, its two tests
and the corresponding protocol sentence changed. The execution runner, oracle,
fixtures, schedule, limits and model configuration are byte-identical to that run.
The 56-episode matrix was not unnecessarily repeated for an analysis-only change.
Its original plan digest is preserved; the analysis records its own source digest.
Fresh direct controls bind the current review plans, whose digests differ.

The review package contains the exact ordered matrices, source archive and both
dry-run plans (zero API calls, no credentials):

- [Main: 56 ordered episode positions](../results/study-review-20261022T204654Z/main-matrix.csv)
- [Fallback: 32 ordered episode positions](../results/study-review-20261022T204654Z/fallback-matrix.csv)
- [Main plan](../results/study-review-20261022T204654Z/main-plan.json),
  digest `1e00f5af637f0bcc2cef3ceace884591ffc2956cf5086a4ab5fa4da27a3ee3ad`
- [Fallback plan](../results/study-review-20261022T204654Z/fallback-plan.json),
  digest `6ddfa3d228d70c75808b4e741f2eb07194685c4fa73bd235bb4913900f49f6f8`
- [Source snapshot](../results/study-review-20261022T204654Z/source_snapshot.zip)
- [Independent arithmetic check of all 14 literal answers](../results/study-preparation-final-20261022T202617Z/label-arithmetic-check.json)

The arithmetic check is automated engineering validation, not an independent
human review. The review template remains unapproved.

Earlier candidate evidence is retained: the first suite exhausted the isolated
8 MiB test tmpfs by accumulating per-test checkpoints; the next exposed two test
harness assumptions (reused local paths and host-only manifest files). The fixes
release only pytest-owned per-case files and correct the test doubles; production
resource limits were not increased. Both unsuccessful check directories and their
source snapshots remain at `checks-20261022T195946Z-ea121b` and
`checks-20261022T200100Z-745e51`. The intermediate 379-test pass and the earlier
56-episode candidate fake run also remain in `results/`; none is relabeled as
final-candidate or scientific LLM evidence. Result directory timestamps are UTC,
which was still 22 October during this 23 October local preparation session.

[The consolidated review verification](../results/study-review-20261022T204654Z/verification.json)
records current plan/image hashes, the analysis-only difference after the full fake
matrix, and byte-for-byte preservation of all 385 prior result files and README.
Docker teardown left zero experiment containers and zero disposable channel
volumes. New real-model episodes and paid API attempts are both zero. No commit
or push was performed. The setup is ready for independent review; human label
attestation and explicit approval of a paid batch remain pending.
