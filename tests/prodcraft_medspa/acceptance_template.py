"""
acceptance_template.py
description: Acceptance test for the ProdCraft 0.5-preview Next.js template's
  static export. Serves `template/out/` locally with `http.server` and runs
  Playwright checks (390x844 mobile emulation + 1440x900 desktop): no
  horizontal overflow at top or bottom of scroll (checked at BOTH 390px and
  1440px), a `[data-cta="book"]` element fully inside the first viewport,
  watermark bar visible, `[data-remove-link]` present with an href,
  `noindex` robots meta, zero console errors, zero failed requests, every
  `img` has non-empty alt + intrinsic width/height, total transferred bytes
  < 1.5 MB, no forbidden medical-claim terms in rendered text, and the
  `/expired/` page renders. Also (template v2, scroll-scrubbed motion):
  the hero's numbered copy states change `is-on` class as the page scrolls
  (`_check_hero_states`), sticky folio cards actually get a CSS transform
  applied on a desktop-width viewport (`_check_folio_transforms`), and with
  `prefers-reduced-motion: reduce` emulated, the hero/folio/approach sections
  render all their content visible with no transform applied at all
  (`_check_reduced_motion_fallback`) — i.e. the JS-driven motion never gates
  content visibility.
inputs: template/out/ (the built static export — run `npm run build` first)
outputs: screenshots under .tmp/prodcraft_medspa/acceptance/{viewport}.png;
  prints a one-line JSON summary; exits non-zero on any failure.
"""

from __future__ import annotations

import http.server
import json
import os
import socket
import socketserver
import sys
import threading
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_ROOT = REPO_ROOT / "execution" / "personal_workflows" / "prodcraft_medspa" / "template"
OUT_DIR = TEMPLATE_ROOT / "out"
SCREENSHOT_DIR = REPO_ROOT / ".tmp" / "prodcraft_medspa" / "acceptance"


def _format_expiry(expires_at: str) -> str:
    """Mirrors WatermarkBar.tsx's `formatExpiry`: "Month D, YYYY", or the raw
    string unchanged if it doesn't parse as a date."""
    import datetime

    try:
        d = datetime.date.fromisoformat(expires_at)
    except ValueError:
        return expires_at
    return f"{d.strftime('%B')} {d.day}, {d.year}"


def _expected_watermark_text() -> str:
    """Builds the exact single-sentence watermark the built site must show.

    WatermarkBar.tsx composes this from `business.name` +
    `business.preview.expires_at` (never rendering `preview.watermark`
    verbatim — see that component's docstring for why). Prefers the built
    `business.json` at the template root (what actually drove this build);
    falls back to `business.example.json` when no business.json is present
    (e.g. a bare checkout before ensure-business has run).
    """
    for candidate in (TEMPLATE_ROOT / "business.json", TEMPLATE_ROOT / "business.example.json"):
        if candidate.exists():
            data = json.loads(candidate.read_text(encoding="utf-8"))
            name = data["name"]
            expires = _format_expiry(data["preview"]["expires_at"])
            return f"Concept preview by ProdCraft, not affiliated with or endorsed by {name}. Expires {expires}."
    raise SystemExit(
        f"neither business.json nor business.example.json found under {TEMPLATE_ROOT}"
    )

MAX_TRANSFER_BYTES = 1.5 * 1024 * 1024

FORBIDDEN_TERMS = [
    "cure",
    "guaranteed results",
    "permanent",
    "fda approved",
    "fda-approved",
    "safe for everyone",
    "no side effects",
    "clinically proven",
    "before/after",
    "before & after",
    "before and after",
]

VIEWPORTS = [
    {
        "name": "mobile-390x844",
        "kwargs": {
            "viewport": {"width": 390, "height": 844},
            "is_mobile": True,
            "has_touch": True,
            "device_scale_factor": 2,
        },
    },
    {
        "name": "desktop-1440x900",
        "kwargs": {
            "viewport": {"width": 1440, "height": 900},
            "is_mobile": False,
            "has_touch": False,
            "device_scale_factor": 1,
        },
    },
]


