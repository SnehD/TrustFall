# Build / Deploy Guide (beginner-friendly)

There is no compile step. "Building" means putting the `web/` folder on an HTTPS website.

## A. Test on your PC (no headset)
1. Install the **Immersive Web Emulator** extension from the Chrome Web Store (made by Meta) in Chrome or Edge.
2. In PowerShell: `cd C:\Users\sdinkar2\Trustfall\web` then `python -m http.server 8765`.
3. Open `http://localhost:8765`. `localhost` is allowed for WebXR testing.
4. Open the extension's DevTools panel, choose a Quest device, click **Enter VR** in the page. Use the emulator's hand poses/pinch to test. (This has NOT yet been done by me.)

## B. Host over HTTPS (needed for the real Quest)
Pick any static host you control (e.g. GitHub Pages, Netlify, Cloudflare Pages). Upload the contents of `web/` (`index.html`, `src/`, `assets/`, `data/`). Note the `https://…` address.

## C. On the Quest
1. Settings → Movement tracking → turn **Hand tracking** on.
2. Open Meta Quest Browser → your HTTPS address → **Enter VR**.
3. Look at the panels; pinch your thumb and index finger to select, or touch a panel with your index finger.

## D. If the competition requires an APK / Horizon Store build
Confirm requirements on the Devpost rules page first. Meta documents publishing web apps (PWA) to the Horizon Store; follow Meta's *current* official documentation for packaging. This repo has not been packaged and no command for it is provided here, to avoid inventing syntax.
