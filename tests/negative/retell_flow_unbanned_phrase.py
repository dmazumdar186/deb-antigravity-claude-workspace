"""NEGATIVE: 'Are you still there?' MUST NOT appear in any node instruction.

The hard ban must hold at every layer. Even if the global_prompt forbids the
phrase, a per-node instruction that uses it would override.
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import http_json, RETELL_BASE, env  # type: ignore[import-not-found]


BANNED = ["are you still there", "you there", "can you hear me", "hello?"]


def run() -> dict:
    key = env("RETELL_API_KEY")
    fid = env("RETELL_FLOW_ID")
    code, f = http_json("GET", f"{RETELL_BASE}/get-conversation-flow/{fid}",
                        headers={"Authorization": f"Bearer {key}"})
    if code != 200 or not f:
        return {"ok": False, "summary": f"get-flow {code}"}
    hits = []
    for n in f.get("nodes") or []:
        instr = (n.get("instruction") or {}).get("text", "")
        # Skip the global prompt where we explicitly list the ban
        lo = instr.lower()
        for phrase in BANNED:
            # Skip occurrences in the global prompt context where they're being banned
            if phrase in lo and "never" not in lo[:lo.find(phrase) + 200] and "do not" not in lo[:lo.find(phrase) + 200]:
                hits.append((n.get("id"), phrase))
    if hits:
        return {"ok": False, "summary": f"banned phrase in node instruction: {hits[:3]}"}
    return {"ok": True, "summary": "no banned phrases in node instructions"}
