// Per-job apply mode (email | link), client answer Q8 of 10-11 Nov. Every guard is proven twice:
// it fires on the bad input AND lets the matching good input through.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { DatabaseSync } from 'node:sqlite';
import {
  REPO, SCHEMA_PATH, adminRequest, applyRequest, makeWorld, reapplyImport, seedJob, validJobBody, workerModule,
} from './helpers.mjs';

const V = await workerModule('validate.js');
const { consoleHtml, consoleAsset } = await workerModule('routes/console.js');
const { publicApply } = await workerModule('routes/public.js');

const D1 = resolve(REPO, 'deliverables/greenjobs_migration_2026-11-06/build/d1');
const SCHEMA = readFileSync(SCHEMA_PATH, 'utf8');
const MIGRATION = readFileSync(resolve(D1, 'migrations/0001_apply_mode_consent_alerts.sql'), 'utf8');
const LEGACY = readFileSync(resolve(REPO, 'tests/greenjobs_redesign/fixtures/d1/schema_pre_2026-11-20.sql'), 'utf8');

const get = (host, path, headers = {}) => new Request(`https://${host}${path}`, { headers });
const body = async (res) => res.json();
const BUILD = { Authorization: 'Bearer build-token-for-tests-only' };

// ---------- validateJob ----------

const base = { title: 'Wind Engineer', employer: 'Acme', location: 'Cork', description: 'x'.repeat(25), status: 'live' };
const vj = (o) => V.validateJob({ ...base, ...o }, { site: 'ie', today: '2026-11-07' });

test('validateJob apply mode: default email; good inputs pass, normalised', () => {
  assert.equal(vj({}).value.apply_mode, 'email');
  assert.equal(vj({ apply_mode: '' }).value.apply_mode, 'email');
  const e = vj({ apply_mode: 'email', apply_email: '  HR@Acme.IE ' });
  assert.equal(e.ok, true);
  assert.equal(e.value.apply_email, 'hr@acme.ie');
  assert.equal(e.value.apply_url, null);
  const l = vj({ apply_mode: 'link', apply_url: 'https://ats.example.com/jobs/7?src=gj' });
  assert.equal(l.ok, true);
  assert.equal(l.value.apply_url, 'https://ats.example.com/jobs/7?src=gj');
  assert.equal(l.value.apply_email, null);
  assert.equal(vj({ apply_mode: 'link', apply_url: 'https://ats.example.com/7', apply_email: '' }).ok, true, 'blank email is not "set"');
});

test('validateJob apply mode: every guard fires', () => {
  const errs = (o) => vj(o).errors;
  assert.deepEqual(errs({ apply_mode: 'email', apply_email: 'not-an-email' }), ['apply_email']);
  assert.deepEqual(errs({ apply_mode: 'email', apply_email: 'a@b.ie\r\nBcc: x@evil.example' }), ['apply_email']);
  assert.deepEqual(errs({ apply_mode: 'link', apply_url: 'http://ats.example.com/7' }), ['apply_url']);
  assert.deepEqual(errs({ apply_mode: 'link', apply_url: 'javascript:alert(1)' }), ['apply_url']);
  assert.deepEqual(errs({ apply_mode: 'link', apply_url: 'JavaScript:alert(1)' }), ['apply_url']);
  assert.deepEqual(errs({ apply_mode: 'link', apply_url: 'data:text/html,<script>alert(1)</script>' }), ['apply_url']);
  assert.deepEqual(errs({ apply_mode: 'link', apply_url: 'https://user:pw@ats.example.com/' }), ['apply_url']);
  assert.deepEqual(errs({ apply_mode: 'link' }), ['apply_url'], 'link needs a url');
  assert.deepEqual(errs({ apply_mode: 'link', apply_url: 'https://ats.example.com/7', apply_email: 'hr@acme.ie' }), ['apply_email'], 'link takes no email');
  assert.deepEqual(errs({ apply_mode: 'email', apply_url: 'https://ats.example.com/7' }), ['apply_url'], 'email takes no url');
  for (const legacy of ['inbox', 'consultant', 'advertiser', 'url', 'EMAIL']) assert.deepEqual(errs({ apply_mode: legacy }), ['apply_mode'], legacy);
});

