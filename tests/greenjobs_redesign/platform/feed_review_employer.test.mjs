// Feed import (POST /api/admin/import), sector review queue (/admin/review) and employer self-posting
// (/api/employer/*), offline on node:sqlite with the real schema.sql + migration 0003. Every guard has a
// positive test: it is shown to fire, not only to stay quiet.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { REPO, adminRequest, makeWorld, seedJob, signToken, validJobBody, workerModule } from './helpers.mjs';

const D1 = resolve(REPO, 'deliverables/greenjobs_migration_2026-11-06/build/d1');
const MIG3 = readFileSync(resolve(D1, 'migrations/0003_classifier_feed_review_employers.sql'), 'utf8');
const PKG = resolve(REPO, 'execution/gtm_client_workflows/greenjobs_redesign');
const FIX = resolve(REPO, 'tests/greenjobs_redesign/fixtures/gaia_d1');
const TOKEN = 'build-token-for-tests-only';
const TAX = JSON.parse(readFileSync(resolve(PKG, 'platform_worker/src/taxonomy.json'), 'utf8'));
const TAX_SECTORS = TAX.sectors.map((s) => s.name);

async function world(env = {}) {
  const w = await makeWorld(env);
  w.db.sqlite.exec(MIG3);
  return w;
}

const norm = (s) => s.replace(/\s+/g, ' ').trim();

// ------------------------------------------------------------------ one SQL source of truth

test('sql_0003.js holds exactly the statements of upserts_0003.sql', async () => {
  const Q = await workerModule('sql_0003.js');
  const text = readFileSync(resolve(D1, 'upserts_0003.sql'), 'utf8');
  const parts = text.split(/^-- name: (\w+)\s*$/m);
  const names = [];
  for (let i = 1; i < parts.length; i += 2) {
    const body = parts[i + 1].split('\n').filter((l) => !l.trim().startsWith('--')).join('\n').trim().replace(/;$/, '');
    names.push(parts[i]);
    assert.equal(norm(Q[parts[i].toUpperCase()]), norm(body), parts[i]);
  }
  assert.equal(Object.keys(Q).length, names.length);
});

