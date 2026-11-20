// Shared list-mail core for job alerts and the newsletter: signed links, the send ledger with caps and one retry,
// suppression, board identity and the one-click unsubscribe headers. Tables: d1/migrations/0004_job_alerts_newsletter.sql.
//
// DRY BY DEFAULT. A list mail leaves the Worker only when the channel flag is on (ALERTS_ENABLED / NEWSLETTER_ENABLED
// = "1") AND mail.js isLive(env) (DRY_RUN="0", LIVE_CONFIRM="send-applications", MAIL_PROVIDER="resend", key set).
// Otherwise the ledger row is 'dry_run' and the transport is never called.
// Guards (each one fires in tests/greenjobs_redesign/platform/listmail.test.mjs):
//   LIST_MAIL_RUN_CAP   (default 20)  mails per cron run / request
//   LIST_MAIL_DAILY_CAP (default 100) list mails per UTC day (sent + dry_run + in flight)
//   MAIL_DAILY_CAP      (mail.js)     every live mail the Worker sends, applications included
//   provider failure: retried once in the same call, then logged ('list.mail_failed' audit row, ledger 'failed');
//   a later run retries while attempts < 4. Provider Idempotency-Key = ledger key, so a retry cannot double-send.

import { headerSafe, isLive, resendTransport } from '../mail.js';
import { intVar, nowIso, sha256Hex, todayUtc } from '../util.js';

export const DAY_MS = 86400000;
export const CONFIRM_TTL_DAYS = 30;
export const MAX_ATTEMPTS = 4;

const enc = new TextEncoder();
const dec = new TextDecoder();

// ---------- signed links ----------

function b64url(bytes) {
  let bin = '';
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

function unb64url(s) {
  const bin = atob(s.replace(/-/g, '+').replace(/_/g, '/'));
  return Uint8Array.from(bin, (c) => c.charCodeAt(0));
}

/** The HMAC secret (wrangler secret LIST_MAIL_SIGNING_KEY, >= 32 chars) or null: no key = the channel fails closed. */
export function signingKey(env) {
  const k = env.LIST_MAIL_SIGNING_KEY;
  return typeof k === 'string' && k.length >= 32 ? k : null;
}

async function hmacKey(secret) {
  return crypto.subtle.importKey('raw', enc.encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign', 'verify']);
}

/** token = b64url(parts.join('|')) + '.' + b64url(HMAC-SHA256). Parts never contain '|'. */
export async function signLink(secret, parts) {
  const payload = enc.encode(parts.map(String).join('|'));
  const sig = new Uint8Array(await crypto.subtle.sign('HMAC', await hmacKey(secret), payload));
  return `${b64url(payload)}.${b64url(sig)}`;
}

/** Returns the parts array, or null for anything malformed, oversized or not signed by this secret. */
export async function verifyLink(secret, token) {
  if (!secret || typeof token !== 'string' || token.length > 600 || !/^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$/.test(token)) return null;
  const [p, s] = token.split('.');
  try {
    const payload = unb64url(p);
    const ok = await crypto.subtle.verify('HMAC', await hmacKey(secret), unb64url(s), payload);
    return ok ? dec.decode(payload).split('|') : null;
  } catch {
    return null;
  }
}

export function randomNonce() {
  return b64url(crypto.getRandomValues(new Uint8Array(12)));
}

export function addDays(now, days) {
  return nowIso(new Date(now.getTime() + days * DAY_MS));
}

// ---------- weeks ----------

/** ISO-8601 week key, e.g. '2026-W49'. */
export function isoWeek(date) {
  const d = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate()));
  const dow = d.getUTCDay() || 7;
  d.setUTCDate(d.getUTCDate() + 4 - dow);
  const y = d.getUTCFullYear();
  const week = Math.ceil(((d - Date.UTC(y, 0, 1)) / DAY_MS + 1) / 7);
  return `${y}-W${String(week).padStart(2, '0')}`;
}

/** Monday 00:00 UTC of the week containing date. */
export function weekStart(date) {
  const d = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate()));
  d.setUTCDate(d.getUTCDate() - ((d.getUTCDay() || 7) - 1));
  return d;
}

// ---------- board identity ----------

const BOARDS = {
  ie: { name: 'GreenJobs.ie', base: 'https://greenjobs.ie' },
  uk: { name: 'GreenJobs.co.uk', base: 'https://greenjobs.co.uk' },
};

/** Sender identity per board: LIST_FROM_IE / LIST_FROM_UK (e.g. "GreenJobs.ie <alerts@mail.greenjobs.ie>"). */
export function board(env, site) {
  const S = site.toUpperCase();
  const b = BOARDS[site];
  const base = String(env[`LIST_BASE_URL_${S}`] || b.base).replace(/\/+$/, '');
  return { site, name: b.name, base, from: headerSafe(env[`LIST_FROM_${S}`] || ''), jobUrl: (id) => `${base}/jobs/?id=${encodeURIComponent(id)}` };
}

