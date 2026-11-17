import base64
import copy
import json
from pathlib import Path

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.verification.engine import verify_record, verify_bundle, load_keyring, sign_record, Status
from app.verification.canonical import canonical_bytes, CanonicalizationError
from app.services.fixtures import scenario_records, public_keys, derive_fixture_key
from app.services.scenario import Scenario, REQUIRED_EVIDENCE
from app.services.policy import evaluate_action
from app.ai.investigator import investigate, validate_ai_output, RejectedAIOutput, deterministic_investigation
from app.reporting.report import build_report, to_markdown
from app.connectors.jenkins import fetch_recent_builds

GRANTS = json.loads((Path(__file__).resolve().parents[2] / "sample-data" / "policies.json").read_text())["grants"]


@pytest.fixture
def ring():
    return load_keyring(public_keys())


@pytest.fixture
def recs():
    return scenario_records()


def new_sc():
    return Scenario(scenario_records(), public_keys(), GRANTS)


# ---- Evidence verification (8 required cases)
def test_valid_signed_record(recs, ring):
    assert verify_record(recs[0], ring).status == Status.VERIFIED


def test_tampered_record(recs, ring):
    r = copy.deepcopy(recs[2]); r["payload"]["scope"] = "staging"
    assert verify_record(r, ring).status == Status.INVALID


def test_invalid_signature(recs, ring):
    r = copy.deepcopy(recs[0]); r["signature"] = base64.b64encode(b"x" * 64).decode()
    assert verify_record(r, ring).status == Status.INVALID


def test_signature_from_wrong_key_invalid(recs, ring):
    r = sign_record({k: v for k, v in recs[0].items() if k != "signature"}, Ed25519PrivateKey.generate())
    assert verify_record(r, ring).status == Status.INVALID


def test_missing_signature(recs, ring):
    r = copy.deepcopy(recs[0]); del r["signature"]
    assert verify_record(r, ring).status == Status.MISSING


def test_malformed_record(ring):
    assert verify_record({"evidence_id": "EV-X"}, ring).status == Status.INVALID
    assert verify_record("nope", ring).status == Status.INVALID
    assert verify_record({"evidence_id": "E", "type": "t", "timestamp": "t", "actor": "a", "payload": {}, "signing_key_id": "key-audit-1",
                          "signature": "!!!not-base64!!!"}, ring).status == Status.INVALID


def test_unknown_signing_key(recs, ring):
    r = copy.deepcopy(recs[0]); r["signing_key_id"] = "key-rogue"
    assert verify_record(r, ring).status == Status.UNKNOWN


def test_missing_evidence_in_bundle(recs, ring):
    res = verify_bundle(REQUIRED_EVIDENCE, recs, ring)
    assert res["EV-007"].status == Status.MISSING
    assert res["EV-003"].status == Status.VERIFIED


def test_deterministic_vector(recs):
    # Ed25519 is deterministic: same key + canonical bytes -> same signature, every run.
    again = scenario_records()
    assert [r["signature"] for r in recs] == [r["signature"] for r in again]
    assert canonical_bytes(recs[0]).startswith(b'{"actor":"agent-opsbot-7"')


def test_floats_rejected_in_canonicalization():
    with pytest.raises(CanonicalizationError):
        canonical_bytes({"payload": {"x": 1.5}})


# ---- Authorization is separate from identity
def test_unauthorized_action_with_valid_identity():
    sc = new_sc()
    a = sc.authorization()
    assert a.identity_verified is True and a.authorized is False


def test_policy_allows_staging_write():
    d = evaluate_action("agent-opsbot-7", "config.write", "staging", GRANTS, True)
    assert d.authorized


def test_unknown_agent_not_authorized():
    assert not evaluate_action("ghost", "config.write", "staging", GRANTS, False).authorized


# ---- Scenario & recovery
def test_initial_state():
    sc = new_sc()
    assert sc.health["payments-api"] == "failed" and sc.status == "OPEN"
    assert [e["text"] for e in sc.log][2].startswith("Agent writes")
    assert len(sc.log) == 7


def test_restore_resolves():
    sc = new_sc(); r = sc.recover("restore_previous_config")
    assert r["resolved"] and sc.status == "RESOLVED"
    assert set(sc.health.values()) == {"healthy"}
    assert "previous config restored" in sc.log[-1]["text"]


def test_isolate_does_not_fix_outage():
    sc = new_sc(); sc.recover("isolate_agent")
    assert sc.agent_isolated and sc.health["payments-api"] == "failed" and sc.status == "OPEN"


def test_continue_does_nothing():
    sc = new_sc(); n = len(sc.log); sc.recover("continue_investigation")
    assert sc.status == "OPEN" and len(sc.log) == n


