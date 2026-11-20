// Job alerts (behind ALERTS_ENABLED="1"; dry by default, see core.js).
//   POST /api/alerts                 sign-up {email, keywords?, sectors?|sector?, region?, job_type?, consent:true}
//                                    -> 202 always (no account enumeration); one confirmation mail per alert per day
//   GET  /api/alerts/confirm?t=      page with a Confirm button (link scanners cannot confirm by prefetching)
//   POST /api/alerts/confirm         t in the form body: activates; the link is one-time (its hash is cleared)
//   GET|POST /api/alerts/unsubscribe?t=   immediate + permanent for every alert of that email on that board
// Cron (runAlerts, every scheduled tick; idempotent, a tick with nothing new is a no-op):
//   1. expire: pending rows past confirm_expires_at (30 days) are deleted; an expired import also gets a
//      'reconfirm_expired' suppression so a later import never mails that person again
//   2. re-confirm: ONE mail per imported person (site + email), only with candidates.consent_marketing = 1 and
//      strategies_consent <> 0 (no candidate row = no mail: fail closed); never to a suppressed address
//   3. digest: from Monday LIST_DIGEST_HOUR_UTC (default 7) each week, one mail per active subscriber per ISO week
//      with jobs posted since the last digest that match; an empty digest is recorded and not sent

import { intVar, nowIso, sha256Hex, todayUtc, err, json } from '../util.js';
import { liveWhere } from '../live.js';
import { isValidEmail, normEmail } from '../validate.js';
import {
  CONFIRM_TTL_DAYS, DAY_MS, DONE_SQL, addDays, board, channelLive, emailHash, esc, isSuppressed, isoWeek, ledgerMark,
  listEmail, newRun, page, randomNonce, sendListMail, signLink, signingKey, suppress, verifyLink, weekStart,
} from './core.js';

const CTRL = new RegExp('[\\u0000-\\u001F\\u007F\\u2028\\u2029<>]', 'g');
const clean = (v, max) => (typeof v === 'string' ? v.replace(CTRL, ' ').replace(/\s+/g, ' ').trim().slice(0, max) : '');

/** Sign-up criteria -> the importer's query shape (keywords, sectors[], region, job_type). Returns {ok, query}. */
export function normalizeQuery(input) {
  const q = {};
  const kw = clean(input.keywords, 100);
  if (kw) q.keywords = kw;
  let sectors = Array.isArray(input.sectors) ? input.sectors : input.sector ? [input.sector] : [];
  if (sectors.length > 5) return { ok: false };
  sectors = [...new Set(sectors.map((s) => clean(s, 60)).filter(Boolean))].sort();
  if (sectors.length) q.sectors = sectors;
  const region = clean(input.region, 60);
  if (region) q.region = region;
  const jt = clean(input.job_type, 40);
  if (jt) q.job_type = jt;
  return { ok: true, query: q };
}

/** Same bytes as strategies_import.py: json.dumps(sort_keys=True, separators=(',',':'), ensure_ascii=False). */
export function canonicalJson(q) {
  const sorted = {};
  for (const k of Object.keys(q).sort()) sorted[k] = q[k];
  return JSON.stringify(sorted);
}

function sectorsOf(job) {
  try {
    const v = JSON.parse(job.sectors_json || '[]');
    return Array.isArray(v) ? v.map((s) => String(s).toLowerCase()) : [];
  } catch {
    return [];
  }
}

/**
 * Does a job match a saved search? Handles sign-up and imported (Jobs By Email) shapes:
 * keywords: every word must appear (title, summary, description, employer); sectors/category: any overlap;
 * region: equals job.region or appears in location; job_type: case-insensitive contains;
 * sal_min: excludes only jobs whose known top salary is below it. label, vicinity, period, sal_max: not filters.
 */
