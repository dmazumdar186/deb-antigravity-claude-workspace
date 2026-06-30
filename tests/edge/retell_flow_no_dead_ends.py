"""EDGE: every non-end conversation/function node has at least one outbound edge.

Catches accidental orphan nodes that would trap callers in dead-end flows.
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import http_json, RETELL_BASE, env  # type: ignore[import-not-found]


def run() -> dict:
    key = env("RETELL_API_KEY")
    fid = env("RETELL_FLOW_ID")
    code, f = http_json("GET", f"{RETELL_BASE}/get-conversation-flow/{fid}",
                        headers={"Authorization": f"Bearer {key}"})
    if code != 200 or not f:
        return {"ok": False, "summary": f"get-flow {code}"}
    dead = []
    for n in f.get("nodes") or []:
        if n.get("type") == "end":
            continue
        edges = n.get("edges") or []
        if not edges:
            dead.append(n.get("id"))
    if dead:
        return {"ok": False, "summary": f"orphan nodes: {dead}"}
    return {"ok": True, "summary": "no dead-end non-end nodes"}
