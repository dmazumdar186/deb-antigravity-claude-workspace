// Eye review round 3 (qa/EYE_REVIEW_2026-11-21_r3.md), Worker side. Each test names its defect.
//   R3-1 (M1)  a CV is validated and ATTACHED to the application mail; nothing is stored without CV_STORAGE=r2 + R2;
//              DRY_RUN logs metadata only (never content); a live send carries the attachment.
//   R3-2 (M2)  HTML pages on a host that is not a board host (workers.dev) 301 to the edition's board URL, same path;
//              the API keeps working there; a browser form post without JS (Accept: text/html) gets an HTML page.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { PDF_BYTES, applyRequest, makeWorld, seedJob } from './helpers.mjs';

const WORKERS = 'greenjobs-platform-staging.debanjan186.workers.dev';
const BOARD_IE = 'https://greenjobs-stg-ie.pages.dev';
const BOARD_UK = 'https://greenjobs-stg-uk.pages.dev';
const staging = (over = {}) => makeWorld({
  HOST_SITE_MAP: JSON.stringify({ [WORKERS]: 'ie' }),
  CANONICAL_ORIGIN_IE: BOARD_IE, CANONICAL_ORIGIN_UK: BOARD_UK,
  ALLOWED_ORIGINS: `${BOARD_IE},${BOARD_UK}`, ...over,
});

/** Run fn with console.log/error/warn captured; returns [result, every logged line]. */
async function captureLogs(fn) {
  const lines = [];
  const orig = { log: console.log, error: console.error, warn: console.warn };
  for (const k of Object.keys(orig)) console[k] = (...a) => lines.push(a.map((x) => (typeof x === 'string' ? x : JSON.stringify(x))).join(' '));
  try { return [await fn(), lines]; } finally { Object.assign(console, orig); }
}

// A PDF whose body carries a marker that must never reach a log line.
const MARKER = 'CANDIDATE-SECRET-CV-CONTENT-7f3a';
const SECRET_PDF = new TextEncoder().encode(`%PDF-1.7\n1 0 obj<</T (${MARKER})>>endobj\ntrailer<<>>\n%%EOF`);

test('R3-1: a CV is accepted without R2 (no CVS binding): 201, nothing stored, cv_key NULL', async () => {
  const w = await makeWorld();
  delete w.env.CVS;
  seedJob(w, { id: 'ie:strat:1' });
  const r = await w.fetch(applyRequest({ job_id: 'ie:strat:1' }, { cv: PDF_BYTES }));
  assert.equal(r.status, 201, await r.clone().text());
  assert.equal((await r.json()).delivery, 'dry_run');
  assert.equal(w.db.q('SELECT cv_key FROM applications')[0].cv_key, null);
});

test('R3-1: with an R2 binding the default is still attachment-only; CV_STORAGE=r2 keeps the storage path', async () => {
  const w = await makeWorld();
  seedJob(w, { id: 'ie:strat:1' });
  assert.equal((await w.fetch(applyRequest({ job_id: 'ie:strat:1', email: 'a@example.ie' }, { cv: PDF_BYTES }))).status, 201);
  assert.equal(w.r2.objects.size, 0, 'attach (default): nothing persisted');
  w.env.CV_STORAGE = 'r2';
  assert.equal((await w.fetch(applyRequest({ job_id: 'ie:strat:1', email: 'b@example.ie' }, { cv: PDF_BYTES, ip: '198.51.100.7' }))).status, 201);
  assert.equal(w.r2.objects.size, 1, 'r2 flag + binding: stored as before');
});

test('R3-1: oversize and bad-type CVs are refused without R2 too; nothing stored', async () => {
  const w = await makeWorld({ MAX_CV_BYTES: '1000' });
  delete w.env.CVS;
  seedJob(w, { id: 'ie:strat:1' });
  const big = new Uint8Array(1001);
  big.set(PDF_BYTES);
  const over = await w.fetch(applyRequest({ job_id: 'ie:strat:1', email: 'a@example.ie' }, { cv: big, ip: '198.51.100.1' }));
  assert.equal(over.status, 413);
  assert.equal((await over.json()).error, 'cv_too_large');
  const exe = await w.fetch(applyRequest({ job_id: 'ie:strat:1', email: 'b@example.ie' }, { cv: new TextEncoder().encode('MZ\x90\x00 not a cv'), cvName: 'cv.pdf', ip: '198.51.100.2' }));
  assert.equal(exe.status, 415);
  assert.equal((await exe.json()).error, 'cv_type');
  assert.equal(w.db.q('SELECT COUNT(*) AS n FROM applications')[0].n, 0);
});

