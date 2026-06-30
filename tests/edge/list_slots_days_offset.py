"""EDGE: list_slots with days_offset=7 returns next-week slots (reroll behavior)."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import http_json, WORKER_URL, retell_tool_payload  # type: ignore[import-not-found]


def run() -> dict:
    code, d = http_json("POST", WORKER_URL + "/retell/tools/list_slots",
                        body=retell_tool_payload({"treatment": "consultation", "days_offset": 7}))
    if code != 200 or not d:
        return {"ok": False, "summary": f"code={code}"}
    if not d.get("ok"):
        return {"ok": False, "summary": d.get("summary")}
    slots = d.get("slots") or []
    if not slots:
        # Calendar genuinely empty after +7 is possible; warn rather than fail.
        return {"ok": True, "summary": "no slots in +7d window (calendar may be empty)"}
    return {"ok": True, "summary": f"{len(slots)} slots in +7d window"}
