// List-mail metrics for the status/dashboard `measures` object.
// Read live with listMeasures(env) (staff: GET /api/admin/list-measures) or from the D1 table list_measures, which
// every cron tick rewrites (key, value, updated_at). A value is null when it is unmeasured:
//   - every key is null when migration 0004 is not applied (the tables are missing);
//   - alerts_* keys are null while ALERTS_ENABLED != "1"; newsletter_* keys while NEWSLETTER_ENABLED != "1";
//   - *_sent keys count live sends only, so they are null while that channel has never been live
//     (no 'sent' or 'failed' ledger row yet). Dry runs are counted in *_dry_run_7d instead.
// Keys (counts; "_7d" = ledger rows updated in the last 7 days):
export const MEASURE_KEYS = [
  'alerts_confirmed', // alert subscriptions active now (double opt-in completed)
  'alerts_pending', // awaiting confirmation (sign-ups + imports)
  'alerts_unsubscribed', // alert subscriptions unsubscribed (permanent)
  'alerts_sent', // live alert mails sent, all time (confirm + reconfirm + digest)
  'alerts_sent_7d',
  'alerts_reconfirm_sent', // imported people mailed their one re-confirmation
  'alerts_digest_sent_7d',
  'alerts_failed_7d', // provider failures after the in-run retry
  'alerts_dry_run_7d',
  'newsletter_confirmed',
  'newsletter_pending',
  'newsletter_unsubscribed',
  'newsletter_sent', // live newsletter mails to subscribers, all time (tests excluded)
  'newsletter_sent_7d',
  'newsletter_failed_7d',
  'newsletter_dry_run_7d',
];

import { nowIso } from '../util.js';

const ALERT_KINDS = "('confirm','reconfirm','digest')";
const NL_KINDS = "('nl_confirm','newsletter')";

async function one(db, sql, ...args) {
  const r = await db.prepare(sql).bind(...args).first();
  return r ? Number(r.n) : 0;
}

export async function listMeasures(env, now = new Date()) {
  const out = Object.fromEntries(MEASURE_KEYS.map((k) => [k, null]));
  const db = env.DB;
  if (!db) return out;
  const since = nowIso(new Date(now.getTime() - 7 * 86400000));
  try {
    await db.prepare('SELECT 1 FROM list_mail_ledger LIMIT 1').all();
  } catch {
    return out; // migration 0004 not applied
  }
  if (env.ALERTS_ENABLED === '1') {
    out.alerts_confirmed = await one(db, "SELECT COUNT(*) AS n FROM alert_subscriptions WHERE status = 'active'");
    out.alerts_pending = await one(db, "SELECT COUNT(*) AS n FROM alert_subscriptions WHERE status = 'pending'");
    out.alerts_unsubscribed = await one(db, "SELECT COUNT(*) AS n FROM alert_subscriptions WHERE status = 'unsubscribed'");
    out.alerts_dry_run_7d = await one(db, `SELECT COUNT(*) AS n FROM list_mail_ledger WHERE kind IN ${ALERT_KINDS} AND status = 'dry_run' AND updated_at >= ?1`, since);
    const everLive = await one(db, `SELECT COUNT(*) AS n FROM list_mail_ledger WHERE kind IN ${ALERT_KINDS} AND status IN ('sent','failed')`);
    if (everLive) {
      out.alerts_sent = await one(db, `SELECT COUNT(*) AS n FROM list_mail_ledger WHERE kind IN ${ALERT_KINDS} AND status = 'sent'`);
      out.alerts_sent_7d = await one(db, `SELECT COUNT(*) AS n FROM list_mail_ledger WHERE kind IN ${ALERT_KINDS} AND status = 'sent' AND updated_at >= ?1`, since);
      out.alerts_reconfirm_sent = await one(db, "SELECT COUNT(*) AS n FROM list_mail_ledger WHERE kind = 'reconfirm' AND status = 'sent'");
      out.alerts_digest_sent_7d = await one(db, "SELECT COUNT(*) AS n FROM list_mail_ledger WHERE kind = 'digest' AND status = 'sent' AND updated_at >= ?1", since);
      out.alerts_failed_7d = await one(db, `SELECT COUNT(*) AS n FROM list_mail_ledger WHERE kind IN ${ALERT_KINDS} AND status = 'failed' AND updated_at >= ?1`, since);
    }
  }
  if (env.NEWSLETTER_ENABLED === '1') {
    out.newsletter_confirmed = await one(db, "SELECT COUNT(*) AS n FROM newsletter_subscribers WHERE status = 'active'");
    out.newsletter_pending = await one(db, "SELECT COUNT(*) AS n FROM newsletter_subscribers WHERE status = 'pending'");
    out.newsletter_unsubscribed = await one(db, "SELECT COUNT(*) AS n FROM newsletter_subscribers WHERE status = 'unsubscribed'");
    out.newsletter_dry_run_7d = await one(db, `SELECT COUNT(*) AS n FROM list_mail_ledger WHERE kind IN ${NL_KINDS} AND status = 'dry_run' AND updated_at >= ?1`, since);
    const everLive = await one(db, `SELECT COUNT(*) AS n FROM list_mail_ledger WHERE kind IN ${NL_KINDS} AND status IN ('sent','failed')`);
    if (everLive) {
      out.newsletter_sent = await one(db, "SELECT COUNT(*) AS n FROM list_mail_ledger WHERE kind = 'newsletter' AND status = 'sent'");
      out.newsletter_sent_7d = await one(db, "SELECT COUNT(*) AS n FROM list_mail_ledger WHERE kind = 'newsletter' AND status = 'sent' AND updated_at >= ?1", since);
      out.newsletter_failed_7d = await one(db, `SELECT COUNT(*) AS n FROM list_mail_ledger WHERE kind IN ${NL_KINDS} AND status = 'failed' AND updated_at >= ?1`, since);
    }
  }
  return out;
}

/** Rewrite the list_measures snapshot (one upsert per key). Never throws. */
export async function writeMeasures(env, now) {
  try {
    const m = await listMeasures(env, now);
    const t = nowIso(now);
    for (const [k, v] of Object.entries(m)) {
      await env.DB.prepare('INSERT INTO list_measures (key, value, updated_at) VALUES (?1, ?2, ?3) ON CONFLICT (key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at')
        .bind(k, v, t).run();
    }
    return m;
  } catch {
    return null;
  }
}