def _chromium_executable() -> str | None:
    """Locates the bundled Chromium binary directly.

    The pinned playwright pip package sometimes expects a headless-shell
    build newer than what's pre-provisioned in the sandbox image; fall back
    to the full chromium-* build's `chrome` binary (both satisfy Playwright's
    CDP protocol) rather than running `playwright install`, which is disallowed
    in this environment.
    """
    browsers_root = Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers"))
    if not browsers_root.is_dir():
        return None
    candidates = sorted(browsers_root.glob("chromium-*/chrome-linux/chrome"), reverse=True)
    return str(candidates[0]) if candidates else None


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):  # noqa: A002 - matches base signature
        pass


def _serve(out_dir: Path, port: int) -> socketserver.TCPServer:
    handler = lambda *a, **kw: _QuietHandler(*a, directory=str(out_dir), **kw)  # noqa: E731
    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd


def _check_price_pattern(text_lower: str) -> bool:
    import re

    return bool(re.search(r"\$\s?\d", text_lower))


def _check_hero_states(browser, base_url: str) -> list[str]:
    """The hero's numbered copy states must swap `is-on` as scroll advances."""
    failures: list[str] = []
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()
    page.goto(f"{base_url}/", wait_until="networkidle")

    initial = page.evaluate(
        "() => { const el = document.querySelector('.hero__state.is-on'); "
        "return el ? el.getAttribute('data-hero-state') : null; }"
    )
    if initial is None:
        failures.append("no [data-hero-state] element starts with class is-on")

    # Scroll to the middle of the hero's own (tall) scroll range.
    page.evaluate(
        "() => { const hero = document.querySelector('[data-hero]'); "
        "if (hero) window.scrollTo(0, hero.offsetTop + hero.offsetHeight * 0.6); }"
    )
    page.wait_for_timeout(200)
    later = page.evaluate(
        "() => { const el = document.querySelector('.hero__state.is-on'); "
        "return el ? el.getAttribute('data-hero-state') : null; }"
    )
    if later is None:
        failures.append("no [data-hero-state] element has class is-on after scrolling into the hero")
    elif later == initial:
        failures.append(f"hero state did not change after scrolling (stayed at state {initial!r})")

    context.close()
    return failures


def _check_folio_transforms(browser, base_url: str) -> list[str]:
    """Sticky folio cards must receive an actual CSS transform on desktop."""
    failures: list[str] = []
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()
    page.goto(f"{base_url}/", wait_until="networkidle")

    card_count = page.evaluate("document.querySelectorAll('[data-folio-card]').length")
    if not card_count:
        failures.append("no [data-folio-card] elements found")
        context.close()
        return failures

    before = page.evaluate(
        "() => window.getComputedStyle(document.querySelectorAll('[data-folio-card]')[0]).transform"
    )
    page.evaluate(
        "() => { const folio = document.querySelector('[data-folio]'); "
        "if (folio) window.scrollTo(0, folio.offsetTop + folio.offsetHeight * 0.5); }"
    )
    page.wait_for_timeout(250)
    after = page.evaluate(
        "() => window.getComputedStyle(document.querySelectorAll('[data-folio-card]')[0]).transform"
    )
    if before == after:
        failures.append(f"folio card transform did not change on scroll (stayed {after!r})")
    if after in ("none", ""):
        failures.append("folio card has no transform applied mid-scroll on desktop")

    context.close()
    return failures


def _check_reduced_motion_fallback(browser, base_url: str) -> list[str]:
    """With reduced motion, every hero/folio/approach element must be visible with no transform."""
    failures: list[str] = []
    context = browser.new_context(viewport={"width": 1440, "height": 900}, reduced_motion="reduce")
    page = context.new_page()
    page.goto(f"{base_url}/", wait_until="networkidle")

    report = page.evaluate(
        """
        () => {
          const bad = [];
          const groups = {
            hero: document.querySelectorAll('.hero__state'),
            folio: document.querySelectorAll('[data-folio-card]'),
            approach: document.querySelectorAll('[data-approach-step]'),
          };
          for (const [name, nodes] of Object.entries(groups)) {
            nodes.forEach((el, i) => {
              const style = window.getComputedStyle(el);
              const rect = el.getBoundingClientRect();
              const visible = style.display !== 'none' && style.visibility !== 'hidden'
                && parseFloat(style.opacity) >= 0.99;
              const noTransform = style.transform === 'none' || style.transform === '';
              if (!visible || !noTransform || rect.width === 0) {
                bad.push(`${name}[${i}]: visible=${visible} noTransform=${noTransform} transform=${style.transform}`);
              }
            });
          }
          return bad;
        }
        """
    )
    if report:
        failures.append(f"reduced-motion elements not fully visible / still transformed: {report}")

    context.close()
    return failures


