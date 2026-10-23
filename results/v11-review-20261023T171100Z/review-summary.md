# Expanded Study v1.1 Main: final offline verification

**Ready for independent review only. Independent review and author authorization are PENDING.** No real model requests, real credential access, commit or push occurred during this work. Reviewed baseline remains `3be02741ad3a8f0edf298e5b0cf80266fd07f0d8`.

The [change summary](change-summary.md) lists the exact eight source/documentation files added or modified. The scientific corpus, 56-position schedule, 28 planned pairs, condition ordering, Security Core, policy, executor and oracle remain unchanged; see [scientific invariants](scientific-invariants.json). The [amendment](../../experiments/expanded-study-v1.1.md) explicitly changes execution policy. Historical v1 attempts are not imported or relabeled.

## Final verification

| Check | Result | Evidence |
| --- | --- | --- |
| Full engineering suite on final source/image | 486 passed in 17.39 seconds | [test output](../checks-20261023T171009Z-4dae92/stdout.txt) |
| Fresh real-Docker controls before each segment | 16/16 + 16/16 | [final run](../study-v1.1-offline-main-reviewed-20261023/summary.json) |
| Final-source Docker fake Main with planned stop/resume | 56 valid episodes, 28 complete valid pairs, two segments | [oracle and preservation audit](evidence-audit.json) |
| Broker identities and seed/history/deadline transfer | 56 unique broker sessions; verified receipt associations, counters and deadlines | [audit](evidence-audit.json) |
| Repeated completed resume | Zero additional requests; all 1,693 run files unchanged | [no-op proof](completed-resume-check.json) |
| Legacy fake pilot | 6/6 engineering expectations passed | [pilot](../pilot-20261023T162036Z-a55c08/summary.json) |
| Legacy replay | 15/15 passed | [replay](../dev-20261023T162036Z-6814af/summary.json) |
| Native Windows writer lock | Concurrent writer rejected; lock released after process kill | [check](windows-lock-check.json) |
| Preservation and teardown | 4,264 preexisting evidence files plus 1,693 earlier offline-Main files unchanged; no leftover experiment containers/volumes | [audit](evidence-audit.json) |

All fake behavior is deterministic engineering evidence, not autonomous LLM recovery or a B2 advantage. Validity does not imply task success: infeasible cases and expected B0 effects remain separately reported. The unchanged analyzer's [descriptive output](analysis.json) is engineering-only.

Regression coverage includes an uninterrupted 56-position mock run, interruption between episodes, actual process death during mocked in-flight transport, unknown delivery and reservations, duplicate/concurrent resume, missing/corrupt events/HEAD/artifacts, recoverable unanchored tail, timeout thresholds across segments, setup/incomplete observation, budgets, model/source changes, orphan metadata, and authorization consumption before failed preflight. Native Windows locking was checked before the last correction; its implementation is unchanged. The 33 components relevant to the legacy pilot/replay also remain byte-identical. Intermediate failing engineering checks and the earlier complete Main are preserved and identified in [verification.json](verification.json).

The packaged [read-only audit](verify-recorded-evidence.py) rechecks the saved final run using local private evidence and the local preparation preservation manifests. It does not contact a provider. Private evidence is intentionally absent from this review archive.

## Frozen review target

- Plan SHA-256: `0dd712482d29c323306d0430675ab3659f609c191cdaf60b4fbea69c6d777a6b`
- Canonical source-manifest SHA-256: `7f9765068dd6b99299d9fd48484686eaaef2e739927aaf830e815ff8fbc05c58`
- Docker image: `sha256:2d1ba38dc7d8ae4af11f5ac2e1d7615803a3427336ec4e359ce2ff84d19c6c5f`
- Docker engine: `29.8.1`
- [Source snapshot](source_snapshot.zip): 61 manifest files plus README, both protocols and the v1.1 runbook; all 65 archive entries match current files.
- [Exact Main matrix](main-matrix.csv) and [frozen plan](plan.json).

## Launch and resume boundaries

Offline plan and reproducible fake run (choose a new run ID):

```powershell
python -B scripts/run_expanded_study_v11.py --plan
python scripts/run_expanded_study_v11.py --run-id review-v11-main --backend fake
```

Proposed paid launch, **not executed**, only after independent review and separate explicit author approval:

```powershell
python scripts/run_expanded_study_v11.py --run-id main-v11-01 --backend openai --review-record .local/study-review-v11.json --authorization .local/study-v11-segment-1.json --allow-paid-api
```

Read-only status, then a separately authorized resume:

```powershell
python scripts/run_expanded_study_v11.py --run-id main-v11-01 --status
python scripts/run_expanded_study_v11.py --run-id main-v11-01 --backend openai --resume --review-record .local/study-review-v11.json --authorization .local/study-v11-segment-2.json --allow-paid-api
```

Use the actual next segment number and current checkpoint head. A preflight failure consumes its approval even if the next segment number stays the same. A new authorization ID and head binding are required. Never replay started positions or edit the journal to force progress. Configure credentials only on the trusted host using the [existing first-live instructions](../../docs/first-live-pilot.md); no credentials belong in the archive, approval records or containers. See the [full runbook](../../docs/expanded-study-v1.1-runbook.md).

## Limits and remaining review

Keep gpt-6-luna, reasoning `none`, six requests/actions and three denials per episode (including the recovery seed), zero retries, 120 seconds per episode and a 30-second socket timeout capped by remaining time. Input reservations are at most 8,192/request and output at most 1,024/request. Global ceilings across all segments are 336 requests, 2,752,512 estimated input tokens and 344,064 output tokens.

The unchanged v1 pricing assumptions ($0.125/M input and $0.50/M output, not newly verified prices) imply $0.516096 before tax. This is not a guaranteed monetary cap. Unknown delivery/billing is never assumed free. Plan approximately 3.5 active hours per separately approved segment, plus controls, review and interruptions. Credit expiration/availability was not checked.

The reviewer must approve the prospective timeout/continuation rules, per-segment time-planning amendment, exact source/plan/image, unchanged scientific inputs and outcomes, durable-before-I/O ordering, authorization gates, crash recovery, global budgets and public/private separation. Socket timeout is not a hard cancellation watchdog; trusted-host rollback, OS/storage failure and differential missingness remain limitations. A complete schedule may contain fewer than 28 usable pairs. See [limitations](limitations-and-review.md).

**No independent attestation or paid approval was completed by the implementation agent. Stop here for author review.**
