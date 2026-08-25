# Install status — instantly-reply-notifier

Installed 2026-08-25 from `C:\Users\deban\Downloads\instantly-reply-notifier`.

## Where it lives

- Source: `execution/infrastructure/instantly_reply_notifier/`
- Deployed: <https://instantly-reply-notifier.debanjan186.workers.dev>
- Cloudflare account: `Debanjan186@gmail.com's Account` (personal, not AM)
- KV namespace `DEDUP_KV`: `c48c6f25134749bcbcb7265b491a4e2b` (preview `b0c9c5041b8344ef94f01651e626f159`)

## Current health

```
GET /health
{"status":"ok","telegram_bound":true,"openrouter_bound":true,"kv_bound":true,
 "webhook_secret_bound":true,"client_route_secret_bound":false,"auto_reply_campaigns":0}
```

Fully wired. Operator confirmed real Telegram delivery on 2026-08-25.

## Secrets set

| Secret | Status | Source |
|---|---|---|
| `OPENROUTER_API_KEY` | SET | workspace `.env` |
| `WEBHOOK_SECRET` | SET | generated at install, mirrored to `.env` as `NOTIFIER_WEBHOOK_SECRET` |
| `TELEGRAM_BOT_TOKEN` | SET | bot `@Instantly_Deb_bot`, mirrored to `.env` |
| `TELEGRAM_CHAT_ID` | SET | value in `.env` as `TELEGRAM_CHAT_ID` (not recorded here) |
| `WEBHOOK_SECRET_CLIENT` | not set | only needed for the `/webhook/client` second-account route |
| `INSTANTLY_API_KEY` | not set | only needed for auto-reply, which stays OFF |

## Instantly webhook

Registered 2026-08-25 on Instantly workspace `ad580e93-62da-4ccf-9b4a-26ecd094c7d6`
("Main workspace", owner `f7cf9a47...`). This is NOT the Accessory Masters
workspace - key supplied by the operator as `INSTANTLY_NOTIFIER_API_KEY`.

- Webhook id: `01a0379e-0683-73a7-85fe-9dc7bc08dab8`
- Event: `reply_received` -> `https://instantly-reply-notifier.debanjan186.workers.dev/webhook`
- Auth: `X-Webhook-Secret` header, value mirrored in `.env` as `NOTIFIER_WEBHOOK_SECRET`

**The repo's `scripts/register-webhook.sh` does NOT send the `headers` field.**
Using it as written registers a webhook that gets 401'd by our own worker on
every real delivery, because `WEBHOOK_SECRET` is set. Registration was done with
an explicit `headers` object instead. Fix the script before reusing it.

This account already had its own `reply_received` webhook pointing at
`instantly-reply-notifier.siva-d259.workers.dev` (a different Cloudflare
account). That one was left untouched; ours was added alongside. Instantly
delivers to both.

Active campaigns on the account at install time: "Sticky leads | Window
replacements", "Recruitment Agencies EU 130826", "Recruitment Agencies UK
130826", "SMB Acquisition- Other- 170826".

## Changes made to the downloaded code

Four fixes, all driven by the same principle: for a notifier, a silent drop is
far worse than a false alarm.

1. **`telegram.ts` — send failures were swallowed.** `sendTelegramMessage` logged
   a non-2xx and returned normally, so `index.ts` reported `notified:true` even
   when nothing reached the phone. It now throws, and retries once on 5xx or a
   network blip (not on 4xx, which is a config error a retry cannot fix).

2. **`index.ts` — honest reporting.** The response now carries the real
   `notified` value plus a `notify_error` field, so "dropped on purpose" and
   "tried to reach the phone and failed" are distinguishable in `wrangler tail`.

