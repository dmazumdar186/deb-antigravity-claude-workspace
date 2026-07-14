# Phase 2 Handoff — self_outbound_system_v2

**Written**: 2026-07-13, end of Phase 1
**Target start**: any time from now through 2026-07-27 (day 14 = warmup ends)
**Session model**: Opus 4.8 (orchestration) with Sonnet 4.6 sub-agents per workspace policy

---

## Frozen state (Phase 1 closed on 2026-07-13)

Live production infrastructure:

| Layer | State | Notes |
|---|---|---|
| Domain `debanjanm.com` | Live, 301 → prodcraft.fyi | Porkbun URL forward (id 29860761) |
| Google Workspace Business Starter | Live | Primary user `debanjan@debanjanm.com` |
| SPF / DKIM / DMARC / MX | Live | All in Porkbun DNS |
| Mail-tester baseline | 9.5/10 | Locked baseline 2026-07-13 |
| Instantly Emails Starter (EU DC) | Live, warmup ON | 10 warmup/day + slow ramp + read emulation |
| Cal.com booking | Existing 30-min link + UTM `?utm_source=outbound&utm_campaign=debanjanm-outbound&utm_medium=email` |
| Telegram bot `@debanjanm_outbound_bot` | Live | Token + `chat_id 1221087464` in `.env` |
| Apify Free tier | Live | Token in `.env` as `APIFY_TOKEN`, $5/mo credits |
| **Total cost** | **~€96/mo TTC** | Assumes no French VAT number |

Warmup runs autonomously through **day 14 = ~2026-07-27**. Do not touch Instantly settings, do not send real mail from `debanjan@debanjanm.com`, do not create a live campaign in Instantly.

---

## Files to read on session entry (in this order)

1. `directives/personal_workflows/self_outbound_system.md` — full pipeline spec (Blueprint A2)
2. `execution/personal_workflows/self_outbound_system/` — the entire scaffold (18 files, ~2281 LOC)
3. `execution/personal_workflows/self_outbound_system/config/tone.json` — current 3-variant email copy (A/B/C) — this is what Phase 2 rewrites
4. `execution/personal_workflows/self_outbound_system/config/icp.json` — 3 ICP segments + anti-ICP rules
5. `execution/personal_workflows/self_outbound_system/tests/acceptance_corpus.json` — 20 known-bad + 12 known-good regression corpus
6. `execution/personal_workflows/self_outbound_system/landing_page/` — scaffolded but NOT deployed (operator dropped scope; Porkbun URL forward serves the domain now)
7. `.env` — has `INSTANTLY_API_KEY`, `APIFY_TOKEN`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `PORKBUN_API_KEY`, `PORKBUN_SECRET_KEY`, `ANTHROPIC_API_KEY`
8. `legal/lia.md` — scaffolded but not enforced; operator dropped legal scope on 2026-07-13. Keep the file for future re-enable, but do not depend on it in the campaign.

---

## Phase 2 objective

Prep an Instantly campaign that is ready to flip from DRAFT to ACTIVE on day 14. Three parallel workstreams.

### Workstream A — Rewrite `config/tone.json` A/B/C variants using Nick Saraev's cold-email framework

**Task**: Distill the best-of-the-best from Nick Saraev's "The Definitive Guide to Cold Email Copywriting" (transcript at end of this document). Apply to our 3 current A/B/C variants.

**Distilled principles rubric** (verify against transcript below):

**7 psychology-of-yes principles**:
1. **Give first** — start with concrete value that costs the recipient nothing (a spotted misconfiguration, a 1-line insight, a link to a demo)
2. **Micro commitments** — start with tiny ask, escalate. Never ask for the meeting in message 1 without giving first
3. **Social proof** — SPECIFIC numbers + matched reference group ("I did this for a Paris seed-stage founder last month" beats "I've worked with many clients")
4. **Authority** — hyper-relevant expertise, no hedging ("I could probably help you" is banned; "I built X for Y and here's how it applies to you" is preferred)
5. **Rapport** — one shared-context line (Paris, PM, fractional, ex-companies overlap, etc.)
6. **Scarcity** — REAL constraints only, tied to your capacity ("I can take one more build this month" not "limited spots")
7. **Shared identity** — subtle in-group language matching recipient's world (SaaS founder vs agency owner vs HoP language differs)

