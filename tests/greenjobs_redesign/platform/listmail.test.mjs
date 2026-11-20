// Job alerts + newsletter (platform_worker/src/listmail/). Offline: FakeD1 (schema.sql + migration 0004), a
// recording mail transport, a fixed clock. Every guard is proven to fire.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { REPO, UPSERTS_PATH, adminRequest, makeWorld, seedJob, workerModule } from './helpers.mjs';

const MIGRATION = readFileSync(resolve(REPO, 'deliverables/greenjobs_migration_2026-11-06/build/d1/migrations/0004_job_alerts_newsletter.sql'), 'utf8');
const { signLink, verifyLink, isoWeek } = await workerModule('listmail/core.js');
const { jobMatches, canonicalJson } = await workerModule('listmail/alerts.js');
const { MEASURE_KEYS } = await workerModule('listmail/measures.js');

const KEY = 'test-signing-key-0123456789abcdef-not-real';
const LIVE = {
  DRY_RUN: '0', LIVE_CONFIRM: 'send-applications', ALERTS_ENABLED: '1', NEWSLETTER_ENABLED: '1',
  LIST_MAIL_SIGNING_KEY: KEY, LIST_FROM_IE: 'GreenJobs.ie <alerts@mail.greenjobs.ie>', LIST_FROM_UK: 'GreenJobs.co.uk <alerts@mail.greenjobs.co.uk>',
};
const DRY = { ...LIVE, DRY_RUN: '1' };
const MONDAY = '2026-11-09T08:00:00Z'; // digest window opens Monday 07:00 UTC
const IMPORT_ALERT_SQL = readFileSync(UPSERTS_PATH, 'utf8').replace(/--[^\n]*/g, '').split(';').map((x) => x.trim()).find((x) => x.startsWith('INSERT INTO alert_subscriptions'));

async function world(env = LIVE) {
  const w = await makeWorld(env);
  w.db.sqlite.exec(MIGRATION);
  w.db.sqlite.exec(MIGRATION); // idempotent
  w.cron = () => w.handler.scheduled({}, w.env, {});
  w.at = (iso) => { w.clock.now = new Date(iso); };
  return w;
}

const json = (host, path, body, ip = '198.51.100.20') =>
  new Request(`https://${host}${path}`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'CF-Connecting-IP': ip }, body: JSON.stringify(body) });
const signup = (w, body, host = 'greenjobs.ie', ip) => w.fetch(json(host, '/api/alerts', { consent: true, ...body }, ip));
const form = (url, fields) =>
  new Request(url, { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body: new URLSearchParams(fields).toString() });
const linkFrom = (mail, kind) => {
  const m = new RegExp(`(https://[^\\s]+/api/(?:alerts|newsletter)/${kind}\\?t=[A-Za-z0-9_.-]+)`).exec(mail.payload.text);
  assert.ok(m, `no ${kind} link in mail`);
  return m[1];
};
const tokenOf = (url) => new URL(url).searchParams.get('t');
const confirmVia = async (w, mail, channel = 'alerts') => w.fetch(form(`https://greenjobs.ie/api/${channel}/confirm`, { t: tokenOf(linkFrom(mail, 'confirm')) }));
const sub = (w, email) => w.db.q('SELECT * FROM alert_subscriptions WHERE email_norm = ?1 ORDER BY id', email);
const ledger = (w, kind) => w.db.q('SELECT * FROM list_mail_ledger WHERE kind = ?1 ORDER BY key', kind);

function seedCandidate(w, email, { marketing = 1, consent = 1, site = 'ie' } = {}) {
  w.db.sqlite.prepare(`INSERT INTO candidates (id, site, source, source_id, email_norm, consent_marketing, strategies_consent, created_at, updated_at)
    VALUES (?1, ?2, 'strategies', ?3, ?4, ?5, ?6, 't', 't')`).run(`${site}:strat:c-${email}`, site, `c-${email}`, email, marketing, consent);
}
let importN = 0;
function seedImportedAlert(w, email, query = { keywords: 'wind' }, site = 'ie') {
  importN++;
  const qjson = canonicalJson(query);
  // exactly the importer's upsert (upserts.sql): always 'pending', an unsubscribe is never undone
  w.db.sqlite.prepare(IMPORT_ALERT_SQL).run(`${site}:strat:alert-${importN}-${email}`, site, email, qjson, `h${importN}-${qjson}`, 'weekly', null, null, null, '2026-11-01T00:00:00Z');
  return `${site}:strat:alert-${importN}-${email}`;
}
async function confirmedAlert(w, email, query = { keywords: 'wind' }) {
  const before = w.mail.calls.length;
  assert.equal((await signup(w, { email, ...query }, 'greenjobs.ie', `203.0.113.${(before % 200) + 1}`)).status, 202);
  const mail = w.mail.calls[before];
  assert.equal((await confirmVia(w, mail)).status, 200);
  return sub(w, email)[0];
}

