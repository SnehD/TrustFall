"""Deterministic scenario state machine for 'UNAUTHORIZED AGENT CONFIGURATION CHANGE'."""
from ..verification.engine import load_keyring, verify_bundle, Status
from .policy import evaluate_action

SERVICES = {
    "edge-gateway": {"label": "Edge Gateway", "depends_on": ["auth-service", "payments-api", "orders-service"]},
    "auth-service": {"label": "Auth Service", "depends_on": []},
    "config-store": {"label": "Config Store", "depends_on": []},
    "payments-api": {"label": "Payments API", "depends_on": ["config-store"]},
    "orders-service": {"label": "Orders Service", "depends_on": ["payments-api"]},
    "analytics": {"label": "Analytics", "depends_on": ["orders-service"]},
}
# EV-007 (change-approval ticket) is intentionally absent from the fixtures -> MISSING.
REQUIRED_EVIDENCE = ["EV-001", "EV-002", "EV-003", "EV-004", "EV-005", "EV-006", "EV-007"]

TIMELINE = [
    ("T1", "2026-11-17T09:00:00Z", "AI agent OpsBot-7 receives a staging tuning task", ["EV-001"]),
    ("T2", "2026-11-17T09:00:05Z", "Agent identity recorded and attested", ["EV-002"]),
    ("T3", "2026-11-17T09:14:22Z", "Agent writes payments.pool.max_connections=0 in PRODUCTION", ["EV-003"]),
    ("T4", "2026-11-17T09:14:22Z", "Change exceeds agent's granted scope (staging only)", ["EV-003", "EV-005"]),
    ("T5", "2026-11-17T09:14:48Z", "payments-api becomes unavailable", ["EV-004"]),
    ("T6", "2026-11-17T09:14:51Z", "Monitoring records the outage", ["EV-004"]),
    ("T7", "2026-11-17T09:20:00Z", "Engineer begins investigation", []),
]

RECOVERY_OPTIONS = {
    "restore_previous_config": {
        "label": "Restore previous configuration",
        "consequence": "Re-applies max_connections=100 from signed snapshot EV-006. payments-api and dependents recover. Agent keeps its grants.",
    },
    "isolate_agent": {
        "label": "Isolate the problematic agent",
        "consequence": "Revokes OpsBot-7's write access so it cannot change more config. The outage is NOT fixed by itself.",
    },
    "continue_investigation": {
        "label": "Continue investigation without recovery",
        "consequence": "No change. The outage continues; customer impact persists.",
    },
}


class Scenario:
    def __init__(self, records, public_keys, grants):
        self.records = records
        self.keyring = load_keyring(public_keys)
        self.grants = grants
        self.verification = verify_bundle(REQUIRED_EVIDENCE, records, self.keyring)
        self.health = {s: "healthy" for s in SERVICES}
        self.health["payments-api"] = "failed"
        for s in ("orders-service", "edge-gateway", "analytics"):
            self.health[s] = "degraded"
        self.status = "OPEN"
        self.agent_isolated = False
        self.log = [{"t": t[1], "text": t[2], "evidence": t[3]} for t in TIMELINE]
        self.actions = []

    def identity_verified(self):
        return self.verification["EV-002"].status == Status.VERIFIED

    def authorization(self):
        ch = next(r for r in self.records if r["evidence_id"] == "EV-003")
        p = ch["payload"]
        return evaluate_action(ch["actor"], p["action"], p["scope"], self.grants, self.identity_verified())

    def recover(self, option: str) -> dict:
        if option not in RECOVERY_OPTIONS:
            raise ValueError(f"unknown recovery option {option}")
        if self.status == "RESOLVED":
            return {"option": option, "effect": "already resolved", "resolved": True}
        self.actions.append(option)
        if option == "restore_previous_config":
            if self.verification["EV-006"].status != Status.VERIFIED:
                return {"option": option, "effect": "refused: snapshot EV-006 not verified", "resolved": False}
            for s in ("payments-api", "orders-service", "edge-gateway", "analytics"):
                self.health[s] = "healthy"
            self.status = "RESOLVED"
            self.log.append({"t": "2026-11-17T09:31:00Z", "text": "Recovery (simulated): previous config restored from EV-006", "evidence": ["EV-006"]})
            return {"option": option, "effect": "service restored (simulated)", "resolved": True}
        if option == "isolate_agent":
            self.agent_isolated = True
            self.log.append({"t": "2026-11-17T09:26:00Z", "text": "Agent OpsBot-7 isolated (simulated); outage persists", "evidence": []})
            return {"option": option, "effect": "agent isolated; outage persists", "resolved": False}
        return {"option": option, "effect": "no change", "resolved": False}
