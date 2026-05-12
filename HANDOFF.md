# Accessory Masters — Handoff to Bryce

Last updated: 2026-05-13 by Debanjan / Claude. Everything below is verified live via curl as of this commit.

---

## What's running where

| Surface | URL | Hosted on | Notes |
|---|---|---|---|
| **Marketing site** | https://accessory-masters-site.pages.dev/ | Cloudflare Pages (project `accessory-masters-site`) | Title is "Elite Broker Group". Will move to `elitebrokergroup.com` once DNS is pointed (see below). |
| **Marketing site (Vercel mirror, stale)** | https://website-flame-phi-90.vercel.app/ | Vercel | Older deploy showing "Keelson & Rowe". Unused after the Pages cutover. Can be ignored or deleted. |
| **Dashboard** | https://website-dashboard-self.vercel.app/ | Vercel (project `website-dashboard`, team `aleksandars-projects-3d89ded0`) | Has the 7-day metrics, 🔥 hot leads card, recent activity, pipeline banner, dry-run button. Paste `WORKER_SECRET` into the top input to unlock the auth-protected sections. |
| **Worker (API + cron)** | https://accessory-masters-api.accessory-masters.workers.dev/ | Cloudflare Workers (`accessory-masters-api`) | All routes return 401 without auth. Cron: every-30-min reply poll, daily 6am UTC lead pipeline, Monday 7am UTC weekly report. |
| **KV store** | binding `REPLY_STATE`, id `e38c04f316594621bacb3b0c3d7fd444` | Cloudflare KV | Reply records, pipeline runs, seen-business dedup, auto_replied gate, pending_followup, exclusions. |
| **Source code** | https://github.com/dmazumdar186/deb-antigravity-claude-workspace | GitHub | Everything committed. `.env` is gitignored. |

---

## Worker endpoints (all require `X-Worker-Secret` header except where noted)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/api/form-submit` | none | Public contact form → GHL |
| GET | `/api/dashboard?range=7d\|30d\|all` | WORKER_SECRET | Email + CRM metrics |
| GET | `/api/dashboard-extras?range=7d` | WORKER_SECRET | Hot leads + recent activity + pipeline banner |
| POST | `/api/webhook/reply` | INSTANTLY_WEBHOOK_SECRET (`X-Webhook-Secret`) | Instantly fires this on every reply |
| POST | `/api/webhook/telegram` | TELEGRAM_WEBHOOK_SECRET (`X-Telegram-Bot-Api-Secret-Token`) | Telegram bot incoming updates. Currently dormant — see Outstanding. |
| GET | `/api/exclusions` | WORKER_SECRET | List manual exclusion list |
| POST | `/api/exclusions` | WORKER_SECRET | Add `{ domain, business_name?, reason? }` |
| DELETE | `/api/exclusions?key=excluded_(domain\|name)_<value>` | WORKER_SECRET | Remove an entry |
| POST | `/api/run-pipeline?dry_run=true` | WORKER_SECRET | Trigger pipeline manually; `dry_run=true` uses mocks, no API credits |
| POST | `/api/process-replies` | WORKER_SECRET | Trigger reply poll manually |
| GET | `/api/variants?campaign_id=...` | WORKER_SECRET | Inspect Instantly variants |
| GET | `/api/pipeline-status` | WORKER_SECRET | Recent pipeline runs from KV |

---

## Cloudflare Worker secrets (set; values NOT in this repo)

All set via `cd execution/infrastructure/api-proxy && npx wrangler secret put NAME`:

- `WORKER_SECRET` — admin auth header for the dashboard + manual triggers
- `INSTANTLY_WEBHOOK_SECRET` — Instantly → Worker webhook auth
- `INSTANTLY_API_KEY` — Instantly v2 API
- `GHL_API_KEY` — GoHighLevel v2 API (Private Integration Token)
- `OPENROUTER_API_KEY` — reply classification + opener generation
- `SERPER_API_KEY` — Google Maps + Places lead sourcing
- `ANYMAILFINDER_API_KEY` — email finding
- `MILLION_VERIFIER_API_KEY` — email verification

Verify with: `npx wrangler secret list` (run from `execution/infrastructure/api-proxy/`).

---

## What's still outstanding

