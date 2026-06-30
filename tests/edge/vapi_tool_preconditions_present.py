"""EDGE: Vapi tool descriptions contain explicit precondition language.

This is the strongest LLM-side guard against the eager-tool-call bug. If the
description loses the PRECONDITIONS keyword, Gemini falls back to eager firing.
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import http_json, VAPI_BASE, env  # type: ignore[import-not-found]


def run() -> dict:
    key = env("VAPI_API_KEY")
    aid = env("VAPI_ASSISTANT_ID")
    code, a = http_json("GET", f"{VAPI_BASE}/assistant/{aid}",
                        headers={"Authorization": f"Bearer {key}"})
    if code != 200 or not a:
        return {"ok": False, "summary": f"get-assistant {code}"}
    tools = (a.get("model") or {}).get("tools") or []
    missing = []
    for t in tools:
        fn = t.get("function") or {}
        desc = fn.get("description") or ""
        if "PRECONDITIONS" not in desc:
            missing.append(fn.get("name"))
    if missing:
        return {"ok": False, "summary": f"tools missing PRECONDITIONS: {missing}"}
    return {"ok": True, "summary": f"all {len(tools)} tools have preconditions"}
