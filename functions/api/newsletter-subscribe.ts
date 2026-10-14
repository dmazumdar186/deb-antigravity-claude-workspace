// Cloudflare Pages Function: POST /api/newsletter-subscribe
//
// KV-only fallback backend for the newsletter opt-in popup.
//
// 2026-08-05 backend swap: this file was originally a Brevo double-opt-in
// wrapper (see docs/gdpr_newsletter_popup_assessment.md for the assessed
// architecture). Operator elected a KV-only fallback for today because
// a Brevo account has not yet been provisioned. Brevo integration is
// deferred, not abandoned.
//
// TODO(brevo): re-introduce the Brevo DOI call when the operator has
// provisioned an account + list + template. Batch-import every existing
// newsletter:sub:* record into Brevo's DOI flow (force re-confirmation)
// BEFORE any first marketing campaign send, so unconfirmed KV addresses
// cannot receive marketing email without a fresh opt-in click. The
// hardening entry in HARDENING.md (2026-08-05 session 3) captures this
// commitment explicitly.
//
// Contract:
//   POST application/json  { email, consent, lang, consent_text_version, source_url }
//   → 202  { ok: true, message: "Merci !" }                normal KV write success
//   → 400  { ok: false, error: "..." }                     validation failed
//   → 429  { ok: false, error: "rate_limited" }            too many attempts
//   → 500  { ok: false, error: "internal" }                KV unreachable
//
// Storage side-effects:
//   - KV put(newsletter:sub:<sha256(email)>, {email, ts, ip_hash,
//     consent_text_version, source_url, lang, method: "kv-only-fallback"},
//     TTL 3y)   -- plaintext email is stored today because this sub IS the
//     list until Brevo lands. HARDENING.md notes the widened exposure.
//   - KV incr(newsletter:rl:<ip-hash>, TTL 1h)
//
// Non-enumerability preserved: a repeat submit for the same email returns
// 202 either way; KV put is idempotent (last-write-wins on the same key).

export interface Env {
  DASHBOARD_KV?: KVNamespace;
}

const CONSENT_PROOF_TTL_SECONDS = 3 * 365 * 24 * 60 * 60; // 3 years
const RATE_LIMIT_WINDOW_SECONDS = 60 * 60;                // 1 hour
const RATE_LIMIT_MAX = 5;                                 // 5 attempts / IP / hour
const EMAIL_MAX_LEN = 254;
// RFC 5321-ish, permissive; the definitive check is a delivery test.
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

interface SubscribeBody {
  email?: unknown;
  consent?: unknown;
  lang?: unknown;
  consent_text_version?: unknown;
  source_url?: unknown;
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      'Cache-Control': 'no-store',
    },
  });
}

