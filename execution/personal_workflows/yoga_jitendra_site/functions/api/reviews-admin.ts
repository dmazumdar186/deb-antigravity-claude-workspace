// Cloudflare Pages Function: /api/reviews-admin
//
// Moderation CRUD. Behind existing Basic-Auth via _middleware.ts. Used by
// /dashboard/reviews to approve/reject/edit/delete/import reviews.
//
// GET  ?type=pending|approved  → list of records
// GET  ?count=1                 → { pending, approved } counts (for badge)
// POST FormData:
//     action=approve  id=<pending-id>  [featured=1]  [name=<override>] [rating=<override>] [body=<override>] [lang=<override>]
//     action=reject   id=<pending-id>
//     action=edit     id=<approved-id> [name=..] [rating=..] [body=..] [featured=..] [lang=..]
//     action=delete   id=<approved-id>
//     action=import   name=..&rating=..&body=..&source=..&source_url=..&lang=..&submitted_at=.. [featured=..]
//
// Firing a Pages Deploy Hook after any mutation is handled by the caller
// (see dashboard/reviews.astro) via a separate POST — this endpoint stays
// pure CRUD so tests can hit it without triggering deploys.

export interface Env {
  DASHBOARD_KV?: KVNamespace;
  DEPLOY_HOOK_URL?: string;
}

const PENDING_PREFIX = 'review:pending:';
const APPROVED_PREFIX = 'review:approved:';

const ALLOWED_SOURCES = new Set([
  'onsite',
  'meetup',
  'superprof',
  'trainme',
  'instagram',
  'email',
  'other',
]);
const ALLOWED_LANGS = new Set(['fr', 'en']);

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      'Cache-Control': 'no-store',
    },
  });
}

async function listAll(env: Env, prefix: string): Promise<Array<{ key: string; value: unknown }>> {
  const out: Array<{ key: string; value: unknown }> = [];
  let cursor: string | undefined = undefined;
  let iterations = 0;
  do {
    const listRes: KVNamespaceListResult<unknown, string> = await env.DASHBOARD_KV!.list({
      prefix,
      limit: 1000,
      cursor,
    });
    for (const k of listRes.keys) {
      const raw = await env.DASHBOARD_KV!.get(k.name);
      if (!raw) continue;
      try {
        out.push({ key: k.name, value: JSON.parse(raw) });
      } catch (e) {
        console.error('reviews-admin: corrupt entry', k.name, e);
      }
    }
    cursor = listRes.list_complete ? undefined : (listRes as { cursor?: string }).cursor;
    iterations += 1;
    if (iterations > 10) {
      // Hard cap at 10 * 1000 = 10k keys per prefix. Log so silent
      // truncation surfaces in observability instead of vanishing.
      console.warn(`reviews-admin: listAll truncated at 10 pages for prefix "${prefix}"; ${out.length} items returned, more may exist`);
      break;
    }
  } while (cursor);
  return out;
}

async function fireDeployHook(env: Env): Promise<{ triggered: boolean; status?: number; error?: string }> {
  if (!env.DEPLOY_HOOK_URL) return { triggered: false, error: 'DEPLOY_HOOK_URL not set' };
  try {
    const resp = await fetch(env.DEPLOY_HOOK_URL, { method: 'POST' });
    return { triggered: true, status: resp.status };
  } catch (err) {
    return { triggered: false, error: (err as Error)?.message || 'fetch failed' };
  }
}

export const onRequestGet: PagesFunction<Env> = async ({ request, env }) => {
  if (!env.DASHBOARD_KV) return jsonResponse({ error: 'kv_unbound' }, 503);

  const url = new URL(request.url);

  // Client-side fire-and-forget rebuild trigger. The moderation UI GETs this
  // after any approve/reject/edit/delete/import so the SSG site rebuilds
  // within ~60s and the new review lands on the public pages + JSON-LD.
  // Auth is inherited from the Basic-Auth middleware (this is under /api/).
  if (url.searchParams.get('deploy_hook_ping') === '1') {
    const result = await fireDeployHook(env);
    return jsonResponse({ ok: result.triggered, ...result });
  }

  if (url.searchParams.get('count') === '1') {
    const pending = await listAll(env, 'review:pending:');
    const approved = await listAll(env, APPROVED_PREFIX);
    return jsonResponse({ pending: pending.length, approved: approved.length });
  }

  const type = (url.searchParams.get('type') || 'pending').toLowerCase();
  const prefix = type === 'approved' ? APPROVED_PREFIX : 'review:pending:';
  const items = await listAll(env, prefix);
  items.sort((a, b) => {
    const av: any = a.value;
    const bv: any = b.value;
    const ak = av.approved_at || av.submitted_at || '';
    const bk = bv.approved_at || bv.submitted_at || '';
    return bk.localeCompare(ak);
  });
  return jsonResponse({ type, count: items.length, items: items.map((i) => ({ key: i.key, ...(i.value as object) })) });
};

