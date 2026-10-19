# Initial literature evidence matrix

This is a selective reading record for supplied archive versions. It establishes
specific precedents, not the novelty or empirical effectiveness of our prototype.
PDF page numbers below are one-based file pages. Archive hashes and page counts are
in `literature_inventory.json`; publisher metadata must be reconciled before the
manuscript bibliography is finalized.

| Supported claim | Source and location | Relevance and limit |
| --- | --- | --- |
| Runtime enforcement through structured rules already exists. | AgentSpec, supplied ICSE 2026 PDF, p. 1, abstract (printed p. 2938). | Triggers, predicates, and enforcement are prior mechanisms; our YAML broker cannot claim to invent runtime checking. Their measurements are not our results. |
| Utility and attacker success can be checked against environment state. | AgentDojo, supplied NeurIPS 2024 PDF, p. 2, Figure 1 and Introduction. | Motivates separate outcome checks. Our five custom filesystem cases are not AgentDojo scores. |
| Control/data-flow separation and capability-based policies are prior defenses. | Defeating Prompt Injections by Design, arXiv:2503.18813v2, 24 June 2025, p. 1. | CaMeL is a relevant comparison; this filesystem broker does not implement its program-flow or information-flow mechanism. |
| An LLM can generate a plan and guardrail code for checking agent actions. | GuardAgent, supplied workshop-marked version, pp. 1–2, abstract and Introduction. | Distinguishes generated guardrail code from this fixed trusted executor. Does not establish that GuardAgent lacks resource binding. |
| Adaptive generation and optimization of safety checks are studied. | AGrail, supplied ACL 2025 PDF, p. 1, abstract (printed p. 8104). | Requires mechanism-level comparison before claiming model independence or adaptation is new. |
| Task alignment checking can provide feedback during agent interaction. | Task Shield, supplied ACL 2025 PDF, pp. 1–2, abstract and Figure 1. | Feedback after intervention is prior work; the proposed B2/B2a comparison must measure a narrower claim rather than presume novelty. |

Metadata hazards actually observed: the Tool Learning survey PDF has a placeholder
DOI on its first page; do not copy it. The supplied GuardAgent first page includes
Nathaniel D. Bastian and a workshop notice, so the older manuscript's author list
and claimed publication version cannot simply be reused. The supplied ToolSandbox
first page uses Felix Bai, whereas the earlier draft lists Haoping Bai; reconcile
the version and official metadata rather than guessing.

No “first”, superior-security, universal model compatibility, or complete prevention
claim follows from this matrix. A focused review of mechanisms, released code, limits,
and relevant later publications remains necessary before positioning the article.

## Technical implementation references

Python's official [os documentation](https://docs.python.org/3.12/library/os.html)
documents descriptor-relative filesystem calls and flags used by the Linux executor.
Docker's official [container runtime documentation](https://docs.docker.com/engine/containers/run/)
documents the containment options used by the harness. These references explain
interfaces; they do not verify this implementation or prove container isolation.
