# Trustfall — The AgentOps Command Center

A hands-first WebXR workspace (Meta Quest Browser) for investigating an incident caused by an AI agent. A miniature 3D infrastructure city shows service health; a spatial evidence graph connects the agent, the change, the outage, the policy and the recovery; cryptographic verification is kept strictly separate from authorization.

> **Status:** working vertical slice, tested on desktop (Edge) and in Meta's IWER emulated Quest 3 (hand pinch + poke). **Not yet tested on a physical Quest headset.** No APK exists. See `Docs/LIMITATIONS.md`.

Screenshots (desktop dev render, not headset footage): `Submission/screenshots/dev-*.png`.
Placeholders still needed: `Submission/screenshots/quest-*.png` (real headset/emulator captures).

## Implemented
- 3D city, 6 services, animated dependency links, failure beacon, agent marker, incident banner, onboarding.
- Scenario "UNAUTHORIZED AGENT CONFIGURATION CHANGE" with 7-step timeline.
- Agent inspector: **IDENTITY VERIFIED** and **ACTION NOT AUTHORIZED** shown as separate verdicts.
- Spatial evidence graph (7 nodes, 8 edges): select/highlight neighbours, evidence status, "why connected", FACT vs HYPOTHESIS, step-through trace.
- Ed25519 evidence verification: Python (`cryptography`) and live in-browser (WebCrypto Ed25519 when the browser supports it; otherwise precomputed results, labelled as such). VERIFIED / INVALID / MISSING / UNKNOWN. Tamper test.
- AI investigator: strict schema, evidence-ID grounding, deterministic fallback (default); optional Anthropic API if `ANTHROPIC_API_KEY` is set (backend only).
- Simulated recovery (3 options), live city/graph/timeline/report updates.
- Report export: Markdown + JSON (browser download; Python API too).
- Read-only Jenkins connector (backend; mock-tested, **not verified against a live server**).
- Input: XR pinch ray + fingertip poke code paths (device-untested), optional controllers, desktop mouse (dev stand-in only).

## Architecture
```
sample-data/  + tools/export_scenario.py  ──►  web/data/scenario.json
backend/app   verification (Ed25519, canonical JSON) · policy · scenario · recovery · ai · reporting · connectors
web/src       engine.js (logic, UMD) · ui.js (panels) · main.js (three.js + WebXR)
```
Details: `Docs/ARCHITECTURE.md`, `Docs/VERIFICATION_DESIGN.md`, `Docs/SECURITY_MODEL.md`.

## Prerequisites
Python 3.11+ (`pip install -r backend/requirements.txt`), any recent browser, Node (any version ≥ 8) for the JS logic tests. Quest 3/3S/Pro with Meta Quest Browser for VR.

## Run
```powershell
# regenerate data (only if you change the scenario)
python tools/export_scenario.py
# serve the web app
cd web ; python -m http.server 8765        # then open http://localhost:8765
# optional API
cd backend ; python -m uvicorn app.main:app --port 8000
```
URL params for scripted views: `?onboard=0&sel=service|change|agent&rtab=VERIFY|AI|RECOVER|REPORT&ltab=TIMELINE&recover=restore_previous_config&shot=1`.

## Test
```powershell
cd backend ; python -m pytest -q          # 31 tests
node web/tests/engine.test.js             # 16 tests
# browser + emulated-XR tests (needs Edge, `pip install websockets`, web/ served on :8765)
python web/tests/browser_test.py          # 29 checks
```
Results: `Docs/TEST_RESULTS.md`.

## Configuration
Copy `.env.example` to `.env` (placeholders only; never commit). Variables: `ANTHROPIC_API_KEY`, `JENKINS_URL`, `JENKINS_USER`, `JENKINS_API_TOKEN`.

## Quest
WebXR on Quest needs HTTPS. Host `web/` (e.g. any static HTTPS host), open the URL in Quest Browser, enable hand tracking in Settings, tap **Enter VR**. Guide: `Docs/BUILD_GUIDE.md`.

## Security limitations
Fixture keys are deterministic TEST-ONLY keys. The AI never overrides verification. Recovery is simulated. No production credentials are used. See `Docs/SECURITY_MODEL.md`.

## Roadmap
Device validation + performance measurement; real evidence ingestion; Kubernetes connector; additional incidents; PWA/APK packaging.

License: MIT.
