# Test Plan

Automated: `backend/tests/test_trustfall.py` (31), `web/tests/engine.test.js` (16). Run per `README.md`. Results in `TEST_RESULTS.md`.

Manual checklist for Quest / emulator (all currently UNEXECUTED):
- [ ] Page loads over HTTPS; Enter VR appears and starts a session.
- [ ] Hand tracking: `S.inputMode` banner text changes to "Hand tracking".
- [ ] Pinch on: Begin, building, graph node, each tab, each recovery button.
- [ ] Poke (fingertip) on the same targets; no accidental double-activation.
- [ ] Text legible from seated position at panel distance (~1.2 m).
- [ ] Tamper test shows INVALID; Re-run verification shows source (live vs precomputed).
- [ ] Recovery → banner green, buildings green, report RESOLVED.
- [ ] Export Markdown/JSON works in Quest Browser.
- [ ] Frame rate measured (e.g. OVR Metrics Tool) over 2 minutes; record numbers.
- [ ] Reload restarts cleanly.