**3 outbound components**:
1. **Clear goal in ONE sentence** — pick: reply / asset watch / book call / buy. For us: **book Cal.com 30-min call**
2. **Frame like human 1-to-1 comms** — kill "hope this finds you well", kill illustrious signatures, use "I" never "we", short + casual + slightly imperfect. Text-message test: would a friend think this was personal?
3. **Iterate on data, not gut** — target 500+ sends per variant to get statistical significance; kill bottom, evolve from top

**4-step formula (personalization / who / offer / CTA)**:
1. **Personalization** (2 sentences MAX, 1 ideal) — highest ROI slot in email; must NOT signal selling; must be short + informal (long = fake); test: "would a real person send this?"
2. **Who** — one line, no fluff, no titles-in-signature theater
3. **Offer** — concrete, quantified, non-BS ("fixed-price EUR 1-2.5k AI builds, 1-2 weeks" beats "AI consulting services")
4. **CTA** — ONE action, minimize steps ("2:15pm today at [Cal.com link]?" beats "would you like to book a call?")

**Rewrite the 3 variants in `config/tone.json`** so each:
- Has a personalization opener that mines a specific fact per lead (research signal from Apify — recent hire, funding round, product launch, blog post, LinkedIn post)
- Uses the give-first principle (not "we help X do Y" but "I noticed [specific thing] on your [asset] — here's a 30-sec fix / here's how a similar setup won us Z")
- One social proof line with a real number and matched reference group
- One offer line (fixed-price + duration + outcome)
- One CTA with a specific time proposal (not a vague "let's chat")
- No corporate signals; ends "Debanjan" with maybe a "Sent from mobile" trick for perceived authenticity
- Under 100 words total per email

Save the rewrites in `config/tone.json` (overwrite in place, git tracks history). Run the acceptance corpus after — 0 regressions allowed.

### Workstream B — Source first 100 leads

1. In `execution/personal_workflows/self_outbound_system/sourcer.py`, wire the Apify LinkedIn Sales Navigator actor (search: Paris + Ile-de-France, 3 ICP-segment matches from `icp.json` — seed founders, SMB agency owners, HoP/ops leaders at Series A-B)
2. Run through `enricher.py` (add domain check, catchall check)
3. Run through `icp_filter.py` (verify 0 leaks against acceptance corpus)
4. Save output to `.tmp/self_outbound_system/leads_batch_001.json`
5. Sanity-check 10 randomly sampled leads by hand — do they fit the ICP? If >=8/10 match, greenlight. If <8/10, tighten `icp.json` and re-run.

### Workstream C — Wire deferred Phase 4 pieces

Per the directive changelog + earlier P0/P1 audits:
1. **`webhook_receiver.js`** — Cloudflare Worker that receives Instantly webhooks (reply-received, campaign-bounced, unsubscribe) and writes to `config/suppression.json` + fires Telegram alert
2. **Suppression writer** — the writer side of `_writer_owed` in `config/suppression.json`
3. **Real mail-tester canary** — `canary.py` currently mocked; wire to real mail-tester API (or scripted send via Gmail API + parse response)
4. **Real Sonnet eyeball** — one manual dogfood run of `personalizer.py` on 5 real leads to confirm output quality (~EUR 0.02)

Each of these is 1-2h. All are pre-live prep; none affect warmup.

---

## Guardrails (non-negotiable)

