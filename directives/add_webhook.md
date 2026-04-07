# Directive: Add Webhook

## Goal
Expose a Claude-callable endpoint that triggers a specific directive when hit via HTTP. Supports two runtimes: Modal (Python, heavy compute) and Cloudflare Workers (edge, lightweight).

## When to Use
When the user says "add a webhook that does X" or needs an HTTP endpoint to trigger an automated workflow.

## Choosing a Runtime

| Use Modal when | Use Cloudflare Workers when |
|---------------|-----------------------------|
| Task needs Python libraries (pandas, requests, etc.) | Task is lightweight JS/TS transformation |
| Task takes >1s to complete | Low-latency response needed (<50ms) |
| Task needs full execution environment | Global edge distribution needed |
| Task involves file I/O or heavy compute | Simple routing or data pass-through |

## Steps: Modal Path

1. **Create the directive** — Write `directives/{category}/{name}.md` describing what the webhook does, its inputs (request body schema), and outputs.

2. **Add to webhooks.json** — Add an entry to `execution/webhooks.json`:
   ```json
   {
     "your-webhook-slug": "directives/{category}/{name}.md"
   }
   ```

3. **Deploy** — Run:
   ```bash
   modal deploy execution/modal_webhook.py
   ```

4. **Test** — Hit the endpoint:
   ```bash
   curl -X POST https://your-modal-app.modal.run/your-webhook-slug \
     -H "Content-Type: application/json" \
     -d '{"key": "value"}'
   ```

## Steps: Cloudflare Workers Path

1. **Create the directive** — Same as Modal step 1.

2. **Create the worker script** — Add `execution/infrastructure/{name}_worker.js` (or `.ts`).

3. **Deploy** — Run from the `execution/infrastructure/` directory:
   ```bash
   wrangler deploy
   ```

4. **Test** — Hit the worker URL provided by `wrangler deploy`.

## Key Files
- `execution/webhooks.json` — Modal webhook registry
- `execution/modal_webhook.py` — Modal app entry point (do not modify unless necessary)
- `execution/infrastructure/` — Cloudflare Worker scripts

## Edge Cases
- Validate all incoming request bodies before processing
- Return structured JSON responses (never raw text)
- Log errors with enough context to debug without exposing secrets
- Always return HTTP 200 with `{"status": "error", "message": "..."}` for handled errors — never 500 in production

## Changelog
| Date | Change |
|------|--------|
| 2026-04-07 | Created |