// ---------- double opt-in ----------

test('alerts: double opt-in: pending until the signed link is POSTed; GET only shows a button; link is one-time', async () => {
  const w = await world();
  const r = await signup(w, { email: ' Aoife@Example.ie ', keywords: 'wind engineer', sectors: ['Wind'], region: 'Cork', job_type: 'Permanent' });
  assert.equal(r.status, 202);
  assert.deepEqual(await r.json(), { ok: true, next: 'check_email' });
  assert.equal(w.mail.calls.length, 1);
  const s0 = sub(w, 'aoife@example.ie')[0];
  assert.equal(s0.status, 'pending');
  assert.deepEqual(JSON.parse(s0.query_json), { job_type: 'Permanent', keywords: 'wind engineer', region: 'Cork', sectors: ['Wind'] });
  assert.ok(s0.confirm_token_hash && !s0.confirm_token_hash.includes('.'), 'only a hash of the token is stored');

  const link = linkFrom(w.mail.calls[0], 'confirm');
  const page = await w.fetch(new Request(link));
  assert.equal(page.status, 200);
  assert.match(await page.text(), /<form method="post" action="\/api\/alerts\/confirm">/);
  assert.equal(sub(w, 'aoife@example.ie')[0].status, 'pending', 'a link scanner GET cannot confirm');

  const ok = await w.fetch(form('https://greenjobs.ie/api/alerts/confirm', { t: tokenOf(link) }));
  assert.equal(ok.status, 200);
  const s1 = sub(w, 'aoife@example.ie')[0];
  assert.equal(s1.status, 'active');
  assert.equal(s1.consent_at, '2026-11-07T10:00:00Z');
  assert.equal(s1.confirm_token_hash, null, 'one-time: the hash is cleared');
  assert.match(await (await w.fetch(form('https://greenjobs.ie/api/alerts/confirm', { t: tokenOf(link) }))).text(), /Already confirmed/);
  // a repeat sign-up for an active alert sends nothing
  await signup(w, { email: 'aoife@example.ie', keywords: 'wind engineer', sectors: ['Wind'], region: 'Cork', job_type: 'Permanent' }, 'greenjobs.ie', '203.0.113.50');
  assert.equal(w.mail.calls.length, 1);
});

test('alerts: sign-up input guards: consent, email, JSON, honeypot, per-IP rate limit, 3 confirmations per address per day', async () => {
  const w = await world();
  assert.equal((await w.fetch(json('greenjobs.ie', '/api/alerts', { email: 'a@b.ie' }))).status, 400);
  assert.equal((await signup(w, { email: 'not-an-email' })).status, 400);
  assert.equal((await signup(w, { email: 'a@b.ie', sectors: ['1', '2', '3', '4', '5', '6'] })).status, 400);
  assert.equal((await w.fetch(new Request('https://greenjobs.ie/api/alerts', { method: 'POST', body: 'x' }))).status, 415);
  assert.equal((await signup(w, { email: 'bot@b.ie', website: 'http://spam' }, 'greenjobs.ie', '203.0.113.77')).status, 202);
  assert.equal(w.mail.calls.length, 0, 'honeypot: accepted, nothing sent');
  for (let i = 0; i < 5; i++) await signup(w, { email: `p${i}@b.ie` }, 'greenjobs.ie', '203.0.113.88');
  assert.equal((await signup(w, { email: 'p9@b.ie' }, 'greenjobs.ie', '203.0.113.88')).status, 429);
  const before = w.mail.calls.length;
  for (let i = 0; i < 5; i++) await signup(w, { email: 'victim@b.ie', keywords: `k${i}` }, 'greenjobs.ie', `192.0.2.${i + 1}`);
  assert.equal(w.mail.calls.length - before, 3, 'mail-bomb guard: 3 confirmation mails per address per day');
  await signup(w, { email: 'victim@b.ie', keywords: 'k0' }, 'greenjobs.ie', '192.0.2.99');
  assert.equal(w.mail.calls.length - before, 3, 'same alert twice in a day: no second mail, first link stays valid');
});

