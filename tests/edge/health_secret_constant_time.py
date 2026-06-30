"""EDGE: /api/health authed branch responds with both correct AND wrong secret.

Wrong secret should NOT 401; it should return the unauth view (constant-time compare,
no information leak about secret length).
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import http_json, WORKER_URL  # type: ignore[import-not-found]


def run() -> dict:
    # Wrong secret => unauth view (no cal_reachable field)
    code, d = http_json("GET", WORKER_URL + "/api/health",
                        headers={"X-Voice-Agent-Secret": "wrong-secret-xyz"})
    if code != 200 or not d:
        return {"ok": False, "summary": f"wrong-secret returned {code}"}
    if "cal_reachable" in d:
        return {"ok": False, "summary": "wrong-secret leaked auth-only field"}
    return {"ok": True, "summary": "wrong secret returns unauth view (no leak)"}