### 1. Telegram bot (Bryce specifically asked for this for testing)

Worker code is fully in place. Two-channel routing, `/status` command handler, idempotency. The setup helper script lives at `execution/infrastructure/setup_telegram_webhook.py`.

**To activate:**
1. On Telegram, message `@BotFather` → `/newbot` → name + username → copy the bot token.
2. Open the bot's chat (`t.me/<your_bot_name>`) → send any message (e.g. `hi`) — needed so chat ID is discoverable.
3. Set the secrets on Cloudflare:
   ```bash
   cd execution/infrastructure/api-proxy
   echo -n "<bot_token>" | npx wrangler secret put TELEGRAM_BOT_TOKEN
   echo -n "<chat_id>"   | npx wrangler secret put TELEGRAM_CHAT_ID
   # Optional, for two-channel routing:
   echo -n "<hot_chat_id>"  | npx wrangler secret put TELEGRAM_CHAT_ID_HIGH_PRIORITY
   echo -n "<reg_chat_id>"  | npx wrangler secret put TELEGRAM_CHAT_ID_REGULAR
   # Optional, comma-separated user IDs allowed to use /status:
   echo -n "<user_id_a>,<user_id_b>" | npx wrangler secret put TELEGRAM_AUTHORIZED_USERS
   ```
4. Register the webhook + generate the shared secret:
   ```bash
   py execution/infrastructure/setup_telegram_webhook.py
   ```
   This generates `TELEGRAM_WEBHOOK_SECRET`, pushes it to Cloudflare, and calls Telegram's `setWebhook`.
5. From your phone, message the bot `/status` — expect a 7-day summary in 2-5 seconds.

Chat ID lookup if you need it: message `@userinfobot` on Telegram (your own user ID == chat ID for private DMs with the bot).

### 2. `elitebrokergroup.com` DNS (Namecheap-side, ~3 minutes)

The domain is registered (Namecheap, currently showing a parking redirect). The Cloudflare Pages side is already configured — both `elitebrokergroup.com` (apex) and `www.elitebrokergroup.com` are added as custom domains on the `accessory-masters-site` project (Cloudflare will auto-issue SSL once DNS resolves).

**To activate in Namecheap:**
1. Log into Namecheap → Domain List → click **Manage** on `elitebrokergroup.com` → **Advanced DNS** tab.
2. Delete any existing A / CNAME / URL Redirect records at `@` and `www` (the "Redirecting..." parking).
3. Add two records:

| Type | Host | Value | TTL |
|---|---|---|---|
| CNAME | `@` | `accessory-masters-site.pages.dev` | Automatic |
| CNAME | `www` | `accessory-masters-site.pages.dev` | Automatic |

4. Save. Within 5-30 min DNS propagates, Cloudflare validates via HTTP-01, SSL certs issue, site is live at `https://elitebrokergroup.com/`.

After it's live, update `og:url` + `og:image` in `website/index.html` and `website/signup.html` from `accessory-masters-site.pages.dev` → `elitebrokergroup.com` for clean link previews. Then `wrangler pages deploy website --project-name=accessory-masters-site --branch=main`.

### 3. Optional: `dashboard.elitebrokergroup.com` subdomain for Vercel

Currently the dashboard is at `website-dashboard-self.vercel.app`. To put it on a branded subdomain:
- In Vercel: Project `website-dashboard` → Settings → Domains → Add `dashboard.elitebrokergroup.com` → Vercel will show the CNAME target.
- In Namecheap: add `CNAME dashboard → cname.vercel-dns.com`.
- Update Worker `ALLOWED_ORIGINS` in `execution/infrastructure/api-proxy/wrangler.toml` to add `https://dashboard.elitebrokergroup.com`, then redeploy.

### 4. Optional: Vercel deployment protection on the dashboard

Right now `website-dashboard-self.vercel.app` is publicly reachable (data is still protected by `WORKER_SECRET` though). To gate the page itself behind Vercel SSO:
- Vercel project → Settings → Deployment Protection → enable for Production. One toggle.

---

## Common operations

### Deploy Worker (after code changes in `execution/infrastructure/api-proxy/src/index.js`)
```bash
cd execution/infrastructure/api-proxy
npx wrangler deploy
```
Note the printed `Current Version ID`.