test('alerts: signed-link tampering is rejected (payload, signature, foreign key, kind swap)', async () => {
  const w = await world();
  await signup(w, { email: 'tamper@example.ie', keywords: 'solar' });
  const t = tokenOf(linkFrom(w.mail.calls[0], 'confirm'));
  const [p, s] = t.split('.');
  const flip = (x) => x.slice(0, -2) + (x.slice(-2, -1) === 'A' ? 'B' : 'A') + x.slice(-1);
  const forged = await signLink('another-secret-0123456789abcdef-xyz', ['ac', sub(w, 'tamper@example.ie')[0].id, 9999999999, 'n']);
  const other = Buffer.from(Buffer.from(p, 'base64url').toString().replace(':gj:', ':strat:')).toString('base64url');
  assert.notEqual(other, p);
  for (const bad of [`${flip(p)}.${s}`, `${p}.${flip(s)}`, `${other}.${s}`, forged, 'garbage', '']) {
    const r = await w.fetch(form('https://greenjobs.ie/api/alerts/confirm', { t: bad }));
    assert.equal(r.status, 400, `rejected: ${bad.slice(0, 20)}`);
  }
  const unsubAsConfirm = tokenOf(linkFrom(w.mail.calls[0], 'unsubscribe'));
  assert.equal((await w.fetch(form('https://greenjobs.ie/api/alerts/confirm', { t: unsubAsConfirm }))).status, 400);
  assert.equal((await w.fetch(new Request(`https://greenjobs.ie/api/alerts/unsubscribe?t=${flip(unsubAsConfirm)}`))).status, 400);
  assert.equal(sub(w, 'tamper@example.ie')[0].status, 'pending', 'nothing changed');
  assert.deepEqual(await verifyLink(KEY, t).then((x) => x[0]), 'ac');
});

test('alerts: expiry: link expires and unconfirmed sign-ups are deleted after 30 days', async () => {
  const w = await world(DRY);
  await signup(w, { email: 'late@example.ie' });
  await signup(w, { email: 'ontime@example.ie' }, 'greenjobs.ie', '203.0.113.2');
  assert.equal(w.mail.calls.length, 0, 'dry run: transport never called');
  assert.equal(ledger(w, 'confirm').length, 2);
  assert.ok(ledger(w, 'confirm').every((r) => r.status === 'dry_run'));
  // dry run still issues a valid token; read it back from the ledger-built payload via a live world instead:
  const live = await world();
  await signup(live, { email: 'late@example.ie' });
  const link = linkFrom(live.mail.calls[0], 'confirm');
  live.at('2026-12-08T10:00:01Z'); // 31 days later
  assert.equal((await live.fetch(form('https://greenjobs.ie/api/alerts/confirm', { t: tokenOf(link) }))).status, 410);
  assert.equal((await live.fetch(new Request(link))).status, 410);
  await live.cron();
  assert.equal(sub(live, 'late@example.ie').length, 0, 'expired pending row deleted');
  assert.equal(live.db.q('SELECT COUNT(*) AS n FROM alert_meta')[0].n, 0);
  // 29 days: still there
  w.at('2026-12-06T10:00:00Z');
  await w.cron();
  assert.equal(sub(w, 'ontime@example.ie').length, 1);
});

// ---------- imported subscribers ----------

test('import: ONE re-confirmation per person, consent-gated (Marketing=0, Consent=0, no candidate row = no mail)', async () => {
  const w = await world();
  seedCandidate(w, 'keen@example.ie');
  const a = seedImportedAlert(w, 'keen@example.ie', { keywords: 'wind', label: 'Wind jobs' });
  const b = seedImportedAlert(w, 'keen@example.ie', { sectors: ['Solar'] });
  seedCandidate(w, 'nomarketing@example.ie', { marketing: 0 });
  seedImportedAlert(w, 'nomarketing@example.ie');
  seedCandidate(w, 'noconsent@example.ie', { consent: 0 });
  seedImportedAlert(w, 'noconsent@example.ie');
  seedImportedAlert(w, 'orphan@example.ie');
  await w.cron();
  assert.equal(w.mail.calls.length, 1, 'one mail, to the one consenting person, covering both searches');
  const m = w.mail.calls[0];
  assert.deepEqual(m.payload.to, ['keen@example.ie']);
  assert.match(m.payload.text, /Wind jobs/);
  assert.match(m.payload.text, /Solar/);
  await w.cron();
  w.at('2026-11-20T10:00:00Z');
  await w.cron();
  assert.equal(w.mail.calls.length, 1, 're-runs never re-send');
  assert.equal(ledger(w, 'reconfirm').length, 1);
  assert.equal((await confirmVia(w, m)).status, 200);
  assert.deepEqual(sub(w, 'keen@example.ie').map((s) => s.status), ['active', 'active']);
  assert.ok([a, b].every((id) => sub(w, 'keen@example.ie').some((s) => s.id === id)));
});

