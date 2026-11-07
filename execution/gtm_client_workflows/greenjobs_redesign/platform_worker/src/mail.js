// Mail adapter. DRY BY DEFAULT: a message leaves the Worker only when
//   DRY_RUN === "0" AND LIVE_CONFIRM === "send-applications" AND MAIL_PROVIDER === "resend"
//   AND the RESEND_API_KEY secret is set AND today's send count is under MAIL_DAILY_CAP.
// Otherwise deliver() returns {status:'dry_run'} and the transport is never called.
// Every live send writes an audit_log 'mail.send' row: that is the cost ledger (spend = rows x unit price).
// Alert channel (#21): any live delivery failure (cap, timeout, transport, provider) writes one audit_log
// 'delivery.failed' row per application (ids + reason only, no PII) and, the first time only, attempts one
// alert mail to OPS_ALERT_EMAIL (if set). The alert counts against MAIL_DAILY_CAP like any other send.

import { intVar, nowIso, todayUtc } from './util.js';
import { isValidEmail } from './validate.js';

export const SEND_TIMEOUT_MS = 10000;

export function isLive(env) {
  return env.DRY_RUN === '0' && env.LIVE_CONFIRM === 'send-applications' && env.MAIL_PROVIDER === 'resend' && !!env.RESEND_API_KEY;
}

// Header values: every control char and Unicode line/paragraph separator collapses to one space.
const HEADER_UNSAFE_RE = new RegExp('[\\u0000-\\u001F\\u007F\\u2028\\u2029]+', 'g');

export function headerSafe(s, max = 200) {
  return String(s ?? '').replace(HEADER_UNSAFE_RE, ' ').trim().slice(0, max);
}

const PROVIDER_URL = 'https://api.resend.com/emails';

/** timeoutMs is injectable for tests; a hung provider aborts (TimeoutError) instead of leaving the row 'pending'. */
export function resendTransport(fetchImpl = (...a) => fetch(...a), { timeoutMs = SEND_TIMEOUT_MS } = {}) {
  return async (payload, env, idempotencyKey) => {
    const res = await fetchImpl(PROVIDER_URL, {
      method: 'POST',
      signal: AbortSignal.timeout(timeoutMs),
      headers: {
        Authorization: `Bearer ${env.RESEND_API_KEY}`,
        'Content-Type': 'application/json',
        // The provider de-duplicates on this key for 24 h: a cron retry after a lost status update cannot double-send.
        'Idempotency-Key': idempotencyKey,
      },
      body: JSON.stringify(payload),
    });
    return { ok: res.ok, status: res.status };
  };
}

function bytesToB64(bytes) {
  let bin = '';
  const b = new Uint8Array(bytes);
  for (let i = 0; i < b.length; i += 0x8000) bin += String.fromCharCode(...b.subarray(i, i + 0x8000));
  return btoa(bin);
}

export function buildApplicationEmail(env, { app, job, cv }) {
  const lines = [
    `New application for: ${job.title} (${job.id})`,
    '',
    `Name: ${app.applicant_name}`,
    `Email: ${app.applicant_email}`,
    `Phone: ${app.phone || '-'}`,
    '',
    'Cover note:',
    app.cover_note || '-',
    '',
    cv ? 'CV attached.' : 'No CV uploaded.',
    `Application id: ${app.id}`,
  ];
  const payload = {
    from: headerSafe(env.MAIL_FROM),
    to: [headerSafe(app.routed_to, 254)],
    reply_to: headerSafe(app.applicant_email, 254),
    subject: headerSafe(`Application: ${job.title} - ${app.applicant_name}`),
    text: lines.join('\n'),
  };
  if (cv) payload.attachments = [{ filename: `cv.${cv.ext}`, content: bytesToB64(cv.bytes) }];
  return payload;
}

const SQL_AUDIT_ROW = 'INSERT OR IGNORE INTO audit_log (at, actor, action, entity, entity_id, request_id, detail_json) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)';

async function underCap(env, db, now) {
  const cap = intVar(env, 'MAIL_DAILY_CAP', 200);
  const sentToday = await db
    .prepare("SELECT COUNT(*) AS n FROM audit_log WHERE action = 'mail.send' AND at >= ?1")
    .bind(`${todayUtc(now)}T00:00:00Z`)
    .first();
  return (sentToday?.n || 0) < cap;
}

function ledgerRow(db, now, entity, key, requestId) {
  return db.prepare(SQL_AUDIT_ROW).bind(nowIso(now), 'system', 'mail.send', entity, key, requestId, JSON.stringify({ provider: 'resend', units: 1 })).run();
}

export function buildAlertEmail(env, appId, reason) {
  return {
    from: headerSafe(env.MAIL_FROM),
    to: [headerSafe(env.OPS_ALERT_EMAIL, 254)],
    subject: headerSafe(`GreenJobs: application delivery failed (${reason})`),
    text: [`Application id: ${appId}`, `Reason: ${reason}`, 'The cron retries every 10 minutes for 48 h. Check the inbox and Resend status.'].join('\n'),
  };
}

export function createMailer({ transport } = {}) {
  /** One 'delivery.failed' row per application (stable request_id); the alert goes only on the first. Never throws. */
  async function onFailure(env, db, send, key, reason, now) {
    try {
      const res = await db.prepare(SQL_AUDIT_ROW)
        .bind(nowIso(now), 'system', 'delivery.failed', 'application', key, `delivery.failed:${key}`, JSON.stringify({ reason }))
        .run();
      const first = !!(res && res.meta && res.meta.changes > 0);
      const to = env.OPS_ALERT_EMAIL || '';
      if (!first || !to || !isValidEmail(to) || !isLive(env)) return;
      if (!(await underCap(env, db, now))) return;
      const r = await send(buildAlertEmail(env, key, reason), env, `alert:${key}`);
      if (r && r.ok) await ledgerRow(db, now, 'alert', key, `mail:alert:${key}`);
    } catch {
      console.error('mail: alert_failed', key);
    }
  }

  return {
    /** Returns {status: 'dry_run'|'sent'|'failed', reason?}. */
    async deliver(env, db, payload, { idempotencyKey, now }) {
      if (!isLive(env)) return { status: 'dry_run' };
      const send = transport || resendTransport();
      const fail = async (reason) => {
        await onFailure(env, db, send, idempotencyKey, reason, now);
        return { status: 'failed', reason };
      };
      if (!(await underCap(env, db, now))) return fail('daily_cap');
      let r;
      try {
        r = await send(payload, env, idempotencyKey);
      } catch (e) {
        const name = e && e.name;
        return fail(name === 'TimeoutError' || name === 'AbortError' ? 'timeout' : 'transport');
      }
      if (!r || !r.ok) return fail('provider');
      await ledgerRow(db, now, 'application', idempotencyKey, `mail:${idempotencyKey}`);
      return { status: 'sent' };
    },
  };
}
