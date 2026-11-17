"""Incident report generated strictly from scenario state."""
from ..services.scenario import SERVICES


def build_report(sc, ai: dict) -> dict:
    auth = sc.authorization()
    return {
        "incident_id": "INC-2026-1117-001",
        "title": "UNAUTHORIZED AGENT CONFIGURATION CHANGE",
        "timeline": sc.log,
        "affected_service": {"id": "payments-api", "label": SERVICES["payments-api"]["label"], "health": sc.health["payments-api"]},
        "agent": {"id": "agent-opsbot-7", "name": "OpsBot-7", "identity_verified": auth.identity_verified},
        "permission_findings": {"authorized": auth.authorized, "reason": auth.reason},
        "evidence_verification": {k: v.to_dict() for k, v in sc.verification.items()},
        "suspected_root_cause": ai["suspected_root_cause"],
        "root_cause_source": ai.get("source"),
        "supporting_evidence": ai["supporting_evidence"],
        "recovery_actions": sc.actions,
        "resolution_status": "RESOLVED" if sc.status == "RESOLVED" else "UNRESOLVED",
        "remaining_uncertainties": ai["unresolved_questions"],
    }


def to_markdown(r: dict) -> str:
    L = [f"# Incident {r['incident_id']}: {r['title']}", "", f"**Status:** {r['resolution_status']}", "",
         "## Affected service", f"{r['affected_service']['label']} ({r['affected_service']['health']})", "",
         "## Agent", f"{r['agent']['name']} (`{r['agent']['id']}`) - identity verified: {r['agent']['identity_verified']}", "",
         "## Permission findings", f"Authorized: {r['permission_findings']['authorized']}. {r['permission_findings']['reason']}", "",
         "## Timeline"]
    L += [f"- {e['t']} - {e['text']} {e['evidence']}" for e in r["timeline"]]
    L += ["", "## Evidence verification"]
    L += [f"- {k}: **{v['status']}** - {v['reason']}" for k, v in r["evidence_verification"].items()]
    L += ["", "## Suspected root cause", f"{r['suspected_root_cause']} (source: {r['root_cause_source']})", "",
          "## Supporting evidence", ", ".join(r["supporting_evidence"]) or "none", "",
          "## Recovery actions", ", ".join(r["recovery_actions"]) or "none", "", "## Remaining uncertainties"]
    L += [f"- {u}" for u in r["remaining_uncertainties"]]
    L += ["", "_A VERIFIED signature proves record integrity for a configured key, not safety, authorization, or causation._"]
    return "\n".join(L)
