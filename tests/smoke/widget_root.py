"""SMOKE: GET / returns the Retell widget HTML with the clinic name."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import http, WORKER_URL  # type: ignore[import-not-found]


def run() -> dict:
    code, body = http("GET", WORKER_URL + "/")
    if code != 200:
        return {"ok": False, "summary": f"GET / returned {code}"}
    if "Cabinet Dentylis" not in body:
        return {"ok": False, "summary": "GET / missing clinic name"}
    if "RetellWebClient" not in body:
        return {"ok": False, "summary": "GET / missing Retell SDK reference"}
    if "call_id" not in body:
        return {"ok": False, "summary": "GET / missing call_id (token not minted)"}
    return {"ok": True, "summary": "widget served"}
