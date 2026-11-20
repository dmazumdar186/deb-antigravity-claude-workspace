// Public board pages rendered from D1 (ARCHITECTURE.md §3.1): job list, job pages, sector views,
// the jobs sitemap and /api/stats. A post in the console is live on the next request after the
// edge cache (s-maxage <= 300 s) expires, so within 5 minutes (metric M5: 15 minutes).
//
// Paths follow the static tree so the redesign's relative links keep working:
//   /{site}/jobs/            list (filters ?sector= ?loc= (alias ?region=) ?type= ?q=, ?page=N, 25 rows per page)
//   /{site}/jobs/<slug>/     one job; closed or expired -> 410 with a link to the list; unknown -> 404
//   /{site}/sectors/<slug>/  the list filtered to one taxonomy sector
//   /jobs/..., /sectors/...  301 to the /{host site}/ form
//   /sitemap-jobs.xml        every live job of the host's site
// <slug> is the Strategies id for an imported job (/ie/jobs/11488772/, the URL the static demo already
// published) and "<source>-<ref>" otherwise (/ie/jobs/gj-<uuid>/).

import { descriptionHtml, stripTags } from '../render/sanitise.js';
import { TAXONOMY, UNVERIFIED_SOURCE, dashboardKpis, edition, salaryStats, sectorColor, sectorStat, tallies } from '../render/lib.js';
import { datasetFacets, gonePage, jobPage, listPage, sitemap, slim } from '../render/pages.js';
import { err, json, SECURITY_HEADERS, todayUtc } from '../util.js';
import { renderDescription } from '../validate.js';

export const PAGE_SIZE = 25;
export const CACHE_SECONDS = 300; // edge TTL: a console write is public within 5 minutes
const MAX_LIVE = 5000;
const SLUG_RE = /^(?:\d{1,20}|(gj|gaia|broadbean|idibu|logicmelon)-[A-Za-z0-9-]{1,64})$/; // gaia: feed jobs (ie:gaia:<wp id>)

/** D1 id -> public slug, and back. */
export function slugOf(id) {
  const [, source, ref] = String(id).split(':');
  return source === 'strat' ? ref : `${source}-${ref}`;
}
export function idOfSlug(site, slug) {
  if (!SLUG_RE.test(slug)) return null;
  if (/^\d+$/.test(slug)) return `${site}:strat:${slug}`;
  const i = slug.indexOf('-');
  return `${site}:${slug.slice(0, i)}:${slug.slice(i + 1)}`;
}

/** The origin a site's pages canonicalise to: CANONICAL_ORIGIN_IE/UK when set, else the request's own origin. */
export function canonicalOrigin(env, site, url) {
  const v = String(env[`CANONICAL_ORIGIN_${site.toUpperCase()}`] || '').replace(/\/+$/, '');
  return /^https:\/\/[a-z0-9.-]+$/i.test(v) ? v : url.origin;
}

const parseList = (s) => { try { const v = JSON.parse(s || '[]'); return Array.isArray(v) ? v.filter((x) => typeof x === 'string') : []; } catch { return []; } };

const SELECT = `SELECT j.id, j.site, j.title, j.location, j.sal_min, j.sal_max, j.currency, j.period, j.sal_text, j.summary, j.description,
  j.apply_mode, j.apply_url, j.status, j.posted_at, j.closing_at, j.created_at, j.updated_at, e.name AS employer, e.logo_key,
  f.sectors_json AS f_sectors, f.regions_json AS f_regions, f.job_type AS f_type, f.workplace AS f_workplace, f.contract_json AS f_contract,
  f.loc_class AS f_loc, f.level AS f_level, f.is_agency AS f_agency, f.unverified_cur AS f_unverified, f.search_text AS f_text
  FROM jobs j LEFT JOIN employers e ON e.id = j.employer_id LEFT JOIN job_facets f ON f.job_id = j.id`;

// Per-isolate memo of sanitised descriptions, keyed on id + updated_at (an edit changes the key). Bounded.
const MEMO = new Map();
const MEMO_MAX = 4000;
function derived(r, origin) {
  const key = `${r.id}|${r.updated_at}|${origin}`;
  let html = null;
  let text = null;
  const get = () => {
    if (html === null) {
      const hit = MEMO.get(key);
      if (hit) html = hit;
      else {
        html = descriptionHtml(r.description, `${origin}/`, renderDescription);
        if (MEMO.size >= MEMO_MAX) MEMO.delete(MEMO.keys().next().value);
        MEMO.set(key, html);
      }
    }
    return html;
  };
  return { html: get, text: () => (text === null ? (text = stripTags(get())) : text) };
}

