# Instantly Reply Notifier

Get a **Telegram message on your phone the moment a lead replies** to an Instantly.ai cold email campaign, but only for the replies that are actually worth your attention. Out-of-office bounces and "remove me" replies are dropped silently.

It runs as a **Cloudflare Worker**, so it lives on Cloudflare's edge 24/7. No server, no laptop that has to stay awake, no n8n instance. Free tier covers this comfortably.

Built because Instantly's own mobile notifications are unreliable.

---

## What it does

```
Instantly (reply_received webhook)
   -> Cloudflare Worker
        -> KV dedup (120s, absorbs Instantly's retries)
        -> Classify the reply:
             Layer 1: regex rules (free)      -> ooo / not_interested / booking_ready
             Layer 2: GPT-4o-mini via OpenRouter (~$0.001) -> positive / negative / neutral
        -> Telegram sendMessage, for the categories a human needs to see
```

**You get pinged for:** `booking_ready`, `positive`, `neutral` (ambiguous questions like "who is this?"), and `unknown` (LLM error, fails open so nothing is ever silently lost).

**You do not get pinged for:** `ooo` (out of office, auto-replies), `not_interested` (remove me, unsubscribe, wrong person, etc.).

It fires on **every** reply in a thread, not just the first one.

Sample message:

```
🔥 Booking Ready

Lead: John Doe
Email: john@acmecorp.com
Company: Acme Corp
Campaign: Q1 SaaS Outreach
Subject: Re: Quick question

Reply:
Hey, sounds interesting! When can we hop on a call this week?
```

### Two accounts, one worker

- `POST /webhook` - your own Instantly account.
- `POST /webhook/client` - a second Instantly account (a client's, a partner's). **Notify-only.** Messages from this route get a `🏢 CLIENT ACCOUNT 🏢` banner on top so you can never confuse them with your own. Rename the banner with the `CLIENT_ACCOUNT_LABEL` var in `wrangler.toml`.

Each route has its own webhook secret on purpose: a leak on one account's webhook config cannot forge requests to the other.

If you only have one account, just ignore `/webhook/client` and never register it.

---

## What you need

| Thing | Cost | Why |
|---|---|---|
| Cloudflare account | Free | Runs the worker + KV store |
| Node.js 18+ | Free | To deploy with `wrangler` |
| Instantly.ai account + API key | You already pay for Instantly | Source of the webhook |
| Telegram account | Free | Where the notifications land |
| OpenRouter account + API key | Pay as you go, ~$0.001 per ambiguous reply | LLM fallback classifier |

Realistically the LLM costs cents per month. Most replies are caught by the free regex layer.

---

## Setup

### 1. Get the code running locally

```bash
cd instantly-reply-notifier
npm install
```

### 2. Create your Telegram bot

1. In Telegram, message **@BotFather** and send `/newbot`. Follow the prompts.
2. It gives you a **bot token** that looks like `123456789:AAE...`. Save it.
3. Send your new bot any message (e.g. `/start`) - a bot cannot message you until you message it first.
4. Get your **chat ID**:
   ```bash
   curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates"
   ```
   Look for `"chat":{"id":123456789` in the response. That number is your `TELEGRAM_CHAT_ID`.

### 3. Get an OpenRouter API key

Sign up at <https://openrouter.ai>, create a key, add a few dollars of credit. The worker uses `openai/gpt-4o-mini`. To use a different model, change the `model` field in `src/classifier.ts`.

### 4. Create the KV namespace

```bash
npx wrangler login
npx wrangler kv namespace create DEDUP_KV
npx wrangler kv namespace create DEDUP_KV --preview
```

Each command prints an `id`. Paste them into the two placeholders in `wrangler.toml`.

### 5. Generate two webhook secrets

```bash
openssl rand -hex 32   # -> WEBHOOK_SECRET
openssl rand -hex 32   # -> WEBHOOK_SECRET_CLIENT
```

Keep them different. See the note under "Webhook secrets" below before deciding whether to set them at all.

### 6. Set the secrets in Cloudflare

Secrets are stored by Cloudflare, never in this repo:

```bash
npx wrangler secret put TELEGRAM_BOT_TOKEN
npx wrangler secret put TELEGRAM_CHAT_ID
npx wrangler secret put OPENROUTER_API_KEY
npx wrangler secret put WEBHOOK_SECRET
npx wrangler secret put WEBHOOK_SECRET_CLIENT     # only if you use the second route
npx wrangler secret put INSTANTLY_API_KEY         # only if you enable auto-reply (off by default)
```

Each command prompts for the value and stores it encrypted. Confirm with `npx wrangler secret list` (it shows names only, values are never readable back).

For local development instead, copy `.dev.vars.example` to `.dev.vars` and fill it in. That file is gitignored.

### 7. Deploy

```bash
npm run deploy
```

Wrangler prints your worker URL, e.g. `https://instantly-reply-notifier.<your-subdomain>.workers.dev`. Check it:

```bash
curl https://instantly-reply-notifier.<your-subdomain>.workers.dev/health
# {"status":"ok","timestamp":"..."}
```

### 8. Register the webhook in Instantly

Grab your Instantly API key (Instantly dashboard → Settings → Integrations → API), then:

```bash
INSTANTLY_API_KEY=your_key ./scripts/register-webhook.sh \
  https://instantly-reply-notifier.<your-subdomain>.workers.dev/webhook
```