def _check_mobile_folio_opacity(browser, base_url: str) -> list[str]:
    """Below the 800px desktop-motion breakpoint, every folio card must sit at
    full opacity in the stacked layout — never a leftover --folio-opacity
    written by MotionController while the page was last above 800px wide."""
    failures: list[str] = []
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()
    page.goto(f"{base_url}/", wait_until="networkidle")

    # Scroll partway into the folio section at desktop width first, so
    # MotionController actually writes non-1 --folio-opacity values, then
    # shrink below the 800px breakpoint and confirm they don't linger.
    page.evaluate(
        "() => { const folio = document.querySelector('[data-folio]'); "
        "if (folio) window.scrollTo(0, folio.offsetTop + folio.offsetHeight * 0.5); }"
    )
    page.wait_for_timeout(200)
    page.set_viewport_size({"width": 390, "height": 844})
    page.wait_for_timeout(250)

    opacities = page.evaluate(
        "() => Array.from(document.querySelectorAll('[data-folio-card]'))"
        ".map((el) => parseFloat(window.getComputedStyle(el).opacity))"
    )
    if not opacities:
        failures.append("no [data-folio-card] elements found at 390px")
    for i, op in enumerate(opacities):
        if op < 1:
            failures.append(f"folio card [{i}] has opacity {op} (<1) in the 390px stacked layout")

    context.close()
    return failures


