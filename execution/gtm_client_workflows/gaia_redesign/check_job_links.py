"""HEAD every live Gaia Talent role URL and record whether it still resolves.

description: Verifies each role URL in jobs.json is reachable, so the note to
  the client can state a real "N of M links verified live on <date>" figure
  instead of an unchecked claim. A refused HEAD is reported as inconclusive
  rather than counted as verified, and a control request distinguishes a blocked
  network from a board that is actually down.
inputs: a list of job records (dicts with "url"), or --jobs <path to jobs.json>
outputs: link_check.json {checked_at, total, ok, inconclusive, failed, blocked,
  control, results[]}
"""

from __future__ import annotations

import argparse
import http.client
import json
import socket
import ssl
import threading
import time
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
RETRIES = 2
CONTROL_URL = "https://gaiatalent.com/"

# A server that refuses the method or the client is not evidence either way.
INCONCLUSIVE_STATUSES = (403, 405)
# Worth trying again: rate limiting and transient server faults.
RETRY_STATUSES = (408, 429, 500, 502, 503, 504)

NETWORK_ERRORS = (
    urllib.error.URLError,
    ssl.SSLError,
    socket.timeout,
    socket.gaierror,
    http.client.HTTPException,
    ValueError,
    OSError,
)


class _HeadRequest(urllib.request.Request):
    def get_method(self) -> str:  # noqa: D102
        return "HEAD"


def _status(url: str, *, head: bool) -> dict[str, Any]:
    """HTTP status (and where the request actually landed) for one request, or
    an error row if it never got that far.

    `urllib.request.urlopen` follows redirects itself, so a redirected URL
    comes back with a 200 status from the *final* page, not the 3xx a raw
    socket would see. `resp.geturl()` is compared against the requested URL
    so a silent redirect is still visible to the caller.
    """
    headers = {"User-Agent": UA, "Accept": "*/*"}
    if head:
        req: urllib.request.Request = _HeadRequest(url, headers=headers)
    else:
        # A one-byte ranged GET: some edges (Cloudflare among them) refuse HEAD
        # from anything that looks automated but serve GET normally, and a
        # refused method is not evidence that the page is gone.
        headers["Range"] = "bytes=0-0"
        req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            status = int(getattr(resp, "status", 0) or resp.getcode() or 0)
            final_url = resp.geturl()
        return {"status": status, "final_url": final_url}
    except urllib.error.HTTPError as exc:
        try:
            return {"status": int(exc.code), "final_url": exc.geturl() or url}
        finally:
            exc.close()
    except NETWORK_ERRORS as exc:
        return {"status": 0, "verdict": "failed", "error": f"{type(exc).__name__}: {str(exc)[:160]}"}


def _attempt(url: str) -> dict[str, Any]:
    """One probe. HEAD first, then a ranged GET if the method was refused."""
    probe = _status(url, head=True)
    if "verdict" in probe:
        return probe
    status, final_url = probe["status"], probe["final_url"]
    if status in INCONCLUSIVE_STATUSES:
        retry = _status(url, head=False)
        if "verdict" in retry:
            return {"status": status, "verdict": "inconclusive", "reason": "refused", "error": "server refused the request"}
        if retry["status"] != 405:
            status, final_url = retry["status"], retry["final_url"]
    if status in INCONCLUSIVE_STATUSES:
        return {"status": status, "verdict": "inconclusive", "reason": "refused", "error": "server refused the request"}
    if status in (200, 206):
        if final_url.rstrip("/") != url.rstrip("/"):
            # urlopen already followed the redirect, so this is the only place
            # a redirect is still visible: the page IS live, but not at the
            # URL we published, so it is not counted as verified-as-published.
            return {
                "status": status,
                "verdict": "inconclusive",
                "reason": "redirected",
                "error": f"redirected to {final_url}",
            }
        return {"status": status, "verdict": "ok", "error": ""}
    return {"status": status, "verdict": "failed", "error": f"HTTP {status}"}


def check_one(url: str, retries: int = RETRIES) -> dict[str, Any]:
    """HEAD a URL, retrying transient failures with a short backoff."""
    row = _attempt(url)
    for attempt in range(retries):
        transient = row["verdict"] == "failed" and (row["status"] in RETRY_STATUSES or row["status"] == 0)
        if not transient:
            break
        time.sleep(0.6 * (attempt + 1))
        row = _attempt(url)
    row["url"] = url
    row["ok"] = row["verdict"] == "ok"
    return row


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
    ok = sum(1 for r in results if r["verdict"] == "ok")
    inconclusive = [r for r in results if r["verdict"] == "inconclusive"]
    failed = [r for r in results if r["verdict"] == "failed"]

    # A control request separates "this machine cannot reach the internet" from
    # "Gaia's board is down"; without it a blocked proxy reads as 63 dead pages.
    control = check_one(CONTROL_URL)
    blocked = bool(urls) and ok == 0 and control["verdict"] == "failed"

    return {
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "checked_on": date.today().isoformat(),
        "total": len(urls),
        "ok": ok,
        "inconclusive": [
            {"url": r["url"], "status": r["status"], "error": r["error"], "reason": r.get("reason", "refused")}
            for r in inconclusive
        ],
        "failed": [{"url": r["url"], "status": r["status"], "error": r["error"]} for r in failed],
        "blocked": blocked,
        "control": {"url": CONTROL_URL, "status": control["status"], "verdict": control["verdict"]},
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
    inconclusive = report.get("inconclusive", []) or []
    refused = sum(1 for r in inconclusive if r.get("reason", "refused") == "refused")
    redirected = sum(1 for r in inconclusive if r.get("reason") == "redirected")
    dead = len(report.get("failed", []) or [])
    sentence = f"{ok} of {total} role links were verified live on {when}"
    if refused:
        sentence += f", {refused} could not be checked (server refused the request)"
    if redirected:
        sentence += f", {redirected} now redirect elsewhere"
    if dead:
        sentence += f", {dead} did not respond"
    return sentence + "."


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