export function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
}

/**
 * Every list mail: board sender, plain text + HTML, one-click unsubscribe (RFC 8058 headers + a visible link),
 * no tracking pixel, no click tracking (links are plain).
 */
export function listEmail(b, { to, subject, text, html, unsubUrl }) {
  const foot = `\n\n--\nYou get this from ${b.name}. Unsubscribe (one click, immediate): ${unsubUrl}\n`;
  const htmlFoot = `<hr><p style="font-size:12px;color:#555">You get this from ${esc(b.name)}. <a href="${esc(unsubUrl)}">Unsubscribe</a> (one click, immediate).</p>`;
  return {
    from: b.from,
    to: [headerSafe(to, 254)],
    subject: headerSafe(subject, 150),
    text: text + foot,
    html: `<!doctype html><html><body style="font-family:Arial,sans-serif;max-width:640px">${html}${htmlFoot}</body></html>`,
    headers: { 'List-Unsubscribe': `<${unsubUrl}>`, 'List-Unsubscribe-Post': 'List-Unsubscribe=One-Click' },
  };
}

// ---------- suppression ----------

export async function emailHash(email) {
  return sha256Hex(`gj-list|${String(email).trim().toLowerCase()}`);
}

export async function isSuppressed(db, site, email, reasons) {
  const h = await emailHash(email);
  const marks = reasons.map((_, i) => `?${i + 3}`).join(',');
  const r = await db.prepare(`SELECT 1 AS x FROM list_suppression WHERE site = ?1 AND email_hash = ?2 AND reason IN (${marks}) LIMIT 1`).bind(site, h, ...reasons).first();
  return !!r;
}

export async function suppress(db, site, email, reason, now) {
  await db.prepare('INSERT OR IGNORE INTO list_suppression (site, email_hash, reason, created_at) VALUES (?1, ?2, ?3, ?4)')
    .bind(site, await emailHash(email), reason, nowIso(now)).run();
}

// ---------- ledger + send ----------

const AUDIT = 'INSERT OR IGNORE INTO audit_log (at, actor, action, entity, entity_id, request_id, detail_json) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)';

export function channelLive(env, channel) {
  const flag = channel === 'newsletter' ? env.NEWSLETTER_ENABLED : env.ALERTS_ENABLED;
  return flag === '1' && isLive(env);
}

/** {count, cap}: one per cron run (shared by alerts and newsletter) or per request. */
export function newRun(env, cap) {
  return { count: 0, cap: cap ?? intVar(env, 'LIST_MAIL_RUN_CAP', 20), capped: false };
}

/** Write a terminal no-mail row (empty digest, suppressed) unless the key already has a row. */
export async function ledgerMark(db, { kind, key, period, site }, status, now, reason = null) {
  const t = nowIso(now);
  await db.prepare(`INSERT INTO list_mail_ledger (kind, key, period, site, status, attempts, reason, day, created_at, updated_at)
    VALUES (?1, ?2, ?3, ?4, ?5, 0, ?6, ?7, ?8, ?8) ON CONFLICT (kind, key, period) DO NOTHING`)
    .bind(kind, key, period, site, status, reason, todayUtc(now), t).run();
}

export async function ledgerStatus(db, kind, key, period) {
  const r = await db.prepare('SELECT status, attempts FROM list_mail_ledger WHERE kind = ?1 AND key = ?2 AND period = ?3').bind(kind, key, period).first();
  return r || null;
}

/** SQL fragment: "this (kind,key,period) is finished for this mode" (used to pre-filter candidates). */
export const DONE_SQL = (alias, live) =>
  `(${alias}.status IN ('sent','sending','empty','skipped') OR (${alias}.status = 'dry_run' AND ${live ? 0 : 1} = 1) OR (${alias}.status = 'failed' AND ${alias}.attempts >= ${MAX_ATTEMPTS}))`;

async function underCaps(env, db, now, live) {
  const day = todayUtc(now);
  const listCap = intVar(env, 'LIST_MAIL_DAILY_CAP', 100);
  const n = await db.prepare("SELECT COUNT(*) AS n FROM list_mail_ledger WHERE day = ?1 AND status IN ('sent','dry_run','sending')").bind(day).first();
  if ((n?.n || 0) >= listCap) return 'daily_cap';
  if (live) {
    const all = await db.prepare("SELECT COUNT(*) AS n FROM audit_log WHERE action = 'mail.send' AND at >= ?1").bind(`${day}T00:00:00Z`).first();
    if ((all?.n || 0) >= intVar(env, 'MAIL_DAILY_CAP', 200)) return 'daily_cap';
  }
  return null;
}