- Read `~/.claude/rules/mandatory-audit-stack.md` — before declaring Phase 2 "done", run all 6 auditors in parallel per that rule
- Read `~/.claude/rules/panel-pass.md` — 4 lenses before any "shipped" claim
- Read `~/.claude/rules/output-acceptance-gate.md` — every rewrite must re-pass `acceptance_corpus.json` (20 rejects still reject, 12 accepts still accept)
- Read `~/.claude/rules/currency-eur.md` — all user-facing prices in EUR
- Read `~/.claude/rules/environ-not-copy-copy.md` — never `copy.copy(os.environ)`
- Read `~/.claude/rules/prior-art-first.md` — before writing any new API integration
- Read `~/.claude/rules/front-door-synthetic.md` — before any "live" claim
- Do NOT deploy the landing page (operator explicitly dropped this scope on 2026-07-13)
- Do NOT touch anything under `execution/infrastructure/api-proxy/` or any AM-locked path (see `CLAUDE.local.md`)
- Do NOT paste secrets in chat; append to `.env` instead
- Do NOT send real email from `debanjan@debanjanm.com` — warmup only until day 14
- Do NOT create a live Instantly campaign — draft state only

---

## Success criteria for Phase 2

- 3 rewritten variants pass the acceptance corpus with 0 regressions
- 100 leads sourced, 100% pass ICP filter (no leaks against corpus), >=80% pass operator eyeball sanity
- Instantly campaign in DRAFT with 20/day cap, Europe/Paris timezone, Mon-Fri 09:00-18:00, opens+clicks OFF
- Cloudflare Worker webhook receiver deployed and receiving Instantly test webhooks
- Real Sonnet dogfood on 5 leads shows human-passing output
- Handoff-ready state: one operator click flips draft to active

After success, write a Phase 2 to Phase 3 handoff (canary week: 5/day sends starting day 15, ramp to 20/day by day 21).

---

## Notes to the future you (from current me, 2026-07-13)

