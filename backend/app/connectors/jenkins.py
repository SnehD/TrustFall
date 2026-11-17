"""Read-only Jenkins connector (UNVERIFIED against a live server; tested with a mocked transport).
Credentials come from environment variables only. Only HTTP GET is ever issued."""
import os
import httpx


def normalize_build(job: str, b: dict) -> dict:
    return {"source": "jenkins", "job": job, "number": b.get("number"),
            "result": b.get("result") or "IN_PROGRESS", "timestamp_ms": b.get("timestamp"), "url": b.get("url")}


def fetch_recent_builds(job: str, transport=None, env=None):
    """Returns (status, events). Never raises; status['state'] in {connected, not_configured, error}."""
    env = os.environ if env is None else env
    base, user, tok = env.get("JENKINS_URL"), env.get("JENKINS_USER"), env.get("JENKINS_API_TOKEN")
    if not (base and user and tok):
        return {"state": "not_configured", "detail": "JENKINS_* env vars not set; using sample data"}, []
    try:
        with httpx.Client(timeout=5.0, transport=transport, auth=(user, tok)) as c:
            r = c.get(f"{base.rstrip('/')}/job/{job}/api/json", params={"tree": "builds[number,result,timestamp,url]{0,10}"})
            r.raise_for_status()
            builds = r.json().get("builds", [])
            return {"state": "connected", "detail": f"{len(builds)} builds"}, [normalize_build(job, b) for b in builds]
    except (httpx.HTTPError, ValueError) as e:
        return {"state": "error", "detail": type(e).__name__}, []
