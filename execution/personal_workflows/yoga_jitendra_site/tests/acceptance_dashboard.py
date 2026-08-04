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


def check_hero_tile_hydration_upgrades_skeleton() -> list[str]:
    """
    2026-08-04 regression: hero tiles reach + interest were stuck on
    "Data source pending activation: X" forever on the live dashboard, even
    when the client-hydration rollup returned real live numbers.

    Root cause: the SSR-time static fallback JSON has
    hero_tiles.{reach,interest}.value = null, so HeroTile.astro rendered
    those tiles in the SKELETON branch (no .hero-tile-bignumber, no
    [data-metric] hook). The hydration script's updateHeroTiles() only
    ran `document.querySelector('[data-metric=X]').textContent = ...`
    — a no-op when the element doesn't exist. Two of three tiles never
    upgraded to live state.

    Two required fingerprints to prevent recurrence:
      1. HeroTile.astro's <article> MUST carry data-tile-key={metric_key}
         so the hydration script can find the tile even when it's still
         in skeleton state.
      2. dashboard.astro's updateHeroTiles MUST perform a skeleton →
         live DOM upgrade (not just a textContent write) when the live
         rollup delivers a real value for a tile that SSR rendered as
         skeleton.
    """
    errors: list[str] = []
    hero = SRC / "components" / "dashboard" / "HeroTile.astro"
    if hero.exists():
        src = hero.read_text(encoding="utf-8")
        if "data-tile-key" not in src:
            errors.append(
                "HeroTile.astro: <article> must expose data-tile-key={metric_key} so "
                "the dashboard hydration script can address skeleton-state tiles by key."
            )
    dash = SRC / "pages" / "dashboard.astro"
    if dash.exists():
        src = dash.read_text(encoding="utf-8")
        # The upgrade path must query .hero-tile[data-tile-key=...] AND rebuild
        # the number row when the tile is in skeleton state.
        if 'data-tile-key="' not in src and "data-tile-key=`" not in src and 'data-tile-key=$' not in src:
            errors.append(
                "dashboard.astro: hydration must look up hero tiles via "
                "`.hero-tile[data-tile-key=...]`, not just [data-metric=...] "
                "(which does not exist in the skeleton SSR branch)."
            )
        if ".hero-tile-number-row" not in src or "innerHTML" not in src:
            errors.append(
                "dashboard.astro: hydration must rebuild .hero-tile-number-row "
                "innerHTML to upgrade skeleton → live. Without this the reach + "
                "interest tiles stay stuck on 'Data source pending activation' "
                "forever, even after real KV rollup lands."
            )
    return errors


def check_dashboard_banner_defaults_hidden() -> list[str]:
    """
    2026-08-04 regression: on every page load, the SSR emitted a bright amber
    banner reading "All 4 data sources are degraded. Check /health on the cron
    Worker." for ~200ms before hydration hid it. The banner text is honest
    for the static-fallback shape (which lists all 4 sources as degraded
    because it is the bootstrap-empty placeholder), but it is NOT honest for
    live production where 3 of 4 sources are actually healthy. It flashed a
    scary alarm on every visit.

    Fix: the SSR banner must default to `hidden` with empty text; hydration
    reveals it only when the LIVE rollup reports a genuinely degraded state.

    Regression guard: dashboard.astro must NOT render an initially-visible
    banner directly from the static `initialBanner` value.
    """
    errors: list[str] = []
    dash = SRC / "pages" / "dashboard.astro"
    if not dash.exists():
        return errors
    src = dash.read_text(encoding="utf-8")
    # Ban the exact pattern where the SSR banner is visible-by-default with
    # initialBanner content interpolated in. We accept the hidden default
    # (`hidden` attribute + empty <span class="dash-banner-text">`) which
    # relies on hydration to reveal.
    banned = re.compile(
        r'\{initialBanner\s*&&\s*\(\s*<aside[^>]*class="dash-banner"(?![^>]*\bhidden\b)'
    )
    if banned.search(src):
        errors.append(
            "dashboard.astro: <aside class=\"dash-banner\"> must default to hidden. "
            "Rendering it visible from static-fallback data flashes 'All 4 data "
            "sources are degraded' on every load. Let hydration reveal it only "
            "when the LIVE rollup reports a degraded state."
        )
    return errors


