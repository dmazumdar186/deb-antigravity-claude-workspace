// Cross-stream gaps closed at integration (2026-11-20): every check here fires on the broken shape it guards.
//   b  alert / newsletter mails link to the real job-page scheme /ie/jobs/<slug>/, /uk/jobs/<slug>/
//   c  GET /api/health: no auth, no secrets, release version + D1 reachability (staging smoke reads it)
//   d  Cloudflare Access service tokens (CF-Access-Client-Id/Secret -> JWT with common_name) reach the import
//      and smoke paths only; staff JWTs keep working; an unlisted token, or any other path, is refused

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { PDF_BYTES, adminRequest, applyRequest, makeWorld, seedJob, signToken, validJobBody, workerModule } from './helpers.mjs';

const SVC = 'smoke-0123abcd.access';
const svcClaims = (cn = SVC) => ({ email: undefined, sub: '', common_name: cn });

// ------------------------------------------------------------------ b. mail links

test('b: alert digest + newsletter job links use /{site}/jobs/<slug>/ (never the dead /jobs/?id=)', async () => {
  const core = await workerModule('listmail/core.js');
  const alerts = await workerModule('listmail/alerts.js');
  const ie = core.board({}, 'ie');
  const uk = core.board({ CANONICAL_ORIGIN_UK: 'https://www.greenjobs.co.uk' }, 'uk');
  assert.equal(ie.jobUrl('ie:strat:11513670'), 'https://greenjobs.ie/ie/jobs/11513670/');
  assert.equal(ie.jobUrl('ie:gj:3f1c2b'), 'https://greenjobs.ie/ie/jobs/gj-3f1c2b/');
  assert.equal(ie.jobUrl('ie:gaia:4512'), 'https://greenjobs.ie/ie/jobs/gaia-4512/');
  assert.equal(uk.jobUrl('uk:strat:900'), 'https://www.greenjobs.co.uk/uk/jobs/900/');
  // a non-https or path-carrying override is ignored (no open redirect into mail)
  assert.equal(core.board({ CANONICAL_ORIGIN_IE: 'http://evil.example' }, 'ie').base, 'https://greenjobs.ie');
  const mail = await alerts.digestEmail('k'.repeat(40), ie, {
    to: 'a@example.ie', subId: 'ie:alert:1', query: { keywords: 'wind' },
    jobs: [{ id: 'ie:strat:11513670', title: 'Wind Analyst', employer: 'Acme', location: 'Cork' }],
  });
  const blob = JSON.stringify(mail);
  assert.match(blob, /https:\/\/greenjobs\.ie\/ie\/jobs\/11513670\//);
  assert.doesNotMatch(blob, /\/jobs\/\?id=/);
});

test('b: the linked page exists: the Worker serves the slug the mail links to', async () => {
  const core = await workerModule('listmail/core.js');
  const w = await makeWorld();
  seedJob(w, { id: 'ie:strat:4242', title: 'Hydrologist' });
  w.db.sqlite.prepare(`INSERT INTO job_facets (job_id, sectors_json, taxonomy_version, set_by, updated_at) VALUES ('ie:strat:4242', '["Water & flood"]', 1, 'import', 't')`).run();
  const url = new URL(core.board({}, 'ie').jobUrl('ie:strat:4242'));
  const r = await w.fetch(new Request(`https://greenjobs.ie${url.pathname}`));
  assert.equal(r.status, 200);
  assert.match(await r.text(), /Hydrologist/);
});

// ------------------------------------------------------------------ c. health

test('c: GET /api/health: 200 without auth, version + D1 reachability, no secrets, never cached', async () => {
  const w = await makeWorld({ RELEASE_SHA: 'abc1234def5678', CF_VERSION_METADATA: { id: 'ver-1' } });
  const r = await w.fetch(new Request('https://greenjobs.ie/api/health'));
  assert.equal(r.status, 200);
  assert.equal(r.headers.get('Cache-Control'), 'no-store');
  assert.equal(r.headers.get('X-Content-Type-Options'), 'nosniff');
  const b = await r.json();
  assert.equal(b.ok, true);
  assert.deepEqual(b.version, { release: 'abc1234def5678', worker_version: 'ver-1' });
  assert.equal(b.d1.reachable, true);
  assert.equal(b.d1.migrated, true);
  const text = JSON.stringify(b);
  for (const k of ['build-token-for-tests-only', 'dummy-not-a-real-key', 'keith@greenjobs.ie', 'aud-test']) assert.ok(!text.includes(k), k);
  // any host (a staging workers.dev host need not be in HOST_SITE_MAP), and a junk RELEASE_SHA is not echoed
  const w2 = await makeWorld({ RELEASE_SHA: '<script>' });
  const r2 = await w2.fetch(new Request('https://unknown.example/api/health'));
  assert.equal(r2.status, 200);
  assert.equal((await r2.json()).version.release, null);
});

test('c: GET /api/health answers 503 {ok:false} when D1 is unreachable', async () => {
  const w = await makeWorld();
  w.env.DB = { prepare() { throw new Error('D1_ERROR: network'); } };
  const r = await w.fetch(new Request('https://greenjobs.ie/api/health'));
  assert.equal(r.status, 503);
  const b = await r.json();
  assert.equal(b.ok, false);
  assert.equal(b.d1.reachable, false);
  assert.doesNotMatch(JSON.stringify(b), /D1_ERROR/);
  assert.equal((await w.fetch(new Request('https://greenjobs.ie/api/health', { method: 'POST' }))).status, 405);
});

// ------------------------------------------------------------------ d. Access service tokens

test('d: an allow-listed service token runs the smoke flow: create, read back, close', async () => {
  const w = await makeWorld({ ACCESS_SERVICE_TOKEN_IDS: `other-id,${SVC}` });
  const create = await w.fetch(await adminRequest('POST', '/api/admin/jobs', { body: validJobBody(), claims: svcClaims() }));
  assert.equal(create.status, 201, await create.clone().text());
  const { id } = await create.json();
  const get = await w.fetch(await adminRequest('GET', `/api/admin/jobs/${id}`, { claims: svcClaims() }));
  assert.equal(get.status, 200);
  const close = await w.fetch(await adminRequest('POST', `/api/admin/jobs/${id}/close`, { body: {}, claims: svcClaims() }));
  assert.equal(close.status, 200);
  assert.equal((await close.json()).status, 'closed');
  const actors = w.db.q('SELECT DISTINCT actor FROM audit_log ORDER BY actor').map((r) => r.actor);
  assert.deepEqual(actors, [`service:${SVC}`]);
});

test('d: service tokens are scoped: console, list, edit, review, newsletter and employer paths are 403', async () => {
  const w = await makeWorld({ ACCESS_SERVICE_TOKEN_IDS: SVC, NEWSLETTER_ENABLED: '1', EMPLOYER_POSTING_ENABLED: '1' });
  seedJob(w, { id: 'ie:strat:777' });
  const denied = [
    ['GET', '/admin/'], ['GET', '/api/admin/jobs'], ['GET', '/api/admin/review'], ['GET', '/admin/review'],
    ['PUT', '/api/admin/jobs/ie:strat:777', { version: 1, title: 'Hijacked title' }], ['GET', '/api/admin/newsletters'],
    ['GET', '/api/admin/list-measures'], ['POST', '/api/admin/review/ie:strat:777/approve', {}],
  ];
  for (const [m, p, body] of denied) {
    const r = await w.fetch(await adminRequest(m, p, { body, claims: svcClaims() }));
    assert.equal(r.status, 403, `${m} ${p}`);
  }
  const emp = await w.fetch(await adminRequest('GET', '/api/employer/jobs', { claims: svcClaims() }));
  assert.equal(emp.status, 403);
  assert.equal(w.db.q("SELECT title FROM jobs WHERE id='ie:strat:777'")[0].title, 'Senior Wind Engineer');
});

test('d: an unlisted service token, an empty allow-list, a forged token and a token without identity are refused', async () => {
  const w = await makeWorld({ ACCESS_SERVICE_TOKEN_IDS: SVC });
  assert.equal((await w.fetch(await adminRequest('POST', '/api/admin/jobs', { body: validJobBody(), claims: svcClaims('not-listed') }))).status, 403);
  const empty = await makeWorld({ ACCESS_SERVICE_TOKEN_IDS: '' });
  assert.equal((await empty.fetch(await adminRequest('POST', '/api/admin/jobs', { body: validJobBody(), claims: svcClaims() }))).status, 403);
  const forged = await signToken(svcClaims(), { wrongKey: true });
  assert.equal((await w.fetch(await adminRequest('POST', '/api/admin/jobs', { body: validJobBody(), token: forged }))).status, 401);
  assert.equal((await w.fetch(await adminRequest('POST', '/api/admin/jobs', { body: validJobBody(), claims: { email: undefined } }))).status, 401);
  assert.equal(w.db.q('SELECT COUNT(*) AS n FROM jobs')[0].n, 0);
});

test('d: staff JWTs still work everywhere; a staff email cannot be smuggled as common_name', async () => {
  const w = await makeWorld({ ACCESS_SERVICE_TOKEN_IDS: SVC });
  assert.equal((await w.fetch(await adminRequest('GET', '/admin/'))).status, 200);
  assert.equal((await w.fetch(await adminRequest('POST', '/api/admin/jobs', { body: validJobBody() }))).status, 201);
  const smuggled = await w.fetch(await adminRequest('GET', '/admin/', { claims: { email: undefined, common_name: 'keith@greenjobs.ie' } }));
  assert.equal(smuggled.status, 401); // '@' is not a service-token id shape
});

function importReq(body, headers = {}) {
  return new Request('https://greenjobs.ie/api/admin/import', {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'CF-Connecting-IP': '198.51.100.9', ...headers }, body: JSON.stringify(body),
  });
}

