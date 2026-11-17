# Installation

1. Install Python 3.11+ (python.org). Verify: `python --version` (on this PC use `py --version` or the full path).
2. `cd Trustfall\backend` → `python -m pip install -r requirements.txt`.
3. Run tests: `python -m pytest -q`; `node ..\web\tests\engine.test.js`.
4. Serve: `cd ..\web` → `python -m http.server 8765` → open http://localhost:8765.
5. Optional API: `cd ..\backend` → `python -m uvicorn app.main:app --port 8000` → `/docs`.
6. Optional secrets: copy `.env.example` to `.env` and fill in values you own. Never commit `.env`.

For Quest, see `BUILD_GUIDE.md`.
