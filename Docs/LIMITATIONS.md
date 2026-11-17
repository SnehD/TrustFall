# Limitations (honest status)

| Feature | Status |
|---|---|
| Evidence verification (Ed25519, 4 outcomes, canonical JSON) | IMPLEMENTED AND TESTED (Python + Edge) |
| Authorization policy separate from identity | IMPLEMENTED AND TESTED |
| Scenario state machine, recovery, report (MD/JSON) | IMPLEMENTED AND TESTED |
| AI validation + deterministic fallback | IMPLEMENTED AND TESTED |
| AI via external provider (Anthropic) | IMPLEMENTED BUT NOT TESTED (no key / no live call) |
| Jenkins connector | IMPLEMENTED, mock-tested; NOT verified against live Jenkins |
| 3D city, graph, panels, desktop interaction | IMPLEMENTED; rendered in Edge, click paths exercised via URL state, not by manual mouse test |
| Hand pinch-ray and fingertip-poke input in XR | IMPLEMENTED BUT NOT TESTED (never run in an XR session or emulator) |
| Quest performance (72/90 FPS) | NOT MEASURED |
| Sound | Minimal generated tones; IMPLEMENTED BUT NOT TESTED in XR |
| Report export in headset | Browser download; behaviour in Quest Browser UNVERIFIED |
| Quest APK / store packaging | NOT IMPLEMENTED |
| Demo video | NOT PRODUCED (no recording/encoding tools, no headset/emulator session) |
| Recovery | SIMULATED only |
| Multiple incidents, multiplayer, Kubernetes | NOT IMPLEMENTED |

Other: AI findings shown in the headset are the deterministic fallback, precomputed by the backend. The in-VR app does not call an AI provider. EV-007 (approval ticket) is intentionally absent from the fixtures to demonstrate MISSING. Scenario data is fictional.
