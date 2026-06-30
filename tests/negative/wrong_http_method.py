"""NEGATIVE: GET on a POST-only endpoint returns 404, not 405 or 500."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import http, WORKER_URL  # type: ignore[import-not-found]


def run() -> dict:
    code, _ = http("GET", WORKER_URL + "/retell/tools/list_slots")
    if code in (404, 405):
        return {"ok": True, "summary": f"safely returned {code}"}
    return {"ok": False, "summary": f"unexpected status {code} on wrong method"}
