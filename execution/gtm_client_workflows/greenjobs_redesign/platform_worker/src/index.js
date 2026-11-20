// GreenJobs platform Worker: public job reads, application intake, staff posting console.
// Dry by default (DRY_RUN="1"): no application email leaves unless DRY_RUN="0" AND
// LIVE_CONFIRM="send-applications". See README.md for config and deploy.
//
// createHandler(deps) lets tests inject: jwksFetcher (host -> async () => JWKS), mailTransport
// (async (payload, env, key) => {ok}), now (() => Date). The default export uses the real ones.

import { authenticateAccess, createJwksCache, defaultJwksFetcher } from './auth.js';
import { createMailer } from './mail.js';
import { createRateLimiter } from './ratelimit.js';
import { closeJob, createJob, editJob, getAdminJob, listAdminJobs } from './routes/admin.js';
import { apply, deliverApplication } from './routes/apply.js';
import { consoleAsset, consoleHtml } from './routes/console.js';
import { employerRoute } from './routes/employer.js';
import { importBatch } from './routes/import.js';
import { decideReview, listReview, REVIEW_DECIDE_PATH, reviewAsset, reviewHtml } from './routes/review.js';
import { boardRoute, statsRoute } from './routes/board.js';
import { exportJobs, getJob, listJobs } from './routes/public.js';
import { corsHeaders, preflight, siteForHost } from './site.js';
import { clientIp, err, intVar, json, nowIso, sha256Hex, UUID_RE } from './util.js';
import { alertsRoute, runAlerts } from './listmail/alerts.js';
import { newRun } from './listmail/core.js';
import { listMeasures, writeMeasures } from './listmail/measures.js';
import { newsletterAdmin, newsletterConsoleHtml, newsletterConsoleJs, newsletterRoute, runNewsletter } from './listmail/newsletter.js';

const JOB_PATH = /^\/api\/jobs\/([^/]+)$/;
const ADMIN_JOB_PATH = /^\/api\/admin\/jobs\/([^/]+)$/;
const ADMIN_CLOSE_PATH = /^\/api\/admin\/jobs\/([^/]+)\/close$/;
const NEWSLETTER_ADMIN = /^\/api\/admin\/newsletters(\/|$)/;
const STATIC_UNDER_ROUTE = /^\/(ie|uk)\/sectors\/(index\.html)?$/;
// Paths an Access SERVICE token may reach (release-pipeline smoke: create, read back, close one job). Everything
// else under /admin and /api/admin is staff only. The import path is handled before admin() (see route()).
const SERVICE_SCOPES = [
  ['POST', /^\/api\/admin\/jobs$/],
  ['GET', ADMIN_JOB_PATH],
  ['POST', ADMIN_CLOSE_PATH],
];
export const serviceAllowed = (method, path) => SERVICE_SCOPES.some(([m, re]) => m === method && re.test(path));
export const RELEASE = { name: 'greenjobs-platform', schema: '0004' };
const PUBLIC_PREFLIGHT = /^\/api\/(jobs(\/[^/]+)?|apply|alerts|newsletter|stats)$/;

/**
 * Edge cache for public GET pages and /api/stats (Cache API; the responses carry s-maxage <= 300 s, so a
 * console write is public within 5 minutes). Requests with an Origin header are not cached (CORS varies).
 * Absent Cache API (tests, local) = no caching. `produce` may return null (not a board path).
 */
async function cached(request, ctx, produce) {
  const cache = typeof caches !== 'undefined' && caches && caches.default ? caches.default : null;
  if (!cache || request.method !== 'GET' || request.headers.get('Origin')) return produce();
  const hit = await cache.match(request);
  if (hit) return hit;
  const res = await produce();
  if (res && [200, 404, 410].includes(res.status) && ctx && typeof ctx.waitUntil === 'function') ctx.waitUntil(cache.put(request, res.clone()));
  return res;
}

/**
 * GET /api/health: no auth, no secrets. Release + Worker version and whether D1 answers (SELECT 1 and the newest
 * migration's tables). 200 {ok:true} when D1 is reachable, 503 {ok:false} when not. Never cached.
 */
async function health(request, env, now) {
  if (request.method !== 'GET' && request.method !== 'HEAD') return err('method_not_allowed', 405);
  const t0 = Date.now();
  let d1 = false;
  let migrated = null;
  try {
    const r = await env.DB.prepare(`SELECT 1 AS one, (SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name IN ('job_facets','job_review','alert_meta')) AS mig`).first();
    d1 = Boolean(r && r.one === 1);
    migrated = Boolean(r && r.mig === 3);
  } catch {
    d1 = false; // reported as {ok:false, d1.reachable:false}; the error text is never echoed
  }
  const meta = env.CF_VERSION_METADATA && typeof env.CF_VERSION_METADATA === 'object' ? env.CF_VERSION_METADATA : {};
  const release = /^[0-9a-f]{7,40}$/.test(String(env.RELEASE_SHA || '')) ? env.RELEASE_SHA : null;
  const body = {
    ok: d1, service: RELEASE.name, version: { release, worker_version: typeof meta.id === 'string' ? meta.id : null },
    d1: { reachable: d1, migrated, ms: Date.now() - t0 }, time: nowIso(now),
  };
  return json(body, d1 ? 200 : 503);
}