export function jobMatches(job, q) {
  const lc = (s) => String(s || '').toLowerCase();
  if (q.keywords) {
    const hay = lc(`${job.title} ${job.summary} ${job.description} ${job.employer}`);
    const words = lc(q.keywords).split(/[\s,]+/).filter((w) => w.length >= 2);
    if (!words.every((w) => hay.includes(w))) return false;
  }
  const want = [...(Array.isArray(q.sectors) ? q.sectors : []), ...(q.category ? [q.category] : [])].map(lc).filter(Boolean);
  if (want.length) {
    const have = sectorsOf(job);
    if (!want.some((w) => have.includes(w))) return false;
  }
  if (q.region) {
    const r = lc(q.region);
    if (lc(job.region) !== r && !lc(job.location).includes(r)) return false;
  }
  if (q.job_type && !lc(job.job_type).includes(lc(q.job_type))) return false;
  const top = job.sal_max ?? job.sal_min;
  if (q.sal_min != null && top != null && Number(top) < Number(q.sal_min)) return false;
  return true;
}

export function describeQuery(q) {
  const bits = [];
  if (q.label) bits.push(q.label);
  if (q.keywords) bits.push(`"${q.keywords}"`);
  if (q.sectors && q.sectors.length) bits.push(q.sectors.join(', '));
  if (q.category) bits.push(q.category);
  if (q.job_type) bits.push(q.job_type);
  if (q.region) bits.push(q.region);
  return bits.length ? bits.join(' / ') : 'All new jobs';
}

const parseQuery = (s) => {
  try {
    const v = JSON.parse(s || '{}');
    return v && typeof v === 'object' ? v : {};
  } catch {
    return {};
  }
};

async function unsubUrl(secret, b, subId) {
  return `${b.base}/api/alerts/unsubscribe?t=${await signLink(secret, ['au', subId])}`;
}

// ---------- emails ----------

export async function confirmEmail(secret, b, { to, subId, token, queries, reconfirm }) {
  const url = `${b.base}/api/alerts/confirm?t=${token}`;
  const list = queries.map(describeQuery);
  const subject = reconfirm ? `Keep your ${b.name} job alerts?` : `Confirm your ${b.name} job alert`;
  const lead = reconfirm
    ? `${b.name} has moved to a new website. You had these job alerts on the old site:`
    : 'You (or someone using this address) asked for this job alert:';
  const after = reconfirm
    ? 'We will only email you again if you confirm. If you do nothing, your alerts are deleted after 30 days and you will not hear from us again.'
    : 'If you did not ask for this, ignore this email: nothing is sent unless you confirm. The link works for 30 days.';
  const text = [lead, '', ...list.map((l) => `- ${l}`), '', `Confirm: ${url}`, '', after].join('\n');
  const html = `<p>${esc(lead)}</p><ul>${list.map((l) => `<li>${esc(l)}</li>`).join('')}</ul>
<p><a href="${esc(url)}">Confirm my job alert${list.length > 1 ? 's' : ''}</a></p><p>${esc(after)}</p>`;
  return listEmail(b, { to, subject, text, html, unsubUrl: await unsubUrl(secret, b, subId) });
}

export async function digestEmail(secret, b, { to, subId, query, jobs }) {
  const label = describeQuery(query);
  const subject = `${jobs.length} new job${jobs.length === 1 ? '' : 's'} for "${label}" on ${b.name}`;
  const lines = jobs.map((j) => `- ${j.title}${j.employer ? `, ${j.employer}` : ''} (${j.location})\n  ${b.jobUrl(j.id)}`);
  const text = [`New jobs matching your alert "${label}":`, '', ...lines].join('\n');
  const html = `<p>New jobs matching your alert <strong>${esc(label)}</strong>:</p><ul>${jobs
    .map((j) => `<li><a href="${esc(b.jobUrl(j.id))}">${esc(j.title)}</a>${j.employer ? `, ${esc(j.employer)}` : ''} (${esc(j.location)})</li>`)
    .join('')}</ul>`;
  return listEmail(b, { to, subject, text, html, unsubUrl: await unsubUrl(secret, b, subId) });
}

