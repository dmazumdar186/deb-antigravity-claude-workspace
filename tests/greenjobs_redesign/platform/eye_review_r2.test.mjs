// Eye review round 2 (qa/EYE_REVIEW_2026-11-20_r2.md), Worker side. Each test names its defect.
//   N1  the apply form from a staging Pages board reaches the Worker (cross-origin, ?site=), a same-origin Worker page
//       sends a real Origin (Referrer-Policy), Origin "null" and foreign origins stay refused, preflight is exact
//   N2  the Worker's job page renders the labelled apply form; N4 its button says "Apply now"
//   N9  link-apply source line; no headline zero
//   m1  no demo wording on Worker pages; m3 display locations (parity with build_site.display_location)
//   m4  the mid-sentence paragraph break (parity with build_site.MID_SENTENCE_BREAK)
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { resolve } from 'node:path';
import test from 'node:test';
import { REPO, applyRequest, makeWorld, seedJob, workerModule } from './helpers.mjs';

const PAGES_IE = 'https://greenjobs-stg-ie.pages.dev';
const PAGES_UK = 'https://greenjobs-stg-uk.pages.dev';
const STAGING = { ALLOWED_ORIGINS: `${PAGES_IE},${PAGES_UK}` };

test('N1: a staging Pages board posts the multipart form cross-origin; ?site= picks the edition; CORS on the answer', async () => {
  const w = await makeWorld(STAGING);
  seedJob(w, { id: 'ie:strat:8101' });
  seedJob(w, { id: 'uk:strat:8102', site: 'uk' });
  let r = await w.fetch(applyRequest({ job_id: 'ie:strat:8101', email: 'n1-ie@example.com' }, { origin: PAGES_IE }));
  assert.equal(r.status, 201);
  assert.equal(r.headers.get('Access-Control-Allow-Origin'), PAGES_IE);
  // the IE Pages project also carries /uk/: its UK job form names the edition
  const fd = await applyRequest({ job_id: 'uk:strat:8102', email: 'n1-uk@example.com' }, { origin: PAGES_IE }).formData();
  r = await w.fetch(new Request('https://greenjobs.ie/api/apply?site=uk', { method: 'POST', body: fd, headers: { Origin: PAGES_IE, 'CF-Connecting-IP': '203.0.113.20' } }));
  assert.equal(r.status, 201, 'UK job accepted through ?site=uk cross-origin');
  assert.deepEqual(w.db.q("SELECT site FROM applications WHERE applicant_email = 'n1-uk@example.com'").map((x) => x.site), ['uk']);
});

test('N1: the static board form sends its page id (11501460 / gaia-9360); the Worker maps it to the D1 id', async () => {
  const w = await makeWorld(STAGING);
  seedJob(w, { id: 'ie:strat:8601' });
  seedJob(w, { id: 'uk:gaia:8602', site: 'uk', source: 'feed', source_id: 'gaia:8602' });
  let r = await w.fetch(applyRequest({ job_id: '8601', email: 'slug-ie@example.com' }, { origin: PAGES_IE }));
  assert.equal(r.status, 201, 'numeric page id');
  const fd = await applyRequest({ job_id: 'gaia-8602', email: 'slug-uk@example.com' }).formData();
  r = await w.fetch(new Request('https://greenjobs.ie/api/apply?site=uk', { method: 'POST', body: fd, headers: { Origin: PAGES_UK, 'CF-Connecting-IP': '203.0.113.30' } }));
  assert.equal(r.status, 201, 'feed page id on the other edition');
  assert.deepEqual(w.db.q("SELECT job_id FROM applications WHERE applicant_email IN ('slug-ie@example.com','slug-uk@example.com') ORDER BY job_id").map((x) => x.job_id), ['ie:strat:8601', 'uk:gaia:8602']);
  for (const bad of ['../x', 'nope-1', '']) {
    r = await w.fetch(applyRequest({ job_id: bad, email: 'bad@example.com' }, { origin: PAGES_IE, ip: '203.0.113.31' }));
    assert.equal(r.status, 400, bad);
  }
});

