// Regression tests for the 2026-11-07 audit findings #15, #22, #21, #6 (REDTEAM_CHECKLIST.md).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { FakeD1, NOW, PDF_BYTES, adminRequest, applyRequest, baseEnv, makeWorld, reapplyImport, seedJob, workerModule } from './helpers.mjs';

const { createMailer, resendTransport } = await workerModule('mail.js');
const { deliverApplication } = await workerModule('routes/apply.js');

const get = (host, path, headers = {}) => new Request(`https://${host}${path}`, { headers });
const BUILD = { Authorization: 'Bearer build-token-for-tests-only' };

// ---------- #15 console edit survives re-import ----------

test('#15 console edit of an imported job survives a re-import; untouched imports still update', async () => {
  const w = await makeWorld();
  seedJob(w, { id: 'ie:strat:7001', source_id: '7001', title: 'Wind Engineer' });
  seedJob(w, { id: 'ie:strat:7002', source_id: '7002', title: 'Solar Engineer' });
  const r = await w.fetch(await adminRequest('PUT', '/api/admin/jobs/ie:strat:7001', { body: { title: 'Senior Wind Engineer', version: 1 } }));
  assert.equal(r.status, 200);
  assert.deepEqual(w.db.q("SELECT source, source_id FROM jobs WHERE id = 'ie:strat:7001'")[0], { source: 'console', source_id: '7001' });
  for (let i = 0; i < 2; i++) {
    reapplyImport(w, 'ie:strat:7001', { title: 'Wind Engineer' });
    reapplyImport(w, 'ie:strat:7002', { title: 'Solar Engineer II' });
  }
  assert.equal(w.db.q("SELECT title FROM jobs WHERE id = 'ie:strat:7001'")[0].title, 'Senior Wind Engineer');
  assert.equal(w.db.q("SELECT title FROM jobs WHERE id = 'ie:strat:7002'")[0].title, 'Solar Engineer II');
  // A second edit of the now console-owned row still works (no UNIQUE (site, source, source_id) collision).
  const r2 = await w.fetch(await adminRequest('PUT', '/api/admin/jobs/ie:strat:7001', { body: { title: 'Lead Wind Engineer', version: 2 } }));
  assert.equal(r2.status, 200);
});

// ---------- #22 keyset pagination ----------

function seedMany(w, n) {
  for (let i = 0; i < n; i++) {
    const day = String(1 + (i % 5)).padStart(2, '0'); // ties on the sort key exercise the id tiebreak
    seedJob(w, { id: `ie:strat:${9000 + i}`, posted_at: `2026-11-${day}T09:00:00Z` });
  }
}

async function walk(w, base, headers, limit) {
  const seen = [];
  let after = null;
  let pages = 0;
  do {
    const url = `${base}${base.includes('?') ? '&' : '?'}limit=${limit}${after ? `&after=${encodeURIComponent(after)}` : ''}`;
    const res = await w.fetch(get('greenjobs.ie', url, headers));
    assert.equal(res.status, 200);
    const d = await res.json();
    assert.ok(d.jobs.length <= limit);
    seen.push(...d.jobs.map((j) => j.id));
    after = d.next;
    pages++;
    assert.ok(pages < 100, 'pagination terminates');
  } while (after);
  return { seen, pages };
}

test('#22 /api/jobs and /api/export/jobs walk every live row exactly once; next is null at the end', async () => {
  const w = await makeWorld();
  seedMany(w, 23);
  seedJob(w, { id: 'ie:strat:8999', status: 'closed' });
  for (const [base, headers] of [['/api/jobs', {}], ['/api/export/jobs?site=ie', BUILD]]) {
    const { seen, pages } = await walk(w, base, headers, 5);
    assert.equal(pages, 5);
    assert.equal(seen.length, 23);
    assert.equal(new Set(seen).size, 23, `${base}: no duplicates`);
    assert.ok(!seen.includes('ie:strat:8999'));
  }
  const all = await (await w.fetch(get('greenjobs.ie', '/api/jobs'))).json();
  assert.equal(all.jobs.length, 23);
  assert.equal(all.next, null);
});

