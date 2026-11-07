// Offline fakes for the GreenJobs platform Worker tests: D1 on node:sqlite loading the real
// schema.sql, R2 as a Map, a recording mail transport, a local RS256 key pair for Access JWTs,
// and a fixed clock. Nothing here touches the network.

import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { DatabaseSync } from 'node:sqlite';

const HERE = dirname(fileURLToPath(import.meta.url));
export const REPO = resolve(HERE, '../../..');
export const SCHEMA_PATH = resolve(REPO, 'deliverables/greenjobs_migration_2026-11-06/build/d1/schema.sql');
export const FEATURES_DIR = resolve(REPO, 'deliverables/greenjobs_migration_2026-11-06/build/features');
const WORKER = resolve(REPO, 'execution/gtm_client_workflows/greenjobs_redesign/platform_worker/src');
export const workerModule = (name) => import(resolve(WORKER, name));

const SCHEMA = readFileSync(SCHEMA_PATH, 'utf8');

class FakeStmt {
  constructor(db, sql, params = []) {
    this.db = db;
    this.sql = sql;
    this.params = params;
  }
  bind(...params) {
    for (const p of params) {
      if (p === undefined) throw new TypeError('D1_TYPE_ERROR: undefined bound');
      if (typeof p === 'boolean' || (typeof p === 'object' && p !== null)) throw new TypeError('D1_TYPE_ERROR: unsupported type');
    }
    return new FakeStmt(this.db, this.sql, params);
  }
  _stmt() {
    this.db.log.push(this.sql);
    return this.db.sqlite.prepare(this.sql);
  }
  _exec() {
    const st = this._stmt();
    if (st.columns().length > 0) return { success: true, results: st.all(...this.params).map((r) => ({ ...r })), meta: {} };
    const r = st.run(...this.params);
    return { success: true, results: [], meta: { changes: Number(r.changes), last_row_id: Number(r.lastInsertRowid) } };
  }
  async first(col) {
    const row = this._stmt().get(...this.params);
    if (!row) return null;
    return col ? row[col] : { ...row };
  }
  async all() {
    return { success: true, results: this._stmt().all(...this.params).map((r) => ({ ...r })), meta: {} };
  }
  async run() {
    return this._exec();
  }
}

export class FakeD1 {
  constructor() {
    this.sqlite = new DatabaseSync(':memory:');
    this.sqlite.exec(SCHEMA);
    this.log = [];
  }
  prepare(sql) {
    return new FakeStmt(this, sql);
  }
  async batch(stmts) {
    this.sqlite.exec('BEGIN');
    try {
      const out = stmts.map((s) => s._exec());
      this.sqlite.exec('COMMIT');
      return out;
    } catch (e) {
      this.sqlite.exec('ROLLBACK');
      throw e;
    }
  }
  q(sql, ...params) {
    return this.sqlite.prepare(sql).all(...params).map((r) => ({ ...r }));
  }
}

export class FakeR2 {
  constructor() {
    this.objects = new Map();
  }
  async put(key, bytes, opts = {}) {
    this.objects.set(key, { bytes: new Uint8Array(bytes), httpMetadata: opts.httpMetadata || {}, customMetadata: opts.customMetadata || {} });
  }
  async get(key) {
    const o = this.objects.get(key);
    if (!o) return null;
    return { httpMetadata: o.httpMetadata, arrayBuffer: async () => o.bytes.buffer.slice(0) };
  }
  async delete(key) {
    this.objects.delete(key);
  }
}

export class FakeKV {
  constructor() {
    this.map = new Map();
  }
  async get(k) {
    return this.map.has(k) ? this.map.get(k) : null;
  }
  async put(k, v) {
    this.map.set(k, v);
  }
}

// One RSA key pair per process (generation is the slow part).
let keysP = null;
export function testKeys() {
  keysP ||= (async () => {
    const pair = await crypto.subtle.generateKey(
      { name: 'RSASSA-PKCS1-v1_5', modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: 'SHA-256' },
      true,
      ['sign', 'verify'],
    );
    const other = await crypto.subtle.generateKey(
      { name: 'RSASSA-PKCS1-v1_5', modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: 'SHA-256' },
      true,
      ['sign', 'verify'],
    );
    const jwk = await crypto.subtle.exportKey('jwk', pair.publicKey);
    return { privateKey: pair.privateKey, otherPrivateKey: other.privateKey, jwks: { keys: [{ ...jwk, kid: 'test-kid', alg: 'RS256', use: 'sig' }] } };
  })();
  return keysP;
}

const b64url = (bytes) => Buffer.from(bytes).toString('base64').replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
const b64urlJson = (o) => b64url(Buffer.from(JSON.stringify(o)));

export const TEAM = 'greenjobs.cloudflareaccess.com';
export const AUD = 'aud-test-0123456789';
export const NOW = new Date('2026-11-07T10:00:00Z');