test('import: no reply in 30 days -> deleted, suppressed, and a later re-import is never mailed', async () => {
  const w = await world();
  seedCandidate(w, 'silent@example.ie');
  seedImportedAlert(w, 'silent@example.ie');
  await w.cron();
  assert.equal(w.mail.calls.length, 1);
  w.at('2026-12-08T10:00:01Z');
  await w.cron();
  assert.equal(sub(w, 'silent@example.ie').length, 0);
  assert.equal(w.db.q("SELECT COUNT(*) AS n FROM list_suppression WHERE reason = 'reconfirm_expired'")[0].n, 1);
  assert.equal(w.db.q("SELECT COUNT(*) AS n FROM list_suppression WHERE email_hash LIKE '%silent%'")[0].n, 0, 'only a hash is kept');
  seedImportedAlert(w, 'silent@example.ie', { keywords: 'other' });
  await w.cron();
  w.at('2026-12-20T10:00:00Z');
  await w.cron();
  assert.equal(w.mail.calls.length, 1, 'never mailed again');
});

test('import: a dry run records the re-confirmation but never starts the 30-day deletion clock', async () => {
  const w = await world(DRY);
  seedCandidate(w, 'dry@example.ie');
  seedImportedAlert(w, 'dry@example.ie');
  await w.cron();
  await w.cron();
  assert.equal(w.mail.calls.length, 0);
  assert.deepEqual(ledger(w, 'reconfirm').map((r) => r.status), ['dry_run']);
  w.at('2027-01-30T10:00:00Z');
  await w.cron();
  assert.equal(sub(w, 'dry@example.ie').length, 1, 'not deleted');
  w.env.DRY_RUN = '0'; // go live: the dry-run row is claimed once and really sent
  await w.cron();
  await w.cron();
  assert.equal(w.mail.calls.length, 1);
  assert.deepEqual(ledger(w, 'reconfirm').map((r) => r.status), ['sent']);
});

// ---------- weekly digest ----------

test('digest: matching new jobs only, one per (subscriber, week), empty digests skipped, re-runs never double-send', async () => {
  const w = await world();
  const s = await confirmedAlert(w, 'digest@example.ie', { keywords: 'wind', sectors: ['Wind'] });
  const mailsAfterConfirm = w.mail.calls.length;
  seedJob(w, { id: 'ie:strat:old', title: 'Wind Tech (old)', posted_at: '2026-11-01T09:00:00Z' });
  seedJob(w, { id: 'ie:strat:new', title: 'Wind Turbine Engineer', posted_at: '2026-11-08T09:00:00Z' });
  seedJob(w, { id: 'ie:strat:solar', title: 'Solar Lead', sectors: ['Solar'], summary: 'solar', description: 'Solar farm delivery lead, plenty of detail.', posted_at: '2026-11-08T09:00:00Z' });
  seedJob(w, { id: 'uk:strat:wind', site: 'uk', title: 'UK Wind Engineer', posted_at: '2026-11-08T09:00:00Z' });
  w.at('2026-11-09T06:59:00Z');
  await w.cron();
  assert.equal(w.mail.calls.length, mailsAfterConfirm, 'before the Monday window: nothing');
  w.at(MONDAY);
  await w.cron();
  assert.equal(w.mail.calls.length, mailsAfterConfirm + 1);
  const d = w.mail.calls.at(-1).payload;
  assert.match(d.text, /Wind Turbine Engineer/);
  assert.doesNotMatch(d.text, /old\)|Solar Lead|UK Wind/);
  assert.equal(w.mail.calls.at(-1).key, `list:digest:${s.id}:${isoWeek(new Date(MONDAY))}`, 'provider idempotency key = ledger key');
  w.at('2026-11-09T09:00:00Z');
  await w.cron();
  w.at('2026-11-12T09:00:00Z');
  await w.cron();
  assert.equal(w.mail.calls.length, mailsAfterConfirm + 1, 'same week: never again');
  w.at('2026-11-16T08:00:00Z');
  await w.cron();
  assert.equal(w.mail.calls.length, mailsAfterConfirm + 1, 'next week with nothing new: no mail');
  assert.deepEqual(ledger(w, 'digest').map((r) => [r.period, r.status]), [['2026-W46', 'sent'], ['2026-W47', 'empty']]);
  seedJob(w, { id: 'ie:strat:new2', title: 'Wind Analyst', posted_at: '2026-11-17T09:00:00Z' });
  w.at('2026-11-23T08:00:00Z');
  await w.cron();
  assert.equal(w.mail.calls.length, mailsAfterConfirm + 2);
  assert.match(w.mail.calls.at(-1).payload.text, /Wind Analyst/);
  assert.doesNotMatch(w.mail.calls.at(-1).payload.text, /Wind Turbine Engineer/, 'already sent last time');
});

