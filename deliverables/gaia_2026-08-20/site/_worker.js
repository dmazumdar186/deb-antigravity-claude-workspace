/*
 * Every request to this site passes through here first.
 *
 * The page names thirteen identifiable people, their employers, their work
 * addresses and an assessment of how likely each is to leave. robots.txt and
 * the noindex headers keep it out of search results; they do nothing about a
 * forwarded link. Cloudflare Access is the better lock, but enabling Zero
 * Trust is a dashboard action that also fixes a permanent team domain, so this
 * is the lock that can exist without making that decision for anyone.
 *
 * This is _worker.js rather than functions/_middleware.js deliberately.
 * `wrangler pages deploy <dir>` resolves functions/ against the working
 * directory, not against <dir> -- so a middleware sitting inside the asset
 * folder is uploaded as a static file and never runs, and the site serves
 * unprotected while every local check passes. _worker.js lives in the asset
 * directory itself and ships with it.
 *
 * The password lives in the SITE_PASSWORD environment secret, never in the
 * repository. If it is unset the site fails CLOSED.
 */

function constantTimeEqual(a, b) {
  // Comparing with === leaks the length of the shared prefix through timing.
  const encoder = new TextEncoder();
  const x = encoder.encode(a);
  const y = encoder.encode(b);
  let diff = x.length ^ y.length;
  const n = Math.max(x.length, y.length);
  for (let i = 0; i < n; i++) {
    diff |= (x[i] || 0) ^ (y[i] || 0);
  }
  return diff === 0;
}

function challenge(body) {
  return new Response(body, {
    status: 401,
    headers: {
      "WWW-Authenticate": 'Basic realm="Gaia Talent shortlist", charset="UTF-8"',
      "Content-Type": "text/plain; charset=utf-8",
      "Cache-Control": "no-store",
      "X-Robots-Tag": "noindex, nofollow, noarchive, nosnippet",
    },
  });
}

export default {
  async fetch(request, env) {
    const expected = env.SITE_PASSWORD;
    if (!expected) {
      // Fail closed. A missing secret is a misconfiguration, not permission.
      return new Response("This site is not configured for access.", {
        status: 503,
        headers: { "Cache-Control": "no-store" },
      });
    }

    const header = request.headers.get("Authorization") || "";
    if (header.startsWith("Basic ")) {
      let decoded = "";
      try {
        decoded = atob(header.slice(6));
      } catch (err) {
        return challenge("Malformed credentials.");
      }
      const i = decoded.indexOf(":");
      const supplied = i < 0 ? "" : decoded.slice(i + 1);
      if (constantTimeEqual(supplied, expected)) {
        const asset = await env.ASSETS.fetch(request);
        const out = new Response(asset.body, asset);
        // Never let a shared cache hold an authenticated response.
        out.headers.set("Cache-Control", "private, no-store");
        out.headers.set("X-Robots-Tag",
                        "noindex, nofollow, noarchive, nosnippet");
        return out;
      }
    }
    return challenge("This shortlist is private. A password is required.");
  },
};
