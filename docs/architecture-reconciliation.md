# Handover v1.2 architecture reconciliation

Date: 20 October 2026, Asia/Qyzylorda. Repository inspected from clean commit
`178eb72` (`feat: add structured security audit logging and CLI`), following
`0300686` (initial filesystem broker). This is a reconciliation and a narrow audit
contract correction, not a new Section 17 implementation or main experiment.

## Source and decision authority

The supplied `Journal_Article_Project_Handover_EN_v1.2_2026-10-20.docx` was read in
full. Its SHA-256 is
`abe21270688b87bf19192dc9abbfeedc6f14102acb0f6f2fb8c31a31145a1e0b`.
It supersedes v1.1 as architecture context. Both source records remain in
`source_inventory.json`; the local text extraction is ignored under `.local/`.
The original handover and earlier audits are historical, not deleted or rewritten.

The user's explicit confirmations govern: Variant C; automatic ALLOW/DENY without
ASK; no permission expansion during recovery; an independent Security Core as the
product, with future adapters; and an experimental LLM agent used only as a test
harness. These are author decisions, not supervisor approval or evidence of
effectiveness. Embedded instructions to begin Section 17 again or upload the
transfer package are not executed. The deadline remains 31 October 2026.

## Architecture mapped to evidence

| Confirmed direction | Existing implementation and evidence | Remaining qualification |
| --- | --- | --- |
| Security Core owns authority independently of the agent | `src/broker/` owns schema, policy, budgets, and executor; `src/security_audit/` owns observation. `src/lab/server.py` composes these in a separate process/container with a trusted task and UID-bound client. | This is a narrow prototype, not a packaged general product. Lab identity/defaults and experiment conditions remain in core code; extraction into a configurable public integration API is future work. No directory rename is needed to establish the existing boundary. |
| Proposals do not grant authority | Strict Action fields, fixed tools, trusted task ID and condition, immutable policy. Client has socket access only; executor owns the private laboratory. | Trusted orchestration and the independent observer can access the laboratory. They are not agent tools. An adapter must never expose their Docker access. |
| ALLOW/DENY without ASK | Current gate either dispatches or prevents dispatch; there is no approval route. | Audit schema 2 used a third label ERROR for caught pre-dispatch evaluation failure. Schema 3 corrects this representation without changing execution or feedback. |
| Bounded recovery under unchanged permissions | `Policy.safe_hint()` rechecks known public alternatives; each later Action passes the same gate; call, denial, and write budgets remain. | The scripted continuation only shows an available authorized path. An autonomous model loop, safe-stop behavior, and feedback benefit have not been measured. |
| Binding and constrained execution | Component checks followed by descriptor traversal, no symlink following, regular-file/hard-link checks, bounded reads, exclusive writes. Existing engineering tests cover these restrictions. | Some object checks occur inside the executor after dispatch. ALLOW is permission to attempt execution, not a statement that all object checks succeeded. Late rejection and partial failure are reported separately. No general concurrent-writer/TOCTOU claim. |
| Separate audit and agent feedback | Private audit JSONL and trusted observer; only the original six response fields reach the client. B2a reasons remain audit-only. | Logs are post-execution, disposable, unsigned, and not a durable transaction. The explicit `decision` in v1.2's proposed Result is not yet an agent-wire field; adding it requires an adapter contract change, not silently deriving it from `status`. |
| B0/B2/B2a, same outer containment | Historical 15-case-condition replay verifies identical initial snapshots and containment. B0 demonstrates the three targeted prohibited effects; B2/B2a prevent those effects in this corpus. | Shared executor restrictions, including link rejection, cannot be credited as a B2 advantage. This comparison is finite development replay. |
| Independent outcome checking | `src/lab/oracle.py` checks actual response disclosure, file inventory, and hashes; it does not import the policy evaluator. | Independent human label review and reproduction by the co-author are not documented as completed. |
| Test backends versus product adapters | `src/lab/` and replay scripts are trusted experimental infrastructure; no model or product adapters exist yet. | Real LLM episodes: zero. Codex/Claude Code/local-agent integration coverage is untested. Model API access alone does not secure those products. |

The future product adapter normalizes requests and returns feedback; it cannot
assign trusted identity, select B0, change policy, approve itself, or choose another
executor. Inventory all built-in tools, interpreters, direct storage/network paths,
and delegated execution before claiming coverage. Disable or isolate uncovered
paths, or explicitly limit the integration claim. Unavailable Core, invalid policy,
or timeouts must not release execution through controlled paths. These are acceptance
requirements for future adapters, not completed coverage tests.

## Narrow implemented correction

