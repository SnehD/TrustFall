# Verification Design

## Evidence record format
```json
{ "evidence_id": "EV-003", "type": "config.change", "timestamp": "2026-11-17T09:14:22Z",
  "actor": "agent-opsbot-7", "payload": { "...": "..." },
  "signing_key_id": "key-audit-1", "signature": "<base64 Ed25519>" }
```
Required: `evidence_id, type, timestamp, actor, payload (object), signing_key_id`. `signature` is excluded from the signed bytes.

## Canonical serialization
UTF-8 JSON, keys sorted, no whitespace, **no floats** (rejected). For float-free data this equals RFC 8785 (JCS) output. Implemented identically in `backend/app/verification/canonical.py` and `web/src/engine.js` (`canonical`).

## Signature scheme
Ed25519 via the maintained `cryptography` library (Python) and WebCrypto (browser). No custom primitives. Ed25519 signing is deterministic, so test vectors are stable (`test_deterministic_vector`).

## Outcomes
| Status | Meaning |
|---|---|
| VERIFIED | Signature validates against the configured public key for exactly this content. |
| INVALID | Signature fails, content was altered, or record is malformed. |
| MISSING | Required record absent, or record has no signature. |
| UNKNOWN | `signing_key_id` is not in the configured keyring, so verification cannot complete. |

**VERIFIED never means safe, authorized or causally responsible.** Authorization is a separate policy evaluation (`services/policy.py`), and the UI shows both verdicts side by side.

## Key handling
- Public keys: `sample-data/public_keys.json`.
- Fixture signing keys are derived from a public, documented, non-secret label (`services/fixtures.py`) so tests are reproducible. They are TEST-ONLY and protect nothing. **No private key file exists in the repo** (`.gitignore` blocks `*.pem`/`*.key`).
- Real deployments must sign in the evidence source (CI, monitoring, policy service) with keys held in an HSM/KMS, and distribute only public keys here.

## Known gap
The browser trusts the public keys shipped in `scenario.json`; a real deployment needs a trusted key distribution channel.
