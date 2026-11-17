"""Generate sample-data/* and web/data/scenario.json from the backend (single source of truth).
Run:  python tools/export_scenario.py
"""
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.fixtures import scenario_records, public_keys  # noqa: E402
from app.services.scenario import Scenario, SERVICES, TIMELINE, RECOVERY_OPTIONS, REQUIRED_EVIDENCE  # noqa: E402
from app.ai.investigator import investigate  # noqa: E402
from app.verification.engine import verify_record  # noqa: E402

GRANTS = {"agent-opsbot-7": [{"action": "config.read", "scopes": ["staging", "production"]},
                             {"action": "config.write", "scopes": ["staging"]}]}

GRAPH = {
    "nodes": [
        {"id": "agent", "label": "OpsBot-7", "kind": "agent", "evidence": ["EV-001", "EV-002"], "detail": "AI agent agent-opsbot-7. Identity attested (EV-002)."},
        {"id": "change", "label": "Config change", "kind": "change", "evidence": ["EV-003"], "detail": "payments.pool.max_connections 100 -> 0 in PRODUCTION."},
        {"id": "event", "label": "Outage record", "kind": "event", "evidence": ["EV-004"], "detail": "Monitoring: payments-api failed at 09:14:48Z."},
        {"id": "service", "label": "Payments API", "kind": "service", "evidence": ["EV-004"], "detail": "Depends on config-store."},
        {"id": "policy", "label": "Permission policy", "kind": "policy", "evidence": ["EV-005"], "detail": "config.write granted for STAGING only."},
        {"id": "verify", "label": "Verification", "kind": "verification", "evidence": ["EV-002", "EV-003", "EV-004", "EV-005"], "detail": "Signatures VERIFIED. This proves integrity, not authorization."},
        {"id": "recovery", "label": "Recovery action", "kind": "recovery", "evidence": ["EV-006"], "detail": "Restore max_connections=100 from signed snapshot EV-006."},
    ],
    "edges": [
        {"from": "agent", "to": "change", "kind": "fact", "why": "EV-003 actor is agent-opsbot-7.", "evidence": ["EV-003"]},
        {"from": "change", "to": "policy", "kind": "fact", "why": "Change scope 'production' is outside granted scope 'staging' (EV-005).", "evidence": ["EV-003", "EV-005"]},
        {"from": "change", "to": "event", "kind": "hypothesis", "why": "Outage began 26s after the change and payments-api depends on the changed key. Timing and dependency suggest causation; no record proves it.", "evidence": ["EV-003", "EV-004"]},
        {"from": "event", "to": "service", "kind": "fact", "why": "EV-004 reports payments-api failed.", "evidence": ["EV-004"]},
        {"from": "verify", "to": "agent", "kind": "fact", "why": "EV-002 signature verifies: identity VERIFIED (not the same as authorized).", "evidence": ["EV-002"]},
        {"from": "verify", "to": "change", "kind": "fact", "why": "EV-003 signature verifies: record is untampered.", "evidence": ["EV-003"]},
        {"from": "recovery", "to": "service", "kind": "hypothesis", "why": "Restoring the verified snapshot should recover payments-api.", "evidence": ["EV-006"]},
        {"from": "recovery", "to": "change", "kind": "fact", "why": "EV-006 is the value before the change.", "evidence": ["EV-006", "EV-003"]},
    ],
}


def write(p: Path, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main():
    records, keys = scenario_records(), public_keys()
    sc = Scenario(records, keys, GRANTS)
    ver = {k: v.to_dict() for k, v in sc.verification.items()}
    inv = investigate(ver, set(ver))
    auth = sc.authorization().to_dict()

    # tamper demo, computed by the real verifier
    tampered = copy.deepcopy(records[2])
    tampered["payload"]["scope"] = "staging"
    tamper = verify_record(tampered, sc.keyring).to_dict()

    sd = ROOT / "sample-data"
    write(sd / "incident.json", {"incident_id": "INC-2026-1117-001", "title": "UNAUTHORIZED AGENT CONFIGURATION CHANGE",
                                 "services": SERVICES, "timeline": [{"id": t[0], "time": t[1], "text": t[2], "evidence": t[3]} for t in TIMELINE],
                                 "required_evidence": REQUIRED_EVIDENCE})
    write(sd / "agent.json", {"agent_id": "agent-opsbot-7", "name": "OpsBot-7", "build": "opsbot@4.2.1",
                              "declared_capabilities": ["config.read", "config.write", "ticket.comment"]})
    write(sd / "policies.json", {"grants": GRANTS})
    write(sd / "public_keys.json", keys)
    for r in records:
        write(sd / "evidence" / f"{r['evidence_id']}.json", r)

    write(ROOT / "web" / "data" / "scenario.json", {
        "incident": {"id": "INC-2026-1117-001", "title": "UNAUTHORIZED AGENT CONFIGURATION CHANGE"},
        "services": SERVICES,
        "initial_health": sc.health,
        "timeline": [{"id": t[0], "time": t[1], "text": t[2], "evidence": t[3]} for t in TIMELINE],
        "agent": {"agent_id": "agent-opsbot-7", "name": "OpsBot-7", "capabilities": ["config.read", "config.write", "ticket.comment"],
                  "grants": GRANTS["agent-opsbot-7"]},
        "records": records, "public_keys": keys, "required_evidence": REQUIRED_EVIDENCE,
        "verification_precomputed": ver, "authorization_precomputed": auth,
        "investigation": inv, "graph": GRAPH, "recovery_options": RECOVERY_OPTIONS,
        "tamper_demo": {"description": "EV-003 with scope edited production->staging, verified by the Python engine", "result": tamper},
        "connector": {"name": "jenkins", "state": "not_configured", "verified_live": False},
    })
    print("exported; verification:", {k: v["status"] for k, v in ver.items()}, "tamper:", tamper["status"])


if __name__ == "__main__":
    main()