// ---------- routes ----------

async function readJson(request, max = 4096) {
  const t = await request.text();
  if (t.length > max) return null;
  try {
    const v = JSON.parse(t);
    return v && typeof v === 'object' && !Array.isArray(v) ? v : null;
  } catch {
    return null;
  }
}

/** Token from ?t= or a urlencoded form body field t. */
export async function tokenFrom(request, url) {
  const q = url.searchParams.get('t');
  if (q) return q;
  if (request.method !== 'POST') return '';
  const ct = (request.headers.get('Content-Type') || '').toLowerCase();
  if (!ct.startsWith('application/x-www-form-urlencoded')) return '';
  const body = await request.text();
  if (body.length > 2048) return '';
  return new URLSearchParams(body).get('t') || '';
}

export async function alertsRoute({ env, site, now, request, cors, rate, transport, path, url, clientKey }) {
  const secret = signingKey(env);
  if (!secret || !env.DB) return err('alerts_not_configured', 503, cors);
  const b = board(env, site);
  const db = env.DB;
  const method = request.method;

  if (path === '/api/alerts/unsubscribe' && (method === 'GET' || method === 'POST')) {
    const parts = await verifyLink(secret, await tokenFrom(request, url));
    if (!parts || parts[0] !== 'au') return page(b, 'Link not valid', '<p>This unsubscribe link is not valid. Reply to any alert email and we will remove you.</p>', 400);
    await unsubscribeAlerts(db, parts[1], now);
    if (method === 'POST') return new Response('unsubscribed', { status: 200, headers: { 'Content-Type': 'text/plain', 'Cache-Control': 'no-store' } });
    return page(b, 'You are unsubscribed', '<p>You will not get any more job alert emails from us. This is permanent.</p>');
  }

  if (path === '/api/alerts/confirm' && method === 'GET') {
    const t = url.searchParams.get('t') || '';
    const parts = await verifyLink(secret, t);
    if (!parts || (parts[0] !== 'ac' && parts[0] !== 'ar')) return page(b, 'Link not valid', '<p>This confirmation link is not valid.</p>', 400);
    if (Number(parts[2]) * 1000 < now.getTime()) return page(b, 'Link expired', '<p>This link has expired. Sign up again on the jobs page.</p>', 410);
    return page(b, 'Confirm your job alert', `<form method="post" action="/api/alerts/confirm"><input type="hidden" name="t" value="${esc(t)}"><button type="submit">Yes, send me job alerts</button></form>`);
  }

  if (path === '/api/alerts/confirm' && method === 'POST') {
    const r = await confirmAlert(db, secret, await tokenFrom(request, url), now);
    if (r === 'ok') return page(b, 'Job alert confirmed', '<p>Done. You will get a weekly email when new jobs match. Every email has a one-click unsubscribe link.</p>');
    if (r === 'already') return page(b, 'Already confirmed', '<p>This alert is already active.</p>');
    if (r === 'expired') return page(b, 'Link expired', '<p>This link has expired. Sign up again on the jobs page.</p>', 410);
    return page(b, 'Link not valid', '<p>This confirmation link is not valid or was already used.</p>', 400);
  }

  if (path !== '/api/alerts') return err('not_found', 404, cors);
  if (method !== 'POST') return err('method_not_allowed', 405, cors);
  if (!(request.headers.get('Content-Type') || '').toLowerCase().startsWith('application/json')) return err('unsupported_media_type', 415, cors);
  const nowMs = now.getTime();
  if (!(await rate(env, { scope: 'alerts-ip', key: clientKey, limit: intVar(env, 'RATE_ALERTS_PER_10MIN', 5), windowSec: 600, nowMs }))) {
    return err('rate_limited', 429, { ...cors, 'Retry-After': '600' });
  }
  const body = await readJson(request);
  if (!body) return err('invalid_json', 400, cors);
  const accepted = () => json({ ok: true, next: 'check_email' }, 202, cors);
  if (body.website) return accepted(); // honeypot
  if (body.consent !== true) return err('consent_required', 400, cors);
  if (!isValidEmail(body.email)) return err('invalid_email', 400, cors);
  const email = normEmail(body.email);
  const nq = normalizeQuery(body);
  if (!nq.ok) return err('invalid_query', 400, cors);
  const r = await signupAlert({ env, db, site, now, transport, secret, b, email, query: nq.query });
  return r.status === 'daily_cap' ? err('try_later', 503, { ...cors, 'Retry-After': '3600' }) : accepted();
}