/**
 * Send one list mail through the ledger. build() runs only after the claim succeeds (so a link is rotated only
 * when a mail really goes) and returns the payload. Returns {status}:
 *   done (already handled) | run_cap | daily_cap | dry_run | sent | failed
 */
export async function sendListMail(ctx, { channel, kind, key, period, site, build }) {
  const { env, db, now, run } = ctx;
  if (run.count >= run.cap) {
    run.capped = true;
    return { status: 'run_cap' };
  }
  const live = channelLive(env, channel);
  const capHit = await underCaps(env, db, now, live);
  if (capHit) {
    run.capped = true;
    return { status: capHit };
  }
  const t = nowIso(now);
  const claim = await db.prepare(`INSERT INTO list_mail_ledger (kind, key, period, site, status, attempts, day, created_at, updated_at)
    VALUES (?1, ?2, ?3, ?4, 'sending', 0, ?5, ?6, ?6)
    ON CONFLICT (kind, key, period) DO UPDATE SET status = 'sending', reason = NULL, day = excluded.day, updated_at = excluded.updated_at
    WHERE (list_mail_ledger.status = 'failed' AND list_mail_ledger.attempts < ${MAX_ATTEMPTS})
       OR (list_mail_ledger.status = 'dry_run' AND ?7 = 1)`)
    .bind(kind, key, period, site, todayUtc(now), t, live ? 1 : 0).run();
  if (!(claim && claim.meta && claim.meta.changes > 0)) return { status: 'done' };
  run.count++;
  const setStatus = (status, add, reason = null) =>
    db.prepare('UPDATE list_mail_ledger SET status = ?4, attempts = attempts + ?5, reason = ?6, updated_at = ?7 WHERE kind = ?1 AND key = ?2 AND period = ?3')
      .bind(kind, key, period, status, add, reason, t).run();

  let payload;
  try {
    payload = await build();
  } catch (e) {
    await setStatus('failed', MAX_ATTEMPTS, 'build');
    console.error('listmail: build_failed', kind);
    return { status: 'failed', reason: 'build' };
  }
  if (!live) {
    await setStatus('dry_run', 0);
    return { status: 'dry_run', payload };
  }
  const idem = `list:${kind}:${key}:${period}`;
  if (!payload.from) {
    await setStatus('failed', MAX_ATTEMPTS, 'no_sender');
    await db.prepare(AUDIT).bind(t, 'system', 'list.mail_failed', kind, key, `${idem}:no_sender`, JSON.stringify({ reason: 'no_sender' })).run();
    return { status: 'failed', reason: 'no_sender' };
  }
  const send = ctx.transport || resendTransport();
  let reason = null;
  let tries = 0;
  for (; tries < 2; tries++) {
    try {
      const r = await send(payload, env, idem);
      if (r && r.ok) {
        reason = null;
        break;
      }
      reason = 'provider';
    } catch (e) {
      reason = e && (e.name === 'TimeoutError' || e.name === 'AbortError') ? 'timeout' : 'transport';
    }
  }
  if (reason) {
    await setStatus('failed', 2, reason);
    await db.prepare(AUDIT).bind(t, 'system', 'list.mail_failed', kind, key, `${idem}:${t}`, JSON.stringify({ reason, tries: 2 })).run();
    console.error('listmail: send_failed', kind, reason);
    return { status: 'failed', reason };
  }
  await setStatus('sent', tries + 1);
  await db.prepare(AUDIT).bind(t, 'system', 'mail.send', `list.${kind}`, key, `mail:${idem}`, JSON.stringify({ provider: 'resend', units: 1 })).run();
  return { status: 'sent', payload };
}

// ---------- tiny HTML pages for confirm / unsubscribe ----------

const PAGE_HEADERS = {
  'Content-Type': 'text/html; charset=utf-8',
  'Cache-Control': 'no-store',
  'X-Content-Type-Options': 'nosniff',
  'Referrer-Policy': 'no-referrer',
  'X-Frame-Options': 'DENY',
  'Content-Security-Policy': "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'",
};

export function page(b, title, bodyHtml, status = 200) {
  const html = `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex"><title>${esc(title)} | ${esc(b.name)}</title></head>
<body style="font-family:Arial,sans-serif;max-width:560px;margin:40px auto;padding:0 16px">
<h1 style="font-size:22px">${esc(title)}</h1>${bodyHtml}<p><a href="${esc(b.base)}/">Back to ${esc(b.name)}</a></p></body></html>`;
  return new Response(html, { status, headers: PAGE_HEADERS });
}
