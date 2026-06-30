"""EDGE: 5 concurrent list_slots requests all succeed (no race, no rate-limit on Cal.com)."""
from pathlib import Path
import sys
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import http_json, WORKER_URL, retell_tool_payload  # type: ignore[import-not-found]


def _one() -> bool:
    code, d = http_json("POST", WORKER_URL + "/retell/tools/list_slots",
                        body=retell_tool_payload({"treatment": "consultation"}))
    return code == 200 and bool(d and d.get("ok") and d.get("slots"))


def run() -> dict:
    with ThreadPoolExecutor(max_workers=5) as ex:
        results = list(ex.map(lambda _: _one(), range(5)))
    n_ok = sum(results)
    if n_ok < 5:
        return {"ok": False, "summary": f"only {n_ok}/5 concurrent requests succeeded"}
    return {"ok": True, "summary": "5/5 concurrent"}
