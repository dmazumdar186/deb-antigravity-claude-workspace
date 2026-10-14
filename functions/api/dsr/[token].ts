// Cloudflare Pages Function: GET / DELETE /api/dsr/:token
//
// Data Subject Request — magic-link target endpoint.
//
// Query params:
//   e=<email>   the email the request-link endpoint was asked about (used
//               to derive the KV key + call Brevo delete). Must match the
//               email_sha256 baked into the signed token, otherwise reject.
//   lang=fr|en  which language to render the page in
//
// Contract:
//   GET  → verify HMAC + not expired → render HTML view of stored data +
//          a form that POSTs to same URL with _method=DELETE
//   DELETE (or POST with _method=DELETE) → verify → purge KV consent record
//                                          → call Brevo contact delete
//                                          → render "your data is gone" page
//
// Rendering is server-side HTML string (not Astro) so this survives without
// the Pages static assets pipeline touching it.

export interface Env {
  DASHBOARD_KV?: KVNamespace;
  BREVO_API_KEY?: string;
  SUBTLECRYPTO_SIGNING_KEY?: string;
}

const BREVO_CONTACTS_ENDPOINT = 'https://api.brevo.com/v3/contacts';
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// ---------- crypto helpers (mirror of request-link.ts) ----------

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

function base64UrlDecode(s: string): Uint8Array {
  s = s.replace(/-/g, '+').replace(/_/g, '/');
  while (s.length % 4) s += '=';
  const bin = atob(s);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
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

interface VerifiedToken { emailHash: string; exp: number; }

async function verifyDsrToken(token: string, keyHex: string): Promise<VerifiedToken | null> {
  const parts = token.split('.');
  if (parts.length !== 2) return null;
  const [payloadB64, sigB64] = parts;

  let key: CryptoKey;
  try { key = await importHmacKey(keyHex); }
  catch { return null; }

  let ok = false;
  try {
    ok = await crypto.subtle.verify(
      'HMAC',
      key,
      base64UrlDecode(sigB64),
      new TextEncoder().encode(payloadB64),
    );
  } catch { return null; }
  if (!ok) return null;

  let payload: { e?: string; x?: number };
  try {
    payload = JSON.parse(new TextDecoder().decode(base64UrlDecode(payloadB64)));
  } catch { return null; }

  if (!payload.e || typeof payload.x !== 'number') return null;
  if (Math.floor(Date.now() / 1000) > payload.x) return null; // expired
  return { emailHash: payload.e, exp: payload.x };
}

// ---------- HTML rendering ----------

function esc(s: string): string {
  return s.replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c] || c
  ));
}

function pageShell(lang: 'fr' | 'en', bodyHtml: string): Response {
  const title = lang === 'en'
    ? 'Manage your newsletter data — Yoga avec Jitendra'
    : 'Gérer vos données de newsletter — Yoga avec Jitendra';
  const html = `<!doctype html>
<html lang="${lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>${esc(title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:wght@500;600&family=Inter:wght@400;500&display=swap">
<style>
  body { font-family: 'Inter', system-ui, sans-serif; background: #f8f4ed; color: #2e2a26; margin: 0; padding: 2rem 1rem; }
  main { max-width: 640px; margin: 0 auto; background: #fffdf9; border-radius: 12px; padding: 2rem 1.75rem; box-shadow: 0 8px 24px rgba(0,0,0,0.08); }
  h1 { font-family: 'Fraunces', Georgia, serif; margin-top: 0; }
  h2 { font-family: 'Fraunces', Georgia, serif; font-size: 1.15rem; margin-top: 1.75rem; }
  .kv { background: #f5f0e6; border-radius: 8px; padding: 0.85rem 1rem; font-family: ui-monospace, monospace; font-size: 0.85rem; word-break: break-all; }
  .row { display: flex; gap: 0.6rem; margin: 0.4rem 0; }
  .row strong { min-width: 130px; }
  form { margin-top: 1.75rem; }
  button, .btn {
    display: inline-block; font: inherit; font-weight: 500;
    padding: 0.7rem 1.1rem; border-radius: 8px; cursor: pointer;
    border: 1px solid transparent; text-decoration: none;
  }
  button.danger { background: #c05b3e; color: white; }
  button.danger:hover { background: #a94b30; }
  .btn.ghost { background: white; color: #2e2a26; border-color: rgba(46,42,38,0.22); }
  .notice { background: rgba(192,91,62,0.08); padding: 1rem; border-radius: 8px; font-size: 0.9rem; margin-bottom: 1.25rem; }
  .expired { background: rgba(192,91,62,0.12); color: #8a3820; padding: 1rem; border-radius: 8px; }
  a { color: #c05b3e; }
</style>
</head>
<body>
<main>
${bodyHtml}
</main>
</body>
</html>`;
  return new Response(html, {
    status: 200,
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
      'Cache-Control': 'no-store',
      'X-Robots-Tag': 'noindex, nofollow',
    },
  });
}

