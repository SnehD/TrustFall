"""TEST-ONLY deterministic fixture signing.

Private keys are derived from a public, documented, non-secret label so test vectors are
reproducible (Ed25519 signing is deterministic). These keys protect nothing and must never
be used for real systems. No private key material is stored in the repository.
"""
import base64
import hashlib
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from ..verification.engine import sign_record

KEY_IDS = ("key-audit-1", "key-monitor-1", "key-policy-1")


def derive_fixture_key(key_id: str) -> Ed25519PrivateKey:
    seed = hashlib.sha256(f"trustfall-TEST-ONLY-fixture-key:{key_id}".encode()).digest()
    return Ed25519PrivateKey.from_private_bytes(seed)


def public_key_b64(key_id: str) -> str:
    raw = derive_fixture_key(key_id).public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return base64.b64encode(raw).decode()


def public_keys() -> dict:
    return {k: public_key_b64(k) for k in KEY_IDS}


def _rec(eid, typ, ts, actor, payload, key):
    return sign_record({"evidence_id": eid, "type": typ, "timestamp": ts, "actor": actor,
                        "payload": payload, "signing_key_id": key}, derive_fixture_key(key))


def scenario_records() -> list:
    A = "agent-opsbot-7"
    return [
        _rec("EV-001", "agent.task_assigned", "2026-11-17T09:00:00Z", A,
             {"task": "Tune connection pool for payments-api in STAGING", "requested_by": "eng-lead-12", "scope": "staging"}, "key-audit-1"),
        _rec("EV-002", "agent.identity_attestation", "2026-11-17T09:00:05Z", A,
             {"agent_id": A, "name": "OpsBot-7", "build": "opsbot@4.2.1", "attested_by": "identity-service"}, "key-audit-1"),
        _rec("EV-003", "config.change", "2026-11-17T09:14:22Z", A,
             {"service": "config-store", "key": "payments.pool.max_connections", "old": 100, "new": 0,
              "scope": "production", "action": "config.write"}, "key-audit-1"),
        _rec("EV-004", "monitor.outage", "2026-11-17T09:14:51Z", "monitoring",
             {"service": "payments-api", "state": "failed", "symptom": "connection pool size 0; requests rejected",
              "since": "2026-11-17T09:14:48Z"}, "key-monitor-1"),
        _rec("EV-005", "policy.snapshot", "2026-11-17T08:00:00Z", "policy-service",
             {"agent_id": A, "grants": [{"action": "config.read", "scopes": ["staging", "production"]},
                                        {"action": "config.write", "scopes": ["staging"]}]}, "key-policy-1"),
        _rec("EV-006", "config.snapshot", "2026-11-17T09:10:00Z", "config-store",
             {"service": "config-store", "key": "payments.pool.max_connections", "value": 100, "scope": "production"}, "key-audit-1"),
    ]