test('publicApply never carries apply_email; apply_url only for link mode', () => {
  assert.deepEqual(publicApply({ apply_mode: 'email', apply_email: 'hr@acme.ie', apply_url: null }), { apply_mode: 'email', apply_url: null });
  assert.deepEqual(publicApply({ apply_mode: 'link', apply_url: 'https://ats.example.com/1' }), { apply_mode: 'link', apply_url: 'https://ats.example.com/1' });
  assert.deepEqual(publicApply({ apply_mode: 'email', apply_url: 'https://stale.example.com' }), { apply_mode: 'email', apply_url: null });
  assert.deepEqual(publicApply({ apply_mode: 'link', apply_url: 'javascript:alert(1)' }), { apply_mode: 'email', apply_url: null });
});

// ---------- schema ----------

test('schema applies twice; the jobs CHECKs refuse what the validator refuses', () => {
  const db = new DatabaseSync(':memory:');
  db.exec(SCHEMA);
  db.exec(SCHEMA);
  db.exec("INSERT INTO employers (id, site, source, name, name_norm, created_at, updated_at) VALUES ('ie:gj:e', 'ie', 'console', 'A', 'a', 't', 't')");
  const ins = (mode, email, url, id) => db.prepare(`INSERT INTO jobs (id, site, source, employer_id, title, location, description, apply_mode, apply_email, apply_url, created_by, created_at, updated_at)
    VALUES (?1, 'ie', 'console', 'ie:gj:e', 'Title x', 'Cork', '${'d'.repeat(25)}', ?2, ?3, ?4, 'test', 't', 't')`).run(id, mode, email, url);
  // positive: both legal shapes insert
  ins('email', null, null, 'ie:gj:1');
  ins('email', 'hr@acme.ie', null, 'ie:gj:2');
  ins('link', null, 'https://ats.example.com/3', 'ie:gj:3');
  // negative: every illegal shape is refused by the database itself
  const bad = [
    ['inbox', null, null], ['url', null, 'https://ats.example.com'], ['link', null, null],
    ['link', 'hr@acme.ie', 'https://ats.example.com'], ['email', null, 'https://ats.example.com'],
    ['link', null, 'http://ats.example.com'], ['link', null, 'javascript:alert(1)'],
    ['email', 'HR@Acme.ie', null], ['email', 'no-at-sign', null],
  ];
  bad.forEach(([m, e, u], i) => assert.throws(() => ins(m, e, u, `ie:gj:bad${i}`), /CHECK constraint failed/, JSON.stringify([m, e, u])));
  assert.equal(db.prepare("SELECT apply_mode FROM jobs WHERE id = 'ie:gj:1'").get().apply_mode, 'email');
});