def test_restore_refused_if_snapshot_tampered():
    recs = scenario_records(); recs[5]["payload"]["value"] = 5
    sc = Scenario(recs, public_keys(), GRANTS)
    assert not sc.recover("restore_previous_config")["resolved"] and sc.health["payments-api"] == "failed"


def test_unknown_recovery_option():
    with pytest.raises(ValueError):
        new_sc().recover("nuke")


# ---- AI
def _ver(sc):
    return {k: v.to_dict() for k, v in sc.verification.items()}


def test_ai_fallback_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    out = investigate(_ver(new_sc()), set(REQUIRED_EVIDENCE))
    assert out["source"] == "deterministic-fallback"
    assert any(f["kind"] == "hypothesis" for f in out["findings"])
    assert all(f["evidence_ids"] for f in out["findings"])


def test_ai_rejects_invented_evidence():
    sc = new_sc(); good = deterministic_investigation(_ver(sc)).model_dump()
    good["findings"][0]["evidence_ids"] = ["EV-999"]
    with pytest.raises(RejectedAIOutput):
        validate_ai_output(json.dumps(good), set(REQUIRED_EVIDENCE), _ver(sc))


def test_ai_rejects_fact_on_missing_evidence():
    sc = new_sc(); good = deterministic_investigation(_ver(sc)).model_dump()
    good["findings"][0]["evidence_ids"] = ["EV-007"]
    with pytest.raises(RejectedAIOutput):
        validate_ai_output(json.dumps(good), set(REQUIRED_EVIDENCE), _ver(sc))


def test_ai_rejects_malformed_and_falls_back():
    out = investigate(_ver(new_sc()), set(REQUIRED_EVIDENCE), call_model=lambda p: "not json")
    assert out["source"] == "deterministic-fallback"


def test_ai_accepts_valid_output():
    sc = new_sc(); good = deterministic_investigation(_ver(sc)).model_dump_json()
    out = investigate(_ver(sc), set(REQUIRED_EVIDENCE), call_model=lambda p: good)
    assert out["source"] == "ai-validated"


def test_ai_cannot_override_verification():
    recs = scenario_records(); recs[2]["payload"]["new"] = 50  # tamper EV-003
    sc = Scenario(recs, public_keys(), GRANTS)
    out = investigate(_ver(sc), set(REQUIRED_EVIDENCE))
    assert sc.verification["EV-003"].status == Status.INVALID
    assert out["confidence"] == "low" and out["findings"][0]["kind"] == "hypothesis"


# ---- Report accuracy
def test_report_reflects_state():
    sc = new_sc()
    r0 = build_report(sc, investigate(_ver(sc), set(REQUIRED_EVIDENCE)))
    assert r0["resolution_status"] == "UNRESOLVED" and r0["permission_findings"]["authorized"] is False
    assert r0["evidence_verification"]["EV-007"]["status"] == "MISSING"
    sc.recover("restore_previous_config")
    r1 = build_report(sc, investigate(_ver(sc), set(REQUIRED_EVIDENCE)))
    assert r1["resolution_status"] == "RESOLVED" and r1["affected_service"]["health"] == "healthy"
    assert "restore_previous_config" in to_markdown(r1)
    json.dumps(r1)


# ---- Connector
def test_connector_not_configured():
    s, ev = fetch_recent_builds("job", env={})
    assert s["state"] == "not_configured" and ev == []


ENV = {"JENKINS_URL": "http://jenkins.test", "JENKINS_USER": "u", "JENKINS_API_TOKEN": "t"}


def test_connector_success_and_readonly():
    seen = []

    def h(req):
        seen.append(req.method)
        return httpx.Response(200, json={"builds": [{"number": 7, "result": "FAILURE", "timestamp": 1, "url": "u"}]})
    s, ev = fetch_recent_builds("deploy", transport=httpx.MockTransport(h), env=ENV)
    assert s["state"] == "connected" and ev[0]["result"] == "FAILURE" and set(seen) == {"GET"}


def test_connector_http_error_safe():
    s, ev = fetch_recent_builds("d", transport=httpx.MockTransport(lambda r: httpx.Response(500)), env=ENV)
    assert s["state"] == "error" and ev == []


def test_connector_timeout_safe():
    def h(req):
        raise httpx.ConnectTimeout("t")
    s, ev = fetch_recent_builds("d", transport=httpx.MockTransport(h), env=ENV)
    assert s["state"] == "error" and ev == []


def test_connector_bad_json_safe():
    s, ev = fetch_recent_builds("d", transport=httpx.MockTransport(lambda r: httpx.Response(200, content=b"<html>")), env=ENV)
    assert s["state"] == "error"