/** A D1 row -> the normalised job dict build_site.py renders (facets as stored; nothing re-classified).
 * `text` comes from job_facets.search_text (set at write time); a row without it falls back to sanitising. */
export function toJob(r, site, origin) {
  const slug = slugOf(r.id);
  const d = derived(r, origin);
  const text = r.f_text != null ? r.f_text : d.text();
  const sectors = parseList(r.f_sectors);
  const link = r.apply_mode === 'link' && typeof r.apply_url === 'string' && r.apply_url.startsWith('https://');
  return {
    id: r.id, slug, title: r.title, employer: r.employer || 'Confidential employer', location: r.location,
    regions: parseList(r.f_regions), type: r.f_type || '', sal_min: r.sal_min ?? null, sal_max: r.sal_max ?? null, cur: r.currency || null,
    period: r.period || null, sal_text: (r.sal_text || '').trim(), sectors, color: sectors[0] ? sectorColor(sectors[0]) : '',
    posted: (r.posted_at || r.created_at || '').slice(0, 10), closing: r.closing_at ? r.closing_at.slice(0, 10) : '',
    summary: (r.summary || '').trim() || text.slice(0, 180), text: text.slice(0, 1500),
    // Sanitised on demand: a page renders one description, not the whole board's (Workers CPU budget).
    get description_html() { return d.html(); },
    // Logos live in R2 (employers.logo_key) and are not served yet: the page shows the monogram. The key still
    // counts as "has a logo" for the dashboard's listing-quality score.
    logo: '', lw: 0, lh: 0, has_logo: Boolean(r.logo_key), href: `/${site}/jobs/${slug}/`, url: `${origin}/${site}/jobs/${slug}/`,
    loc_class: r.f_loc || 'unspecified', workplace: r.f_workplace || 'unspecified', level: r.f_level || '', contract: parseList(r.f_contract),
    agency: Boolean(r.f_agency), currency_source: r.f_unverified ? UNVERIFIED_SOURCE : '',
    apply_mode: link ? 'link' : 'email', apply_url: link ? r.apply_url : '', status: r.status, updated_at: r.updated_at,
  };
}

/** Every live, unexpired job of a site, newest first (normalise()'s sort: posted desc, then title desc). */
export async function liveJobs(env, site, today, origin) {
  const { results } = await env.DB.prepare(`${SELECT} WHERE j.site = ?1 AND j.status = 'live' AND (j.closing_at IS NULL OR j.closing_at >= ?2) LIMIT ?3`)
    .bind(site, today, MAX_LIVE).all();
  const jobs = results.map((r) => toJob(r, site, origin));
  jobs.sort((a, b) => (a.posted < b.posted ? 1 : a.posted > b.posted ? -1 : a.title < b.title ? 1 : a.title > b.title ? -1 : 0));
  return jobs;
}

const norm = (s) => String(s || '').toLowerCase().replace(/\s+/g, ' ').trim();
/** Server-side filters, mirroring lib.js filterJobs for q / loc / sector / type. */
export function applyFilters(jobs, f) {
  const words = norm(f.q).split(' ').filter(Boolean);
  const secs = norm(f.sector).split('|').map((x) => x.trim()).filter(Boolean);
  const loc = norm(f.loc);
  const typ = norm(f.type);
  return jobs.filter((j) => {
    if (words.length) {
      const hay = norm([j.title, j.employer, j.location, j.summary, j.sectors.join(' '), j.type, j.text].join(' '));
      if (!words.every((w) => hay.includes(w))) return false;
    }
    if (loc && !(norm(j.location).includes(loc) || j.regions.some((r) => norm(r) === loc))) return false;
    if (secs.length && !j.sectors.some((s) => secs.includes(norm(s)))) return false;
    if (typ && norm(j.type) !== typ && !j.contract.includes(typ.replace(/ /g, '-'))) return false;
    return true;
  });
}

