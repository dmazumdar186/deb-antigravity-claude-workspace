// Mail adapter. DRY BY DEFAULT: a message leaves the Worker only when
//   DRY_RUN === "0" AND LIVE_CONFIRM === "send-applications" AND MAIL_PROVIDER === "resend"
//   AND the RESEND_API_KEY secret is set AND today's send count is under MAIL_DAILY_CAP.
// Otherwise deliver() returns {status:'dry_run'} and the transport is never called.
// Every live send writes an audit_log 'mail.send' row: that is the cost ledger (spend = rows x unit price).

import { intVar, nowIso, todayUtc } from './util.js';

export function isLive(env) {
  return env.DRY_RUN === '0' && env.LIVE_CONFIRM === 'send-applications' && env.MAIL_PROVIDER === 'resend' && !!env.RESEND_API_KEY;
}

// Header values: every control char and Unicode line/paragraph separator collapses to one space.
const HEADER_UNSAFE_RE = new RegExp('[\\u0000-\\u001F\\u007F\\u2028\\u2029]+', 'g');

export function headerSafe(s, max = 200) {
  return String(s ?? '').replace(HEADER_UNSAFE_RE, ' ').trim().slice(0, max);
}

const PROVIDER_URL = 'https://api.resend.com/emails';

export function resendTransport(fetchImpl = (...a) => fetch(...a)) {
  return async (payload, env, idempotencyKey) => {
    const res = await fetchImpl(PROVIDER_URL, {
      method: 'POST',
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

export function createMailer({ transport } = {}) {
  return {
    /** Returns {status: 'dry_run'|'sent'|'failed', reason?}. */
    async deliver(env, db, payload, { idempotencyKey, now }) {
      if (!isLive(env)) return { status: 'dry_run' };
      const cap = intVar(env, 'MAIL_DAILY_CAP', 200);
      const sentToday = await db
        .prepare("SELECT COUNT(*) AS n FROM audit_log WHERE action = 'mail.send' AND at >= ?1")
        .bind(`${todayUtc(now)}T00:00:00Z`)
        .first();
      if ((sentToday?.n || 0) >= cap) return { status: 'failed', reason: 'daily_cap' };
      const send = transport || resendTransport();
      let r;
      try {
        r = await send(payload, env, idempotencyKey);
      } catch {
        return { status: 'failed', reason: 'transport' };
      }
      if (!r || !r.ok) return { status: 'failed', reason: 'provider' };
      await db
        .prepare('INSERT OR IGNORE INTO audit_log (at, actor, action, entity, entity_id, request_id, detail_json) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)')
        .bind(nowIso(now), 'system', 'mail.send', 'application', idempotencyKey, `mail:${idempotencyKey}`, JSON.stringify({ provider: 'resend', units: 1 }))
        .run();
      return { status: 'sent' };
    },
  };
}