async function sha256Hex(input: string): Promise<string> {
  const buf = new TextEncoder().encode(input);
  const digest = await crypto.subtle.digest('SHA-256', buf);
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

async function ipHash(ip: string, salt: string): Promise<string> {
  return sha256Hex(`${salt || 'yj-nl'}::${ip}`);
}

async function checkAndBumpRateLimit(
  env: Env,
  ipKey: string,
): Promise<{ ok: true } | { ok: false; retryAfter: number }> {
  if (!env.DASHBOARD_KV) return { ok: true }; // KV unbound → fail-open
  const key = `newsletter:rl:${ipKey}`;
  const raw = await env.DASHBOARD_KV.get(key);
  const now = Math.floor(Date.now() / 1000);
  let entry = raw ? (JSON.parse(raw) as { count: number; window_start: number }) : null;
  if (!entry || now - entry.window_start > RATE_LIMIT_WINDOW_SECONDS) {
    entry = { count: 0, window_start: now };
  }
  entry.count += 1;
  await env.DASHBOARD_KV.put(key, JSON.stringify(entry), {
    expirationTtl: RATE_LIMIT_WINDOW_SECONDS,
  });
  if (entry.count > RATE_LIMIT_MAX) {
    return {
      ok: false,
      retryAfter: RATE_LIMIT_WINDOW_SECONDS - (now - entry.window_start),
    };
  }
  return { ok: true };
}

export const onRequestPost: PagesFunction<Env> = async ({ request, env }) => {
  // --- Parse + validate ---
  let body: SubscribeBody;
  try {
    body = (await request.json()) as SubscribeBody;
  } catch {
    return json({ ok: false, error: 'bad_body' }, 400);
  }

  const email = String(body.email ?? '').trim().toLowerCase();
  const consent = body.consent === true || body.consent === 'true' || body.consent === 'on';
  const lang = body.lang === 'en' ? 'en' : 'fr';
  const consentTextVersion = String(body.consent_text_version ?? '').slice(0, 32);
  const sourceUrl = String(body.source_url ?? '').slice(0, 500);

  if (!email || email.length > EMAIL_MAX_LEN || !EMAIL_RE.test(email)) {
    return json({ ok: false, error: 'bad_email' }, 400);
  }
  if (!consent) {
    return json({ ok: false, error: 'consent_required' }, 400);
  }
  if (!consentTextVersion) {
    return json({ ok: false, error: 'missing_consent_version' }, 400);
  }

  // --- Rate limit ---
  const ip = request.headers.get('CF-Connecting-IP') || '0.0.0.0';
  const salt = (env as Record<string, unknown>).SUBTLECRYPTO_SIGNING_KEY as string | undefined;
  const ipKey = await ipHash(ip, salt || '');
  const rl = await checkAndBumpRateLimit(env, ipKey);
  if (!rl.ok) {
    return new Response(
      JSON.stringify({ ok: false, error: 'rate_limited' }),
      {
        status: 429,
        headers: {
          'Content-Type': 'application/json; charset=utf-8',
          'Retry-After': String(rl.retryAfter),
          'Cache-Control': 'no-store',
        },
      },
    );
  }

  // --- Persist the sub record. This IS the mailing list today.
  // On Brevo swap, this KV prefix is enumerated + force-DOI'd before any
  // first campaign send (see TODO at file head + HARDENING entry).
  if (!env.DASHBOARD_KV) {
    console.error('newsletter-subscribe: DASHBOARD_KV binding missing');
    return json({ ok: false, error: 'not_configured' }, 500);
  }

  const emailHash = await sha256Hex(email);
  const subKey = `newsletter:sub:${emailHash}`;
  const nowIso = new Date().toISOString();

  // Read-before-write: preserve the ORIGINAL first_seen_ts on repeat submits
  // so the dashboard "new in last 7d" delta doesn't inflate when an existing
  // subscriber re-opens the popup (e.g., after clearing localStorage). `ts`
  // moves forward (last-seen); `first_seen_ts` is anchored on the first put.
  let firstSeenTs = nowIso;
  try {
    const existingRaw = await env.DASHBOARD_KV.get(subKey);
    if (existingRaw) {
      try {
        const existing = JSON.parse(existingRaw) as { first_seen_ts?: string; ts?: string };
        // Prefer first_seen_ts; fall back to the older `ts` field for records
        // written before this rule landed.
        firstSeenTs = existing.first_seen_ts || existing.ts || nowIso;
      } catch {
        // Corrupt existing record — treat as new.
      }
    }
  } catch (e) {
    console.error('newsletter-subscribe: KV read-before-write failed, treating as new', e);
  }

  const subRecord = {
    email,                        // plaintext — required so operator can send emails from KV
    email_sha256: emailHash,      // convenience for future dedup
    first_seen_ts: firstSeenTs,   // anchored on first-ever submit for this email
    ts: nowIso,                   // most recent submit (updated on every put)
    ip_hash: ipKey,
    consent_text_version: consentTextVersion,
    source_url: sourceUrl,
    lang,
    method: 'kv-only-fallback' as const,
  };

  try {
    await env.DASHBOARD_KV.put(subKey, JSON.stringify(subRecord), {
      expirationTtl: CONSENT_PROOF_TTL_SECONDS,
      metadata: { location: 'eu' }, // soft region hint
    });
  } catch (e) {
    console.error('newsletter-subscribe: KV write failed', e);
    return json({ ok: false, error: 'internal' }, 500);
  }

  return json(
    {
      ok: true,
      message: lang === 'en'
        ? 'Thanks! Your subscription is saved.'
        : 'Merci ! Votre inscription est enregistrée.',
    },
    202,
  );
};