function htmlResponse(body, status, extra = {}) {
  return new Response(body, {
    status,
    headers: {
      'Content-Type': 'text/html; charset=utf-8', ...SECURITY_HEADERS, 'X-Frame-Options': 'SAMEORIGIN',
      'Cache-Control': status === 200 ? `public, max-age=60, s-maxage=${CACHE_SECONDS}` : 'public, max-age=60, s-maxage=60', ...extra,
    },
  });
}
const redirect = (location) => new Response(null, { status: 301, headers: { Location: location, 'Cache-Control': 'public, max-age=3600' } });

const BOARD = /^\/(ie|uk)\/(jobs|sectors)\/(?:([^/]+)\/(?:index\.html)?)?(index\.html)?$/;
const SHORT = /^\/(jobs|sectors)(\/.*)?$/;

/** Returns a Response for a board path, or null when the path is not a board page. */
export async function boardRoute(request, env, hostSite, now) {
  if (request.method !== 'GET' && request.method !== 'HEAD') return null;
  const url = new URL(request.url);
  const path = url.pathname;
  if (path === '/sitemap-jobs.xml') return sitemapResponse(env, hostSite, now, url);
  const short = SHORT.exec(path);
  if (short && (short[1] === 'jobs' || short[2])) return redirect(`/${hostSite}${path}${url.search}`);
  const m = BOARD.exec(path);
  if (!m) return null;
  const [, site, kind, slug] = m;
  if (kind === 'sectors' && !slug) return null; // /{site}/sectors/ is the static sectors page
  if (site !== hostSite) {
    const other = String(env[`CANONICAL_ORIGIN_${site.toUpperCase()}`] || '');
    return /^https:\/\//.test(other) ? redirect(`${other.replace(/\/+$/, '')}${path}${url.search}`) : null;
  }
  const today = todayUtc(now);
  const origin = canonicalOrigin(env, site, url);
  const indexable = env.ROBOTS_INDEX === '1';
  const jobs = await liveJobs(env, site, today, origin);

  if (kind === 'jobs' && slug) {
    const id = idOfSlug(site, slug);
    const hit = id && jobs.find((j) => j.id === id);
    if (hit) return htmlResponse(jobPage(hit, jobs, { site, today, canonical: hit.url, indexable, reqHost: url.hostname }), 200);
    let gone = null;
    if (id) gone = await env.DB.prepare(`SELECT title, status FROM jobs WHERE id = ?1 AND site = ?2`).bind(id, site).first();
    const status = gone && gone.status !== 'draft' ? 410 : 404;
    return htmlResponse(gonePage({ site, today, status, title: status === 410 ? gone.title : '', nJobs: jobs.length, indexable, reqHost: url.hostname }), status);
  }

  const q = url.searchParams;
  const filters = { q: (q.get('q') || '').slice(0, 200), sector: (q.get('sector') || '').slice(0, 200), loc: (q.get('loc') || q.get('region') || '').slice(0, 120), type: (q.get('type') || '').slice(0, 60) };
  let heading = '';
  let samePath = 'jobs/index.html';
  if (kind === 'sectors') {
    const sec = TAXONOMY.sectors.find((s) => s.slug === slug);
    if (!sec) return htmlResponse(gonePage({ site, today, status: 404, title: '', nJobs: jobs.length, indexable, reqHost: url.hostname }), 404);
    filters.sector = sec.name;
    heading = `${sec.name} jobs`;
    samePath = `sectors/${slug}/index.html`;
  }
  const matched = applyFilters(jobs, filters);
  const pages = Math.max(1, Math.ceil(matched.length / PAGE_SIZE));
  const pageNo = Math.min(pages, Math.max(1, Number.parseInt(q.get('page') || '1', 10) || 1));
  const shown = matched.slice((pageNo - 1) * PAGE_SIZE, pageNo * PAGE_SIZE);
  const canonical = kind === 'sectors' ? `${origin}/${site}/sectors/${slug}/` : `${origin}/${site}/jobs/`;
  const tally = tallies(jobs, site);
  const html = listPage({
    site, today, all: jobs, shown, page: pageNo, pages, filters: { ...filters, total: matched.length, ...(kind === 'sectors' ? { sector: '' } : {}) },
    tally, canonical, indexable, heading, samePath, reqHost: url.hostname,
  });
  return htmlResponse(html, 200);
}

async function sitemapResponse(env, site, now, url) {
  const origin = canonicalOrigin(env, site, url);
  const jobs = await liveJobs(env, site, todayUtc(now), origin);
  const urls = [{ loc: `${origin}/${site}/jobs/` }, ...jobs.map((j) => ({ loc: j.url, lastmod: (j.updated_at || '').slice(0, 10) }))];
  return new Response(sitemap(urls), { status: 200, headers: { 'Content-Type': 'application/xml; charset=utf-8', 'Cache-Control': `public, max-age=60, s-maxage=${CACHE_SECONDS}`, ...SECURITY_HEADERS } });
}

