"""NEGATIVE: book_slot with missing required args returns graceful 'Missing' message."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import http_json, WORKER_URL, retell_tool_payload  # type: ignore[import-not-found]


def run() -> dict:
    code, d = http_json("POST", WORKER_URL + "/retell/tools/book_slot",
                        body=retell_tool_payload({"treatment": "consultation"}))
    if code != 200 or not d:
        return {"ok": False, "summary": f"code={code}"}
    if d.get("ok") is True:
        return {"ok": False, "summary": "accepted booking with missing args"}
    summary = (d.get("summary") or "").lower()
    if "missing" not in summary:
        return {"ok": False, "summary": f"unexpected error message: {summary}"}
    return {"ok": True}
