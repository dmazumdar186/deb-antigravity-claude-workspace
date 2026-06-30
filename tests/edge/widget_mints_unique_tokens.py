"""EDGE: every GET / mints a unique Retell access token (no token reuse between page loads).

Token reuse would let a second visitor join the first visitor's room. Each load must
get its own call_id.
"""
from pathlib import Path
import sys, re
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import http, WORKER_URL  # type: ignore[import-not-found]


def _call_id(body: str) -> str | None:
    m = re.search(r"call_id:\s*<code>([^<]+)</code>", body)
    return m.group(1) if m else None


def run() -> dict:
    ids = []
    for _ in range(3):
        code, body = http("GET", WORKER_URL + "/")
        if code != 200:
            return {"ok": False, "summary": f"GET / returned {code}"}
        cid = _call_id(body)
        if not cid:
            return {"ok": False, "summary": "no call_id in widget HTML"}
        ids.append(cid)
    if len(set(ids)) != 3:
        return {"ok": False, "summary": f"token reuse detected: {ids}"}
    return {"ok": True, "summary": f"3 unique call_ids minted"}
