# Public release boundaries

This document explains the scope of the release-facing documentation and offline
entry point. It does not revise the study, its analysis, or an existing review.

## Authoritative research material

The completed dataset is [Main v1.1, run main-v11-01](../results/study-v1.1-main-v11-01/).
Its 121 public-format files include all 56 episode records, their progress bindings,
the frozen plan, controls, metadata, and both execution segments. The authoritative
English research representation is the unchanged 35-file package
[publication/main-v1.1-en-v1.0](../publication/main-v1.1-en-v1.0/).

Its [package manifest](../publication/main-v1.1-en-v1.0/package_manifest.json)
hashes the other 34 files and excludes itself. The manifest's SHA-256 is
`8fa8089b6409260c61bdfae7ac000ab5a7903d9b30a07c68330b51a2f095f68d`.
[Provenance](../publication/main-v1.1-en-v1.0/provenance.json) binds the original
Main inputs and distinguishes unchanged analysis copies from editorial material.
This English package is not byte-identical to the earlier mixed-language analysis.

The frozen identities are:

| Identity | Value |
| --- | --- |
| Implementation commit | `a47904c43f03d1bf8feb08764722995aec967f83` |
| Source digest | `ea7f7dab488d20750098ee21606d426e0e435e0df80f8214321b05e73cb22801` |
| Plan digest | `6d7a4153a1df255abf3f8b9076fd0576eeb46ed3a25e1814341d86232cc5646d` |
| Recorded Docker image | `sha256:4622dac95bac2d5687fe0033330a1681c3cd1240df794b04cdc3596f083b84b4` |

Image identity is historical provenance; offline result verification does not
require Docker. A hash demonstrates byte or canonical-data consistency, not
reviewer identity, hidden model stability, or the truth of undisclosed evidence.

## Three different kinds of reproduction

**Level A: offline results verification.** From the repository root, with Python
3.12 and its standard library:

```powershell
python -B reproduce.py --offline
```

The root wrapper invokes the existing checker using the current Python executable,
`-B -S`, and repository-relative paths. It preserves the checker's JSON on stdout,
prints a short PASS or FAIL message on stderr, and propagates validation failures
as nonzero exit codes. It writes no files. The original command remains available:

```powershell
python -B publication/main-v1.1-en-v1.0/render_publication.py --verify-only
```

The checker validates the English package inventory and hashes, the bound Main
files and frozen source inputs, canonical source/plan digests, progress-to-episode
hashes, table consistency, denominators, preserved invalid outcomes, operation
origins, request/usage totals, and agreement with the frozen analyzer. It uses
neither an API key nor Docker, model inference, or an external network service.
Its success status is `PUBLIC_CHECKS_PASSED_NOT_INDEPENDENT_REVIEW`.

These checks reproduce the disclosed descriptive calculations. They do not
reconstruct the private journal, raw model histories, receipts, service evidence,
or the full oracle inputs. Supplemental proposal/duplicate classifications from
the historical private audit cannot all be independently rediscovered from the
sanitized exports. Public readers can check disclosed aggregates and consistency.

Presentation reproduction is a separate workflow documented in
[REPRODUCIBILITY](../publication/main-v1.1-en-v1.0/REPRODUCIBILITY.md). It needs the
listed rendering dependencies and fonts and writes to a new directory outside the
checkout. Rendering is not part of `--offline`; alternative runtime/font versions
may change presentation bytes and require visual review.

**Level B: deterministic broker demonstration.** The existing
[v1.1 runner](../scripts/run_expanded_study_v11.py) supports
`--backend fake --controls-only` with an unused run ID. It exercises declared
synthetic controls through Docker and creates new public/private evidence.
It does not establish real-model behavior. No `--demo` mode is added by this
publication patch; any future demonstration should run in an isolated checkout
and preserve all historical evidence.