/** Returns {status}: suppressed | active | unsubscribed | throttled | done | daily_cap | run_cap | dry_run | sent | failed. */
export async function signupAlert({ env, db, site, now, transport, secret, b, email, query }) {
  if (await isSuppressed(db, site, email, ['alerts_unsubscribed'])) return { status: 'suppressed' };
  const qjson = canonicalJson(query);
  const qhash = await sha256Hex(qjson);
  const t = nowIso(now);
  const day = todayUtc(now);
  const existing = await db.prepare('SELECT id, status FROM alert_subscriptions WHERE site = ?1 AND email_norm = ?2 AND query_hash = ?3').bind(site, email, qhash).first();
  if (existing && existing.status !== 'pending') return { status: existing.status };
  // At most 3 confirmation mails per address per day, whatever the criteria (stops mail-bombing a stranger).
  const perEmail = await db.prepare(`SELECT COUNT(*) AS n FROM list_mail_ledger l JOIN alert_subscriptions s ON s.id = l.key
    WHERE l.kind = 'confirm' AND l.period = ?1 AND s.site = ?2 AND s.email_norm = ?3`).bind(day, site, email).first();
  if ((perEmail?.n || 0) >= 3) return { status: 'throttled' };
  const id = existing ? existing.id : `${site}:gj:alert-${(await sha256Hex(`${site}|${email}|${qhash}`)).slice(0, 24)}`;
  await db.prepare(`INSERT INTO alert_subscriptions (id, site, email_norm, query_json, query_hash, frequency, status, created_at, updated_at)
    VALUES (?1, ?2, ?3, ?4, ?5, 'weekly', 'pending', ?6, ?6) ON CONFLICT (site, email_norm, query_hash) DO NOTHING`)
    .bind(id, site, email, qjson, qhash, t).run();
  const expires = addDays(now, CONFIRM_TTL_DAYS);
  const run = newRun(env, 1);
  return sendListMail({ env, db, now, run, transport }, {
    channel: 'alerts', kind: 'confirm', key: id, period: day, site,
    build: async () => {
      const token = await signLink(secret, ['ac', id, Math.floor(Date.parse(expires) / 1000), randomNonce()]);
      await db.prepare("UPDATE alert_subscriptions SET confirm_token_hash = ?2, updated_at = ?3 WHERE id = ?1 AND status = 'pending'").bind(id, await sha256Hex(token), t).run();
      await db.prepare(`INSERT INTO alert_meta (sub_id, origin, confirm_expires_at, created_at, updated_at) VALUES (?1, 'signup', ?2, ?3, ?3)
        ON CONFLICT (sub_id) DO UPDATE SET origin = 'signup', confirm_expires_at = excluded.confirm_expires_at, updated_at = excluded.updated_at`)
        .bind(id, expires, t).run();
      return confirmEmail(secret, b, { to: email, subId: id, token, queries: [query], reconfirm: false });
    },
  });
}