/** Sign an Access-style JWT. opts: {alg, kid, wrongKey, tamper, claims overrides}. */
export async function signToken(overrides = {}, opts = {}) {
  const k = await testKeys();
  const nowS = Math.floor((opts.nowMs ?? NOW.getTime()) / 1000);
  const claims = { aud: [AUD], iss: `https://${TEAM}`, email: 'keith@greenjobs.ie', iat: nowS, nbf: nowS - 5, exp: nowS + 3600, sub: 'u1', ...overrides };
  for (const [key, v] of Object.entries(claims)) if (v === undefined) delete claims[key];
  const header = { alg: opts.alg || 'RS256', kid: opts.kid || 'test-kid', typ: 'JWT' };
  const signingInput = `${b64urlJson(header)}.${b64urlJson(claims)}`;
  if (opts.alg === 'none') return `${signingInput}.`;
  const sig = await crypto.subtle.sign('RSASSA-PKCS1-v1_5', opts.wrongKey ? k.otherPrivateKey : k.privateKey, new TextEncoder().encode(signingInput));
  let token = `${signingInput}.${b64url(new Uint8Array(sig))}`;
  if (opts.tamper) {
    const [h, , s] = token.split('.');
    token = `${h}.${b64urlJson({ ...claims, email: 'attacker@evil.example' })}.${s}`;
  }
  return token;
}

export const HOST_SITE_MAP = JSON.stringify({
  'greenjobs.ie': 'ie', 'www.greenjobs.ie': 'ie', 'greenjobs.co.uk': 'uk', 'www.greenjobs.co.uk': 'uk',
  'ie.staging.greenjobs.test': 'ie', 'uk.staging.greenjobs.test': 'uk',
});

export function baseEnv(overrides = {}) {
  return {
    DRY_RUN: '1',
    LIVE_CONFIRM: '',
    HOST_SITE_MAP,
    ACCESS_TEAM_DOMAIN: TEAM,
    ACCESS_AUD: AUD,
    STAFF_EMAILS: 'keith@greenjobs.ie,staff@greenjobs.ie',
    APPLY_ROUTING: 'inbox',
    APPLY_INBOX_IE: 'jobs@greenjobs.ie',
    APPLY_INBOX_UK: 'jobs@greenjobs.co.uk',
    MAIL_PROVIDER: 'resend',
    MAIL_FROM: 'GreenJobs <applications@greenjobs.ie>',
    RESEND_API_KEY: 'dummy-not-a-real-key',
    MAIL_DAILY_CAP: '200',
    RATE_APPLY_PER_10MIN: '5',
    RATE_ADMIN_PER_MIN: '60',
    MAX_CV_BYTES: '5242880',
    ALERTS_ENABLED: '0',
    NEWSLETTER_ENABLED: '0',
    ALLOWED_ORIGINS: 'https://greenjobs.ie,https://www.greenjobs.ie,https://greenjobs.co.uk,https://www.greenjobs.co.uk',
    BUILD_TOKEN: 'build-token-for-tests-only',
    ...overrides,
  };
}

/** A fresh world per test/scenario: fakes + handler with injected JWKS, mail transport and clock. */
export async function makeWorld(envOverrides = {}) {
  const { createHandler } = await workerModule('index.js');
  const keys = await testKeys();
  const db = new FakeD1();
  const r2 = new FakeR2();
  const mail = { calls: [], ok: true };
  const clock = { now: new Date(NOW) };
  const jwksFetches = [];
  const env = baseEnv({ DB: db, CVS: r2, ...envOverrides });
  const handler = createHandler({
    jwksFetcher: (host) => async () => {
      jwksFetches.push(host);
      return keys.jwks;
    },
    mailTransport: async (payload, e, key) => {
      mail.calls.push({ payload, key });
      return { ok: mail.ok, status: mail.ok ? 200 : 500 };
    },
    now: () => new Date(clock.now),
  });
  const world = {
    env, db, r2, mail, clock, handler, jwksFetches,
    fetch: (req) => handler.fetch(req, env, {}),
    advance(ms) {
      clock.now = new Date(clock.now.getTime() + ms);
    },
  };
  return world;
}

let seedN = 0;
/** Insert a job directly (as an import would). */
export function seedJob(world, o = {}) {
  seedN++;
  const site = o.site || 'ie';
  const id = o.id || `${site}:strat:${1000 + seedN}`;
  const emp = `${site}:strat:emp${seedN}`;
  const ts = '2026-11-01T09:00:00Z';
  world.db.sqlite
    .prepare(`INSERT INTO employers (id, site, source, source_id, name, name_norm, created_at, updated_at) VALUES (?1, ?2, 'strategies', ?3, ?4, ?5, ?6, ?6)`)
    .run(emp, site, `emp${seedN}`, o.employer || 'Acme Renewables Ltd', 'acme renewables', ts);
  world.db.sqlite
    .prepare(`INSERT INTO jobs (id, site, source, source_id, employer_id, title, location, job_type, sal_text, sectors_json, summary, description,
      apply_mode, apply_email, apply_url, status, posted_at, closing_at, created_by, created_at, updated_at)
      VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12, ?13, ?14, ?15, ?16, ?17, ?18, 'import', ?19, ?19)`)
    .run(
      id, site, o.source || 'strategies', o.source_id ?? String(1000 + seedN), emp, o.title || 'Senior Wind Engineer', o.location || 'Cork',
      o.job_type || 'Permanent', o.sal_text || 'EUR 60,000 - 70,000', JSON.stringify(o.sectors || ['Wind']), o.summary || 'Lead onshore wind projects.',
      o.description || 'Lead the design of onshore wind farms across Munster. Plenty of detail here.',
      o.apply_mode || 'inbox', o.apply_email ?? null, o.apply_url ?? null, o.status || 'live', o.posted_at || ts,
      o.closing_at === undefined ? '2026-12-31T23:59:59Z' : o.closing_at, ts,
    );
  return id;
}

