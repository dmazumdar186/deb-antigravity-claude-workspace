// Newsletter (promised advertiser feature, RECORD P15; behind NEWSLETTER_ENABLED="1", dry by default, see core.js).
// Consent is separate from job alerts: own table, own double opt-in, own unsubscribe and suppression reason.
//
// Public:
//   POST /api/newsletter                 {email, consent:true} -> 202 always; one confirmation mail per address per day
//   GET  /api/newsletter/confirm?t=      page with a Confirm button;  POST /api/newsletter/confirm (t in the form body)
//   GET|POST /api/newsletter/unsubscribe?t=   immediate + permanent (newsletter only; alerts are untouched)
// Staff (Cloudflare Access + CSRF + Idempotency-Key, enforced in index.js before these run):
//   GET  /admin/newsletter (+ /admin/newsletter.js)   compose page
//   GET  /api/admin/newsletters                       list for this board
//   POST /api/admin/newsletters                       create draft {subject, intro, jobs:[ids], advertisers:[ids]}
//   PUT  /api/admin/newsletters/:id                   edit draft {..., version}; bumps version
//   GET  /api/admin/newsletters/:id/preview           {subject, text, html, recipients}
//   POST /api/admin/newsletters/:id/test              send to the signed-in staff address (once per version)
//   POST /api/admin/newsletters/:id/send              {confirm_subject}: needs a test of the current version; queues it
// Cron (runNewsletter): sends queued newsletters to active subscribers who consented before queueing, under the
// shared run/day caps; one ledger row per (subscriber, newsletter) so a re-run never double-sends.

import { CONSOLE_CSP, SECURITY_HEADERS, err, intVar, json, nowIso, sha256Hex, todayUtc, uuidFromSeed } from '../util.js';
import { escapeHtml, isValidEmail, normEmail } from '../validate.js';
import {
  CONFIRM_TTL_DAYS, DONE_SQL, addDays, board, channelLive, esc, isSuppressed, ledgerMark, listEmail, newRun, page,
  randomNonce, sendListMail, signLink, signingKey, suppress, verifyLink,
} from './core.js';
import { tokenFrom } from './alerts.js';

const MAX_JOBS = 12;
const MAX_ADVERTISERS = 6;

async function unsubUrl(secret, b, subId) {
  return `${b.base}/api/newsletter/unsubscribe?t=${await signLink(secret, ['nu', subId])}`;
}

// ---------- public ----------