/** 'ok' | 'already' | 'expired' | 'invalid'. 'ac' confirms one alert; 'ar' confirms a person's imported alerts. */
export async function confirmAlert(db, secret, token, now) {
  const parts = await verifyLink(secret, token);
  if (!parts || (parts[0] !== 'ac' && parts[0] !== 'ar')) return 'invalid';
  if (Number(parts[2]) * 1000 < now.getTime()) return 'expired';
  const th = await sha256Hex(token);
  const t = nowIso(now);
  const rows = (await db.prepare("SELECT id, status FROM alert_subscriptions WHERE confirm_token_hash = ?1 AND status = 'pending'").bind(th).all()).results;
  if (!rows.length) {
    if (parts[0] === 'ac') {
      const s = await db.prepare('SELECT status FROM alert_subscriptions WHERE id = ?1').bind(parts[1]).first();
      if (s && s.status === 'active') return 'already';
    }
    return 'invalid';
  }
  for (const r of rows) {
    await db.prepare("UPDATE alert_subscriptions SET status = 'active', consent_at = ?2, confirm_token_hash = NULL, updated_at = ?2 WHERE id = ?1 AND status = 'pending' AND confirm_token_hash = ?3")
      .bind(r.id, t, th).run();
    await db.prepare(`INSERT INTO alert_meta (sub_id, confirmed_at, last_digest_at, created_at, updated_at) VALUES (?1, ?2, ?2, ?2, ?2)
      ON CONFLICT (sub_id) DO UPDATE SET confirmed_at = excluded.confirmed_at, last_digest_at = excluded.last_digest_at, confirm_expires_at = NULL, updated_at = excluded.updated_at`)
      .bind(r.id, t).run();
  }
  return 'ok';
}

/** Immediate and permanent: every alert for that email on that board, plus a suppression mark. */
export async function unsubscribeAlerts(db, subId, now) {
  const s = await db.prepare('SELECT site, email_norm FROM alert_subscriptions WHERE id = ?1').bind(subId).first();
  if (!s) return false;
  const t = nowIso(now);
  await suppress(db, s.site, s.email_norm, 'alerts_unsubscribed', now);
  const ids = (await db.prepare('SELECT id FROM alert_subscriptions WHERE site = ?1 AND email_norm = ?2').bind(s.site, s.email_norm).all()).results;
  await db.prepare("UPDATE alert_subscriptions SET status = 'unsubscribed', confirm_token_hash = NULL, updated_at = ?3 WHERE site = ?1 AND email_norm = ?2")
    .bind(s.site, s.email_norm, t).run();
  for (const r of ids) {
    await db.prepare(`INSERT INTO alert_meta (sub_id, unsubscribed_at, created_at, updated_at) VALUES (?1, ?2, ?2, ?2)
      ON CONFLICT (sub_id) DO UPDATE SET unsubscribed_at = COALESCE(alert_meta.unsubscribed_at, excluded.unsubscribed_at), updated_at = excluded.updated_at`)
      .bind(r.id, t).run();
  }
  return true;
}

// ---------- cron ----------

async function expirePending(db, now) {
  const t = nowIso(now);
  const rows = (await db.prepare(`SELECT s.id, s.site, s.email_norm, m.origin FROM alert_subscriptions s JOIN alert_meta m ON m.sub_id = s.id
    WHERE s.status = 'pending' AND m.confirm_expires_at IS NOT NULL AND m.confirm_expires_at < ?1 LIMIT 500`).bind(t).all()).results;
  for (const r of rows) {
    if (r.origin === 'import') await suppress(db, r.site, r.email_norm, 'reconfirm_expired', now);
    await db.prepare("DELETE FROM alert_subscriptions WHERE id = ?1 AND status = 'pending'").bind(r.id).run();
    await db.prepare('DELETE FROM alert_meta WHERE sub_id = ?1').bind(r.id).run();
  }
  return rows.length;
}