test('#22 limit is clamped (floor 1, ceiling 1000, default 500); bad or unknown cursors are 400', async () => {
  const w = await makeWorld();
  seedMany(w, 3);
  const page = async (q) => (await w.fetch(get('greenjobs.ie', `/api/jobs${q}`))).json();
  assert.equal((await page('?limit=0')).jobs.length, 1);
  assert.equal((await page('?limit=-5')).jobs.length, 1);
  assert.equal((await page('?limit=abc')).jobs.length, 3);
  const { parsePage, PAGE_DEFAULT, PAGE_MAX } = await workerModule('routes/public.js');
  assert.equal(parsePage(new URLSearchParams('limit=99999')).limit, PAGE_MAX);
  assert.equal(parsePage(new URLSearchParams('')).limit, PAGE_DEFAULT);
  assert.equal([PAGE_DEFAULT, PAGE_MAX].join(), '500,1000');
  for (const bad of ['..%2f..%2fetc', 'ie:strat:%252e%252e', "x' OR 1=1 --"]) {
    assert.equal((await w.fetch(get('greenjobs.ie', `/api/jobs?after=${encodeURIComponent(bad)}`))).status, 400, bad);
    assert.equal((await w.fetch(get('greenjobs.ie', `/api/export/jobs?site=ie&after=${encodeURIComponent(bad)}`, BUILD))).status, 400, bad);
  }
  assert.equal((await w.fetch(get('greenjobs.ie', '/api/jobs?after=ie:strat:424242'))).status, 400, 'unknown cursor');
});

// ---------- #21 timeout + delivery.failed alert channel ----------

const hangingFetch = (calls) => (url, init) => {
  calls.push(url);
  // AbortSignal.timeout's timer is unref'd in Node; a ref'd timer keeps the test's event loop alive until it fires.
  const keepAlive = setTimeout(() => {}, 2000);
  return new Promise((_, reject) => init.signal.addEventListener('abort', () => { clearTimeout(keepAlive); reject(init.signal.reason); }));
};
const LIVE = { DRY_RUN: '0', LIVE_CONFIRM: 'send-applications' };

async function storedApp(env) {
  const w = await makeWorld();
  seedJob(w, { id: 'ie:strat:1' });
  assert.equal((await w.fetch(applyRequest({ job_id: 'ie:strat:1' }))).status, 201); // dry run: stored as 'dry_run'
  w.db.sqlite.prepare("UPDATE applications SET delivery_status = 'pending'").run();
  Object.assign(w.env, env);
  return { w, appId: w.db.q('SELECT id FROM applications')[0].id };
}

test('#21 a hung provider times out: delivery_status failed, one delivery.failed row (ids only), one alert', async () => {
  const { w, appId } = await storedApp({ ...LIVE, OPS_ALERT_EMAIL: 'ops@greenjobs.ie' });
  const calls = [];
  const sent = [];
  const transport = async (payload, env, key) => {
    if (key.startsWith('alert:')) {
      sent.push(payload);
      return { ok: true, status: 200 };
    }
    return resendTransport(hangingFetch(calls), { timeoutMs: 20 })(payload, env, key);
  };
  const mailer = createMailer({ transport });
  const job = { id: 'ie:strat:1', title: 'Senior Wind Engineer' };
  const t0 = Date.now();
  assert.equal(await deliverApplication(w.env, mailer, appId, job, null, NOW), 'failed');
  assert.ok(Date.now() - t0 < 5000, 'aborted by the timeout');
  assert.equal(w.db.q('SELECT delivery_status FROM applications')[0].delivery_status, 'failed');
  const rows = w.db.q("SELECT entity_id, detail_json FROM audit_log WHERE action = 'delivery.failed'");
  assert.deepEqual(rows, [{ entity_id: appId, detail_json: '{"reason":"timeout"}' }]);
  assert.equal(sent.length, 1);
  assert.deepEqual(sent[0].to, ['ops@greenjobs.ie']);
  assert.doesNotMatch(JSON.stringify(sent[0]), /aoife|Aoife|Wind/, 'alert carries ids only');
  assert.equal(w.db.q("SELECT COUNT(*) AS n FROM audit_log WHERE action = 'mail.send' AND entity = 'alert'")[0].n, 1, 'alert is on the cost ledger');
  // A cron retry that fails again adds no second row and no second alert.
  assert.equal(await deliverApplication(w.env, mailer, appId, job, null, NOW), 'failed');
  assert.equal(w.db.q("SELECT COUNT(*) AS n FROM audit_log WHERE action = 'delivery.failed'")[0].n, 1);
  assert.equal(sent.length, 1);
});