export async function newsletterRoute({ env, site, now, request, cors, rate, transport, path, url, clientKey }) {
  const secret = signingKey(env);
  if (!secret || !env.DB) return err('newsletter_not_configured', 503, cors);
  const b = board(env, site);
  const db = env.DB;
  const method = request.method;

  if (path === '/api/newsletter/unsubscribe' && (method === 'GET' || method === 'POST')) {
    const parts = await verifyLink(secret, await tokenFrom(request, url));
    if (!parts || parts[0] !== 'nu') return page(b, 'Link not valid', '<p>This unsubscribe link is not valid. Reply to the newsletter and we will remove you.</p>', 400);
    await unsubscribeNewsletter(db, parts[1], now);
    if (method === 'POST') return new Response('unsubscribed', { status: 200, headers: { 'Content-Type': 'text/plain', 'Cache-Control': 'no-store' } });
    return page(b, 'You are unsubscribed', '<p>You will not get the newsletter again. This is permanent. Job alerts, if you have any, are not affected.</p>');
  }
  if (path === '/api/newsletter/confirm' && method === 'GET') {
    const t = url.searchParams.get('t') || '';
    const parts = await verifyLink(secret, t);
    if (!parts || parts[0] !== 'nc') return page(b, 'Link not valid', '<p>This confirmation link is not valid.</p>', 400);
    if (Number(parts[2]) * 1000 < now.getTime()) return page(b, 'Link expired', '<p>This link has expired. Sign up again.</p>', 410);
    return page(b, 'Confirm the newsletter', `<form method="post" action="/api/newsletter/confirm"><input type="hidden" name="t" value="${esc(t)}"><button type="submit">Yes, send me the newsletter</button></form>`);
  }
  if (path === '/api/newsletter/confirm' && method === 'POST') {
    const r = await confirmNewsletter(db, secret, await tokenFrom(request, url), now);
    if (r === 'ok') return page(b, 'Subscribed', `<p>Done. You will get the ${esc(b.name)} newsletter. Every issue has a one-click unsubscribe link.</p>`);
    if (r === 'already') return page(b, 'Already subscribed', '<p>You are already subscribed.</p>');
    if (r === 'expired') return page(b, 'Link expired', '<p>This link has expired. Sign up again.</p>', 410);
    return page(b, 'Link not valid', '<p>This confirmation link is not valid or was already used.</p>', 400);
  }
  if (path !== '/api/newsletter') return err('not_found', 404, cors);
  if (method !== 'POST') return err('method_not_allowed', 405, cors);
  if (!(request.headers.get('Content-Type') || '').toLowerCase().startsWith('application/json')) return err('unsupported_media_type', 415, cors);
  if (!(await rate(env, { scope: 'newsletter-ip', key: clientKey, limit: intVar(env, 'RATE_ALERTS_PER_10MIN', 5), windowSec: 600, nowMs: now.getTime() }))) {
    return err('rate_limited', 429, { ...cors, 'Retry-After': '600' });
  }
  let body;
  try {
    const text = await request.text();
    body = text.length <= 2048 ? JSON.parse(text) : null;
  } catch {
    body = null;
  }
  if (!body || typeof body !== 'object') return err('invalid_json', 400, cors);
  const accepted = () => json({ ok: true, next: 'check_email' }, 202, cors);
  if (body.website) return accepted();
  if (body.consent !== true) return err('consent_required', 400, cors);
  if (!isValidEmail(body.email)) return err('invalid_email', 400, cors);
  const r = await signupNewsletter({ env, db, site, now, transport, secret, b, email: normEmail(body.email) });
  return r.status === 'daily_cap' ? err('try_later', 503, { ...cors, 'Retry-After': '3600' }) : accepted();
}

export async function signupNewsletter({ env, db, site, now, transport, secret, b, email }) {
  if (await isSuppressed(db, site, email, ['newsletter_unsubscribed'])) return { status: 'suppressed' };
  const t = nowIso(now);
  const id = `${site}:nl:${(await sha256Hex(`${site}|${email}`)).slice(0, 24)}`;
  const existing = await db.prepare('SELECT status FROM newsletter_subscribers WHERE id = ?1').bind(id).first();
  if (existing && existing.status !== 'pending') return { status: existing.status };
  await db.prepare(`INSERT INTO newsletter_subscribers (id, site, email_norm, status, created_at, updated_at) VALUES (?1, ?2, ?3, 'pending', ?4, ?4)
    ON CONFLICT (site, email_norm) DO NOTHING`).bind(id, site, email, t).run();
  const expires = addDays(now, CONFIRM_TTL_DAYS);
  return sendListMail({ env, db, now, run: newRun(env, 1), transport }, {
    channel: 'newsletter', kind: 'nl_confirm', key: id, period: todayUtc(now), site,
    build: async () => {
      const token = await signLink(secret, ['nc', id, Math.floor(Date.parse(expires) / 1000), randomNonce()]);
      await db.prepare("UPDATE newsletter_subscribers SET confirm_token_hash = ?2, confirm_expires_at = ?3, updated_at = ?4 WHERE id = ?1 AND status = 'pending'")
        .bind(id, await sha256Hex(token), expires, t).run();
      const url = `${b.base}/api/newsletter/confirm?t=${token}`;
      const after = 'If you did not ask for this, ignore this email: nothing is sent unless you confirm. The link works for 30 days.';
      return listEmail(b, {
        to: email,
        subject: `Confirm your ${b.name} newsletter subscription`,
        text: `You (or someone using this address) asked for the ${b.name} newsletter.\n\nConfirm: ${url}\n\n${after}`,
        html: `<p>You (or someone using this address) asked for the ${esc(b.name)} newsletter.</p><p><a href="${esc(url)}">Confirm my subscription</a></p><p>${esc(after)}</p>`,
        unsubUrl: await unsubUrl(secret, b, id),
      });
    },
  });
}

