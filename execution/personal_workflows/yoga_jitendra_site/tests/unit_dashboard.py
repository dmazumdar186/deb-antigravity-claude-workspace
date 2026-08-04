"""
description: Dist-based structural + regression unit checks for the yoga-jitendra dashboard.
inputs: none (static build under dist/ + source tree under src/).
outputs: exit 0 on pass, non-zero + failure reasons on stderr.

Fast pre-deploy check. Does NOT prove production works — see
`acceptance_dashboard.py` (LIVE) for the acceptance gate.

Contents were previously in `acceptance_dashboard.py` under a misleading
name (2026-07 shipped-broken exhibit — see live-artifact-acceptance.md).
Renamed to `unit_dashboard.py` on 2026-08-04 so the acceptance gate name
correctly implies "asserts on the live artifact."

Covers:
  * Every required V0.1 source file present.
  * dashboard-data.json schema (rollup shape + tiles + funnel + palette).
  * /wa-out has PHONE_BY_SOURCE allowlist (no querystring open-redirect).
  * apexcharts in package.json dependencies.
  * FunnelStrip range pills are <button>s, not <span>s.
  * Worker wrangler.toml has DST-split cron + DASHBOARD_KV binding.
  * Built dist/dashboard/index.html: noindex, no French leaks, hourglass
    skeletons, Source: labels, palette hygiene, no document.cookie writes.
  * Reviews-admin import path requires submitted_at (silent-now regression guard).
  * Reviews-admin UI form marks review-date as required.
  * dashboard-data.ts fallback ships a labeled donut (not empty labels).
  * dashboard.astro has NO hardcoded 24-48h hint copy.
  * Cron writes pipeline:last_run + pipeline:last_full_failure KV keys.
  * Every functions/*.ts is tracked in git (2026-08-03 Pattern A).
  * HeroTile hydration upgrades skeleton→live (2026-08-04 fix guard).
  * Dashboard banner defaults to hidden (2026-08-04 FOUC fix).
  * Zero-with-degraded-source hero-tile shows source-name caveat.
  * Banner never rendered visible-empty (dash-banner[hidden] override).
  * Built HTML references /_astro/apexcharts*.js (2026-08-04 bare-specifier bug guard).
  * NO inline `<script type=module>` with a bare `import ApexCharts` (same bug shape).

Run:
    py execution/personal_workflows/yoga_jitendra_site/tests/unit_dashboard.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
SRC = ROOT / "src"
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
    initial = data.get("initial_rollup")
    if not initial:
        errors.append("dashboard-data.json missing 'initial_rollup'")
        return errors
    for k in ("range", "as_of", "sources_healthy", "sources_degraded",
              "hero_tiles", "funnel", "time_series", "source_split", "_delta_threshold"):
        if k not in initial:
            errors.append(f"initial_rollup.{k} missing")
    for key in ("reach", "interest", "conversation"):
        tile = initial.get("hero_tiles", {}).get(key)
        if not tile:
            errors.append(f"initial_rollup.hero_tiles.{key} missing")
            continue
        value = tile.get("value")
        if value is not None and not isinstance(value, (int, float)):
            errors.append(f"initial_rollup.hero_tiles.{key}.value must be null or number")
        if not tile.get("source"):
            errors.append(f"initial_rollup.hero_tiles.{key}.source missing")
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
        errors.append("source_split.unit must be 'clicks'")
    milestones = data.get("milestones", [])
    if len(milestones) < 3:
        errors.append("Need at least 3 milestones")
    for m in milestones:
        if m.get("state") not in {"done", "expected", "goal"}:
            errors.append(f"milestone state must be done|expected|goal: {m}")
    return errors


def check_wa_out_no_open_redirect() -> list[str]:
    errors: list[str] = []
    p = FUNCTIONS / "wa-out.ts"
    if not p.exists():
        errors.append("functions/wa-out.ts missing")
        return errors
    src = p.read_text(encoding="utf-8")
    if "PHONE_BY_SOURCE" not in src:
        errors.append("wa-out.ts: expected PHONE_BY_SOURCE allowlist")
    if re.search(r'searchParams\.get\(\s*[\'"]to[\'"]\s*\)', src):
        errors.append("wa-out.ts: accepts `to=` from querystring — open-redirect risk")
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
    if "apexcharts" not in pkg.get("dependencies", {}):
        errors.append("package.json missing apexcharts dependency")
    return errors


def check_funnel_pills_are_buttons() -> list[str]:
    errors: list[str] = []
    p = SRC / "components" / "dashboard" / "FunnelStrip.astro"
    if not p.exists():
        return errors
    src = p.read_text(encoding="utf-8")
    m = re.search(r'class="funnel-range"[\s\S]{0,600}?</div>', src)
    if not m:
        errors.append("FunnelStrip.astro: could not locate .funnel-range block")
        return errors
    block = m.group(0)
    if "<button" not in block:
        errors.append("FunnelStrip.astro: range pills must be <button>")
    if re.search(r'<span[^>]*class:?list=\[[^\]]*funnel-range-pill', block):
        errors.append("FunnelStrip.astro: legacy <span> range pill detected")
    return errors


def check_worker_cron_and_kv() -> list[str]:
    errors: list[str] = []
    worker_root = ROOT.parent.parent / "infrastructure" / "yoga_jitendra_cron"
    toml_path = worker_root / "wrangler.toml"
    if not toml_path.exists():
        return errors
    src = toml_path.read_text(encoding="utf-8")
    if "[triggers]" not in src or "crons" not in src:
        errors.append("yoga_jitendra_cron/wrangler.toml missing [triggers] crons")
    if "DASHBOARD_KV" not in src:
        errors.append("yoga_jitendra_cron/wrangler.toml missing DASHBOARD_KV binding")
    if "4cdf5cdb6fc14db3b29edcab6c464714" not in src:
        errors.append("yoga_jitendra_cron/wrangler.toml: KV namespace id must match Pages")
    idx = worker_root / "src" / "index.js"
    if idx.exists():
        idx_src = idx.read_text(encoding="utf-8")
        if "Europe/Paris" not in idx_src or "Intl.DateTimeFormat" not in idx_src:
            errors.append("yoga_jitendra_cron/src/index.js: missing DST-safe Europe/Paris gating")
    return errors


def check_palette(html: str) -> list[str]:
    errors: list[str] = []
    for hex_val in HEX_RE.findall(html):
        low = hex_val.lower()
        if low in GEMINI_LEAKS:
            errors.append(f"Palette leak (Gemini prototype colour): {hex_val}")
        elif low not in ALLOWED_HEX and not low.startswith("#rgba"):
            errors.append(f"Palette leak (unknown colour): {hex_val}")
    seen: set[str] = set()
    unique: list[str] = []
    for e in errors:
        if e not in seen:
            unique.append(e); seen.add(e)
    return unique


def check_dashboard_html() -> list[str]:
    errors: list[str] = []
    if not DIST.exists():
        errors.append("dist/ not found. Run `npm run build` first.")
        return errors
    html_path = None
    for c in [DIST / "dashboard" / "index.html", DIST / "dashboard.html"]:
        if c.exists():
            html_path = c; break
    if html_path is None:
        errors.append("Dashboard HTML not found in dist/")
        return errors
    html = html_path.read_text(encoding="utf-8")
    if 'name="robots"' not in html or "noindex" not in html:
        errors.append("Dashboard HTML is missing noindex meta")
    lower = html.lower()
    for w in FR_WORDS:
        if w in lower:
            errors.append(f"French-leak word in dashboard HTML: '{w}'")
    hourglass_count = html.count("⏳") + html.count("&#x23F3;") + html.count("&#9203;")
    if hourglass_count < 3:
        errors.append(f"Expected >=3 hourglass skeleton badges, found {hourglass_count}")
    if html.count("Source:") < 6:
        errors.append(f"Need Source: on every hero tile + funnel stage. Found {html.count('Source:')}, need >=6")
    errors.extend(check_palette(html))
    if "document.cookie" in html:
        errors.append("Inline script writes document.cookie (GDPR rule violation)")
    # 2026-08-04 apexcharts bare-specifier bug guard.
    # HTML references the CHART chunks; those chunks transitively import apexcharts.
    # The strong fingerprint is: at least one chart-chunk reference AND no inline
    # bare `import ApexCharts` statement.
    chart_chunks = re.search(
        r'/_astro/(TimeSeriesChart|SourceDonut|Sparkline)[^\'"\s]*\.js',
        html,
    )
    if not chart_chunks:
        errors.append(
            "dashboard HTML does not reference any /_astro/(TimeSeriesChart|SourceDonut|"
            "Sparkline)*.js chunk — chart components are not being bundled. That is the "
            "2026-08-04 bare-specifier bug fingerprint. Charts render blank in prod."
        )
    if re.search(
        r'<script[^>]*type="module"[^>]*>[^<]*import\s+ApexCharts\s+from\s+[\'"]apexcharts[\'"]',
        html, re.DOTALL,
    ):
        errors.append(
            "dashboard HTML contains inline <script type=module> with bare "
            "`import ApexCharts from 'apexcharts'` — silent browser crash. "
            "Use a hoisted <script> (no define:vars)."
        )
    # And the apexcharts bundle must exist somewhere under /_astro/ on disk (it's
    # loaded transitively via the chart chunks — never referenced from HTML
    # directly). If the file is missing from disk, the transitive import will 404
    # at runtime — same effective bug.
    if DIST.exists():
        astro_dir = DIST / "_astro"
        if astro_dir.exists():
            has_apex = any(p.name.startswith("apexcharts") and p.suffix == ".js" for p in astro_dir.iterdir())
            if not has_apex:
                errors.append(
                    "dist/_astro/apexcharts*.js missing — chart chunks will 404 their "
                    "transitive import at runtime."
                )
    return errors


def check_reviews_import_requires_submitted_at() -> list[str]:
    errors: list[str] = []
    p = FUNCTIONS / "api" / "reviews-admin.ts"
    if not p.exists():
        errors.append("functions/api/reviews-admin.ts missing")
        return errors
    src = p.read_text(encoding="utf-8")
    banned = re.compile(
        r"submitted_at['\"]\s*\)\s*\?\?\s*['\"]{2}\s*\)\s*\.trim\(\)\s*\|\|\s*new\s+Date\s*\(\s*\)\s*\.toISOString\s*\(\s*\)"
    )
    if banned.search(src):
        errors.append("reviews-admin.ts: `submitted_at` still silently defaults to now()")
    if "submitted_at_required" not in src:
        errors.append("reviews-admin.ts: expected `submitted_at_required` error branch")
    return errors


def check_reviews_ui_requires_review_date() -> list[str]:
    errors: list[str] = []
    p = SRC / "pages" / "dashboard" / "reviews.astro"
    if not p.exists():
        errors.append("src/pages/dashboard/reviews.astro missing")
        return errors
    src = p.read_text(encoding="utf-8")
    m = re.search(r'<input[^>]*name="submitted_at_date"[^>]*>', src)
    if not m:
        errors.append("reviews.astro: submitted_at_date input missing")
    elif "required" not in m.group(0):
        errors.append("reviews.astro: submitted_at_date input must have `required`")
    return errors


def check_dashboard_fallback_donut_labeled() -> list[str]:
    errors: list[str] = []
    p = FUNCTIONS / "api" / "dashboard-data.ts"
    if not p.exists():
        errors.append("functions/api/dashboard-data.ts missing")
        return errors
    src = p.read_text(encoding="utf-8")
    m = re.search(r"source_split:\s*\{[^}]*\}", src, re.DOTALL)
    if not m:
        errors.append("dashboard-data.ts: source_split block not found in fallback")
        return errors
    if re.search(r"labels:\s*\[\s*\]", m.group(0)):
        errors.append("dashboard-data.ts: source_split.labels is empty in fallback")
    return errors


def check_dashboard_no_hardcoded_wait_hint() -> list[str]:
    errors: list[str] = []
    p = SRC / "pages" / "dashboard.astro"
    if not p.exists():
        errors.append("src/pages/dashboard.astro missing")
        return errors
    src = p.read_text(encoding="utf-8")
    if 'hint="First data ~24-48h after first cron fire"' in src:
        errors.append("dashboard.astro: hardcoded 24-48h hint detected")
    if "function tileHint" not in src:
        errors.append("dashboard.astro: expected a tileHint() helper")
    return errors


def check_cron_dead_man_surface() -> list[str]:
    errors: list[str] = []
    worker_root = ROOT.parent.parent / "infrastructure" / "yoga_jitendra_cron"
    idx = worker_root / "src" / "index.js"
    if not idx.exists():
        return errors
    src = idx.read_text(encoding="utf-8")
    if "pipeline:last_run" not in src:
        errors.append("cron: pipeline must write `pipeline:last_run` KV key")
    if "pipeline:last_full_failure" not in src:
        errors.append("cron: pipeline must write `pipeline:last_full_failure` on 0-healthy")
    return errors


def check_hero_tile_hydration_upgrades_skeleton() -> list[str]:
    errors: list[str] = []
    hero = SRC / "components" / "dashboard" / "HeroTile.astro"
    if hero.exists():
        src = hero.read_text(encoding="utf-8")
        if "data-tile-key" not in src:
            errors.append("HeroTile.astro: <article> must expose data-tile-key")
    dash = SRC / "pages" / "dashboard.astro"
    if dash.exists():
        src = dash.read_text(encoding="utf-8")
        if 'data-tile-key="' not in src and "data-tile-key=`" not in src and 'data-tile-key=$' not in src:
            errors.append("dashboard.astro: hydration must lookup via [data-tile-key]")
        if ".hero-tile-number-row" not in src or "innerHTML" not in src:
            errors.append("dashboard.astro: hydration must rebuild .hero-tile-number-row")
    return errors


def check_dashboard_banner_defaults_hidden() -> list[str]:
    errors: list[str] = []
    dash = SRC / "pages" / "dashboard.astro"
    if not dash.exists():
        return errors
    src = dash.read_text(encoding="utf-8")
    banned = re.compile(
        r'\{initialBanner\s*&&\s*\(\s*<aside[^>]*class="dash-banner"(?![^>]*\bhidden\b)'
    )
    if banned.search(src):
        errors.append("dashboard.astro: <aside class=dash-banner> must default to hidden")
    return errors


def check_hero_zero_with_degraded_shows_source_caveat() -> list[str]:
    errors: list[str] = []
    hero = SRC / "components" / "dashboard" / "HeroTile.astro"
    if hero.exists():
        src = hero.read_text(encoding="utf-8")
        if ".hero-tile-caveat" not in src:
            errors.append("HeroTile.astro: missing `.hero-tile-caveat` CSS class")
        if ".hero-tile-bignumber.partial" not in src:
            errors.append("HeroTile.astro: missing `.hero-tile-bignumber.partial` CSS rule")
        if "partial_caveat" not in src:
            errors.append("HeroTile.astro: missing `partial_caveat` prop")
    dash = SRC / "pages" / "dashboard.astro"
    if dash.exists():
        src = dash.read_text(encoding="utf-8")
        if "function tileCaveat" not in src:
            errors.append("dashboard.astro: missing `tileCaveat()` SSR helper")
        if "tileCaveatText" not in src:
            errors.append("dashboard.astro: hydration script missing `tileCaveatText()`")
    if not DIST.exists():
        return errors
    html_path = None
    for c in [DIST / "dashboard" / "index.html", DIST / "dashboard.html"]:
        if c.exists():
            html_path = c; break
    if html_path is None:
        return errors
    html = html_path.read_text(encoding="utf-8")
    m = re.search(
        r'<article[^>]*data-tile-key="conversation"[^>]*>.*?</article>',
        html, re.DOTALL,
    )
    if not m:
        errors.append("dashboard HTML: no <article data-tile-key='conversation'>")
        return errors
    tile_html = m.group(0)
    source_label_names = [
        "Google Search Console", "Google Business Profile",
        "Bing Webmaster", "Cloudflare Web Analytics",
    ]
    if not any(name in tile_html for name in source_label_names):
        errors.append(
            "conversation hero tile: NO source-name caveat despite value=0 + all degraded. "
            "2026-08-04 'bare 0—' regression."
        )
    if 'data-partial="true"' not in tile_html:
        errors.append("conversation hero tile: expected data-partial=true attribute")
    return errors


def check_dashboard_banner_never_empty_visible() -> list[str]:
    errors: list[str] = []
    dash = SRC / "pages" / "dashboard.astro"
    if dash.exists():
        src = dash.read_text(encoding="utf-8")
        if not re.search(r"\.dash-banner\[hidden\]\s*\{[^}]*display\s*:\s*none", src):
            errors.append("dashboard.astro: missing `.dash-banner[hidden] { display:none !important }` CSS")
    if not DIST.exists():
        return errors
    html_path = None
    for c in [DIST / "dashboard" / "index.html", DIST / "dashboard.html"]:
        if c.exists():
            html_path = c; break
    if html_path is None:
        return errors
    html = html_path.read_text(encoding="utf-8")
    m = re.search(
        r'<aside[^>]*id="dash-status-banner"([^>]*)>(.*?)</aside>',
        html, re.DOTALL,
    )
    if not m:
        errors.append("dashboard HTML: <aside id=dash-status-banner> not found")
        return errors
    attrs, inner = m.group(1), m.group(2)
    is_hidden_attr = bool(re.search(r'(?:^|\s)hidden(?:=|\s|/?>|$)', attrs))
    tm = re.search(
        r'<span[^>]*class="dash-banner-text"[^>]*>(.*?)</span>',
        inner, re.DOTALL,
    )
    text_body = (tm.group(1) if tm else "").strip()
    if not is_hidden_attr and not text_body:
        errors.append("dashboard HTML: dash-banner rendered visible-empty (empty amber pill)")
    return errors


def check_pages_functions_tracked_in_git() -> list[str]:
    import subprocess
    errors: list[str] = []
    if not FUNCTIONS.exists():
        return errors
    on_disk: set[str] = set()
    for path in FUNCTIONS.rglob("*"):
        if path.is_file() and path.suffix in (".ts", ".js"):
            on_disk.add(str(path.relative_to(ROOT)).replace("\\", "/"))
    if not on_disk:
        return errors
    try:
        proc = subprocess.run(
            ["git", "ls-files", "functions/"],
            capture_output=True, text=True, cwd=str(ROOT),
            encoding="utf-8", errors="replace", check=False,
        )
    except FileNotFoundError:
        return errors
    if proc.returncode != 0:
        return errors
    tracked = {line.strip() for line in proc.stdout.splitlines() if line.strip()}
    for rel in sorted(on_disk - tracked):
        errors.append(
            f"Pages Function file untracked in git: {rel}. `wrangler pages deploy` "
            "only ships tracked files."
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
    all_errors.extend(check_reviews_import_requires_submitted_at())
    all_errors.extend(check_reviews_ui_requires_review_date())
    all_errors.extend(check_dashboard_fallback_donut_labeled())
    all_errors.extend(check_dashboard_no_hardcoded_wait_hint())
    all_errors.extend(check_cron_dead_man_surface())
    all_errors.extend(check_pages_functions_tracked_in_git())
    all_errors.extend(check_hero_tile_hydration_upgrades_skeleton())
    all_errors.extend(check_dashboard_banner_defaults_hidden())
    all_errors.extend(check_hero_zero_with_degraded_shows_source_caveat())
    all_errors.extend(check_dashboard_banner_never_empty_visible())

    if all_errors:
        print(f"FAIL — {len(all_errors)} issue(s):", file=sys.stderr)
        for e in all_errors:
            fail(e)
        return 1

    print("PASS — dashboard V0.1 unit + regression checks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