def check_hero_zero_with_degraded_shows_source_caveat() -> list[str]:
    """
    2026-08-04 regression #2: when a hero tile receives value === 0 from the
    aggregator AND one of its needed sources is degraded, the tile MUST render
    the number 0 in a muted style with a caveat line naming the still-pending
    source. Prior behavior rendered a bare `0—` visually indistinguishable
    from a genuine zero, so the operator saw "0 Reach" and "0 Interest"
    without any indication that Google Business Profile access is denied.

    Regression fingerprint (evaluated against the built dist/ HTML):
      - The static fallback JSON has sources_degraded = [gsc, gbp, bing, cfwa]
        and conversation.value = 0. Therefore the SSR'd `conversation` tile
        MUST render a caveat containing a source-name string
        (from SOURCE_LABELS: Google Search Console | Google Business Profile |
        Bing Webmaster | Cloudflare Web Analytics).

    Also requires the caveat CSS class + partial-number class to exist in
    HeroTile.astro so the hydration script's runtime insertion has valid
    selectors to target.
    """
    errors: list[str] = []
    # Static-analysis: HeroTile has caveat + partial affordances.
    hero = SRC / "components" / "dashboard" / "HeroTile.astro"
    if hero.exists():
        src = hero.read_text(encoding="utf-8")
        if ".hero-tile-caveat" not in src:
            errors.append(
                "HeroTile.astro: missing `.hero-tile-caveat` CSS class. "
                "Required so a zero-with-degraded-source tile can surface a "
                "truthful caveat instead of a bare `0—`."
            )
        if ".hero-tile-bignumber.partial" not in src:
            errors.append(
                "HeroTile.astro: missing `.hero-tile-bignumber.partial` CSS "
                "rule (muted number for a partial-live zero). Without this "
                "the caveat prints under a fully-saturated terracotta 0, "
                "which reads as a healthy value."
            )
        if "partial_caveat" not in src:
            errors.append(
                "HeroTile.astro: missing `partial_caveat` prop. Required so "
                "dashboard.astro can pass the per-tile pending-source caveat."
            )
    # Static-analysis: dashboard.astro computes + passes tileCaveat + has a
    # client-side counterpart for hydration.
    dash = SRC / "pages" / "dashboard.astro"
    if dash.exists():
        src = dash.read_text(encoding="utf-8")
        if "function tileCaveat" not in src:
            errors.append(
                "dashboard.astro: missing `tileCaveat()` SSR helper that "
                "returns a per-tile caveat string when value===0 AND a "
                "needed source is degraded."
            )
        if "tileCaveatText" not in src:
            errors.append(
                "dashboard.astro: hydration script is missing "
                "`tileCaveatText()` — the client-side twin of `tileCaveat()`. "
                "Without it the caveat only renders at SSR time and vanishes "
                "the moment hydration replaces the number row."
            )
    # Live check: SSR HTML for the conversation tile must contain a source-
    # label string somewhere inside its <article> when the static fallback
    # has value=0 + at least one degraded source.
    if not DIST.exists():
        return errors  # dist not built yet — structural check already flagged
    html_path = None
    for c in [DIST / "dashboard" / "index.html", DIST / "dashboard.html"]:
        if c.exists():
            html_path = c
            break
    if html_path is None:
        return errors  # already flagged by check_dashboard_html
    html = html_path.read_text(encoding="utf-8")
    # Locate the conversation tile <article>. It carries
    # data-tile-key="conversation". Match up to the closing </article>.
    m = re.search(
        r'<article[^>]*data-tile-key="conversation"[^>]*>.*?</article>',
        html,
        re.DOTALL,
    )
    if not m:
        errors.append(
            "dashboard HTML: could not locate <article data-tile-key='conversation'>. "
            "Either HeroTile.astro no longer exposes data-tile-key, or the tile "
            "was removed."
        )
        return errors
    tile_html = m.group(0)
    source_label_names = [
        "Google Search Console",
        "Google Business Profile",
        "Bing Webmaster",
        "Cloudflare Web Analytics",
    ]
    # The static fallback puts cfwa (Cloudflare Web Analytics) in
    # sources_degraded and sets conversation.value = 0 — so the tile MUST
    # render a caveat mentioning one of the SOURCE_LABELS names.
    label_hit = any(name in tile_html for name in source_label_names)
    if not label_hit:
        errors.append(
            "conversation hero tile (value=0, all sources degraded per static "
            "fallback) renders NO source-name caveat. Expected one of "
            f"{source_label_names} inside the tile HTML — this is the exact "
            "'bare 0—' regression from 2026-08-04. Verify tileCaveat() in "
            "dashboard.astro fires and HeroTile.astro's partial-caveat "
            "affordance renders it."
        )
    # Also assert the tile flags itself with data-partial="true" so CSS + tests
    # can target the state cheaply.
    if 'data-partial="true"' not in tile_html:
        errors.append(
            "conversation hero tile: expected data-partial=\"true\" attribute "
            "on the <article> when value=0 AND caveat is present."
        )
    return errors