async function reconfirmImports(ctx, secret, stats) {
  const { env, db, now, run } = ctx;
  const live = channelLive(env, 'alerts');
  // Consent gate (exec_CTO_CDO M9): Jobs By Email has no Marketing column, so join candidates on (site, email).
  const rows = (await db.prepare(`SELECT s.id, s.site, s.email_norm, s.query_json FROM alert_subscriptions s
    JOIN candidates c ON c.site = s.site AND c.email_norm = s.email_norm
    LEFT JOIN alert_meta m ON m.sub_id = s.id
    WHERE s.status = 'pending' AND (m.origin IS NULL OR m.origin = 'import') AND m.confirm_expires_at IS NULL
      AND c.consent_marketing = 1 AND COALESCE(c.strategies_consent, 1) <> 0
    ORDER BY s.site, s.email_norm, s.id LIMIT 2000`).all()).results;
  const people = new Map();
  for (const r of rows) {
    const k = `${r.site}|${r.email_norm}`;
    if (!people.has(k)) people.set(k, { site: r.site, email: r.email_norm, subs: [] });
    people.get(k).subs.push(r);
  }
  for (const p of people.values()) {
    if (run.count >= run.cap) {
      run.capped = true;
      break;
    }
    const key = `${p.site}:${await emailHash(p.email)}`;
    const done = await db.prepare(`SELECT 1 AS x FROM list_mail_ledger l WHERE l.kind = 'reconfirm' AND l.key = ?1 AND l.period = 'once' AND ${DONE_SQL('l', live)}`).bind(key).first();
    if (done) continue;
    if (await isSuppressed(db, p.site, p.email, ['alerts_unsubscribed', 'reconfirm_expired'])) {
      await ledgerMark(db, { kind: 'reconfirm', key, period: 'once', site: p.site }, 'skipped', now, 'suppressed');
      stats.skipped++;
      continue;
    }
    const b = board(env, p.site);
    const expires = addDays(now, CONFIRM_TTL_DAYS);
    const t = nowIso(now);
    const r = await sendListMail(ctx, {
      channel: 'alerts', kind: 'reconfirm', key, period: 'once', site: p.site,
      build: async () => {
        const token = await signLink(secret, ['ar', key, Math.floor(Date.parse(expires) / 1000), randomNonce()]);
        const th = await sha256Hex(token);
        for (const s of p.subs) await db.prepare("UPDATE alert_subscriptions SET confirm_token_hash = ?2, updated_at = ?3 WHERE id = ?1 AND status = 'pending'").bind(s.id, th, t).run();
        return confirmEmail(secret, b, { to: p.email, subId: p.subs[0].id, token, queries: p.subs.map((s) => parseQuery(s.query_json)), reconfirm: true });
      },
    });
    stats[r.status] = (stats[r.status] || 0) + 1;
    if (r.status === 'sent') {
      // The 30-day clock starts only when a mail really went: a dry run never deletes anyone.
      for (const s of p.subs) {
        await db.prepare(`INSERT INTO alert_meta (sub_id, origin, confirm_expires_at, created_at, updated_at) VALUES (?1, 'import', ?2, ?3, ?3)
          ON CONFLICT (sub_id) DO UPDATE SET confirm_expires_at = excluded.confirm_expires_at, updated_at = excluded.updated_at`).bind(s.id, expires, t).run();
      }
    }
    if (r.status === 'run_cap' || r.status === 'daily_cap') break;
  }
}

async function liveJobs(db, site, since, now) {
  const { results } = await db.prepare(`SELECT j.id, j.title, j.location, j.region, j.job_type, j.sal_min, j.sal_max, j.sectors_json, j.summary,
      j.description, COALESCE(j.posted_at, j.created_at) AS posted, e.name AS employer
    FROM jobs j LEFT JOIN employers e ON e.id = j.employer_id
    WHERE j.site = ?1 AND ${liveWhere('j', '?4')}
      AND COALESCE(j.posted_at, j.created_at) > ?2 AND COALESCE(j.posted_at, j.created_at) <= ?3
    ORDER BY posted DESC, j.id LIMIT 2000`).bind(site, since, nowIso(now), nowIso(now).slice(0, 10)).all();
  return results;
}