test('d: /api/admin/import accepts a service token or a staff JWT as well as BUILD_TOKEN; a bad JWT is not retried as bearer', async () => {
  const { TAXONOMY } = await workerModule('render/lib.js');
  const body = { source: 'gaia', site: 'ie', dry_run: true, close_missing: false, taxonomy: { version: `frozen-${TAXONOMY.version}`, sectors: TAXONOMY.sectors.map((s) => s.name) }, jobs: [], links: [] };
  const w = await makeWorld({ ACCESS_SERVICE_TOKEN_IDS: SVC });
  const svc = await w.fetch(importReq(body, { 'Cf-Access-Jwt-Assertion': await signToken(svcClaims()) }));
  assert.equal(svc.status, 200, await svc.clone().text());
  assert.equal((await svc.json()).dry_run, true);
  assert.equal((await w.fetch(importReq(body, { 'Cf-Access-Jwt-Assertion': await signToken({}) }))).status, 200);
  assert.equal((await w.fetch(importReq(body, { Authorization: 'Bearer build-token-for-tests-only' }))).status, 200);
  const bad = await w.fetch(importReq(body, { 'Cf-Access-Jwt-Assertion': await signToken(svcClaims('not-listed')), Authorization: 'Bearer build-token-for-tests-only' }));
  assert.equal(bad.status, 403);
  assert.equal((await w.fetch(importReq(body))).status, 401);
});

