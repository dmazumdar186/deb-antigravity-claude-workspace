# Phase 4a — Per-App Cloudflare Worker (scaffold from scratch)

## Goal

Stand up a brand-new Cloudflare Worker dedicated to this app, with a `/api/health` endpoint and a webhook receiver guarded by idempotency keys (KV, 60-day TTL). Scaffolded from `wrangler init`, **never** cloned from any existing Worker in this workspace. The Worker becomes the app's API base URL for Phase 2's axios client.

## Inputs

- App slug (kebab-case, from registry)
- `wrangler` CLI installed + `wrangler whoami` shows the correct (non-AM) account — verified by preflight
- Cloudflare account ID (read from `CLOUDFLARE_ACCOUNT_ID` env var or `wrangler whoami` output)
- Per-app repo at `C:\Users\deban\dev\mobile-apps\<slug>\`

## Tools/Scripts

- `wrangler init <name> --yes --type javascript` — non-interactive scaffold
- `wrangler kv:namespace create <name>` — provisions KV
- `wrangler deploy` — pushes the Worker
- The app's repo gets a sibling `api/` directory: `C:\Users\deban\dev\mobile-apps\<slug>\api\` (Worker source)

## Hard rules (read before doing anything)

1. **`--yes` is mandatory.** Plain `wrangler init` is interactive (asks about TS, git, deploy). Sub-agents hang on stdin. The correct invocation is:
   ```
   wrangler init <slug>-api --yes --type javascript
   ```
2. **Wrangler v4+ may ignore `--type javascript`** and default to TypeScript. Check `wrangler --version` first.
   - v3.x: `--type javascript` works.
   - v4.x+: flag may be silently dropped → falls back to TS scaffold. If TS scaffold is unacceptable, use the template-based approach: `npm create cloudflare@latest -- <slug>-api --type=hello-world --framework=none --ts=false --git=true --deploy=false --yes`.
3. **FORBIDDEN: do NOT read, copy, edit, or model after `execution/infrastructure/api-proxy/`.** That Worker is locked under Accessory Masters per `CLAUDE.local.md`. The 3-layer pattern (KV idempotency, `/api/health`, secret guards) is reference architecture only — re-derive every line from scratch for this Worker.

## Steps

1. **Version check.** `wrangler --version`. If < 3.0, advise the user to upgrade. If ≥ 4.0, plan for the TS fallback.
2. **Scaffold.**
   ```
   cd C:\Users\deban\dev\mobile-apps\<slug>
   wrangler init <slug>-api --yes --type javascript
   ```
   Creates `<slug>-api/` with `src/index.js`, `wrangler.toml`, `package.json`.
3. **Customize `wrangler.toml`:**
   - `name = "<slug>-api"`
   - `account_id` — from `CLOUDFLARE_ACCOUNT_ID` env var (do NOT hardcode)
   - `compatibility_date` — today's date
   - Remove any `--type javascript` defaults that point at TS files if Wrangler v4 emitted them
4. **Create KV namespace.**
   ```
   wrangler kv:namespace create <slug>-state
   wrangler kv:namespace create <slug>-state --preview
   ```
   Copy the printed IDs into `wrangler.toml` under `[[kv_namespaces]]` (production + preview).
5. **Implement `/api/health`.** In `src/index.js`:
   ```js
   if (url.pathname === '/api/health') {
     return Response.json({
       status: 'ok',
       version: env.BUILD_SHA ?? 'unknown',
       kv_check: await env.STATE.get('healthcheck-ping').then(() => true).catch(() => false),
       timestamp: new Date().toISOString(),
     });
   }
   ```
   Per the canary directive: include `secrets_present` (boolean per required key, never values), `upstream_credit_balances` (cached in KV with 1-5 min TTL — no live paid calls inside health), `last_success_per_job` (read from KV), `build_sha` (`BUILD_SHA` env var injected at deploy).
6. **Webhook receiver + idempotency.** For `POST /api/webhook/<event>`:
   - Read `X-Idempotency-Key` header. If missing, 400.
   - Check KV: `await env.STATE.get('idem:' + key)`. If present, return cached response (idempotent replay).
   - Process the webhook. On success, write `env.STATE.put('idem:' + key, JSON.stringify(response), { expirationTtl: 60 * 60 * 24 * 60 })` (60 days).
   - Auth: every webhook checks `X-Worker-Secret` header against `env.WORKER_SECRET`. Reject 401 on mismatch.
7. **Set secrets.** `wrangler secret put WORKER_SECRET` — paste a generated 32-char random string (the user generates it, you never echo it). Add the same secret to the app's `.env` so Phase 2's axios client can attach it.
8. **Deploy.** `wrangler deploy`. Capture the public URL (e.g. `https://<slug>-api.<account>.workers.dev`). Write it to the app's `.env` as `EXPO_PUBLIC_API_BASE_URL`.
9. **Smoke test.**
   - `curl https://<slug>-api.<account>.workers.dev/api/health` → 200 with JSON shape.
   - `curl -X POST .../api/webhook/test -H "X-Idempotency-Key: abc" -H "X-Worker-Secret: <secret>" -d '{}'` → 200. Repeat the same call → 200 with identical response (replay).
10. **Update registry.** Append `health_url` and `worker_url` to the app's `registry.json` entry.
11. **Commit.** Two repos: app repo (`.env.example` updated, `EXPO_PUBLIC_API_BASE_URL` in dev) and Worker subdirectory (`wrangler.toml`, `src/index.js`).

## Outputs

- `<slug>-api/` directory with deployed Worker
- KV namespace `<slug>-state` with production + preview IDs in `wrangler.toml`
- Public URLs: `/api/health`, `/api/webhook/<event>`
- `WORKER_SECRET` in both Worker secrets and app `.env`
- Registry updated with `health_url` and `worker_url`

## Edge Cases

- **`wrangler init` exits with "directory not empty".** The app repo already has files. Run from the app repo root; `wrangler init` creates a subdirectory.
- **KV namespace already exists.** `wrangler kv:namespace create` errors. Either reuse (read the ID via `wrangler kv:namespace list`) or pick a new name (`<slug>-state-v2`).
- **Wrangler v4 strips `--type javascript`.** Detected at step 1. Fallback path uses `npm create cloudflare@latest` with explicit `--ts=false`.
- **`account_id` missing.** Worker deploys to wrong account or hangs. Always set in `wrangler.toml`, never rely on default.
- **Idempotency-key collision.** Two webhook events with the same key are treated as replays. Use a UUID or `<source>:<event-id>` to scope. Document the key shape in the Worker's README.
- **KV write inside the response handler.** Workers run with a 30s wall-clock limit; KV writes are async but should complete well under that. If a webhook does heavy processing, write the response to KV first, then process via `event.waitUntil(...)` so the client sees a fast 202.
- **`WORKER_SECRET` rotation.** Rotating requires updating both the Worker secret (`wrangler secret put`) and every client (`EXPO_PUBLIC_*` requires a new app build). Plan rotations in maintenance windows.
- **Forbidden: api-proxy/ peek.** If a sub-agent reads `execution/infrastructure/api-proxy/` for "reference", stop the sub-agent and reassign. AM-locked per `CLAUDE.local.md`.

## Notes

- The Worker is the source of truth for the app's API. Phase 4b's Modal cron writes status back into this Worker's KV via the webhook.
- The `/api/health` shape must match the canary directive (`directives/mobile_apps/canary.md`) so `mobile_app_canary.py` can assert against it.
- Anneal adversarial mode runs after this phase via the `/mobile-app` skill (positional base-ref SHA, NOT `--diff-file`).
