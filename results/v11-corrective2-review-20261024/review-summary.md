# Expanded Study v1.1 — second corrective review package

Prepared 24 October 2026 (Asia/Qyzylorda; execution log timestamps use UTC).
Status: **implementation evidence for narrow independent re-review, not an
independent PASS or paid-run authorization**. Existing uncommitted work and commit
`3be02741ad3a8f0edf298e5b0cf80266fd07f0d8` are preserved.

## Reproduced before correction

`reproduce.py before` ran against the preceding corrective Docker image, using
the real local broker/Core, Agent Loop, receipts and filesystem executor, with a
deterministic timeout backend and its actual reservation interface. No network
transport was present. All four independent mutations to private evidence allowed
the next original schedule position: false send marker, false observation status,
missing receipts, and a changed task prompt. The healthy control also continued.
Each case had a separate temporary run and retained its first position.

A separate child process rolled an active writer's HEAD back to a valid older
anchor, then called `os._exit(29)` immediately before block-marker creation.
Reload accepted the journal and a synthetic paid-ledger segment could enter
position 2. There were no API requests or real approval credentials. Before-output
source hashes match `before-source.zip` and the task-start source inventory.

Exact script, command and output: `reproduce.py`, `reproduce-before-command.json`,
`reproduce-before-stdout.txt`. The final corrected replay is recorded separately
in `reproduce-after-final-command.json` and `reproduce-after-final-stdout.txt`.
All four negative cases now stop with their invalid position retained; the healthy
control continues. The child termination now prevents reload/resume.

## P1: semantic evidence verification

The new `src/lab/study_timeout.py` validates evidence, without changing the oracle
or policy. The journal supplies trusted plan, position, backend and reservations.
The verifier checks:

- Actual saved public report equals the returned row; task identity/hash matches
  the frozen task; initial state matches its independent fixture declaration.
- Private calls match every reservation/result's index, number, segment, outcome
  and metadata. All preceding calls are proposals; the final call is a sent,
  unanswered timeout. Paid/fake accounting mode is bound to the journal backend.
- Complete call histories equal the common prompt/setup plus the preceding
  proposal/feedback sequence; origins and execution associations remain checked.
- Separately collected broker audit/receipt logs equal the retained records,
  with no pending writes. Missing receipt fields, gaps, inconsistent fingerprints,
  unreadable files, or even rehashed contradictory service data are rejected.
- The existing export/oracle pipeline recomputes observations and reports from
  the verified inputs. Both private observation records, public outcomes, loop
  counts, traces and anonymized before/after/change relationships must agree.

The prior independent worker/execution/observation/evidence-health gates remain.
The fresh runtime check is reached only after all these checks. Validation also
runs when a continued timeout is committed and when its journal is reloaded.
Hashing alone never establishes consistency. Resource pseudonyms remain anonymous;
their value/change relationships are compared without publishing a private map.

## P2: durable verification lifecycle

Before reading integrity-sensitive checkpoint/input/evidence state, create
`VERIFYING/` and synchronize its parent directory where supported. Only a successful
verification removes it. An exception, interruption or process exit leaves it as
an unconditional resume block, even if `RESUME_BLOCKED/` cannot be created.
Journal load, active HEAD/tail/evidence checks and runner source/input checks use
this protocol. Status now takes the run lock and performs the same write-capable
verification. Do not delete either marker to reopen a run.

Successful verification completes before ordinary event/HEAD persistence begins.
Thus an event committed before a crash updating HEAD can still be recovered as a
valid unanchored tail. Requests/positions are never repeated or refunded. Pure
transition/budget checks remain separate from evidence verification. A crash
during an otherwise valid verification is conservatively blocked: an unfinished
check is not proof of success. This is an explicit operational limitation.

## Exact scope

Modified since this task began:

- `src/lab/study_journal.py`
- `scripts/run_expanded_study_v11.py`
- `tests/test_study_v11.py`
- `tests/test_study_v11_corrective.py`
- `experiments/expanded-study-v1.1.md`
- `docs/expanded-study-v1.1-runbook.md`

Added:

- `src/lab/study_timeout.py`
- `tests/study_timeout_helpers.py`
- `tests/study_integrity_crash.py`
- `tests/test_study_v11_second_corrective.py`

Old timeout test doubles now generate consistent local-broker/ledger/service
evidence; they do not bypass the new verifier. `scripts/run_expanded_study.py`,
Security Core, policy, task definitions, oracle, first-live/pair entry points and
analysis code are unchanged during this pass. The patch in this package compares
with the task-start snapshot, including previously untracked sources.

## Offline results

Final targeted invocation inside the restricted Docker test container:

```text
python -m pytest -q -p no:cacheprovider tests/test_study_v11.py tests/test_study_v11_corrective.py tests/test_study_v11_second_corrective.py
```

**111 passed**, including all 70 earlier v1.1/corrective regressions and 41 new
cases. New coverage includes the four reported contradictions, related missing or
contradictory records, a timeout after actual local read/write effects, the mock
Responses adapter with paid-ledger reservations, 16 child-process termination
boundaries, and three verification-storage failures. HTTP doubles use synthetic
test labels only and cannot contact a provider.

Full invocation: `python -B scripts/run_checks.py` — **549 passed**. Exact final
output location, source/image digest and restricted container configuration are
in `verification.json`. Earlier successful intermediate outputs (70, 109 and 547)
remain preserved and are not substituted for the final revision's results.

`verify-native-process.py` repeats process termination on the native Windows
filesystem: detection before the block write, during checking, before successful
guard removal, and an ordinary committed tail before HEAD update. The first three
block; the last recovers. See `native-process-final-stdout.txt`. No private raw
experimental content is included in these outputs.

`prepare-review.py` verifies previous evidence hashes, source equality in the
Docker image, no leftover experiment resources and unchanged scientific inputs.
See `verification.json`, `source-manifest.json`, `plan.json`,
`source-snapshot.zip`, `corrective-only.patch`, and `review-manifest.json`.

## Preserved boundaries and remaining limits

Main still has exactly 56 positions and 28 planned pairs. Corpus, ordering,
scientific labels, model, policy, oracle, token/request budgets and timeout limits
are unchanged. Only source/protocol/plan identities and explicit verification
rule flags change. Previous evidence is byte-preserved; no failed result is
rewritten or selectively rerun. This work launches no experimental batch, fresh
production control series or real LLM episode, and performs no commit/push.

The protection assumes a trusted host and normal local filesystem persistence.
It does not protect against unrestricted host modification/deleting guards or
total storage rollback, and is not a universal power-loss guarantee. If guard
creation cannot complete, verification and provider I/O do not begin. A valid but
unfinished verification sacrifices resumability; operators must preserve its
evidence instead of removing markers. An old valid HEAD first observed with no
active-check history remains indistinguishable from an ordinary interrupted HEAD
update. Provider timeout uncertainty/cancellation/billing limitations are unchanged.

The final revision has not run a new full production Docker-worker Main or real
model batch. Its evidence is offline engineering evidence. Independent review
should narrowly repeat the five original counterexamples, positive continuation,
the crash lifecycle and earlier P1/P2 tests on the exact new digests. Before paid
execution, fresh matching controls, a genuine independent PASS and separate
explicit author approval remain required. This package creates none of those
attestations and stops for independent verification.