export async function confirmNewsletter(db, secret, token, now) {
  const parts = await verifyLink(secret, token);
  if (!parts || parts[0] !== 'nc') return 'invalid';
  if (Number(parts[2]) * 1000 < now.getTime()) return 'expired';
  const t = nowIso(now);
  const r = await db.prepare("UPDATE newsletter_subscribers SET status = 'active', consent_at = ?3, confirm_token_hash = NULL, confirm_expires_at = NULL, updated_at = ?3 WHERE id = ?1 AND status = 'pending' AND confirm_token_hash = ?2")
    .bind(parts[1], await sha256Hex(token), t).run();
  if (r.meta && r.meta.changes > 0) return 'ok';
  const s = await db.prepare('SELECT status FROM newsletter_subscribers WHERE id = ?1').bind(parts[1]).first();
  return s && s.status === 'active' ? 'already' : 'invalid';
}

export async function unsubscribeNewsletter(db, subId, now) {
  const s = await db.prepare('SELECT site, email_norm FROM newsletter_subscribers WHERE id = ?1').bind(subId).first();
  if (!s) return false;
  const t = nowIso(now);
  await suppress(db, s.site, s.email_norm, 'newsletter_unsubscribed', now);
  await db.prepare("UPDATE newsletter_subscribers SET status = 'unsubscribed', confirm_token_hash = NULL, unsubscribed_at = COALESCE(unsubscribed_at, ?2), updated_at = ?2 WHERE id = ?1")
    .bind(subId, t).run();
  return true;
}

// ---------- compose + render ----------

const CTRL = new RegExp('[\\u0000-\\u0008\\u000B\\u000C\\u000E-\\u001F\\u007F\\u2028\\u2029]', 'g');

function idList(v, max) {
  if (v == null) return { ok: true, value: [] };
  if (!Array.isArray(v) || v.length > max || !v.every((x) => typeof x === 'string' && x.length >= 1 && x.length <= 120)) return { ok: false };
  return { ok: true, value: [...new Set(v)] };
}

/** Validate a compose body against this board's live jobs and employers. Returns {ok, value} or {ok:false, errors}. */
export async function validateNewsletter(db, site, body) {
  const errors = [];
  const subject = typeof body.subject === 'string' ? body.subject.replace(CTRL, ' ').replace(/[\r\n]+/g, ' ').trim() : '';
  if (subject.length < 3 || subject.length > 150) errors.push('subject');
  const intro = typeof body.intro === 'string' ? body.intro.replace(CTRL, '').trim() : '';
  if (intro.length < 1 || intro.length > 5000) errors.push('intro');
  const jobs = idList(body.jobs, MAX_JOBS);
  const adv = idList(body.advertisers, MAX_ADVERTISERS);
  if (!jobs.ok) errors.push('jobs');
  if (!adv.ok) errors.push('advertisers');
  if (!errors.length) {
    for (const id of jobs.value) {
      const j = await db.prepare("SELECT 1 AS x FROM jobs WHERE id = ?1 AND site = ?2 AND status = 'live'").bind(id, site).first();
      if (!j) {
        errors.push('jobs');
        break;
      }
    }
    for (const id of adv.value) {
      const e = await db.prepare('SELECT 1 AS x FROM employers WHERE id = ?1 AND site = ?2').bind(id, site).first();
      if (!e) {
        errors.push('advertisers');
        break;
      }
    }
  }
  if (errors.length) return { ok: false, errors };
  return { ok: true, value: { subject, intro, items_json: JSON.stringify({ jobs: jobs.value, advertisers: adv.value }) } };
}

async function featured(db, nl) {
  const items = JSON.parse(nl.items_json || '{}');
  const jobs = [];
  for (const id of items.jobs || []) {
    const j = await db.prepare(`SELECT j.id, j.title, j.location, j.sal_text, e.name AS employer FROM jobs j LEFT JOIN employers e ON e.id = j.employer_id
      WHERE j.id = ?1 AND j.site = ?2 AND j.status = 'live'`).bind(id, nl.site).first();
    if (j) jobs.push(j); // a job closed after composing simply drops out
  }
  const advertisers = [];
  for (const id of items.advertisers || []) {
    const e = await db.prepare('SELECT id, name, website FROM employers WHERE id = ?1 AND site = ?2').bind(id, nl.site).first();
    if (e) advertisers.push(e);
  }
  return { jobs, advertisers };
}