test('R3-1: DRY_RUN logs CV metadata only, never its content; no mail transport call', async () => {
  const w = await makeWorld();
  seedJob(w, { id: 'ie:strat:1' });
  const [r, lines] = await captureLogs(() => w.fetch(applyRequest({ job_id: 'ie:strat:1' }, { cv: SECRET_PDF })));
  assert.equal(r.status, 201);
  assert.equal(w.mail.calls.length, 0);
  const all = lines.join('\n');
  assert.ok(!all.includes(MARKER), 'CV content never logged');
  assert.ok(!all.includes(Buffer.from(SECRET_PDF).toString('base64').slice(0, 24)), 'nor its base64');
  const meta = lines.find((l) => l.startsWith('apply: cv'));
  assert.ok(meta, 'one metadata line');
  const m = JSON.parse(meta.slice('apply: cv '.length));
  assert.deepEqual(m, { site: 'ie', type: 'pdf', bytes: SECRET_PDF.length, storage: 'attach', dry_run: true });
  assert.ok(!all.includes('aoife@example.ie'), 'no applicant PII in logs either');
});

test('R3-1: a mocked live send carries the CV as an attachment (base64 of the exact bytes); nothing stored', async () => {
  const w = await makeWorld({ DRY_RUN: '0', LIVE_CONFIRM: 'send-applications' });
  seedJob(w, { id: 'ie:strat:1' });
  const [r, lines] = await captureLogs(() => w.fetch(applyRequest({ job_id: 'ie:strat:1' }, { cv: SECRET_PDF })));
  assert.equal(r.status, 201);
  assert.equal((await r.json()).delivery, 'sent');
  assert.equal(w.mail.calls.length, 1);
  const p = w.mail.calls[0].payload;
  assert.equal(p.attachments.length, 1);
  assert.equal(p.attachments[0].filename, 'cv.pdf');
  assert.equal(p.attachments[0].content, Buffer.from(SECRET_PDF).toString('base64'));
  assert.match(p.text, /CV attached\./);
  assert.equal(w.r2.objects.size, 0);
  assert.ok(!lines.join('\n').includes(MARKER));
});

test('R3-1: a failed live send of a CV application answers 502 delivery_failed and frees the dedupe key (no silent CV loss)', async () => {
  const w = await makeWorld({ DRY_RUN: '0', LIVE_CONFIRM: 'send-applications' });
  seedJob(w, { id: 'ie:strat:1' });
  w.mail.ok = false;
  const r = await w.fetch(applyRequest({ job_id: 'ie:strat:1' }, { cv: PDF_BYTES }));
  assert.equal(r.status, 502);
  assert.equal((await r.json()).error, 'delivery_failed');
  assert.equal(w.db.q('SELECT COUNT(*) AS n FROM applications')[0].n, 0);
  w.mail.ok = true;
  const again = await w.fetch(applyRequest({ job_id: 'ie:strat:1' }, { cv: PDF_BYTES, ip: '198.51.100.9' }));
  assert.equal(again.status, 201, 'the candidate can send again');
  assert.equal(w.mail.calls.at(-1).payload.attachments.length, 1);
});

test('R3-2: job, list and sector pages on workers.dev answer 301 to the board URL, same path and query', async () => {
  const w = await staging();
  seedJob(w, { id: 'ie:strat:1' });
  for (const path of ['/ie/jobs/1/', '/ie/jobs/', '/ie/jobs/?q=ecolog', '/ie/sectors/ecology-nature-recovery-biodiversity/', '/jobs/', '/uk/jobs/2/', '/sitemap-jobs.xml', '/ie/']) {
    const r = await w.fetch(new Request(`https://${WORKERS}${path}`));
    assert.equal(r.status, 301, path);
    assert.equal(r.headers.get('Location'), `${BOARD_IE}${path}`, path);
  }
  const head = await w.fetch(new Request(`https://${WORKERS}/ie/jobs/1/`, { method: 'HEAD' }));
  assert.equal(head.status, 301);
});