- Phase 1 took ~8 hours with lots of live UI-drift issues (Instantly UI didn't match my training data — I had to fetch help.instantly.ai docs mid-flow). Expect the same for the Instantly campaign-builder UI in Phase 2. Do not fabricate UI, fetch docs.
- The operator explicitly told me "us it and don't ask for HITL unless absolutely needed" for Porkbun DNS. Same energy applies to Apify actor runs, Instantly API, etc. — use the APIs, only ask when literally blocked.
- The operator's brief is COMMERCIAL: find clients. Ignore admin/legal (no SIRET, no LIA, no postal address footer — operator dropped this scope). Focus on deliverability + copy quality + booking conversion.
- The operator prefers full URLs pasted (not "click here" or "go back") — always give absolute clickable URLs.
- The operator prefers parallelism — run parallel tool calls always.
- End-of-Phase-1 secret rotation is queued (Telegram bot token + Apify token were pasted in chat during Phase 1). Rotate via BotFather `/revoke` + Apify console before flipping live campaigns.

---

## Nick Saraev transcript — "The Definitive Guide to Cold Email Copywriting"

**Source**: pasted by operator 2026-07-13 from a Nick Saraev video (Left Click Media). Coverage below is partial (through Personalization Techniques section) due to the paste truncating at ~50k chars. If more depth is needed, ask operator for the video URL and rerun the `youtube-video-analyzer` skill. this is the video link https://www.youtube.com/watch?v=uSTGNHGFOAo&t=5s , analyze this video, every uttered character, syllable, word, this has to be leveraged 100% in this project, this entire project is this 3:59:11 long video, this is the core.

### Section 0:00 — Introduction

Nick's credentials: 10 years outbound sales, ~$15M generated for self+clients, runs a $4M/yr profit business, teaches 2,000+ community members. Course goal: convince a stranger with no pre-established trust to buy something. Sections: (1) psychology of yes, (2) 3 components of successful outbound, (3) 4-step copywriting framework, (4) offers, (5) 10 live outbound roasts + rewrites, (6) per-platform optimization (email/LinkedIn/X/IG/iMessage), (7) subject lines + follow-ups + iteration, (8) AI module, (9) advanced "grey hat" techniques.

### Section 4:00 — The 7 Psychology Principles (Cialdini + Nick)

Framing: everything empirically documented; Nick has behavioral neuroscience degree. Reference: Cialdini's "Influence".

**1. Give First**
Restaurant breadmints. Costco samples. Momentary sense of obligation lowers resistance and disarms skepticism. In outbound: start by giving something small (insight on landing page misconfig, spotted issue costing them $10-20k/mo, "here's how to fix" — no ask). Ask is inferred. Positive value assigned without transactional negatives. Very powerful. Every outbound in current year must include something you give so recipient feels they got value in exchange for attention.

**2. Micro Commitments**
Sense of increasing escalation. Don't jump to "pay me $4,000 now." Start with "watch this custom video I made for you — 1 minute, if not valuable message me to screw off." If they watch and like → escalate to longer video → phone call → video call → close. Every small agreement makes the next slightly larger one feel good. Study cited: series of small "yes" questions ("is your name Bob?" "do you live in X?") massively raises probability of yes to the ask.

**3. Social Proof**
Humans are herd/consensus animals. Show or tell others taking the action you want. Best modern outbound makes this a throwaway line, not a bragging list. **Use very specific numbers**. Concrete data (names, results, counts) is much more powerful than "a lot of people have signed up." **Match the reference group**: if pitching B2B SaaS, cite B2B SaaS proof, not "I helped a freelance dog walker." Vin diagram overlap between your proof and prospect's characteristics/business/ICP matters. Three tactical checks: (a) show others taking action, (b) use specific numbers, (c) match the reference group.

**4. Authority**
Demonstrate hyper-relevant expertise via credentialism, renowned accomplishment, or in-writing confidence (no hedging every 5 seconds). "I could absolutely 100% help you. I'm very confident because I just helped XYZ do this before" (combines authority + social proof). Match credibility to ICP: behavioral-neuroscience angle didn't land with blue-collar SMBs in Surrey; "I'm a Google Partner" did. Easy authority sources: free partner programs, incentive programs, easy-to-get certifications.

**5. Rapport**
Find shared context: ethnic, cultural, career, hobby (Yorkshire terriers!). Be super specific. **Match tone** — this is huge. Explicit: "Hey how's it going." Implicit: mirror communication style, message lengths, punctuation. Pitching SF VCs in 2022 = use lowercase (in-group signal). Anything that pushes recipient to think "we could be at a bar hanging out casually."

**6. Scarcity**
Limit availability (# things you have to give) OR create time pressure (proposal expires end of week). Make constraints REAL (fake constraints trip BS detectors). Genuine ones: your own personal capacity, your schedule, admitting fault ("I'm juggling a few client projects, I need to make sure I have time for all of them"). Least commonly used of the 7 principles.

**7. Shared Identity**
Common ground beyond rapport: industry values, political/cultural/ethnic values, shared struggle/hardship (inspirational business-owner arcs). Mirror tonality + length + in-group language. Highlight shared struggle if authentic.

Meta note: don't memorize these. Recognize them. The rest of the course is "sheer rote repetition" applying and watching Nick apply.

### Section 18:37 — 3 Components of Great Outbound

**1. Establish clear goals**
Most people miss this. B2B goal is usually money (short-term close or long-term awareness → funnel → close). Assign KPIs.

**2. Build the right frame**
Cold email frame is one-to-one comms, not corporate. Some niches need a specifically non-highbrow frame. Depends on location, ICP, language cultural norms.

**3. Iterate**
Great outbound isn't one-shot. 3.5% reply rate → tweak → 4.5% → 5% → 8% → 10%. Data science game.

Details on each:

**Goal-setting details**:
- Nick treats every single message as its own self-contained campaign (can strip away all others, that one should still do the job)
- Options for goal: reply / watch something (asset click) / book a call / buy
- Reply = easy, low ask
- Watch = middle ask, click through to asset
- Book call = big ask, closer to actual outcome
- Buy = golden grail, rare
- Nick's usual: **reply / asset watch / book call**. Rarely buy. No pricing in email typically.
- Goal drives copy. If goal = reply, write vague. If goal = book call, minimize steps: "Can I ring you at 2:15? Your number is X. Cool?" — one CTA, all info in email
- **More steps = worse performance**. Leads leak, prospects leave, grandmas pass away, they're on 2-week vacation. You're not the priority.
- If you can't describe your goal in ONE sentence, you're not ready to write the campaign

**Frame details**:
- Cold email frame = 1-to-1 comms, not corporate. Everything else you learn in this course goes to hell without this.
- Get the 7 principles on paper by writing as if you're writing just to them (even though it's a template)
- **Text-message test**: if a friend saw you typing this, would they think it's personal or a mass email? Optimize for personal.
- Go through your own phone/email and mirror how you write to trusted-but-not-crazy-close people.
- **Kill corporate signals**: no "hope this finds you well", no illustrious Dr. Sarif signature block. Use "I", not "we". "I help you do X" not "we help people do X."
- Short, casual, slightly imperfect. Real person having a conversation.
- **AI-era trick**: intentionally include small "imperfections" so recipient thinks "he wrote this on his phone." Include "Sent from my iPhone" / "Sent from Android" at the bottom.
- Big test: if I read this back and someone sent it to me, would I think spam-blast or personal?
- P2P = player-to-player, person-to-person. Not company-to-facelessdollarsigns.

**Iteration details**:
- Scientific method: hypothesis → send → measure → apply feedback
- Not 1 email to 1 person; treat as science experiment. Send 500-1000 for stat significance.
- Measure: open rate, reply rate, booked-call rate, proposal-sent rate, product-purchase rate. Build a full funnel with LTV tied to campaign.
- Kill losers fast. Write new variants based on top performer. Test again.
- **Data over gut**. Nick has written "no way this works" campaigns that hit 15% reply rate and generated hundreds of thousands.
- **Stated preference vs revealed preference**: customer says one thing, behavior shows another. Optimize for behavior.

### Section 34:34 — 4-Step Copywriting Framework

The formula that generated $15M. Not the best possible on earth, but Nick's proven one for 2,000+ students.

**Step 1: Personalization**
- Highest ROI place in the whole email — the only place ALL readers actually read
- Email dropoff is nuts: word 1 = 100% readership, word 5 = 50%
- Hook attention with extraordinarily personalized-seeming line
- Composition: greeting + observation/thing-in-common + segue into pitch
- Handles rapport principle + in-group signal
- **CRITICAL**: cannot signal selling
- Point: sneakily + cleverly evade sales radar. Make reader think "wow, this person actually looked at my stuff — read my blog, watched my masterclass, read my book, followed me on LinkedIn."
- **Rule**: short + informal. Long personalizations feel fake. Nick's rule: 2 sentences MAX, 1 sentence ideal.
- Test: would a real person send this? Yes → strong opener. No → LLM slop, restart.
- (Section truncated in operator's paste at this point — full continuation would cover Who / Offer / CTA in same depth.)

### Sections NOT captured (in operator's paste due to 50k truncation)

- Full Step 2 (Who am I)
- Full Step 3 (Offer construction)
- Full Step 4 (CTA)
- Offers deep-dive (constructing something that sounds good without sounding too-good-to-be-true)
- 10 live outbound roasts + rewrites (the meat + potatoes per Nick)
- Per-platform optimization (email, LinkedIn, X, Instagram, iMessage)
- Subject lines section
- Follow-ups section
- Iteration deep-dive
- AI module
- Advanced grey-hat techniques

If Phase 2 needs the missing sections, ask operator for video URL and rerun `youtube-video-analyzer`.

---

## Suggested Phase 2 kick-off order

1. Read all files in "Files to read on session entry" list
2. Run `pytest tests/` in the scaffold — confirm no regressions from Phase 1 changes
3. Start Workstream A (rewrite tone.json variants) — dogfood on 5 mock leads with real Sonnet call
4. Start Workstream B in parallel (Apify sourcing)
5. Workstream C after A + B produce first outputs
6. Panel-pass + full audit stack before "done"
7. Write Phase 3 handoff

Good luck. Send well.
