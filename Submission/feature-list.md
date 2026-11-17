# Feature List (implemented; see Docs/LIMITATIONS.md for test status)
- Miniature 3D infrastructure city with 6 services, animated dependency links, failure beacon, agent marker
- Incident banner, onboarding card, timeline of 7 events (click to highlight in graph)
- AI Agent Inspector: capabilities, grants, recorded actions, IDENTITY vs AUTHORIZATION verdicts
- Spatial evidence graph: select, highlight neighbours, evidence status, "why connected", FACT vs HYPOTHESIS, trace
- Ed25519 evidence verification (Python + in-browser WebCrypto), tamper test, 4 outcomes
- Evidence-grounded AI investigator with schema validation and deterministic fallback
- Simulated recovery (3 options) updating city, graph, timeline and report
- Incident report export: Markdown + JSON
- Read-only Jenkins connector (mock-tested)
- Hands-first input code (pinch ray, fingertip poke); optional controllers; desktop dev mouse

Tech: three.js 0.160.0, WebXR, WebCrypto, Python 3.13, FastAPI, cryptography, pydantic, pytest.