test('R3-2: the API keeps working on workers.dev (jobs, stats, config, apply JSON)', async () => {
  const w = await staging();
  seedJob(w, { id: 'ie:strat:1' });
  const h = { Origin: BOARD_IE };
  assert.equal((await w.fetch(new Request(`https://${WORKERS}/api/jobs?view=board&site=ie`, { headers: h }))).status, 200);
  assert.equal((await w.fetch(new Request(`https://${WORKERS}/api/stats?site=ie`, { headers: h }))).status, 200);
  assert.equal((await w.fetch(new Request(`https://${WORKERS}/api/health`))).status, 200);
  const req = applyRequest({ job_id: '1' }, { host: WORKERS, origin: BOARD_IE });
  const r = await w.fetch(new Request(`https://${WORKERS}/api/apply?site=ie`, req));
  assert.equal(r.status, 201, await r.clone().text());
  assert.match(r.headers.get('Content-Type'), /application\/json/);
});

test('R3-2: a board host itself (production apex or www) is never redirected', async () => {
  const w = await makeWorld({ CANONICAL_ORIGIN_IE: 'https://www.greenjobs.ie', CANONICAL_ORIGIN_UK: 'https://www.greenjobs.co.uk' });
  seedJob(w, { id: 'ie:strat:1' });
  for (const host of ['greenjobs.ie', 'www.greenjobs.ie']) {
    assert.equal((await w.fetch(new Request(`https://${host}/ie/jobs/1/`))).status, 200, host);
  }
  const w2 = await makeWorld(); // no canonical origin configured: the request host is the board
  seedJob(w2, { id: 'ie:strat:1' });
  assert.equal((await w2.fetch(new Request('https://greenjobs.ie/ie/jobs/1/'))).status, 200);
});

const htmlPost = (fields, o = {}) => {
  const base = applyRequest(fields, { host: WORKERS, origin: BOARD_IE, ...o });
  const headers = new Headers(base.headers);
  headers.set('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8');
  return new Request(`https://${WORKERS}/api/apply?site=ie`, { method: 'POST', body: base.body, headers, duplex: 'half' });
};

test('R3-2: a non-JS form post (Accept: text/html) gets the site HTML page, success and error, never raw JSON', async () => {
  const w = await staging();
  seedJob(w, { id: 'ie:strat:1' });
  const ok = await w.fetch(htmlPost({ job_id: '1' }));
  assert.equal(ok.status, 201);
  assert.match(ok.headers.get('Content-Type'), /^text\/html/);
  const page = await ok.text();
  assert.match(page, /<h1>Application received<\/h1>/);
  assert.match(page, new RegExp(`href="${BOARD_IE}/css/styles\\.css`), 'styled from the board origin');
  assert.doesNotMatch(page, /"status":"received"|\{"error"/);
  const bad = await w.fetch(htmlPost({ job_id: '1', ts: undefined, email: 'z@example.ie' }, { ip: '198.51.100.30' }));
  assert.equal(bad.status, 400);
  assert.match(bad.headers.get('Content-Type'), /^text\/html/);
  const bt = await bad.text();
  assert.match(bt, /<h1>Not sent<\/h1>/);
  assert.match(bt, /reload the job page/);
  assert.doesNotMatch(bt, /invalid_ts|\{"error"/);
  // the alert sign-up form posted without JS: HTML too
  const a = new Request(`https://${WORKERS}/api/alerts?site=ie`, { method: 'POST', headers: { Accept: 'text/html', Origin: BOARD_IE, 'Content-Type': 'application/x-www-form-urlencoded' }, body: 'email=x%40example.ie' });
  const ar = await w.fetch(a);
  assert.match(ar.headers.get('Content-Type'), /^text\/html/);
  assert.doesNotMatch(await ar.text(), /\{"error"/);
});

test('R3-2: fetch() from the page (Accept */*) still gets JSON', async () => {
  const w = await staging();
  seedJob(w, { id: 'ie:strat:1' });
  const base = applyRequest({ job_id: '1' }, { host: WORKERS, origin: BOARD_IE });
  const r = await w.fetch(new Request(`https://${WORKERS}/api/apply?site=ie`, { method: 'POST', body: base.body, headers: { ...Object.fromEntries(base.headers), Accept: '*/*' }, duplex: 'half' }));
  assert.equal(r.status, 201);
  assert.equal((await r.json()).status, 'received');
});