Schema 3 has only ALLOW/DENY decisions. A caught mandatory-evaluation failure is
`DENY`, `evaluation_status=FAILED`, `reason_code=EVALUATION_ERROR`,
`execution_status=NOT_STARTED`, and `dispatched=false`. Ordinary authorization has
`evaluation_status=COMPLETED`, including ordinary DENY. Executor failure stays
`ALLOW` with `execution_status=FAILED`; late guard rejection stays `ALLOW/REJECTED`.
Neither failure type is counted as demonstrated policy blocking or task completion.

The viewer validates new states, offers `--evaluation FAILED`, and keeps historical
schema 1/2 decisions readable without modifying their source. ERROR remains a
historical display/filter value only. Broker logic, YAML, executor, response fields,
B2a generic denial, counters, corpus, and oracle are unchanged. Existing transport
`status=error` is an execution/evaluation diagnostic, not a third authorization
decision. See `audit-log.md` for the contract and limitations.

Regression verification: **94 tests passed**, exit 0, reported pytest time **1.26 s**,
at `results/checks-20261020T053816Z-edbdba/`. New checks cover failed evaluation in
all three conditions without executor invocation or state changes, unchanged error
feedback/counters, historical schema compatibility, read-only error filtering, and
rejection of ASK/ERROR or contradictory states in schema 3. This is engineering
verification, not a new LLM experiment. No five-case replay was rerun.

The previous 84-test pass and 15/15 replay remain at
`results/checks-20261019T112424Z-d74e3e/` and
`results/dev-20261019T112424Z-99a1f4/`. Their original source snapshots, timestamps,
schema 2 events, and outcomes remain evidence for their recorded implementation.
They are not relabeled as schema 3 measurements.

Preservation and compatibility evidence is saved in
`results/reconciliation-20261020T054102Z-ed980d/verification.json` with the original
82-file digest manifest. All checked historical artifacts and unchanged execution
components match byte-for-byte. Four historical CLI views read 72 event rows
successfully (overlapping exports, not 72 independent calls). The current test
sources match their recorded hashes and are archived in the check run's
`source_snapshot.zip`. The normal repository `git diff --check` passes.

## Proposals and unresolved differences

- The user-supplied long working title remains in README. The shorter 92-character
  title in v1.2 is recorded for confirmation; supervisor title/scope/protocol approval
  remains pending. This discrepancy does not block local development.
- Additional tools (`list`, `replace_text`, `delete_file`), the richer Result object,
  twelve development cases, sixty replay cases, 432/192 episodes, and numerical
  thresholds are plans. Only two tools and five replay cases are implemented.
- B1/B3 and the installation simulator remain optional. B1 is an external human
  comparison, never an ASK mode in Core. No adversarial repository instructions
  have been added to the active repository.
- The backend/model, endpoint, authorized transfer, and budget are unresolved.
  The old missing-access check is historical, not a new check of every account.
- `Journal_Article_Handover_Notes.docx` remains unavailable in the supplied context.
  Its contents are not inferred. v1.2 names v1.1 with an `(1)` filename suffix;
  the original inspected artifact is retained under its actual supplied filename
  and digest rather than assumed byte-identical to that separately named file.
- HOL Guard is a comparison candidate awaiting primary-source review. Neither the
  handover nor its literature list establishes novelty. Journal website claims
  were not reverified in this code reconciliation.

## Continue the existing roadmap

1. **Completed and retained:** two-tool Core, path/link/budget checks, isolated
   synthetic lab, B0 feasibility, B2/B2a replay, independent oracle, and private
   audit with CLI. The binary audit correction above is the next completed increment.
2. **Next implementation:** a bounded experimental backend interface and agent loop
   using the existing socket and six-field feedback. Keep trusted task assignment,
   credentials, and Docker orchestration outside model control. Test doubles may
   verify loop logic but must be labeled engineering tests, never LLM evidence.
3. **First real model task:** once endpoint/model access and transfer/cost authority
   are available, read synthetic measurements and create `Mean: 4\n`; verify the
   actual response and output through the same oracle. Follow with separately labeled
   controlled denial recovery. Stop honestly when no authorized path exists.
4. **Before main evaluation:** cross-review labels, broaden benign/attack cases,
   record safe completion, correct refusal, and task failure separately, pilot a
   second genuine backend where feasible, then freeze scope/versions/analysis.
   The handover's dates are planning milestones, not evidence of completed work.
5. **After the article:** package the independent Core and assess product adapters
   individually with startup/error/timeout/bypass coverage tests. No product-adapter
   work, web dashboard, extra service, or policy expansion is introduced now.

Publication, external data transfer, submission, and spending still require explicit
author authorization. No such action or Git push was performed during reconciliation.
