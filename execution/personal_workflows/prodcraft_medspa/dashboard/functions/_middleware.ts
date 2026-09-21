// HTTP Basic Auth on every path (dashboard is 100% private — no public
// endpoints, unlike the yoga_jitendra_site house pattern this mirrors).
// Constant-time compare on both user and pass. 401 + WWW-Authenticate when
// missing or wrong. Every response also carries X-Robots-Tag: noindex and
// Cache-Control: no-store so nothing here is cached or indexed.
//
// Required env vars set on the Pages project (see wrangler.toml comments):
//   DASHBOARD_USER — plain text
//   DASHBOARD_PASS — secret, no default (503 if missing — never fail open)

export interface Env {
  DASHBOARD_USER?: string;
  DASHBOARD_PASS?: string;
  SUPABASE_URL?: string;
  SUPABASE_SERVICE_KEY?: string;
}

function timingSafeEqual(a: string, b: string): boolean {
  // Compare over a fixed-length buffer so string length itself doesn't leak
  // via early-return timing; pad the shorter side before diffing.
  const len = Math.max(a.length, b.length);
  let diff = a.length === b.length ? 0 : 1;
  for (let i = 0; i < len; i++) {
    const ca = i < a.length ? a.charCodeAt(i) : 0;
    const cb = i < b.length ? b.charCodeAt(i) : 0;
    diff |= ca ^ cb;
  }
  return diff === 0;
}

function withSecurityHeaders(res: Response): Response {
  const headers = new Headers(res.headers);
  headers.set('X-Robots-Tag', 'noindex');
  headers.set('Cache-Control', 'no-store');
  return new Response(res.body, { status: res.status, statusText: res.statusText, headers });
}

function unauthorized(): Response {
  return withSecurityHeaders(
    new Response('Authentication required.', {
      status: 401,
      headers: {
        'WWW-Authenticate': 'Basic realm="ProdCraft Med Spa Dashboard", charset="UTF-8"',
      },
    }),
  );
}

export const onRequest: PagesFunction<Env> = async (context) => {
  const expectedUser = context.env.DASHBOARD_USER || '';
  const expectedPass = context.env.DASHBOARD_PASS;

  if (!expectedPass) {
    return withSecurityHeaders(
      new Response('Dashboard auth is not configured (DASHBOARD_PASS is missing on the Pages project).', {
        status: 503,
      }),
    );
  }

  const auth = context.request.headers.get('Authorization');
  if (!auth || !auth.startsWith('Basic ')) {
    return unauthorized();
  }

  let decoded: string;
  try {
    decoded = atob(auth.slice(6));
  } catch {
    return unauthorized();
  }

  const idx = decoded.indexOf(':');
  if (idx < 0) {
    return unauthorized();
  }
  const user = decoded.slice(0, idx);
  const pass = decoded.slice(idx + 1);

  const userOk = timingSafeEqual(user, expectedUser);
  const passOk = timingSafeEqual(pass, expectedPass);
  if (!userOk || !passOk) {
    return unauthorized();
  }

  const res = await context.next();
  return withSecurityHeaders(res);
};
