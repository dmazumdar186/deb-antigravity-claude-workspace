// Cloudflare Pages Function: POST /api/newsletter-subscribe
//
// Newsletter opt-in submission handler. See
// docs/gdpr_newsletter_popup_assessment.md for the full architecture +
// legal analysis.
//
// Contract:
//   POST application/json  { email, consent, lang, consent_text_version, source_url }
//   → 202  { ok: true, message: "check your inbox" }   normal DOI success
//   → 400  { ok: false, error: "..." }                validation failed
//   → 429  { ok: false, error: "rate_limited" }       too many attempts
//   → 500  { ok: false, error: "internal" }           Brevo unreachable / other
//
// The handler never leaks whether an email is already subscribed
// (non-enumerable): it always calls Brevo's DOI endpoint, which
// idempotently sends a fresh confirmation whether the contact exists or
// not, and returns 202 to the browser in either case.
//
// Storage side-effects:
//   - KV put(newsletter:consent:<sha256(email)>, {ts, ip_hash,
//     consent_text_version, source_url, brevo_status}, TTL 3y)
//   - KV incr(newsletter:rl:<ip-hash>, TTL 1h)
//
// Secrets required (set via `wrangler pages secret put ...`):
//   BREVO_API_KEY               Brevo API key ("v2 API" style, xkeysib-...)
//   BREVO_NEWSLETTER_LIST_ID    numeric list ID (Contacts → Lists in Brevo)
//   BREVO_DOI_TEMPLATE_ID       numeric transactional template ID for DOI
//
// Non-secret vars (fine to hardcode below):
//   BREVO_DOI_ENDPOINT          https://api.brevo.com/v3/contacts/doubleOptinConfirmation
//   DOI_REDIRECT_URL            https://yogaavecjitendra.fr/merci

export interface Env {
  DASHBOARD_KV?: KVNamespace;
  BREVO_API_KEY?: string;
  BREVO_NEWSLETTER_LIST_ID?: string;
  BREVO_DOI_TEMPLATE_ID?: string;
}

const BREVO_DOI_ENDPOINT = 'https://api.brevo.com/v3/contacts/doubleOptinConfirmation';
const DOI_REDIRECT_URL = 'https://yogaavecjitendra.fr/merci';
const CONSENT_PROOF_TTL_SECONDS = 3 * 365 * 24 * 60 * 60; // 3 years
const RATE_LIMIT_WINDOW_SECONDS = 60 * 60;                // 1 hour
const RATE_LIMIT_MAX = 5;                                 // 5 attempts / IP / hour
const EMAIL_MAX_LEN = 254;
// RFC 5321-ish, permissive; the definitive check is Brevo's own validation.
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
  // Salt with the signing key so KV alone can't be rainbow-tabled back to
  // raw IPs. Silently degrades to unsalted sha256 if no salt yet configured.
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
  const salt = (env as any).SUBTLECRYPTO_SIGNING_KEY as string | undefined;
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

  // --- Config sanity ---
  if (!env.BREVO_API_KEY || !env.BREVO_NEWSLETTER_LIST_ID || !env.BREVO_DOI_TEMPLATE_ID) {
    console.error('newsletter-subscribe: missing Brevo secrets');
    return json({ ok: false, error: 'not_configured' }, 500);
  }

  const listId = parseInt(env.BREVO_NEWSLETTER_LIST_ID, 10);
  const templateId = parseInt(env.BREVO_DOI_TEMPLATE_ID, 10);
  if (!Number.isFinite(listId) || !Number.isFinite(templateId)) {
    console.error('newsletter-subscribe: Brevo list/template id not numeric');
    return json({ ok: false, error: 'not_configured' }, 500);
  }

  // --- Write consent proof BEFORE calling Brevo. If Brevo fails, we still
  //     have a defensible record that the user asked to subscribe (they can
  //     retry, we can retry). Also protects against a race where Brevo
  //     succeeds but our KV write fails and we lose the proof.
  const emailHash = await sha256Email(email);
  const consentKey = `newsletter:consent:${emailHash}`;
  const consentRecord = {
    email_sha256: emailHash,
    ts: new Date().toISOString(),
    ip_hash: ipKey,
    consent_text_version: consentTextVersion,
    source_url: sourceUrl,
    lang,
    // brevo_status populated after the Brevo call below
    brevo_status: 0,
  };

  if (env.DASHBOARD_KV) {
    try {
      await env.DASHBOARD_KV.put(consentKey, JSON.stringify(consentRecord), {
        expirationTtl: CONSENT_PROOF_TTL_SECONDS,
        metadata: { location: 'eu' }, // soft region hint
      });
    } catch (e) {
      console.error('newsletter-subscribe: KV write failed', e);
      // Continue — Brevo is the source of truth for the mailing list
      // itself; KV consent proof is defensive backup.
    }
  }

  // --- Call Brevo DOI endpoint ---
  let brevoStatus = 0;
  try {
    const brevoRes = await fetch(BREVO_DOI_ENDPOINT, {
      method: 'POST',
      headers: {
        'accept': 'application/json',
        'content-type': 'application/json',
        'api-key': env.BREVO_API_KEY,
      },
      body: JSON.stringify({
        email,
        includeListIds: [listId],
        templateId,
        redirectionUrl: DOI_REDIRECT_URL,
        attributes: {
          LANG: lang,
          SIGNUP_SOURCE: 'popup',
          CONSENT_TS: consentRecord.ts,
          CONSENT_TEXT_VERSION: consentTextVersion,
        },
      }),
    });
    brevoStatus = brevoRes.status;

    // Brevo returns 201 on new-contact DOI-sent, 204 on already-confirmed
    // (idempotent re-request). Both are OK from our perspective.
    if (brevoStatus !== 201 && brevoStatus !== 204 && brevoStatus !== 200) {
      const detail = await brevoRes.text().catch(() => '');
      console.error('newsletter-subscribe: Brevo non-2xx', brevoStatus, detail.slice(0, 400));
      // Update consent proof with the failure status so ops can trace
      if (env.DASHBOARD_KV) {
        try {
          await env.DASHBOARD_KV.put(
            consentKey,
            JSON.stringify({ ...consentRecord, brevo_status: brevoStatus }),
            { expirationTtl: CONSENT_PROOF_TTL_SECONDS },
          );
        } catch {}
      }
      return json({ ok: false, error: 'processor_error' }, 502);
    }
  } catch (e) {
    console.error('newsletter-subscribe: Brevo fetch threw', e);
    return json({ ok: false, error: 'processor_unreachable' }, 502);
  }

  // --- Persist the successful Brevo status on the consent record ---
  if (env.DASHBOARD_KV) {
    try {
      await env.DASHBOARD_KV.put(
        consentKey,
        JSON.stringify({ ...consentRecord, brevo_status: brevoStatus }),
        {
          expirationTtl: CONSENT_PROOF_TTL_SECONDS,
          metadata: { location: 'eu' },
        },
      );
    } catch {}
  }

  return json(
    {
      ok: true,
      message: lang === 'en'
        ? 'Check your inbox — click the confirmation link.'
        : 'Vérifiez votre boîte mail — cliquez sur le lien de confirmation.',
    },
    202,
  );
};

async function sha256Email(email: string): Promise<string> {
  return sha256Hex(email);
}
