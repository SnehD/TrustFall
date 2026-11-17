"""Evidence verification engine (Ed25519 via the maintained `cryptography` library).

A VERIFIED result means ONLY: the signature validates against the configured public
key for the exact record content. It does NOT mean the action was safe, authorized,
or causally responsible. Authorization is evaluated separately (see policy.py).
"""
import base64
import binascii
from dataclasses import dataclass
from enum import Enum

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey, Ed25519PrivateKey

from .canonical import canonical_bytes, CanonicalizationError

REQUIRED_FIELDS = ("evidence_id", "type", "timestamp", "actor", "payload", "signing_key_id")


class Status(str, Enum):
    VERIFIED = "VERIFIED"
    INVALID = "INVALID"
    MISSING = "MISSING"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class VerificationResult:
    evidence_id: str
    status: Status
    reason: str

    def to_dict(self):
        return {"evidence_id": self.evidence_id, "status": self.status.value, "reason": self.reason}


def load_keyring(public_keys_b64: dict) -> dict:
    """{key_id: base64 raw 32-byte public key} -> {key_id: Ed25519PublicKey}."""
    ring = {}
    for kid, b64 in public_keys_b64.items():
        ring[kid] = Ed25519PublicKey.from_public_bytes(base64.b64decode(b64, validate=True))
    return ring


def sign_record(record: dict, private_key: Ed25519PrivateKey) -> dict:
    """Test-fixture helper. Production signing keys must live outside this repository."""
    out = {k: v for k, v in record.items() if k != "signature"}
    out["signature"] = base64.b64encode(private_key.sign(canonical_bytes(out))).decode("ascii")
    return out


def verify_record(record, keyring: dict) -> VerificationResult:
    if not isinstance(record, dict):
        return VerificationResult("?", Status.INVALID, "malformed: record is not an object")
    eid = record.get("evidence_id") if isinstance(record.get("evidence_id"), str) else "?"
    absent = [f for f in REQUIRED_FIELDS if f not in record]
    if absent:
        return VerificationResult(eid, Status.INVALID, f"malformed: missing fields {absent}")
    if not isinstance(record["payload"], dict) or not isinstance(record["signing_key_id"], str):
        return VerificationResult(eid, Status.INVALID, "malformed: bad field types")
    sig = record.get("signature")
    if sig in (None, ""):
        return VerificationResult(eid, Status.MISSING, "signature is missing")
    key = keyring.get(record["signing_key_id"])
    if key is None:
        return VerificationResult(eid, Status.UNKNOWN, f"signing key '{record['signing_key_id']}' is not configured")
    try:
        sig_bytes = base64.b64decode(sig, validate=True)
        msg = canonical_bytes(record)
    except (binascii.Error, TypeError, ValueError, CanonicalizationError) as e:
        return VerificationResult(eid, Status.INVALID, f"malformed: {e}")
    try:
        key.verify(sig_bytes, msg)
    except InvalidSignature:
        return VerificationResult(eid, Status.INVALID, "signature does not match record content")
    return VerificationResult(eid, Status.VERIFIED, "signature valid for configured key (says nothing about authorization)")


def verify_bundle(required_ids, records: list, keyring: dict) -> dict:
    """Verify every required evidence id; absent records -> MISSING."""
    by_id = {r.get("evidence_id"): r for r in records if isinstance(r, dict)}
    out = {}
    for eid in required_ids:
        if eid not in by_id:
            out[eid] = VerificationResult(eid, Status.MISSING, "required evidence record not available")
        else:
            out[eid] = verify_record(by_id[eid], keyring)
    return out
