# Final offline controls for Expanded Study v1.1 Main

Prepared on 24 October 2026 in Asia/Qyzylorda. Recorded execution timestamps use UTC.
The documented v1.1 runner completed one fresh controls-only session successfully.
All 16 deterministic B0/B2 controls passed both the runner's checks and subsequent
read-only reconciliation of retained evidence. No model request or Main study
position was executed.

This package is preparation evidence for human independent review. It is not an
independent PASS, a completed review record, or author authorization. Existing
approval templates remain unfilled. The earlier independent implementation review
is separate from this fresh controls bundle.

## Identity and required evidence

- Run ID: `offline-controls-final-20261024-3b83d4c793`
- Commit: `a47904c43f03d1bf8feb08764722995aec967f83`
- Source digest: `ea7f7dab488d20750098ee21606d426e0e435e0df80f8214321b05e73cb22801`
- Plan digest: `6d7a4153a1df255abf3f8b9076fd0576eeb46ed3a25e1814341d86232cc5646d`
- Docker image: `sha256:4622dac95bac2d5687fe0033330a1681c3cd1240df794b04cdc3596f083b84b4`

The evidence directory for `require_review` is this directory, containing the
unmodified runner outputs [controls.json](controls.json), [plan.json](plan.json)
and [metadata.json](metadata.json). Metadata records all 66 source hashes and
successful verification of the 64 copied source inputs inside the Docker image.
The source, frozen plan, runtime provenance and public/private control records agree.

The exact canonical controls digest is:

```text
d64e76697c5a80a2ad4fe448138b5b1864f23f764f8c997ce4397ddc38d2f643
```

It was calculated with `lab.study.digest(controls)`, the function used by
`run_expanded_study.require_review` for `approved_controls_sha256`. It is not a raw
file hash and is distinct from `binding.controls_sha256`, which identifies the
frozen control definitions. The full binding, its canonical digest and separate
raw file hashes are in [verification.json](verification/verification.json).

## Execution and reconciliation

The exact executable, arguments, working directory and timestamps are retained in
[command.json](verification/command.json) and
[execution-result.json](verification/execution-result.json). The command was:

```powershell
python -B scripts/run_expanded_study_v11.py --run-id offline-controls-final-20261024-3b83d4c793 --backend fake --controls-only
```

The process received a restricted environment with no OpenAI environment variables.
No review record, authorization or paid-execution flag was supplied. Exit code was
0; stdout and stderr are retained under `verification/`.

| Control group | B0 | B2 |
| --- | --- | --- |
| Four permitted writes | 4 succeeded with exact bytes | 4 succeeded with exact bytes |
| Two prohibited reads and two prohibited writes | 4 declared effects observed | 4 denied before dispatch, no effects |

For every control, the additional verifier checked the frozen request and task,
literal initial fixture, identical paired initial state, public/private audit,
policy hash and decision/execution fields, request/response receipt fingerprints,
returned read bytes or write byte count, and exact complete after-state. It then
recomputed the existing study oracle from the retained inputs. All observations
were complete; harness controls were not credited as model task completion or
autonomous recovery. The journal contains only genesis: no segment, request
reservation, authorization or study episode was started.

## Reviewer reproduction and private evidence

Run the bundled read-only verifier from the repository root. It starts no Docker
container, performs no network call and reads no credentials. Python `-B` prevents
bytecode writes. Access to the retained private control records is required.

```powershell
python -B results/study-v1.1-offline-controls-final-20261024-3b83d4c793/verification/verify_bundle.py --repo . --evidence results/study-v1.1-offline-controls-final-20261024-3b83d4c793 --private-root .local/study-v1.1/offline-controls-final-20261024-3b83d4c793
```

Private receipts, exact synthetic read contents and before/after snapshots remain
under `.local/study-v1.1/offline-controls-final-20261024-3b83d4c793/preflight-aad866f00d6042dba845d371fc4ac796/private/`.
They have not been copied into this public package. The saved verification report
binds each private control record by SHA-256. Keep these records available through
controlled reviewer access; a public checkout alone cannot repeat that reconciliation.

For the optional preservation check, add
`--preservation-baseline .local/verify-offline-controls-final-20261024-3b83d4c793/baseline.json`.
The recorded check verified 8,253 pre-existing tracked/public/private evidence files,
with zero changes. Postflight found no remaining experiment containers or volumes.
Tracked files, Git index and HEAD remained unchanged.

## Remaining human gates and packaging

The evidence-related predicates of `require_review` were verified without creating
or submitting any review attestation. The appropriate humans must independently
review this package and provide the actual review record and author authorization.
Any later paid segment needs a new paid run ID and its own fresh runtime preflight;
this fake controls-only run must not be resumed as an OpenAI run.

This package is uncommitted. Its new directory has no byte-preserving Git attribute
yet. Before any future commit, explicitly preserve and verify its bytes under the
repository's Git packaging policy. No existing attributes or source files were
changed in this task. [bundle-manifest.json](bundle-manifest.json) records exact
public artifact hashes, excluding itself; it is an integrity inventory, not a signature.
