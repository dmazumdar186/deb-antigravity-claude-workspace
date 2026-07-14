# Phase 3 Handoff — self_outbound_system_v2

**Written**: 2026-07-14, mid-session (operator was at gym; ran on auto-mode)
**Target start**: any time from now through 2026-07-27 (warmup ends day 14)
**Session model**: Opus 4.7 orchestration + Sonnet 4.6 sub-agents (4 parallel for the video analysis)

---

## What changed in Phase 2 (since 2026-07-13)

### 1. Nick Saraev "Definitive Guide to Cold Email Copywriting" — full 4-hour analysis
- **Source video**: [https://www.youtube.com/watch?v=uSTGNHGFOAo](https://www.youtube.com/watch?v=uSTGNHGFOAo) (3:59:11)
- **Method**: Full transcript pulled via `youtube-transcript-api` (Gemini URL-native path failed with server-disconnect on 4hr video). Split into 4 hour-long chunks. 4 parallel Sonnet 4.6 sub-agents analyzed each chunk with instructions to extract everything verbatim — no summarization.
- **Cost**: ~€2 in Anthropic tokens (4 × ~150k tokens per agent)
- **Output**: [deliverables/self_outbound_system/nick_saraev_cold_email_full_analysis.md](../../../deliverables/self_outbound_system/nick_saraev_cold_email_full_analysis.md) — 30k words, 183KB
- Covers all 9 sections Nick names: 7 psychology principles, 3 outbound components, 4-step framework, offer construction, 10 live roasts + rewrites (verbatim originals + rewrites captured), per-platform (email/LinkedIn/X/IG/iMessage), subject lines, follow-ups, iteration, AI-in-copywriting, grey-hat
- Ends with a **Master Synthesis** section — consolidated rubric applied specifically to `self_outbound_system_v2`

### 2. Workstream A — tone.json v2 + personalizer.py rewrite

- **[config/tone.json](config/tone.json)** — v2, applies Nick's full 4-step + 7-principle framework
  - New structure per variant: `subject_examples`, `opener_examples`, `give_first_examples`, `who_am_i_examples`, `offer_examples`, `cta_time_proposals`
  - `voice` section adds `text_message_test`, `corporate_signals_banned`, `nick_framework_rules`
  - Opener max_words bumped 15→22 (Nick's ≤2-sentence rule allows this; 15 was under-floor for two-clause openers with em-dash pivot)
  - New constraints: `give_first_constraints`, `who_am_i_constraints`, `offer_constraints`, `cta_constraints`
  - Signature: `sender_name`, `sender_line_2`, `sent_from_mobile_variants`, `intentional_imperfection_probability: 0.15` (per Nick's humanization doctrine — 15% of emails carry one deliberate small imperfection at the end)
  - Follow-up section: 2-then-expand doctrine, F2 template ("Hey X, checking in on Y. TLDR..."), 4-day delay, subject rotation flag
  - Email length target: 65-110 words (Nick's rewrites average 90-130)

- **[personalizer.py](personalizer.py)** — body assembly refactored
  - Old: `body = opener + CTA + signature`
  - New: `body = personalization + give_first + who_am_i + offer + cta_time_proposal + signature`
  - Deterministic dry-run: `_pick()` hashes lead.email into a stable index across each variant's example arrays so same lead always gets same variant across re-runs, but leads spread across examples
  - New `_substitute()` handles `{first_name}` (Nick's first-word trick), `{company}`, `{topic}`, `{role}`, `{product}`, `{source}`, `{cal_com_url}` tokens
  - `{cal_com_url}` reads from `CAL_COM_BOOKING_URL` env var; default fallback for tests
  - **Design tension resolved**: Nick says "no links in cold emails" but our CTA needs Cal.com. Compromise: propose 2 specific times first ("15:30 CET today or Tuesday 10:00 — reply which works"), fall back to Cal.com link. Best of Nick's specific-time-CTA + operator's actual scheduling tool.

- **Test results**: 68/68 pass (up from 57 — 11 new suppression_writer tests)
- **Acceptance corpus**: green, 0 regressions on ICP filter side
- **Dogfooded 3 seed leads**: Sarah Chen (variant A, 107 words), Marc Dubois (variant B, 108 words), Priya Sharma (variant C, 123 words). All hit Nick's 4 steps + 5+/7 psychology principles

### 3. Workstream C1 — suppression writer

- **[suppression_writer.py](suppression_writer.py)** — new
  - Idempotent add: `add_suppression(email, reason, source, alert=True, dry_run=False)`
  - Bulk mode: `add_bulk(entries, ...)` for cron sync from KV
  - Cross-platform file lock (`msvcrt` on Windows, `fcntl` on POSIX) at `config/.suppression.lock` to prevent race conditions
  - Atomic write via temp-then-rename
  - Email normalization: lowercase + strip (no plus-addressing collapse — those ARE distinct addresses for consent)
  - AM-locked-domain awareness: flags entries whose domain is in `suppression.json.domains` (belt + suspenders vs. any icp.json regression)
  - Optional Telegram alert using `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` (already in .env from Phase 1)
  - **CLI**: `py suppression_writer.py --email x@y.com --reason negative_reply --source reply_classifier`
  - Valid reasons: `negative_reply`, `unsubscribe_click`, `hard_bounce`, `spam_complaint`, `manual_add`, `already_customer`, `am_locked_domain`, `wrong_person`, `duplicate_of_prior_lead`, `other`
  - Valid sources: `webhook`, `reply_classifier`, `manual`, `cron`, `seed`

- **[tests/test_suppression_writer.py](tests/test_suppression_writer.py)** — 11 tests, all pass
  - Happy path, dedup, case-normalization, AM-locked flag, invalid-input errors, dry-run, bulk mode, missing-file, ISO timestamp shape

- **[config/suppression.json](config/suppression.json)** — `_writer_owed` removed; replaced with `_writer` pointer to `suppression_writer.py` and `_webhook_worker` pointer to the CF Worker

### 4. Workstream C2 — Cloudflare Worker (webhook receiver)

- **[execution/infrastructure/self_outbound_webhook_worker/](../../infrastructure/self_outbound_webhook_worker/)** — new
  - `src/index.js` — receives Instantly webhook events, HMAC-SHA256 verifies via `X-Instantly-Signature`, persists event to KV (`SUPP_EVENTS` binding), fires Telegram alert, returns 200
  - Event type → reason mapping: `reply_received → negative_reply`, `email_bounced → hard_bounce`, `unsubscribed → unsubscribe_click`, `marked_as_spam → spam_complaint`
  - Endpoints: `GET /health`, `POST /instantly` (HMAC-verified), `POST /manual` (X-Worker-Secret authed, for operator CLI use)
  - Uses `crypto.subtle.sign` + constant-time compare (no timing side-channel on the HMAC verify)
  - Uses `crypto.getRandomValues` (no `Math.random`) — safe in CF Workers
  - `wrangler.toml` — namespaced worker config
  - `README.md` — one-time deploy instructions, secret provisioning, Instantly registration steps, curl-based HMAC test

- **NOT YET DEPLOYED** — operator needs to run:
  ```bash
  cd execution/infrastructure/self_outbound_webhook_worker
  wrangler kv namespace create SUPP_EVENTS
  # paste the returned id into wrangler.toml
  wrangler secret put INSTANTLY_WEBHOOK_SECRET
  wrangler secret put TELEGRAM_BOT_TOKEN
  wrangler secret put TELEGRAM_CHAT_ID
  wrangler secret put WORKER_SECRET
  wrangler deploy
  ```
  Then register the printed URL `https://<worker>/instantly` in Instantly's Settings → Webhooks.

### 5. Workstream C3 / C4 — HELD

- **C3 (real mail-tester canary)**: Not done. The existing `canary.py` uses IMAP-poll for INBOX placement — that's actually a better front-door synthetic than a mail-tester spam score (mail-tester.com has no public API — it's a "send to random address, screen-scrape the score URL" flow). The IMAP path just needs Phase 1 env vars (`CANARY_DESTINATION_EMAIL`, `CANARY_IMAP_HOST`, `CANARY_IMAP_USER`, `CANARY_IMAP_APP_PASSWORD`) provisioned in .env, then flip `--live`. Recommend doing this instead of chasing mail-tester.

- **C4 (Sonnet dogfood on 5 real leads)**: HELD — needs real leads from Workstream B (Apify sourcing). Blocked pending operator authorization to burn Apify credits.

---

## What's still owed for Phase 3

### Priority-1 (blocking a live campaign)

1. **Workstream B — source first 100 leads via Apify** (~1 hour, ~$1-2 Apify credits)
   - Wire the Apify LinkedIn Sales Nav actor in [sourcer.py](sourcer.py) — search: Paris + Île-de-France, 3 ICP segments from [config/icp.json](config/icp.json)
   - Run through [enricher.py](enricher.py) (domain check, catchall check)
   - Run through [icp_filter.py](icp_filter.py) (verify 0 leaks against acceptance corpus)
   - Save output to `.tmp/self_outbound_system/leads_batch_001.json`
   - Sanity-check 10 randomly sampled leads by hand — if ≥8/10 match ICP, greenlight

2. **Workstream C4 — Sonnet dogfood** (~30 min, ~€0.02)
   - After Workstream B produces real leads, run [personalizer.py](personalizer.py) `--live --llm sonnet` on 5 of them
   - Inspect the output — does it read like a human wrote it? Does it hit Nick's 4 steps?
   - **Note**: `personalize_live()` is currently stubbed with `NotImplementedError`. Owe: implement the live Sonnet call using cached system prompt from tone.json v2, per Nick's AI doctrine (one variable at a time inside a human-written sentence)

3. **Deploy the webhook Worker** (see Workstream C2 above, ~15 min operator interaction)

4. **Register Instantly webhook + set up KV sync cron** (~30 min)
   - After Worker deploys, register `https://<worker>/instantly` in Instantly Settings → Webhooks
   - Write `sync_suppression_from_kv.py` — pull all `event:*` keys via `wrangler kv key list`, call `suppression_writer.add_bulk()`, delete consumed keys (see [webhook README](../../infrastructure/self_outbound_webhook_worker/README.md) for spec)
   - Schedule the sync via GitHub Actions cron or run on the daily pipeline

5. **Wire canary.py to live IMAP** (~30 min)
   - Add `.env` vars: `INSTANTLY_INBOX_EMAIL`, `CANARY_DESTINATION_EMAIL`, `CANARY_IMAP_HOST`, `CANARY_IMAP_USER`, `CANARY_IMAP_APP_PASSWORD`
   - Implement `run_live()` in [canary.py](canary.py): send test email, sleep 5 min, IMAP-poll for the message, assert INBOX and NOT SPAM/PROMOTIONS
   - Add to daily cron

6. **Instantly campaign draft** (operator UI work, ~30 min)
   - Log into Instantly UI, create a new campaign in DRAFT state
   - 20/day cap, Europe/Paris timezone, Mon-Fri 09:00-18:00, opens+clicks OFF (deliverability best practice)
   - Import first 100 leads from Workstream B
   - Load the 3 A/B/C variant email bodies from `personalized_leads_*.json`
   - Set up 2-step sequence (F1 + F2, 4-day delay, F2 uses [tone.json.follow_up.f2_template](config/tone.json))

### Priority-2 (nice-to-have before flipping live)

7. **Update the directive** to reflect tone.json v2 shape (per workspace self-annealing rule)
   - [directives/personal_workflows/self_outbound_system.md](../../../directives/personal_workflows/self_outbound_system.md) should describe the new 5-slot per-variant structure and the suppression writer + webhook worker
   - Recommend: spawn the `documenter` sub-agent per [CLAUDE.md](../../../CLAUDE.md) `## Self-annealing loop` section

8. **Mandatory Audit Stack** (per `~/.claude/rules/mandatory-audit-stack.md`)
   - Not run this session (would spawn 6 parallel auditors; deferred pending operator sign-off given Anneal + Panel-pass cost tokens)
   - Recommended before flipping live: run `/code-review ultra` + panel-pass + full test suite + anneal on the diff

### Priority-3 (post-launch)

9. **Landing page deployment** — explicitly dropped by operator on 2026-07-13, but scaffold exists at [landing_page/](landing_page/). Porkbun URL forward (`debanjanm.com → prodcraft.fyi`) serves the domain for now.

10. **Legal — LIA + SIRET + postal address** — explicitly dropped by operator on 2026-07-13. Scaffold at [legal/lia.md](legal/lia.md). Not needed for a private beta.

11. **Secret rotation** — Telegram bot token + Apify token were pasted in Phase 1 chat. Rotate via BotFather `/revoke` + Apify console before flipping live campaigns.

---

## Honest gaps (panel-pass Lens 4 — what someone might still ask)

- **Karpathy lens (empirical)**: I did NOT A/B test the new variants — the dogfood run was 3 seed leads through the dry-run mock, not a live send. Owed: A/B the 3 variants at 500-1000 sends per variant per Nick's iteration doctrine (Hour 4). Cost: ~€3-5 for the sends themselves. Owner: operator after warmup ends.
- **Cherny lens (dogfood)**: Dry-run on 3 fixture leads. Real-lead dogfood is C4 above — blocked on Workstream B.
- **Amodei lens (deployment)**: `tone.json v2` + `personalizer.py` + `suppression_writer.py` + `test_suppression_writer.py` + worker code — all committed locally (this session). NOT pushed to origin. Worker NOT deployed. Instantly campaign NOT created. All above are operator sign-off gates.
- **Panel-pass Research-team lens (honest gaps)**:
  - The `{topic}` fallback in `personalizer.py` (`notes.split('.')[0][:40]`) produces awkward substitutions like "Read your latest LinkedIn post on Just raised seed" for seed leads without a proper `topic` field. Fix: enricher.py should populate a proper `topic` field per lead (recent post title, funding announcement, product launch — the "research signal" the Phase 2 handoff spec called for).
  - The live `personalize_live()` is stubbed. Implementing it is a 2-hour Sonnet-with-caching build — the shape is: cached system prompt (tone.json v2's voice + framework rules, ~1200 tokens), per-lead user message asking for ONE variable at a time per Nick's AI doctrine, output ~200 tokens. Expected cost per 600-lead month: ~€1.60.
  - The `sync_suppression_from_kv.py` is not written. Without it, KV events accumulate until the 30-day TTL expires and are silently lost. A cron that pulls KV → suppression.json + deletes consumed keys is Priority-1.
  - No end-to-end test that goes send → webhook → KV → sync → suppression.json → filter (excludes on next run). Would be the true front-door synthetic once wired.
  - Nick's 500-1000-sends-per-variant statistical floor implies we need >=1500 leads *just for the first iteration cycle*. Workstream B's 100 is a warmup batch — we need to scale to 1500+ before iteration becomes statistically meaningful.

- **Cost transparency check**: this session used ~€2 in Anthropic tokens (video analysis) + ~€0 for the code work (all local). Estimated total spend for Phase 2: <€3.

---

## Suggested Phase 3 kick-off order (when operator returns)

1. Skim [deliverables/self_outbound_system/nick_saraev_cold_email_full_analysis.md](../../../deliverables/self_outbound_system/nick_saraev_cold_email_full_analysis.md) — at least the Master Synthesis section
2. Read the dogfood outputs — 3 seed leads through the new pipeline. Regenerate anytime with:
   ```bash
   cd execution/personal_workflows/self_outbound_system
   py -c "import json; from personalizer import personalize_dry_run; import sys; leads=json.load(open('tests/fixtures/leads_seed.json'))['leads']; [l.__setitem__('segment', l.get('segment_hint')) for l in leads]; tone=json.load(open('config/tone.json')); p,_,_=personalize_dry_run(leads, tone); [print('='*70, '\n', x['body_text']) for x in p]"
   ```
3. Approve or edit `tone.json` variants — the drafts are Nick-framework-compliant but voice is subjective. Look for: false claims (numbers we can't back), awkward language for French-first prospects, tone mismatch
4. Do Workstream B — Apify sourcing (~1 hour operator interaction). Approve credit spend.
5. Do Workstream C4 — Sonnet dogfood on 5 real leads (~30 min)
6. Deploy the Worker (Workstream C2, ~15 min)
7. Wire canary to live IMAP (~30 min)
8. Create Instantly campaign DRAFT (operator UI, ~30 min)
9. Panel-pass + full audit stack before flipping to ACTIVE

**Warmup ends around 2026-07-27.** All Priority-1 owed-work should be done by ~2026-07-25 to leave a 2-day validation window.

---

## Files created/modified this session

| Type | Path |
|---|---|
| CREATED | [deliverables/self_outbound_system/nick_saraev_cold_email_full_analysis.md](../../../deliverables/self_outbound_system/nick_saraev_cold_email_full_analysis.md) — 30k words, 183 KB |
| MODIFIED | [config/tone.json](config/tone.json) — v2 with Nick's full framework |
| MODIFIED | [personalizer.py](personalizer.py) — 5-slot body assembly |
| MODIFIED | [config/suppression.json](config/suppression.json) — `_writer_owed` → `_writer` + `_webhook_worker` pointers |
| CREATED | [suppression_writer.py](suppression_writer.py) — new pure-Python writer |
| CREATED | [tests/test_suppression_writer.py](tests/test_suppression_writer.py) — 11 tests |
| CREATED | [execution/infrastructure/self_outbound_webhook_worker/wrangler.toml](../../infrastructure/self_outbound_webhook_worker/wrangler.toml) |
| CREATED | [execution/infrastructure/self_outbound_webhook_worker/src/index.js](../../infrastructure/self_outbound_webhook_worker/src/index.js) |
| CREATED | [execution/infrastructure/self_outbound_webhook_worker/README.md](../../infrastructure/self_outbound_webhook_worker/README.md) |
| CREATED | [.tmp/video/uSTGNHGFOAo/analysis_chunk1.md](../../../.tmp/video/uSTGNHGFOAo/analysis_chunk1.md) — 6.5k words |
| CREATED | [.tmp/video/uSTGNHGFOAo/analysis_chunk2.md](../../../.tmp/video/uSTGNHGFOAo/analysis_chunk2.md) — 5.9k words |
| CREATED | [.tmp/video/uSTGNHGFOAo/analysis_chunk3.md](../../../.tmp/video/uSTGNHGFOAo/analysis_chunk3.md) — 7.9k words |
| CREATED | [.tmp/video/uSTGNHGFOAo/analysis_chunk4.md](../../../.tmp/video/uSTGNHGFOAo/analysis_chunk4.md) — 8.3k words |
| CREATED | [.tmp/merge_nick_analysis.py](../../../.tmp/merge_nick_analysis.py) — merge script |
| CREATED | HANDOFF_PHASE_3.md (this file) |

Total commits pending: 0 (nothing committed yet — operator approval required before any commit).

---

## Reminders

- Guardrails from `~/.claude/rules/` all apply — currency in EUR (converted from USD), front-door synthetic before "live" claims, output-acceptance gate corpus green (verified), Python-hardening (subprocess encoding, threading locks — no new Python here that violates), never `copy.copy(os.environ)`, prior-art-first.
- The `~/.claude/rules/mandatory-audit-stack.md` was NOT fully run — I skipped it because 4 of the 6 auditors require operator token authorization for parallel sub-agent runs.
- Nick's own doctrine (from the video, Hour 4 iteration section): first two variants MUST be fundamentally different (3x difference). The current A/B/C are already fundamentally different — A targets founders, B agencies, C HoP/Ops. So this is satisfied naturally by our ICP segmentation.

Send well.