test('N1: same-origin ignores ?site=; Origin "null" (no-referrer form POST) and foreign origins are refused', async () => {
  const w = await makeWorld(STAGING);
  seedJob(w, { id: 'ie:strat:8201' });
  const fd = await applyRequest({ job_id: 'ie:strat:8201', email: 'same@example.com' }).formData();
  let r = await w.fetch(new Request('https://greenjobs.ie/api/apply?site=uk', { method: 'POST', body: fd, headers: { Origin: 'https://greenjobs.ie', 'CF-Connecting-IP': '203.0.113.21' } }));
  assert.equal(r.status, 201, 'the Host decides on a same-origin post');
  for (const origin of ['null', 'https://evil.example', 'https://greenjobs-stg-ie.pages.dev.evil.example']) {
    r = await w.fetch(applyRequest({ job_id: 'ie:strat:8201', email: `o${origin.length}@example.com` }, { origin, ip: '203.0.113.22' }));
    assert.equal(r.status, 403, origin);
    assert.equal((await r.json()).error, 'origin_not_allowed');
  }
});

test('N1: preflight from a board origin allows POST + Content-Type only; a foreign origin gets 403', async () => {
  const w = await makeWorld(STAGING);
  let r = await w.fetch(new Request('https://greenjobs.ie/api/apply', { method: 'OPTIONS', headers: { Origin: PAGES_UK, 'Access-Control-Request-Method': 'POST' } }));
  assert.equal(r.status, 204);
  assert.equal(r.headers.get('Access-Control-Allow-Origin'), PAGES_UK);
  assert.equal(r.headers.get('Access-Control-Allow-Methods'), 'GET, POST, OPTIONS');
  assert.equal(r.headers.get('Access-Control-Allow-Headers'), 'Content-Type');
  r = await w.fetch(new Request('https://greenjobs.ie/api/apply', { method: 'OPTIONS', headers: { Origin: 'https://evil.example', 'Access-Control-Request-Method': 'POST' } }));
  assert.equal(r.status, 403);
});

test('N1/N2/N4/m1: the Worker job page sends its Origin, renders the labelled form and "Apply now", no demo wording', async () => {
  const w = await makeWorld();
  seedJob(w, { id: 'ie:strat:8301', apply_mode: 'email' });
  const r = await w.fetch(new Request('https://greenjobs.ie/ie/jobs/8301/'));
  assert.equal(r.status, 200);
  assert.equal(r.headers.get('Referrer-Policy'), 'strict-origin-when-cross-origin', 'no-referrer makes Chrome send Origin: null on the form POST');
  const html = await r.text();
  assert.match(html, /<form class="job__apply-form"[^>]*action="\/api\/apply"/);
  for (const id of ['ap-name', 'ap-email', 'ap-phone', 'ap-cover', 'ap-cv']) {
    assert.match(html, new RegExp(`<div class="field"><label for="${id}">[^<]*(<span class="field__opt">[^<]*</span>)?</label><(input|textarea) class="in[^"]*" id="${id}"`), id);
  }
  assert.match(html, /<label class="check check--apply" for="ap-consent"><input id="ap-consent"/);
  assert.match(html, /data-apply-err="email"/);
  assert.match(html, />Apply now<span class="arw"/);
  assert.doesNotMatch(html, />Apply on greenjobs\.ie</);
  assert.doesNotMatch(html, /Demo redesign/);
});

test('N9: a link-apply page credits its own site; a job with no similar roles shows no headline zero', async () => {
  const w = await makeWorld();
  seedJob(w, { id: 'ie:gaia:9401', source: 'feed', source_id: 'gaia:9401', apply_mode: 'link', apply_url: 'https://gaiatalent.com/jobs/ecologist/', sal_text: 'EUR 40,000 - 45,000', location: 'Roscommon' });
  const html = await (await w.fetch(new Request('https://greenjobs.ie/ie/jobs/gaia-9401/'))).text();
  assert.match(html, /Description as published on gaiatalent\.com; reference ie:gaia:9401\./);
  assert.doesNotMatch(html, /published by the employer on greenjobs\.ie/);
  assert.doesNotMatch(html, /<b class="num">0<\/b> similar/);
});

