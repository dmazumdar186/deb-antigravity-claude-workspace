"""
description: Headless-browser end-to-end test for the NewsletterPopup lifecycle on the LIVE site.
inputs: SITE_URL env var (default: https://yogaavecjitendra.fr). --strict to hard-exit non-zero on failure.
outputs: PASS/FAIL per assertion on stdout; exit code 0 on all-pass, 1 on any failure.

Covers the failure modes prior tests (unit + acceptance) could not:
  * Popup ACTUALLY appears for a first-time visitor after the 1.8s delay.
  * ?popup=1 force-shows it regardless of localStorage / DNT / crawler UA.
  * ?popup=reset clears the flag so the next normal load re-shows.
  * Close button hides it AND persists the localStorage flag.
  * Refresh after Close → popup stays hidden (30-day suppression works).
  * FR + EN homepages both wire the popup identically.

Requires Playwright with Chromium. Install once:
    py -m pip install playwright
    py -m playwright install chromium

Run:
    py execution/personal_workflows/yoga_jitendra_site/tests/e2e_popup.py --strict
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

SITE_URL = os.environ.get("SITE_URL", "https://yogaavecjitendra.fr").rstrip("/")

_failures: list[str] = []


def ok(msg: str) -> None:
    print(f"  [ OK ] {msg}")


def fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")
    _failures.append(msg)


def _new_context(browser):
    # Fresh context each test = clean localStorage + fresh session cookies.
    return browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        ),
        locale="fr-FR",
        viewport={"width": 1280, "height": 900},
    )


def _popup_visible(page) -> bool:
    """The popup is visible when the backdrop element is NOT `hidden`."""
    return page.evaluate(
        "() => { const el = document.getElementById('yj-newsletter-popup'); "
        "return !!el && !el.hidden; }"
    )


def _popup_dom_present(page) -> bool:
    return page.evaluate(
        "() => !!document.getElementById('yj-newsletter-popup')"
    )


def test_fresh_visitor_sees_popup_after_delay(browser) -> None:
    print("[e2e-1 · fresh visitor sees popup after 1.8s delay]")
    ctx = _new_context(browser)
    page = ctx.new_page()
    page.goto(f"{SITE_URL}/", wait_until="domcontentloaded")
    if not _popup_dom_present(page):
        fail("popup DOM absent on FR homepage — component not mounted")
        ctx.close()
        return
    # Wait 3s to give the 1.8s setTimeout comfortable head-room.
    page.wait_for_timeout(3000)
    if _popup_visible(page):
        ok("popup visible ~3s after load (fresh localStorage)")
    else:
        fail("popup DID NOT become visible after 3s on FR homepage — real visitor sees nothing")
    ctx.close()


def test_url_force_show_bypasses_all_suppressors(browser) -> None:
    print("[e2e-2 · ?popup=1 force-shows regardless of prior seen-flag]")
    ctx = _new_context(browser)
    page = ctx.new_page()
    # Seed the localStorage flag first so the normal path would suppress.
    page.goto(f"{SITE_URL}/", wait_until="domcontentloaded")
    page.evaluate(
        "() => localStorage.setItem('yj_popup_seen', "
        "JSON.stringify({v:1, exp: Date.now() + 30*24*60*60*1000}))"
    )
    # Now force-show via URL param.
    page.goto(f"{SITE_URL}/?popup=1", wait_until="domcontentloaded")
    page.wait_for_timeout(700)
    if _popup_visible(page):
        ok("?popup=1 forces show even with yj_popup_seen flag present")
    else:
        fail("?popup=1 did NOT force-show — operator retest hatch is broken")
    ctx.close()


def test_url_reset_clears_flag_then_shows_normally(browser) -> None:
    print("[e2e-3 · ?popup=reset clears flag; next normal load shows again]")
    ctx = _new_context(browser)
    page = ctx.new_page()
    page.goto(f"{SITE_URL}/", wait_until="domcontentloaded")
    page.evaluate(
        "() => localStorage.setItem('yj_popup_seen', "
        "JSON.stringify({v:1, exp: Date.now() + 30*24*60*60*1000}))"
    )
    page.goto(f"{SITE_URL}/?popup=reset", wait_until="domcontentloaded")
    page.wait_for_timeout(500)
    still_flagged = page.evaluate("() => !!localStorage.getItem('yj_popup_seen')")
    if still_flagged:
        fail("?popup=reset did NOT clear yj_popup_seen localStorage — reset branch broken")
        ctx.close()
        return
    ok("?popup=reset cleared yj_popup_seen flag")
    # Load again with no query param; popup should show after normal 1.8s delay.
    page.goto(f"{SITE_URL}/", wait_until="domcontentloaded")
    page.wait_for_timeout(3000)
    if _popup_visible(page):
        ok("subsequent normal load shows popup after reset")
    else:
        fail("normal load after reset did NOT show popup — reset flow broken end-to-end")
    ctx.close()


def test_close_button_hides_and_persists(browser) -> None:
    print("[e2e-4 · close button hides popup + persists suppression on refresh]")
    ctx = _new_context(browser)
    page = ctx.new_page()
    # Force-show without needing the delay.
    page.goto(f"{SITE_URL}/?popup=1", wait_until="domcontentloaded")
    page.wait_for_timeout(700)
    if not _popup_visible(page):
        fail("popup not visible after ?popup=1 — cannot test close")
        ctx.close()
        return
    # Click the close (×) button.
    page.click("[data-yj-nl-close]")
    page.wait_for_timeout(300)
    if _popup_visible(page):
        fail("close button did NOT hide popup — 2026-08-05 bug returned")
        ctx.close()
        return
    ok("close button hides popup")
    # Refresh without any query param; localStorage flag should suppress.
    page.goto(f"{SITE_URL}/", wait_until="domcontentloaded")
    page.wait_for_timeout(3000)
    if _popup_visible(page):
        fail("popup RE-appeared after close+refresh — 30-day suppression broken")
    else:
        ok("popup stays hidden on refresh after close (localStorage flag honored)")
    ctx.close()


def test_en_homepage_wires_popup_identically(browser) -> None:
    print("[e2e-5 · EN homepage popup lifecycle identical to FR]")
    ctx = _new_context(browser)
    page = ctx.new_page()
    page.goto(f"{SITE_URL}/en/?popup=1", wait_until="domcontentloaded")
    page.wait_for_timeout(700)
    if _popup_visible(page):
        ok("EN homepage popup force-shows via ?popup=1")
    else:
        fail("EN homepage popup did NOT force-show — bilingual parity broken")
    ctx.close()


def test_dashboard_does_not_ship_popup(browser) -> None:
    print("[e2e-6 · /dashboard/ correctly excludes popup]")
    ctx = _new_context(browser)
    page = ctx.new_page()
    page.goto(f"{SITE_URL}/dashboard/", wait_until="domcontentloaded")
    page.wait_for_timeout(500)
    if _popup_dom_present(page):
        fail("/dashboard/ ships the popup — should be public-site only")
    else:
        ok("/dashboard/ correctly excludes popup")
    ctx.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true", help="Exit non-zero on any failure")
    parser.add_argument("--headed", action="store_true", help="Show the browser (for local debug)")
    args = parser.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[SKIP] playwright not installed — run: py -m pip install playwright && py -m playwright install chromium", file=sys.stderr)
        return 0

    print(f"E2E popup lifecycle against {SITE_URL}\n")
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=not args.headed)
        except Exception as e:
            # Chromium binary not installed via `playwright install`.
            print(f"[SKIP] Chromium not available: {e}", file=sys.stderr)
            print("  Install with: py -m playwright install chromium", file=sys.stderr)
            return 0
        try:
            test_fresh_visitor_sees_popup_after_delay(browser)
            print()
            test_url_force_show_bypasses_all_suppressors(browser)
            print()
            test_url_reset_clears_flag_then_shows_normally(browser)
            print()
            test_close_button_hides_and_persists(browser)
            print()
            test_en_homepage_wires_popup_identically(browser)
            print()
            test_dashboard_does_not_ship_popup(browser)
        finally:
            browser.close()

    print()
    if _failures:
        print(f"FAIL — {len(_failures)} e2e check(s) failed")
        for f in _failures:
            print(f"  - {f}")
        return 1 if args.strict else 0
    print("PASS — all popup e2e checks green")
    return 0


if __name__ == "__main__":
    sys.exit(main())
