// Public job reads (site from Host) and the bearer-authenticated export for the static rebuild.

import { err, json, safeEqual, todayUtc } from '../util.js';
import { renderDescription, safeParam } from '../validate.js';

const LIVE_SQL = `SELECT j.id, j.title, e.name AS employer, j.location, j.region, j.job_type, j.sal_min, j.sal_max,
  j.currency, j.period, j.sal_text, j.sectors_json, j.posted_at, j.closing_at, j.created_at, j.summary,
  j.description, j.apply_mode, j.apply_url
  FROM jobs j LEFT JOIN employers e ON e.id = j.employer_id
  WHERE j.site = ?1 AND j.status = 'live' AND (j.closing_at IS NULL OR j.closing_at >= ?2)`;
// Keyset pagination (#22): ?limit= (default 500, floor 1, ceiling 1000) and ?after=<job id> cursor.
// Every page returns `next` (the last id on the page) or null at the end; callers follow it until null.
export const PAGE_DEFAULT = 500;
export const PAGE_MAX = 1000;

/** Parse ?limit= and ?after=. Returns {ok, limit, after} or {ok:false, res}. */
export function parsePage(q, cors) {
  const n = Number.parseInt(q.get('limit') || '', 10);
  const limit = Number.isFinite(n) ? Math.min(PAGE_MAX, Math.max(1, n)) : PAGE_DEFAULT;
  const raw = q.get('after');
  if (raw === null || raw === '') return { ok: true, limit, after: null };
  const a = safeParam(raw);
  if (!a.ok) return { ok: false, res: err('invalid_cursor', 400, cors) };
  return { ok: true, limit, after: a.value };
}

function parseSectors(s) {
  try {
    const v = JSON.parse(s || '[]');
    return Array.isArray(v) ? v.filter((x) => typeof x === 'string') : [];
  } catch {
    return [];
  }
}

/** Shape of one entry in the static site's data/jobs.json. */
export function toJobsJson(r) {
  return {
    id: r.id,
    title: r.title,
    employer: r.employer || '',
    location: r.location,
    type: r.job_type || '',
    sal_text: r.sal_text || '',
    sectors: parseSectors(r.sectors_json),
    posted: (r.posted_at || r.created_at || '').slice(0, 10),
    closing: r.closing_at ? r.closing_at.slice(0, 10) : '',
    summary: r.summary || '',
  };
}

export async function listJobs(env, site, now, cors, url) {
  const today = todayUtc(now);
  const pg = parsePage(url ? url.searchParams : new URLSearchParams(), cors);
  if (!pg.ok) return pg.res;
  const SORT = 'COALESCE(j.posted_at, j.created_at)';
  let stmt;
  if (pg.after) {
    // The cursor's sort key is read from jobs without the live filter, so a job closed between pages still anchors.
    const cur = await env.DB.prepare('SELECT COALESCE(posted_at, created_at) AS k FROM jobs WHERE id = ?1 AND site = ?2').bind(pg.after, site).first();
    if (!cur) return err('invalid_cursor', 400, cors);
    stmt = env.DB.prepare(`${LIVE_SQL} AND (${SORT} < ?4 OR (${SORT} = ?4 AND j.id > ?5)) ORDER BY ${SORT} DESC, j.id LIMIT ?3`)
      .bind(site, today, pg.limit + 1, cur.k, pg.after);
  } else {
    stmt = env.DB.prepare(`${LIVE_SQL} ORDER BY ${SORT} DESC, j.id LIMIT ?3`).bind(site, today, pg.limit + 1);
  }
  const { results } = await stmt.all();
  const page = results.slice(0, pg.limit);
  const next = results.length > pg.limit ? page[page.length - 1].id : null;
  return json({ today, jobs: page.map(toJobsJson), next }, 200, { ...cors, 'Cache-Control': 'public, max-age=60' });
}

export async function getJob(env, site, rawId, now, cors) {
  const id = safeParam(rawId);
  if (!id.ok) return err('invalid_id', 400, cors);
  if (!id.value.startsWith(`${site}:`)) return err('not_found', 404, cors);
  const r = await env.DB.prepare(`${LIVE_SQL} AND j.id = ?3`).bind(site, todayUtc(now), id.value).first();
  if (!r) return err('not_found', 404, cors);
  return json(
    {
      ...toJobsJson(r),
      description: r.description,
      description_html: renderDescription(r.description),
      apply_mode: r.apply_mode === 'url' ? 'url' : 'form',
      apply_url: r.apply_mode === 'url' ? r.apply_url : null,
    },
    200,
    { ...cors, 'Cache-Control': 'public, max-age=60' },
  );
}

export async function exportJobs(request, env, now) {
  const auth = request.headers.get('Authorization') || '';
  const token = auth.startsWith('Bearer ') ? auth.slice(7) : '';
  if (!env.BUILD_TOKEN) return err('export_not_configured', 503);
  if (!(await safeEqual(token, env.BUILD_TOKEN))) return err('unauthenticated', 401);
  const q = new URL(request.url).searchParams;
  const site = q.get('site');
  if (site !== 'ie' && site !== 'uk') return err('invalid_site', 400);
  const pg = parsePage(q);
  if (!pg.ok) return pg.res;
  const today = todayUtc(now);
  const { results } = await env.DB.prepare(`${LIVE_SQL} AND (?4 IS NULL OR j.id > ?4) ORDER BY j.id LIMIT ?3`)
    .bind(site, today, pg.limit + 1, pg.after)
    .all();
  const page = results.slice(0, pg.limit);
  const next = results.length > pg.limit ? page[page.length - 1].id : null;
  return json({
    site,
    today,
    next,
    jobs: page.map((r) => ({
      ...toJobsJson(r),
      region: r.region || '',
      sal_min: r.sal_min,
      sal_max: r.sal_max,
      cur: r.currency || '',
      period: r.period || '',
      description: r.description,
      apply_mode: r.apply_mode === 'url' ? 'url' : 'form',
      apply_url: r.apply_mode === 'url' ? r.apply_url : null,
    })),
  });
}
