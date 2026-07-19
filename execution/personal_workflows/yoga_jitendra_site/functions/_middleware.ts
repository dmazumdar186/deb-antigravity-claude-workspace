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
