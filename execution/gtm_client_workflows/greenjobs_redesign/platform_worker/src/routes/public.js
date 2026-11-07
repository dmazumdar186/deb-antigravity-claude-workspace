// Public job reads (site from Host) and the bearer-authenticated export for the static rebuild.

import { err, json, safeEqual, todayUtc } from '../util.js';
import { renderDescription, safeParam } from '../validate.js';

const LIVE_SQL = `SELECT j.id, j.title, e.name AS employer, j.location, j.region, j.job_type, j.sal_min, j.sal_max,
  j.currency, j.period, j.sal_text, j.sectors_json, j.posted_at, j.closing_at, j.created_at, j.summary,
  j.description, j.apply_mode, j.apply_url
  FROM jobs j LEFT JOIN employers e ON e.id = j.employer_id
  WHERE j.site = ?1 AND j.status = 'live' AND (j.closing_at IS NULL OR j.closing_at >= ?2)`;
const MAX_ROWS = 5000;

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

export async function listJobs(env, site, now, cors) {
  const today = todayUtc(now);
  const { results } = await env.DB.prepare(`${LIVE_SQL} ORDER BY COALESCE(j.posted_at, j.created_at) DESC, j.id LIMIT ?3`)
    .bind(site, today, MAX_ROWS)
    .all();
  return json({ today, jobs: results.map(toJobsJson) }, 200, { ...cors, 'Cache-Control': 'public, max-age=60' });
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
  const site = new URL(request.url).searchParams.get('site');
  if (site !== 'ie' && site !== 'uk') return err('invalid_site', 400);
  const today = todayUtc(now);
  const { results } = await env.DB.prepare(`${LIVE_SQL} ORDER BY j.id LIMIT ?3`).bind(site, today, MAX_ROWS).all();
  return json({
    site,
    today,
    jobs: results.map((r) => ({
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
