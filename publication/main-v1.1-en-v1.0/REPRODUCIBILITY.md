# Offline public verification and reproduction

Run these commands from the repository root. A clean checkout of evidence commit 2777732c37c3b3ca7ac28dfc34850682ef41b2f1, plus this 35-file candidate at its documented location, is sufficient for the advertised public workflow. No internal working directory, private receipt, raw history or manuscript is an input. No command launches the study or calls a model service.

## Frozen identities and methods

- Reviewed implementation: a47904c43f03d1bf8feb08764722995aec967f83.
- Source: ea7f7dab488d20750098ee21606d426e0e435e0df80f8214321b05e73cb22801.
- Plan: 6d7a4153a1df255abf3f8b9076fd0576eeb46ed3a25e1814341d86232cc5646d.
- Image identity: sha256:4622dac95bac2d5687fe0033330a1681c3cd1240df794b04cdc3596f083b84b4; provenance only, no Docker execution needed.

Use the [v1 protocol and predeclared analysis](../../experiments/expanded-study-v1.md), [v1.1 amendment](../../experiments/expanded-study-v1.1.md), [frozen plan](../../results/study-v1.1-main-v11-01/plan.json), [final public summary](../../results/study-v1.1-main-v11-01/summary.json), [unchanged analyzer](../../scripts/analyze_expanded_study.py), [broker implementation](../../src/broker/) and [data dictionary](data_dictionary.txt).

Source/plan digests use the repository's canonical serialization. Manifest SHA-256 values bind exact bytes. These are different checks. Do not normalize historical CRLF.

## 1. Verify public bytes and numerical consistency

Requires Python 3.12. Verification-only mode uses the standard library and existing repository modules; it does not require ReportLab, Pillow, fonts or Poppler.

    python -B publication/main-v1.1-en-v1.0/render_publication.py --verify-only

Expected result: PUBLIC_CHECKS_PASSED_NOT_INDEPENDENT_REVIEW. This checks the exact manifest inventory, all 121 public evidence files, 66 frozen source files, canonical digests, all 56 progress-to-episode hash bindings, eleven CSV/JSON table representations, public outcome labels, operation-origin/decision counts, request/token totals, relative links and equality with the unchanged predeclared analyzer. It prints JSON and writes nothing.

The check compares public observations; it does not independently reconstruct the private oracle or prove the trusted host's honesty. Some supplemental scope/duplicate labels originate in the historical private audit. Readers can check aggregate consistency but cannot rediscover undisclosed proposals from these exports.

## 2. Run the frozen analyzer directly

Use a new sibling output filename; it must not already exist:

    python -B scripts/analyze_expanded_study.py results/study-v1.1-main-v11-01/summary.json --plan results/study-v1.1-main-v11-01/plan.json --output ../main-v1.1-analysis-reproduced.json

Compare parsed JSON with this package's data/predeclared_analysis.json; command 1 performs that exact comparison. Formatting is not the statistical comparison.

Paired direction is B2 minus B0 for A and B2 minus B2a for R. Both repetitions must be complete and valid for family aggregation. The exploratory bootstrap uses 10,000 whole-family resamples, seed 20261023, and requires four complete families. No R interval is eligible. Invalid #13/#52 and valid unsuccessful outcomes retain their original treatment.

## 3. Rebuild presentation and the findings PDF

Rendering requires preinstalled versions from [requirements-publication.txt](requirements-publication.txt), Poppler pdftoppm 26.07.0 and legally available fonts. Tested: Python 3.12.14, ReportLab 4.4.9, Pillow 12.3.0. Dependencies and fonts are not vendored; a machine without them must provision them before offline rendering. Verification and numerical analysis do not require these presentation dependencies.

Example for Windows with Arial and pdftoppm on PATH:

    python -B publication/main-v1.1-en-v1.0/render_publication.py --output ../main-v1.1-render-reproduced --font-regular C:/Windows/Fonts/arial.ttf --font-bold C:/Windows/Fonts/arialbd.ttf --font-italic C:/Windows/Fonts/ariali.ttf --pdftoppm pdftoppm

Use existing local font/executable paths on other systems. The italic option is optional; the regular face is used when absent. Alternative fonts may change pagination and require visual review. The new output directory must be outside the checkout and must not exist; reruns require a different name. This guard protects original inputs and outputs.

Nine files are produced after public verification: two figures each in PDF/SVG/600-dpi PNG, HTML tables, English captions, and pdf/scientific_findings_EN_v0.1.pdf built from the current scientific_findings_EN.md. The retained legacy PDF filename does not denote its content version; the title/footer identify v1.0, 27 October 2026. PDF file links are relative to its pdf/ location in this package. For complete navigation use the package reading copy or retain the package layout beside a reproduced copy.

The findings PDF uses a normalized metadata timestamp for deterministic rendering. The editorial date is stated in the title block and footer; the metadata timestamp is not a review date.

The report uses all Markdown sections, tables and figure captions. Numerical values and figure rates come from preserved data. Original figure sets remain unchanged here. Reproduced presentation files are separate outputs; no source evidence or validated CSV is rewritten. Rendering bytes depend on library/font versions and serialization; visual/content equivalence is the general claim.

## 4. Separate historical private audit

audit_analysis.py and supplementary_audit.py are unchanged historical scripts for an authorized reviewer. Both require private inputs and are **not part of commands 1-3**. Full reconstruction of the journal, histories, receipts, service observations, private proposal attribution and oracle inputs is unavailable from public files alone.

The main audit binds the original 1,865-file evidence inventory and original repository-relative layout. Arbitrary relocation will not satisfy that binding. Private locations and raw inputs are not distributed. An authorized reviewer must use preserved private evidence and fresh outputs. This preparation does not execute those scripts, create authorization or modify historical PENDING fields.

## Review and integrity limits

The historical AI review is described, with limited scope and non-public source metadata, in [provenance.json](provenance.json). It is not human peer review or approval of this edition. Independent review remains pending; see the [reviewer checklist](README.md#independent-review-checklist).

No public command reproduces stochastic responses or reruns the experiment. Hashes establish byte consistency, not human identity, alias stability, billing or correctness of undisclosed evidence.
