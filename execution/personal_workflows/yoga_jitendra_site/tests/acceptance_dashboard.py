"""
description: LIVE-artifact acceptance gate for the yoga-jitendra dashboard V0.1.
inputs: SITE_URL (default https://yogaavecjitendra.fr), DASHBOARD_USER, DASHBOARD_PASS,
        --strict flag (upgrade WARN-skip on missing DASHBOARD_PASS to a hard FAIL)
outputs: exit 0 on full pass, 2 on pass-with-skips (non-strict), 1 on any FAIL.

Runs against the DEPLOYED artifact — per ~/.claude/rules/live-artifact-acceptance.md.
A gate that only exercises `dist/` proves the local build works; it does NOT
prove production serves working data. The 2026-07-21 → 2026-08-03 incident
(13 days of stale-fallback in prod while every static check green) was
caused exactly by trusting build-time asserts.

The dist-only structural + regression checks that used to live here now live
in `unit_dashboard.py`. That file remains useful as a fast pre-deploy check
but is NOT the acceptance gate.

Checks (all HARD-FAIL, exit non-zero on any miss):

 1. /api/dashboard-data?range=7d returns 200 with valid rollup
 2. When >=1 source is healthy, time_series.labels + series NON-EMPTY
    (root cause guard for the 2026-08-04 apexcharts bare-specifier bug)
 3. When >=1 source is healthy, source_split.values has at least one > 0
 4. Live rollup is NOT the bootstrap fallback shape (`_warning` absent OR
    `_pipeline_status != 'not_activated'`) once the cron has fired
 5. /dashboard/ HTML references an /_astro/apexcharts*.js bundle
    (regression guard: bundle absence = bare-specifier bug back)
 6. /dashboard/ HTML has NO inline `<script type=module>` with a bare
    `import ApexCharts` (same bug fingerprint from another angle)
 7. Every hero-tile in SSR has data-status=live OR data-status=waiting
    with a source-name hint (not a bare `0—`)
 8. /wa-out proxy: 302→wa.me on known source; 400 on unknown (live
    open-redirect defense)
 9. GET all three ranges {7d, 30d, all} — same schema, valid JSON
10. /api/reviews-public is public + returns valid rollup with per-record
    date_provenance (regression guard for the 2026-08-04 provenance work)

Env:
  SITE_URL         Base URL under test. Default: https://yogaavecjitendra.fr
  DASHBOARD_USER   Basic-Auth user. Default: debanjan
  DASHBOARD_PASS   Basic-Auth pass. If missing, gate skips auth-gated checks
                   with a WARN (non-strict) or FAIL (strict).

Verdict semantics (2026-08-05 tightening — closes the false-PASS gap
where the gate printed "PASS" while warn-skipping the auth-gated core
check, i.e. exactly the pattern ~/.claude/rules/output-acceptance-gate.md
warns against):
  exit 0  — PASS: no failures AND no warnings
  exit 2  — PASS-WITH-SKIPS: no failures BUT >=1 warning (partial coverage)
  exit 1  — FAIL: >=1 failure (or, with --strict, >=1 warning)

CI should ALWAYS pass --strict. Interactive runs default to non-strict so
the operator can see coverage without hard-failing on a missing local secret.

Run:
    py execution/personal_workflows/yoga_jitendra_site/tests/acceptance_dashboard.py
    py execution/personal_workflows/yoga_jitendra_site/tests/acceptance_dashboard.py --strict
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from base64 import b64encode
from urllib import error, request

try:
    from dotenv import load_dotenv  # type: ignore[import-untyped]
    # Walk up looking for the workspace-root .env (5 levels above tests/).
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed; env vars must be set externally.

SITE_URL = os.environ.get("SITE_URL", "https://yogaavecjitendra.fr").rstrip("/")
USER = os.environ.get("DASHBOARD_USER", "debanjan")
PASS = os.environ.get("DASHBOARD_PASS")

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

FAILURES: list[str] = []
WARNINGS: list[str] = []


def fail(msg: str) -> None:
    FAILURES.append(msg)
    print(f"  [FAIL] {msg}", file=sys.stderr)


def ok(msg: str) -> None:
    print(f"  [ OK ] {msg}")


def warn(msg: str) -> None:
    WARNINGS.append(msg)
    print(f"  [WARN] {msg}")


def http_get(
    url: str,
    headers: dict[str, str] | None = None,
    auth: bool = False,
    timeout: float = 15.0,
    follow_redirects: bool = True,
) -> tuple[int, str, str]:
    """Returns (status, body, location_header)."""
    hdrs = dict(headers or {})
    hdrs.setdefault("User-Agent", DEFAULT_UA)
    hdrs.setdefault(
        "Accept",
        "text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,*/*;q=0.5",
    )
    if auth:
        if not PASS:
            return 0, "SKIP: no DASHBOARD_PASS", ""
        tok = b64encode(f"{USER}:{PASS}".encode("utf-8")).decode("ascii")
        hdrs["Authorization"] = f"Basic {tok}"

    class NoRedirect(request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, hdrs_, newurl):
            return None

    opener = request.build_opener() if follow_redirects else request.build_opener(NoRedirect())
    req_ = request.Request(url, headers=hdrs)
    try:
        with opener.open(req_, timeout=timeout) as resp:
            return (
                resp.status,
                resp.read().decode("utf-8", errors="replace"),
                resp.headers.get("Location") or "",
            )
    except error.HTTPError as e:
        loc = e.headers.get("Location", "") if e.headers else ""
        return e.code, (e.read() or b"").decode("utf-8", errors="replace"), loc
    except Exception as e:
        return 0, f"ERROR: {e!s}", ""


# ---------------------------------------------------------------------------
# Checks 1-4 + 9: /api/dashboard-data live rollup semantics
# ---------------------------------------------------------------------------

def check_dashboard_data(range_key: str) -> dict | None:
    print(f"[/api/dashboard-data?range={range_key}]")
    status, body, _ = http_get(f"{SITE_URL}/api/dashboard-data?range={range_key}", auth=True)
    if status == 0 and "SKIP" in body:
        warn(f"SKIP live dashboard-data (no DASHBOARD_PASS): {body}")
        return None
    if status != 200:
        fail(f"/api/dashboard-data?range={range_key} returned {status}")
        return None
    try:
        d = json.loads(body)
    except Exception as e:
        fail(f"/api/dashboard-data?range={range_key} not valid JSON: {e}")
        return None
    if d.get("range") != range_key:
        fail(f"range mismatch: expected {range_key}, got {d.get('range')}")
    for k in ("hero_tiles", "time_series", "source_split", "sources_healthy", "sources_degraded"):
        if k not in d:
            fail(f"rollup missing required field {k}")
    ok(f"/api/dashboard-data?range={range_key} status 200, valid schema")
    return d


def check_live_charts(d: dict) -> None:
    """Checks 2 + 3 + 4 — the LIVE regression class."""
    if not d:
        return
    healthy = d.get("sources_healthy") or []
    ts = d.get("time_series") or {}
    ss = d.get("source_split") or {}
    values = ss.get("values") or []

    if healthy:
        # Trend chart data must be non-empty when >=1 source is healthy.
        if not ts.get("labels") or not ts.get("series"):
            fail(
                f"time_series is empty ({len(ts.get('labels') or [])} labels, "
                f"{len(ts.get('series') or [])} series) despite {len(healthy)} "
                "healthy sources — blank trend chart on prod (the 2026-08-04 bug)"
            )
        else:
            ok(f"time_series populated: {len(ts.get('labels'))} labels, {len(ts.get('series'))} series")
        # Donut must have at least one positive slice.
        if not values or all(v == 0 for v in values):
            fail(
                f"source_split.values is all-zero despite {len(healthy)} healthy sources "
                "— blank discovery donut on prod"
            )
        else:
            ok(f"source_split has {sum(1 for v in values if v > 0)}/{len(values)} positive slice(s)")
        # Not the bootstrap fallback.
        if d.get("_warning") or d.get("_pipeline_status") == "not_activated":
            fail(
                f"live rollup carries fallback markers (_warning={d.get('_warning')!r} "
                f"_pipeline_status={d.get('_pipeline_status')!r}) despite healthy sources"
            )
        else:
            ok("rollup is not the bootstrap fallback shape")
    else:
        warn(
            f"sources_healthy=[] on live rollup (all {len(d.get('sources_degraded') or [])} "
            "degraded). Live chart checks skipped."
        )


# ---------------------------------------------------------------------------
# Checks 5-7: /dashboard/ SSR HTML
# ---------------------------------------------------------------------------

def check_dashboard_html() -> None:
    print("[/dashboard/ HTML]")
    status, html, _ = http_get(f"{SITE_URL}/dashboard/", auth=True)
    if status == 0 and "SKIP" in html:
        warn(f"SKIP live dashboard HTML (no DASHBOARD_PASS): {html}")
        return
    if status != 200:
        fail(f"/dashboard/ returned {status}")
        return
    ok(f"/dashboard/ status 200 ({len(html)} bytes)")

    # 5 — chart-chunk fingerprint for the 2026-08-04 bare-specifier bug
    # (apexcharts is loaded transitively via the chart chunks; the fingerprint
    # is: no chart chunk referenced from HTML = components not bundled).
    if not re.search(r"/_astro/(TimeSeriesChart|SourceDonut|Sparkline)[^\"'\s]*\.js", html):
        fail(
            "dashboard HTML does not reference /_astro/(TimeSeriesChart|SourceDonut|"
            "Sparkline)*.js — 2026-08-04 bare-specifier bug fingerprint (charts blank)"
        )
    else:
        ok("dashboard HTML references bundled chart chunks")

    # 6 — no inline module with bare import
    if re.search(
        r'<script[^>]*type="module"[^>]*>[^<]*import\s+ApexCharts\s+from\s+[\'"]apexcharts[\'"]',
        html,
        re.DOTALL,
    ):
        fail(
            "dashboard HTML contains inline <script type=module> with bare "
            "`import ApexCharts from 'apexcharts'` — silent browser crash. "
            "Use a hoisted <script> (no define:vars)."
        )
    else:
        ok("dashboard HTML has NO inline bare `import ApexCharts` statement")

    # 7 — hero-tile status semantics
    tiles = re.findall(r'<article[^>]*class="hero-tile"[^>]*>', html)
    if len(tiles) < 3:
        fail(f"expected 3 hero-tile <article>s, found {len(tiles)}")
    else:
        bad = 0
        for i, t in enumerate(tiles):
            if not re.search(r'data-status="(live|waiting)"', t):
                fail(f"hero-tile[{i}] missing data-status attribute")
                bad += 1
        if bad == 0:
            ok(f"{len(tiles)} hero-tiles carry data-status")


# ---------------------------------------------------------------------------
# Check 8: /wa-out live open-redirect defense
# ---------------------------------------------------------------------------

def check_wa_out() -> None:
    print("[/wa-out proxy]")
    status, _, loc = http_get(
        f"{SITE_URL}/wa-out?source=hero&text=test", auth=False, follow_redirects=False
    )
    if status == 302 and loc.startswith("https://wa.me/"):
        ok(f"/wa-out?source=hero -> 302 {loc}")
    else:
        fail(f"/wa-out?source=hero expected 302 -> wa.me/*, got {status} loc={loc!r}")
    status, _, _ = http_get(
        f"{SITE_URL}/wa-out?source=phishattacker", auth=False, follow_redirects=False
    )
    if status == 400:
        ok("/wa-out?source=phishattacker -> 400 (open-redirect defense)")
    else:
        fail(f"/wa-out?source=phishattacker expected 400, got {status} — open-redirect risk")


# ---------------------------------------------------------------------------
# Check 10: /api/reviews-public — no auth needed; verifies deployment freshness
# ---------------------------------------------------------------------------

def check_reviews_public() -> None:
    print("[/api/reviews-public]")
    status, body, _ = http_get(f"{SITE_URL}/api/reviews-public?fresh=1", auth=False)
    if status != 200:
        fail(f"/api/reviews-public returned {status}")
        return
    try:
        d = json.loads(body)
    except Exception as e:
        fail(f"/api/reviews-public not valid JSON: {e}")
        return
    reviews = d.get("reviews") or []
    if not isinstance(reviews, list):
        fail("/api/reviews-public reviews is not a list")
        return
    if reviews:
        without = [r.get("id", "?") for r in reviews if "date_provenance" not in r]
        if without:
            fail(
                f"/api/reviews-public: {len(without)} record(s) missing date_provenance "
                f"— 2026-08-04 provenance regression class. First 3 IDs: {without[:3]}"
            )
        else:
            ok(
                f"/api/reviews-public: {len(reviews)} reviews, avg {d.get('average_rating')}, "
                f"unknown_date_count={d.get('unknown_date_count')}"
            )
    else:
        ok("/api/reviews-public: 0 reviews (KV bootstrap)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Upgrade WARN-skip on missing DASHBOARD_PASS to a hard FAIL (CI mode).",
    )
    args = parser.parse_args()

    print(f"acceptance_dashboard.py — LIVE target {SITE_URL}")
    print(f"  user={USER} pass={'set' if PASS else 'UNSET (warn-mode)'} strict={args.strict}")
    print()

    # Range 7d — do the full deep check on this one.
    d7 = check_dashboard_data("7d")
    check_live_charts(d7)
    print()

    # Ranges 30d + all — shape only.
    for r in ("30d", "all"):
        check_dashboard_data(r)
    print()

    check_dashboard_html()
    print()

    check_wa_out()
    print()

    check_reviews_public()
    print()

    if WARNINGS:
        print("WARNINGS:")
        for w in WARNINGS:
            print(f"  ! {w}")
        print()

    # 2026-08-05 verdict tightening — do NOT print "PASS" when warn-skips
    # covered up the auth-gated core check. That's the exact pattern
    # ~/.claude/rules/output-acceptance-gate.md was born to kill.
    if FAILURES:
        print(f"FAIL — {len(FAILURES)} live-acceptance check(s) failed", file=sys.stderr)
        return 1
    if WARNINGS:
        if args.strict:
            print(
                f"FAIL (strict) — {len(WARNINGS)} check(s) skipped for lack of "
                f"DASHBOARD_PASS. Provision the secret and re-run.",
                file=sys.stderr,
            )
            return 1
        print(
            f"PASS-WITH-SKIPS — 0 failures BUT {len(WARNINGS)} auth-gated check(s) "
            f"skipped. This run does NOT verify /dashboard/ HTML or "
            f"/api/dashboard-data on prod. Run with --strict once DASHBOARD_PASS "
            f"is provisioned to close the gap.",
            file=sys.stderr,
        )
        return 2
    print("PASS — dashboard V0.1 LIVE acceptance gate (all checks executed).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