### Deploy marketing site (after edits in `website/`)
```bash
cd "<repo root>"
npx wrangler pages deploy website --project-name=accessory-masters-site --branch=main
```

### Deploy dashboard (after edits in `website-dashboard/`)
```bash
cd website-dashboard
npx vercel deploy --prod --yes --scope aleksandars-projects-3d89ded0 --token=$VERCEL_TOKEN
```
The `VERCEL_TOKEN` lives in `.env` (gitignored).

### Trigger a dry-run pipeline (no API credits used)
```bash
curl -X POST -H "X-Worker-Secret: <secret>" \
  "https://accessory-masters-api.accessory-masters.workers.dev/api/run-pipeline?dry_run=true"
```

### Add a business to the exclusion list
```bash
curl -X POST -H "X-Worker-Secret: <secret>" -H "Content-Type: application/json" \
  -d '{"domain":"junkcompany.com","reason":"already approached in 2024"}' \
  "https://accessory-masters-api.accessory-masters.workers.dev/api/exclusions"
```

---

## Local `.env` (gitignored — never committed)

The following keys live in `.env` on the local machine. Bryce can either request them from Debanjan or regenerate from each provider:

- `ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY`
- `INSTANTLY_API_KEY`, `ANYMAILFINDER_API_KEY`, `MILLION_VERIFIER_API_KEY`, `SERPER_API_KEY`, `PROSPEO_API_KEY`
- `GHL_API_KEY`
- `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID` (account id: `26e5b8612be35e5d23a9186fcf5288d0`)
- `VERCEL_TOKEN` (scoped to team `aleksandars-projects-3d89ded0`)
- `GITHUB_PAT`
- `APIFY_API_TOKEN`, `FIRECRAWL_API_KEY`, `TAVILY_API_KEY`
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` — currently empty placeholders; populate when bot is created

---

## Feature timeline (newest first)

| Date | Commit | Feature |
|---|---|---|
| 2026-05-13 | `7c373cf` | Re-track `website-dashboard/` in git (after a brief untrack misread) |
| 2026-05-12 | `9417040` | Deploy `website-dashboard/` to Vercel project `website-dashboard` |
| 2026-05-12 | `ea2b6af` | Day-2 follow-up + one-and-done auto-reply gate + manual exclusion list |
| 2026-05-12 | `2fed194` | Relocate dashboard from `website/dashboard.html` to standalone `website-dashboard/` |
| 2026-05-12 | `10cfdb3` | Worker parity with Bryce's auto-reply work (11 objections, voice ref, CTA variants) + Serper Places + Telegram two-channel routing + Elite Broker Group rebrand |
| earlier | `7966e82` | Dashboard `dashboard-extras` endpoint + cross-run dedup (60-day TTL) + dry-run pipeline |

---

## Architecture (1-paragraph mental model)

Three runtime surfaces:
1. **Cloudflare Worker** (`execution/infrastructure/api-proxy/src/index.js`, ~3300 lines) runs all backend logic: cron-driven lead sourcing, reply classification + routing, dashboard data APIs, webhook receivers for Instantly and Telegram. Stateless except for Cloudflare KV (replies, dedup, follow-up scheduling, exclusions).
2. **Cloudflare Pages** serves the marketing site (`website/`) as static HTML/JS. Pages auto-deploys are NOT wired up — deploy via `wrangler pages deploy`.
3. **Vercel** serves the dashboard (`website-dashboard/`) as static HTML/JS. Deploys via `vercel deploy --prod --token=$VERCEL_TOKEN`.

External services: **Instantly.ai** (cold email send + warmup), **GoHighLevel** (CRM + appointments), **OpenRouter** (LLM for classification + opener generation, currently uses `claude-haiku-4.5`), **Serper.dev** (Google Maps + Places sourcing), **AnymailFinder** + **Million Verifier** (email enrichment).

The full PRD lives at `c:/Users/deban/OneDrive/Documents/Bryce Projects/Accessory Masters 27 Apr 26/Accessory_Masters_PRD 12 May 26.md`. Per-feature directives live in `directives/`. Tests live in `tests/` (340 Python tests covering the original Python module pipeline; the Worker is a JS port of that logic — no JS tests yet, that's separate scope).