def run() -> dict:
    if not OUT_DIR.exists():
        raise SystemExit(
            f"template/out/ not found at {OUT_DIR}. Run `npm run build` in "
            f"{TEMPLATE_ROOT} first."
        )

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover
        raise SystemExit(f"playwright is not installed: {exc}") from exc

    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

    expected_watermark = _expected_watermark_text()

    port = _free_port()
    httpd = _serve(OUT_DIR, port)
    base_url = f"http://127.0.0.1:{port}"

    failures: list[str] = []
    results: dict[str, dict] = {}

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=_chromium_executable())
            for viewport_cfg in VIEWPORTS:
                name = viewport_cfg["name"]
                context = browser.new_context(**viewport_cfg["kwargs"])
                page = context.new_page()

                console_errors: list[str] = []
                failed_requests: list[str] = []
                transferred_bytes = 0

                page.on(
                    "console",
                    lambda msg: console_errors.append(msg.text) if msg.type == "error" else None,
                )
                page.on(
                    "requestfailed",
                    lambda req: failed_requests.append(f"{req.method} {req.url} -> {req.failure}"),
                )

                def _on_response(resp, _bytes_holder=None):
                    nonlocal transferred_bytes
                    try:
                        body = resp.body()
                        transferred_bytes += len(body)
                    except Exception:
                        pass

                page.on("response", _on_response)

                page.goto(f"{base_url}/", wait_until="networkidle")

                viewport_failures: list[str] = []

                # --- no horizontal overflow, at top ---
                overflow_top = page.evaluate(
                    "document.scrollingElement.scrollWidth <= window.innerWidth + 1"
                )
                if not overflow_top:
                    viewport_failures.append("horizontal overflow at top of page")

                # --- scroll to bottom, re-check ---
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(150)
                overflow_bottom = page.evaluate(
                    "document.scrollingElement.scrollWidth <= window.innerWidth + 1"
                )
                if not overflow_bottom:
                    viewport_failures.append("horizontal overflow after scrolling to bottom")
                page.evaluate("window.scrollTo(0, 0)")
                page.wait_for_timeout(100)

                # --- data-cta="book" fully inside the initial viewport ---
                cta_in_viewport = page.evaluate(
                    """
                    () => {
                      const els = Array.from(document.querySelectorAll('[data-cta="book"]'));
                      if (els.length === 0) return false;
                      const vw = window.innerWidth;
                      const vh = window.innerHeight;
                      return els.some((el) => {
                        const r = el.getBoundingClientRect();
                        return r.top >= 0 && r.left >= 0 && r.bottom <= vh && r.right <= vw
                          && r.width > 0 && r.height > 0;
                      });
                    }
                    """
                )
                if not cta_in_viewport:
                    viewport_failures.append('no [data-cta="book"] fully inside the initial viewport')

                # --- watermark visible ---
                watermark_visible = page.evaluate(
                    """
                    () => {
                      const el = document.querySelector('[data-watermark]');
                      if (!el) return false;
                      const r = el.getBoundingClientRect();
                      const style = window.getComputedStyle(el);
                      return r.width > 0 && r.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
                    }
                    """
                )
                if not watermark_visible:
                    viewport_failures.append("watermark bar not visible")

                # --- watermark bar contains the full preview.watermark sentence ---
                watermark_text = page.evaluate(
                    """
                    () => {
                      const el = document.querySelector('[data-watermark]');
                      return el ? el.innerText : null;
                    }
                    """
                )
                if watermark_text is None or expected_watermark not in watermark_text:
                    viewport_failures.append(
                        f"watermark bar innerText missing full preview.watermark sentence "
                        f"(expected {expected_watermark!r}, got {watermark_text!r})"
                    )

                # --- data-remove-link present with href ---
                remove_link_href = page.evaluate(
                    """
                    () => {
                      const el = document.querySelector('[data-remove-link]');
                      return el ? el.getAttribute('href') : null;
                    }
                    """
                )
                if not remove_link_href:
                    viewport_failures.append("[data-remove-link] missing or has no href")

                # --- meta robots noindex ---
                robots_content = page.evaluate(
                    """
                    () => {
                      const el = document.querySelector('meta[name="robots"]');
                      return el ? el.getAttribute('content') : null;
                    }
                    """
                )
                if not robots_content or "noindex" not in robots_content.lower():
                    viewport_failures.append(f"meta[name=robots] missing or lacks noindex: {robots_content!r}")

                # --- images: alt + width + height ---
                bad_images = page.evaluate(
                    """
                    () => Array.from(document.querySelectorAll('img')).map((img) => ({
                      src: img.getAttribute('src'),
                      alt: img.getAttribute('alt'),
                      width: img.getAttribute('width'),
                      height: img.getAttribute('height'),
                    })).filter((i) => !i.alt || !i.width || !i.height)
                    """
                )
                if bad_images:
                    viewport_failures.append(f"images missing alt/width/height: {bad_images}")

                # --- sticky mobile bar must not cover the footer remove-preview link ---
                if viewport_cfg["kwargs"].get("is_mobile"):
                    page.evaluate(
                        "document.querySelector('footer [data-remove-link]')"
                        ".scrollIntoView({block: 'center'})"
                    )
                    page.wait_for_timeout(150)
                    overlap_check = page.evaluate(
                        """
                        () => {
                          const link = document.querySelector('footer [data-remove-link]');
                          const bar = document.querySelector('.fixed.inset-x-0.bottom-0');
                          if (!link) return { ok: false, reason: 'footer remove link not found' };
                          if (!bar) return { ok: true, reason: 'no sticky bottom bar present' };
                          const barStyle = window.getComputedStyle(bar);
                          if (barStyle.display === 'none' || barStyle.visibility === 'hidden') {
                            return { ok: true, reason: 'sticky bottom bar not displayed' };
                          }
                          const l = link.getBoundingClientRect();
                          const b = bar.getBoundingClientRect();
                          const intersects = l.left < b.right && l.right > b.left
                            && l.top < b.bottom && l.bottom > b.top;
                          if (!intersects) return { ok: true, reason: 'no bbox intersection' };
                          const cx = l.left + l.width / 2;
                          const cy = l.top + l.height / 2;
                          const top = document.elementFromPoint(cx, cy);
                          const clickable = top === link || (top && link.contains(top));
                          return {
                            ok: clickable,
                            reason: clickable
                              ? 'bbox overlaps but link is the top hit-tested element'
                              : 'sticky bar covers the footer remove link',
                          };
                        }
                        """
                    )
                    if not overlap_check.get("ok"):
                        viewport_failures.append(
                            f"sticky mobile bar covers footer remove link: {overlap_check.get('reason')}"
                        )
                    page.evaluate("window.scrollTo(0, 0)")
                    page.wait_for_timeout(100)

                # --- forbidden terms / price pattern in body text ---
                body_text = page.evaluate("document.body.innerText")
                lower = body_text.lower()
                hit_terms = [t for t in FORBIDDEN_TERMS if t in lower]
                if hit_terms:
                    viewport_failures.append(f"forbidden terms present: {hit_terms}")
                if _check_price_pattern(lower):
                    viewport_failures.append("price pattern ($<digit>) present in body text")

                # --- console errors / failed requests ---
                if console_errors:
                    viewport_failures.append(f"console errors: {console_errors}")
                if failed_requests:
                    viewport_failures.append(f"failed requests: {failed_requests}")

                # --- transferred bytes budget ---
                if transferred_bytes >= MAX_TRANSFER_BYTES:
                    viewport_failures.append(
                        f"transferred {transferred_bytes} bytes >= {MAX_TRANSFER_BYTES} budget"
                    )

                screenshot_path = SCREENSHOT_DIR / f"{name}.png"
                page.screenshot(path=str(screenshot_path), full_page=True)

                results[name] = {
                    "failures": viewport_failures,
                    "transferred_bytes": transferred_bytes,
                    "screenshot": str(screenshot_path),
                }
                failures.extend(f"[{name}] {f}" for f in viewport_failures)

                context.close()

            # --- /expired/ page renders (once, desktop context is fine) ---
            context = browser.new_context(viewport={"width": 1440, "height": 900})
            page = context.new_page()
            expired_ok = True
            try:
                resp = page.goto(f"{base_url}/expired/", wait_until="networkidle")
                if resp is None or resp.status >= 400:
                    expired_ok = False
                    failures.append(f"/expired/ did not render (status={resp.status if resp else None})")
                body_len = page.evaluate("document.body.innerText.length")
                if body_len < 10:
                    expired_ok = False
                    failures.append("/expired/ rendered with near-empty body")
            except Exception as exc:  # noqa: BLE001
                expired_ok = False
                failures.append(f"/expired/ raised: {exc}")
            results["expired_page_ok"] = expired_ok
            context.close()

            # --- template v2 motion checks (desktop-only effects + reduced-motion fallback) ---
            motion_failures: list[str] = []
            motion_failures.extend(_check_hero_states(browser, base_url))
            motion_failures.extend(_check_folio_transforms(browser, base_url))
            motion_failures.extend(_check_reduced_motion_fallback(browser, base_url))
            motion_failures.extend(_check_mobile_folio_opacity(browser, base_url))
            results["motion_checks"] = motion_failures
            failures.extend(f"[motion] {f}" for f in motion_failures)

            browser.close()
    finally:
        httpd.shutdown()

    # One "check group" per viewport, plus /expired/ and the motion checks —
    # each group counts as passed only if it recorded zero failures.
    group_passed = [not v["failures"] for k, v in results.items() if k not in ("expired_page_ok", "motion_checks")]
    group_passed.append(bool(results.get("expired_page_ok")))
    group_passed.append(not results.get("motion_checks"))
    total_checks = len(group_passed)
    summary = {
        "script": "acceptance_template",
        "in": total_checks,
        "out": sum(1 for ok in group_passed if ok),
        "dropped": {"failures": failures},
        "results": {
            k: (v if k in ("expired_page_ok", "motion_checks") else v["failures"]) for k, v in results.items()
        },
    }
    print(json.dumps(summary))

    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        raise SystemExit(1)

    return summary


def test_acceptance_template():
    """pytest entrypoint — skips if the static export hasn't been built."""
    import pytest

    if not OUT_DIR.exists():
        pytest.skip(f"template/out/ not found at {OUT_DIR} — run `npm run build` first")
    run()


if __name__ == "__main__":
    run()