export async function renderNewsletter(env, db, secret, nl, { to, subId }) {
  const b = board(env, nl.site);
  const { jobs, advertisers } = await featured(db, nl);
  const paras = nl.intro.split(/\n\s*\n/).map((p) => p.trim()).filter(Boolean);
  const text = [
    ...paras.flatMap((p) => [p, '']),
    ...(jobs.length ? ['Featured jobs:', ...jobs.map((j) => `- ${j.title}${j.employer ? `, ${j.employer}` : ''} (${j.location})\n  ${b.jobUrl(j.id)}`), ''] : []),
    ...(advertisers.length ? ['Featured employers:', ...advertisers.map((a) => `- ${a.name}${a.website && /^https:\/\//.test(a.website) ? ` ${a.website}` : ''}`)] : []),
  ].join('\n').trim();
  const html = [
    ...paras.map((p) => `<p>${esc(p).replace(/\n/g, '<br>')}</p>`),
    jobs.length ? `<h2 style="font-size:18px">Featured jobs</h2><ul>${jobs.map((j) => `<li><a href="${esc(b.jobUrl(j.id))}">${esc(j.title)}</a>${j.employer ? `, ${esc(j.employer)}` : ''} (${esc(j.location)})</li>`).join('')}</ul>` : '',
    advertisers.length ? `<h2 style="font-size:18px">Featured employers</h2><ul>${advertisers.map((a) => `<li>${a.website && /^https:\/\//.test(a.website) ? `<a href="${esc(a.website)}">${esc(a.name)}</a>` : esc(a.name)}</li>`).join('')}</ul>` : '',
  ].join('');
  return listEmail(b, { to, subject: nl.subject, text, html, unsubUrl: await unsubUrl(secret, b, subId) });
}

// ---------- staff ----------

const NL_PATH = /^\/api\/admin\/newsletters\/([^/]+)(?:\/(preview|test|send))?$/;

async function loadNl(db, site, id) {
  return db.prepare('SELECT * FROM newsletters WHERE id = ?1 AND site = ?2').bind(id, site).first();
}

async function recipientsCount(db, nl) {
  const r = await db.prepare("SELECT COUNT(*) AS n FROM newsletter_subscribers WHERE site = ?1 AND status = 'active' AND consent_at IS NOT NULL").bind(nl.site).first();
  return r?.n || 0;
}

async function readBody(request) {
  try {
    const t = await request.text();
    return t.length <= 16384 ? JSON.parse(t) : null;
  } catch {
    return null;
  }
}

/** Staff API. ctx = {env, site, now, request, actor, idemKey, transport}; auth/CSRF/idempotency already checked. */
export async function newsletterAdmin(ctx, path) {
  const { env, site, now, request, actor } = ctx;
  if (env.NEWSLETTER_ENABLED !== '1') return err('not_found', 404);
  const secret = signingKey(env);
  if (!secret || !env.DB) return err('newsletter_not_configured', 503);
  const db = env.DB;
  const t = nowIso(now);
  const method = request.method;

  if (path === '/api/admin/newsletters') {
    if (method === 'GET') {
      const { results } = await db.prepare('SELECT id, subject, status, version, created_by, queued_at, sent_at, updated_at FROM newsletters WHERE site = ?1 ORDER BY created_at DESC LIMIT 50').bind(site).all();
      return json({ newsletters: results });
    }
    if (method !== 'POST') return err('method_not_allowed', 405);
    const body = await readBody(request);
    if (!body || typeof body !== 'object') return err('invalid_json', 400);
    const v = await validateNewsletter(db, site, body);
    if (!v.ok) return json({ error: 'invalid', fields: v.errors }, 400);
    const id = `${site}:nl:${await uuidFromSeed(`newsletter|${ctx.idemKey}`)}`;
    await db.prepare(`INSERT INTO newsletters (id, site, subject, intro, items_json, status, version, created_by, created_at, updated_at)
      VALUES (?1, ?2, ?3, ?4, ?5, 'draft', 1, ?6, ?7, ?7) ON CONFLICT (id) DO NOTHING`)
      .bind(id, site, v.value.subject, v.value.intro, v.value.items_json, actor, t).run();
    return json({ id, version: 1, status: 'draft' }, 201);
  }

  const m = NL_PATH.exec(path);
  if (!m) return err('not_found', 404);
  const nl = await loadNl(db, site, decodeURIComponent(m[1]));
  if (!nl) return err('not_found', 404);
  const action = m[2] || '';

  if (action === '' && method === 'GET') return json({ newsletter: nl });
  if (action === '' && method === 'PUT') {
    const body = await readBody(request);
    if (!body || typeof body !== 'object') return err('invalid_json', 400);
    if (nl.status !== 'draft') return err('not_draft', 409);
    if (Number(body.version) !== nl.version) return err('version_conflict', 409);
    const v = await validateNewsletter(db, site, body);
    if (!v.ok) return json({ error: 'invalid', fields: v.errors }, 400);
    await db.prepare("UPDATE newsletters SET subject = ?2, intro = ?3, items_json = ?4, version = version + 1, updated_at = ?5 WHERE id = ?1 AND version = ?6 AND status = 'draft'")
      .bind(nl.id, v.value.subject, v.value.intro, v.value.items_json, t, nl.version).run();
    return json({ id: nl.id, version: nl.version + 1, status: 'draft' });
  }
  if (action === 'preview' && method === 'GET') {
    const p = await renderNewsletter(env, db, secret, nl, { to: actor, subId: 'preview' });
    return json({ subject: p.subject, text: p.text, html: p.html, headers: p.headers, recipients: await recipientsCount(db, nl), live: channelLive(env, 'newsletter') });
  }
  if (action === 'test' && method === 'POST') {
    if (!isValidEmail(actor)) return err('no_staff_email', 400);
    const key = `${nl.id}:${(await sha256Hex(normEmail(actor))).slice(0, 16)}`;
    const r = await sendListMail({ env, db, now, run: newRun(env, 1), transport: ctx.transport }, {
      channel: 'newsletter', kind: 'nl_test', key, period: `v${nl.version}`, site,
      build: async () => {
        const p = await renderNewsletter(env, db, secret, nl, { to: actor, subId: 'test' });
        return { ...p, subject: `[TEST] ${p.subject}` };
      },
    });
    return json({ status: r.status === 'done' ? 'already_tested' : r.status, version: nl.version });
  }
  if (action === 'send' && method === 'POST') {
    const body = (await readBody(request)) || {};
    if (nl.status !== 'draft') return json({ id: nl.id, status: nl.status }); // replay converges
    if (body.confirm_subject !== nl.subject) return err('confirm_subject_mismatch', 400);
    const tested = await db.prepare("SELECT 1 AS x FROM list_mail_ledger WHERE kind = 'nl_test' AND key LIKE ?1 AND period = ?2 AND status IN ('sent','dry_run')")
      .bind(`${nl.id}:%`, `v${nl.version}`).first();
    if (!tested) return err('test_send_required', 409);
    await db.prepare("UPDATE newsletters SET status = 'queued', queued_by = ?2, queued_at = ?3, updated_at = ?3 WHERE id = ?1 AND status = 'draft'").bind(nl.id, actor, t).run();
    await db.prepare('INSERT OR IGNORE INTO audit_log (at, actor, action, entity, entity_id, request_id, detail_json) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)')
      .bind(t, actor, 'newsletter.queue', 'newsletter', nl.id, ctx.idemKey, JSON.stringify({ version: nl.version })).run();
    return json({ id: nl.id, status: 'queued', recipients: await recipientsCount(db, nl) }, 202);
  }
  return err('method_not_allowed', 405);
}

// ---------- cron ----------

export async function runNewsletter(ctx) {
  const { env, db, now, run } = ctx;
  const out = { expired: 0, sent: 0, dry_run: 0, failed: 0, skipped: 0, completed: [] };
  if (env.NEWSLETTER_ENABLED !== '1') return { ...out, skipped: 'disabled' };
  const secret = signingKey(env);
  if (!secret) return { ...out, skipped: 'no_signing_key' };
  try {
    const t = nowIso(now);
    const ex = await db.prepare("DELETE FROM newsletter_subscribers WHERE status = 'pending' AND confirm_expires_at IS NOT NULL AND confirm_expires_at < ?1").bind(t).run();
    out.expired = ex.meta?.changes || 0;
    const live = channelLive(env, 'newsletter');
    const queued = (await db.prepare("SELECT * FROM newsletters WHERE status = 'queued' ORDER BY queued_at, id LIMIT 5").all()).results;
    for (const nl of queued) {
      if (run.capped) break;
      for (let pg = 0; pg < 20 && !run.capped; pg++) {
        const subs = (await db.prepare(`SELECT s.id, s.site, s.email_norm FROM newsletter_subscribers s
          WHERE s.site = ?1 AND s.status = 'active' AND s.consent_at IS NOT NULL AND s.consent_at <= ?2
            AND NOT EXISTS (SELECT 1 FROM list_mail_ledger l WHERE l.kind = 'newsletter' AND l.key = s.id AND l.period = ?3 AND ${DONE_SQL('l', live)})
          ORDER BY s.id LIMIT 100`).bind(nl.site, nl.queued_at, nl.id).all()).results;
        if (!subs.length) {
          // Every consenting subscriber has a terminal row for this issue. In a dry run it stays queued so the
          // live switch can still send it; only a live run (or nobody to send to) completes it.
          const anyDry = await db.prepare("SELECT 1 AS x FROM list_mail_ledger WHERE kind = 'newsletter' AND period = ?1 AND status = 'dry_run' LIMIT 1").bind(nl.id).first();
          if (live || !anyDry) {
            await db.prepare("UPDATE newsletters SET status = 'sent', sent_at = ?2, updated_at = ?2 WHERE id = ?1 AND status = 'queued'").bind(nl.id, t).run();
            out.completed.push(nl.id);
          }
          break;
        }
        for (const s of subs) {
          const ref = { kind: 'newsletter', key: s.id, period: nl.id, site: s.site };
          if (await isSuppressed(db, s.site, s.email_norm, ['newsletter_unsubscribed'])) {
            await ledgerMark(db, ref, 'skipped', now, 'suppressed');
            out.skipped++;
            continue;
          }
          const r = await sendListMail(ctx, { channel: 'newsletter', ...ref, build: () => renderNewsletter(env, db, secret, nl, { to: s.email_norm, subId: s.id }) });
          if (r.status in out) out[r.status]++;
          if (r.status === 'run_cap' || r.status === 'daily_cap') break;
        }
      }
    }
  } catch (e) {
    console.error('newsletter: cron_failed', e && e.message ? e.message.slice(0, 120) : 'Error');
    out.error = true;
  }
  return out;
}

// ---------- console page ----------

const PAGE_HEADERS = { ...SECURITY_HEADERS, 'Content-Security-Policy': CONSOLE_CSP, 'Cache-Control': 'no-store', 'Cross-Origin-Opener-Policy': 'same-origin' };

export function newsletterConsoleHtml(site, email) {
  const html = `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>GreenJobs newsletter (${escapeHtml(site)})</title><link rel="stylesheet" href="/admin/console.css"></head>
<body data-site="${escapeHtml(site)}">
<header><h1>Newsletter</h1><p>Site <strong>${escapeHtml(site)}</strong> &middot; signed in as ${escapeHtml(email)} &middot; <a href="/admin/">Jobs console</a></p></header>
<main>
<section><h2>Compose</h2>
<form id="nl-form" autocomplete="off">
<input type="hidden" name="id"><input type="hidden" name="version">
<label>Subject <input name="subject" required minlength="3" maxlength="150"></label>
<label>Intro (blank line = new paragraph) <textarea name="intro" required maxlength="5000" rows="8"></textarea></label>
<label>Featured job ids (comma separated, live jobs on this board, max 12) <input name="jobs" maxlength="2000"></label>
<label>Featured advertiser ids (comma separated, max 6) <input name="advertisers" maxlength="1000"></label>
<button type="submit">Save draft</button> <button type="button" id="preview">Preview</button>
<button type="button" id="test">Send test to me</button> <button type="button" id="send">Send to subscribers</button>
<p id="msg" role="status"></p>
</form></section>
<section><h2>Preview</h2><pre id="preview-text"></pre></section>
<section><h2>Newsletters</h2><ul id="list"></ul></section>
</main><script src="/admin/newsletter.js" defer></script></body></html>`;
  return new Response(html, { status: 200, headers: { ...PAGE_HEADERS, 'Content-Type': 'text/html; charset=utf-8' } });
}

const CONSOLE_JS = `'use strict';
(function () {
  const f = document.getElementById('nl-form');
  const msg = document.getElementById('msg');
  const say = (t) => { msg.textContent = t; };
  const ids = (s) => s.split(',').map((x) => x.trim()).filter(Boolean);
  async function call(method, path, body) {
    const h = { 'Content-Type': 'application/json', 'Idempotency-Key': crypto.randomUUID() };
    const r = await fetch(path, { method, headers: method === 'GET' ? {} : h, body: body ? JSON.stringify(body) : undefined, credentials: 'same-origin' });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.error + (j.fields ? ': ' + j.fields.join(', ') : ''));
    return j;
  }
  const current = () => f.elements.id.value;
  async function list() {
    const j = await call('GET', '/api/admin/newsletters');
    const ul = document.getElementById('list');
    ul.textContent = '';
    for (const n of j.newsletters) {
      const li = document.createElement('li');
      li.textContent = n.subject + ' [' + n.status + ', v' + n.version + ']';
      li.addEventListener('click', async () => {
        const d = (await call('GET', '/api/admin/newsletters/' + encodeURIComponent(n.id))).newsletter;
        const items = JSON.parse(d.items_json || '{}');
        f.elements.id.value = d.id; f.elements.version.value = d.version;
        f.elements.subject.value = d.subject; f.elements.intro.value = d.intro;
        f.elements.jobs.value = (items.jobs || []).join(', '); f.elements.advertisers.value = (items.advertisers || []).join(', ');
        say('Loaded ' + d.status);
      });
      ul.appendChild(li);
    }
  }
  f.addEventListener('submit', async (e) => {
    e.preventDefault();
    const body = { subject: f.elements.subject.value, intro: f.elements.intro.value, jobs: ids(f.elements.jobs.value), advertisers: ids(f.elements.advertisers.value) };
    try {
      let j;
      if (current()) j = await call('PUT', '/api/admin/newsletters/' + encodeURIComponent(current()), { ...body, version: Number(f.elements.version.value) });
      else j = await call('POST', '/api/admin/newsletters', body);
      f.elements.id.value = j.id; f.elements.version.value = j.version; say('Saved draft v' + j.version); list();
    } catch (err) { say('Not saved: ' + err.message); }
  });
  document.getElementById('preview').addEventListener('click', async () => {
    if (!current()) return say('Save first');
    try {
      const j = await call('GET', '/api/admin/newsletters/' + encodeURIComponent(current()) + '/preview');
      document.getElementById('preview-text').textContent = 'Subject: ' + j.subject + '\\n\\n' + j.text + '\\n\\nRecipients: ' + j.recipients + (j.live ? '' : ' (DRY RUN: nothing is sent)');
    } catch (err) { say('Preview failed: ' + err.message); }
  });
  document.getElementById('test').addEventListener('click', async () => {
    if (!current()) return say('Save first');
    try { const j = await call('POST', '/api/admin/newsletters/' + encodeURIComponent(current()) + '/test', {}); say('Test: ' + j.status); }
    catch (err) { say('Test failed: ' + err.message); }
  });
  document.getElementById('send').addEventListener('click', async () => {
    if (!current()) return say('Save first');
    const typed = window.prompt('Type the subject exactly to send to all subscribers:');
    if (typed === null) return;
    try { const j = await call('POST', '/api/admin/newsletters/' + encodeURIComponent(current()) + '/send', { confirm_subject: typed }); say('Queued for ' + j.recipients + ' subscribers'); list(); }
    catch (err) { say('Not sent: ' + err.message); }
  });
  list().catch(() => say('Could not load newsletters'));
})();
`;

export function newsletterConsoleJs() {
  return new Response(CONSOLE_JS, { status: 200, headers: { ...PAGE_HEADERS, 'Content-Type': 'text/javascript; charset=utf-8' } });
}
