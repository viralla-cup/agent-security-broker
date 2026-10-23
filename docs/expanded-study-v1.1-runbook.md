# Expanded Study v1.1 Main: review, launch and resume

This runbook implements the [prospective amendment](../experiments/expanded-study-v1.1.md).
Status: offline preparation only; independent review and paid authorization pending.
The initial and first corrective v1.1 reviews failed (P1/P2). Corrective code requires a new independent
verification; previous offline results or approval files do not attest this revision.
v1 sources/results are not migrated. The article title and scientific protocol
remain unchanged except for the explicitly documented execution amendment.

## Offline commands

```powershell
docker build --tag agent-security-broker:mvp .
python scripts/run_checks.py
python scripts/run_expanded_study_v11.py --plan
python scripts/run_expanded_study_v11.py --run-id review-v11-main --backend fake
```

These commands require no API credentials. Fake behavior is scripted engineering
evidence. To exercise real Docker checkpoint/resume, use a NEW run ID:

```powershell
python scripts/run_expanded_study_v11.py --run-id review-v11-resume --backend fake --stop-after 2
python scripts/run_expanded_study_v11.py --run-id review-v11-resume --backend fake --status
python scripts/run_expanded_study_v11.py --run-id review-v11-resume --backend fake --resume
```

Main always has 56 positions; there is no v1.1 fallback or matrix override. The
offline stop-after option is rejected for OpenAI. A new run ID never reuses an
existing evidence directory. Status takes the run lock and creates/removes durable
verification state even for valid checkpoints. Interrupted verification or detected
corruption blocks resume. Never edit checkpoint files to force progress.

## Independent review and author authorization

Use the existing [review template](../experiments/study-review-template.json) for
the new exact v1.1 plan and its 16 fresh controls, image/source identity and
canonical control digest. The reviewer must independently approve the amendment,
unchanged labels/matrix/oracle, durable-before-I/O ordering, locks, recovery of an
unanchored committed tail, missing/corrupt-state rejection, all global budgets,
timeout gates, non-replay of uncertain positions, and public/private separation.
Old v1 approval cannot authorize v1.1. Do not self-complete the review record.

Separately, the author fills a copy of the
[segment authorization template](../experiments/study-v11-authorization-template.json)
in `.local/`. The first segment uses `segment: 1`, `checkpoint_head: null`, the
chosen unique run ID and exact approved plan hash. Only the author sets
`allow_paid_api: true`, their name and a fresh authorization ID. This authorizes
that execution segment, not automatic future resumes. Account credentials are
configured only on the trusted host using the existing first-live runbook; never
put a key into these files, arguments, chat, Git, logs, or containers.

Proposed launch, ONLY after separate explicit paid authorization:

```powershell
python scripts/run_expanded_study_v11.py --run-id main-v11-01 --backend openai --review-record .local/study-review-v11.json --authorization .local/study-v11-segment-1.json --allow-paid-api
```

Before any resume, inspect status without credentials:

```powershell
python scripts/run_expanded_study_v11.py --run-id main-v11-01 --status
```

The author must approve the surviving evidence/missingness and supply a NEW
authorization for the next segment number and exact `checkpoint_head` returned by
status. Preserve any orphan Docker evidence offline and resolve leftover resources;
the runner does not silently remove them. Keep the computer awake on stable power
and Docker running. Resume rechecks the approved sources/image and all 16 controls.

```powershell
python scripts/run_expanded_study_v11.py --run-id main-v11-01 --backend openai --resume --review-record .local/study-review-v11.json --authorization .local/study-v11-segment-2.json --allow-paid-api
```

The second filename is illustrative: use the actual next segment number. Stale
authorization, changed source/plan, corrupt evidence, concurrent execution or a
terminal safety/model/timeout stop cannot be bypassed by this command. Completed,
invalid and in-flight positions are never retried. A stopped segment with no final
episode record consumes that position and retains all partial artifacts. Missing
usage does not erase its durable API reservation.