def check_dashboard_banner_never_empty_visible() -> list[str]:
    """
    2026-08-04 regression #1: `.dash-banner { display: flex }` has equal
    specificity to the UA `[hidden] { display: none }` rule; author sheets
    win over UA sheets in the cascade, so the `hidden` attribute did NOT
    hide the banner. Result: an empty amber warning pill (⚠ icon, no text)
    rendered at the top of the dashboard on every load.

    Two guards:
      (1) dashboard.astro CSS MUST include a `.dash-banner[hidden]` override
          that restores display:none semantics.
      (2) The SSR'd dashboard HTML MUST NOT contain a visible-and-empty
          banner: the <aside id="dash-status-banner"> must EITHER carry the
          `hidden` attribute OR have non-whitespace content inside
          `.dash-banner-text`.
    """
    errors: list[str] = []
    dash = SRC / "pages" / "dashboard.astro"
    if dash.exists():
        src = dash.read_text(encoding="utf-8")
        # Guard 1: CSS override present.
        if not re.search(r"\.dash-banner\[hidden\]\s*\{[^}]*display\s*:\s*none", src):
            errors.append(
                "dashboard.astro: missing `.dash-banner[hidden] { display: none !important; }` "
                "CSS override. Without it, the sibling `.dash-banner { display: flex }` "
                "wins over the UA `[hidden]` rule and renders an empty amber pill on load."
            )
    # Guard 2: built HTML has no visible-empty banner.
    if not DIST.exists():
        return errors
    html_path = None
    for c in [DIST / "dashboard" / "index.html", DIST / "dashboard.html"]:
        if c.exists():
            html_path = c
            break
    if html_path is None:
        return errors
    html = html_path.read_text(encoding="utf-8")
    # Extract the banner <aside>. Two shapes possible: hidden (attribute
    # present, standalone or `hidden=""`) OR text-populated.
    m = re.search(
        r'<aside[^>]*id="dash-status-banner"([^>]*)>(.*?)</aside>',
        html,
        re.DOTALL,
    )
    if not m:
        errors.append(
            "dashboard HTML: <aside id='dash-status-banner'> not found. Banner element "
            "was expected in SSR output; hydration cannot un-hide a missing element."
        )
        return errors
    attrs, inner = m.group(1), m.group(2)
    is_hidden_attr = bool(
        re.search(r'(?:^|\s)hidden(?:=|\s|/?>|$)', attrs)
    )
    # Pull the .dash-banner-text content.
    tm = re.search(
        r'<span[^>]*class="dash-banner-text"[^>]*>(.*?)</span>',
        inner,
        re.DOTALL,
    )
    text_body = (tm.group(1) if tm else "").strip()
    if not is_hidden_attr and not text_body:
        errors.append(
            "dashboard HTML: <aside id='dash-status-banner'> is visible "
            "(no `hidden` attribute) AND has empty `.dash-banner-text`. "
            "That renders as an empty amber warning pill — the exact "
            "2026-08-04 regression. Either default to `hidden` or populate "
            "the text at SSR time."
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
    # Regression guards for the 2026-08-04 shipped-broken incident:
    all_errors.extend(check_hero_tile_hydration_upgrades_skeleton())
    all_errors.extend(check_dashboard_banner_defaults_hidden())
    # Regression guards for the 2026-08-04 follow-on (bare-0-tile + empty-pill):
    all_errors.extend(check_hero_zero_with_degraded_shows_source_caveat())
    all_errors.extend(check_dashboard_banner_never_empty_visible())

    if all_errors:
        print(f"FAIL — {len(all_errors)} issue(s):", file=sys.stderr)
        for e in all_errors:
            fail(e)
        return 1

    print("PASS — dashboard V0.1 acceptance gate.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
