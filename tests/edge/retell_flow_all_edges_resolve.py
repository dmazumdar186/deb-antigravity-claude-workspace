"""EDGE: every edge's destination_node_id resolves to an existing node.

Catches typos / refactor regressions where a node is renamed but an edge still
points to the old name. Production exhibit would be a caller's transition that
silently no-ops.
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
    node_ids = {n.get("id") for n in (f.get("nodes") or [])}
    broken = []
    for n in f.get("nodes") or []:
        for e in n.get("edges") or []:
            dst = e.get("destination_node_id")
            if dst not in node_ids:
                broken.append(f"{n.get('id')}.{e.get('id')} -> {dst}")
    if broken:
        return {"ok": False, "summary": f"broken edges: {broken[:5]}"}
    return {"ok": True, "summary": "all edges resolve"}
