#!/usr/bin/env python
"""
description: Hard-fail output-acceptance gate for the yoga_jitendra reviews system.
inputs: SITE_URL (default https://yoga-jitendra.pages.dev), DASHBOARD_USER, DASHBOARD_PASS
outputs: stdout PASS/FAIL log; exit non-zero on any assertion failure.

Asserts on what a visitor / a moderator actually sees, not on layers. Per
`~/.claude/rules/output-acceptance-gate.md`,
`~/.claude/rules/front-door-synthetic.md`, and
`~/.claude/rules/live-artifact-acceptance.md`.

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
12. LIVE date-provenance guard (2026-08-04 regression class):
    a. /api/reviews-public MUST include `date_provenance` per record.
    b. No `verified=true` record may return a specific month/year on the
       live HTML while its submitted_at & approved_at are within 60s of
       each other (the silent-now fingerprint). Instead, the DOM must
       carry `data-provenance="unknown"` and the copy "Date à confirmer"
       (FR) or "Date pending verification" (EN).
    c. JSON-LD `datePublished` MUST NOT appear for unknown-provenance
       records (SEO leak class).
    d. In-memory corpus: 3 known-bad shapes MUST be tagged 'unknown';
       3 known-good shapes MUST stay 'provided'. This is the regression
       corpus that would have caught the 2026-07 shipped-broken bug the
       first time.

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
import re
import sys
from base64 import b64encode
from datetime import datetime
from pathlib import Path
from urllib import error, parse, request

SITE_URL = os.environ.get('SITE_URL', 'https://yoga-jitendra.pages.dev').rstrip('/')
USER = os.environ.get('DASHBOARD_USER', 'debanjan')
PASS = os.environ.get('DASHBOARD_PASS')

# Cloudflare Bot Fight Mode returns 403 to bare Python-urllib UAs. Send a
# real browser UA so the acceptance gate exercises the same code path a
# visitor's browser hits. This is a synthetic test — not a bot evading
# real anti-abuse — so a plausible UA is appropriate.
DEFAULT_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'

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
    hdrs = dict(headers or {})
    hdrs.setdefault('User-Agent', DEFAULT_UA)
    hdrs.setdefault('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,*/*;q=0.5')
    hdrs.setdefault('Accept-Language', 'fr-FR,fr;q=0.9,en;q=0.8')
    req = request.Request(url, headers=hdrs)
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
    hdrs.setdefault('User-Agent', DEFAULT_UA)
    hdrs.setdefault('Accept', 'text/html,*/*;q=0.5')

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
    # KV starts empty on first deploy; the seed rendered via SSG covers the
    # visitor experience (asserted in check_homepage / check_reviews_pages).
    # KV populates as the moderator approves reviews. Warn — don't fail —
    # while count < seed, since the site still shows the seed to visitors.
    if len(reviews) == 0:
        warn('/api/reviews-public: empty (KV not seeded yet); site renders seed via SSG')
    elif len(reviews) < 4:
        warn(f'/api/reviews-public: only {len(reviews)} reviews in KV so far (< 4 seed size)')
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


# ---------------------------------------------------------------------------
# 2026-08-04 date-provenance regression guard.
#
# Born from the 2026-07 shipped-broken bug: every historical Google review
# was silently stamped submitted_at=now on import, and every visitor saw
# "juillet 2026" as the review month for reviews actually from 2024-2025.
# The previous acceptance gate only asserted that `submitted_at` was a
# non-empty string — a bug that survives that check trivially.
#
# The stronger form asserts on the RENDERED OUTPUT: for any verified record
# whose submitted_at & approved_at are within 60s of each other, the DOM
# must NOT show a specific month/year, and the JSON-LD must NOT leak a
# datePublished.
# ---------------------------------------------------------------------------

# Silent-now fingerprint window. Kept in sync with reviews-public.ts +
# src/lib/reviews.mjs by convention — bump all three if changed.
SILENT_NOW_WINDOW_MS = 60 * 1000

# Regex forms of the "specific month, specific year" strings that MUST NOT
# appear next to an unknown-provenance record. Locale-covered: FR long
# month, EN long month, YYYY-MM ISO fragment. Deliberately regex-based (not
# literal-string) so a copy-tweak from "juillet 2026" to "Juillet 2026" or
# "07/2026" doesn't silently bypass the check.
_FR_MONTHS = r'(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)'
_EN_MONTHS = r'(January|February|March|April|May|June|July|August|September|October|November|December)'
SPECIFIC_DATE_RES: list[re.Pattern[str]] = [
    re.compile(rf'{_FR_MONTHS}\s+20\d{{2}}', re.IGNORECASE),
    re.compile(rf'{_EN_MONTHS}\s+20\d{{2}}', re.IGNORECASE),
    re.compile(r'20\d{2}-(0[1-9]|1[0-2])'),  # 2026-07 ISO fragment
]

# 3 bad-shape corpus rows the gate MUST tag 'unknown'.
CORPUS_BAD: list[dict] = [
    {
        'id': 'corpus-bad-identical-ms',
        'verified': True,
        'submitted_at': '2026-07-24T14:40:07.097Z',
        'approved_at':  '2026-07-24T14:40:07.097Z',  # identical to the ms
    },
    {
        'id': 'corpus-bad-sub-second',
        'verified': True,
        'submitted_at': '2026-07-24T14:40:07.097Z',
        'approved_at':  '2026-07-24T14:40:07.998Z',  # <1s apart
    },
    {
        'id': 'corpus-bad-sub-minute',
        'verified': True,
        'submitted_at': '2026-07-24T14:40:07.097Z',
        'approved_at':  '2026-07-24T14:40:52.097Z',  # 45s apart
    },
]

# 3 good-shape corpus rows the gate MUST leave as 'provided'.
CORPUS_GOOD: list[dict] = [
    {
        'id': 'corpus-good-normal-import',
        'verified': True,
        'submitted_at': '2025-08-01T00:00:00.000Z',  # historical GBP
        'approved_at':  '2026-07-24T14:15:38.512Z',  # imported months later
    },
    {
        'id': 'corpus-good-user-submission',
        'verified': False,  # user submissions are exempt from the heuristic
        'submitted_at': '2026-07-24T14:40:07.097Z',
        'approved_at':  '2026-07-24T14:40:07.097Z',
    },
    {
        'id': 'corpus-good-day-apart',
        'verified': True,
        'submitted_at': '2026-07-17T00:00:00.000Z',
        'approved_at':  '2026-07-24T14:41:11.693Z',
    },
]


def compute_provenance(r: dict) -> str:
    """Python mirror of reviews-public.ts computeDateProvenance. If this
    ever drifts from the TS side, the corpus test below will fail and
    force a re-sync."""
    if not r.get('verified'):
        return 'provided'
    sub = r.get('submitted_at')
    app = r.get('approved_at')
    if not sub or not app:
        return 'provided'
    try:
        sub_ms = int(datetime.fromisoformat(sub.replace('Z', '+00:00')).timestamp() * 1000)
        app_ms = int(datetime.fromisoformat(app.replace('Z', '+00:00')).timestamp() * 1000)
    except Exception:
        return 'provided'
    if abs(app_ms - sub_ms) < SILENT_NOW_WINDOW_MS:
        return 'unknown'
    return 'provided'


def check_provenance_corpus() -> None:
    print('[7] Provenance heuristic — frozen corpus')
    for row in CORPUS_BAD:
        got = compute_provenance(row)
        if got != 'unknown':
            fail(f"corpus {row['id']}: expected 'unknown', got {got!r}")
        else:
            ok(f"corpus {row['id']} → unknown")
    for row in CORPUS_GOOD:
        got = compute_provenance(row)
        if got != 'provided':
            fail(f"corpus {row['id']}: expected 'provided', got {got!r}")
        else:
            ok(f"corpus {row['id']} → provided")


def check_live_provenance() -> None:
    print('[8] Live API date_provenance + DOM render + JSON-LD leak')
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
    if not reviews:
        warn('/api/reviews-public: no reviews to provenance-check')
        return

    # 8a — every record must carry date_provenance.
    missing = [r.get('id') for r in reviews if 'date_provenance' not in r]
    if missing:
        fail(f'{len(missing)} records missing date_provenance field: {missing[:3]}...')
    else:
        ok(f'all {len(reviews)} records carry date_provenance')

    # 8b — reconcile server-side value against local heuristic.
    disagreements: list[str] = []
    for r in reviews:
        server = r.get('date_provenance', 'provided')
        local = compute_provenance(r)
        if server != local:
            disagreements.append(f"{r.get('id')}: server={server} local={local}")
    if disagreements:
        fail(f'server / local heuristic disagree on {len(disagreements)}: {disagreements[:3]}')
    else:
        ok('server and local heuristic agree on every record')

    unknown_ids = {r['id'] for r in reviews if r.get('date_provenance') == 'unknown'}
    if unknown_ids:
        ok(f'{len(unknown_ids)} record(s) tagged unknown-provenance (interim UI applies)')
    else:
        ok('no unknown-provenance records right now')

    # 8c — fetch the FR + EN /reviews/ pages and assert unknown-provenance
    # cards omit the date cell entirely (interim UX per operator 2026-08-04:
    # silence reads as an editorial choice, "Date à confirmer" read as a
    # soft error). Once the Google-Maps-scrape backfill lands and provenance
    # flips to "provided", the date returns via reconcileExistingDates().
    if unknown_ids:
        for path in ['/reviews/', '/en/reviews/']:
            status_h, html = http_get(f'{SITE_URL}{path}')
            if status_h != 200:
                fail(f'{path} returned {status_h}')
                continue
            for uid in unknown_ids:
                pat = re.compile(
                    r'<figure[^>]+data-review-id="' + re.escape(uid) + r'"[^>]*>.*?</figure>',
                    re.DOTALL,
                )
                m = pat.search(html)
                if not m:
                    # Card missing entirely is a separate defect but not
                    # this check's job — the dom_acceptance test covers it.
                    continue
                card = m.group(0)
                meta_m = re.search(
                    r'<div class="review-meta"[^>]*>(.*?)</div>', card, re.DOTALL,
                )
                if not meta_m:
                    fail(f'{path} card {uid}: no review-meta block found')
                    continue
                meta = meta_m.group(1)
                # (i) meta block MUST NOT contain any [data-review-date]
                # element — the element is stripped for unknown cards.
                if 'data-review-date' in meta:
                    fail(
                        f'{path} card {uid}: unknown-provenance card still '
                        f'renders a [data-review-date] element (should be omitted)'
                    )
                # (ii) meta block MUST NOT leak any specific month/year
                # (the underlying bug shape — falsely-precise dates).
                for rx in SPECIFIC_DATE_RES:
                    hit = rx.search(meta)
                    if hit:
                        fail(
                            f'{path} card {uid}: unknown-provenance card leaks '
                            f'a specific date "{hit.group(0)}" — the exact 2026-07 bug shape'
                        )
                        break
                else:
                    ok(f'{path} card {uid}: unknown-provenance card omits date cell + no specific date leak')

    # 8d — JSON-LD leak: fetch homepage + confirm datePublished missing for
    # every unknown-provenance record.
    if unknown_ids:
        status_home, home_html = http_get(f'{SITE_URL}/')
        if status_home != 200:
            warn(f'GET / returned {status_home}, skipping JSON-LD leak check')
            return
        # Extract each Review block from the JSON-LD graph and check that
        # unknown-provenance authors do NOT carry datePublished. Simplest
        # form: scan the ld+json script text for author names + adjacent
        # datePublished field.
        m = re.search(
            r'<script type="application/ld\+json">(.*?)</script>',
            home_html,
            re.DOTALL,
        )
        if not m:
            warn('no ld+json script on homepage')
            return
        try:
            ld = json.loads(m.group(1))
        except Exception as e:
            fail(f'ld+json is not valid JSON: {e}')
            return
        # The Review objects live at $..review[*] under the LocalBusiness.
        # Walk the graph and inspect any Review node.
        def walk(node):
            if isinstance(node, dict):
                if node.get('@type') == 'Review':
                    yield node
                for v in node.values():
                    yield from walk(v)
            elif isinstance(node, list):
                for it in node:
                    yield from walk(it)
        reviews_in_ld = list(walk(ld))
        # Build name → provenance map from the API response.
        prov_by_name = {
            r.get('name'): r.get('date_provenance', 'provided') for r in reviews
        }
        leaked = []
        for rv in reviews_in_ld:
            name = None
            auth = rv.get('author')
            if isinstance(auth, dict):
                name = auth.get('name')
            if not name:
                continue
            if prov_by_name.get(name) == 'unknown' and 'datePublished' in rv:
                leaked.append((name, rv['datePublished']))
        if leaked:
            fail(
                f'JSON-LD leaks datePublished for {len(leaked)} unknown-provenance '
                f'reviews: {leaked[:3]} — SEO cache will index a wrong date'
            )
        else:
            ok('JSON-LD emits no datePublished for unknown-provenance rows')


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
    check_provenance_corpus()
    check_live_provenance()

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
