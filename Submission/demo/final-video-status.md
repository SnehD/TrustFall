# Final video status
**PRODUCED:** `Submission/demo/Trustfall_demo.mp4` — 1920x1080, 24 fps, H.264 + AAC, **2:53 (173 s, under the 180 s limit)**, ~106 MB.

## What it is (be accurate when you describe it)
- Real Trustfall app running in desktop Edge (WebGL), driven by a script (`tools/demo/record.py`): camera moves, cursor and clicks are scripted, rendered frame-by-frame on a manual clock for smooth 24 fps.
- Female voice-over: Microsoft Zira (Windows text-to-speech). Burned-in captions, chapter titles, title and end cards. Ambient bed, click sounds and a recovery chord are synthesized originals.
- It is **NOT Quest headset footage and NOT an XR-emulator capture.** A small on-screen line says "Real app, scripted desktop run". If the official rules require headset or simulator footage, re-record following `recording-checklist.md` (the voice-over/captions assets in `tools/demo/` can be reused).
- Disclosed on screen: data fictional, recovery simulated, AI = deterministic fallback.

## Regenerate
`python -m http.server 8765` in `web/`, then `python tools/demo/record.py --gpu` (~40 min) and `python tools/demo/assemble.py` (needs `pip install imageio-ffmpeg numpy websockets`).

## Not done
Uploaded to YouTube/Vimeo: NO. Public video URL: none. (You must upload it yourself.)
Thumbnail/title card: `../screenshots/demo-title-card.jpg`.
