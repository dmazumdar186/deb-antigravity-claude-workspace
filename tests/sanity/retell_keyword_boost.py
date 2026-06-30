"""SANITY: Retell agent boosted_keywords include time/day words (slot-pick ASR regression)."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import http_json, RETELL_BASE, env  # type: ignore[import-not-found]


# Subset that MUST be present after the 2026-06-30 listen test where "Nine AM"
# was misheard as "Chen in" twice in a row.
REQUIRED_BOOSTS = {"nine", "ten", "AM", "PM", "Wednesday", "Debanjan", "Mazumdar"}


def run() -> dict:
    key = env("RETELL_API_KEY")
    aid = env("RETELL_AGENT_ID")
    if not all([key, aid]):
        return {"ok": False, "summary": "Retell keys missing"}
    code, a = http_json("GET", f"{RETELL_BASE}/get-agent/{aid}",
                        headers={"Authorization": f"Bearer {key}"})
    if code != 200 or not a:
        return {"ok": False, "summary": f"get-agent failed: {code}"}
    boosts = set(a.get("boosted_keywords") or [])
    missing = REQUIRED_BOOSTS - boosts
    if missing:
        return {"ok": False, "summary": f"missing boosts: {sorted(missing)}"}
    return {"ok": True, "summary": f"{len(boosts)} keywords boosted"}
