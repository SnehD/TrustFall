# Architecture

```
backend/app
  verification/   canonical.py (canonical JSON) · engine.py (Ed25519 verify/sign, VERIFIED/INVALID/MISSING/UNKNOWN)
  services/       policy.py (authorization) · scenario.py (state machine, recovery) · fixtures.py (TEST-ONLY signing)
  ai/             investigator.py (pydantic schema, evidence grounding, fallback, optional Anthropic call)
  reporting/      report.py (JSON + Markdown from scenario state)
  connectors/     jenkins.py (read-only GET, timeout, normalization)
  main.py         FastAPI wrapper (optional)
tools/export_scenario.py   backend → sample-data/*.json + web/data/scenario.json  (single source of truth)
web/
  index.html      importmap (three@0.160.0), HUD
  src/engine.js   UMD logic: state, WebCrypto verification, recovery, graph queries, report
  src/ui.js       canvas panels + hit-tested buttons + sprites
  src/main.js     three.js scene, XR input router, panels
  tests/          node tests for engine.js
```
Design rules: logic is separate from rendering (`engine.js` has no THREE dependency, so it is testable headlessly); all selection goes through one `activateHit` path fed by four input sources: XR pinch ray, XR fingertip poke, XR controller ray (optional), desktop mouse (dev stand-in, labelled as such). The Python and JS engines implement the same rules and are tested against the same scenario data.

Scene layout (seated, arm-reach): city table at 1.0 m ahead; evidence graph floating above it; Agent/Timeline panel left; Evidence/Verify/AI/Recover/Report panel right; incident banner above.
