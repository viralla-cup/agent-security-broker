"""Content-free public pilot evidence; complete synthetic exchanges remain private."""

from dataclasses import asdict

from .fixtures import canary_for
from .oracle import evaluate_pilot
from .pilot_observation import classify_episode
from security_audit.events import AuditContext


def public_snapshot(state, references):
    """Do not publish model-controlled filenames or protected contents."""
    return {references.reference("res", path): {
        key: value for key, value in metadata.items() if key in ("type", "size", "sha256")
    } for path, metadata in state.items()}


def summarize_episodes(rows, *, fake_engineering_pass, paired_initial_states_and_containment_equal):
    """Aggregate observed outcomes without treating completion as recovery."""
    evidence_kinds = sorted({row["evidence_kind"] for row in rows})
    claims = ["No feedback-benefit, spontaneous-attack-detection or portability claim."]
    if "fake_backend_engineering" in evidence_kinds:
        claims.append("Fake-backend continuation is scripted engineering evidence.")
    if "real_model_pilot" in evidence_kinds:
        claims.append("Real-model outcomes require separate checks for safe completion, "
                      "policy denial and safe completion after denial.")
    return {
        "report_phase": "post_run", "episodes": len(rows), "evidence_kinds": evidence_kinds,
        "actual_llm_episodes": sum(row["actual_llm_episodes"] for row in rows),
        "real_api_attempts": sum(row["real_api_attempts"] for row in rows),
        "deny_origin_counts": {origin: sum(row["observed"]["deny_origin_counts"][origin] for row in rows)
                               for origin in ("harness_setup", "model_selected", "unattributed")},
        "outcome_episode_counts": {
            key: sum(bool(row["observed"][key]) for row in rows)
            for key in ("task_completed", "safe_task_completed", "deny_event_observed",
                        "policy_denial_observed", "recovery_eligible", "continued_after_denial",
                        "safe_completion_after_denial")
        },
        "fake_engineering_pass": fake_engineering_pass,
        "paired_initial_states_and_containment_equal": paired_initial_states_and_containment_equal,
        "claims": " ".join(claims),
    }


def export_episode(task, condition, backend, limits, episode, loop, exchanges, calls, healthy, after):
    canary = canary_for(episode.seed)
    classification = classify_episode(loop["stop_reason"], healthy=healthy)
    receipts = getattr(episode, "receipts", ())
    harness_requests = getattr(episode, "harness_requests", ())
    observed = evaluate_pilot(task, episode.before, after, exchanges, canary,
                              model_proposals=[c.get("proposal") for c in calls], model_calls=calls,
                              receipts=receipts, harness_requests=harness_requests,
                              infrastructure_ok=classification["episode_valid"])
    classification = classify_episode(loop["stop_reason"], healthy=healthy,
                                      observation_complete=observed["observation_complete"])
    observed["infrastructure_ok"] = classification["episode_valid"]
    observed.update(classification)
    # Reporting only: keep the independent oracle's eligibility/continuation labels.
    # A fail-closed evaluation error is a DENY event, not a completed policy denial.
    denials = [e["audit"] for e in exchanges if e["audit"].get("decision") == "DENY"]
    observed.update(
        deny_event_count=len(denials), deny_event_observed=bool(denials),
        policy_denial_observed=any(e.get("evaluation_status") == "COMPLETED" for e in denials),
    )
    references = AuditContext()
    public_outcome = {key: value for key, value in observed.items() if key not in ("changed_paths", "action_origins")}
    public_outcome["changed_resources"] = [references.reference("res", path) for path in observed["changed_paths"]]
    public = {
        "report_phase": "post_run",
        "task": task["id"], "condition": condition,
        "backend": backend.name, "model": backend.model, "limits": asdict(limits),
        "loop": loop, "observed": public_outcome, "isolation": episode.isolation,
        "observed_steps": len(exchanges), "observed_model_calls": len(calls),
        "before": public_snapshot(episode.before, references),
        "after": public_snapshot(after, references),
        "model_calls": [{key: value for key, value in call.items() if key != "proposal"} for call in calls],
        "tool_trace": [{"audit": e["audit"], "feedback_status": e["response"]["status"],
                        "retryable": e["response"]["retryable"], "origin": observed["action_origins"][i]}
                       for i, e in enumerate(exchanges)],
        "actual_llm_episodes": int(backend.name != "deterministic-fake"
                                   and any(c["metadata"].get("response_received") for c in calls)),
        "real_api_attempts": sum(c["metadata"].get("request_sent", True) for c in calls)
        if backend.name != "deterministic-fake" else 0,
        "evidence_kind": "fake_backend_engineering" if backend.name == "deterministic-fake" else "real_model_pilot",
    }
    raw = {"task": task, "loop": loop, "exchanges": exchanges, "model_calls": calls,
           "operation_receipts": receipts, "harness_requests": harness_requests,
           "before": episode.before, "after": after, "observed": observed}
    return public, raw
