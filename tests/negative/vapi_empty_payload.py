"""NEGATIVE: Vapi tool endpoint with empty {} body doesn't crash."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import http_json, WORKER_URL  # type: ignore[import-not-found]


def run() -> dict:
    code, d = http_json("POST", WORKER_URL + "/vapi/tools/list_slots", body={})
    if code != 200 or not d:
        return {"ok": False, "summary": f"code={code}"}
    # extractToolCalls returns [] for empty body; Promise.all over [] yields [].
    if d.get("results") != []:
        return {"ok": False, "summary": f"expected empty results array; got {d}"}
    return {"ok": True}
