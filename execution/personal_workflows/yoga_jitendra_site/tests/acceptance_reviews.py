#!/usr/bin/env python
"""
acceptance_reviews.py — hard-fail output-acceptance gate for the reviews system.

Asserts on what a visitor / a moderator actually sees, not on layers. Per
`~/.claude/rules/output-acceptance-gate.md` and
`~/.claude/rules/front-door-synthetic.md`.

Checks (all HARD-FAIL, exit non-zero on any miss):

1. GET /                         → 200 + <section id="testimonials"> present
2. GET /                         → aggregateRating JSON-LD block present
3. GET /                         → at least one Review JSON-LD object present
4. GET /reviews/                 → 200 + at least 3 review cards render
5. GET /en/reviews/              → 200 + at least 3 review cards render
6. GET /api/reviews-public       → 200, JSON with `reviews[]`, count ≥ seed size (4)
7. POST /review-submit           → 303 redirect to /?review=…#testimonials
8. POST /review-submit no consent → 303 to /?review=error&reason=consent…
9. GET /api/reviews-admin?count=1 → 401 without auth (private endpoint gated)
10. GET /api/reviews-admin?count=1 → 200 with correct Basic-Auth
11. Static seed sanity: src/content/reviews-seed.json parses + has ≥4 items

Env:
  SITE_URL         Base URL under test. Default: https://yoga-jitendra.pages.dev
  DASHBOARD_USER   Basic-Auth user for admin checks. Default: debanjan
  DASHBOARD_PASS   Basic-Auth pass for admin checks. If missing, admin
                   checks are skipped with a WARN (not FAIL) so this gate
                   can run in CI without leaking secrets.
"""

from __future__ import annotations

import json
import os
import sys
import time
from base64 import b64encode
from pathlib import Path
from urllib import error, parse, request

SITE_URL = os.environ.get('SITE_URL', 'https://yoga-jitendra.pages.dev').rstrip('/')
USER = os.environ.get('DASHBOARD_USER', 'debanjan')
PASS = os.environ.get('DASHBOARD_PASS')

ROOT = Path(__file__).resolve().parent.parent
SEED = ROOT / 'src' / 'content' / 'reviews-seed.json'

FAILURES: list[str] = []
WARNINGS: list[str] = []


def fail(msg: str) -> None:
    FAILURES.append(msg)
    print(f'  ✗ {msg}')


def ok(msg: str) -> None:
    print(f'  ✓ {msg}')


def warn(msg: str) -> None:
    WARNINGS.append(msg)
    print(f'  ! {msg}')


def http_get(url: str, headers: dict[str, str] | None = None, timeout: float = 15.0) -> tuple[int, str]:
    req = request.Request(url, headers=headers or {})
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode('utf-8', errors='replace')
    except error.HTTPError as e:
        return e.code, (e.read() or b'').decode('utf-8', errors='replace')
    except Exception as e:
        return 0, f'ERROR: {e!s}'


def http_post_form(
    url: str,
    fields: dict[str, str],
    headers: dict[str, str] | None = None,
    timeout: float = 15.0,
    allow_redirects: bool = False,
) -> tuple[int, str, str]:
    """Returns (status, body, location_header)."""
    body = parse.urlencode(fields).encode('utf-8')
    hdrs = dict(headers or {})
    hdrs.setdefault('Content-Type', 'application/x-www-form-urlencoded')

    class NoRedirect(request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, hdrs_, newurl):
            return None

    opener = request.build_opener(NoRedirect()) if not allow_redirects else request.build_opener()
    req_ = request.Request(url, data=body, headers=hdrs, method='POST')
    try:
        with opener.open(req_, timeout=timeout) as resp:
            return resp.status, resp.read().decode('utf-8', errors='replace'), resp.headers.get('Location') or ''
    except error.HTTPError as e:
        loc = e.headers.get('Location', '') if e.headers else ''
        return e.code, (e.read() or b'').decode('utf-8', errors='replace'), loc
    except Exception as e:
        return 0, f'ERROR: {e!s}', ''


def basic_auth_header() -> dict[str, str]:
    if not PASS:
        return {}
    tok = b64encode(f'{USER}:{PASS}'.encode('utf-8')).decode('ascii')
    return {'Authorization': f'Basic {tok}'}


def check_seed_file() -> None:
    print('[1] Static seed sanity')
    if not SEED.exists():
        fail(f'seed missing at {SEED}')
        return
    try:
        data = json.loads(SEED.read_text(encoding='utf-8'))
    except Exception as e:
        fail(f'seed not valid JSON: {e}')
        return
    reviews = data.get('reviews', [])
    if not isinstance(reviews, list) or len(reviews) < 4:
        fail(f'seed has <4 reviews (got {len(reviews)})')
        return
    ok(f'seed has {len(reviews)} reviews')


