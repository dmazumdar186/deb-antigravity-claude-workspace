# Outbound Client Acquisition (LinkedIn-first + Cold Email)

> Personal client-acquisition engine for Debanjan's AI/automation build services. Fully isolated from Accessory Masters (fresh keys, own domains/inboxes, no AM paths). Plan of record: `~/.claude/plans/floofy-forging-wilkes.md`.

## Goal

Book discovery calls for AI/automation build work ($1-2.5K fixed-price, 1-3 week builds) from founder-led SaaS/DTC/agency companies (10-200 emp) that show a manual-work pain signal. **LinkedIn DMs are the first (manual) channel; cold email is the scaled channel.** Stay <=EUR 25/mo. Approve-before-send. Target ~20-40 personalized emails/day after warmup.

The success criterion is NOT "emails sent" — it is the SPEC in the plan file (G1-G11). G9 (the offer actually converts: v0 >=1 interested reply / 30 touches; v1 positive-reply >=0.3% / 500 sends + >=1 booked call) is the only goal that matters; the rest are mechanics.

## Inputs

### Config (gitignored, copied from examples)
- `config/outbound_debanjan.json` (from `.example.json`) — ICP, geos (exclude CA), send caps, inbox roster, warmup schedule, scoring weights, kill-criteria.
- `config/tone_debanjan.json` (from `.example.json`) — voice profile; example_openers + writing_samples filled from the v0 3-warmest-conversation debrief.
- `config/outbound_lia.md` — GDPR Legitimate-Interest Assessment (drafted; operator confirms French registered address).

### Environment (fresh personal keys only — NEVER AM keys)
| Var | Purpose |
|---|---|
| `GEMINI_API_KEY` | personalization + reply classification + auto-reply (free tier) |
| `OUTBOUND_MILLIONVERIFIER_KEY` / Reoon key | email verification (fresh, not AM's `MILLION_VERIFIER_API_KEY`) |
| `OUTBOUND_ANYMAILFINDER_KEY` | pay-per-verified finder (fresh, not AM's `ANYMAILFINDER_API_KEY`) |
| `APOLLO_API_KEY` | Apollo (free-tier UI export path) |
| `OUTBOUND_TELEGRAM_BOT_TOKEN` / `OUTBOUND_TELEGRAM_CHAT_ID` | hot-lead pings (new bot) |
| `SMTP_USER_N` / `SMTP_PASS_N` per inbox | Zoho/Hostinger SMTP submission + IMAP |

## Tools / Scripts

`execution/personal_workflows/outbound_engine/`:
- `signal_sourcing.py` — Gate-0 company-signal harvest (job/intent/stack/growth feeds).
- `lead_scorer.py` — deterministic ICP-fit + signal-strength + deliverability score; threshold gate.
- `stage1_source_draft.py` — orchestrates source -> resolve -> enrich -> verify -> personalize -> Sheet (`--dry-run`).
- `sheet_review.py` — writes the review batch to Google Sheet; reads `approve=Y` rows.
- `multi_inbox_sender.py` — SMTP submission, rotation, caps, jitter, footer, suppression (`--dry-run`).
- `followup_scheduler.py` — SQLite; 2-3 steps; stop-on-reply.
- `reply_ingest.py` — IMAP per-inbox poll -> classify -> auto-reply -> Telegram -> suppression.
- `warmup.py` — reciprocal warmup ramp; mail-tester gate.
- `health.py` — status (credit/secret/last-run/reputation); LIVE-PROBATIONARY counter.

Reused workspace modules: `enrichment/anymailfinder_lookup.py`, `enrichment/million_verifier.py`, `personalization/ai_opener_generator.py` (Gemini edit), `modules/reply_classifier.py` (reframe), `modules/outputs/auto_reply.py` (Gemini + voice), `modules/telegram.py`, `modules/pipeline_utils.py`, `modules/llm_client.py`, `/humanizer`.

Tests (contract, written test-first): `tests/acceptance_outbound.py` (G1/G4/G5/G7), `tests/front_door_outbound.py` (G6/G8/G11).

## Outputs

- Daily review batch in a Google Sheet (approve-before-send).
- After approval: ~20-40 plain-text personalized emails/day from warmed inboxes.
- Replies classified (hot/positive/neutral/negative/auto-reply-OOO); hot -> Telegram <5min + Cal.com auto-reply; negative/unsub -> permanent suppression.
- Weekly report: sent/replied/positive/hot/booked + cost ledger (EUR) + reply-rate vs kill-criterion.

## Steps

1. **Phase 0 (operator):** provision 2 domains + DNS (SPF/DKIM/DMARC), 3 Zoho/Hostinger inboxes, fresh keys, Telegram bot, Cal.com. Copy example configs, fill real values.
2. **Phase 0.5 (operator, v0):** hand-send ~30 LinkedIn DMs (manual, 1st-degree + warm 2nd, <20 cold requests/week) + ~10 emails from an existing warm inbox. Debrief the 3 warmest conversations -> fill `tone_debanjan.json` + seed the acceptance corpus. GATE: >=1 interested reply before Phase 2.
3. **Phase 2a:** `py execution/personal_workflows/outbound_engine/stage1_source_draft.py --config config/outbound_debanjan.json --dry-run` -> verify `would_*` counts sane.
4. **Phase 2b:** acceptance gate green on the v0 corpus; junk rows hard-fail the run.
5. **Phase 3-4:** sender dry-run, then reply pipeline.
6. **Phase 5-6:** warmup 3-4 wks; front-door synthetic 5 consecutive green days; then live at ~20/day ramping to 40. Status = `LIVE-PROBATIONARY: day N of 5` until cleared.

## Edge Cases

- **AM lockdown:** never use AM keys/credits/paths (`api-proxy/`, `accessory_masters*`, `config/accessory_masters*`, AM `INSTANTLY/GHL/ANYMAILFINDER/MILLION_VERIFIER` keys). Fresh keys only.
- **Haiku ban:** `auto_reply_model` / `classifier_model` must be Gemini or Sonnet, never `claude-haiku-*`.
- **Canada excluded:** drop any `.ca` / Canadian-geo prospect (CASL near opt-in).
- **Free finder cap (~225-280/mo):** free-only ~= 8/day; the Anymail pay-per-verified path lifts to 20-30/day. If stacked-finder UI management is too costly in time, go straight to Anymail.
- **DIY warmup weaker than managed:** if mail-tester <8 or seed lands in spam at week 4, escalate to paid Warmbox (~EUR 19/inbox) or route sending via Instantly (+EUR 34/mo) — re-authorize budget.
- **Corpus optimism:** v0 corpus from warm touches may over-pass vs cold; recalibrate after first 50-100 cold sends.
- **Kill-criteria:** v0 0 interested/30 -> rewrite offer before building; v1 <0.3% positive/500 sends -> pause + review.
- **Reply attribution:** IMAP poll per inbox + match reply `From:` to prospect; do not rely on Gmail-forward header parsing.
- **Send compute:** run the send stage from a stable IP (Windows Task Scheduler or Modal), not an ephemeral CI runner (provider may flag many cloud-IP logins).
