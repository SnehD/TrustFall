# Test Results

Run 2026-11-17. Environment: Windows 11, Python 3.13.0, pytest 9.1.1, Node v12.16.3, Edge (headless, SwiftShader software GL). No Quest, no Unity.

## Automated suites
| Suite | Command | Expected | Actual | Result |
|---|---|---|---|---|
| Backend (verification, policy, scenario, recovery, AI, report, connector) | `cd backend; python -m pytest -v` | 31 pass | 31 passed in 2.60 s | PASS |
| Web engine logic (state, recovery, graph, report) | `node web/tests/engine.test.js` | 16 pass | 16 passed, 0 failed | PASS |

## Required cases → tests
| Requirement | Test | Result |
|---|---|---|
| Valid signed record | `test_valid_signed_record` | PASS |
| Tampered record | `test_tampered_record` | PASS |
| Invalid signature | `test_invalid_signature`, `test_signature_from_wrong_key_invalid` | PASS |
| Missing signature | `test_missing_signature` | PASS |
| Malformed record | `test_malformed_record` | PASS |
| Unknown signing key | `test_unknown_signing_key` | PASS |
| Unauthorized action, valid identity | `test_unauthorized_action_with_valid_identity` | PASS |
| Missing evidence | `test_missing_evidence_in_bundle` | PASS |
| Scenario sequence / state transitions | `test_initial_state`, `test_restore_resolves`, `test_isolate_does_not_fix_outage` | PASS |
| Report accuracy | `test_report_reflects_state` (Py), `report reflects state…` (JS) | PASS |
| AI validation + fallback | `test_ai_*` (6 tests) | PASS |
| Connector errors/timeouts/read-only | `test_connector_*` (5 tests) | PASS |
| Recovery decisions | Py + JS recovery tests | PASS |

## Manual / environment checks
| Check | Result |
|---|---|
| Page loads, no script error; all panels render (Edge headless) | PASS — screenshots `Submission/screenshots/dev-*.png` |
| Live in-browser Ed25519 verification (WebCrypto) | PASS in Edge: screen shows "verified live in this browser"; tamper test → INVALID |
| Recovery updates city, graph, banner, timeline, report | PASS (screenshot dev-05) |
| Secret scan (regex for API keys, private-key blocks, tokens) | PASS — 0 matches |
| Dependency validation | `cryptography`, `pydantic`, `fastapi`, `httpx`, `pytest` import and run. three.js loaded from pinned CDN URL 0.160.0 (HTTP 200). No `npm audit` run (no npm deps). |
| Accessibility (contrast vs panel bg #0a1222) | text 15.6:1, dim 7.3:1, cyan 10.4:1, amber 9.2:1, red 5.3:1, green 11.1:1 — all ≥ 4.5:1. Status is also conveyed by words, not colour alone. Text sizes: body 19–28 px on 1024 px/0.95 m panels; **legibility in headset NOT verified**. |
| Build validation | N/A — static site, no build step. No APK produced. |

## Not tested (unresolved)
- **Any Quest headset run, Immersive Web Emulator run, or XR session.** The XR input code (pinch ray, fingertip poke, hand models) has never executed in an XR session.
- **Performance / frame rate**: not measured. Headless software rendering is not representative. No FPS claim is made.
- Live Jenkins connector, live AI provider call.
- Browsers without WebCrypto Ed25519 (Quest Browser support unverified; precomputed fallback is used and labelled).
- Screen-reader/accessibility inside VR.
