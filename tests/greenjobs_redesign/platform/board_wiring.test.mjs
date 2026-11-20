// Static boards -> Worker wiring (2026-11-20): the public flags endpoint, the paginated live board set
// (/api/jobs?view=board), sign-ups from another origin (staging Pages -> workers.dev) and the GA4 hook on
// Worker-rendered job pages (production hosts only).
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import test from 'node:test';
import { REPO, makeWorld, seedJob } from './helpers.mjs';

const MIGRATION = readFileSync(resolve(REPO, 'deliverables/greenjobs_migration_2026-11-06/build/d1/migrations/0004_job_alerts_newsletter.sql'), 'utf8');
const KEY = 'test-signing-key-0123456789abcdef-not-real';
const ON = { ALERTS_ENABLED: '1', NEWSLETTER_ENABLED: '1', LIST_MAIL_SIGNING_KEY: KEY, MAIL_PROVIDER: 'none' };
const STAGING_PAGES = 'https://greenjobs-staging-uk.pages.dev';

async function world(env = {}) {
  const w = await makeWorld(env);
  w.db.sqlite.exec(MIGRATION);
  return w;
}
const get = (w, url, headers = {}) => w.fetch(new Request(url, { headers }));
const post = (w, url, body, headers = {}) => w.fetch(new Request(url, {
  method: 'POST', headers: { 'Content-Type': 'application/json', 'CF-Connecting-IP': '198.51.100.7', ...headers }, body: JSON.stringify(body),
}));

test('GET /api/config: the flags the boards read before posting; off by default; ?site= names the edition; CORS allow-list', async () => {
  const off = await world();
  let r = await get(off, 'https://greenjobs.ie/api/config');
  assert.equal(r.status, 200);
  assert.deepEqual(await r.json(), { site: 'ie', alerts: false, newsletter: false });
  assert.match(r.headers.get('Cache-Control'), /s-maxage=300/);
  const on = await world({ ...ON, ALLOWED_ORIGINS: `https://greenjobs.ie,${STAGING_PAGES}` });
  r = await get(on, 'https://greenjobs.ie/api/config?site=uk', { Origin: STAGING_PAGES });
  assert.equal(r.status, 200);
  assert.equal(r.headers.get('Access-Control-Allow-Origin'), STAGING_PAGES);
  assert.deepEqual(await r.json(), { site: 'uk', alerts: true, newsletter: true });
  r = await get(on, 'https://greenjobs.ie/api/config', { Origin: 'https://evil.example' });
  assert.equal(r.status, 403);
  r = await get(on, 'https://greenjobs.ie/api/config?site=xx');
  assert.equal((await r.json()).site, 'ie'); // an unknown ?site= falls back to the host's board
});

test('GET /api/jobs?view=board: #gj-data rows, newest first, keyset pages, facets on page 1, total on every page, bad cursor 400', async () => {
  const w = await world();
  for (let i = 0; i < 7; i++) seedJob(w, { id: `ie:strat:${5000 + i}`, title: `Role ${i}`, posted_at: `2026-11-0${i + 1}T09:00:00Z` });
  seedJob(w, { id: 'ie:strat:4999', status: 'closed' });
  seedJob(w, { id: 'uk:strat:6000', site: 'uk' });
  const seen = [];
  let after = null;
  let pages = 0;
  for (;;) {
    const r = await get(w, `https://greenjobs.ie/api/jobs?view=board&limit=3${after ? `&after=${after}` : ''}`);
    assert.equal(r.status, 200);
    const b = await r.json();
    assert.equal(b.site, 'ie');
    assert.equal(b.total, 7);
    if (!pages) {
      assert.ok(b.facets && Array.isArray(b.facets.sectors) && Array.isArray(b.facets.regions) && Array.isArray(b.facets.contracts));
      assert.equal(b.facets.currency, 'EUR');
    } else assert.equal(b.facets, undefined);
    pages++;
    seen.push(...b.jobs.map((j) => j.id));
    for (const j of b.jobs) {
      assert.ok('text' in j && 'regions' in j && 'loc_class' in j && j.href.startsWith('/ie/jobs/'));
      assert.ok(!('description_html' in j) && !('apply_url' in j) && !('apply_email' in j), 'no apply or description fields');
    }
    after = b.next;
    if (!after) break;
  }
  assert.equal(pages, 3);
  assert.deepEqual(seen, ['5006', '5005', '5004', '5003', '5002', '5001', '5000'], 'public ids (Strategies id), newest first, no closed / other-site rows');
  const uk = await (await get(w, 'https://greenjobs.ie/api/jobs?view=board&site=uk')).json();
  assert.deepEqual(uk.jobs.map((j) => j.id), ['6000']);
  const notext = await (await get(w, 'https://greenjobs.ie/api/jobs?view=board&text=0&limit=1')).json();
  assert.ok(!('text' in notext.jobs[0]));
  assert.equal((await get(w, 'https://greenjobs.ie/api/jobs?view=board&after=9999999')).status, 400);
  assert.equal((await get(w, 'https://greenjobs.ie/api/jobs?view=board&after=%3Cscript%3E')).status, 400);
  const big = await (await get(w, 'https://greenjobs.ie/api/jobs?view=board&limit=99999')).json();
  assert.equal(big.jobs.length, 7); // ceiling 500 > 7
  // the plain /api/jobs (export shape) is unchanged
  const plain = await (await get(w, 'https://greenjobs.ie/api/jobs')).json();
  assert.ok(plain.jobs.every((j) => j.id.startsWith('ie:strat:')));
});