This registers `reply_received` across **all campaigns** on that account, and then lists every webhook registered so you can confirm.

For a second account, run the same script with **that account's** API key and the `/webhook/client` URL.

### 9. Prove it works

```bash
WEBHOOK_SECRET=your_secret ./scripts/test-webhook.sh \
  https://instantly-reply-notifier.<your-subdomain>.workers.dev/webhook
```

You should see: health ok, a real Telegram message for the positive reply, `notified:false` and **no** Telegram message for the not-interested reply, and `401` for the bad secret.

Do not skip the negative case. A notifier that never fires looks identical to one that is dropping everything, so you have to watch it stay quiet on purpose before you trust its silence.

Then send yourself one real reply through a live campaign to confirm end to end.

---

## Webhook secrets: read this

The worker checks an `X-Webhook-Secret` header, **but only if the corresponding secret is set**. If `WEBHOOK_SECRET` is unset, the route accepts unauthenticated POSTs.

Instantly's webhook registration may not let you attach a custom header. So:

- Test whether real Instantly deliveries arrive with your secret **before** you rely on it. If real replies stop notifying after you set the secret, that is why.
- If Instantly cannot send the header, either leave the secret unset (the worst case is a stranger who knows your URL sending you fake Telegram messages), or move the secret into the URL path in `src/index.ts` and register that longer path with Instantly.

Either way, decide it deliberately rather than assuming the header is being sent.

---

## Tuning the classifier

Everything lives in `src/classifier.ts`:

- `OOO_PATTERNS` - substrings that mark an out-of-office.
- `NOT_INTERESTED_PATTERNS` - regexes that mark a decline. Includes standalone `REMOVE` / `STOP` on their own line, which catches replies where someone types one word above their signature.
- `BOOKING_PATTERNS` - regexes that mark a hot reply. Note that bare "yes"/"sure" are deliberately **excluded** - they were too broad and fired on removal replies.
- `BOOKING_NEGATORS` - phrases that cancel a booking match ("sounds good, but I don't...").
- `shouldNotify()` - the final allowlist of categories that reach Telegram.

Rules run first and are free. Anything that matches nothing goes to the LLM. If your LLM bill is climbing, that means lots of replies fall through the rules - add patterns.

---

## The auto-reply feature (off by default, and there is a reason)

`src/autoReply.ts` can auto-send a template reply on whitelisted campaigns, with no human in the loop. `AUTO_REPLY_CAMPAIGNS` is empty, which disables it entirely.

**It misfired in production.** Instantly's `GET /api/v2/emails?search=<lead_email>` does not actually filter by lead - verified live, two different `search` values returned identical result sets. The code picks the most recent received email in the campaign, which turned out to be a **different person's** thread, and an automated pitch went out into a real, months-old human conversation.

If you want to enable it, fix it first:

1. Compare the resolved record's recipient with the webhook's `lead_email` and **abort on mismatch** (fail closed).
2. Add a dry-run mode that logs the resolved `{id, eaccount, recipient}` instead of sending, and eyeball it.
3. Test on a dedicated throwaway campaign with no overlapping leads. Do not use a fake lead inside a live campaign, and do not reuse a real prospect's old subject line (that is exactly how the misfire happened).
4. Replace the placeholder copy and booking link in `renderBody()` / `BOOKING_LINK`.

The client route (`/webhook/client`) is hard-gated to never auto-send, regardless of what is in `AUTO_REPLY_CAMPAIGNS`. Keep it that way.

Notifications work perfectly without any of this. Most people should leave it off.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| No Telegram message at all | Worker not receiving events | `npx wrangler tail` in this dir, then trigger a reply and watch |
| No Telegram message | Instantly webhook missing | Re-run `scripts/register-webhook.sh`, check the listing it prints |
| No Telegram message | Secret mismatch (401) | See "Webhook secrets" above |
| Telegram API "chat not found" | You never messaged the bot | Send `/start` to your bot, then re-check the chat ID |
| Telegram "bot was blocked" | You blocked it | Unblock, send `/start` again |
| Duplicate messages | Instantly retried outside the dedup window | Raise `DEDUP_TTL_SECONDS` in `src/index.ts` |
| Real replies never notify | Over-aggressive not-interested patterns | Check `wrangler tail` for the category, trim `NOT_INTERESTED_PATTERNS` |
| OpenRouter bill rising | Too many replies missing the rules | Add patterns to `classifier.ts` |
| `KV namespace not found` on deploy | Placeholder ids still in `wrangler.toml` | Step 4 |

Live logs: `npx wrangler tail`. Every decision is logged (`[webhook]`, `[classify]`, `[autoReply]`).

---

## Files

```
src/index.ts       webhook routing, secret check, KV dedup, orchestration
src/classifier.ts  rules + LLM classification, shouldNotify allowlist
src/telegram.ts    message formatting (HTML-escaped) and Bot API send
src/autoReply.ts   optional auto-reply, disabled, read the warning
wrangler.toml      worker name, KV bindings, non-secret vars
scripts/           webhook registration + smoke test
.dev.vars.example  template for local secrets (copy to .dev.vars)
```

No API keys, tokens, account ids, or personal URLs are in this repo. Everything sensitive comes from Cloudflare secrets you set yourself.
