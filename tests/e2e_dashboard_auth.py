"""
description: Headless-browser end-to-end test for the dashboard auth flow — proves the session-cookie fix eliminates the double-prompt on /dashboard/subscribers/.
inputs: SITE_URL (default: https://yogaavecjitendra.fr), DASHBOARD_USER (default: debanjan), DASHBOARD_PASS (required — skipped if unset). --strict to hard-exit on failure.
outputs: PASS/FAIL per assertion on stdout; exit 0 on all-pass, 1 on any failure.

The failure this test guards against:
  Basic Auth prompt on /dashboard/ (accept once).
  Click Subscribers count → /dashboard/subscribers/.
  Client script fires fetch('/api/subscribers').
  Browser does NOT auto-attach cached Basic Auth to XHR → 401 → prompt appears again.

The fix under test:
  On successful Basic Auth, middleware returns a 302/307 to the same URL
  with Set-Cookie: yj_dash_sess=<sha256(user:pass:v1)>. Browser follows,
  cookie is set from a Function-generated response (not a static-asset
  response — CF Pages strips Set-Cookie from those). All subsequent
  requests (page loads, XHRs) authorize via cookie fast-path in the
  middleware. Zero re-prompts.

Setup:
    py -m pip install playwright
    py -m playwright install chromium

Run locally:
    set DASHBOARD_PASS=<your-password>
    py execution/personal_workflows/yoga_jitendra_site/tests/e2e_dashboard_auth.py --strict
"""
from __future__ import annotations

import argparse
import os
import sys

SITE_URL = os.environ.get("SITE_URL", "https://yogaavecjitendra.fr").rstrip("/")
DASHBOARD_USER = os.environ.get("DASHBOARD_USER", "debanjan")
DASHBOARD_PASS = os.environ.get("DASHBOARD_PASS", "")

_failures: list[str] = []


def ok(msg: str) -> None:
    print(f"  [ OK ] {msg}")


def fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")
    _failures.append(msg)


def _new_context(browser):
    return browser.new_context(
        http_credentials={"username": DASHBOARD_USER, "password": DASHBOARD_PASS},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1280, "height": 900},
    )


def _get_session_cookie(context) -> str | None:
    for c in context.cookies():
        if c.get("name") == "yj_dash_sess":
            return c.get("value")
    return None


def test_dashboard_load_sets_session_cookie(browser) -> None:
    print("[e2e-auth-1 · /dashboard/ load sets yj_dash_sess cookie]")
    ctx = _new_context(browser)
    page = ctx.new_page()
    resp = page.goto(f"{SITE_URL}/dashboard/", wait_until="domcontentloaded")
    if not resp or resp.status not in (200, 304):
        fail(f"/dashboard/ returned {resp.status if resp else 'no response'}; auth may be failing")
        ctx.close()
        return
    cookie_val = _get_session_cookie(ctx)
    if not cookie_val:
        fail("/dashboard/ load did NOT set yj_dash_sess cookie — redirect fix is not working")
    elif len(cookie_val) != 64:
        fail(f"yj_dash_sess cookie has unexpected length {len(cookie_val)} (want 64 hex chars for sha256)")
    else:
        ok(f"/dashboard/ load set yj_dash_sess (len={len(cookie_val)})")
    ctx.close()