test('sign-ups: flags off = 404 and nothing stored; cross-origin board may name its edition, same-origin cannot; CSRF + rate limit hold', async () => {
  const off = await world({ ALERTS_ENABLED: '0', NEWSLETTER_ENABLED: '0', LIST_MAIL_SIGNING_KEY: KEY });
  assert.equal((await post(off, 'https://greenjobs.ie/api/alerts', { email: 'a@example.com', consent: true })).status, 404);
  assert.equal((await post(off, 'https://greenjobs.ie/api/newsletter', { email: 'a@example.com', consent: true })).status, 404);
  assert.equal(off.db.q('SELECT COUNT(*) AS n FROM alert_subscriptions')[0].n, 0);

  const w = await world({ ...ON, ALLOWED_ORIGINS: `https://greenjobs.ie,${STAGING_PAGES}` });
  // staging: the UK Pages board posts to the one Worker host with ?site=uk
  let r = await post(w, 'https://greenjobs.ie/api/alerts?site=uk', { email: 'uk@example.com', consent: true, sectors: ['Wind energy'] }, { Origin: STAGING_PAGES });
  assert.equal(r.status, 202);
  assert.equal(r.headers.get('Access-Control-Allow-Origin'), STAGING_PAGES);
  assert.deepEqual(w.db.q("SELECT site FROM alert_subscriptions WHERE email_norm = 'uk@example.com'").map((x) => x.site), ['uk']);
  // production same-origin: the Host decides, ?site= is ignored
  r = await post(w, 'https://greenjobs.ie/api/alerts?site=uk', { email: 'ie@example.com', consent: true });
  assert.equal(r.status, 202);
  assert.deepEqual(w.db.q("SELECT site FROM alert_subscriptions WHERE email_norm = 'ie@example.com'").map((x) => x.site), ['ie']);
  // newsletter the same way
  r = await post(w, 'https://greenjobs.ie/api/newsletter?site=uk', { email: 'nl@example.com', consent: true }, { Origin: STAGING_PAGES });
  assert.equal(r.status, 202);
  assert.deepEqual(w.db.q("SELECT site FROM newsletter_subscribers WHERE email_norm = 'nl@example.com'").map((x) => x.site), ['uk']);
  // CSRF: a foreign origin is refused before the route; a simple (non-JSON) cross-site POST is 415
  r = await post(w, 'https://greenjobs.ie/api/alerts', { email: 'x@example.com', consent: true }, { Origin: 'https://evil.example' });
  assert.equal(r.status, 403);
  r = await w.fetch(new Request('https://greenjobs.ie/api/alerts', { method: 'POST', headers: { 'Content-Type': 'text/plain', Origin: STAGING_PAGES }, body: '{"email":"x@example.com","consent":true}' }));
  assert.equal(r.status, 415);
  // preflight for the board origin allows exactly the JSON POST
  r = await w.fetch(new Request('https://greenjobs.ie/api/alerts', { method: 'OPTIONS', headers: { Origin: STAGING_PAGES, 'Access-Control-Request-Method': 'POST' } }));
  assert.equal(r.status, 204);
  assert.equal(r.headers.get('Access-Control-Allow-Headers'), 'Content-Type');
  // rate limit: 5 per 10 minutes per client
  const rl = await world({ ...ON });
  const codes = [];
  for (let i = 0; i < 7; i++) codes.push((await post(rl, 'https://greenjobs.ie/api/alerts', { email: `r${i}@example.com`, consent: true })).status);
  assert.deepEqual(codes, [202, 202, 202, 202, 202, 429, 429]);
});

test('GA4 hook on Worker-rendered pages: tag + consent banner only on a production host; job_view / apply events wired', async () => {
  const w = await world();
  seedJob(w, { id: 'ie:strat:7001', apply_mode: 'link', apply_url: 'https://careers.example.com/a' });
  seedJob(w, { id: 'ie:strat:7002', apply_mode: 'email' });
  const prod = await (await get(w, 'https://www.greenjobs.ie/ie/jobs/7001/')).text();
  assert.match(prod, /<meta name="gj-ga4" content="G-ZQPJGM484J" data-hosts="greenjobs.ie,www.greenjobs.ie">/);
  assert.match(prod, /<script src="\/js\/analytics.js" defer><\/script>/);
  assert.match(prod, /data-cookie-ga/);
  assert.match(prod, /data-cookie-reject/);
  assert.match(prod, /class="job__aside"[\s\S]*?data-apply data-ev="apply_click" data-ev-job="ie:strat:7001"/);
  assert.ok(!/googletagmanager/.test(prod), 'gtag.js is requested by analytics.js after consent, never by the page');
  const mail = await (await get(w, 'https://www.greenjobs.ie/ie/jobs/7002/')).text();
  assert.match(mail, /data-apply-form data-ev="apply_submit" data-ev-job="ie:strat:7002"/);
  assert.ok(!/data-apply data-ev="apply_click"/.test(mail), 'email mode: the in-page Apply link is not an apply_click');
  // any other host (staging workers.dev, test hosts): no tag, the no-tracking banner
  for (const host of ['ie.staging.greenjobs.test']) {
    const html = await (await get(w, `https://${host}/ie/jobs/7001/`)).text();
    assert.ok(!/gj-ga4|analytics\.js|data-cookie-ga/.test(html), host);
    assert.match(html, /No tracking\./);
  }
  // the list and gone pages follow the same rule
  assert.match(await (await get(w, 'https://greenjobs.ie/ie/jobs/')).text(), /gj-ga4/);
  assert.ok(!/gj-ga4/.test(await (await get(w, 'https://ie.staging.greenjobs.test/ie/jobs/')).text()));
  // the UK id never leaks onto the IE board and vice versa
  const uk = await (await get(w, 'https://www.greenjobs.co.uk/uk/jobs/')).text();
  assert.match(uk, /content="G-ZFW03XQE2N"/);
  assert.ok(!/G-ZQPJGM484J/.test(uk));
});