**Level C: full LLM experiment reproduction.** Repeating model-dependent episodes
requires separately authorized API access, budget, model availability, and matching
conditions. It is not required for Level A and is never launched by the wrapper.
Historical pilot, fake, failed-attempt, and Main datasets must remain separate.

## Review statuses and historical records

The sealed provenance records a scoped AI-agent PASS for the earlier analysis on
24 October 2026. That review concerned the earlier analysis and its specified
evidence; it was not human journal peer review. It does not approve this new root
README, wrapper, or release-boundary document.

Historical `PENDING` fields in copied evidence and the English package remain
unchanged. They describe their recorded snapshot, not a live review register or
proof that no later review occurred. Any later review must identify its own scope,
reviewer type, source record, and exact artifact digest separately. Automated
consistency checks do not supply an independent scientific attestation or author
authorization. The final publication candidate still needs a separate release
review and the repository owner's publication decision.

## Privacy and publication decisions

At preparation, the GitHub repository is private. Committing research files to it
does not make them publicly available. A manuscript's availability statement must
match the access actually provided when submitted or published.

The release audit found user-specific host paths in eight historical files:

- `results/study-v1.1-offline-controls-final-20261024-3b83d4c793/verification/command.json`
- `results/study-v1.1-offline-controls-final-20261024-3b83d4c793/verification/runner-stdout.txt`
- `results/study-v1.1-offline-controls-final-20261024-3b83d4c793/verification/verification.json`
- `results/v11-corrective-review-20261023T182927Z/reproduce-before-command.json`
- `results/v11-corrective-review-20261023T182927Z/reproduce-after-command.json`
- `results/v11-corrective2-review-20261024/reproduce-before-command.json`
- `results/v11-corrective2-review-20261024/reproduce-after-command.json`
- `results/v11-corrective2-review-20261024/reproduce-after-final-command.json`

The values are not repeated here. These files are already in the private remote's
history. Editing a current copy would neither remove that history nor preserve
its original evidence bytes. The audit distinguished synthetic path-rejection
test strings from these user-specific paths. Credential-pattern screening found
no actual credentials in its checked scope; it is not a universal secrecy proof.

The original Russian findings report, mixed-language analysis and ZIP, internal
Astra manuscript and ZIP, third-party paper PDFs, and private `.local` records
remain local-only. The existing [ignore rules](../.gitignore) cover the identified
internal packages. The sealed provenance's filename/hash reference to the Russian
report records its origin; it does not include the report's content and must not
be silently rewritten. Do not archive the entire working directory or stage ignored
material with force.

The owner must choose between:

| Option | Privacy | Reproducibility and maintenance |
| --- | --- | --- |
| A: open the existing repository | Exposes its existing files and reachable history, including the identified host metadata; requires the owner's acceptance. | Retains original commit identities, chronology, and provenance links. One repository remains authoritative. The 937 legacy result files with historical LF/CRLF conversion remain outside the newer exact-byte guarantee. |
| B: publish a curated export in a separate repository | Can exclude the identified legacy metadata and original Git history. The original private repository remains intact. | Preserve required source/evidence bytes and relative layout, add an export manifest and upstream provenance, and rerun Level A. New commits have different identities; original historical hashes remain provenance references. A maintained mapping and two-repository workflow are required. |

Neither option is implemented by this patch. A curated export needs an explicit
allowlist and its own review; it must not claim to reproduce undistributed history
or the private audit. No release archive, visibility change, new public repository,
license, or formal manuscript citation is authorized here.

## Git preservation

Existing `-text` rules protect the 66 frozen source inputs, 121 Main files and
35 English publication files. Preserve these bytes for `core.autocrlf=true`,
`input`, and `false`; do not normalize historical files or regenerate their hashes.
See [Git byte preservation](git-byte-preservation.md) for historical limitations.

The new wrapper is at the repository root because adding Python files under
`scripts/` would expand the runner's dynamic source manifest. The wrapper and this
document are outside that frozen manifest and the Docker build context. Adding
release tooling must not change the study's source identity or sealed package.
