// GET /api/previews?status=review
//
// Previews awaiting approval (or any status filter), joined with business +
// latest audit + content (business.json). "Latest audit" here means the
// business's most recent audit row (previews don't carry an audit_id), so
// this is a second query per result set rather than an embed — see README
// "Assumptions".

import type { Env } from '../../_middleware';
import { requireSupabase } from '../../_lib/supabase';
import { json, withErrorHandling } from '../../_lib/http';

interface PreviewRow {
  id: string;
  business_id: string;
  subdomain_url: string;
  status: string;
  content: unknown;
  deployed_at: string | null;
  expires_at: string | null;
  business: {
    id: string;
    name: string;
    owner_first: string | null;
    suburb: string | null;
    website_url: string | null;
  } | null;
}

interface AuditRow {
  business_id: string;
  total_score: number | null;
  bucket: string | null;
  gaps: unknown;
  audited_at: string;
}

export const onRequestGet: PagesFunction<Env> = (context) =>
  withErrorHandling(async () => {
    const url = new URL(context.request.url);
    const status = url.searchParams.get('status');
    const db = requireSupabase(context.env);

    const filters = status ? [{ column: 'status' as const, op: 'eq' as const, value: status }] : [];
    const previews = await db.select<PreviewRow>('previews', {
      select: 'id,business_id,subdomain_url,status,content,deployed_at,expires_at,business:businesses(id,name,owner_first,suburb,website_url)',
      filters,
      order: [{ column: 'created_at', ascending: false }],
    });

    if (previews.length === 0) {
      return json({ previews: [] });
    }

    const businessIds = [...new Set(previews.map((p) => p.business_id))];
    const audits = await db.select<AuditRow>('audits', {
      select: 'business_id,total_score,bucket,gaps,audited_at',
      filters: [{ column: 'business_id', op: 'in', value: businessIds }],
      order: [{ column: 'audited_at', ascending: false }],
    });
    const latestAuditByBusiness = new Map<string, AuditRow>();
    for (const a of audits) {
      if (!latestAuditByBusiness.has(a.business_id)) latestAuditByBusiness.set(a.business_id, a);
    }

    const enriched = previews.map((p) => ({ ...p, audit: latestAuditByBusiness.get(p.business_id) ?? null }));
    return json({ previews: enriched });
  });