Authorization is consumed before preflight. If preflight fails, status may show the
same next segment number but a new checkpoint head. Supply a fresh authorization ID
and head binding even in that case. Uncommitted metadata files remain preserved;
a subsequent attempt uses another unique metadata filename without replaying work.

## Evidence and interpretation

Public: `results/study-v1.1-<run-id>/`, including immutable plan, first preflight
controls/runtime, per-position episode reports, append-only progress snapshots,
per-segment metadata/summary, and a replaceable derived latest `summary.json`.
Private: `.local/study-v1.1/<run-id>/`, containing the authoritative journal/HEAD,
OS lock file, exact episode histories/receipts/snapshots and separate preserved
preflight evidence. Journal entries bind every committed final artifact; never
publish the private journal or raw evidence. Preflight/control IDs and digests
identify the control records retained under the private root.

If a crash occurs after files are saved but before the final commit, those files
remain uncommitted partial evidence. They are not silently converted into successes.
HEAD may lag a fully committed chain tail; that tail is validated and retained.
Removing an anchored entry or changing any committed evidence fails closed. An
adversary controlling the host can roll back all files together; this is outside
the existing trusted-host assumption. Power-loss durability depends on OS/storage
semantics. Source changes require a new reviewed plan, not ordinary resume.

`RESUME_BLOCKED/` under the private logical-run root is an unconditional permanent
stop, independent of journal HEAD and `run_stop` append success. Even an empty
directory blocks resume. Do not delete it or repair HEAD to reopen the run. Preserve
it for review together with the partial journal. A lagging HEAD without a detected
violation can still recover its complete, valid chain tail after an ordinary crash.

`VERIFYING/` is created durably BEFORE integrity-sensitive reads and removed only
after success, before writing the next journal event. Its presence also blocks
resume, even without `RESUME_BLOCKED/` or its reason file. This closes termination
between detection and error persistence. A crash during a valid but unfinished
check is conservatively blocked too. Preserve both markers for review. Ordinary
interrupted event/HEAD writes after completed verification retain valid-tail
recovery; no started position or reserved request is replayed.

An automatic timeout continuation additionally requires `operational_health` flags
in public/private episode records and a matching saved private service-evidence
digest. Fresh Docker availability does not repair a worker, execution, observation
or evidence-persistence failure in the timed-out episode. Such collisions stop the
segment, retain the invalid position, and never retry it automatically.

Hashes alone are insufficient: the gate now rechecks the frozen task, model-call
history/metadata, reservation journal, independently collected audit/receipt logs,
oracle outcomes and public/private report consistency. It reruns the existing
oracle, without changing task definitions or scientific labels. An inconsistent
episode cannot qualify for the isolated-timeout exception.

Analyze the latest saved summary using the existing analyzer (new output only):

```powershell
python scripts/analyze_expanded_study.py results/study-v1.1-main-v11-01/summary.json --output results/study-v1.1-main-v11-01/analysis-01.json
```

The summary additionally records global reservations, uncertain requests and
segments. The legacy analyzer's per-condition API/usage totals cover committed
episode records only; use the journal-derived summary for full-run spend accounting.
Report this difference explicitly. 56 planned or started positions does not mean
56 valid episodes or 28 usable pairs. Preserve negative outcomes and missingness.
No general security, feedback superiority, autonomous fake recovery or production
integration claim follows from these engineering checks.

Budget remains 336 requests across ALL segments, 2,752,512 input reservations and
344,064 output reservations; six requests and 120 seconds per episode. Timeout is
30 seconds capped by remaining episode time, without a hard cancellation watchdog.
The protocol's pricing assumptions yield $0.516096 before taxes, not a guaranteed
monetary cap. Plan approximately 3.5 active hours for Main, plus review/interruption
time; neither credit availability nor completion of all positions is guaranteed.
