"""NEGATIVE: malformed JSON either parses to {} at Worker (safe empty results)
or is rejected at the Cloudflare edge (403 from WAF). Both are acceptable -- in
both cases the Worker did not crash and no spurious tool call was triggered.
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import WORKER_URL  # type: ignore[import-not-found]


def run() -> dict:
    import urllib.request, urllib.error
    req = urllib.request.Request(
        WORKER_URL + "/retell/tools/list_slots",
        method="POST",
        headers={"Content-Type": "application/json"},
        data=b"{not json at all!!!",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            code = r.status
            if code >= 500:
                return {"ok": False, "summary": f"5xx on malformed JSON: {code}"}
            return {"ok": True, "summary": f"Worker accepted (parsed to empty) {code}"}
    except urllib.error.HTTPError as exc:
        if exc.code in (400, 403):
            return {"ok": True,
                    "summary": f"CF/Worker rejected malformed JSON at edge ({exc.code})"}
        return {"ok": False, "summary": f"unexpected HTTP {exc.code}"}