test('d: the service scope is exactly the smoke paths (unit)', async () => {
  const { serviceAllowed } = await workerModule('index.js');
  assert.equal(serviceAllowed('POST', '/api/admin/jobs'), true);
  assert.equal(serviceAllowed('GET', '/api/admin/jobs/ie:gj:1'), true);
  assert.equal(serviceAllowed('POST', '/api/admin/jobs/ie:gj:1/close'), true);
  for (const [m, p] of [['GET', '/api/admin/jobs'], ['PUT', '/api/admin/jobs/ie:gj:1'], ['GET', '/admin/'], ['POST', '/api/admin/review/x/approve'], ['POST', '/api/admin/newsletters']]) {
    assert.equal(serviceAllowed(m, p), false, `${m} ${p}`);
  }
});

test('staging without R2 (eye r3 R3-1): an apply carrying a CV is accepted, attached to the mail, nothing stored', async () => {
  const w = await makeWorld();
  delete w.env.CVS;
  seedJob(w, { id: 'ie:strat:900', apply_email: 'hr@example.ie' });
  const form = (cv, email) => applyRequest({ job_id: 'ie:strat:900', email }, { cv: cv ? PDF_BYTES : undefined, origin: 'https://greenjobs.ie', ip: '198.51.100.20' });
  const r = await w.fetch(form(true, 'a@example.ie'));
  assert.equal(r.status, 201, await r.clone().text());
  assert.equal(w.db.q('SELECT cv_key FROM applications')[0].cv_key, null);
  const ok = await w.fetch(form(false, 'b@example.ie'));
  assert.equal(ok.status, 201, await ok.clone().text());
});

// ------------------------------------------------------------------ smoke contract (environments.json)

test('smoke contract: /api/stats live_jobs equals the paginated /api/jobs count; closed job API answers 410', async () => {
  const w = await makeWorld();
  seedJob(w, { id: 'ie:strat:1' });
  seedJob(w, { id: 'ie:strat:2' });
  seedJob(w, { id: 'ie:strat:3', status: 'closed' });
  seedJob(w, { id: 'ie:strat:4', status: 'draft' });
  const origin = { Origin: 'https://greenjobs.ie' };
  const stats = await (await w.fetch(new Request('https://greenjobs.ie/api/stats', { headers: origin }))).json();
  const list = await (await w.fetch(new Request('https://greenjobs.ie/api/jobs?limit=1000', { headers: origin }))).json();
  assert.equal(stats.live_jobs, 2);
  assert.equal(list.jobs.length, stats.live_jobs);
  assert.equal((await w.fetch(new Request('https://greenjobs.ie/api/jobs/ie:strat:3', { headers: origin }))).status, 410);
  assert.equal((await w.fetch(new Request('https://greenjobs.ie/api/jobs/ie:strat:4', { headers: origin }))).status, 404);
});
