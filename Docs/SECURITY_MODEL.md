# Security Model

**Trust boundaries:** evidence sources (signed) → verification engine → policy engine → UI. The AI investigator sits *outside* the trust boundary: its output is schema-validated, must cite known evidence IDs, may only label something a "fact" if all cited evidence is VERIFIED, and can never alter verification results (`test_ai_cannot_override_verification`, `test_ai_rejects_*`). On any failure the deterministic fallback is used.

**Secrets:** env vars only (`.env.example` has placeholders). Secret scan run over the repo (see `TEST_RESULTS.md`). No keys, tokens or personal data are stored.

**Connector:** Jenkins, HTTP GET only, 5 s timeout, errors reduced to a class name (no credential/URL leakage), sample-data fallback. Unverified against a live server.

**Recovery:** simulated in memory. Nothing touches real infrastructure.

**Threats not covered:** replay of old valid records (no freshness/nonce check), key distribution, revocation, transparency log, multi-party signing, real-time tamper detection, and authentication of the viewer. See `LIMITATIONS.md`.

**Web:** static page, no cookies, no user data collected; loads three.js from a pinned jsDelivr URL (self-host and add SRI for production).