function renderInvalid(lang: 'fr' | 'en'): Response {
  const msg = lang === 'en'
    ? {
        h: 'Link invalid or expired',
        p: 'Magic links are valid for 30 minutes. Please request a new one from the privacy notice page.',
        back: 'Back to privacy notice',
        backHref: '/en/privacy/newsletter',
      }
    : {
        h: 'Lien invalide ou expiré',
        p: "Les liens magiques sont valables 30 minutes. Merci d'en demander un nouveau depuis la page de politique de confidentialité.",
        back: 'Retour à la politique de confidentialité',
        backHref: '/privacy/newsletter',
      };
  return pageShell(lang, `
    <h1>${esc(msg.h)}</h1>
    <p class="expired">${esc(msg.p)}</p>
    <p><a class="btn ghost" href="${msg.backHref}">${esc(msg.back)}</a></p>
  `);
}

function renderView(
  lang: 'fr' | 'en',
  email: string,
  token: string,
  consentRecord: any,
): Response {
  const t = lang === 'en'
    ? {
        h1: 'Your data',
        intro: 'Here is everything we hold about your subscription. Any question, email jitendranitrr13@gmail.com.',
        emailLabel: 'Email',
        timestampLabel: 'Signup timestamp',
        consentVersion: 'Consent text version',
        source: 'Signup source',
        lang: 'Language',
        brevoNote: 'The email itself lives at Brevo (Sendinblue SAS — France). Cloudflare only holds this technical consent proof.',
        h2: 'Delete everything',
        deleteHelp: 'Clicking below will (1) delete the record above, and (2) remove your email from the Brevo mailing list. Immediate and irreversible.',
        deleteBtn: 'Delete my data',
        back: 'Back to privacy notice',
        backHref: '/en/privacy/newsletter',
        none: 'No consent-proof record found for this address. Your email is likely not (or no longer) in our mailing list. If you still receive emails from us, contact jitendranitrr13@gmail.com.',
      }
    : {
        h1: 'Vos données',
        intro: "Voici tout ce que nous conservons sur votre inscription. Pour toute question, écrivez à jitendranitrr13@gmail.com.",
        emailLabel: 'E-mail',
        timestampLabel: "Horodatage de l'inscription",
        consentVersion: 'Version du texte de consentement',
        source: 'Source',
        lang: 'Langue',
        brevoNote: "L'adresse elle-même est stockée chez Brevo (Sendinblue SAS — France). Cloudflare ne conserve que cette preuve technique de consentement.",
        h2: 'Tout supprimer',
        deleteHelp: 'Cliquer ci-dessous va (1) supprimer la fiche ci-dessus et (2) retirer votre e-mail de la liste Brevo. Immédiat et irréversible.',
        deleteBtn: 'Supprimer mes données',
        back: 'Retour à la politique de confidentialité',
        backHref: '/privacy/newsletter',
        none: "Aucune preuve de consentement trouvée pour cette adresse. Votre e-mail n'est probablement pas (ou plus) dans notre liste. Si vous recevez encore des e-mails de notre part, contactez jitendranitrr13@gmail.com.",
      };

  let recordBlock: string;
  if (!consentRecord) {
    recordBlock = `<p class="notice">${esc(t.none)}</p>`;
  } else {
    recordBlock = `
      <div class="kv">
        <div class="row"><strong>${esc(t.emailLabel)}</strong><span>${esc(email)}</span></div>
        <div class="row"><strong>${esc(t.timestampLabel)}</strong><span>${esc(consentRecord.ts || '')}</span></div>
        <div class="row"><strong>${esc(t.consentVersion)}</strong><span>${esc(consentRecord.consent_text_version || '')}</span></div>
        <div class="row"><strong>${esc(t.source)}</strong><span>${esc(consentRecord.source_url || '')}</span></div>
        <div class="row"><strong>${esc(t.lang)}</strong><span>${esc(consentRecord.lang || '')}</span></div>
      </div>
      <p class="notice">${esc(t.brevoNote)}</p>
    `;
  }

  return pageShell(lang, `
    <h1>${esc(t.h1)}</h1>
    <p>${esc(t.intro)}</p>
    ${recordBlock}

    <h2>${esc(t.h2)}</h2>
    <p>${esc(t.deleteHelp)}</p>
    <form method="POST" action="/api/dsr/${encodeURIComponent(token)}?e=${encodeURIComponent(email)}&lang=${lang}">
      <input type="hidden" name="_method" value="DELETE">
      <button type="submit" class="danger">${esc(t.deleteBtn)}</button>
    </form>

    <p style="margin-top:1.75rem;"><a class="btn ghost" href="${t.backHref}">${esc(t.back)}</a></p>
  `);
}