test('digest: no mail to pending, unsubscribed or suppressed subscribers', async () => {
  const w = await world();
  await signup(w, { email: 'pending@example.ie', keywords: 'wind' });
  const s = await confirmedAlert(w, 'leaver@example.ie');
  seedCandidate(w, 'nomkt@example.ie', { marketing: 0 });
  seedImportedAlert(w, 'nomkt@example.ie');
  seedJob(w, { title: 'Wind Engineer', posted_at: '2026-11-08T09:00:00Z' });
  const unsub = linkFrom(w.mail.calls.find((c) => c.payload.to[0] === 'leaver@example.ie'), 'unsubscribe');
  assert.equal((await w.fetch(new Request(unsub))).status, 200);
  assert.equal(sub(w, 'leaver@example.ie')[0].status, 'unsubscribed');
  const before = w.mail.calls.length;
  w.at(MONDAY);
  await w.cron();
  assert.equal(w.mail.calls.length, before, 'nobody eligible');
  assert.ok(s.id);
});

test('digest: dry run sends nothing and records dry_run; the job matcher handles imported query shapes', async () => {
  const w = await world();
  await confirmedAlert(w, 'dd@example.ie');
  w.env.DRY_RUN = '1';
  seedJob(w, { title: 'Wind Engineer', posted_at: '2026-11-08T09:00:00Z' });
  const before = w.mail.calls.length;
  w.at(MONDAY);
  await w.cron();
  await w.cron();
  assert.equal(w.mail.calls.length, before);
  assert.deepEqual(ledger(w, 'digest').map((r) => r.status), ['dry_run']);
  const job = { title: 'Senior Wind Engineer', summary: '', description: 'x', employer: 'Acme', sectors_json: '["Wind"]', region: 'Munster', location: 'Cork', job_type: 'Permanent', sal_max: 50000 };
  assert.ok(jobMatches(job, { category: 'wind', region: 'cork', sal_min: 40000, vicinity: 'ignored', label: 'x' }));
  assert.ok(!jobMatches(job, { sal_min: 60000 }));
  assert.ok(!jobMatches(job, { keywords: 'wind solar' }));
  assert.ok(jobMatches(job, { keywords: 'WIND, engineer', job_type: 'perm', region: 'Munster' }));
  assert.ok(!jobMatches(job, { sectors: ['Solar'] }));
});

// ---------- unsubscribe + headers ----------

test('every list mail: board sender, text + HTML, List-Unsubscribe + One-Click headers, visible link, no pixel', async () => {
  const w = await world();
  await confirmedAlert(w, 'h@example.ie');
  seedCandidate(w, 'r@example.ie');
  seedImportedAlert(w, 'r@example.ie');
  seedJob(w, { title: 'Wind Engineer', posted_at: '2026-11-08T09:00:00Z' });
  await signup(w, { email: 'uk@example.co.uk' }, 'greenjobs.co.uk', '203.0.113.200');
  await w.fetch(json('greenjobs.ie', '/api/newsletter', { email: 'n@example.ie', consent: true }, '203.0.113.201'));
  w.at(MONDAY);
  await w.cron();
  const kinds = new Set(w.mail.calls.map((c) => c.key.split(':')[1]));
  assert.deepEqual([...kinds].sort(), ['confirm', 'digest', 'nl_confirm', 'reconfirm']);
  for (const { payload: p } of w.mail.calls) {
    const uk = p.to[0].endsWith('.co.uk');
    assert.equal(p.from, uk ? 'GreenJobs.co.uk <alerts@mail.greenjobs.co.uk>' : 'GreenJobs.ie <alerts@mail.greenjobs.ie>');
    assert.match(p.headers['List-Unsubscribe'], uk ? /^<https:\/\/greenjobs\.co\.uk\/api\/(alerts|newsletter)\/unsubscribe\?t=/ : /^<https:\/\/greenjobs\.ie\/api\/(alerts|newsletter)\/unsubscribe\?t=/);
    assert.equal(p.headers['List-Unsubscribe-Post'], 'List-Unsubscribe=One-Click');
    assert.ok(p.text.includes(p.headers['List-Unsubscribe'].slice(1, -1)), 'visible link in text');
    assert.ok(p.html.includes('Unsubscribe</a>'));
    assert.doesNotMatch(p.html, /<img/i, 'no tracking pixel');
  }
});

