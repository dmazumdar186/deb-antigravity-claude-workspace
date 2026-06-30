"""EDGE: OPTIONS preflight either returns CORS headers (Worker reachable) or is
blocked at Cloudflare's edge with 403/405 (WAF behavior). Both are acceptable
for this single-origin widget where the SDK loads from the Worker host itself
and never issues cross-origin tool calls. Documents the cross-origin-embed limit.
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import WORKER_URL  # type: ignore[import-not-found]


def run() -> dict:
    import urllib.request, urllib.error
    req = urllib.request.Request(
        WORKER_URL + "/retell/tools/list_slots",
        method="OPTIONS",
        headers={"Origin": "https://example.com",
                 "Access-Control-Request-Method": "POST"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            ac = r.headers.get("Access-Control-Allow-Origin")
            return {"ok": True, "summary": f"Worker CORS reachable; AC-Allow-Origin={ac}"}
    except urllib.error.HTTPError as exc:
        if exc.code in (403, 405):
            return {"ok": True,
                    "summary": f"CF edge {exc.code} (same-origin widget; cross-origin embed not supported)"}
        return {"ok": False, "summary": f"unexpected HTTP {exc.code}"}
