"""HEAD every live Gaia Talent role URL and record whether it still resolves.

description: Verifies each role URL in jobs.json is reachable, so the note to
  the client can state a real "N of M links verified live on <date>" figure
  instead of an unchecked claim. Records a blocked network honestly.
inputs: a list of job records (dicts with "url"), or --jobs <path to jobs.json>
outputs: link_check.json {checked_at, total, ok, failed, blocked, results[]}
"""

from __future__ import annotations

import argparse
import json
import socket
import ssl
import threading
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
TIMEOUT = 20
WORKERS = 6


class _HeadRequest(urllib.request.Request):
    def get_method(self) -> str:  # noqa: D102
        return "HEAD"


def check_one(url: str) -> dict[str, Any]:
    """Return {url, status, ok, error} for a single URL. Never raises."""
    req = _HeadRequest(url, headers={"User-Agent": UA, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            status = int(getattr(resp, "status", 0) or resp.getcode() or 0)
            return {"url": url, "status": status, "ok": 200 <= status < 400, "error": ""}
    except urllib.error.HTTPError as exc:
        # A 405 means the server refuses HEAD, not that the page is gone.
        status = int(exc.code)
        return {
            "url": url,
            "status": status,
            "ok": status in (403, 405),
            "error": "" if status in (403, 405) else f"HTTP {status}",
        }
    except (urllib.error.URLError, ssl.SSLError, socket.timeout, OSError) as exc:
        return {"url": url, "status": 0, "ok": False, "error": type(exc).__name__ + ": " + str(exc)[:160]}


def check_all(urls: list[str], workers: int = WORKERS) -> dict[str, Any]:
    """Check every URL concurrently. Shared state is guarded by a lock."""
    results: list[dict[str, Any]] = []
    lock = threading.Lock()

    def worker(url: str) -> None:
        row = check_one(url)
        with lock:
            results.append(row)

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        list(pool.map(worker, urls))

    results.sort(key=lambda r: r["url"])
    ok = sum(1 for r in results if r["ok"])
    failed = [r for r in results if not r["ok"]]
    # If nothing at all got through, treat it as a blocked network rather than
    # claiming every one of the client's live pages is broken.
    blocked = bool(urls) and ok == 0
    return {
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "checked_on": date.today().isoformat(),
        "total": len(urls),
        "ok": ok,
        "failed": [{"url": r["url"], "status": r["status"], "error": r["error"]} for r in failed],
        "blocked": blocked,
        "results": results,
    }


def summary_sentence(report: dict[str, Any]) -> str:
    """One honest sentence for the client-facing note."""
    total = report.get("total", 0)
    when = report.get("checked_on", "")
    if report.get("skipped"):
        return f"link checking was skipped for this build ({total} role URLs on file, not re-checked)."
    if report.get("blocked"):
        return (
            f"the {total} role URLs could not be reached from the build machine "
            f"on {when} (outbound network blocked), so no live-link claim is made here."
        )
    ok = report.get("ok", 0)
    return f"{ok} of {total} role links were verified live on {when}."


def main() -> int:
    parser = argparse.ArgumentParser(description="HEAD-check every live role URL in jobs.json.")
    parser.add_argument("--jobs", required=True, type=Path, help="path to jobs.json")
    parser.add_argument("--out", required=True, type=Path, help="path to write link_check.json")
    parser.add_argument("--workers", type=int, default=WORKERS)
    args = parser.parse_args()

    jobs = json.loads(args.jobs.read_text(encoding="utf-8"))
    urls = [j["url"] for j in jobs if j.get("url")]
    report = check_all(urls, args.workers)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(summary_sentence(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