test('unsubscribe: RFC 8058 one-click POST is immediate and permanent; re-sign-up and re-import cannot undo it', async () => {
  const w = await world();
  const s = await confirmedAlert(w, 'gone@example.ie', { keywords: 'wind' });
  await confirmedAlert(w, 'gone@example.ie', { keywords: 'solar' });
  const u = w.mail.calls[0].payload.headers['List-Unsubscribe'].slice(1, -1);
  const r = await w.fetch(form(u, { 'List-Unsubscribe': 'One-Click' }));
  assert.equal(r.status, 200);
  assert.deepEqual(sub(w, 'gone@example.ie').map((x) => x.status), ['unsubscribed', 'unsubscribed'], 'every alert for that address');
  const before = w.mail.calls.length;
  assert.equal((await signup(w, { email: 'gone@example.ie', keywords: 'hydrogen' }, 'greenjobs.ie', '192.0.2.200')).status, 202);
  assert.equal(w.mail.calls.length, before, 'suppressed: accepted silently, nothing sent');
  w.db.sqlite.prepare(IMPORT_ALERT_SQL).run(s.id, 'ie', 'gone@example.ie', s.query_json, s.query_hash, 'weekly', null, null, null, 'z');
  assert.equal(sub(w, 'gone@example.ie').find((x) => x.id === s.id).status, 'unsubscribed', 'import upsert never reactivates');
  seedCandidate(w, 'gone@example.ie');
  seedImportedAlert(w, 'gone@example.ie', { keywords: 'new' });
  await w.cron();
  assert.equal(w.mail.calls.length, before, 'no re-confirmation to an unsubscribed address');
});

// ---------- guards ----------

test('guards: per-run cap, daily list cap and the shared MAIL_DAILY_CAP all stop sending', async () => {
  const w = await world({ ...LIVE, LIST_MAIL_RUN_CAP: '2', LIST_MAIL_DAILY_CAP: '5' });
  for (let i = 0; i < 6; i++) {
    seedCandidate(w, `p${i}@example.ie`);
    seedImportedAlert(w, `p${i}@example.ie`);
  }
  const out = await w.cron();
  assert.equal(w.mail.calls.length, 2, 'run cap');
  assert.equal(out.alerts.reconfirm.sent, 2);
  await w.cron();
  await w.cron();
  assert.equal(w.mail.calls.length, 5, 'daily cap (5) stops the third run at 1');
  await w.cron();
  assert.equal(w.mail.calls.length, 5);
  w.at('2026-11-08T10:00:00Z');
  await w.cron();
  assert.equal(w.mail.calls.length, 6, 'next day resumes; each person still mailed once');
  assert.equal(new Set(w.mail.calls.map((c) => c.payload.to[0])).size, 6);

  const w2 = await world({ ...LIVE, MAIL_DAILY_CAP: '1' });
  seedCandidate(w2, 'a@example.ie');
  seedImportedAlert(w2, 'a@example.ie');
  seedCandidate(w2, 'b@example.ie');
  seedImportedAlert(w2, 'b@example.ie');
  await w2.cron();
  assert.equal(w2.mail.calls.length, 1, 'MAIL_DAILY_CAP is shared with application mail');
  assert.equal((await signup(w2, { email: 'c@example.ie' })).status, 503, 'sign-up over budget: try later');
});

test('guards: a failed provider call is retried once, then logged; later runs retry until 4 attempts, then stop', async () => {
  const w = await world();
  w.mail.ok = false;
  seedCandidate(w, 'flaky@example.ie');
  seedImportedAlert(w, 'flaky@example.ie');
  await w.cron();
  assert.equal(w.mail.calls.length, 2, 'one retry in the same run');
  assert.equal(w.mail.calls[0].key, w.mail.calls[1].key, 'same idempotency key on the retry');
  assert.deepEqual(ledger(w, 'reconfirm').map((r) => [r.status, r.attempts, r.reason]), [['failed', 2, 'provider']]);
  assert.equal(w.db.q("SELECT COUNT(*) AS n FROM audit_log WHERE action = 'list.mail_failed'")[0].n, 1);
  await w.cron();
  await w.cron();
  assert.equal(w.mail.calls.length, 4, 'attempts capped at 4');
  w.mail.ok = true;
  await w.cron();
  assert.equal(w.mail.calls.length, 4);
  // transport throwing (timeout) is handled the same way
  const w2 = await world();
  w2.handler = (await workerModule('index.js')).createHandler({ mailTransport: async () => { throw Object.assign(new Error('t'), { name: 'TimeoutError' }); }, now: () => new Date(w2.clock.now) });
  seedCandidate(w2, 't@example.ie');
  seedImportedAlert(w2, 't@example.ie');
  await w2.handler.scheduled({}, w2.env, {});
  assert.deepEqual(ledger(w2, 'reconfirm').map((r) => r.reason), ['timeout']);
});