export const UPSERTS_PATH = resolve(REPO, 'deliverables/greenjobs_migration_2026-11-06/build/d1/upserts.sql');

/** The canonical import upsert for jobs, read from upserts.sql exactly as the Python emitter uses it. */
export function importJobSql() {
  const stmts = readFileSync(UPSERTS_PATH, 'utf8').replace(/--[^\n]*/g, '').split(';').map((x) => x.trim());
  const hits = stmts.filter((x) => x.startsWith('INSERT INTO jobs '));
  if (hits.length !== 1) throw new Error(`upserts.sql: expected one jobs import upsert, found ${hits.length}`);
  return hits[0];
}

/** Re-apply a Strategies import of an existing job row (as a re-run of the emitted SQL would), with overrides. */
export function reapplyImport(world, id, over = {}) {
  const r = { ...world.db.q('SELECT * FROM jobs WHERE id = ?1', id)[0], ...over };
  const sourceId = r.source_id ?? id.split(':').pop();
  return world.db.sqlite.prepare(importJobSql()).run(
    id, r.site, 'strategies', sourceId, r.employer_id, r.title, r.location, r.region, r.job_type, r.sal_min, r.sal_max,
    r.currency, r.period, r.sal_text, r.sectors_json, r.summary, r.description, r.apply_mode, r.apply_email, r.apply_url,
    r.status, r.posted_at, r.closing_at, 'import', '2026-11-08T09:00:00Z',
  );
}

export const ORIGIN = (host = 'greenjobs.ie') => `https://${host}`;

export async function adminRequest(method, path, o = {}) {
  const host = o.host || 'greenjobs.ie';
  const headers = new Headers();
  if (o.token !== null) headers.set('Cf-Access-Jwt-Assertion', o.token || (await signToken(o.claims || {}, o.signOpts || {})));
  if (o.origin !== null && method !== 'GET') headers.set('Origin', o.origin || ORIGIN(host));
  if (method !== 'GET') {
    if (o.contentType !== null) headers.set('Content-Type', o.contentType || 'application/json');
    if (o.idem !== null) headers.set('Idempotency-Key', o.idem || crypto.randomUUID());
  }
  headers.set('CF-Connecting-IP', o.ip || '198.51.100.7');
  return new Request(`https://${host}${path}`, { method, headers, body: method === 'GET' ? undefined : JSON.stringify(o.body ?? {}) });
}

export function validJobBody(over = {}) {
  return {
    title: 'Solar PV Project Manager',
    employer: 'Sunrise Energy Ltd',
    location: 'Dublin',
    job_type: 'Permanent',
    description: 'Manage utility-scale solar PV builds from grid connection to energisation.',
    summary: 'Utility-scale solar PV delivery.',
    sal_text: 'EUR 65,000',
    sectors: ['Solar'],
    closing: '2026-12-15',
    status: 'live',
    ...over,
  };
}

export const PDF_BYTES = new TextEncoder().encode('%PDF-1.7\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF');
export const DOC_BYTES = new Uint8Array([0xd0, 0xcf, 0x11, 0xe0, 0xa1, 0xb1, 0x1a, 0xe1, 0, 0, 0, 0]);
export function docxBytes() {
  const head = [0x50, 0x4b, 0x03, 0x04, ...new Array(26).fill(0)];
  return new Uint8Array([...head, ...new TextEncoder().encode('word/document.xml')]);
}

export function applyRequest(fields = {}, o = {}) {
  const host = o.host || 'greenjobs.ie';
  const fd = new FormData();
  const all = {
    job_id: 'ie:strat:1001',
    name: 'Aoife Byrne',
    email: 'aoife@example.ie',
    consent: 'yes',
    website: '',
    ts: String(NOW.getTime() - 60_000),
    ...fields,
  };
  for (const [k, v] of Object.entries(all)) if (v !== undefined) fd.append(k, v);
  if (o.cv) fd.append('cv', new File([o.cv], o.cvName || 'cv.pdf', { type: o.cvType || 'application/pdf' }));
  const headers = new Headers({ 'CF-Connecting-IP': o.ip || '203.0.113.9' });
  if (o.origin) headers.set('Origin', o.origin);
  return new Request(`https://${host}/api/apply`, { method: 'POST', body: fd, headers });
}