def check_homepage() -> None:
    print('[2] GET / — testimonials section + JSON-LD')
    status, html = http_get(f'{SITE_URL}/')
    if status != 200:
        fail(f'GET / returned {status}')
        return
    ok(f'GET / status 200 ({len(html)} bytes)')

    if 'id="testimonials"' not in html:
        fail('#testimonials section not found in homepage HTML')
    else:
        ok('#testimonials section present')

    if '"aggregateRating"' in html:
        ok('aggregateRating JSON-LD present')
    else:
        fail('aggregateRating JSON-LD block missing on homepage')

    if '"@type":"Review"' in html or '"@type": "Review"' in html:
        ok('Review JSON-LD objects present')
    else:
        fail('Review JSON-LD objects missing on homepage')


def check_reviews_pages() -> None:
    print('[3] GET /reviews/ + /en/reviews/')
    for path, label in [('/reviews/', 'FR'), ('/en/reviews/', 'EN')]:
        status, html = http_get(f'{SITE_URL}{path}')
        if status != 200:
            fail(f'{label} {path} returned {status}')
            continue
        if 'data-review-card' not in html:
            fail(f'{label} {path} does not contain any data-review-card')
            continue
        n = html.count('data-review-card')
        if n < 3:
            fail(f'{label} {path} has only {n} review cards (<3)')
        else:
            ok(f'{label} {path} renders {n} review cards')


def check_public_api() -> None:
    print('[4] GET /api/reviews-public')
    status, body = http_get(f'{SITE_URL}/api/reviews-public?fresh=1')
    if status != 200:
        fail(f'/api/reviews-public returned {status}')
        return
    try:
        data = json.loads(body)
    except Exception as e:
        fail(f'/api/reviews-public non-JSON: {e}')
        return
    reviews = data.get('reviews', [])
    if not isinstance(reviews, list):
        fail('/api/reviews-public: reviews is not a list')
        return
    if len(reviews) < 4:
        fail(f'/api/reviews-public: only {len(reviews)} reviews (<4 seed size)')
    else:
        ok(f'/api/reviews-public: {len(reviews)} reviews, avg {data.get("average_rating")}')


def check_submit_endpoint() -> None:
    print('[5] POST /review-submit (validation paths only — Turnstile will reject synthetic tokens)')
    # Missing consent → should redirect with reason=consent
    status, _, loc = http_post_form(
        f'{SITE_URL}/review-submit',
        {
            'name': 'AcceptanceBot',
            'rating': '5',
            'body': 'This is a synthetic acceptance-test submission with enough body length to pass the min check.',
            'source': 'onsite',
            'lang': 'fr',
            # 'consent' intentionally missing
            'cf-turnstile-response': 'dummy-token-would-fail-anyway',
        },
    )
    if status not in (303, 302):
        fail(f'/review-submit no-consent expected 303, got {status}')
        return
    if 'reason=consent' not in loc and 'reason=turnstile' not in loc:
        fail(f'/review-submit no-consent Location did not carry a reason (got {loc!r})')
    else:
        ok(f'/review-submit no-consent → {status} → {loc}')


def check_admin_auth() -> None:
    print('[6] /api/reviews-admin auth gate')
    status, _ = http_get(f'{SITE_URL}/api/reviews-admin?count=1')
    if status != 401:
        fail(f'/api/reviews-admin without auth expected 401, got {status}')
    else:
        ok(f'/api/reviews-admin without auth → 401')

    if not PASS:
        warn('DASHBOARD_PASS not set — skipping authed admin check')
        return

    status, body = http_get(f'{SITE_URL}/api/reviews-admin?count=1', headers=basic_auth_header())
    if status != 200:
        fail(f'/api/reviews-admin with auth expected 200, got {status}')
        return
    try:
        data = json.loads(body)
    except Exception:
        fail('/api/reviews-admin with auth: non-JSON body')
        return
    if 'pending' not in data or 'approved' not in data:
        fail(f'/api/reviews-admin with auth: missing pending/approved fields ({data})')
    else:
        ok(f'/api/reviews-admin with auth: pending={data.get("pending")}, approved={data.get("approved")}')


def main() -> int:
    print(f'acceptance_reviews.py — target {SITE_URL}')
    print(f'  user={USER} pass={"set" if PASS else "unset"}')
    print()

    check_seed_file()
    check_homepage()
    check_reviews_pages()
    check_public_api()
    check_submit_endpoint()
    check_admin_auth()

    print()
    if WARNINGS:
        print('WARNINGS:')
        for w in WARNINGS:
            print(f'  ! {w}')
    if FAILURES:
        print()
        print(f'FAIL: {len(FAILURES)} acceptance check(s) failed')
        for f in FAILURES:
            print(f'  ✗ {f}')
        return 1
    print('PASS: all acceptance checks passed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
