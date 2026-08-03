"""
description: Acceptance gate for the yoga-jitendra dashboard (V0.01 + V0.1).
inputs: none (static build under dist/ + source tree under src/).
outputs: exit 0 on pass, non-zero + failure reasons on stderr.

V0.1 additions (vs V0.01):
  - Data schema check now targets `initial_rollup.hero_tiles.*` per the new
    rollup shape (plan §3.3).
  - New required files: ApexCharts components (TimeSeriesChart, SourceDonut,
    Sparkline), the /api/dashboard-data Pages Function reader, the /wa-out
    proxy Function, the Worker cron scaffold (yoga_jitendra_cron/), and the
    local Google OAuth helper script.
  - New checks:
      * /wa-out Function has a phone allowlist (no querystring `to=` accepted).
      * package.json declares apexcharts dependency.
      * Worker wrangler.toml has DST-split cron trigger + DASHBOARD_KV binding.
      * Range pills in FunnelStrip.astro use <button>, not <span>.

Exercises the static build output (dist/) rather than a live URL so it
can run in CI without a network round-trip. Once the site is deployed
and Basic Auth is configured, run the front-door synthetic
(front_door_dashboard.sh) that hits the live URL.

Corpus (frozen — do not weaken):
  - HeroTile skeleton uses U+23F3 hourglass.
  - Every hero tile has a `Source:` line for CDO provenance.
  - Palette allowed:
      #F4EDE1, #FBF7EE, #D9C7A7, #C9744A, #6B7A5A, #2E2A26, #4A423B,
      #A85D37 (hover terracotta, from global.css).

Run:
    py tests/acceptance_dashboard.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
SRC  = ROOT / "src"
FUNCTIONS = ROOT / "functions"

ALLOWED_HEX = {
    "#f4ede1", "#fbf7ee", "#d9c7a7", "#c9744a", "#6b7a5a",
    "#2e2a26", "#4a423b", "#a85d37", "#000000", "#ffffff", "#fff",
}
GEMINI_LEAKS = {
    "#3b82f6", "#f59e0b", "#fb923c", "#dbeafe", "#fef3c7",
    "#dcfce7", "#fecaca", "#e0f2fe",
}
HEX_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b")

FR_WORDS = {"réservations", "occupation", "chiffre", "aperçu", "revenue total"}


def fail(msg: str) -> None:
    print(f"[FAIL] {msg}", file=sys.stderr)


def check_structural_files() -> list[str]:
    errors: list[str] = []
    # V0.01 + V0.1 required files. V0.1 adds: the three new ApexCharts
    # components, the /api/dashboard-data reader, /wa-out proxy, and the
    # Google OAuth local helper script.
    for rel in [
        "src/pages/dashboard.astro",
        "src/pages/dashboard/self-report.astro",
        "src/content/dashboard-data.json",
        "src/components/dashboard/HeroTile.astro",
        "src/components/dashboard/FunnelStrip.astro",
        "src/components/dashboard/MilestoneStrip.astro",
        "src/components/dashboard/NextMoveCard.astro",
        "src/components/dashboard/SelfReportTile.astro",
        "src/components/dashboard/ProvenanceFooter.astro",
        "src/components/dashboard/TimeSeriesChart.astro",
        "src/components/dashboard/SourceDonut.astro",
        "src/components/dashboard/Sparkline.astro",
        "functions/api/self-report.ts",
        "functions/api/dashboard-data.ts",
        "functions/wa-out.ts",
        "scripts/get_google_refresh_token.py",
    ]:
        p = ROOT / rel
        if not p.exists():
            errors.append(f"Missing required file: {rel}")
    # Worker scaffold lives outside this project's tree.
    worker_root = ROOT.parent.parent / "infrastructure" / "yoga_jitendra_cron"
    for rel in [
        "wrangler.toml",
        "package.json",
        "src/index.js",
        "src/oauth.js",
        "src/aggregator.js",
        "src/sources/gsc.js",
        "src/sources/gbp.js",
        "src/sources/bing.js",
        "src/sources/cf_wa.js",
    ]:
        p = worker_root / rel
        if not p.exists():
            errors.append(f"Missing Worker file: infrastructure/yoga_jitendra_cron/{rel}")
    return errors


def check_data_json() -> list[str]:
    errors: list[str] = []
    p = SRC / "content" / "dashboard-data.json"
    if not p.exists():
        errors.append("dashboard-data.json missing")
        return errors
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        errors.append(f"dashboard-data.json is not valid JSON: {e}")
        return errors

    # V0.1 schema: the machine-data lives under initial_rollup (matching the
    # aggregator's rollup shape). Milestones/next_move/provenance still live
    # at top level (hand-curated narrative).
    initial = data.get("initial_rollup")
    if not initial:
        errors.append("dashboard-data.json missing 'initial_rollup' (V0.1 rollup shape)")
        return errors

    # Rollup-level required fields.
    for k in ("range", "as_of", "sources_healthy", "sources_degraded",
              "hero_tiles", "funnel", "time_series", "source_split", "_delta_threshold"):
        if k not in initial:
            errors.append(f"initial_rollup.{k} missing")

    for key in ("reach", "interest", "conversation"):
        tile = initial.get("hero_tiles", {}).get(key)
        if not tile:
            errors.append(f"initial_rollup.hero_tiles.{key} missing")
            continue
        # Value is null OR number. Source is required. Sparkline present (may be []).
        value = tile.get("value")
        source = tile.get("source")
        if value is not None and not isinstance(value, (int, float)):
            errors.append(f"initial_rollup.hero_tiles.{key}.value must be null or number")
        if not source:
            errors.append(f"initial_rollup.hero_tiles.{key}.source missing (CDO provenance)")
        if "sparkline" not in tile:
            errors.append(f"initial_rollup.hero_tiles.{key}.sparkline missing")

    stages = initial.get("funnel", [])
    if len(stages) < 2:
        errors.append("initial_rollup.funnel needs at least 2 stages")
    for s in stages:
        if not s.get("source"):
            errors.append(f"funnel stage {s.get('label')} missing source")

    src_split = initial.get("source_split", {})
    if src_split.get("unit") != "clicks":
        errors.append("source_split.unit must be 'clicks' per plan §3.3")

    milestones = data.get("milestones", [])
    if len(milestones) < 3:
        errors.append("Need at least 3 milestones (real past + future story)")
    for m in milestones:
        if m.get("state") not in {"done", "expected", "goal"}:
            errors.append(f"milestone state must be done|expected|goal: {m}")

    return errors


def check_wa_out_no_open_redirect() -> list[str]:
    """
    /wa-out MUST NOT accept phone from the querystring (open-redirect
    vector). Verify by parsing the TS file — expect a PHONE_BY_SOURCE
    allowlist and no `searchParams.get("to")`.
    """
    errors: list[str] = []
    p = FUNCTIONS / "wa-out.ts"
    if not p.exists():
        errors.append("functions/wa-out.ts missing (Phase H)")
        return errors
    src = p.read_text(encoding="utf-8")
    if "PHONE_BY_SOURCE" not in src:
        errors.append("wa-out.ts: expected PHONE_BY_SOURCE allowlist")
    if re.search(r'searchParams\.get\(\s*[\'"]to[\'"]\s*\)', src):
        errors.append(
            "wa-out.ts: accepts `to=` from querystring — open-redirect risk. Use PHONE_BY_SOURCE instead."
        )
    return errors


def check_apexcharts_dep() -> list[str]:
    errors: list[str] = []
    p = ROOT / "package.json"
    if not p.exists():
        errors.append("package.json missing")
        return errors
    try:
        pkg = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        errors.append(f"package.json is not valid JSON: {e}")
        return errors
    deps = pkg.get("dependencies", {})
    if "apexcharts" not in deps:
        errors.append("package.json missing apexcharts dependency (Phase F)")
    return errors


def check_funnel_pills_are_buttons() -> list[str]:
    """
    Range pills in FunnelStrip.astro MUST be <button>s, not <span>s, so
    they emit real click events for the range-swap hydration. This was
    the operator's headline complaint on 2026-07-21 ("none of these
    data buttons are clickable").
    """
    errors: list[str] = []
    p = SRC / "components" / "dashboard" / "FunnelStrip.astro"
    if not p.exists():
        return errors  # structural check already flagged it
    src = p.read_text(encoding="utf-8")
    # Rough parse: expect `<button` inside the funnel-range block and NOT
    # `<span` in that specific block.
    m = re.search(r'class="funnel-range"[\s\S]{0,600}?</div>', src)
    if not m:
        errors.append("FunnelStrip.astro: could not locate .funnel-range block for pill check")
        return errors
    block = m.group(0)
    if "<button" not in block:
        errors.append("FunnelStrip.astro: range pills must be <button> (Phase G)")
    if re.search(r'<span[^>]*class:?list=\[[^\]]*funnel-range-pill', block):
        errors.append("FunnelStrip.astro: legacy <span> range pill detected — should be <button>")
    return errors


def check_worker_cron_and_kv() -> list[str]:
    errors: list[str] = []
    worker_root = ROOT.parent.parent / "infrastructure" / "yoga_jitendra_cron"
    toml_path = worker_root / "wrangler.toml"
    if not toml_path.exists():
        return errors  # structural check already flagged
    src = toml_path.read_text(encoding="utf-8")
    if "[triggers]" not in src or "crons" not in src:
        errors.append("yoga_jitendra_cron/wrangler.toml missing [triggers] crons")
    if "DASHBOARD_KV" not in src:
        errors.append("yoga_jitendra_cron/wrangler.toml missing DASHBOARD_KV binding")
    if "4cdf5cdb6fc14db3b29edcab6c464714" not in src:
        errors.append(
            "yoga_jitendra_cron/wrangler.toml: KV namespace id must match Pages project "
            "(4cdf5cdb6fc14db3b29edcab6c464714) so both bind the same namespace"
        )
    # DST-safe cron guard: expect the index.js to use Intl.DateTimeFormat with
    # Europe/Paris — not a static-hour heuristic.
    idx = worker_root / "src" / "index.js"
    if idx.exists():
        idx_src = idx.read_text(encoding="utf-8")
        if "Europe/Paris" not in idx_src or "Intl.DateTimeFormat" not in idx_src:
            errors.append(
                "yoga_jitendra_cron/src/index.js: missing DST-safe Europe/Paris gating "
                "(plan §8 Phase A + skeptic round 2)"
            )
    return errors


def check_palette(html: str) -> list[str]:
    errors: list[str] = []
    for hex_val in HEX_RE.findall(html):
        low = hex_val.lower()
        if low in GEMINI_LEAKS:
            errors.append(f"Palette leak (Gemini prototype colour): {hex_val}")
        elif low not in ALLOWED_HEX and not low.startswith("#rgba"):
            # Allow gradient stops that happen to use permitted hex; flag others.
            # Only flag unique unknowns to avoid noise.
            errors.append(f"Palette leak (unknown colour): {hex_val}")
    # Dedup preserving order.
    seen = set()
    unique = []
    for e in errors:
        if e not in seen:
            unique.append(e)
            seen.add(e)
    return unique


def check_dashboard_html() -> list[str]:
    errors: list[str] = []
    if not DIST.exists():
        errors.append(
            "dist/ not found. Run `npm run build` first."
        )
        return errors
    # Astro emits pages under dist/dashboard/index.html for src/pages/dashboard.astro.
    candidates = [
        DIST / "dashboard" / "index.html",
        DIST / "dashboard.html",
    ]
    html_path = next((c for c in candidates if c.exists()), None)
    if html_path is None:
        errors.append(
            f"Dashboard HTML not found. Looked for: {[str(c) for c in candidates]}"
        )
        return errors

    html = html_path.read_text(encoding="utf-8")

    # 1. noindex
    if 'name="robots"' not in html or "noindex" not in html:
        errors.append("Dashboard HTML is missing <meta name='robots' content='noindex...'>")

    # 2. English UI (no French leaks in visible text)
    lower = html.lower()
    for w in FR_WORDS:
        if w in lower:
            errors.append(f"French-leak word visible in dashboard HTML: '{w}'")

    # 3. Every hero tile has either a real number or the skeleton hourglass
    #    (U+23F3, rendered by browsers regardless of literal-vs-entity form).
    #    All three hero tiles start as waiting today, so the badge must
    #    appear at least three times.
    hourglass_count = html.count("⏳") + html.count("&#x23F3;") + html.count("&#9203;")
    if hourglass_count < 3:
        errors.append(
            f"Expected at least 3 hourglass skeleton badges (literal or entity), found {hourglass_count}"
        )

    # 4. Each hero tile AND each funnel stage has a Source: label
    #    (CDO provenance rule; pipeline-auditor 2026-07-19 caught this
    #    as a shared-oracle blind spot when only heroes were checked).
    # Expect: 3 heroes + 3 funnel stages + at least the provenance
    # footer's own label lines = >= 6 Source: occurrences.
    if html.count("Source:") < 6:
        errors.append(
            f"Need Source: on every hero tile and every funnel stage — CDO provenance rule. Found {html.count('Source:')}, need >= 6"
        )

    # 5. Palette
    errors.extend(check_palette(html))

    # 6. No cookies (checked as: no Set-Cookie in the HTML pipeline is
    #    trivially true for static output; the runtime guarantee is
    #    Cloudflare Web Analytics being cookieless. Assertion: no
    #    document.cookie writes appear in inline scripts.)
    if "document.cookie" in html:
        errors.append("Inline script writes document.cookie (GDPR rule violation)")

    return errors


def check_reviews_import_requires_submitted_at() -> list[str]:
    """
    Guardrail against the 2026-07 silent-now regression: the /api/reviews-admin
    `import` action MUST reject empty submitted_at instead of stamping
    `new Date().toISOString()`. That default is the exact bug that made every
    historical Google review appear as a July 2026 review on the customer page.

    Fingerprint we forbid:
      `submitted_at') ?? '').trim() || new Date().toISOString()`
    """
    errors: list[str] = []
    p = FUNCTIONS / "api" / "reviews-admin.ts"
    if not p.exists():
        errors.append("functions/api/reviews-admin.ts missing")
        return errors
    src = p.read_text(encoding="utf-8")
    # Look for the specific silent-default pattern anywhere in the file.
    banned = re.compile(
        r"submitted_at['\"]\s*\)\s*\?\?\s*['\"]{2}\s*\)\s*\.trim\(\)\s*\|\|\s*new\s+Date\s*\(\s*\)\s*\.toISOString\s*\(\s*\)"
    )
    if banned.search(src):
        errors.append(
            "reviews-admin.ts: `submitted_at` still silently defaults to `new Date().toISOString()`. "
            "That is the 2026-07 bug — reject empty submitted_at with 400 instead."
        )
    # Also require that the import path checks for missing/empty submitted_at.
    if "submitted_at_required" not in src:
        errors.append(
            "reviews-admin.ts: expected an explicit `submitted_at_required` error branch "
            "in the import path (missing → 400)."
        )
    return errors


def check_reviews_ui_requires_review_date() -> list[str]:
    """
    Companion to the API-side check: the moderation import form MUST mark the
    review-date input `required` so browsers block submits with an empty date.
    Prevents a well-intentioned moderator from silently mis-dating a review.
    """
    errors: list[str] = []
    p = SRC / "pages" / "dashboard" / "reviews.astro"
    if not p.exists():
        errors.append("src/pages/dashboard/reviews.astro missing")
        return errors
    src = p.read_text(encoding="utf-8")
    # The submitted_at_date input must have `required`.
    m = re.search(r'<input[^>]*name="submitted_at_date"[^>]*>', src)
    if not m:
        errors.append("reviews.astro: submitted_at_date input missing")
    elif "required" not in m.group(0):
        errors.append(
            "reviews.astro: submitted_at_date input must have `required` attribute "
            "(prevents the silent-now bug at the browser layer)."
        )
    return errors


def check_dashboard_fallback_donut_labeled() -> list[str]:
    """
    The /api/dashboard-data empty-rollup fallback MUST ship a labeled
    source_split donut (matching src/content/dashboard-data.json) so hydration
    does not replace a labeled zero-donut with an unlabeled empty one. The
    unlabeled shape is what makes the tile read as a "blank window" to users.
    """
    errors: list[str] = []
    p = FUNCTIONS / "api" / "dashboard-data.ts"
    if not p.exists():
        errors.append("functions/api/dashboard-data.ts missing")
        return errors
    src = p.read_text(encoding="utf-8")
    # Extract the fallback's source_split block and confirm labels is non-empty.
    m = re.search(r"source_split:\s*\{[^}]*\}", src, re.DOTALL)
    if not m:
        errors.append("dashboard-data.ts: source_split block not found in fallback")
        return errors
    block = m.group(0)
    if re.search(r"labels:\s*\[\s*\]", block):
        errors.append(
            "dashboard-data.ts: source_split.labels is empty in the fallback. "
            "Hydration will erase the SSR-time labeled donut and produce a blank tile. "
            "Ship the same 4 labels the static dashboard-data.json ships."
        )
    return errors


def check_dashboard_no_hardcoded_wait_hint() -> list[str]:
    """
    The 24-48h hint copy MUST NOT be hardcoded on hero-tile props. It has to
    be status-derived (via tileHint()) so a pipeline that never activates
    doesn't stay stuck on "First data ~24-48h" forever.
    """
    errors: list[str] = []
    p = SRC / "pages" / "dashboard.astro"
    if not p.exists():
        errors.append("src/pages/dashboard.astro missing")
        return errors
    src = p.read_text(encoding="utf-8")
    if 'hint="First data ~24-48h after first cron fire"' in src:
        errors.append(
            "dashboard.astro: hardcoded 24-48h hint detected. Use tileHint(<key>) "
            "so a stalled pipeline produces a truthful hint instead of a lie."
        )
    if "function tileHint" not in src:
        errors.append(
            "dashboard.astro: expected a tileHint() helper that derives the tile "
            "hint from sources_healthy/sources_degraded/_pipeline_status."
        )
    return errors


def check_cron_dead_man_surface() -> list[str]:
    """
    The cron pipeline MUST write pipeline:last_run + pipeline:last_full_failure
    KV keys so an external monitor (or /health) can detect stalled runs. The
    2026-07 outage went undetected for weeks because every failure was
    swallowed at runSource() with no cross-run trail.
    """
    errors: list[str] = []
    worker_root = ROOT.parent.parent / "infrastructure" / "yoga_jitendra_cron"
    idx = worker_root / "src" / "index.js"
    if not idx.exists():
        return errors  # structural check already flagged
    src = idx.read_text(encoding="utf-8")
    if "pipeline:last_run" not in src:
        errors.append(
            "yoga_jitendra_cron/src/index.js: pipeline must write `pipeline:last_run` "
            "KV key each run so /health can detect stalls."
        )
    if "pipeline:last_full_failure" not in src:
        errors.append(
            "yoga_jitendra_cron/src/index.js: pipeline must write `pipeline:last_full_failure` "
            "when 0 sources are healthy (dead-man for total-outage detection)."
        )
    return errors


def check_pages_functions_tracked_in_git() -> list[str]:
    """
    Every file under functions/ MUST be tracked in git. The 2026-07 dashboard
    disaster's root cause: functions/api/dashboard-data.ts (the file that
    reads KV and serves the dashboard) was written but never `git add`ed, so
    the deploy served a 404 on every request while the acceptance gate
    passed against the checked-in-and-built fallback JSON.

    This check runs `git ls-files` inside functions/ and diffs against the
    filesystem. If any .ts / .js under functions/ is missing from the index,
    the gate fails.
    """
    import subprocess

    errors: list[str] = []
    if not FUNCTIONS.exists():
        return errors
    # Enumerate every .ts / .js on disk under functions/.
    on_disk: set[str] = set()
    for path in FUNCTIONS.rglob("*"):
        if path.is_file() and path.suffix in (".ts", ".js"):
            on_disk.add(str(path.relative_to(ROOT)).replace("\\", "/"))
    if not on_disk:
        return errors
    # Ask git which of those are tracked.
    try:
        proc = subprocess.run(
            ["git", "ls-files", "functions/"],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except FileNotFoundError:
        # No git binary — skip rather than fail (this can happen in CI
        # containers without git). A different check should catch it.
        return errors
    if proc.returncode != 0:
        return errors  # not a git repo or another benign reason
    tracked = {line.strip() for line in proc.stdout.splitlines() if line.strip()}
    untracked_functions = sorted(on_disk - tracked)
    for rel in untracked_functions:
        errors.append(
            f"Pages Function file untracked in git: {rel}. This is the exact "
            "2026-07 failure mode — the file exists locally, the build appears "
            "fine, but `wrangler pages deploy` only ships tracked files."
        )
    return errors


def main() -> int:
    all_errors: list[str] = []
    all_errors.extend(check_structural_files())
    all_errors.extend(check_data_json())
    all_errors.extend(check_wa_out_no_open_redirect())
    all_errors.extend(check_apexcharts_dep())
    all_errors.extend(check_funnel_pills_are_buttons())
    all_errors.extend(check_worker_cron_and_kv())
    all_errors.extend(check_dashboard_html())
    # Regression guards for the 2026-07 shipped-broken incident:
    all_errors.extend(check_reviews_import_requires_submitted_at())
    all_errors.extend(check_reviews_ui_requires_review_date())
    all_errors.extend(check_dashboard_fallback_donut_labeled())
    all_errors.extend(check_dashboard_no_hardcoded_wait_hint())
    all_errors.extend(check_cron_dead_man_surface())
    all_errors.extend(check_pages_functions_tracked_in_git())

    if all_errors:
        print(f"FAIL — {len(all_errors)} issue(s):", file=sys.stderr)
        for e in all_errors:
            fail(e)
        return 1

    print("PASS — dashboard V0.1 acceptance gate.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