test('guards: flags off or no signing key = nothing runs and nothing is sent', async () => {
  const off = await world({ ...LIVE, ALERTS_ENABLED: '0', NEWSLETTER_ENABLED: '0' });
  seedCandidate(off, 'x@example.ie');
  seedImportedAlert(off, 'x@example.ie');
  assert.deepEqual(await off.cron(), { retried: 0, failed: 0 });
  assert.equal((await signup(off, { email: 'x@example.ie' })).status, 404);
  const nokey = await world({ ...LIVE, LIST_MAIL_SIGNING_KEY: 'short' });
  seedCandidate(nokey, 'x@example.ie');
  seedImportedAlert(nokey, 'x@example.ie');
  const out = await nokey.cron();
  assert.equal(out.alerts.skipped, 'no_signing_key');
  assert.equal((await signup(nokey, { email: 'x@example.ie' })).status, 503);
  assert.equal(off.mail.calls.length + nokey.mail.calls.length, 0);
  const noSender = await world({ ...LIVE, LIST_FROM_IE: '' });
  seedCandidate(noSender, 'x@example.ie');
  seedImportedAlert(noSender, 'x@example.ie');
  await noSender.cron();
  assert.equal(noSender.mail.calls.length, 0, 'no sender identity: never sent from a blank From');
  assert.deepEqual(ledger(noSender, 'reconfirm').map((r) => r.reason), ['no_sender']);
});

// ---------- measures ----------

test('measures: documented keys, null when unmeasured, counts after live activity, snapshot table written', async () => {
  const off = await world({ ...DRY, ALERTS_ENABLED: '0', NEWSLETTER_ENABLED: '0' });
  const r0 = await off.fetch(await adminRequest('GET', '/api/admin/list-measures'));
  const m0 = (await r0.json()).measures;
  assert.deepEqual(Object.keys(m0), MEASURE_KEYS);
  assert.ok(Object.values(m0).every((v) => v === null));
  const dry = await world(DRY);
  await signup(dry, { email: 'm@example.ie' });
  const md = (await (await dry.fetch(await adminRequest('GET', '/api/admin/list-measures'))).json()).measures;
  assert.equal(md.alerts_pending, 1);
  assert.equal(md.alerts_dry_run_7d, 1);
  assert.equal(md.alerts_sent, null, 'never live: sent is unmeasured, not 0');
  const w = await world();
  await confirmedAlert(w, 'm1@example.ie');
  const s2 = await confirmedAlert(w, 'm2@example.ie');
  await w.fetch(new Request(w.mail.calls[1].payload.headers['List-Unsubscribe'].slice(1, -1)));
  await w.cron();
  const snap = Object.fromEntries(w.db.q('SELECT key, value FROM list_measures').map((r) => [r.key, r.value]));
  assert.equal(snap.alerts_confirmed, 1);
  assert.equal(snap.alerts_unsubscribed, 1);
  assert.equal(snap.alerts_sent, 2);
  assert.equal(snap.newsletter_sent, null);
  assert.ok(s2);
});

// ---------- newsletter ----------

async function nlSubscriber(w, email, ip) {
  const before = w.mail.calls.length;
  assert.equal((await w.fetch(json('greenjobs.ie', '/api/newsletter', { email, consent: true }, ip))).status, 202);
  assert.equal((await confirmVia(w, w.mail.calls[before], 'newsletter')).status, 200);
}

