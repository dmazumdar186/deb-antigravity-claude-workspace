# Instantly Campaign Setup Runbook — self_outbound_v2 (D-1)

**When**: 2026-07-26 (D-1), after all 30 mailboxes are connected + vetted
**Duration**: ~30 min operator UI + Claude API pre-population
**Goal**: `self_outbound_v2` campaign in DRAFT, ready for 2026-07-27 flip to ACTIVE

---

## Prerequisite checks (Claude runs, operator verifies)

Before starting, all of these must be TRUE:
- [ ] All 30 mailboxes connected to Instantly (green warmup indicator)
- [ ] ≥27 of 30 mailboxes passed mail-tester ≥8 (per Section 6 verification)
- [ ] `docs/legal/lia_paris_founders.md` signed + committed
- [ ] Cloudflare Worker deployed + registered with Instantly webhook
- [ ] Front-door synthetic (`tests/front_door_self_outbound_system.py`) returns 0
- [ ] tone.json v3 committed (unverifiable claims killed, spintax added)
- [ ] First 100 personalized emails generated + operator spot-check complete

---

## Step 1 — create the campaign in Instantly UI

1. Login: https://app.instantly.ai
2. Left nav → **Campaigns** → **New Campaign**
3. Name: `self_outbound_v2 — Paris founders & agencies (2026-07-27 launch)`
4. Duplicate-detection: enable at campaign level (Instantly's built-in)
5. Save DRAFT

---

## Step 2 — sequence builder (Claude drafts, operator reviews)

**Step 1 email** (immediate on lead upload):
- Subject: use the spintax pattern from `config/tone.json` → `subject_line_spintax.en` (or `.fr` based on lead's language). Paste directly:
  ```
  {{RANDOM | {{firstName | there}} — one question | one thought for {{companyName | you}} | worth a look, {{firstName | there}}? | 90 seconds of your time? | one idea for {{companyName | you}} | small win at {{companyName | your team}} | curious about {{firstName | one thing}} | one quick note | 2 minutes? | idea for {{companyName | your roadmap}} }}
  ```
- Body: use one of 3 variants (A / B / C) from `tone.json`. Load pre-generated personalized bodies from `.tmp/self_outbound/personalized_batch_YYYY-MM-DD.json`.
- Tracking: **DISABLE** open tracking (Google flags open pixels as spam signals in 2026). Click tracking: leave ON for Cal.com link only.

**Step 2 email** (delay 4 days):
- Subject: rotate — different pattern from Step 1. Use `follow_up.f2_subject_rotation` list.
- Body: use `follow_up.f2_human_pings` variants. Short, plain, no repeat of the offer.
- Only fires if Step 1 got no reply.

**Step 3+**: **NONE**. Nick's doctrine + our LIA commit to max 2 touchpoints.

---

## Step 3 — sending schedule

- **Days**: Monday to Friday only
- **Time window**: 09:00 to 17:00 Europe/Paris (recipient-local)
- **Time zone**: recipient timezone (Instantly auto-detects); default to Europe/Paris for missing
- **Send throttle**: 15/day/mailbox for first 5 days, then ramp to 30/day
- **Random delay between sends per mailbox**: 3-8 minutes (Instantly setting; humanization)
- **Weekend pause**: yes
- **Bank-holiday pause**: manually pause via Instantly UI for French national holidays (14 July, 15 August, 1 November, 11 November, 25 December, 1 January, Easter Mon, etc.)

---

## Step 4 — mailbox rotation

- Assign ALL 30 mailboxes to this campaign
- Rotation: **round-robin, equal weight**
- Per-mailbox daily cap: 15/day (week 1) → 30/day (from week 2)
- If a mailbox is auto-paused by Instantly (warmup collapse, bounce spike, spam complaint): campaign continues on remaining mailboxes

---

## Step 5 — hard-stop thresholds (safety gates)

Configure in campaign settings:
- **Bounce rate threshold**: 3% (rolling 7-day). Action: **PAUSE campaign** + email operator
- **Spam-complaint threshold**: 0.5% (rolling 7-day). Action: **PAUSE campaign** + email operator
- **Unsubscribe rate**: no auto-pause (unsubs are expected)
- **Reply-rate anomaly**: if reply rate = 0.0% at 500 sends → send operator alert (not auto-pause)

**Screen-capture confirmation** of each threshold setting. Save to `.tmp/self_outbound/instantly_config_YYYY-MM-DD.png`.

---

## Step 6 — upload first-week's 100 leads

- Source: `.tmp/sourced_leads_batch_001.json` (66 real leads already sourced) + top-up 34 more if needed
- Filter through ICP filter first (auto-run)
- Personalize each via `personalizer.py` (auto-run)
- Upload as CSV via Instantly UI OR via Instantly API (Claude prefers API for reproducibility)
- Verify Instantly's built-in de-dup catches any lead already in the workspace

---

## Step 7 — test-to-self synthetic (mandatory)

Before flipping DRAFT to ACTIVE:

1. Add operator's personal Gmail as a "lead" in the campaign (edit the row, mark as internal-test)
2. Trigger the campaign to send ONE email to operator's Gmail from EACH of the 30 mailboxes (30 test sends)
3. Operator verifies:
   - [ ] All 30 land in **Inbox** (not Promotions, not Spam)
   - [ ] Sender name is `Debanjan Mazumdar` (not any Stacy@123click variant)
   - [ ] Subject renders correctly (spintax picked one, not raw `{{RANDOM|...}}`)
   - [ ] Body renders correctly (no broken merge fields like `Hi , I was thinking`)
   - [ ] Cal.com link is clickable
   - [ ] Unsubscribe link is present and clickable
   - [ ] Footer includes postal address + sender name + prodcraft.fyi

If ≥27/30 land in Inbox with everything correct → greenlight campaign flip.
If <27 → identify failing mailboxes, request Primeforge/Litemail replacements, delay launch.

---

## Step 8 — DRAFT → ACTIVE (D-0)

**When**: 2026-07-27 morning, after operator confirms all preflight green.

Operator:
1. Login: https://app.instantly.ai
2. Campaigns → `self_outbound_v2` → click **START** button
3. Confirm the modal
4. Verify status changes from DRAFT to ACTIVE

Claude auto:
- Monitor first-hour metrics via Instantly API
- Send Telegram alert on any threshold breach (bounce, spam)
- Report first-day summary at 20:00 Paris

---

## Rollback (if D-0 goes wrong)

Immediately use `docs/runbooks/instantly_kill_switch.md` — pause the campaign. Investigate. Fix. Do not restart until root cause is identified.
