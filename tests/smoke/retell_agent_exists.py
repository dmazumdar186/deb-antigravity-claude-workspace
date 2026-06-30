"""SMOKE: Retell agent + flow exist and respond on /get-agent and /get-conversation-flow."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import http_json, RETELL_BASE, env  # type: ignore[import-not-found]


def run() -> dict:
    key = env("RETELL_API_KEY")
    aid = env("RETELL_AGENT_ID")
    fid = env("RETELL_FLOW_ID")
    if not all([key, aid, fid]):
        return {"ok": False, "summary": "RETELL_API_KEY / AGENT_ID / FLOW_ID missing"}
    h = {"Authorization": f"Bearer {key}"}
    code1, agent = http_json("GET", f"{RETELL_BASE}/get-agent/{aid}", headers=h)
    if code1 != 200 or not agent:
        return {"ok": False, "summary": f"get-agent failed: {code1}"}
    code2, flow = http_json("GET", f"{RETELL_BASE}/get-conversation-flow/{fid}", headers=h)
    if code2 != 200 or not flow:
        return {"ok": False, "summary": f"get-conversation-flow failed: {code2}"}
    return {"ok": True, "summary": f"agent={agent.get('agent_name')}"}