export function createHandler(deps = {}) {
  const getKey = createJwksCache(deps.jwksFetcher || defaultJwksFetcher);
  const rate = createRateLimiter();
  const mailer = createMailer({ transport: deps.mailTransport });
  const clock = deps.now || (() => new Date());
  const originFetch = deps.originFetch || ((req) => fetch(req));

  async function admin(request, env, site, path, now) {
    const allowed = await rate(env, {
      scope: 'admin', key: clientIp(request), limit: intVar(env, 'RATE_ADMIN_PER_MIN', 60), windowSec: 60, nowMs: now.getTime(),
    });
    if (!allowed) return err('rate_limited', 429, { 'Retry-After': '60' });
    const auth = await authenticateAccess(request, env, { getKey, nowMs: now.getTime() }, { allowService: serviceAllowed(request.method, path) });
    if (!auth.ok) return err(auth.code, auth.status);
    const method = request.method;
    const ctx = { env, site, now, request, actor: auth.email };

    if (method === 'GET') {
      if (path === '/admin') return new Response(null, { status: 301, headers: { Location: '/admin/' } });
      if (path === '/admin/') return consoleHtml(site, auth.email);
      if (path === '/admin/newsletter') return env.NEWSLETTER_ENABLED === '1' ? newsletterConsoleHtml(site, auth.email) : err('not_found', 404);
      if (path === '/admin/newsletter.js') return env.NEWSLETTER_ENABLED === '1' ? newsletterConsoleJs() : err('not_found', 404);
      if (path === '/api/admin/list-measures') return json({ measures: await listMeasures(env, now) });
      if (NEWSLETTER_ADMIN.test(path)) return newsletterAdmin(ctx, path);
      if (path === '/admin/review') return reviewHtml(site, auth.email);
      if (path === '/admin/review.js') return reviewAsset();
      if (path === '/api/admin/review') return listReview(ctx);
      if (path.startsWith('/admin/')) return consoleAsset(path.slice(7)) || err('not_found', 404);
      if (path === '/api/admin/jobs') return listAdminJobs(ctx);
      const m = ADMIN_JOB_PATH.exec(path);
      if (m) return getAdminJob(ctx, m[1]);
      return err('not_found', 404);
    }
    if (method !== 'POST' && method !== 'PUT') return err('method_not_allowed', 405);

    // CSRF: same-origin Origin header and a JSON body are both required on every write.
    if (request.headers.get('Origin') !== new URL(request.url).origin) return err('csrf', 403);
    if (!(request.headers.get('Content-Type') || '').toLowerCase().startsWith('application/json')) return err('unsupported_media_type', 415);
    const idemKey = request.headers.get('Idempotency-Key') || '';
    if (!UUID_RE.test(idemKey)) return err('idempotency_key_required', 400);
    ctx.idemKey = idemKey.toLowerCase();

    if (method === 'POST' && path === '/api/admin/jobs') return createJob(ctx);
    if (NEWSLETTER_ADMIN.test(path)) return newsletterAdmin({ ...ctx, transport: deps.mailTransport }, path);
    const review = REVIEW_DECIDE_PATH.exec(path);
    if (method === 'POST' && review) return decideReview(ctx, review[1]);
    const close = ADMIN_CLOSE_PATH.exec(path);
    if (method === 'POST' && close) return closeJob(ctx, close[1]);
    const edit = ADMIN_JOB_PATH.exec(path);
    if (method === 'PUT' && edit) return editJob(ctx, edit[1]);
    return err('not_found', 404);
  }

  async function route(request, env, ctx) {
    const url = new URL(request.url);
    if (url.pathname === '/api/health') return health(request, env, clock());
    const site = siteForHost(env, url.hostname);
    if (!site) return err('unknown_host', 404);
    const path = url.pathname;
    const now = clock();
    const method = request.method;

    // Feed import is server to server: an Access JWT (staff or an allow-listed service token) or bearer BUILD_TOKEN.
    if (path === '/api/admin/import') {
      if (request.headers.get('Cf-Access-Jwt-Assertion')) {
        const allowed = await rate(env, { scope: 'admin', key: clientIp(request), limit: intVar(env, 'RATE_ADMIN_PER_MIN', 60), windowSec: 60, nowMs: now.getTime() });
        if (!allowed) return err('rate_limited', 429, { 'Retry-After': '60' });
        const auth = await authenticateAccess(request, env, { getKey, nowMs: now.getTime() }, { allowService: true });
        if (!auth.ok) return err(auth.code, auth.status);
        return importBatch({ request, env, now, actor: auth.actor });
      }
      return importBatch({ request, env, now });
    }
    if (path === '/employer' || path.startsWith('/employer/') || path.startsWith('/api/employer/')) {
      return employerRoute({ request, env, site, path, now, getKey, rate });
    }
    if (path === '/admin' || path.startsWith('/admin/') || path.startsWith('/api/admin/')) {
      return admin(request, env, site, path, now);
    }
    if (method === 'OPTIONS' && PUBLIC_PREFLIGHT.test(path)) return preflight(request, env);
    if (method === 'GET' && path === '/api/export/jobs') return exportJobs(request, env, now);
    if (!path.startsWith('/api/')) {
      const page = await cached(request, ctx, () => boardRoute(request, env, site, now));
      if (page) return page;
      // The /{site}/sectors/* route also covers the static sectors overview: hand it back to the origin (Pages).
      if (STATIC_UNDER_ROUTE.test(path)) return originFetch(request);
    }

    const cors = corsHeaders(request, env);
    if (cors === null) return err('origin_not_allowed', 403);
    if (method === 'GET' && path === '/api/stats') return cached(request, ctx, () => statsRoute(env, site, now, url, cors));
    if (method === 'GET' && path === '/api/jobs') return listJobs(env, site, now, cors, url);
    const m = JOB_PATH.exec(path);
    if (method === 'GET' && m) return getJob(env, site, m[1], now, cors);
    if (method === 'POST' && path === '/api/apply') return apply({ env, site, now, request, cors, rate, mailer });
    if (path === '/api/alerts' || path.startsWith('/api/alerts/')) {
      if (env.ALERTS_ENABLED !== '1') return err('not_found', 404, cors);
      const clientKey = await sha256Hex(clientIp(request));
      return alertsRoute({ env, site, now, request, cors, rate, transport: deps.mailTransport, path, url, clientKey });
    }
    if (path === '/api/newsletter' || path.startsWith('/api/newsletter/')) {
      if (env.NEWSLETTER_ENABLED !== '1') return err('not_found', 404, cors);
      const clientKey = await sha256Hex(clientIp(request));
      return newsletterRoute({ env, site, now, request, cors, rate, transport: deps.mailTransport, path, url, clientKey });
    }
    return err('not_found', 404, cors);
  }

  return {
    async fetch(request, env, ctx) {
      try {
        return await route(request, env, ctx);
      } catch (e) {
        console.error('worker: unhandled', e && e.name ? e.name : 'Error');
        return err('internal', 500);
      }
    },

    // Cron: retry deliveries still 'pending'/'failed' from the last 48 h (dry run records 'dry_run').
    async scheduled(event, env) {
      const now = clock();
      const since = nowIso(new Date(now.getTime() - 48 * 3600 * 1000));
      const settled = nowIso(new Date(now.getTime() - 2 * 60 * 1000));
      const { results } = await env.DB.prepare(
        `SELECT a.id, a.cv_key, j.id AS job_id, j.title FROM applications a JOIN jobs j ON j.id = a.job_id
         WHERE a.source = 'apply' AND a.delivery_status IN ('pending','failed') AND a.created_at >= ?1 AND a.created_at <= ?2
         ORDER BY a.created_at LIMIT 25`,
      )
        .bind(since, settled)
        .all();
      let failed = 0;
      for (const r of results) {
        let cv = null;
        if (r.cv_key && env.CVS) {
          const obj = await env.CVS.get(r.cv_key);
          if (obj) cv = { ext: r.cv_key.split('.').pop(), bytes: new Uint8Array(await obj.arrayBuffer()) };
        }
        const status = await deliverApplication(env, mailer, r.id, { id: r.job_id, title: r.title }, cv, now);
        if (status === 'failed') failed++;
      }
      if (failed) console.error('cron: deliveries still failing', failed);
      const out = { retried: results.length, failed };
      // Job alerts + newsletter (listmail/): one shared per-run cap; off (and absent from the result) unless flagged on.
      if (env.ALERTS_ENABLED === '1' || env.NEWSLETTER_ENABLED === '1') {
        const lctx = { env, db: env.DB, now, run: newRun(env), transport: deps.mailTransport };
        out.alerts = await runAlerts(lctx);
        out.newsletter = await runNewsletter(lctx);
        await writeMeasures(env, now);
      }
      return out;
    },
  };
}

const handler = createHandler();
export default { fetch: (req, env, ctx) => handler.fetch(req, env, ctx), scheduled: (ev, env, ctx) => handler.scheduled(ev, env, ctx) };
