"""SANITY: Retell flow's conversation nodes are tool-free; function nodes carry tools.

This is the architectural guarantee that prevents the 2026-06-30 eager-tool-call bug.
Verifies it at the deployed-config level, not just at the docs level.
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import http_json, RETELL_BASE, env  # type: ignore[import-not-found]


def run() -> dict:
    key = env("RETELL_API_KEY")
    fid = env("RETELL_FLOW_ID")
    if not all([key, fid]):
        return {"ok": False, "summary": "RETELL_API_KEY / RETELL_FLOW_ID missing"}
    code, f = http_json("GET", f"{RETELL_BASE}/get-conversation-flow/{fid}",
                        headers={"Authorization": f"Bearer {key}"})
    if code != 200 or not f:
        return {"ok": False, "summary": f"get-flow failed: {code}"}
    nodes = f.get("nodes") or []
    conv = [n for n in nodes if n.get("type") == "conversation"]
    fn = [n for n in nodes if n.get("type") == "function"]
    end = [n for n in nodes if n.get("type") == "end"]
    if not conv or not fn:
        return {"ok": False, "summary": f"missing nodes: conv={len(conv)} fn={len(fn)}"}
    for n in conv:
        if n.get("tool_id"):
            return {"ok": False,
                    "summary": f"conversation node {n['id']} has tool_id (eager-call gate broken)"}
    for n in fn:
        if not n.get("tool_id"):
            return {"ok": False,
                    "summary": f"function node {n['id']} has no tool_id"}
    if not end:
        return {"ok": False, "summary": "no end node (close-loop risk)"}
    return {"ok": True,
            "summary": f"{len(conv)} conv tool-free, {len(fn)} fn with tools, {len(end)} end"}
