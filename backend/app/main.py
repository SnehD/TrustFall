"""Optional FastAPI backend exposing the same logic the static Quest WebXR app uses."""
import json
from pathlib import Path
from fastapi import FastAPI, HTTPException

from .services.scenario import Scenario, RECOVERY_OPTIONS
from .services.fixtures import scenario_records, public_keys
from .ai.investigator import investigate
from .reporting.report import build_report, to_markdown
from .connectors.jenkins import fetch_recent_builds

app = FastAPI(title="Trustfall API")
POLICIES = json.loads((Path(__file__).resolve().parents[2] / "sample-data" / "policies.json").read_text())["grants"]
sc = Scenario(scenario_records(), public_keys(), POLICIES)


def _ver():
    return {k: v.to_dict() for k, v in sc.verification.items()}


@app.get("/state")
def state():
    return {"status": sc.status, "health": sc.health, "verification": _ver(), "authorization": sc.authorization().to_dict()}


@app.post("/recover/{option}")
def recover(option: str):
    if option not in RECOVERY_OPTIONS:
        raise HTTPException(404, "unknown option")
    return sc.recover(option)


@app.get("/investigation")
def inv():
    return investigate(_ver(), set(sc.verification))


@app.get("/report")
def report(fmt: str = "json"):
    r = build_report(sc, investigate(_ver(), set(sc.verification)))
    return {"markdown": to_markdown(r)} if fmt == "md" else r


@app.get("/connector/jenkins/{job}")
def jenkins(job: str):
    status, events = fetch_recent_builds(job)
    return {"status": status, "events": events}
