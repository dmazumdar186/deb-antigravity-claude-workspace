// Cloudflare Pages Function: /api/self-report
//
// POST: accepts form data (month, new_students, recurring_students,
//       avg_revenue_eur), validates, writes to KV under key
//       self_report:YYYY-MM. Redirects back to the dashboard on success.
//
// GET:  returns the full report history as { history: [...] } sorted by
//       month ascending. Used by dashboard.astro to hydrate the
//       SelfReportTile at page-load without a build step.
//
// Setup: bind a KV namespace named DASHBOARD_KV in the Cloudflare Pages
// project settings (Settings, Functions, KV namespace bindings). Free
// tier is 100k reads/day and 1k writes/day; this endpoint uses ~50
// reads/1 write per day.
//
// Auth: relies on Cloudflare Access covering /dashboard/* AND
// /api/self-report to gate this endpoint. Without CF Access on the
// endpoint, anyone could POST arbitrary numbers.

export interface Env {
  DASHBOARD_KV?: KVNamespace;
}

interface Entry {
  month: string;
  new_students: number;
  recurring_students: number;
  avg_revenue_eur: number;
  submitted_at: string;
}

const MONTH_RE = /^\d{4}-\d{2}$/;
const KEY_PREFIX = 'self_report:';

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      'Cache-Control': 'no-store',
    },
  });
}

function parseIntSafe(v: FormDataEntryValue | null): number | null {
  if (v === null) return null;
  const n = parseInt(String(v), 10);
  return Number.isFinite(n) ? n : null;
}

export const onRequestPost: PagesFunction<Env> = async ({ request, env }) => {
  const back = (params: string) =>
    Response.redirect(new URL('/dashboard/self-report/?' + params, request.url).toString(), 303);

  if (!env.DASHBOARD_KV) {
    return back('error=kv_unbound');
  }

  let form: FormData;
  try {
    form = await request.formData();
  } catch {
    return back('error=bad_form');
  }

  const month = String(form.get('month') ?? '').slice(0, 7);
  if (!MONTH_RE.test(month)) {
    return back('error=bad_month');
  }

  const newStudents = parseIntSafe(form.get('new_students'));
  const recurring = parseIntSafe(form.get('recurring_students'));
  const avgRevenue = parseIntSafe(form.get('avg_revenue_eur'));

  for (const v of [newStudents, recurring, avgRevenue]) {
    if (v === null || v < 0 || v > 10000) {
      return back('error=bad_number');
    }
  }

  const entry: Entry = {
    month,
    new_students: newStudents!,
    recurring_students: recurring!,
    avg_revenue_eur: avgRevenue!,
    submitted_at: new Date().toISOString(),
  };

  await env.DASHBOARD_KV.put(KEY_PREFIX + month, JSON.stringify(entry));

  return Response.redirect(new URL('/dashboard/?report=saved', request.url).toString(), 303);
};

export const onRequestGet: PagesFunction<Env> = async ({ env }) => {
  if (!env.DASHBOARD_KV) {
    return jsonResponse({ history: [], warning: 'DASHBOARD_KV binding missing' }, 200);
  }

  const list = await env.DASHBOARD_KV.list({ prefix: KEY_PREFIX, limit: 200 });
  const entries: Entry[] = [];
  for (const k of list.keys) {
    const raw = await env.DASHBOARD_KV.get(k.name);
    if (!raw) continue;
    try {
      entries.push(JSON.parse(raw) as Entry);
    } catch (e) {
      // Skip corrupt entry; keep iterating. Log so it does not go silent.
      console.error('self-report: corrupt KV entry, skipping', k.name, e);
    }
  }

  entries.sort((a, b) => a.month.localeCompare(b.month));

  return jsonResponse({ history: entries });
};
