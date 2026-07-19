"""
Acceptance gate for the yoga-jitendra dashboard V0.01.

Exercises the static build output (dist/) rather than a live URL so it
can run in CI without a network round-trip. Once the site is deployed
and CF Access is enabled, run the front-door variant (bash script,
separate) that hits the live URL.

Hard-fails on:
  1. dashboard.html missing (build did not produce the route).
  2. Every visible-number tile without a real number OR a skeleton badge.
  3. Any hardcoded palette colour outside the declared five (catches
     Gemini-blue leaks like #3b82f6, #f59e0b, #fb923c).
  4. Non-English UI copy (French leaks from copy-paste).
  5. Missing noindex meta (dashboard must never be public-indexable).
  6. Missing dashboard, self-report, and Pages Function files (structural).

Corpus (frozen — do not weaken):
  - HeroTile skeleton uses  U+23F3 hourglass.
  - Every hero tile has a `Source:` line for CDO provenance.
  - Palette allowed:
      #F4EDE1, #FBF7EE, #D9C7A7, #C9744A, #6B7A5A, #2E2A26, #4A423B,
      #A85D37 (hover terracotta, from global.css).

Run:
    py tests/acceptance_dashboard.py

Exit 0 = pass, exit non-zero = fail with reasons on stderr.
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
        "functions/api/self-report.ts",
    ]:
        p = ROOT / rel
        if not p.exists():
            errors.append(f"Missing required file: {rel}")
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

    for key in ("reach", "interest", "conversation"):
        tile = data.get("hero_tiles", {}).get(key)
        if not tile:
            errors.append(f"hero_tiles.{key} missing")
            continue
        status = tile.get("status")
        value = tile.get("value")
        hint = tile.get("hint")
        source = tile.get("source")
        if status not in {"live", "waiting"}:
            errors.append(f"hero_tiles.{key}.status must be live|waiting")
        if status == "waiting" and (value is not None or not hint):
            errors.append(
                f"hero_tiles.{key} is waiting but has non-null value or missing hint"
            )
        if status == "live" and value is None:
            errors.append(
                f"hero_tiles.{key} is live but value is null (would show as bare 0)"
            )
        if not source:
            errors.append(f"hero_tiles.{key}.source missing (CDO provenance rule)")

    stages = data.get("funnel", {}).get("stages", [])
    if len(stages) < 2:
        errors.append("funnel.stages needs at least 2 stages")
    for s in stages:
        if not s.get("source"):
            errors.append(f"funnel stage {s.get('label')} missing source")

    milestones = data.get("milestones", [])
    if len(milestones) < 3:
        errors.append("Need at least 3 milestones (real past + future story)")
    for m in milestones:
        if m.get("state") not in {"done", "expected", "goal"}:
            errors.append(f"milestone state must be done|expected|goal: {m}")

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

    # 4. Each hero tile has a Source: label (CDO provenance rule)
    if html.count("Source:") < 3:
        errors.append("Every hero tile must render a 'Source:' line — CDO provenance rule")

    # 5. Palette
    errors.extend(check_palette(html))

    # 6. No cookies (checked as: no Set-Cookie in the HTML pipeline is
    #    trivially true for static output; the runtime guarantee is
    #    Cloudflare Web Analytics being cookieless. Assertion: no
    #    document.cookie writes appear in inline scripts.)
    if "document.cookie" in html:
        errors.append("Inline script writes document.cookie (GDPR rule violation)")

    return errors


def main() -> int:
    all_errors: list[str] = []
    all_errors.extend(check_structural_files())
    all_errors.extend(check_data_json())
    all_errors.extend(check_dashboard_html())

    if all_errors:
        print(f"FAIL — {len(all_errors)} issue(s):", file=sys.stderr)
        for e in all_errors:
            fail(e)
        return 1

    print("PASS — dashboard V0.01 acceptance gate.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