test('newsletter: double opt-in with its own consent; compose, preview, test-to-self required, send once, unsubscribe', async () => {
  const w = await world();
  await nlSubscriber(w, 'reader1@example.ie', '203.0.113.31');
  await nlSubscriber(w, 'reader2@example.ie', '203.0.113.32');
  await w.fetch(json('greenjobs.ie', '/api/newsletter', { email: 'pending@example.ie', consent: true }, '203.0.113.33'));
  await confirmedAlert(w, 'alertonly@example.ie'); // job-alert consent is not newsletter consent
  const job = seedJob(w, { title: 'Featured Wind Role' });
  const emp = w.db.q('SELECT employer_id AS e FROM jobs WHERE id = ?1', job)[0].e;

  const bad = await w.fetch(await adminRequest('POST', '/api/admin/newsletters', { body: { subject: 'Hi', intro: '', jobs: ['nope'] } }));
  assert.equal(bad.status, 400);
  const idem = crypto.randomUUID();
  const body = { subject: 'November on GreenJobs', intro: 'Hello readers.\n\nNew roles below.', jobs: [job], advertisers: [emp] };
  const c1 = await w.fetch(await adminRequest('POST', '/api/admin/newsletters', { body, idem }));
  assert.equal(c1.status, 201);
  const { id } = await c1.json();
  await w.fetch(await adminRequest('POST', '/api/admin/newsletters', { body, idem }));
  assert.equal(w.db.q('SELECT COUNT(*) AS n FROM newsletters')[0].n, 1, 'replayed Idempotency-Key converges');

  const pv = await (await w.fetch(await adminRequest('GET', `/api/admin/newsletters/${encodeURIComponent(id)}/preview`))).json();
  assert.match(pv.text, /Hello readers\.[\s\S]*Featured Wind Role[\s\S]*Acme Renewables/);
  assert.equal(pv.recipients, 2);
  const path = `/api/admin/newsletters/${encodeURIComponent(id)}`;
  assert.equal((await w.fetch(await adminRequest('POST', `${path}/send`, { body: { confirm_subject: body.subject } }))).status, 409, 'test send required');
  const before = w.mail.calls.length;
  const t = await (await w.fetch(await adminRequest('POST', `${path}/test`, { body: {} }))).json();
  assert.equal(t.status, 'sent');
  assert.deepEqual(w.mail.calls.at(-1).payload.to, ['keith@greenjobs.ie'], 'test goes only to the signed-in staff member');
  assert.match(w.mail.calls.at(-1).payload.subject, /^\[TEST\]/);
  assert.equal((await (await w.fetch(await adminRequest('POST', `${path}/test`, { body: {} }))).json()).status, 'already_tested');
  assert.equal((await w.fetch(await adminRequest('POST', `${path}/send`, { body: { confirm_subject: 'wrong' } }))).status, 400);
  assert.equal((await w.fetch(await adminRequest('POST', `${path}/send`, { body: { confirm_subject: body.subject } }))).status, 202);
  assert.equal((await w.fetch(await adminRequest('PUT', path, { body: { ...body, version: 1 } }))).status, 409, 'queued: no more edits');
  assert.equal(w.mail.calls.length, before + 1, 'queueing sends nothing by itself');
  await w.cron();
  await w.cron();
  const sent = w.mail.calls.slice(before + 1).filter((c) => c.key.startsWith('list:newsletter:'));
  assert.deepEqual(sent.map((c) => c.payload.to[0]).sort(), ['reader1@example.ie', 'reader2@example.ie'], 'confirmed newsletter subscribers only, once each');
  assert.equal(w.db.q('SELECT status FROM newsletters')[0].status, 'sent');
  for (const c of sent) assert.equal(c.payload.headers['List-Unsubscribe-Post'], 'List-Unsubscribe=One-Click');

  await w.fetch(form(sent[0].payload.headers['List-Unsubscribe'].slice(1, -1), { 'List-Unsubscribe': 'One-Click' }));
  assert.equal(w.db.q("SELECT COUNT(*) AS n FROM newsletter_subscribers WHERE status = 'unsubscribed'")[0].n, 1);
  assert.equal(sub(w, 'alertonly@example.ie')[0].status, 'active', 'newsletter unsubscribe leaves alerts alone');
});

test('newsletter: dry run stays queued and sends nothing; going live sends each subscriber exactly once; cap applies', async () => {
  const w = await world({ ...LIVE, LIST_MAIL_RUN_CAP: '1' });
  await nlSubscriber(w, 'a@example.ie', '203.0.113.41');
  await nlSubscriber(w, 'b@example.ie', '203.0.113.42');
  w.env.DRY_RUN = '1';
  const r = await w.fetch(await adminRequest('POST', '/api/admin/newsletters', { body: { subject: 'Dry issue', intro: 'Hello.' } }));
  const { id } = await r.json();
  const path = `/api/admin/newsletters/${encodeURIComponent(id)}`;
  assert.equal((await (await w.fetch(await adminRequest('POST', `${path}/test`, { body: {} }))).json()).status, 'dry_run');
  assert.equal((await w.fetch(await adminRequest('POST', `${path}/send`, { body: { confirm_subject: 'Dry issue' } }))).status, 202);
  const before = w.mail.calls.length;
  for (let i = 0; i < 4; i++) await w.cron();
  assert.equal(w.mail.calls.length, before, 'dry run: nothing sent');
  assert.equal(w.db.q('SELECT status FROM newsletters')[0].status, 'queued');
  w.env.DRY_RUN = '0';
  await w.cron();
  assert.equal(w.mail.calls.length, before + 1, 'run cap 1');
  for (let i = 0; i < 3; i++) await w.cron();
  assert.equal(w.mail.calls.length, before + 2);
  assert.equal(w.db.q('SELECT status FROM newsletters')[0].status, 'sent');
});

test('newsletter: flag off hides public and staff routes', async () => {
  const w = await world({ ...LIVE, NEWSLETTER_ENABLED: '0' });
  assert.equal((await w.fetch(json('greenjobs.ie', '/api/newsletter', { email: 'a@b.ie', consent: true }))).status, 404);
  assert.equal((await w.fetch(await adminRequest('GET', '/api/admin/newsletters'))).status, 404);
  assert.equal((await w.fetch(await adminRequest('GET', '/admin/newsletter'))).status, 404);
  const on = await world();
  const page = await on.fetch(await adminRequest('GET', '/admin/newsletter'));
  assert.equal(page.status, 200);
  assert.match(page.headers.get('Content-Security-Policy'), /default-src 'self'/);
  assert.doesNotMatch(await page.text(), /<script>(?!<)/, 'no inline script');
});