export const onRequestPost: PagesFunction<Env> = async ({ request, env }) => {
  if (!env.DASHBOARD_KV) return jsonResponse({ error: 'kv_unbound' }, 503);

  let form: FormData;
  try {
    form = await request.formData();
  } catch {
    return jsonResponse({ error: 'bad_form' }, 400);
  }

  const action = String(form.get('action') ?? '').trim();
  const id = String(form.get('id') ?? '').trim();

  if (action === 'approve') {
    if (!id) return jsonResponse({ error: 'missing_id' }, 400);
    const pendingKey = 'review:pending:' + id;
    const raw = await env.DASHBOARD_KV.get(pendingKey);
    if (!raw) return jsonResponse({ error: 'not_found' }, 404);

    let record: any;
    try {
      record = JSON.parse(raw);
    } catch {
      return jsonResponse({ error: 'corrupt_record' }, 500);
    }

    // Overrides — moderator can trim/correct name, rating, body, lang.
    const overrideName = String(form.get('name') ?? '').trim();
    const overrideRating = parseInt(String(form.get('rating') ?? ''), 10);
    const overrideBody = String(form.get('body') ?? '').trim();
    const overrideLang = String(form.get('lang') ?? '').trim();
    if (overrideName) record.name = overrideName.slice(0, 60);
    if (Number.isFinite(overrideRating) && overrideRating >= 1 && overrideRating <= 5) record.rating = overrideRating;
    if (overrideBody) record.body = overrideBody.slice(0, 2000);
    if (overrideLang && ALLOWED_LANGS.has(overrideLang)) record.lang = overrideLang;

    record.approved_at = new Date().toISOString();
    record.featured = String(form.get('featured') ?? '').trim() === '1';
    // Strip PII we no longer need once approved.
    delete record.hashed_ip;
    delete record.ua;
    delete record.ref;

    const approvedKey = APPROVED_PREFIX + record.approved_at + ':' + id.slice(0, 8);
    await env.DASHBOARD_KV.put(approvedKey, JSON.stringify(record));
    await env.DASHBOARD_KV.delete(pendingKey);

    return jsonResponse({ ok: true, approved_key: approvedKey });
  }

  if (action === 'reject') {
    if (!id) return jsonResponse({ error: 'missing_id' }, 400);
    const pendingKey = 'review:pending:' + id;
    await env.DASHBOARD_KV.delete(pendingKey);
return jsonResponse({ ok: true });
  }

  if (action === 'delete') {
    // id here is the full approved key (URL-encoded from the moderation UI).
    if (!id) return jsonResponse({ error: 'missing_id' }, 400);
    const targetKey = id.startsWith(APPROVED_PREFIX) ? id : APPROVED_PREFIX + id;
    await env.DASHBOARD_KV.delete(targetKey);
    return jsonResponse({ ok: true });
  }

  if (action === 'edit') {
    if (!id) return jsonResponse({ error: 'missing_id' }, 400);
    const targetKey = id.startsWith(APPROVED_PREFIX) ? id : APPROVED_PREFIX + id;
    const raw = await env.DASHBOARD_KV.get(targetKey);
    if (!raw) return jsonResponse({ error: 'not_found' }, 404);
    let record: any;
    try {
      record = JSON.parse(raw);
    } catch {
      return jsonResponse({ error: 'corrupt_record' }, 500);
    }
    const overrideName = String(form.get('name') ?? '').trim();
    const overrideRating = parseInt(String(form.get('rating') ?? ''), 10);
    const overrideBody = String(form.get('body') ?? '').trim();
    const overrideLang = String(form.get('lang') ?? '').trim();
    const overrideFeatured = String(form.get('featured') ?? '').trim();
    if (overrideName) record.name = overrideName.slice(0, 60);
    if (Number.isFinite(overrideRating) && overrideRating >= 1 && overrideRating <= 5) record.rating = overrideRating;
    if (overrideBody) record.body = overrideBody.slice(0, 2000);
    if (overrideLang && ALLOWED_LANGS.has(overrideLang)) record.lang = overrideLang;
    if (overrideFeatured === '1' || overrideFeatured === 'true') record.featured = true;
    if (overrideFeatured === '0' || overrideFeatured === 'false') record.featured = false;
    record.edited_at = new Date().toISOString();
    await env.DASHBOARD_KV.put(targetKey, JSON.stringify(record));
    return jsonResponse({ ok: true });
  }

  if (action === 'import') {
    // Manual import from Meetup / Superprof / TrainMe / Instagram / email
    // etc. Same schema as an approved user submission but flagged verified.
    const name = String(form.get('name') ?? '').trim().slice(0, 60);
    const rating = parseInt(String(form.get('rating') ?? '5'), 10);
    const body = String(form.get('body') ?? '').trim().slice(0, 2000);
    const source = String(form.get('source') ?? 'other').trim();
    const sourceUrl = String(form.get('source_url') ?? '').trim();
    const lang = String(form.get('lang') ?? 'fr').trim();
    const submittedAt = String(form.get('submitted_at') ?? '').trim() || new Date().toISOString();
    const featured = String(form.get('featured') ?? '').trim() === '1';

    if (!name || name.length < 2) return jsonResponse({ error: 'name' }, 400);
    if (!Number.isFinite(rating) || rating < 1 || rating > 5) return jsonResponse({ error: 'rating' }, 400);
    if (!body || body.length < 10) return jsonResponse({ error: 'body' }, 400);
    if (!ALLOWED_SOURCES.has(source)) return jsonResponse({ error: 'source' }, 400);
    if (!ALLOWED_LANGS.has(lang)) return jsonResponse({ error: 'lang' }, 400);

    const now = new Date().toISOString();
    const importId = crypto.randomUUID();
    const record = {
      id: importId,
      name,
      rating,
      body,
      source,
      source_url: sourceUrl || null,
      lang,
      submitted_at: submittedAt,
      approved_at: now,
      featured,
      verified: true,
    };
    const approvedKey = APPROVED_PREFIX + now + ':' + importId.slice(0, 8);
    await env.DASHBOARD_KV.put(approvedKey, JSON.stringify(record));
    return jsonResponse({ ok: true, approved_key: approvedKey });
  }

  return jsonResponse({ error: 'unknown_action', action }, 400);
};
