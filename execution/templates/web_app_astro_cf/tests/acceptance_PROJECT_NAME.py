"""Output-acceptance gate for <PROJECT_NAME>.

Runs against the LIVE $SITE_URL (or, in CI, against the preview deploy URL
passed via $SITE_URL). Per ~/.claude/rules/live-artifact-acceptance.md:

  1. Every deployed source file must be tracked in git.
  2. Live path must be served, not a stale fallback.
  3. User-visible content is asserted (not just shape).

Exits 0 on pass, non-zero on any assertion failure. Every failure prints
a single "[FAIL] ..." line so CI can grep.

Env:
    SITE_URL         Required. Prod or preview URL.
    DASHBOARD_USER   For Basic-Auth protected routes (optional).
    DASHBOARD_PASS

Frozen corpus:
    The `CORPUS_*` lists below are the OPERATOR-CURATED reality checks.
    Every item MUST always pass (good) or always fail (bad). When a new
    real-world bug slips through, add the offending input to CORPUS_BAD.
    Do not delete corpus entries without an operator-approved reason.

Run:
    py tests/acceptance_<PROJECT_NAME>.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from base64 import b64encode
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE_URL = os.environ.get("SITE_URL", "").rstrip("/")

# ── Frozen corpus (expand as real bugs surface) ─────────────────────────────
# Content that MUST appear on the homepage (in the language it's served in).
CORPUS_HOMEPAGE_MUST_CONTAIN = [
    "<PROJECT_NAME>",  # brand string; replace if you rename
]

# Content that MUST NEVER appear (stale placeholders, TODO markers, empty-
# state fallback copy that would indicate the live-path is not serving).
CORPUS_HOMEPAGE_MUST_NOT_CONTAIN = [
    "First data ~24-48h",   # yoga_jitendra fingerprint
    "TODO",
    "[INSERT",
    "placeholder",
]


def fail(msg: str) -> int:
    print(f"[FAIL] {msg}", file=sys.stderr)
    return 1


def basic_auth_header() -> dict[str, str]:
    u, p = os.environ.get("DASHBOARD_USER", ""), os.environ.get("DASHBOARD_PASS", "")
    if not (u and p):
        return {}
    tok = b64encode(f"{u}:{p}".encode()).decode()
    return {"Authorization": f"Basic {tok}"}


def http_get(path: str, timeout: float = 10.0) -> tuple[int, str]:
    url = f"{SITE_URL}{path}"
    req = urllib.request.Request(url, headers=basic_auth_header())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except Exception as e:
        return -1, f"{type(e).__name__}: {e}"


def check_git_tracked_functions() -> list[str]:
    """Every .ts/.js under functions/ must be tracked in git.

    This is the yoga_jitendra 2026-08-03 disaster gate: `wrangler pages
    deploy` ships only tracked functions, so untracked ones silently 404
    while local dev works.
    """
    errors: list[str] = []
    fns_dir = ROOT / "functions"
    if not fns_dir.exists():
        return errors
    try:
        tracked = subprocess.run(
            ["git", "ls-files", "functions"],
            cwd=ROOT, encoding="utf-8", errors="replace",
            capture_output=True, check=True,
        ).stdout.splitlines()
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        return [f"git ls-files failed: {e}"]
    tracked_set = {Path(p).as_posix() for p in tracked}
    for p in fns_dir.rglob("*"):
        if p.is_file() and p.suffix in {".ts", ".js", ".mjs"}:
            rel = p.relative_to(ROOT).as_posix()
            if rel not in tracked_set:
                errors.append(f"Untracked Pages Function: {rel} -- wrangler pages deploy will NOT ship it")
    return errors


def check_live_home() -> list[str]:
    errors: list[str] = []
    if not SITE_URL:
        return ["SITE_URL not set -- cannot run live acceptance. Set SITE_URL env var."]
    status, body = http_get("/")
    if status != 200:
        errors.append(f"GET / returned {status}: {body[:200]}")
        return errors
    for s in CORPUS_HOMEPAGE_MUST_CONTAIN:
        if s not in body:
            errors.append(f"Homepage missing required string: {s!r}")
    for s in CORPUS_HOMEPAGE_MUST_NOT_CONTAIN:
        if s in body:
            errors.append(f"Homepage contains forbidden string: {s!r} (stale fallback? untracked deploy?)")
    return errors


def check_live_health() -> list[str]:
    errors: list[str] = []
    if not SITE_URL:
        return []
    status, body = http_get("/api/health")
    if status != 200:
        errors.append(f"/api/health returned {status}: {body[:200]}")
        return errors
    try:
        data = json.loads(body)
    except json.JSONDecodeError as e:
        errors.append(f"/api/health returned non-JSON: {e}")
        return errors
    if not data.get("ok"):
        errors.append(f"/api/health ok=false: {data}")
    for k in ("ts", "build_sha", "upstream_status"):
        if k not in data:
            errors.append(f"/api/health missing key: {k}")
    return errors


def main() -> int:
    all_errors: list[str] = []
    all_errors.extend(check_git_tracked_functions())
    all_errors.extend(check_live_home())
    all_errors.extend(check_live_health())
    if all_errors:
        for e in all_errors:
            fail(e)
        print(f"\n[FAIL] {len(all_errors)} acceptance error(s)", file=sys.stderr)
        return 1
    print(f"[PASS] acceptance gate green (SITE_URL={SITE_URL or 'unset'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
