"""SMOKE: GET /vapi returns the Vapi fallback widget."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import http, WORKER_URL  # type: ignore[import-not-found]


def run() -> dict:
    code, body = http("GET", WORKER_URL + "/vapi")
    if code != 200:
        return {"ok": False, "summary": f"GET /vapi returned {code}"}
    if "Cabinet Dentylis" not in body:
        return {"ok": False, "summary": "missing clinic name"}
    if "vapi" not in body.lower():
        return {"ok": False, "summary": "Vapi SDK not referenced"}
    return {"ok": True}
