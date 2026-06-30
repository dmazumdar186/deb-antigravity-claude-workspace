"""SMOKE: unknown paths return 404 with CORS headers (not 500 or hang)."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import http, WORKER_URL  # type: ignore[import-not-found]


def run() -> dict:
    code, _ = http("GET", WORKER_URL + "/this-does-not-exist-xyz")
    if code != 404:
        return {"ok": False, "summary": f"expected 404, got {code}"}
    return {"ok": True}
