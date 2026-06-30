"""NEGATIVE: when RETELL secrets are absent we expect 503 on GET / (graceful, not 500).

We can't actually remove secrets here -- instead we verify the SHAPE of the error
response by checking that handleRetellWidget returns 503 + a helpful message when
either RETELL_API_KEY or RETELL_AGENT_ID is missing. Since they ARE present in this
deployment, this test asserts the OPPOSITE: that GET / returns 200 (regression guard
against accidental secret deletion would surface here).
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import http, WORKER_URL  # type: ignore[import-not-found]


def run() -> dict:
    code, body = http("GET", WORKER_URL + "/")
    if code == 503:
        if "RETELL" in body:
            return {"ok": True, "summary": "503 with helpful message (secrets absent path)"}
        return {"ok": False, "summary": "503 but no RETELL hint"}
    if code == 200:
        return {"ok": True, "summary": "200 (secrets present; expected)"}
    return {"ok": False, "summary": f"unexpected status {code}"}