3. **`classifier.ts` — two OOO false positives that silently dropped hot leads.**
   - `"ooo"` was matched as a bare substring, so `"Sooo interested, let's talk!"`
     was classified out-of-office and dropped. Now `/\booo\b/i`.
   - `"return on"` matched `"return on investment"` — a common phrase in a sales
     reply — and dropped it. Now word-bounded with the money senses excluded.

   Verified: both strings were DROPPED under the original code and notify under
   the fix, while genuine OOO ("I am out of office until Monday", "I return on
   Monday") still drops.

4. **`classifier.ts` — the LLM treated annoyance as a decline.** Caught by the
   acceptance gate running against the live worker:
   `"Who is this and how did you get my email?"` came back `negative` and was
   silently dropped. The old prompt defined negative as "wants to be removed, is
   not interested, or is **dismissive**". Rewritten so `negative` means an
   explicit stop/decline only, and everything short of that — suspicious, blunt,
   annoyed, confused — is `neutral` and reaches the phone.

5. **`index.ts` — `/health` now reports which secrets are bound.** Without it, a
   worker with no Telegram token looks identical to a healthy one right up until
   a real reply goes nowhere.

## Audit round 2 (2026-08-25) — bugs found AFTER the first green

An independent code review found silent-drop bugs that the first 16-case gate
did not cover. All six were verified live before fixing: a real POST to the
deployed worker returned `not_interested` / `ooo` and sent nothing.

| Reply text | Was | Cause |
|---|---|---|
| "we are good to go, what time works Tuesday?" | dropped | `we're (good\|set)` matched a booking confirmation |
| "We are all set for the call, see you then" | dropped | same pattern |
| "please do not hesitate to call me" | dropped | bare `please don't` matched an invitation |
| "I will pass this along to our VP" | dropped | bare `i'll pass` matched a forward |
| "We already have budget approved, lets talk" | dropped | bare `already have` |
| "no need to explain further, lets set up a call" | dropped | bare `no need` |
| "We help clients book dream vacation homes" | dropped | `vacation` as a bare OOO substring |

Each pattern was narrowed to its decline sense only, and counter-cases were
added so the genuine declines ("we are all set, no thanks", "we already have a
vendor", "I am on vacation until the 12th") still drop. Also fixed in the same
round:

- **`index.ts` dropped empty-text replies with no log line and no notification.**
  Instantly returns empty text for image-only and some HTML-only bodies. Now
  fails open: notifies with "(no text extracted - open the thread in Instantly)".
- **The KV dedup key ignored reply content.** Email threads reuse `Re: <subject>`
  for every message, so a lead who wrote "not interested" then "actually wait,
  tell me more" within 120s had the second message dropped as a duplicate. The
  key now includes a content hash.
- **Webhook auth failed OPEN when the secret was unset.** Forgetting
  `wrangler secret put` turned the route into an open endpoint. Now returns 500.
- **Secret comparison was not constant-time.** Now XOR-accumulating.
- **`scripts/register-webhook.sh` omitted the `headers` field**, registering a
  webhook that Instantly reports as active while the worker 401s every delivery.
  Fixed, and it now requires `WEBHOOK_SECRET`.

## Acceptance gate

`tests/acceptance_classifier.sh <webhook-url>` — 28 cases, 17 that must reach
the phone and 11 that must stay silent.

Strictness is decided from `/health`, not assumed: when `telegram_bound=true` a
notify case must return `notified:true`, so an attempted-but-failed send is a
FAIL. Only when Telegram is genuinely unconfigured (local dev) does intent count.
The earlier version credited `notify_error` as a pass unconditionally, which
would have printed GREEN straight through a Telegram outage.

Last run against the deployed worker: **28/28 PASS**.

`tests/front_door_instantly_reply_notifier.sh` — the live front-door synthetic.
No fixtures. Checks (1) the worker is healthy and Telegram is bound, (2) the
Instantly webhook is still registered AND carries the secret header, (3) a real
POST actually delivers. Last run: **PASSING**.

```bash
export WEBHOOK_SECRET=$(grep -E '^NOTIFIER_WEBHOOK_SECRET=' ../../../.env | cut -d= -f2-)
bash tests/acceptance_classifier.sh https://instantly-reply-notifier.debanjan186.workers.dev/webhook
```

## Owed before this can be called working

1. **A real inbound reply.** Every layer is verified except Instantly actually
   emitting `reply_received` for a genuine lead reply. The webhook is registered
   and enabled, but only a real reply on a live campaign proves the last hop.
   Until one lands, this is wired-and-verified, not battle-tested.
2. **OpenRouter balance is ~EUR 0.36** (5.00 credited, 4.61 used). Only replies
   the regex layer cannot classify reach the LLM, so that is thousands of
   replies. When it runs dry the worker fails OPEN - the operator still gets
   notified, with category `unknown` instead of a real label. Nothing goes
   silent, but the filtering quality degrades.
3. **No fallback channel if Telegram itself fails.** A revoked bot token would
   make every notify fail at the last hop, visible only in `wrangler tail`.
   Consecutive-failure tracking surfaced on `/health` is the cheap next step.
4. **`/webhook/client` is unconfigured.** `WEBHOOK_SECRET_CLIENT` is unset, and
   the route now fails closed (500) rather than accepting unauthenticated posts.
   Set the secret if a second account is ever wired.

## Relationship to `self_outbound_webhook_worker`

That worker (`self-outbound-webhook.debanjan186.workers.dev`) is already
deployed and separately handles bounce/unsubscribe events feeding the
suppression list. Its `/health` also reports `telegram_alert_bound:false`, so
its Telegram alerts have never fired either. The two workers are complementary,
not duplicates — this one classifies and notifies, that one persists suppression
events. Registering this one does not affect that one.

## Revert

```bash
cd execution/infrastructure/instantly_reply_notifier
npx wrangler delete instantly-reply-notifier
```
