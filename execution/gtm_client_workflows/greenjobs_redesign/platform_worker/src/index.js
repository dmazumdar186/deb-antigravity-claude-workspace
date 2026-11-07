// GreenJobs platform Worker: public job reads, application intake, staff posting console.
// Dry by default (DRY_RUN="1"): no application email leaves unless DRY_RUN="0" AND
// LIVE_CONFIRM="send-applications". See README.md for config and deploy.
//
// createHandler(deps) lets tests inject: jwksFetcher (host -> async () => JWKS), mailTransport
// (async (payload, env, key) => {ok}), now (() => Date). The default export uses the real ones.

import { authenticateStaff, createJwksCache, defaultJwksFetcher } from './auth.js';
import { createMailer } from './mail.js';
import { createRateLimiter } from './ratelimit.js';
import { closeJob, createJob, editJob, getAdminJob, listAdminJobs } from './routes/admin.js';
import { apply, deliverApplication } from './routes/apply.js';
import { consoleAsset, consoleHtml } from './routes/console.js';
import { exportJobs, getJob, listJobs } from './routes/public.js';
import { corsHeaders, preflight, siteForHost } from './site.js';
import { clientIp, err, intVar, nowIso, UUID_RE } from './util.js';

const JOB_PATH = /^\/api\/jobs\/([^/]+)$/;
const ADMIN_JOB_PATH = /^\/api\/admin\/jobs\/([^/]+)$/;
const ADMIN_CLOSE_PATH = /^\/api\/admin\/jobs\/([^/]+)\/close$/;
const PUBLIC_PREFLIGHT = /^\/api\/(jobs(\/[^/]+)?|apply|alerts|newsletter)$/;

export function createHandler(deps = {}) {
  const getKey = createJwksCache(deps.jwksFetcher || defaultJwksFetcher);
  const rate = createRateLimiter();
  const mailer = createMailer({ transport: deps.mailTransport });
  const clock = deps.now || (() => new Date());

  async function admin(request, env, site, path, now) {
    const allowed = await rate(env, {
      scope: 'admin', key: clientIp(request), limit: intVar(env, 'RATE_ADMIN_PER_MIN', 60), windowSec: 60, nowMs: now.getTime(),
    });
    if (!allowed) return err('rate_limited', 429, { 'Retry-After': '60' });
    const auth = await authenticateStaff(request, env, { getKey, nowMs: now.getTime() });
    if (!auth.ok) return err(auth.code, auth.status);
    const method = request.method;
    const ctx = { env, site, now, request, actor: auth.email };

    if (method === 'GET') {
      if (path === '/admin') return new Response(null, { status: 301, headers: { Location: '/admin/' } });
      if (path === '/admin/') return consoleHtml(site, auth.email);
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
    const close = ADMIN_CLOSE_PATH.exec(path);
    if (method === 'POST' && close) return closeJob(ctx, close[1]);
    const edit = ADMIN_JOB_PATH.exec(path);
    if (method === 'PUT' && edit) return editJob(ctx, edit[1]);
    return err('not_found', 404);
  }

  async function route(request, env) {
    const url = new URL(request.url);
    const site = siteForHost(env, url.hostname);
    if (!site) return err('unknown_host', 404);
    const path = url.pathname;
    const now = clock();
    const method = request.method;

    if (path === '/admin' || path.startsWith('/admin/') || path.startsWith('/api/admin/')) {
      return admin(request, env, site, path, now);
    }
    if (method === 'OPTIONS' && PUBLIC_PREFLIGHT.test(path)) return preflight(request, env);
    if (method === 'GET' && path === '/api/export/jobs') return exportJobs(request, env, now);

    const cors = corsHeaders(request, env);
    if (cors === null) return err('origin_not_allowed', 403);
    if (method === 'GET' && path === '/api/jobs') return listJobs(env, site, now, cors);
    const m = JOB_PATH.exec(path);
    if (method === 'GET' && m) return getJob(env, site, m[1], now, cors);
    if (method === 'POST' && path === '/api/apply') return apply({ env, site, now, request, cors, rate, mailer });
    if (path === '/api/alerts') {
      if (env.ALERTS_ENABLED !== '1') return err('not_found', 404, cors);
      return err('not_implemented', 501, cors); // out of floor scope: stub behind the trim switch
    }
    if (path === '/api/newsletter') {
      if (env.NEWSLETTER_ENABLED !== '1') return err('not_found', 404, cors);
      return err('not_implemented', 501, cors);
    }
    return err('not_found', 404, cors);
  }

  return {
    async fetch(request, env) {
      try {
        return await route(request, env);
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
        if (r.cv_key) {
          const obj = await env.CVS.get(r.cv_key);
          if (obj) cv = { ext: r.cv_key.split('.').pop(), bytes: new Uint8Array(await obj.arrayBuffer()) };
        }
        const status = await deliverApplication(env, mailer, r.id, { id: r.job_id, title: r.title }, cv, now);
        if (status === 'failed') failed++;
      }
      if (failed) console.error('cron: deliveries still failing', failed);
      return { retried: results.length, failed };
    },
  };
}

const handler = createHandler();
export default { fetch: (req, env, ctx) => handler.fetch(req, env, ctx), scheduled: (ev, env, ctx) => handler.scheduled(ev, env, ctx) };
