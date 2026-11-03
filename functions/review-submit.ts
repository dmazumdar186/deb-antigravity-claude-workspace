// Cloudflare Pages Function: /review-submit
//
// Public POST endpoint for on-site review submissions. Turnstile-guarded,
// IP rate-limited, writes to `review:pending:<uuid>` in DASHBOARD_KV for
// moderation by Jitendra via /dashboard/reviews.
//
// Same public-endpoint pattern as /wa-out — lives at the top level so the
// _middleware.ts Basic-Auth regex /^\/(dashboard|api)/ does NOT cover it.
// Any visitor must be able to POST here without credentials.
//
// Flow:
//   1. Parse FormData (name, rating, body, source, lang, consent, cf-turnstile-response)
//   2. Basic validation (fields present, rating 1-5, body length, consent=on)
//   3. Turnstile siteverify (server-side; anti-spam)
//   4. Rate-limit check (1 submission / IP / 24h via KV)
//   5. Write to `review:pending:<uuid>` (7d TTL — auto-purge if never moderated)
//   6. Increment `review:pending_count` for the dashboard badge
//   7. 303 redirect to /?review=thanks#testimonials

export interface Env {
  DASHBOARD_KV?: KVNamespace;
  TURNSTILE_SECRET?: string;
}

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
const MAX_NAME_LEN = 60;
const MAX_BODY_LEN = 2000;
const MIN_BODY_LEN = 20;

async function sha256Hex(input: string): Promise<string> {
  const buf = new TextEncoder().encode(input);
  const digest = await crypto.subtle.digest('SHA-256', buf);
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

function todayUTC(): string {
  return new Date().toISOString().slice(0, 10);
}

function back(request: Request, params: string): Response {
  return Response.redirect(new URL('/?' + params + '#testimonials', request.url).toString(), 303);
}

async function verifyTurnstile(token: string, secret: string, ip: string | null): Promise<boolean> {
  try {
    const body = new FormData();
    body.append('secret', secret);
    body.append('response', token);
    if (ip) body.append('remoteip', ip);
    const resp = await fetch('https://challenges.cloudflare.com/turnstile/v0/siteverify', {
      method: 'POST',
      body,
    });
    if (!resp.ok) return false;
    const data = (await resp.json()) as { success?: boolean };
    return data.success === true;
  } catch {
    return false;
  }
}

export const onRequestPost: PagesFunction<Env> = async ({ request, env }) => {
  if (!env.DASHBOARD_KV) {
    return back(request, 'review=error&reason=kv_unbound');
  }
  if (!env.TURNSTILE_SECRET) {
    // Deploy-time misconfig — surface visibly so operator notices, but do
    // NOT accept unverified submissions.
    return back(request, 'review=error&reason=turnstile_unconfigured');
  }

  let form: FormData;
  try {
    form = await request.formData();
  } catch {
    return back(request, 'review=error&reason=bad_form');
  }

  const name = String(form.get('name') ?? '').trim().slice(0, MAX_NAME_LEN);
  const ratingRaw = String(form.get('rating') ?? '').trim();
  const rating = parseInt(ratingRaw, 10);
  const body = String(form.get('body') ?? '').trim().slice(0, MAX_BODY_LEN);
  const source = String(form.get('source') ?? 'onsite').trim();
  const lang = String(form.get('lang') ?? 'fr').trim();
  const consent = String(form.get('consent') ?? '').trim();
  const turnstileToken = String(form.get('cf-turnstile-response') ?? '').trim();

  // Honeypot: attackers frequently fill every field. This field is hidden
  // via CSS in the frontend; a real user won't touch it. If it's non-empty
  // we still return 303 (looks successful to the bot) but silently drop.
  const honeypot = String(form.get('website') ?? '').trim();
  if (honeypot) {
    return back(request, 'review=thanks');
  }

  if (!name || name.length < 2) {
    return back(request, 'review=error&reason=name');
  }
  if (!Number.isFinite(rating) || rating < 1 || rating > 5) {
    return back(request, 'review=error&reason=rating');
  }
  if (!body || body.length < MIN_BODY_LEN) {
    return back(request, 'review=error&reason=body_short');
  }
  if (!ALLOWED_SOURCES.has(source)) {
    return back(request, 'review=error&reason=source');
  }
  if (!ALLOWED_LANGS.has(lang)) {
    return back(request, 'review=error&reason=lang');
  }
  if (consent !== 'on' && consent !== 'true' && consent !== '1') {
    return back(request, 'review=error&reason=consent');
  }
  if (!turnstileToken) {
    return back(request, 'review=error&reason=turnstile_missing');
  }

  const ip = request.headers.get('CF-Connecting-IP') || request.headers.get('X-Real-IP') || null;

  const turnstileOk = await verifyTurnstile(turnstileToken, env.TURNSTILE_SECRET, ip);
  if (!turnstileOk) {
    return back(request, 'review=error&reason=turnstile_failed');
  }

  // Rate-limit: 1 submission per IP per day. KV write with 24h TTL. If key
  // exists, reject. This is per-day granularity (UTC), which is fine — a
  // genuine second review the next day is allowed. Skipped if IP is null
  // (some edge cases in test rigs); Turnstile is still the primary gate.
  if (ip) {
    const rlKey = 'review:rl:' + (await sha256Hex(ip + ':' + todayUTC()));
    const existing = await env.DASHBOARD_KV.get(rlKey);
    if (existing) {
      return back(request, 'review=error&reason=rate_limited');
    }
    await env.DASHBOARD_KV.put(rlKey, '1', { expirationTtl: 24 * 60 * 60 });
  }

  const id = crypto.randomUUID();
  const submittedAt = new Date().toISOString();
  const hashedIp = ip ? await sha256Hex(ip) : null;

  const record = {
    id,
    name,
    rating,
    body,
    source,
    lang,
    submitted_at: submittedAt,
    consent: true,
    hashed_ip: hashedIp,
    ua: request.headers.get('User-Agent') || null,
    ref: request.headers.get('Referer') || null,
    verified: false,
    source_url: null,
  };

  await env.DASHBOARD_KV.put('review:pending:' + id, JSON.stringify(record), {
    expirationTtl: 7 * 24 * 60 * 60,
  });

  // Note: the moderation dashboard's pending badge counts pending items via
  // /api/reviews-admin?count=1 (KV list) — no dedicated `pending_count`
  // key is maintained here to avoid a lost-update race under concurrent
  // submissions.

  return back(request, 'review=thanks');
};
