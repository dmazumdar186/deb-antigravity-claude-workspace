"""SMOKE: /api/health returns ok=true and all 4 secrets_present flags."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import http_json, WORKER_URL  # type: ignore[import-not-found]


def run() -> dict:
    code, d = http_json("GET", WORKER_URL + "/api/health")
    if code != 200 or not d:
        return {"ok": False, "summary": f"non-JSON or non-200: code={code}"}
    if d.get("ok") is not True:
        return {"ok": False, "summary": f"ok != true: {d.get('ok')}"}
    sp = d.get("secrets_present") or {}
    missing = [k for k in ("calcom", "vapi_public", "vapi_assistant_id", "worker") if not sp.get(k)]
    if missing:
        return {"ok": False, "summary": f"secrets missing: {missing}"}
    return {"ok": True, "summary": f"version={d.get('version')}"}