const norm = (sql) => sql.replace(/--[^\n]*/g, '').replace(/"/g, '').replace(/IF NOT EXISTS /g, '').replace(/\s+/g, ' ').trim();
const legacyDb = () => {
  const db = new DatabaseSync(':memory:');
  db.exec(LEGACY);
  db.exec('PRAGMA foreign_keys = ON');
  db.exec("INSERT INTO employers (id, site, source, name, name_norm, created_at, updated_at) VALUES ('ie:strat:e', 'ie', 'strategies', 'A', 'a', 't', 't')");
  const rows = [['inbox', null, null], ['consultant', 'Sam@Agency.ie', null], ['url', null, 'https://ats.example.com/2'],
    ['advertiser', 'not-an-email', null], ['url', 'hr@acme.ie', 'https://ats.example.com/4'], ['inbox', 'jobs@acme.ie', null]];
  rows.forEach(([m, e, u], i) => db.prepare(`INSERT INTO jobs (id, site, source, employer_id, title, location, description, apply_mode, apply_email, apply_url, status, created_by, created_at, updated_at)
    VALUES (?1, 'ie', 'strategies', 'ie:strat:e', 'Title x', 'Cork', '${'d'.repeat(25)}', ?2, ?3, ?4, 'live', 'import', 't', 't')`).run(`ie:strat:${i}`, m, e, u));
  db.exec("INSERT INTO candidates (id, site, source, email_norm, consent_marketing, created_at, updated_at) VALUES ('ie:strat:c1', 'ie', 'strategies', 'n@x.ie', 1, 't', 't')");
  db.exec("INSERT INTO applications (id, site, source, job_id, candidate_id, applicant_name, applicant_email, dedupe_key, submitted_at, created_at, updated_at) VALUES ('ie:apply:a', 'ie', 'apply', 'ie:strat:1', 'ie:strat:c1', 'N', 'n@x.ie', 'k1', 't', 't', 't')");
  db.exec("INSERT INTO import_batches (sha256, site, report_type, rows_in, rows_kept, imported_at) VALUES ('abc', 'ie', 'jobs', 6, 6, 't')");
  return db;
};
const runMigration = (db) => db.exec(`BEGIN;\n${MIGRATION}\nCOMMIT;`); // D1 wraps a --file run in one transaction

test('migration 0001: legacy DB -> email|link, run twice converges, FKs and data intact', () => {
  const db = legacyDb();
  runMigration(db);
  const first = db.prepare('SELECT id, apply_mode, apply_email, apply_url FROM jobs ORDER BY id').all().map((r) => ({ ...r }));
  assert.deepEqual(first, [
    { id: 'ie:strat:0', apply_mode: 'email', apply_email: null, apply_url: null },
    { id: 'ie:strat:1', apply_mode: 'email', apply_email: 'sam@agency.ie', apply_url: null },
    { id: 'ie:strat:2', apply_mode: 'link', apply_email: null, apply_url: 'https://ats.example.com/2' },
    { id: 'ie:strat:3', apply_mode: 'email', apply_email: null, apply_url: null },
    { id: 'ie:strat:4', apply_mode: 'link', apply_email: null, apply_url: 'https://ats.example.com/4' },
    { id: 'ie:strat:5', apply_mode: 'email', apply_email: 'jobs@acme.ie', apply_url: null },
  ]);
  runMigration(db);
  assert.deepEqual(db.prepare('SELECT id, apply_mode, apply_email, apply_url FROM jobs ORDER BY id').all().map((r) => ({ ...r })), first);
  assert.equal(db.prepare('SELECT COUNT(*) AS n FROM applications').get().n, 1);
  assert.deepEqual(db.prepare('PRAGMA foreign_key_check').all(), []);
  assert.equal(db.prepare("SELECT COUNT(*) AS n FROM sqlite_master WHERE name IN ('jobs_hold','jobs_new')").get().n, 0);
  assert.equal(db.prepare("SELECT COUNT(*) AS n FROM sqlite_master WHERE type = 'index' AND name = 'jobs_live'").get().n, 1);
  // The rebuilt table is exactly the table schema.sql creates (no drift between the two files).
  const fresh = new DatabaseSync(':memory:');
  fresh.exec(SCHEMA);
  const ddl = (d, t) => norm(d.prepare("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?1").get(t).sql);
  for (const t of ['jobs', 'candidates', 'import_batches']) assert.equal(ddl(db, t), ddl(fresh, t), t);
  assert.equal(db.prepare("SELECT COUNT(*) AS n FROM sqlite_master WHERE name LIKE '%\\_hold' ESCAPE '\\' OR name LIKE '%\\_new' ESCAPE '\\'").get().n, 0);
  // candidates: the new strategies_consent column survives a re-run; import_batches now takes 'alerts'
  assert.deepEqual({ ...db.prepare("SELECT consent_marketing, strategies_consent FROM candidates WHERE id = 'ie:strat:c1'").get() }, { consent_marketing: 1, strategies_consent: null });
  db.exec("UPDATE candidates SET strategies_consent = 0 WHERE id = 'ie:strat:c1'");
  runMigration(db);
  assert.equal(db.prepare("SELECT strategies_consent FROM candidates WHERE id = 'ie:strat:c1'").get().strategies_consent, 0);
  assert.equal(db.prepare("SELECT candidate_id FROM applications").get().candidate_id, 'ie:strat:c1');
  assert.equal(db.prepare("SELECT rows_kept FROM import_batches WHERE sha256 = 'abc'").get().rows_kept, 6);
  db.exec("INSERT INTO import_batches (sha256, site, report_type, rows_in, rows_kept, imported_at) VALUES ('def', 'ie', 'alerts', 1, 1, 't')");
  assert.throws(() => db.exec("INSERT INTO candidates (id, site, source, email_norm, strategies_consent, created_at, updated_at) VALUES ('x', 'ie', 'strategies', 'q@x.ie', 2, 't', 't')"), /CHECK/);
  // schema.sql still applies cleanly on top of the migrated DB, and a dangling FK is still refused.
  db.exec(SCHEMA);
  assert.throws(() => db.exec("INSERT INTO applications (id, site, source, job_id, applicant_name, applicant_email, dedupe_key, submitted_at, created_at, updated_at) VALUES ('x', 'ie', 'apply', 'ie:strat:none', 'N', 'm@x.ie', 'k2', 't', 't', 't')"), /FOREIGN KEY/);
});

test('migration 0001 on a DB created from the new schema changes no rows', () => {
  const db = new DatabaseSync(':memory:');
  db.exec(SCHEMA);
  db.exec("INSERT INTO employers (id, site, source, name, name_norm, created_at, updated_at) VALUES ('ie:gj:e', 'ie', 'console', 'A', 'a', 't', 't')");
  db.exec(`INSERT INTO jobs (id, site, source, employer_id, title, location, description, apply_mode, apply_url, created_by, created_at, updated_at)
    VALUES ('ie:gj:1', 'ie', 'console', 'ie:gj:e', 'Title x', 'Cork', '${'d'.repeat(25)}', 'link', 'https://ats.example.com/1', 'x', 't', 't')`);
  const before = db.prepare('SELECT * FROM jobs').all().map((r) => ({ ...r }));
  runMigration(db);
  assert.deepEqual(db.prepare('SELECT * FROM jobs').all().map((r) => ({ ...r })), before);
});

// ---------- console API ----------

test('console create: link job 201, email job 201 with normalised address, guards 400 with field names', async () => {
  const w = await makeWorld();
  const create = async (over) => w.fetch(await adminRequest('POST', '/api/admin/jobs', { body: validJobBody(over) }));
  const link = await create({ apply_mode: 'link', apply_url: 'https://ats.example.com/9', apply_email: '' });
  assert.equal(link.status, 201);
  const lid = (await body(link)).id;
  assert.deepEqual(w.db.q('SELECT apply_mode, apply_email, apply_url FROM jobs WHERE id = ?1', lid)[0], { apply_mode: 'link', apply_email: null, apply_url: 'https://ats.example.com/9' });
  const em = await create({ title: 'Grid Engineer', apply_mode: 'email', apply_email: 'HR@Client.ie', apply_url: '' });
  assert.equal(em.status, 201);
  assert.equal(w.db.q('SELECT apply_email FROM jobs WHERE id = ?1', (await body(em)).id)[0].apply_email, 'hr@client.ie');
  for (const [over, field] of [
    [{ apply_mode: 'email', apply_email: 'nope' }, 'apply_email'],
    [{ apply_mode: 'link', apply_url: 'http://ats.example.com/9' }, 'apply_url'],
    [{ apply_mode: 'link', apply_url: 'javascript:alert(1)' }, 'apply_url'],
    [{ apply_mode: 'link', apply_url: 'https://ats.example.com/9', apply_email: 'hr@client.ie' }, 'apply_email'],
    [{ apply_mode: 'email', apply_url: 'https://ats.example.com/9' }, 'apply_url'],
    [{ apply_mode: 'consultant' }, 'apply_mode'],
  ]) {
    const r = await create({ title: `Role ${field} ${over.apply_mode}`, ...over });
    assert.equal(r.status, 400, JSON.stringify(over));
    assert.deepEqual((await body(r)).fields, [field], JSON.stringify(over));
  }
});

test('console edit: switching email -> link needs the email cleared; the console sends both fields', async () => {
  const w = await makeWorld();
  const c = await w.fetch(await adminRequest('POST', '/api/admin/jobs', { body: validJobBody({ apply_email: 'hr@client.ie' }) }));
  const { id } = await body(c);
  const put = async (b) => w.fetch(await adminRequest('PUT', `/api/admin/jobs/${id}`, { body: b }));
  const stale = await put({ version: 1, apply_mode: 'link', apply_url: 'https://ats.example.com/1' });
  assert.equal(stale.status, 400);
  assert.deepEqual((await body(stale)).fields, ['apply_email']);
  const ok = await put({ version: 1, apply_mode: 'link', apply_url: 'https://ats.example.com/1', apply_email: '' });
  assert.equal(ok.status, 200);
  assert.deepEqual(w.db.q('SELECT apply_mode, apply_email, apply_url FROM jobs WHERE id = ?1', id)[0], { apply_mode: 'link', apply_email: null, apply_url: 'https://ats.example.com/1' });
  const html = await consoleHtml('ie', 'keith@greenjobs.ie').text();
  assert.match(html, /<option value="email">/);
  assert.match(html, /<option value="link">/);
  assert.doesNotMatch(html, /value="(inbox|consultant|advertiser|url)"/);
  const js = await consoleAsset('console.js').text();
  assert.match(js, /body\.apply_email = f\.apply_email\.value;/);
  assert.match(js, /body\.apply_url = f\.apply_url\.value;/);
});

// ---------- public API ----------

test('public JSON never carries apply_email; apply_url only for link mode', async () => {
  const w = await makeWorld();
  seedJob(w, { id: 'ie:strat:1', apply_mode: 'email', apply_email: 'secret.consultant@agency.ie' });
  seedJob(w, { id: 'ie:strat:2', apply_mode: 'link', apply_url: 'https://ats.example.com/2' });
  seedJob(w, { id: 'ie:strat:3' });
  const texts = [];
  for (const req of [get('greenjobs.ie', '/api/jobs'), get('greenjobs.ie', '/api/jobs/ie:strat:1'), get('greenjobs.ie', '/api/jobs/ie:strat:2'),
    get('greenjobs.ie', '/api/export/jobs?site=ie', BUILD)]) {
    const r = await w.fetch(req);
    assert.equal(r.status, 200);
    texts.push(await r.text());
  }
  for (const t of texts) {
    assert.doesNotMatch(t, /secret\.consultant|agency\.ie/);
    assert.doesNotMatch(t, /apply_email/);
  }
  const one = JSON.parse(texts[1]);
  assert.deepEqual([one.apply_mode, one.apply_url], ['email', null]);
  const two = JSON.parse(texts[2]);
  assert.deepEqual([two.apply_mode, two.apply_url], ['link', 'https://ats.example.com/2']);
  const exp = Object.fromEntries(JSON.parse(texts[3]).jobs.map((j) => [j.id, [j.apply_mode, j.apply_url]]));
  assert.deepEqual(exp, { 'ie:strat:1': ['email', null], 'ie:strat:2': ['link', 'https://ats.example.com/2'], 'ie:strat:3': ['email', null] });
});

// ---------- POST /api/apply ----------

test('apply: link-mode job is refused 409 even fully live; nothing stored, nothing sent', async () => {
  const w = await makeWorld({ DRY_RUN: '0', LIVE_CONFIRM: 'send-applications' });
  seedJob(w, { id: 'ie:strat:1', apply_mode: 'link', apply_url: 'https://ats.example.com/1' });
  const r = await w.fetch(applyRequest({ job_id: 'ie:strat:1' }));
  assert.equal(r.status, 409);
  assert.deepEqual(await body(r), { error: 'apply_externally', apply_url: 'https://ats.example.com/1' });
  assert.equal(w.db.q('SELECT COUNT(*) AS n FROM applications')[0].n, 0);
  assert.equal(w.mail.calls.length, 0);
  assert.equal(w.r2.objects.size, 0);
});

test('apply: email-mode job routes to its apply_email; dry run by default, live only with LIVE_CONFIRM', async () => {
  const dry = await makeWorld();
  seedJob(dry, { id: 'ie:strat:1', apply_mode: 'email', apply_email: 'hr@client.ie' });
  assert.equal((await dry.fetch(applyRequest({ job_id: 'ie:strat:1' }))).status, 201);
  assert.deepEqual(dry.db.q('SELECT routed_to, delivery_status FROM applications')[0], { routed_to: 'hr@client.ie', delivery_status: 'dry_run' });
  assert.equal(dry.mail.calls.length, 0);

  const half = await makeWorld({ DRY_RUN: '0' });
  seedJob(half, { id: 'ie:strat:1', apply_mode: 'email', apply_email: 'hr@client.ie' });
  await half.fetch(applyRequest({ job_id: 'ie:strat:1' }));
  assert.equal(half.db.q('SELECT delivery_status FROM applications')[0].delivery_status, 'dry_run');
  assert.equal(half.mail.calls.length, 0, 'DRY_RUN=0 without LIVE_CONFIRM sends nothing');

  const live = await makeWorld({ DRY_RUN: '0', LIVE_CONFIRM: 'send-applications' });
  seedJob(live, { id: 'ie:strat:1', apply_mode: 'email', apply_email: 'hr@client.ie' });
  seedJob(live, { id: 'ie:strat:2', apply_mode: 'email', apply_email: null });
  await live.fetch(applyRequest({ job_id: 'ie:strat:1' }));
  await live.fetch(applyRequest({ job_id: 'ie:strat:2' }));
  assert.deepEqual(live.mail.calls.map((c) => c.payload.to).flat(), ['hr@client.ie', 'jobs@greenjobs.ie']);
  assert.deepEqual(live.db.q('SELECT job_id, routed_to, delivery_status FROM applications ORDER BY job_id'), [
    { job_id: 'ie:strat:1', routed_to: 'hr@client.ie', delivery_status: 'sent' },
    { job_id: 'ie:strat:2', routed_to: 'jobs@greenjobs.ie', delivery_status: 'sent' },
  ]);
});

// ---------- import upsert ----------

test('import re-apply updates apply fields on Strategies rows only', async () => {
  const w = await makeWorld();
  seedJob(w, { id: 'ie:strat:7001' });
  reapplyImport(w, 'ie:strat:7001', { apply_mode: 'link', apply_url: 'https://ats.example.com/7001', apply_email: null });
  assert.deepEqual(w.db.q("SELECT apply_mode, apply_url FROM jobs WHERE id = 'ie:strat:7001'")[0], { apply_mode: 'link', apply_url: 'https://ats.example.com/7001' });
  seedJob(w, { id: 'ie:strat:7002', source: 'console', apply_mode: 'email', apply_email: 'hr@client.ie' });
  reapplyImport(w, 'ie:strat:7002', { apply_mode: 'link', apply_url: 'https://ats.example.com/7002', apply_email: null });
  assert.deepEqual(w.db.q("SELECT apply_mode, apply_email FROM jobs WHERE id = 'ie:strat:7002'")[0], { apply_mode: 'email', apply_email: 'hr@client.ie' });
});