test('migration 0003 is idempotent and additive; job_facets is 0002\'s one table, no taxonomy_terms copy', async () => {
  const w = await world();
  w.db.sqlite.exec(MIG3);
  const t = w.db.q(`SELECT name FROM sqlite_master WHERE type='table' AND name IN ('job_facets','job_review','job_links','employer_accounts','taxonomy_terms') ORDER BY name`);
  assert.deepEqual(t.map((r) => r.name), ['employer_accounts', 'job_facets', 'job_links', 'job_review']);
  const cols = w.db.q('PRAGMA table_info(job_facets)').map((c) => c.name);
  for (const c of ['sectors_json', 'level', 'search_text', 'source_sectors_json', 'sector_confidence', 'sector_method', 'set_by']) assert.ok(cols.includes(c), c);
  assert.ok(!/CREATE TABLE[^;]*job_facets/i.test(MIG3) && !/taxonomy_terms\s*\(/i.test(MIG3));
});

test('import: a batch classified with any vocabulary but taxonomy.json is refused (one source of truth)', async () => {
  const w = await world({ FEED_IMPORT_ENABLED: '1' });
  const r = await w.fetch(importReq(batch({ taxonomy: { version: 'test-1', sectors: TAX_SECTORS } })));
  assert.equal(r.status, 400);
  assert.equal((await r.json()).field, 'taxonomy.version');
  const r2 = await w.fetch(importReq(batch({ taxonomy: { version: `frozen-${TAX.version}`, sectors: TAX_SECTORS.slice(1) } })));
  assert.equal(r2.status, 400);
  const r3 = await w.fetch(importReq(batch({ jobs: [job(101, { facets: { ...job(101).facets, taxonomy_version: TAX.version + 1 } })] })));
  assert.equal((await r3.json()).field, 'jobs[0].facets.taxonomy_version');
  const r4 = await w.fetch(importReq(batch({ jobs: [job(101, { facets: { ...job(101).facets, sectors: ['Moon mining'] } })] })));
  assert.equal((await r4.json()).field, 'jobs[0].facets.sectors');
  assert.equal(w.db.q('SELECT COUNT(*) AS n FROM jobs')[0].n, 0);
});

// ------------------------------------------------------------------ feed import

function batch(over = {}) {
  return {
    source: 'gaia', site: 'ie', dry_run: false,
    taxonomy: { version: `frozen-${TAX.version}`, sectors: TAX_SECTORS },
    jobs: [job(101), job(102, { status: 'draft', review: { reason: 'low confidence', suggested: ['Water & flood'], confidence: 0.4, hold: 1 } })],
    links: [{ source_id: 'gaia:103', board_job_id: 'ie:strat:11500001', method: 'rule' }],
    ...over,
  };
}

function job(n, over = {}) {
  return {
    source_id: `gaia:${n}`, title: `Senior Ecologist ${n}`, location: 'Cork', region: 'Cork', job_type: 'Permanent', sal_text: null,
    sectors: ['Ecology, nature recovery & biodiversity'], summary: 'Habitat surveys.', description: 'Lead habitat and species surveys across Munster.',
    apply_mode: 'link', apply_email: null, apply_url: `https://gaiatalent.com/job/${n}/`, status: 'live', posted_at: '2026-11-10T09:00:00Z',
    closing_at: null, review: null,
    facets: { sectors: over.status === 'draft' ? ['Water & flood'] : ['Ecology, nature recovery & biodiversity'], regions: ['Cork'], job_type: 'Permanent',
      workplace: 'hybrid', contract: ['permanent'], loc_class: 'ie', level: 'Senior/Principal', is_agency: 1, salary_display: null, unverified_cur: 0,
      search_text: 'Lead habitat and species surveys across Munster.', source_sectors: [], sector_confidence: 0.95, sector_method: 'keyword', taxonomy_version: TAX.version },
    ...over,
  };
}

function importReq(body, o = {}) {
  const headers = new Headers({ 'Content-Type': o.contentType || 'application/json', 'CF-Connecting-IP': '198.51.100.9' });
  if (o.auth !== null) headers.set('Authorization', o.auth || `Bearer ${TOKEN}`);
  return new Request(`https://${o.host || 'greenjobs.ie'}/api/admin/import`, { method: 'POST', headers, body: JSON.stringify(body) });
}

test('import: bearer token required (no token, wrong token, no Access JWT path)', async () => {
  const w = await world({ FEED_IMPORT_ENABLED: '1' });
  assert.equal((await w.fetch(importReq(batch(), { auth: null }))).status, 401);
  assert.equal((await w.fetch(importReq(batch(), { auth: 'Bearer nope' }))).status, 401);
  const noTokenEnv = await world({ FEED_IMPORT_ENABLED: '1', BUILD_TOKEN: '' });
  assert.equal((await noTokenEnv.fetch(importReq(batch()))).status, 401);
  assert.equal(w.db.q('SELECT COUNT(*) AS n FROM jobs')[0].n, 0);
});

test('import: dry run by default, live writes need FEED_IMPORT_ENABLED=1', async () => {
  const w = await world();
  const dry = await w.fetch(importReq(batch({ dry_run: undefined })));
  assert.equal(dry.status, 200);
  const d = await dry.json();
  assert.equal(d.dry_run, true);
  assert.deepEqual(d.plan, { insert: 2, update: 0, close: 0, held: 1, live: 1, links: 1 });
  const off = await w.fetch(importReq(batch()));
  assert.equal(off.status, 403);
  assert.equal((await off.json()).error, 'import_disabled');
  assert.equal(w.db.q('SELECT COUNT(*) AS n FROM jobs')[0].n, 0);
  assert.equal(w.db.q('SELECT COUNT(*) AS n FROM job_facets')[0].n, 0);
});

test('import: live write is idempotent, holds review jobs as draft, links instead of listing', async () => {
  const w = await world({ FEED_IMPORT_ENABLED: '1' });
  const r = await w.fetch(importReq(batch()));
  assert.equal(r.status, 200);
  const snap = () => w.db.q('SELECT id, status, version, sectors_json FROM jobs ORDER BY id');
  const first = snap();
  assert.deepEqual(first.map((x) => [x.id, x.status]), [['ie:gaia:101', 'live'], ['ie:gaia:102', 'draft']]);
  assert.equal(w.db.q(`SELECT COUNT(*) AS n FROM job_review WHERE status='queued' AND hold=1`)[0].n, 1);
  assert.equal(w.db.q('SELECT board_job_id FROM job_links')[0].board_job_id, 'ie:strat:11500001');
  const again = await (await w.fetch(importReq(batch()))).json();
  assert.deepEqual(again.plan, { insert: 0, update: 2, close: 0, held: 1, live: 1, links: 1 });
  assert.deepEqual(snap(), first); // no version bump on an unchanged batch
  assert.equal(w.db.q(`SELECT COUNT(*) AS n FROM audit_log WHERE action='import.batch'`)[0].n, 1); // replay: one audit row
});

test('import: validation guards fire', async () => {
  const w = await world({ FEED_IMPORT_ENABLED: '1' });
  const bad = async (b, field) => {
    const r = await w.fetch(importReq(b));
    assert.equal(r.status, 400, field);
    assert.equal((await r.json()).field, field);
  };
  await bad(batch({ source: 'broadbean' }), 'source');
  await bad(batch({ site: 'fr' }), 'site');
  await bad(batch({ jobs: [job(1, { status: 'live', review: { reason: 'x', suggested: [], confidence: 0.2, hold: 1 } })] }), 'jobs[0].status');
  await bad(batch({ jobs: [job(1, { sectors: ['Made Up Sector'] })] }), 'jobs[0].sectors');
  await bad(batch({ jobs: [job(1, { apply_url: 'javascript:alert(1)' })] }), 'jobs[0].apply_url');
  await bad(batch({ jobs: [job(1, { apply_mode: 'email', apply_url: null, apply_email: 'not an email' })] }), 'jobs[0].apply_email');
  await bad(batch({ jobs: [job(1, { title: 'x' })] }), 'jobs[0].title');
  await bad(batch({ jobs: [job(1, { description: 'short' })] }), 'jobs[0].description');
  await bad(batch({ jobs: [job(1, { source_id: 'gaia:abc' })] }), 'jobs[0].source_id');
  await bad(batch({ jobs: [job(1), job(1)] }), 'jobs[1].source_id');
  await bad(batch({ jobs: [job(1, { facets: { ...job(1).facets, workplace: 'moon' } })] }), 'jobs[0].facets.workplace');
  await bad(batch({ links: [{ source_id: 'gaia:103', board_job_id: 'uk:strat:1', method: 'rule' }] }), 'links[0].board_job_id');
  await bad(batch({ links: [{ source_id: 'gaia:101', board_job_id: 'ie:strat:1', method: 'rule' }] }), 'links[0].source_id');
  await bad(batch({ jobs: Array.from({ length: 501 }, (_, i) => job(i + 1)) }), 'jobs');
  assert.equal(w.db.q('SELECT COUNT(*) AS n FROM jobs')[0].n, 0);
  const tooBig = await w.fetch(new Request('https://greenjobs.ie/api/admin/import', {
    method: 'POST', headers: { Authorization: `Bearer ${TOKEN}`, 'Content-Type': 'application/json', 'Content-Length': String(9 * 1024 * 1024) }, body: '{}',
  }));
  assert.equal(tooBig.status, 413);
  assert.equal((await w.fetch(importReq(batch(), { contentType: 'text/plain' }))).status, 415);
});

test('import: closes jobs that left the feed, refuses an empty batch and a mass close', async () => {
  const w = await world({ FEED_IMPORT_ENABLED: '1' });
  await w.fetch(importReq(batch({ jobs: [job(1), job(2), job(3), job(4)], links: [] })));
  const empty = await w.fetch(importReq(batch({ jobs: [], links: [] })));
  assert.equal(empty.status, 409);
  assert.equal((await empty.json()).error, 'empty_batch');
  const mass = await w.fetch(importReq(batch({ jobs: [job(1)], links: [] })));
  assert.equal(mass.status, 409);
  assert.equal((await mass.json()).error, 'mass_close_refused');
  assert.equal(w.db.q(`SELECT COUNT(*) AS n FROM jobs WHERE status='closed'`)[0].n, 0);
  const ok = await (await w.fetch(importReq(batch({ jobs: [job(1), job(2), job(3)], links: [] })))).json();
  assert.equal(ok.plan.close, 1);
  assert.deepEqual(w.db.q(`SELECT id, status FROM jobs WHERE id='ie:gaia:4'`)[0], { id: 'ie:gaia:4', status: 'closed' });
  assert.equal(w.db.q('SELECT COUNT(*) AS n FROM jobs')[0].n, 4); // closed, never deleted
  // a closed job stays closed when it comes back
  await w.fetch(importReq(batch({ jobs: [job(1), job(2), job(3), job(4)], links: [] })));
  assert.equal(w.db.q(`SELECT status FROM jobs WHERE id='ie:gaia:4'`)[0].status, 'closed');
  // allow_mass_close is an explicit override
  const forced = await w.fetch(importReq(batch({ jobs: [job(1)], links: [], allow_mass_close: true })));
  assert.equal(forced.status, 200);
});

test('import: the Python emitter (SQL) and the API converge on the same rows', async () => {
  const dir = mkdtempSync(join(tmpdir(), 'gj-parity-'));
  try {
    execFileSync('python3', [resolve(PKG, 'gaia_d1_sync.py'), '--feed', resolve(FIX, 'feed_small.json'), '--taxonomy', resolve(PKG, 'platform_worker/src/taxonomy.json'),
      '--as-of', '2026-11-20', '--emit-json', join(dir, 'b.json'), '--emit-sql', join(dir, 'b.sql')], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
    const payloads = JSON.parse(readFileSync(join(dir, 'b.json'), 'utf8'));
    const api = await world({ FEED_IMPORT_ENABLED: '1' });
    for (const site of ['ie', 'uk']) {
      const r = await api.fetch(importReq({ ...payloads[site], dry_run: false }));
      assert.equal(r.status, 200, `${site}: ${await r.clone().text()}`);
    }
    const sql = await world();
    sql.db.sqlite.exec(readFileSync(join(dir, 'b.sql'), 'utf8'));
    const cols = `id, site, source, source_id, employer_id, title, location, region, job_type, sal_text, sectors_json, summary, description,
      apply_mode, apply_email, apply_url, status, posted_at, closing_at, version`;
    for (const q of [`SELECT ${cols} FROM jobs ORDER BY id`, 'SELECT job_id, reason, suggested_json, confidence, hold, status FROM job_review ORDER BY job_id',
      'SELECT site, feed_source_id, board_job_id, method FROM job_links ORDER BY 1, 2, 3',
      `SELECT job_id, sectors_json, regions_json, job_type, workplace, contract_json, loc_class, level, is_agency, salary_display, unverified_cur,
        taxonomy_version, set_by, search_text, source_sectors_json, sector_confidence, sector_method FROM job_facets ORDER BY job_id`]) {
      assert.deepEqual(api.db.q(q), sql.db.q(q), q.slice(0, 60));
    }
    assert.ok(api.db.q('SELECT COUNT(*) AS n FROM jobs')[0].n >= 4);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

// ------------------------------------------------------------------ review queue

async function reviewWorld() {
  const w = await world({ FEED_IMPORT_ENABLED: '1' });
  await w.fetch(importReq(batch()));
  return w;
}

test('review: staff list the queue with suggestions and the vocabulary', async () => {
  const w = await reviewWorld();
  const r = await w.fetch(await adminRequest('GET', '/api/admin/review'));
  assert.equal(r.status, 200);
  const d = await r.json();
  assert.equal(d.items.length, 1);
  assert.deepEqual(d.items[0].suggested, ['Water & flood']);
  assert.equal(d.items[0].hold, true);
  assert.deepEqual(d.sectors, [...TAX_SECTORS].sort()); // the vocabulary is taxonomy.json, not a D1 copy
  const page = await w.fetch(await adminRequest('GET', '/admin/review'));
  assert.equal(page.status, 200);
  const html = await page.text();
  assert.ok(html.includes('/admin/review.js') && !/<script>[^<]/.test(html));
  assert.match(page.headers.get('Content-Security-Policy'), /default-src 'self'/);
  assert.equal((await w.fetch(await adminRequest('GET', '/admin/review.js'))).status, 200);
  assert.equal((await w.fetch(await adminRequest('GET', '/api/admin/review', { claims: { email: 'stranger@example.com' } }))).status, 403);
  assert.equal((await w.fetch(await adminRequest('GET', '/api/admin/review', { token: null }))).status, 401);
});

test('review: one click approves the suggestion and takes the held job live; replay is a no-op', async () => {
  const w = await reviewWorld();
  const idem = crypto.randomUUID();
  const r = await w.fetch(await adminRequest('POST', '/api/admin/review/ie:gaia:102/approve', { body: {}, idem }));
  assert.equal(r.status, 200);
  const d = await r.json();
  assert.equal(d.status, 'approved');
  assert.equal(d.job_status, 'live');
  assert.deepEqual(w.db.q(`SELECT status, sectors_json FROM jobs WHERE id='ie:gaia:102'`)[0], { status: 'live', sectors_json: '["Water & flood"]' });
  assert.equal(w.db.q(`SELECT decided_by FROM job_review WHERE job_id='ie:gaia:102'`)[0].decided_by, 'keith@greenjobs.ie');
  const again = await (await w.fetch(await adminRequest('POST', '/api/admin/review/ie:gaia:102/approve', { body: { sectors: ['Ecology, nature recovery & biodiversity'] } }))).json();
  assert.equal(again.already_decided, true);
  assert.equal(w.db.q(`SELECT sectors_json FROM jobs WHERE id='ie:gaia:102'`)[0].sectors_json, '["Water & flood"]');
  assert.equal(w.db.q(`SELECT COUNT(*) AS n FROM audit_log WHERE action LIKE 'review.%'`)[0].n, 1);
  // a re-import does not reopen the review nor overwrite the decided sectors
  const changed = batch();
  changed.jobs[1].sectors = ['Ecology, nature recovery & biodiversity'];
  changed.jobs[1].review.suggested = ['Ecology, nature recovery & biodiversity'];
  await w.fetch(importReq(changed));
  assert.deepEqual(w.db.q(`SELECT status, sectors_json FROM jobs WHERE id='ie:gaia:102'`)[0], { status: 'live', sectors_json: '["Water & flood"]' });
  assert.equal(w.db.q(`SELECT status FROM job_review WHERE job_id='ie:gaia:102'`)[0].status, 'approved');
  // ... and the board's facet row (what the job pages render) keeps the decided sectors too
  assert.deepEqual(w.db.q(`SELECT sectors_json, sector_method, set_by FROM job_facets WHERE job_id='ie:gaia:102'`)[0],
    { sectors_json: '["Water & flood"]', sector_method: 'keyword', set_by: 'feed' });
});

test('review: change & approve takes only active vocabulary, 1..3 sectors', async () => {
  const w = await reviewWorld();
  const post = async (sectors) => w.fetch(await adminRequest('POST', '/api/admin/review/ie:gaia:102/approve', { body: { sectors } }));
  assert.equal((await post(['Invented'])).status, 400);
  assert.equal((await post([])).status, 400);
  assert.equal((await post(['a', 'b', 'c', 'd'])).status, 400);
  assert.equal((await post('Water & flood')).status, 400);
  const ok = await post(['Ecology, nature recovery & biodiversity']);
  assert.equal(ok.status, 200);
  assert.equal((await ok.json()).status, 'changed');
  assert.equal(w.db.q(`SELECT sectors_json FROM jobs WHERE id='ie:gaia:102'`)[0].sectors_json, '["Ecology, nature recovery & biodiversity"]');
  assert.deepEqual(w.db.q(`SELECT sectors_json, sector_method FROM job_facets WHERE job_id='ie:gaia:102'`)[0],
    { sectors_json: '["Ecology, nature recovery & biodiversity"]', sector_method: 'staff' });
  // the decided job now renders on the board under the staff's sector
  const page = await w.fetch(new Request('https://greenjobs.ie/ie/jobs/gaia-102/'));
  assert.equal(page.status, 200);
  assert.match(await page.text(), /Ecology, nature recovery &amp; biodiversity/);
});

test('review: closed job is never taken live; CSRF, idempotency key, unknown job and other site are refused', async () => {
  const w = await reviewWorld();
  assert.equal((await w.fetch(await adminRequest('POST', '/api/admin/review/ie:gaia:102/approve', { body: {}, origin: 'https://evil.example' }))).status, 403);
  assert.equal((await w.fetch(await adminRequest('POST', '/api/admin/review/ie:gaia:102/approve', { body: {}, idem: null }))).status, 400);
  assert.equal((await w.fetch(await adminRequest('POST', '/api/admin/review/ie:gaia:999/approve', { body: {} }))).status, 404);
  assert.equal((await w.fetch(await adminRequest('POST', '/api/admin/review/ie:gaia:102/approve', { body: {}, host: 'greenjobs.co.uk' }))).status, 404);
  assert.equal((await w.fetch(await adminRequest('POST', '/api/admin/review/ie:gaia:102/approve', { body: { status: 'live' } }))).status, 400);
  w.db.sqlite.exec(`UPDATE jobs SET status='closed' WHERE id='ie:gaia:102'`);
  const r = await w.fetch(await adminRequest('POST', '/api/admin/review/ie:gaia:102/approve', { body: {} }));
  assert.equal(r.status, 409);
  assert.equal(w.db.q(`SELECT status FROM jobs WHERE id='ie:gaia:102'`)[0].status, 'closed');
  assert.equal(w.db.q(`SELECT status FROM job_review WHERE job_id='ie:gaia:102'`)[0].status, 'queued');
});

// ------------------------------------------------------------------ employer self-posting

const CHM = 'ie:strat:emp-chm';
const MATT = 'ie:strat:emp-matt';

async function employerWorld(env = { EMPLOYER_POSTING_ENABLED: '1' }) {
  const w = await world(env);
  const ts = '2026-11-01T09:00:00Z';
  const emp = w.db.sqlite.prepare(`INSERT INTO employers (id, site, source, source_id, name, name_norm, created_at, updated_at) VALUES (?1, ?2, 'strategies', ?3, ?4, ?5, ?6, ?6)`);
  emp.run(CHM, 'ie', 'emp-chm', 'CHM Recruit', 'chm recruit', ts);
  emp.run(MATT, 'ie', 'emp-matt', 'Mattinson Partnership', 'mattinson partnership', ts);
  emp.run('uk:strat:emp-chm', 'uk', 'emp-chm', 'CHM Recruit', 'chm recruit', ts);
  const acct = w.db.sqlite.prepare(`INSERT INTO employer_accounts (email_norm, employer_id, status, expires_at, created_by, created_at, updated_at) VALUES (?1, ?2, ?3, ?4, 'keith@greenjobs.ie', ?5, ?5)`);
  acct.run('jobs@chmrecruit.example', CHM, 'active', '2027-01-31T23:59:59Z', ts);
  acct.run('posts@mattinson.example', MATT, 'active', null, ts);
  acct.run('old@chmrecruit.example', CHM, 'active', '2026-10-31T23:59:59Z', ts);
  acct.run('off@chmrecruit.example', CHM, 'disabled', null, ts);
  const chmJob = seedJob(w, { id: 'ie:strat:8001' });
  w.db.sqlite.exec(`UPDATE jobs SET employer_id='${CHM}' WHERE id='${chmJob}'`);
  const mattJob = seedJob(w, { id: 'ie:strat:8002' });
  w.db.sqlite.exec(`UPDATE jobs SET employer_id='${MATT}' WHERE id='${mattJob}'`);
  return w;
}

const as = (email, o = {}) => ({ ...o, claims: { email } });
const empReq = (method, path, email, o = {}) => adminRequest(method, path, as(email, o));

test('employer: feature flag off by default -> every employer path is 404', async () => {
  const w = await employerWorld({});
  for (const [m, p] of [['GET', '/employer/'], ['GET', '/api/employer/jobs'], ['POST', '/api/employer/jobs']]) {
    assert.equal((await w.fetch(await empReq(m, p, 'jobs@chmrecruit.example', { body: validJobBody() }))).status, 404, p);
  }
  assert.equal(w.db.q(`SELECT COUNT(*) AS n FROM jobs`)[0].n, 2);
});

test('employer: posts, lists, edits and closes only its own jobs', async () => {
  const w = await employerWorld();
  const c = await w.fetch(await empReq('POST', '/api/employer/jobs', 'jobs@chmrecruit.example', { body: validJobBody({ employer: 'Somebody Else Ltd' }) }));
  assert.equal(c.status, 201);
  const made = await c.json();
  assert.equal(made.employer_id, CHM); // the name in the body is ignored: the account decides the employer
  const row = w.db.q('SELECT employer_id, created_by, source FROM jobs WHERE id = ?1', made.id)[0];
  assert.deepEqual(row, { employer_id: CHM, created_by: 'jobs@chmrecruit.example', source: 'console' });
  const list = await (await w.fetch(await empReq('GET', '/api/employer/jobs', 'jobs@chmrecruit.example'))).json();
  assert.deepEqual(list.jobs.map((j) => j.id).sort(), [made.id, 'ie:strat:8001'].sort());
  const v = w.db.q(`SELECT version FROM jobs WHERE id='ie:strat:8001'`)[0].version;
  const e = await w.fetch(await empReq('PUT', '/api/employer/jobs/ie:strat:8001', 'jobs@chmrecruit.example', { body: { title: 'Senior Wind Engineer II', version: v } }));
  assert.equal(e.status, 200);
  const cl = await w.fetch(await empReq('POST', '/api/employer/jobs/ie:strat:8001/close', 'jobs@chmrecruit.example', { body: {} }));
  assert.equal(cl.status, 200);
  assert.equal(w.db.q(`SELECT status FROM jobs WHERE id='ie:strat:8001'`)[0].status, 'closed');
  const page = await w.fetch(await empReq('GET', '/employer/', 'jobs@chmrecruit.example'));
  assert.equal(page.status, 200);
  assert.ok((await page.text()).includes('/employer/console.js'));
  const js = await (await w.fetch(await empReq('GET', '/employer/console.js', 'jobs@chmrecruit.example'))).text();
  assert.ok(js.includes('/api/employer/jobs') && !js.includes('/api/admin/'));
});

test('employer: scope escape -> 403 (edit, close or post for another employer)', async () => {
  const w = await employerWorld();
  const before = w.db.q(`SELECT title, status, version FROM jobs WHERE id='ie:strat:8002'`)[0];
  const edit = await w.fetch(await empReq('PUT', '/api/employer/jobs/ie:strat:8002', 'jobs@chmrecruit.example', { body: { title: 'Hijacked title', version: before.version } }));
  assert.equal(edit.status, 403);
  const close = await w.fetch(await empReq('POST', '/api/employer/jobs/ie:strat:8002/close', 'jobs@chmrecruit.example', { body: {} }));
  assert.equal(close.status, 403);
  const post = await w.fetch(await empReq('POST', '/api/employer/jobs', 'jobs@chmrecruit.example', { body: validJobBody({ employer_id: MATT }) }));
  assert.equal(post.status, 403);
  assert.deepEqual(w.db.q(`SELECT title, status, version FROM jobs WHERE id='ie:strat:8002'`)[0], before);
  const list = await (await w.fetch(await empReq('GET', '/api/employer/jobs', 'jobs@chmrecruit.example'))).json();
  assert.ok(!list.jobs.some((j) => j.id === 'ie:strat:8002'));
  // the employer route never reaches the staff API
  assert.equal((await w.fetch(await empReq('GET', '/api/admin/jobs', 'jobs@chmrecruit.example'))).status, 403);
});

test('employer: board allow-list, expiry, disabled, unknown email, bad JWT', async () => {
  const w = await employerWorld();
  // Mattinson has no uk employer row: refused on greenjobs.co.uk
  assert.equal((await w.fetch(await empReq('GET', '/api/employer/jobs', 'posts@mattinson.example', { host: 'greenjobs.co.uk' }))).status, 403);
  // CHM has one: allowed there, but only to its uk employer
  assert.equal((await w.fetch(await empReq('GET', '/api/employer/jobs', 'jobs@chmrecruit.example', { host: 'greenjobs.co.uk' }))).status, 403);
  w.db.sqlite.exec(`INSERT INTO employer_accounts (email_norm, employer_id, status, created_by, created_at, updated_at) VALUES ('jobs@chmrecruit.example', 'uk:strat:emp-chm', 'active', 'k', 't', 't')`);
  assert.equal((await w.fetch(await empReq('GET', '/api/employer/jobs', 'jobs@chmrecruit.example', { host: 'greenjobs.co.uk' }))).status, 200);
  const crossSite = await w.fetch(await empReq('PUT', '/api/employer/jobs/ie:strat:8001', 'jobs@chmrecruit.example', { host: 'greenjobs.co.uk', body: { title: 'x y z', version: 1 } }));
  assert.equal(crossSite.status, 404);
  for (const email of ['old@chmrecruit.example', 'off@chmrecruit.example', 'stranger@example.com']) {
    assert.equal((await w.fetch(await empReq('GET', '/api/employer/jobs', email))).status, 403, email);
  }
  assert.equal((await w.fetch(await adminRequest('GET', '/api/employer/jobs', { token: null }))).status, 401);
  const forged = await signToken({ email: 'jobs@chmrecruit.example' }, { wrongKey: true });
  assert.equal((await w.fetch(await adminRequest('GET', '/api/employer/jobs', { token: forged }))).status, 401);
  const none = await signToken({ email: 'jobs@chmrecruit.example' }, { alg: 'none' });
  assert.equal((await w.fetch(await adminRequest('GET', '/api/employer/jobs', { token: none }))).status, 401);
});

test('employer: CSRF, idempotency (replay = one job), validation', async () => {
  const w = await employerWorld();
  assert.equal((await w.fetch(await empReq('POST', '/api/employer/jobs', 'jobs@chmrecruit.example', { body: validJobBody(), origin: 'https://evil.example' }))).status, 403);
  assert.equal((await w.fetch(await empReq('POST', '/api/employer/jobs', 'jobs@chmrecruit.example', { body: validJobBody(), idem: null }))).status, 400);
  assert.equal((await w.fetch(await empReq('POST', '/api/employer/jobs', 'jobs@chmrecruit.example', { body: validJobBody({ title: 'x' }) }))).status, 400);
  assert.equal((await w.fetch(await empReq('POST', '/api/employer/jobs', 'jobs@chmrecruit.example', { body: validJobBody({ source: 'feed' }) }))).status, 400);
  const idem = crypto.randomUUID();
  const a = await w.fetch(await empReq('POST', '/api/employer/jobs', 'jobs@chmrecruit.example', { body: validJobBody(), idem }));
  const b = await w.fetch(await empReq('POST', '/api/employer/jobs', 'jobs@chmrecruit.example', { body: validJobBody(), idem }));
  assert.equal(a.status, 201);
  assert.equal(b.status, 200);
  assert.equal((await b.json()).replayed, true);
  assert.equal(w.db.q(`SELECT COUNT(*) AS n FROM jobs WHERE created_by='jobs@chmrecruit.example'`)[0].n, 1);
});

test('employer: staff see everything and post for a named employer', async () => {
  const w = await employerWorld();
  const list = await (await w.fetch(await empReq('GET', '/api/employer/jobs', 'keith@greenjobs.ie'))).json();
  assert.ok(list.jobs.some((j) => j.id === 'ie:strat:8001') && list.jobs.some((j) => j.id === 'ie:strat:8002'));
  const noEmp = await w.fetch(await empReq('POST', '/api/employer/jobs', 'keith@greenjobs.ie', { body: validJobBody() }));
  assert.equal(noEmp.status, 400);
  const ok = await w.fetch(await empReq('POST', '/api/employer/jobs', 'keith@greenjobs.ie', { body: validJobBody({ employer_id: MATT }) }));
  assert.equal(ok.status, 201);
  const v = w.db.q(`SELECT version FROM jobs WHERE id='ie:strat:8002'`)[0].version;
  assert.equal((await w.fetch(await empReq('PUT', '/api/employer/jobs/ie:strat:8002', 'keith@greenjobs.ie', { body: { title: 'Staff edited title', version: v } }))).status, 200);
});
