"""
Render 13 Upwork portfolio cards as 1200x900 PNGs.

Loads projects.json + card.html, injects PROJECTS into the page as a global,
and screenshots the .card element once per project index.

Output: deliverables/upwork_portfolio/<slug>.png
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]  # execution/personal_workflows/personal_brand/upwork_portfolio_generator -> repo root
OUT = REPO / "deliverables" / "upwork_portfolio"
OUT.mkdir(parents=True, exist_ok=True)

PROJECTS = json.loads((HERE / "projects.json").read_text(encoding="utf-8"))
CARD_HTML = (HERE / "card.html").read_text(encoding="utf-8")
ICONS_JS = (HERE / "icons.js").read_text(encoding="utf-8")


def build_page(idx: int) -> str:
    payload = json.dumps(PROJECTS)
    # Inject data BEFORE the existing script so PROJECTS is defined when render() runs.
    injection = (
        f"<script>window.__PROJECTS__ = {payload}; window.__INDEX__ = {idx};</script>"
    )
    # Also override the URL-param read at the end of card.html by re-invoking render().
    override = (
        "<script>"
        "if (typeof render === 'function') { render(window.__INDEX__); }"
        "</script>"
    )
    return CARD_HTML.replace(
        "</head>", injection + "</head>"
    ).replace(
        "</body>", override + "</body>"
    )


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except ImportError:
        print(
            "playwright not installed. Run: py -m pip install playwright && py -m playwright install chromium",
            file=sys.stderr,
        )
        return 2

    written = []
    tmpdir = Path(tempfile.mkdtemp(prefix="upwork_cards_"))
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            context = browser.new_context(
                viewport={"width": 1200, "height": 900},
                device_scale_factor=2,
            )
            page = context.new_page()

            # Copy icons.js next to the tmp html files so <script src="./icons.js"> resolves.
            (tmpdir / "icons.js").write_text(ICONS_JS, encoding="utf-8")

            for idx, project in enumerate(PROJECTS):
                html = build_page(idx)
                tmp = tmpdir / f"card_{idx:02d}.html"
                tmp.write_text(html, encoding="utf-8")
                page.goto(tmp.resolve().as_uri(), wait_until="load")
                page.wait_for_selector(".card", timeout=8000)
                # let fonts + SVG layout settle
                page.wait_for_timeout(150)

                out = OUT / f"{project['slug']}.png"
                card = page.locator(".card")
                card.screenshot(path=str(out), omit_background=False)
                print(f"[{idx + 1:02d}/{len(PROJECTS)}] {out.relative_to(REPO)}")
                written.append(out)
        finally:
            browser.close()

    print(f"\nDone. {len(written)} cards written to {OUT.relative_to(REPO)}/")
    print(f"(tmp html at {tmpdir} — safe to delete)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