function renderDeleted(lang: 'fr' | 'en', brevoOk: boolean, kvOk: boolean): Response {
  const t = lang === 'en'
    ? {
        h1: 'Deletion complete',
        p1: 'The following actions have been performed:',
        brevoOk: 'Brevo mailing list: contact removed.',
        brevoBad: 'Brevo mailing list: removal request sent, but the processor did not confirm. Contact Jitendra if you continue to receive emails.',
        kvOk: 'Consent proof record: deleted.',
        kvBad: 'Consent proof record: no record found (already deleted or never subscribed).',
        back: 'Back to the site',
        backHref: '/en/',
      }
    : {
        h1: 'Suppression effectuée',
        p1: 'Les actions suivantes ont été effectuées :',
        brevoOk: 'Liste Brevo : contact supprimé.',
        brevoBad: "Liste Brevo : demande envoyée, mais le prestataire n'a pas confirmé. Contactez Jitendra si vous continuez à recevoir des e-mails.",
        kvOk: 'Preuve de consentement : supprimée.',
        kvBad: 'Preuve de consentement : aucune fiche trouvée (déjà supprimée ou jamais inscrite).',
        back: 'Retour au site',
        backHref: '/',
      };

  return pageShell(lang, `
    <h1>${esc(t.h1)}</h1>
    <p>${esc(t.p1)}</p>
    <ul>
      <li>${esc(brevoOk ? t.brevoOk : t.brevoBad)}</li>
      <li>${esc(kvOk ? t.kvOk : t.kvBad)}</li>
    </ul>
    <p><a class="btn ghost" href="${t.backHref}">${esc(t.back)}</a></p>
  `);
}

// ---------- handlers ----------

function pickLang(url: URL): 'fr' | 'en' {
  return url.searchParams.get('lang') === 'en' ? 'en' : 'fr';
}

async function ensureVerified(
  params: Record<string, string>,
  url: URL,
  env: Env,
): Promise<{ ok: true; email: string; token: string; emailHash: string } | { ok: false }> {
  if (!env.SUBTLECRYPTO_SIGNING_KEY) return { ok: false };
  const token = params.token;
  const email = (url.searchParams.get('e') || '').trim().toLowerCase();
  if (!token || !email || !EMAIL_RE.test(email)) return { ok: false };

  const verified = await verifyDsrToken(token, env.SUBTLECRYPTO_SIGNING_KEY);
  if (!verified) return { ok: false };

  // Bind the token to the exact email in the querystring.
  const eh = await sha256Hex(email);
  if (eh !== verified.emailHash) return { ok: false };

  return { ok: true, email, token, emailHash: eh };
}

export const onRequestGet: PagesFunction<Env, 'token'> = async ({ params, request, env }) => {
  const url = new URL(request.url);
  const lang = pickLang(url);

  const v = await ensureVerified(params as Record<string, string>, url, env);
  if (!v.ok) return renderInvalid(lang);

  const consentKey = `newsletter:consent:${v.emailHash}`;
  const raw = env.DASHBOARD_KV ? await env.DASHBOARD_KV.get(consentKey) : null;
  const record = raw ? safeParse(raw) : null;

  return renderView(lang, v.email, v.token, record);
};

async function handleDelete(
  params: Record<string, string>,
  request: Request,
  env: Env,
): Promise<Response> {
  const url = new URL(request.url);
  const lang = pickLang(url);

  const v = await ensureVerified(params, url, env);
  if (!v.ok) return renderInvalid(lang);

  const consentKey = `newsletter:consent:${v.emailHash}`;

  // 1) KV delete
  let kvOk = false;
  if (env.DASHBOARD_KV) {
    try {
      const existed = await env.DASHBOARD_KV.get(consentKey);
      await env.DASHBOARD_KV.delete(consentKey);
      kvOk = !!existed;
    } catch (e) {
      console.error('dsr/[token] DELETE: KV delete failed', e);
    }
  }

  // 2) Brevo contact delete
  let brevoOk = false;
  if (env.BREVO_API_KEY) {
    try {
      const res = await fetch(
        `${BREVO_CONTACTS_ENDPOINT}/${encodeURIComponent(v.email)}`,
        {
          method: 'DELETE',
          headers: {
            'accept': 'application/json',
            'api-key': env.BREVO_API_KEY,
          },
        },
      );
      // 204 = deleted; 404 = never existed (also fine); anything else = fail
      brevoOk = res.status === 204 || res.status === 404;
      if (!brevoOk) {
        const t = await res.text().catch(() => '');
        console.error('dsr/[token] DELETE: Brevo non-2xx', res.status, t.slice(0, 400));
      }
    } catch (e) {
      console.error('dsr/[token] DELETE: Brevo fetch threw', e);
    }
  }

  return renderDeleted(lang, brevoOk, kvOk);
}

export const onRequestDelete: PagesFunction<Env, 'token'> = async ({ params, request, env }) =>
  handleDelete(params as Record<string, string>, request, env);

// POST with hidden `_method=DELETE` (used by the HTML form, since browsers
// only issue GET/POST from forms).
export const onRequestPost: PagesFunction<Env, 'token'> = async ({ params, request, env }) => {
  let form: FormData;
  try { form = await request.formData(); }
  catch { return renderInvalid(pickLang(new URL(request.url))); }
  if (String(form.get('_method') || '').toUpperCase() !== 'DELETE') {
    return new Response('Method Not Allowed', { status: 405 });
  }
  return handleDelete(params as Record<string, string>, request, env);
};

function safeParse(raw: string): any | null {
  try { return JSON.parse(raw); }
  catch { return null; }
}
