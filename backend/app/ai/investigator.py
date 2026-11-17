"""AI investigator: strict schema, evidence-grounded, deterministic fallback.

AI output can never change verification results; it is rejected if it cites unknown
evidence IDs, omits references, or asserts a 'fact' backed by non-VERIFIED evidence.
"""
import json
import os
from typing import List, Literal
from pydantic import BaseModel, ValidationError, field_validator


class Finding(BaseModel):
    statement: str
    kind: Literal["fact", "hypothesis"]
    evidence_ids: List[str]


class Investigation(BaseModel):
    suspected_root_cause: str
    findings: List[Finding]
    supporting_evidence: List[str]
    affected_components: List[str]
    investigation_steps: List[str]
    suggested_recovery: str
    confidence: Literal["low", "medium", "high"]
    confidence_explanation: str
    unresolved_questions: List[str]

    @field_validator("findings")
    @classmethod
    def nonempty(cls, v):
        if not v:
            raise ValueError("findings required")
        return v


class RejectedAIOutput(ValueError):
    pass


def validate_ai_output(raw: str, known_ids: set, verification: dict) -> Investigation:
    try:
        inv = Investigation.model_validate(json.loads(raw))
    except (json.JSONDecodeError, ValidationError) as e:
        raise RejectedAIOutput(f"schema validation failed: {e}") from e
    for f in inv.findings:
        if not f.evidence_ids:
            raise RejectedAIOutput(f"finding without evidence reference: {f.statement!r}")
        bad = [e for e in f.evidence_ids if e not in known_ids]
        if bad:
            raise RejectedAIOutput(f"unknown evidence ids {bad}")
        if f.kind == "fact":
            unverified = [e for e in f.evidence_ids if verification[e]["status"] != "VERIFIED"]
            if unverified:
                raise RejectedAIOutput(f"fact relies on unverified evidence {unverified}")
    if set(inv.supporting_evidence) - known_ids:
        raise RejectedAIOutput("supporting_evidence contains unknown ids")
    return inv


def deterministic_investigation(verification: dict) -> Investigation:
    v = lambda e: verification[e]["status"]
    missing = [e for e in verification if v(e) == "MISSING"]
    facts_ok = all(v(e) == "VERIFIED" for e in ("EV-003", "EV-004", "EV-005"))
    if facts_ok:
        findings = [
            Finding(statement="OpsBot-7 wrote max_connections=0 in production config-store.", kind="fact", evidence_ids=["EV-003"]),
            Finding(statement="OpsBot-7's grants allow config.write only on staging.", kind="fact", evidence_ids=["EV-005"]),
            Finding(statement="payments-api was recorded as failed 26 seconds after the change.", kind="fact", evidence_ids=["EV-003", "EV-004"]),
            Finding(statement="The zero pool size caused the payments-api outage (timing and dependency support this; no record directly proves causation).",
                    kind="hypothesis", evidence_ids=["EV-003", "EV-004"]),
        ]
    else:
        findings = [Finding(statement="Core evidence is not fully verified; no conclusion can be drawn.", kind="hypothesis", evidence_ids=["EV-003"])]
    return Investigation(
        suspected_root_cause="An unauthorized production config write by OpsBot-7 (pool size 0) likely exhausted payments-api's connection pool.",
        findings=findings,
        supporting_evidence=["EV-003", "EV-004", "EV-005"],
        affected_components=["config-store", "payments-api", "orders-service", "edge-gateway", "analytics"],
        investigation_steps=["Confirm payments-api logs show pool-size-0 errors", "Find who requested production access for OpsBot-7", "Review other changes by OpsBot-7"],
        suggested_recovery="Restore max_connections=100 from verified snapshot EV-006, then review OpsBot-7's scopes.",
        confidence="medium" if facts_ok else "low",
        confidence_explanation=("Facts are signature-verified; causation is a hypothesis; approval record is missing." if facts_ok else "Evidence incomplete."),
        unresolved_questions=[f"Evidence {m} is missing: was the change approved?" for m in missing] + ["Why did a staging task touch production?"],
    )


def investigate(verification: dict, known_ids: set, call_model=None) -> dict:
    """call_model(prompt)->str is injected (tests) or built from ANTHROPIC_API_KEY. Any failure -> deterministic fallback."""
    source, inv = "deterministic-fallback", None
    if call_model is None and os.environ.get("ANTHROPIC_API_KEY"):
        call_model = _anthropic_call
    if call_model:
        try:
            inv = validate_ai_output(call_model(_prompt(verification)), known_ids, verification)
            source = "ai-validated"
        except Exception:
            inv = None
    if inv is None:
        inv = deterministic_investigation(verification)
    d = inv.model_dump()
    d["source"] = source
    return d


def _prompt(verification: dict) -> str:
    return ("Return ONLY JSON matching the Investigation schema (suspected_root_cause, findings[{statement,kind,evidence_ids}], "
            "supporting_evidence, affected_components, investigation_steps, suggested_recovery, confidence, confidence_explanation, "
            "unresolved_questions). Cite only these evidence IDs with statuses: "
            + json.dumps({k: v["status"] for k, v in verification.items()})
            + ". Label unproven causation as hypothesis. Admit insufficient evidence.")


def _anthropic_call(prompt: str) -> str:
    import httpx
    r = httpx.post("https://api.anthropic.com/v1/messages",
                   headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01"},
                   json={"model": os.environ.get("TRUSTFALL_AI_MODEL", "claude-sonnet-5-5"), "max_tokens": 1500,
                         "messages": [{"role": "user", "content": prompt}]}, timeout=20.0)
    r.raise_for_status()
    return r.json()["content"][0]["text"]