/**
 * GET /api/stats?site=ie|uk: every job-derived figure the static pages print, computed from D1 with the
 * same rules as build_site.py (salary_stats, sector_stat, dashboard_kpis; unverified-currency and
 * non-comparable salaries excluded alike). `measures` is the slot for the applications / alerts /
 * advertiser-enquiry feed: each value null until that feed exists, and the dashboard shows null as "coming".
 */
export async function statsRoute(env, hostSite, now, url, cors) {
  const site = url.searchParams.get('site') || hostSite;
  if (site !== 'ie' && site !== 'uk') return err('invalid_site', 400, cors);
  const today = todayUtc(now);
  const jobs = await liveJobs(env, site, today, canonicalOrigin(env, site, url));
  const ed = edition(site);
  const t = tallies(jobs, site);
  const salary = salaryStats(jobs, ed);
  const sectors = t.sectors.map((s) => ({ ...s, stat: s.n ? sectorStat(jobs.filter((j) => j.sectors.includes(s.name)), ed.sym) : '' }));
  return json({
    // live_jobs: the count the paginated /api/jobs list returns (same live filter); the release smoke compares them
    site, asof: today, taxonomy_version: TAXONOMY.version, live_jobs: jobs.length, salary, sectors, regions: t.regions,
    kpis: dashboardKpis(jobs, t.sectors, t.regions, site, today),
    measures: { applications_30d: null, alert_signups_30d: null, advertiser_enquiries_30d: null },
  }, 200, { ...cors, 'Cache-Control': `public, max-age=60, s-maxage=${CACHE_SECONDS}` });
}

export const BOARD_PAGE_DEFAULT = 200;
export const BOARD_PAGE_MAX = 500;

/**
 * GET /api/jobs?view=board&site=ie|uk[&limit=N][&after=<slug>][&text=0]: the live job set in the static board's
 * #gj-data shape (slim() rows, newest first, the same live filter and sort as the board pages), so the static
 * insights charts and board search can read live data instead of the build-time snapshot. Keyset pagination on
 * the board sort: `next` is the last slug of the page, null at the end; an unknown cursor is 400 (the client
 * falls back to the build-time data). The first page (no cursor) also carries `facets` (sectors, regions, types,
 * contracts as build_site.py's dataset_script) and `total`; every page carries `total` so a client can tell the
 * set changed between pages. Cached at the edge <= 300 s like /api/stats.
 */
export async function boardJobsRoute(env, site, now, url, cors) {
  if (site !== 'ie' && site !== 'uk') return err('invalid_site', 400, cors);
  const q = url.searchParams;
  const n = Number.parseInt(q.get('limit') || '', 10);
  const limit = Number.isFinite(n) ? Math.min(BOARD_PAGE_MAX, Math.max(1, n)) : BOARD_PAGE_DEFAULT;
  const after = q.get('after');
  if (after !== null && !SLUG_RE.test(after)) return err('invalid_cursor', 400, cors);
  const text = q.get('text') !== '0';
  const today = todayUtc(now);
  const all = await liveJobs(env, site, today, canonicalOrigin(env, site, url));
  let start = 0;
  if (after !== null) {
    const i = all.findIndex((j) => j.slug === after);
    if (i < 0) return err('invalid_cursor', 400, cors);
    start = i + 1;
  }
  const page = all.slice(start, start + limit);
  const next = start + limit < all.length ? page[page.length - 1].slug : null;
  const body = { site, today, total: all.length, jobs: page.map((j) => slim(j, { publicId: true, text })), next };
  if (after === null) body.facets = datasetFacets(site, all, tallies(all, site));
  return json(body, 200, { ...cors, 'Cache-Control': `public, max-age=60, s-maxage=${CACHE_SECONDS}` });
}

/** GET /api/config?site=: the public feature flags the static boards need before they post anything. */
export function configRoute(env, site, cors) {
  return json({ site, alerts: env.ALERTS_ENABLED === '1', newsletter: env.NEWSLETTER_ENABLED === '1' }, 200,
    { ...cors, 'Cache-Control': 'public, max-age=60, s-maxage=300' });
}
