# gtm-people-ask Worker (not deployed — concept hook)

1. `cd site/worker && wrangler login`
2. `wrangler secret put ANTHROPIC_API_KEY` (paste the key when prompted; never commit it).
3. `wrangler deploy` → note the URL, e.g. `https://gtm-people-ask.<account>.workers.dev`.
4. In `site/index.html` set `<html lang="en" data-ask-url="https://gtm-people-ask.<account>.workers.dev">`.
5. `js/main.js` then POSTs `{brief, parsed}` on every brief change and merges `{summary, tiles}` over the local answer; on any error the local answer stands.
6. CORS allows `*.pages.dev` and localhost; rate limit is 10 requests / minute / IP per isolate (in-memory token bucket, no KV).
7. Upstream: Anthropic Messages API, model `claude-fable-5-1`, max_tokens 600, 10 s timeout; the system prompt is the KB facts as JSON with "answer only from these facts".
8. Test: `curl -X POST <url> -H 'content-type: application/json' -d '{"brief":"Series A, London, founding AE"}'`.
