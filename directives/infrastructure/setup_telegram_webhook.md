# Setup Telegram Webhook

## Goal
Provision (or rotate) the Telegram bot webhook so incoming user commands (like `/status`) hit the Cloudflare Worker at `POST /api/webhook/telegram`, authenticated via Telegram's `secret_token` field (sent back as the `X-Telegram-Bot-Api-Secret-Token` header). Idempotent — running again rotates the secret and re-registers the webhook.

## When to Use
- First-time Telegram bot setup, after Bryce creates the bot via `@BotFather` and supplies `TELEGRAM_BOT_TOKEN`.
- When rotating the shared secret.
- When the worker URL changes (rare).
- After running, also push `TELEGRAM_CHAT_ID_HIGH_PRIORITY`, `TELEGRAM_CHAT_ID_REGULAR`, and `TELEGRAM_AUTHORIZED_USERS` to Cloudflare as separate `wrangler secret put` calls.

## Inputs

### Environment variables
- `TELEGRAM_BOT_TOKEN` — bot token from `@BotFather` (put in `.env`).
- `TELEGRAM_WEBHOOK_SECRET_OVERRIDE` — optional, force a specific secret instead of generating one.

### CLI arguments
- `--info` — print current Telegram webhook info and exit (no changes).
- `--delete` — delete the Telegram webhook. Does not touch Cloudflare.
- `--dry-run` — print intended actions, don't call Telegram or wrangler.
- `--worker-url URL` — override the default worker URL.
- `--no-cloudflare` — skip the wrangler secret push (only call Telegram).

## Tools / Scripts
- `execution/infrastructure/setup_telegram_webhook.py` — the runner.
- `npx wrangler secret put TELEGRAM_WEBHOOK_SECRET` — invoked by the script.
- Telegram Bot API: `setWebhook`, `getWebhookInfo`, `deleteWebhook`.

## Outputs
- Generates a 32-byte URL-safe shared secret.
- Pushes the secret to Cloudflare as `TELEGRAM_WEBHOOK_SECRET`.
- Calls Telegram `setWebhook` with the worker URL + secret + `allowed_updates: [message, edited_message]`.
- Prints the final webhook info from `getWebhookInfo`.

## Steps
1. Load `.env`. Read `TELEGRAM_BOT_TOKEN`. Fail loudly with instructions if missing.
2. Generate (or reuse via override) a 32-byte URL-safe secret.
3. Push `TELEGRAM_WEBHOOK_SECRET` to Cloudflare via `npx wrangler secret put` (unless `--no-cloudflare`).
4. Call Telegram `setWebhook` with `url`, `secret_token`, `allowed_updates`, `drop_pending_updates: true`.
5. Call `getWebhookInfo` and print the result so the operator can verify.
6. Print next-step reminders (set `TELEGRAM_CHAT_ID_*` and `TELEGRAM_AUTHORIZED_USERS`).

## Edge Cases
- **Missing `TELEGRAM_BOT_TOKEN`** — script exits with a pointer to `@BotFather`.
- **Bot token revoked** — Telegram `setWebhook` returns a `401` error; the script raises and prints the error body. Re-issue via `@BotFather`, update `.env`, re-run.
- **Cloudflare wrangler not installed** — `npx` will fetch it on first run. If the network blocks npx, fall back to `--no-cloudflare` and run `wrangler secret put TELEGRAM_WEBHOOK_SECRET` manually with the printed secret.
- **Webhook URL not HTTPS** — Telegram requires HTTPS. The default worker URL is HTTPS.
- **Telegram only delivers `allowed_updates`** — we register `message` and `edited_message`. Inline queries, polls, callback queries are ignored. Expand the list if those are added later.
- **Secret rotation** — running the script again rotates the secret. The old secret stops working immediately; any in-flight Telegram retries fail. Telegram does its own retry queue, so this is generally safe but expect a brief gap.
- **`getWebhookInfo` shows non-zero `pending_update_count`** — Telegram is queueing updates. Either the worker is failing or the secret is mismatched. Check Cloudflare logs.

## Exit Criteria

- `py execution/infrastructure/setup_telegram_webhook.py --info` exits `0` and prints the current webhook URL, pending update count, and last error code — no `TELEGRAM_BOT_TOKEN` error.
- `getWebhookInfo` response shows `pending_update_count == 0` within 60 seconds of provisioning (Telegram is delivering updates to the worker successfully).
- `npx wrangler secret list` from the worker directory lists `TELEGRAM_WEBHOOK_SECRET` as a present secret.
- Sending `/status` to the bot from Telegram results in a reply from the Worker within 10 seconds.
- Re-running the provisioning script on an already-configured webhook completes without error and leaves exactly one webhook registered (idempotency confirmed by `--info` output).

## Verification
```bash
# Inspect current state
py execution/infrastructure/setup_telegram_webhook.py --info

# Set up the webhook + push secret to Cloudflare
py execution/infrastructure/setup_telegram_webhook.py

# Smoke test: from Telegram, message the bot /status — should reply within 2 seconds
```
