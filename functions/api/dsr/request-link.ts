// Cloudflare Pages Function: POST /api/dsr/request-link
//
// Data Subject Request — magic-link request endpoint.
//
// Contract:
//   POST application/json  { email }
//   → 202 always (non-enumerable). Body: { ok: true, message: "..." }
//
// Rate-limited to 3 attempts per IP per hour so this endpoint can't be
// used to spam Brevo transactional sends.
//
// Flow:
//   1. Rate-limit check (KV: dsr:rl:<ip-hash>).
//   2. HMAC-SHA-256 sign {email_hash, exp} with SUBTLECRYPTO_SIGNING_KEY.
//   3. Send transactional email via Brevo containing the magic link.
//   4. Return 202 regardless of whether the email is actually subscribed.
//
// Secrets required:
//   BREVO_API_KEY                 same key as newsletter-subscribe
//   BREVO_DSR_MAGIC_TEMPLATE_ID   Brevo template ID for the magic-link email
//                                 (body must reference {{ params.dsrUrl }})
//   SUBTLECRYPTO_SIGNING_KEY      64-char hex string (32 random bytes)
//                                 Generate: `openssl rand -hex 32`

export interface Env {
  DASHBOARD_KV?: KVNamespace;
  BREVO_API_KEY?: string;
  BREVO_DSR_MAGIC_TEMPLATE_ID?: string;
  SUBTLECRYPTO_SIGNING_KEY?: string;
}

const BREVO_TRANSACTIONAL_ENDPOINT = 'https://api.brevo.com/v3/smtp/email';
const SITE_ORIGIN = 'https://yogaavecjitendra.fr';
const TOKEN_TTL_SECONDS = 30 * 60; // 30 minutes
const RATE_LIMIT_WINDOW_SECONDS = 60 * 60;
const RATE_LIMIT_MAX = 3;
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const EMAIL_MAX_LEN = 254;

function json(body: unknown, status = 200, extraHeaders: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      'Cache-Control': 'no-store',
      ...extraHeaders,
    },
  });
}

async function sha256Hex(input: string): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(input));
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

function hexToBytes(hex: string): Uint8Array {
  if (hex.length % 2 !== 0) throw new Error('bad hex');
  const out = new Uint8Array(hex.length / 2);
  for (let i = 0; i < out.length; i++) out[i] = parseInt(hex.substr(i * 2, 2), 16);
  return out;
}

function bytesToBase64Url(bytes: Uint8Array): string {
  let s = '';
  for (let i = 0; i < bytes.length; i++) s += String.fromCharCode(bytes[i]);
  return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

async function importHmacKey(keyHex: string): Promise<CryptoKey> {
  return crypto.subtle.importKey(
    'raw',
    hexToBytes(keyHex),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign', 'verify'],
  );
}

/**
 * Sign a compact token: base64url(payload).base64url(hmac(payload)).
 * payload = JSON({ e: email_sha256, x: exp_unix }).
 */
export async function signDsrToken(
  emailHash: string,
  expUnix: number,
  keyHex: string,
): Promise<string> {
  const key = await importHmacKey(keyHex);
  const payload = JSON.stringify({ e: emailHash, x: expUnix });
  const payloadB64 = bytesToBase64Url(new TextEncoder().encode(payload));
  const sig = await crypto.subtle.sign(
    'HMAC',
    key,
    new TextEncoder().encode(payloadB64),
  );
  const sigB64 = bytesToBase64Url(new Uint8Array(sig));
  return `${payloadB64}.${sigB64}`;
}

async function checkAndBumpRateLimit(
  env: Env,
  ipKey: string,
): Promise<{ ok: true } | { ok: false; retryAfter: number }> {
  if (!env.DASHBOARD_KV) return { ok: true };
  const key = `dsr:rl:${ipKey}`;
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
    return { ok: false, retryAfter: RATE_LIMIT_WINDOW_SECONDS - (now - entry.window_start) };
  }
  return { ok: true };
}

export const onRequestPost: PagesFunction<Env> = async ({ request, env }) => {
  let body: { email?: unknown; lang?: unknown };
  try {
    body = await request.json();
  } catch {
    return json({ ok: false, error: 'bad_body' }, 400);
  }

  const email = String(body.email ?? '').trim().toLowerCase();
  const lang = body.lang === 'en' ? 'en' : 'fr';
  const generic = lang === 'en'
    ? 'If this address is on record, we have sent you a link. Check your inbox.'
    : "Si cette adresse est enregistrée, nous vous avons envoyé un lien. Vérifiez votre boîte mail.";

  // Even invalid email → 202 (non-enumerable). But we don't waste a
  // Brevo send on obviously bogus input.
  if (!email || email.length > EMAIL_MAX_LEN || !EMAIL_RE.test(email)) {
    return json({ ok: true, message: generic }, 202);
  }

  const ip = request.headers.get('CF-Connecting-IP') || '0.0.0.0';
  const ipKey = await sha256Hex(`dsr::${ip}`);
  const rl = await checkAndBumpRateLimit(env, ipKey);
  if (!rl.ok) {
    return json({ ok: true, message: generic }, 202, {
      'Retry-After': String(rl.retryAfter),
    });
  }

  if (!env.BREVO_API_KEY || !env.BREVO_DSR_MAGIC_TEMPLATE_ID || !env.SUBTLECRYPTO_SIGNING_KEY) {
    console.error('dsr/request-link: missing secrets');
    // Still 202 so callers get the generic message; ops sees the log.
    return json({ ok: true, message: generic }, 202);
  }

  const templateId = parseInt(env.BREVO_DSR_MAGIC_TEMPLATE_ID, 10);
  if (!Number.isFinite(templateId)) {
    console.error('dsr/request-link: DSR template id not numeric');
    return json({ ok: true, message: generic }, 202);
  }

  const emailHash = await sha256Hex(email);
  const exp = Math.floor(Date.now() / 1000) + TOKEN_TTL_SECONDS;

  let token: string;
  try {
    token = await signDsrToken(emailHash, exp, env.SUBTLECRYPTO_SIGNING_KEY);
  } catch (e) {
    console.error('dsr/request-link: sign failed', e);
    return json({ ok: true, message: generic }, 202);
  }

  const dsrUrl = `${SITE_ORIGIN}/api/dsr/${encodeURIComponent(token)}?e=${encodeURIComponent(email)}&lang=${lang}`;

  try {
    const res = await fetch(BREVO_TRANSACTIONAL_ENDPOINT, {
      method: 'POST',
      headers: {
        'accept': 'application/json',
        'content-type': 'application/json',
        'api-key': env.BREVO_API_KEY,
      },
      body: JSON.stringify({
        to: [{ email }],
        templateId,
        params: {
          dsrUrl,
          lang,
          expiryMinutes: Math.floor(TOKEN_TTL_SECONDS / 60),
        },
      }),
    });
    if (res.status !== 201 && res.status !== 200) {
      const detail = await res.text().catch(() => '');
      console.error('dsr/request-link: Brevo non-2xx', res.status, detail.slice(0, 400));
    }
  } catch (e) {
    console.error('dsr/request-link: Brevo fetch threw', e);
  }

  return json({ ok: true, message: generic }, 202);
};
