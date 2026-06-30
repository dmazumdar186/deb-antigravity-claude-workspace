"""SMOKE: /api/health with X-Voice-Agent-Secret returns cal_reachable=true + a sample_slot."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import http_json, WORKER_URL, env  # type: ignore[import-not-found]


def run() -> dict:
    secret = env("WORKER_SECRET")
    if not secret:
        return {"ok": False, "summary": "WORKER_SECRET not set in env"}
    code, d = http_json("GET", WORKER_URL + "/api/health",
                        headers={"X-Voice-Agent-Secret": secret})
    if code != 200 or not d:
        return {"ok": False, "summary": f"non-JSON or non-200: code={code}"}
    if d.get("cal_reachable") is not True:
        return {"ok": False, "summary": f"cal_reachable != true: {d}"}
    if not d.get("sample_slot"):
        return {"ok": False, "summary": "no sample_slot field"}
    return {"ok": True, "summary": d.get("sample_slot")}
