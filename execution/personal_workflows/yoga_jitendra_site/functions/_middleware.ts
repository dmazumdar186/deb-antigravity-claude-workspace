// Basic Auth middleware for /dashboard/* and /api/*.
// V0.01+ stopgap for Cloudflare Access (which requires broader token scopes
// than we granted). Same effect (dashboard is private, URL is not leakable),
// with no CF Zero Trust configuration. Replaceable with CF Access later
// without breaking the URL — the CF Access product intercepts before this
// middleware runs.
//
// 2026-08-06 addition — session cookie: browsers do not reliably auto-attach
// cached Basic Auth to fetch()/XHR requests. That caused a double prompt
// (once on /dashboard/, again when clicking the subscribers count and the
// page's XHR hit /api/subscribers). Fix: on successful Basic Auth we
// Set-Cookie yj_dash_sess=<sha256(user:pass:v1)>; subsequent requests are
// authorized via the cookie without any prompt. If DASHBOARD_PASS ever
// rotates, all outstanding cookies invalidate automatically because the
// expected signature changes. 8-hour max-age matches a working day.
//
// Required env vars set on the Pages project:
//   DASHBOARD_USER — plain text, default 'debanjan' if not set
//   DASHBOARD_PASS — secret, no default (401 with a friendly message if missing)

interface Env {
  DASHBOARD_USER?: string;
  DASHBOARD_PASS?: string;
}

const PROTECTED = /^\/(dashboard|api)(\/|$)/;

// Public read-only endpoints under /api/. Whitelisted OUT of the Basic-Auth
// gate so build-time hydration + anonymous site visitors can read them.
// Keep this list tight; every entry is an unauthenticated read surface.
const PUBLIC_API_ALLOWLIST = new Set<string>([
  '/api/reviews-public',
  // 2026-08-05 session 3: newsletter-subscribe MUST be public so real
  // visitors can opt in via the popup on public pages. The endpoint has
  // its own defenses (consent-required, honeypot, rate-limit 5/hr/IP,
  // email-format validation). Without this the popup submits 401 to
  // every visitor and captures zero opt-ins.
  '/api/newsletter-subscribe',
]);

const SESSION_COOKIE_NAME = 'yj_dash_sess';
const SESSION_MAX_AGE_SECONDS = 8 * 60 * 60; // 8 hours

function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) {
    diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return diff === 0;
}

async function sessionSig(user: string, pass: string): Promise<string> {
  const buf = new TextEncoder().encode(`${user}:${pass}:yj-dash-v1`);
  const digest = await crypto.subtle.digest('SHA-256', buf);
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

function readSessionCookie(request: Request): string | null {
  const header = request.headers.get('Cookie') || '';
  const parts = header.split(/;\s*/);
  for (const part of parts) {
    if (part.startsWith(`${SESSION_COOKIE_NAME}=`)) {
      return part.slice(SESSION_COOKIE_NAME.length + 1);
    }
  }
  return null;
}

function sessionCookieHeader(sig: string): string {
  return `${SESSION_COOKIE_NAME}=${sig}; Path=/; Max-Age=${SESSION_MAX_AGE_SECONDS}; HttpOnly; Secure; SameSite=Strict`;
}

// 2026-08-06 — replaces stampSessionCookie (which appended Set-Cookie to
// context.next()'s response). Cloudflare Pages' static-asset handler
// strips Set-Cookie from static-asset responses on the way out, so the
// stamp silently disappeared and every XHR re-prompted. Redirecting from
// a Function-generated response guarantees the cookie is issued — CF
// cannot strip headers on responses we build ourselves. GET/HEAD → 302,
// other methods → 307 (POST/PUT/DELETE preserve method + body on
// follow-up). One extra RTT on first-auth, zero prompts afterward.
function cookieSetRedirect(url: URL, sig: string, method: string): Response {
  const safe = method === 'GET' || method === 'HEAD';
  return new Response(null, {
    status: safe ? 302 : 307,
    headers: {
      'Location': url.pathname + url.search,
      'Set-Cookie': sessionCookieHeader(sig),
      'Cache-Control': 'no-store',
    },
  });
}

export const onRequest: PagesFunction<Env> = async (context) => {
  const url = new URL(context.request.url);

  if (!PROTECTED.test(url.pathname)) {
    return context.next();
  }

  // Public whitelist bypass — must be a read-only endpoint by contract.
  // Normalize the trailing slash so `/api/reviews-public` and
  // `/api/reviews-public/` both bypass auth (CDN prefetch, browser
  // normalization, or a different fetch client may append the slash).
  const normalized = url.pathname.endsWith('/') && url.pathname.length > 1
    ? url.pathname.slice(0, -1)
    : url.pathname;
  if (PUBLIC_API_ALLOWLIST.has(normalized)) {
    return context.next();
  }

  const expectedUser = context.env.DASHBOARD_USER || 'debanjan';
  const expectedPass = context.env.DASHBOARD_PASS;

  if (!expectedPass) {
    return new Response(
      'Dashboard auth is not configured (DASHBOARD_PASS is missing on the Pages project).',
      { status: 503, headers: { 'Cache-Control': 'no-store' } },
    );
  }

  const expectedSig = await sessionSig(expectedUser, expectedPass);

  // Fast path: valid session cookie → allow, no re-prompt, no Set-Cookie
  // (already stamped). Cookie is invalidated automatically when the
  // password rotates because the expected sig changes.
  const existingCookie = readSessionCookie(context.request);
  if (existingCookie && timingSafeEqual(existingCookie, expectedSig)) {
    return context.next();
  }

  // Fall-through: Basic Auth. On success, redirect to the same URL with
  // Set-Cookie header. Browser follows, sends the cookie, cookie
  // fast-path (above) validates, request proceeds. Safe against loops:
  // the cookie fast-path returns BEFORE this branch runs, so a valid
  // cookie always wins and we never re-issue the redirect.
  const auth = context.request.headers.get('Authorization');
  if (auth && auth.startsWith('Basic ')) {
    let decoded: string;
    try {
      decoded = atob(auth.slice(6));
    } catch {
      decoded = '';
    }
    const idx = decoded.indexOf(':');
    if (idx > 0) {
      const user = decoded.slice(0, idx);
      const pass = decoded.slice(idx + 1);
      if (timingSafeEqual(user, expectedUser) && timingSafeEqual(pass, expectedPass)) {
        return cookieSetRedirect(url, expectedSig, context.request.method);
      }
    }
  }

  return new Response('Authentication required.', {
    status: 401,
    headers: {
      'WWW-Authenticate': 'Basic realm="Yoga avec Jitendra Dashboard", charset="UTF-8"',
      'Cache-Control': 'no-store',
    },
  });
};
