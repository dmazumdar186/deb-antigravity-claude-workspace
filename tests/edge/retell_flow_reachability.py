"""EDGE: every non-end node is reachable from start_node_id; every node can reach an end.

Catches unreachable nodes (will never execute) and missing-terminal nodes
(callers can transition there but never hang up).
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import http_json, RETELL_BASE, env  # type: ignore[import-not-found]


def _bfs(adj: dict, start: str) -> set:
    seen, stack = {start}, [start]
    while stack:
        cur = stack.pop()
        for nxt in adj.get(cur, []):
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return seen


def run() -> dict:
    key = env("RETELL_API_KEY")
    fid = env("RETELL_FLOW_ID")
    code, f = http_json("GET", f"{RETELL_BASE}/get-conversation-flow/{fid}",
                        headers={"Authorization": f"Bearer {key}"})
    if code != 200 or not f:
        return {"ok": False, "summary": f"get-flow {code}"}
    nodes = f.get("nodes") or []
    start = f.get("start_node_id")
    # Forward adjacency
    fwd = {n["id"]: [e.get("destination_node_id") for e in n.get("edges") or []]
           for n in nodes}
    # Reverse adjacency
    rev: dict[str, list[str]] = {}
    for src, dsts in fwd.items():
        for d in dsts:
            rev.setdefault(d, []).append(src)
    end_ids = {n["id"] for n in nodes if n.get("type") == "end"}
    reachable_from_start = _bfs(fwd, start)
    unreachable = {n["id"] for n in nodes} - reachable_from_start
    if unreachable:
        return {"ok": False, "summary": f"unreachable from start: {unreachable}"}
    # From each non-end node, check at least one end is reachable
    no_end = []
    for n in nodes:
        if n.get("type") == "end":
            continue
        reachable = _bfs(fwd, n["id"])
        if not (reachable & end_ids):
            no_end.append(n["id"])
    if no_end:
        return {"ok": False, "summary": f"nodes cannot reach any end: {no_end}"}
    return {"ok": True, "summary": "all nodes reachable + all reach an end"}
