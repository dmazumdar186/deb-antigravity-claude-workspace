// Google OAuth 2.0 refresh-token → access-token helper.
//
// Used by sources/gsc.js and sources/gbp.js. Exchanges a long-lived refresh
// token (obtained once via scripts/get_google_refresh_token.py) for a
// short-lived access token, then caches it in KV for its lifetime minus
// a 5-minute safety margin. Subsequent calls in the same day reuse the
// cached access token — one refresh call per day per scope, at most.
//
// Refresh tokens for OAuth apps in "Testing" publishing status expire
// after 7 days per Google policy. When refresh fails with invalid_grant,
// the caller sees a clear error naming the scope; the source's throw
// then bubbles up as `sources_degraded` in the rollup with actionable
// copy in the frontend telling the operator to re-run the local script.
//
// See plan §7.2a for the operator-approved weekly-re-auth strategy.

const TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token";
const CACHE_KEY_PREFIX = "oauth:access:";
const SAFETY_MARGIN_MS = 5 * 60 * 1000; // refresh 5 min before real expiry

/**
 * Exchange a refresh token for an access token. Caches the access token in
 * DASHBOARD_KV with `expirationTtl = expires_in - 5min` so subsequent calls
 * within the same day are free.
 *
 * @param {Env} env      Worker env (must have GOOGLE_CLIENT_ID + _SECRET + refresh token key)
 * @param {string} scope Short scope key: "gsc" or "gbp" (used to name the cache key + refresh-token env var)
 * @returns {Promise<string>} A valid access token, ready for Authorization: Bearer
 */
export async function getAccessToken(env, scope) {
  if (!["gsc", "gbp"].includes(scope)) {
    throw new Error(`getAccessToken: unknown scope "${scope}"`);
  }

  const cacheKey = `${CACHE_KEY_PREFIX}${scope}`;
  const cached = await env.DASHBOARD_KV.get(cacheKey, { type: "json" });
  if (cached && cached.access_token && cached.expires_at) {
    const now = Date.now();
    if (now < cached.expires_at - SAFETY_MARGIN_MS) {
      return cached.access_token;
    }
  }

  const refreshTokenEnvVar = scope === "gsc" ? "GOOGLE_REFRESH_TOKEN_GSC" : "GOOGLE_REFRESH_TOKEN_GBP";
  const refreshToken = env[refreshTokenEnvVar];
  const clientId = env.GOOGLE_CLIENT_ID;
  const clientSecret = env.GOOGLE_CLIENT_SECRET;

  if (!refreshToken) {
    throw new Error(`${refreshTokenEnvVar} not set — run scripts/get_google_refresh_token.py`);
  }
  if (!clientId || !clientSecret) {
    throw new Error("GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET not set");
  }

  const body = new URLSearchParams({
    client_id: clientId,
    client_secret: clientSecret,
    refresh_token: refreshToken,
    grant_type: "refresh_token",
  });

  const resp = await fetch(TOKEN_ENDPOINT, {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded" },
    body,
  });

  if (!resp.ok) {
    const text = await resp.text();
    // Google returns `invalid_grant` when the refresh token has expired
    // (Testing-status apps: after 7 days). Surface a specific message so
    // the aggregator's degraded reason is actionable, not just "401".
    const isExpiry = text.includes("invalid_grant");
    const hint = isExpiry
      ? " — refresh token expired (Testing-status app 7-day limit). Run scripts/get_google_refresh_token.py."
      : "";
    // Do NOT include response body in the thrown error message (may contain
    // partial secret fragments). Log length + status only, then throw a
    // sanitized message.
    console.error(`oauth ${scope} refresh failed: status=${resp.status} body_len=${text.length}${hint}`);
    throw new Error(`oauth ${scope} refresh failed: ${resp.status}${hint}`);
  }

  const payload = await resp.json();
  const expiresInSec = payload.expires_in || 3600;
  const expiresAt = Date.now() + expiresInSec * 1000;

  const cacheValue = {
    access_token: payload.access_token,
    expires_at: expiresAt,
    scope,
  };
  const ttlSec = Math.max(60, expiresInSec - Math.floor(SAFETY_MARGIN_MS / 1000));
  await env.DASHBOARD_KV.put(cacheKey, JSON.stringify(cacheValue), { expirationTtl: ttlSec });

  return payload.access_token;
}

/**
 * Returns the age of the newest refresh token in KV cache. Used by
 * /health to surface "Google source last refreshed N days ago" so the
 * dashboard's re-auth reminder can nudge before the 7-day expiry hits.
 *
 * Note: this reports the access-token cache age, not the refresh-token
 * age. Refresh-token age is not observable from the Worker — it must be
 * inferred from the timestamp when the operator ran the local script.
 * A tighter version would have the local script also `wrangler secret put`
 * an ISO timestamp; deferred to V0.5.
 */
export async function accessTokenAgeSeconds(env, scope) {
  const cached = await env.DASHBOARD_KV.get(`${CACHE_KEY_PREFIX}${scope}`, { type: "json" });
  if (!cached || !cached.expires_at) return null;
  const issuedApproxMs = cached.expires_at - 3600 * 1000; // access tokens last 1h
  return Math.floor((Date.now() - issuedApproxMs) / 1000);
}