async function digests(ctx, secret, stats) {
  const { env, db, now, run } = ctx;
  const start = weekStart(now);
  const hour = Math.min(23, Math.max(0, Number.parseInt(env.LIST_DIGEST_HOUR_UTC ?? '7', 10) || 0));
  if (now.getTime() < start.getTime() + hour * 3600000) return;
  const week = isoWeek(now);
  const live = channelLive(env, 'alerts');
  const floor = nowIso(new Date(start.getTime() - 7 * DAY_MS)); // never more than one week back (dry-run -> live switch)
  const jobsBySite = {};
  let after = '';
  for (let pg = 0; pg < 20 && !run.capped; pg++) {
    const subs = (await db.prepare(`SELECT s.id, s.site, s.email_norm, s.query_json, s.consent_at, m.last_digest_at FROM alert_subscriptions s
      LEFT JOIN alert_meta m ON m.sub_id = s.id
      WHERE s.status = 'active' AND s.consent_at IS NOT NULL AND s.id > ?2
        AND NOT EXISTS (SELECT 1 FROM list_mail_ledger l WHERE l.kind = 'digest' AND l.key = s.id AND l.period = ?1 AND ${DONE_SQL('l', live)})
      ORDER BY s.id LIMIT 100`).bind(week, after).all()).results;
    if (!subs.length) break;
    after = subs[subs.length - 1].id;
    for (const s of subs) {
      if (run.count >= run.cap) {
        run.capped = true;
        break;
      }
      const ref = { kind: 'digest', key: s.id, period: week, site: s.site };
      if (await isSuppressed(db, s.site, s.email_norm, ['alerts_unsubscribed'])) {
        await ledgerMark(db, ref, 'skipped', now, 'suppressed');
        stats.skipped++;
        continue;
      }
      jobsBySite[s.site] ||= await liveJobs(db, s.site, floor, now);
      const since = [s.last_digest_at || s.consent_at || floor, floor].sort().pop();
      const query = parseQuery(s.query_json);
      const jobs = jobsBySite[s.site].filter((j) => j.posted > since && jobMatches(j, query)).slice(0, 20);
      const t = nowIso(now);
      const advance = () => db.prepare(`INSERT INTO alert_meta (sub_id, last_digest_at, created_at, updated_at) VALUES (?1, ?2, ?2, ?2)
        ON CONFLICT (sub_id) DO UPDATE SET last_digest_at = excluded.last_digest_at, updated_at = excluded.updated_at`).bind(s.id, t).run();
      if (!jobs.length) {
        await ledgerMark(db, ref, 'empty', now);
        stats.empty++;
        continue;
      }
      const b = board(env, s.site);
      const r = await sendListMail(ctx, { channel: 'alerts', ...ref, build: () => digestEmail(secret, b, { to: s.email_norm, subId: s.id, query, jobs }) });
      stats[r.status] = (stats[r.status] || 0) + 1;
      if (r.status === 'sent' || r.status === 'dry_run') await advance();
      if (r.status === 'sent') await db.prepare('UPDATE alert_subscriptions SET last_sent_at = ?2 WHERE id = ?1').bind(s.id, t).run();
      if (r.status === 'run_cap' || r.status === 'daily_cap') break;
    }
  }
}

/** One cron tick. ctx = {env, db, now, run, transport}. Never throws (a failing helper must not break deliveries). */
export async function runAlerts(ctx) {
  const out = { expired: 0, reconfirm: { skipped: 0 }, digest: { skipped: 0, empty: 0 } };
  if (ctx.env.ALERTS_ENABLED !== '1') return { ...out, skipped: 'disabled' };
  const secret = signingKey(ctx.env);
  if (!secret) return { ...out, skipped: 'no_signing_key' };
  try {
    out.expired = await expirePending(ctx.db, ctx.now);
    await reconfirmImports(ctx, secret, out.reconfirm);
    await digests(ctx, secret, out.digest);
  } catch (e) {
    console.error('alerts: cron_failed', e && e.message ? e.message.slice(0, 120) : 'Error');
    out.error = true;
  }
  return out;
}