const PY = (expr, arg) => {
  const code = `import json,sys;sys.path.insert(0,${JSON.stringify(resolve(REPO, 'execution/gtm_client_workflows/greenjobs_redesign'))});import build_site as b;print(json.dumps([${expr} for x in json.loads(sys.stdin.read())]))`;
  const out = spawnSync('python3', ['-c', code], { input: JSON.stringify(arg), encoding: 'utf8' });
  assert.equal(out.status, 0, out.stderr);
  return JSON.parse(out.stdout);
};

const LOCS = [
  ['West Yorkshire, Scotland (nationwide)', 'West Yorkshire, Scotland'],
  ['London Central, West Yorkshire, England', 'Central London, West Yorkshire'],
  ['Dublin, United Kingdom (UK)', 'Dublin'],
  ['Manchester, England, Scotland (nationwide)', 'Manchester, Scotland'],
  ['London City, Manchester', 'City of London, Manchester'],
  ['Monagahan, Donegal, Cavan, Leitrim', 'Monaghan, Donegal, Cavan, Leitrim'],
  ['United Kingdom (UK), Ireland (nationwide)', 'United Kingdom (UK), Ireland (nationwide)'],
  ['Scotland (nationwide)', 'Scotland (nationwide)'],
  ['England', 'England'],
  ['London Central', 'Central London'],
  ['Cork, Dublin, Galway', 'Cork, Dublin, Galway'],
  ['', ''],
];

test('m3: display locations, Worker displayLocation === build_site.display_location, idempotent', async () => {
  const { displayLocation } = await workerModule('render/lib.js');
  const js = LOCS.map(([a]) => displayLocation(a));
  assert.deepEqual(js, LOCS.map(([, b]) => b));
  assert.deepEqual(js.map(displayLocation), js, 'idempotent');
  assert.deepEqual(PY('b.display_location(x)', LOCS.map(([a]) => a)), js);
});

test('m3: a D1 row with a multi-select location renders the display form on the job page', async () => {
  const w = await makeWorld();
  seedJob(w, { id: 'uk:strat:8501', site: 'uk', location: 'London Central, West Yorkshire, England' });
  const html = await (await w.fetch(new Request('https://greenjobs.co.uk/uk/jobs/8501/'))).text();
  assert.match(html, /Central London, West Yorkshire/);
  assert.doesNotMatch(html, /London Central, West Yorkshire, England/);
});

const ARBORIST = '<div> <p><div>to provide joined-up arboricultural and</div><div>ecological advice to clients across Ireland.</div><div>The position is suited to someone.</div><div>Key Responsibilities:</div><div>survey work, reports,</div><div>advice</div></p></div>';

test('m4: a sentence an editor split across two <div>s is one paragraph (Worker === build_site)', async () => {
  const S = await workerModule('render/sanitise.js');
  assert.equal(typeof S.divsToParagraphs, 'function');
  const js = S.divsToParagraphs(ARBORIST);
  assert.match(js, /arboricultural and ecological advice to clients across Ireland\./);
  assert.doesNotMatch(js, /arboricultural and<\/p>/);
  assert.match(js, /<p>The position is suited to someone\.<\/p>/, 'a finished sentence keeps its own paragraph');
  assert.match(js, /<p>Key Responsibilities:<\/p>/, 'a line ending in a colon is not joined');
  assert.match(js, /survey work, reports, advice/, 'a comma-ended line joins the next lowercase line');
  assert.deepEqual(PY('b.divs_to_paragraphs(x)', [ARBORIST]), [js]);
});
