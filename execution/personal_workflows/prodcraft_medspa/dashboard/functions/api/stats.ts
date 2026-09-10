// GET /api/stats
//
// Funnel counts per metro (businesses, audited, qualified, owner found,
// verified, previews approved, sent touch1, replied, calls, closed_won),
// reply rate per touch, sends-per-reply, bounce rate, phase0 status, and
// the latest metro_stats row per metro.

import type { Env } from '../_middleware';
import { requireSupabase } from '../_lib/supabase';
import { json, withErrorHandling } from '../_lib/http';
import { bounceRate30d } from '../_lib/queue';

interface BusinessRow {
  id: string;
  metro: string;
  is_chain: boolean;
  drop_reason: string | null;
  owner_email: string | null;
  email_status: string | null;
  do_not_contact: boolean;
}
interface AuditRow {
  business_id: string;
  bucket: string | null;
}
interface PreviewRow {
  business_id: string;
  status: string;
}
interface OutreachRow {
  business_id: string;
  touch: number;
  status: string;
  sent_at: string | null;
  reply_sentiment: string | null;
}
interface MetroStatsRow {
  metro: string;
  sampled: number;
  qualified: number;
  pct_qualified: number;
  ci_low: number;
  ci_high: number;
  score_version: string;
  measured_at: string;
}

function emptyFunnel() {
  return {
    businesses: 0,
    audited: 0,
    qualified: 0,
    owner_found: 0,
    verified: 0,
    previews_approved: 0,
    sent_touch1: 0,
    replied: 0,
    calls: 0,
    closed_won: 0,
  };
}

export const onRequestGet: PagesFunction<Env> = (context) =>
  withErrorHandling(async () => {
    const db = requireSupabase(context.env);

    const [businesses, audits, previews, outreach, phase0, metroStatsRaw] = await Promise.all([
      db.select<BusinessRow>('businesses', {
        select: 'id,metro,is_chain,drop_reason,owner_email,email_status,do_not_contact',
      }),
      db.select<AuditRow>('audits', { select: 'business_id,bucket' }),
      db.select<PreviewRow>('previews', { select: 'business_id,status' }),
      db.select<OutreachRow>('outreach', { select: 'business_id,touch,status,sent_at,reply_sentiment' }),
      db.getConfig('phase0'),
      db.select<MetroStatsRow>('metro_stats', { select: '*', order: [{ column: 'measured_at', ascending: false }] }),
    ]);

    const kept = businesses.filter((b) => !b.is_chain && !b.drop_reason);
    const auditedBizIds = new Set(audits.map((a) => a.business_id));
    const qualifiedBizIds = new Set(audits.filter((a) => a.bucket === 'qualified').map((a) => a.business_id));
    const previewApprovedBizIds = new Set(
      previews.filter((p) => p.status === 'approved' || p.status === 'live').map((p) => p.business_id),
    );

    const funnels = new Map<string, ReturnType<typeof emptyFunnel>>();
    const metroOf = (id: string) => kept.find((b) => b.id === id)?.metro;

    for (const b of kept) {
      const f = funnels.get(b.metro) ?? emptyFunnel();
      f.businesses += 1;
      if (auditedBizIds.has(b.id)) f.audited += 1;
      if (qualifiedBizIds.has(b.id)) f.qualified += 1;
      if (b.owner_email) f.owner_found += 1;
      if (b.email_status === 'deliverable') f.verified += 1;
      if (previewApprovedBizIds.has(b.id)) f.previews_approved += 1;
      funnels.set(b.metro, f);
    }

    const repliedTouch1BusinessIds = new Set<string>();
    const touchTotals: Record<number, { sent: number; replied: number }> = { 1: { sent: 0, replied: 0 }, 2: { sent: 0, replied: 0 }, 3: { sent: 0, replied: 0 }, 4: { sent: 0, replied: 0 } };

    for (const o of outreach) {
      const metro = metroOf(o.business_id);
      const wasSent = o.status !== 'queued' && o.status !== 'drafted';
      const wasReplied = ['replied', 'call_booked', 'closed_won', 'closed_lost'].includes(o.status);
      if (o.touch >= 1 && o.touch <= 4 && wasSent) {
        touchTotals[o.touch]!.sent += 1;
        if (wasReplied) touchTotals[o.touch]!.replied += 1;
      }
      if (!metro) continue;
      const f = funnels.get(metro) ?? emptyFunnel();
      if (o.touch === 1 && wasSent) f.sent_touch1 += 1;
      if (wasReplied) repliedTouch1BusinessIds.add(o.business_id);
      if (o.status === 'call_booked' || o.status === 'closed_won') f.calls += 1;
      if (o.status === 'closed_won') f.closed_won += 1;
      funnels.set(metro, f);
    }
    for (const [metro, f] of funnels) {
      f.replied = [...repliedTouch1BusinessIds].filter((id) => metroOf(id) === metro).length;
      funnels.set(metro, f);
    }

    const replyRatePerTouch: Record<string, number> = {};
    for (const [touch, t] of Object.entries(touchTotals)) {
      replyRatePerTouch[touch] = t.sent === 0 ? 0 : t.replied / t.sent;
    }

    const totalSends = outreach.filter((o) => o.status !== 'queued' && o.status !== 'drafted').length;
    const totalReplies = outreach.filter((o) => ['replied', 'call_booked', 'closed_won', 'closed_lost'].includes(o.status)).length;
    const sendsPerReply = totalReplies === 0 ? null : totalSends / totalReplies;

    const today = new Date().toISOString().slice(0, 10);
    const bounceRate = bounceRate30d(
      outreach.map((o) => ({ status: o.status, sent_at: o.sent_at, reply_sentiment: o.reply_sentiment })),
      today,
    );

    const latestMetroStats = new Map<string, MetroStatsRow>();
    for (const row of metroStatsRaw) {
      if (!latestMetroStats.has(row.metro)) latestMetroStats.set(row.metro, row);
    }

    return json({
      funnel_by_metro: Object.fromEntries(funnels),
      reply_rate_per_touch: replyRatePerTouch,
      sends_per_reply: sendsPerReply,
      bounce_rate_30d: bounceRate,
      phase0: phase0 ?? { passed: false, sends: 0, calls_booked: 0 },
      metro_stats: [...latestMetroStats.values()],
    });
  });
