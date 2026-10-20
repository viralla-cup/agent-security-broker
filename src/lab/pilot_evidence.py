"""Content-free public pilot evidence; complete synthetic exchanges remain private."""

from dataclasses import asdict

from .fixtures import canary_for
from .oracle import evaluate_pilot
from security_audit.events import AuditContext


def public_snapshot(state, references):
    """Do not publish model-controlled filenames or protected contents."""
    return {references.reference("res", path): {
        key: value for key, value in metadata.items() if key in ("type", "size", "sha256")
    } for path, metadata in state.items()}


def export_episode(task, condition, backend, limits, episode, loop, exchanges, calls, healthy, after):
    canary = canary_for(episode.seed)
    infrastructure_ok = healthy and loop["stop_reason"] not in {
        "INFRASTRUCTURE_ERROR", "TRANSPORT_ERROR", "BACKEND_ERROR", "BACKEND_TIMEOUT",
        "BACKEND_HTTP_ERROR", "BACKEND_RESPONSE_LIMIT",
    }
    observed = evaluate_pilot(task, episode.before, after, exchanges, canary,
                              model_proposals=[c.get("proposal") for c in calls], infrastructure_ok=infrastructure_ok)
    references = AuditContext()
    public_outcome = {key: value for key, value in observed.items() if key != "changed_paths"}
    public_outcome["changed_resources"] = [references.reference("res", path) for path in observed["changed_paths"]]
    public = {
        "task": task["id"], "condition": condition,
        "backend": backend.name, "model": backend.model, "limits": asdict(limits),
        "loop": loop, "observed": public_outcome, "isolation": episode.isolation,
        "observed_steps": len(exchanges), "observed_model_calls": len(calls),
        "before": public_snapshot(episode.before, references),
        "after": public_snapshot(after, references),
        "model_calls": [{key: value for key, value in call.items() if key != "proposal"} for call in calls],
        "tool_trace": [{"audit": e["audit"], "feedback_status": e["response"]["status"],
                        "retryable": e["response"]["retryable"]} for e in exchanges],
        "actual_llm_episodes": int(backend.name != "deterministic-fake"
                                   and any(c["metadata"].get("response_received") for c in calls)),
        "real_api_attempts": len(calls) if backend.name != "deterministic-fake" else 0,
        "evidence_kind": "fake_backend_engineering" if backend.name == "deterministic-fake" else "real_model_pilot",
    }
    raw = {"task": task, "loop": loop, "exchanges": exchanges, "model_calls": calls,
           "before": episode.before, "after": after, "observed": observed}
    return public, raw
