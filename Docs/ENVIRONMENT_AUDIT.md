# Environment Audit

Audit date: 2026-11-17 (competition deadline: 2026-11-18 12:00 PM Pacific). Machine: Windows 11 Pro 10.0.26200.

## Available
| Tool | Result |
|---|---|
| Git | 2.53.0 |
| Python | 3.13.0 (`%LOCALAPPDATA%\Programs\Python\Python313`; 3.12 also present). The bare `python` command is only a Microsoft Store stub, so use the full path or `py`. |
| Python packages | cryptography 50.0.0, pydantic 2.12.5, fastapi 0.141.1, httpx 0.28.1, pytest 9.1.1 |
| Node.js | v12.16.3 (too old for the current Immersive Web SDK toolchain; used only to run dependency-free ES5 tests) |
| Browsers | Microsoft Edge and Chrome installed (Edge headless used for screenshots) |
| winget | 1.29 |
| RAM / disk | 14.8 GB RAM; ~60 GB free on C: |
| GPU | AMD Radeon integrated graphics (1 GB reported adapter RAM) |

## Missing
Unity Hub / Editor, Android SDK, Java/JDK, .NET SDK, adb, Meta Quest Developer Hub, Meta XR packages, ffmpeg (no video editing/encoding), a Quest headset.

## Build limitations
- Unity would require ~10+ GB of installs (Hub, Editor + Android module, JDK, SDK/NDK, Meta XR SDK) and, on integrated graphics, a slow editor. Nothing from Unity could be compiled here, so none was written.
- No APK can be produced on this machine as it stands.
- Node 12 cannot run Immersive Web SDK (IWSDK) tooling; upgrade Node to use it.

## Engine decision
Chosen: **WebXR (three.js 0.160.0, pinned) running in Meta Quest Browser**, hands-first, plus a Python backend/verification reference implementation.
Reasons: it runs and can be tested on this machine today; Meta documents WebXR, hand tracking via `hand-tracking`, and the Immersive Web Emulator/IWER for headset-free testing.
**Unconfirmed risk:** the official Devpost rules text could not be retrieved. Public summaries say projects must target Meta VR devices and be fully hands-usable; whether a hosted WebXR/PWA entry is accepted (versus an APK on a "Competition" release channel) MUST be confirmed on the Devpost rules page before relying on it. See `COMPETITION_SUBMISSION.md`.

## Fastest viable path
1. Host `web/` on any HTTPS static host (WebXR on Quest requires HTTPS).
2. Open it in Quest Browser, enable hand tracking, test.
3. If an APK is required, package the hosted PWA per Meta's current PWA-publishing documentation (verify current docs; commands not included here to avoid inventing them).

## Required manual actions
See the ordered list in the final delivery report and `Docs/BUILD_GUIDE.md`.
