// Basic Auth middleware for /dashboard/* and /api/*.
// V0.01+ stopgap for Cloudflare Access (which requires broader token scopes
// than we granted). Same effect (dashboard is private, URL is not leakable),
// with no CF Zero Trust configuration. Replaceable with CF Access later
// without breaking the URL — the CF Access product intercepts before this
// middleware runs.
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
]);

function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) {
    diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return diff === 0;
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
        return context.next();
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
