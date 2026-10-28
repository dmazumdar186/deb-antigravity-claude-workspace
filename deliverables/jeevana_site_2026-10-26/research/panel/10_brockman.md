# Panel lens 10 — Greg Brockman (execution & reliability)

**Verdict: CONDITIONAL.** The handlers are tidy, but the deploy path probably ships no Functions at all. Nobody can run this unattended for 30 days until a live POST /api/subscribe returns 200.

## Findings
1. **Functions may never deploy.** `wrangler pages deploy <dir>` reads `functions/` and `wrangler.toml` from the *cwd*, not from `<dir>`. `deploy.sh:9` runs from whatever directory the caller is in, so unless that is `site/`, the deploy has no Functions and no KV binding, and every `/api/*` request gets a 405 from static hosting. Fix: `cd "$SITE"` before line 9, then probe the API after deploy.
2. **Source files are public.** With `pages_build_output_dir = "."` (`wrangler.toml:2`), the static upload includes `wrangler.toml` and `functions/api/*.ts`, so the KV id and the handler code are downloadable. Low severity, but move the static files to `site/public/`.
3. **Rate limiter can throw.** In `_lib.ts:38-42`, `KV.get`/`put` and `JSON.parse` run outside any try. A KV hiccup gives an unhandled 500 with no JSON body, and the read-modify-write isn't atomic, so the 5/10-min limit is approximate. TTLs are fine (660 s).
4. **Missing binding returns 500, not 503** (`register.ts:24`, `subscribe.ts:17`, `export.ts:29`). This happens after the rate limiter fails open (`_lib.ts:34`), so the error is silent. Return 503 and log.
5. **No body-size bound.** `request.json()` (`_lib.ts:48`) parses the whole payload before `str()` truncates. Check `Content-Length` first and reject anything over ~16 KB.
6. **Duplicate subscribes overwrite** (`subscribe.ts:23`). It is idempotent per sha256(email), but each repeat resets `ts` and `phone`, so the original consent timestamp is lost. Use get-then-put, or store `first_ts`.
7. **`reg:` keys** (`register.ts:29`) are ms timestamp plus 32 random bits. Collisions are negligible, and the keys sort by time. OK.
8. **No Origin check / CSRF.** Same-origin is enforced only by CSP `connect-src` on our own page, and any site can POST. Honeypot plus rate limit is acceptable for v1.
9. **Method guards are OK.** Only `onRequestPost`/`onRequestGet` are exported, so other methods get 405.
10. **CSP** (`_headers:8`) covers Google Fonts CSS and fonts, the manifest, and `media-src 'self'`. Strict `script-src` is fine because the JSON-LD is a data block. Gap: no `worker-src`, and any inline `style=` would be blocked (none found in index.html).
11. **Caching.** HTML has no Cache-Control (Pages default revalidates, OK). css/js cache for 1 h without fingerprinting, so a deploy can show mixed versions for up to an hour. Add `?v=` hashes or `immutable`.
12. **SEO and error pages are consistent.** Canonical, sitemap and robots all use `jeevana-yoga.pages.dev`, and `404.html` and `_redirects` are fine. These must all change in one commit when the domain is bound.
13. **Export does N+1 reads.** `export.ts:37` makes one KV get per key, which becomes a problem past ~1k rows (subrequest limit). Store values in metadata or paginate.

## 6-line runbook
1. `cd site && export CLOUDFLARE_API_TOKEN=… CLOUDFLARE_ACCOUNT_ID=…`
2. `npx wrangler@4 pages deploy . --project-name jeevana-yoga --branch main`
3. `curl -sX POST $URL/api/subscribe -d '{"email":"t@x.io","consent":true}'` → expect `{"ok":true}`
4. 405/404 means Functions are missing (see #1). 500 `internal` means check the KV binding in the dashboard.
5. Set secrets: `npx wrangler@4 pages secret put EXPORT_USER` (and `EXPORT_PASS`).
6. Roll back: Pages dashboard → Deployments → previous → "Rollback".

## Honest gaps
- I didn't run a live deploy or curl the endpoints, so #1 is inferred from wrangler's documented behaviour, not observed.
- I didn't check whether Pages actually serves `functions/*.ts` as static files.
- I didn't verify that the KV id belongs to this account.
- I didn't read the full directive text.
