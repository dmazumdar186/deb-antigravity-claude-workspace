"""SMOKE: Vapi assistant exists and has the expected model+voice+transcriber wired."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import http_json, VAPI_BASE, env  # type: ignore[import-not-found]


def run() -> dict:
    key = env("VAPI_API_KEY")
    aid = env("VAPI_ASSISTANT_ID")
    if not all([key, aid]):
        return {"ok": False, "summary": "VAPI_API_KEY / VAPI_ASSISTANT_ID missing"}
    code, a = http_json("GET", f"{VAPI_BASE}/assistant/{aid}",
                        headers={"Authorization": f"Bearer {key}"})
    if code != 200 or not a:
        return {"ok": False, "summary": f"GET /assistant/{aid} failed: {code}"}
    if (a.get("model") or {}).get("provider") != "google":
        return {"ok": False, "summary": "model.provider != google"}
    if (a.get("voice") or {}).get("provider") != "azure":
        return {"ok": False, "summary": "voice.provider != azure"}
    return {"ok": True}