test('#21 the alert counts against MAIL_DAILY_CAP; no OPS_ALERT_EMAIL = audit row only', async () => {
  const { w, appId } = await storedApp({ ...LIVE, OPS_ALERT_EMAIL: '' });
  const keys = [];
  const mailer = createMailer({ transport: async (p, e, key) => { keys.push(key); return { ok: false, status: 500 }; } });
  assert.equal(await deliverApplication(w.env, mailer, appId, { id: 'ie:strat:1', title: 'x' }, null, NOW), 'failed');
  assert.deepEqual(keys, [appId], 'no alert without OPS_ALERT_EMAIL');
  assert.equal(w.db.q("SELECT detail_json FROM audit_log WHERE action = 'delivery.failed'")[0].detail_json, '{"reason":"provider"}');

  const db = new FakeD1();
  const env = baseEnv({ ...LIVE, DB: db, OPS_ALERT_EMAIL: 'ops@greenjobs.ie', MAIL_DAILY_CAP: '1' });
  db.sqlite.prepare("INSERT INTO audit_log (at, actor, action, entity, entity_id, request_id) VALUES ('2026-11-07T08:00:00Z', 'system', 'mail.send', 'application', 'ie:apply:earlier', 'mail:ie:apply:earlier')").run();
  const k2 = [];
  const m2 = createMailer({ transport: async (p, e, key) => { k2.push(key); return { ok: true, status: 200 }; } });
  assert.deepEqual(await m2.deliver(env, db, {}, { idempotencyKey: 'ie:apply:cap', now: NOW }), { status: 'failed', reason: 'daily_cap' });
  assert.deepEqual(k2, [], 'cap reached: neither the application nor the alert is sent');
  assert.equal(db.q("SELECT COUNT(*) AS n FROM audit_log WHERE action = 'delivery.failed'")[0].n, 1);
});

test('#21 dry run: no send, no alert, no delivery.failed row, even with OPS_ALERT_EMAIL set', async () => {
  const db = new FakeD1();
  const env = baseEnv({ DB: db, OPS_ALERT_EMAIL: 'ops@greenjobs.ie' }); // DRY_RUN=1
  const keys = [];
  const mailer = createMailer({ transport: async (p, e, key) => { keys.push(key); return { ok: false }; } });
  assert.deepEqual(await mailer.deliver(env, db, {}, { idempotencyKey: 'ie:apply:x', now: NOW }), { status: 'dry_run' });
  assert.deepEqual(keys, []);
  assert.equal(db.q('SELECT COUNT(*) AS n FROM audit_log')[0].n, 0);
});

test('#21 resendTransport passes an AbortSignal with the default 10 s timeout', async () => {
  let init;
  const { SEND_TIMEOUT_MS } = await workerModule('mail.js');
  await resendTransport(async (u, i) => { init = i; return { ok: true, status: 200 }; })({}, { RESEND_API_KEY: 'k' }, 'id');
  assert.ok(init.signal instanceof AbortSignal);
  assert.equal(SEND_TIMEOUT_MS, 10000);
});

// ---------- #6 zero-byte CV ----------

test('#6 a named zero-byte CV is 400 cv_empty; an unnamed empty part (no file chosen) is no CV', async () => {
  const w = await makeWorld();
  seedJob(w, { id: 'ie:strat:1' });
  const r = await w.fetch(applyRequest({ job_id: 'ie:strat:1' }, { cv: new Uint8Array(0), cvName: 'cv.pdf' }));
  assert.equal(r.status, 400);
  assert.deepEqual(await r.json(), { error: 'cv_empty' });
  assert.equal(w.db.q('SELECT COUNT(*) AS n FROM applications')[0].n, 0);
  assert.equal(w.r2.objects.size, 0);
  const fd = new FormData();
  for (const [k, v] of Object.entries({ job_id: 'ie:strat:1', name: 'Aoife Byrne', email: 'aoife@example.ie', consent: 'yes', website: '', ts: String(NOW.getTime() - 60_000) })) fd.append(k, v);
  fd.append('cv', new File([], '', { type: 'application/octet-stream' }));
  const blank = await w.fetch(new Request('https://greenjobs.ie/api/apply', { method: 'POST', body: fd, headers: { 'CF-Connecting-IP': '203.0.113.10' } }));
  assert.equal(blank.status, 201, 'browser blank file input');
  assert.equal(w.db.q('SELECT cv_key FROM applications')[0].cv_key, null);
  assert.ok(PDF_BYTES.length > 0);
});