def test_subscribers_page_reuses_cookie_no_reprompt(browser) -> None:
    """The operator's exact reproduction: log into /dashboard/, click the
    subscribers count, /dashboard/subscribers/ + its XHR should authorize
    silently via the session cookie. No 401 anywhere in the trace."""
    print("[e2e-auth-2 · /dashboard/subscribers/ + XHR reuse cookie, zero 401s]")
    ctx = _new_context(browser)
    page = ctx.new_page()

    seen_401s: list[str] = []
    page.on("response", lambda r: seen_401s.append(r.url) if r.status == 401 else None)

    page.goto(f"{SITE_URL}/dashboard/", wait_until="domcontentloaded")
    # Navigate to subscribers page — same-tab click semantics.
    resp = page.goto(f"{SITE_URL}/dashboard/subscribers/", wait_until="networkidle")

    if not resp or resp.status not in (200, 304):
        fail(f"/dashboard/subscribers/ returned {resp.status if resp else 'no response'}")
        ctx.close()
        return

    # Wait for the client-side fetch to /api/subscribers to complete.
    try:
        page.wait_for_response(
            lambda r: "/api/subscribers" in r.url and r.request.method == "GET",
            timeout=8000,
        )
    except Exception as e:
        fail(f"/api/subscribers XHR never completed within 8s: {e}")
        ctx.close()
        return

    if seen_401s:
        fail(f"saw {len(seen_401s)} 401 response(s) — cookie fast-path failed: {seen_401s[:5]}")
    else:
        ok("/dashboard/subscribers/ + /api/subscribers XHR both authorized via cookie, no 401s")

    # Extra assertion: subscriber count landed in the DOM
    count_text = page.text_content("[data-subs-count]") or ""
    if count_text.strip() and count_text.strip() != "—":
        ok(f"subscriber table hydrated (count: {count_text.strip()})")
    else:
        fail(f"subscriber table did NOT hydrate — count element still empty: {count_text!r}")
    ctx.close()


def test_csv_download_link_authorized(browser) -> None:
    print("[e2e-auth-3 · CSV download endpoint authorized via cookie]")
    ctx = _new_context(browser)
    page = ctx.new_page()
    page.goto(f"{SITE_URL}/dashboard/", wait_until="domcontentloaded")
    # Direct fetch to the CSV endpoint with the browser session cookie.
    resp = page.request.get(f"{SITE_URL}/api/subscribers?format=csv")
    if resp.status != 200:
        fail(f"CSV endpoint returned {resp.status}; expected 200")
    else:
        ctype = resp.headers.get("content-type", "")
        body = resp.text()
        if "text/csv" not in ctype:
            fail(f"CSV endpoint returned wrong content-type: {ctype}")
        elif not body.startswith("email,"):
            fail(f"CSV endpoint body doesn't start with expected header row: {body[:80]!r}")
        else:
            ok(f"CSV endpoint returned 200 text/csv (body starts: {body[:40]!r})")
    ctx.close()


def test_missing_cookie_and_no_auth_still_401(browser) -> None:
    """Defensive: strip cookies + no credentials → still 401. Ensures the
    redirect fix didn't accidentally open a bypass."""
    print("[e2e-auth-4 · no cookie + no basic auth → 401 (no bypass)]")
    # Fresh browser context WITHOUT http_credentials.
    bare = browser.new_context()
    resp = bare.request.get(f"{SITE_URL}/dashboard/subscribers/")
    if resp.status == 401:
        ok("/dashboard/subscribers/ correctly 401 without any auth")
    else:
        fail(f"expected 401 without auth, got {resp.status} — POTENTIAL BYPASS")
    resp2 = bare.request.get(f"{SITE_URL}/api/subscribers")
    if resp2.status == 401:
        ok("/api/subscribers correctly 401 without any auth")
    else:
        fail(f"expected 401 without auth, got {resp2.status} — POTENTIAL BYPASS")
    bare.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args()

    if not DASHBOARD_PASS:
        print("[SKIP] DASHBOARD_PASS env var not set — cannot run authed E2E", file=sys.stderr)
        return 0

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[SKIP] playwright not installed", file=sys.stderr)
        return 0

    print(f"Auth-flow E2E against {SITE_URL} as {DASHBOARD_USER}\n")
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=not args.headed)
        except Exception as e:
            print(f"[SKIP] Chromium not available: {e}", file=sys.stderr)
            return 0
        try:
            test_dashboard_load_sets_session_cookie(browser)
            print()
            test_subscribers_page_reuses_cookie_no_reprompt(browser)
            print()
            test_csv_download_link_authorized(browser)
            print()
            test_missing_cookie_and_no_auth_still_401(browser)
        finally:
            browser.close()

    print()
    if _failures:
        print(f"FAIL — {len(_failures)} auth-flow check(s) failed")
        for f in _failures:
            print(f"  - {f}")
        return 1 if args.strict else 0
    print("PASS — all dashboard-auth E2E checks green")
    return 0


if __name__ == "__main__":
    sys.exit(main())
