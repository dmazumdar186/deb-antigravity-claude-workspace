# Claude Code Marketing Full Course — Nick Saraev (library extract)

**Source**: "CLAUDE CODE MARKETING FULL COURSE (6 HOURS)" — Nick Saraev,
youtube.com/watch?v=yulWjh3rq28, published 2026-08-08, 6h02m49s.
**Extracted**: 2026-08-31, via 4 parallel extraction agents over the full
auto-caption transcript (2,839 segments). Timestamps `[h:mm:ss]` cite the video.
All content below is paraphrased/structured, not verbatim transcript.
Course-quoted dollar figures are kept in USD deliberately as source quotes
(per `~/.claude/rules/currency-eur.md` exception); convert before quoting to
the operator in a decision context.

**What this doc is**: the workspace's permanent record of every framework,
workflow, artifact pattern, and rule taught in the course, plus the mapping to
what this workspace already had and what was added. Implementation artifacts
created from this course are listed in §8.

---

## 1. The frameworks

### 1.1 Business pipeline + RACE [47:46–52:35]
Universal pipeline: **Marketing → Sales → Fulfillment → Admin**. The course
covers only Marketing (+ the marketing side of Sales), framed with **RACE**:
**R**each, **A**cquire (marketing) | **C**lose, **E**xpand (sales). Nick's
agency (LeftClick) redirects clients who ask for backend/admin automation to
RACE first — "dramatically better results from that ordering."

**RACE breakdown** [52:17–57:22]: under **Reach**, three areas — (a) creative
(AI images/video/audio for ads + organic), (b) copy (personalized
newsletter/marketing copy, warm audience), (c) outbound/direct-outreach copy
(cold prospecting). Under **Acquire**, three levers — (a) speed to lead
(respond in ~30s; claim: 300–400% revenue lift; case: home-services
$3M→$9M/mo), (b) booking % (shorten opt-in forms by pre-researching prospects
instead of asking), (c) follow-up/nurture.

### 1.2 The five marketing functions [1:05 roadmap; recap 5:33:04]
Nick's own enumeration, given twice (course roadmap and closing recap):
1. **Creative generation** — ads/organic images, video, audio via AI.
2. **Personalized copy** — newsletters (warm) and cold outreach, fuzzy-variable filling via research.
3. **Speed to lead** — email + SMS + voice, triggered on intent events.
4. **Data collection / tracking / dashboards** — ingestion pipeline + AI interpretation.
5. **Automated follow-ups** — bottom-of-funnel nurture/chase.

### 1.3 Bottleneck thinking [57:37–1:03:07]
Pipeline output is capped by its narrowest step (factory example: 100-unit step
feeding a 10-unit step produces 10; doubling the 100 changes nothing). Diagnose
the actual constraint first; every system in the course is "a solution to a
bottleneck," never a blanket install. Corollary used later [4:04:41]: don't
promote a skill to loop/routine without a genuine recurring need.

### 1.4 Prompt → Skill → Loop → Routine (the automation-maturity ladder) [1:03:06–1:11:45]
- **Prompt**: manual, human drives every step. For first-time process discovery.
- **Skill**: saved reusable instruction set; trigger by name. Rule [1:09:40]: "the moment you find yourself saying the same thing more than once, turn it into a skill." Skills chain into **meta-skills** (Nick's YouTube channel is run by chained granular skills).
- **Loop**: skill on a local timer (his UI's `/loop`, 1-min floor). Brittle — needs your machine on; hard to share.
- **Routine**: cloud-hosted, connector-driven, triggered by schedule / API POST / webhook. "Spend ~$1 in tokens, get ~$100 of deliverable."
- Build pattern for EVERY system: prompt → verify output quality → skill → harden by repetition → loop → routine. Always "start at the end": prove the manual output is good before automating [3:28:05] — automating a bad process just scales badness.
- **Autonomous-threshold test** [1:10:14]: before converting a frequent task to a skill, test whether it clears the fully-autonomous bar; if it can't, a human stays in the driver's seat — not everything is skill-able.
- **Best-use mapping** [1:11:26]: prompts → quick experimentation/building; skills → repeat tasks with a human still in the loop; loops → monitoring/scraping; routines → daily production.
- **Workspace mapping**: our equivalent ladder is prompt → skill (`.claude/skills/`) → scheduled task/cron (local) → deployed Worker/GH-Actions cron or Claude cloud session. Same shape; our directives layer adds a written SOP between prompt and skill.

### 1.5 Probability multiplication [1:13:05–1:15:23]
Chained AI steps multiply error: 3 steps × 0.8 reliability ≈ 51% end-to-end.
Prescription: human designs the process and judges the output; AI executes the
middle. Don't expect single-shot perfection — generate volume, curate winners.
(Matches our eval-first / output-acceptance-gate discipline: the "judge" is a
hard-failing gate, not vibes.)

### 1.6 "Don't come to AI without a process" [1:12:08–1:13:05]
Vague asks ("make me great ads") produce clarifying questions + mediocre output.
Whiteboard the process first; never let AI simultaneously choose the process,
execute it, and evaluate the result.

### 1.7 Fuzzy variables [3:20:00–3:24:52] — full definition
- **Hard variable**: raw data copied verbatim into a template (first name, city) — legacy mail merge.
- **Fuzzy variable**: raw data passed through an LLM that generates a natural-language phrase weaving the fact into the copy so it reads as originally human-written. Example: hobbies "pottery and indie films" → "saw you love pottery and indie films, warmed my heart to see that." (Source note: the course's on-screen example output actually referenced different hobbies than its input row — a source-side inconsistency; the example here is normalized to be self-consistent.)
- **Naming = spec**: long descriptive camelCase names (`shortPlausibleReasonWhyTheySignedUp`); the variable NAME is the generation instruction.
- **Length discipline**: ~10 words for reason-type, ~5 for paraphrase-type. "The fewer AI-generated words as a proportion of the email, the lower the probability anybody thinks AI wrote it."
- **Human template, AI slots**: the surrounding email is always human-written; AI never authors the whole email.
- **Distinctness**: instruct row-to-row variation in structure and word choice; two rows with similar data must not read identically; read every row, never sample.
- Implemented in this workspace: `directives/personalization/fuzzy_variables.md`.

### 1.8 Compositing vs direct-gen creative [1:56:00–2:02:36]
- **Compositing** (procedural HTML/CSS/SVG, Claude as Photoshop): ~80% usable rate, cheap, low variance — for templated/simple ads.
- **Direct-gen** (GPT Image 2, video models): ~25% usable rate, several-x cost — plan ~4x overgeneration; needed for photorealism.
- **Zone constraint** [2:18:33]: for direct-gen against a reference format, split the layout into fixed vs variable zones (logo band / negative space / product band / footer) instead of free reinterpretation — trades creative ceiling for repeatability.
- Economics [1:41:01]: ~$2/AI ad attempt vs ~$500 traditional video ad → generate many variants, let ad-platform performance pick winners, not personal taste.

### 1.9 Parallelization [4:56:34–4:59:47]
Spawn N independent sub-agents on non-conflicting slices; wall clock ≈ 2×T
instead of N×T. Costs more, individual runs fail more — acceptable because only
one of N needs to win. Demo: 5 sub-agents building 5 dashboard styles
(editorial / terminal / Swiss / dense-ops / warm-print) at once.
(Already law here: `.claude/rules/always-parallelize.md`.)

### 1.10 Iterative variant-narrowing [4:42:32–4:43:23]
Generate 5–6 design variants → pick best → spawn sub-variants of the winner →
pick → repeat ~3 rounds. Use for any design/dashboard/creative task.

### 1.11 Model escalation [4:47:19–4:48:56]
Run structuring/design decisions on a cheap model, then re-run on the top model
("assume the analysis before was by a dumber, less capable model") and compare.
High-stakes design → best model, high reasoning. (In the course's dashboard
build, Fable 5's client-centric structure beat Opus 5's funnel structure on
explicit data-shape reasoning. **Workspace override**: we skip the cheap-first
pass — per `~/.claude/rules/model-tier.md`, structuring/design decisions are
judgement work and go straight to Fable 5; a wrong cheap-pass answer is
expensive to detect later.)

### 1.12 Maintenance trio [5:35:45–5:52:11]
Frame first [5:35:48]: **maintenance** = keeping the system running;
**upgrading** = wholesale self-improvement built into every run, not a
separate manual step.
1. **Auth first**: ~70% of maintenance issues are login/credential breakage. Nick's fix — hold root credentials so the agent can self-service reauth via its browser ("debug flow"). Named trade-off: security vs maintainability. *Workspace stance: we keep per-service API keys in `.env`/cloud env instead; the debug-flow idea maps to our `/api/health` secret-presence checks, not to credential hoarding.*
2. **Self-healing** (he also calls it "self-annealing"): standing instruction in every skill/loop/routine — same error >3 times → assume the external system changed → investigate with full autonomy → fix → update the skill's own instructions with a change log. Not foolproof (a rate-limit blip can trigger a wrong self-rewrite) but beats giving up. *This workspace already runs the stronger form (self-anneal loop + anneal tool); the change-log-inside-the-skill idea is adopted in `.claude/rules/automation-boundaries.md`.*
3. **Error channel**: every production routine logs errors to a dedicated channel where the business already talks (Slack/Discord/WhatsApp) with a fixed shape: service / environment / error / count. Test with a manual sample-send first. Time-to-detect argument: a 5:59am failure caught at 6am leaves a 2-hour buffer before the 8am deliverable. *Maps to our canary/dead-man patterns; the fixed message shape is adopted.*

### 1.13 Effectiveness > efficiency [5:52:20–5:56:06]
Efficiency = fast and cheap; effectiveness = automating the right things.
Exhibit: a PE firm wanting to automate ~1h/week of relationship-building
prospecting calls — their core revenue activity — for trivial savings ("new
trade offer" meme: gain 1h/week, lose the business). Never automate the
singular activity that is the actual source of revenue.

### 1.14 When NOT to automate [5:57:10–6:01:33]
**Filter**: does the customer *feel* this process? Is a relationship at risk?
No → automate. Yes → keep the human; AI may draft, human QAs and delivers.
- OK: data entry, first-draft copy/creative, reporting mechanics, scheduling (caveat).
- NOT OK: final creative asset production (AI = ideation, human picks/polishes), bad-news delivery from reports (never auto-send a "signals" alert to a client), anything where a paying customer must feel valued (appointment-setting should feel human).
- Principle: "automation should buy you more time WITH people, not replace the time you have with people." Closing caution: "people will overautomate tremendously."
Implemented as `.claude/rules/automation-boundaries.md`.

---

## 2. Function playbook 1 — Ad creative (top of funnel) [1:15:23–2:59:15]

### Compositing pipeline ("Maker School ads" pattern)
1. Collect reference ad formats (own winners; competitors via Meta Ads Library as stand-in — "scoop and spin," never clone) into a folder of screenshots.
2. Voice-dump business context (offer, audience, angles) + references into Claude.
3. Claude scaffolds a procedural HTML/CSS/SVG template (gradient mesh, noise/grain filters, wordmark, headline, CTA).
4. Have Claude build an interactive **ad tuner** page — sliders for gradient angle/type, grain amount/size/seed/blend, font (e.g. Red Hat Display), letter spacing, padding, CTA style/copy, zoom — with **Export Settings → JSON**.
5. Tune by hand, export JSON, paste back to lock the visual profile.
6. Batch-generate (e.g. 50) variants with varied copy/CTA; iterate corrections (vary gradient angle; add multi-select + download).
7. Consolidate into a skill; re-run unmodified for another product by supplying its URL/info.
8. Escalate: daily loop (batch 20, 5:59am) → cloud routine (GitHub repo backing, Google Drive dated subfolders, shared-link folder).

### Direct-gen pipeline ("product ad gen" pattern)
Manually verify the image model can do the transformation first [2:07:02] →
convert formats (webp→png) → API key in env storage (never chat) → Claude reads
API docs, calls model directly → constrain with fixed/variable zones → 5
variants per template → HTML review app (checkboxes, download-selected) → skill
→ routine (key in the cloud environment).

### UGC video pipeline (Higgsfield)
Reference photo (Pinterest) → synthetic influencer (GPT Image 2, resemble-but-
differ) → second pass compositing influencer + real product (start frame) →
~10 script candidates, first-person testimonial voice, hand-trimmed to
duration — word-count rule: <22 words → 8s clip, ≥22 → 10s [3:01:12] → test
same prompt across parallel video models → Higgsfield MCP/CLI for direct
control → skill with human checkpoint (approve hero frames + scripts BEFORE
spending video credits), 3 candidates/script, concurrency cap ~8 jobs, cross
every influencer × every product. Scale-out proposal: N personas × N settings ×
N scripts, per-second frame-extraction vision QA to cull malformed clips, human
picks winners from survivors.

Tips: script under clip length makes models invent filler (product vanished
mid-clip) [2:57:39]; male synthetic UGC reads worse than female (training-data
gap) — overgenerate; add grain/audio/QA passes to cut the AI look; upload the
real product as a reusable "element" image rather than describing it in text,
for prop consistency across generations [2:45:05]; prefer a platform's CLI
over hand-wiring raw API calls when one exists — faster, simpler auth
[2:54:19]; correct a wrong model/parameter the moment you notice it — waiting
burns tokens on output you'll discard anyway [2:15:40].

**Workspace delta**: net-new capability → `directives/content/ad_creative_pipeline.md`
+ `.claude/skills/ad-creative/`. We already hold Higgsfield MCP experience
(veo3_1_lite free-tier path, `feedback_higgsfield_free_tier`); for the
$0-budget case, GLM 5.2 covers procedural/compositing template code (Tier 1 —
it is a text/code model, not an image model) and Gemini free tier covers
direct image generation (Tier 2).

## 3. Function playbook 2 — Personalized copy: newsletters [3:11:12–3:43:01]

Kit (ConvertKit) welcome-email flow: human-written template with 3 fuzzy slots
(`shortPlausibleReasonWhyTheySignedUp` ~10w, `shortCustomReasonWhyItsUseful`
~10w, `paraphraseChallenge` ~5w) → one-shot prompt over the subscriber sheet
(read every row, vary row-to-row, never modify source, create NEW sheet,
validate before delivering link) → preview 2+ records in the ESP → skill
querying the Kit API directly (24h new-subscriber check → generate 3 vars →
update custom fields → tag-filtered broadcast → remove pending tag = dedup-safe
send) → routine. Em dashes removed from templates ("kind of AI-y").
Never test against real subscriber emails with fake data — protects
deliverability [3:40:23]. Demo API keys named distinctly and rotated after use.

**Workspace delta**: methodology → `directives/personalization/fuzzy_variables.md`.
We have no Kit; nearest rails are Gmail SMTP + Instantly. The tag-pending →
send → untag dedup shape maps to our KV-sentinel idempotency pattern.

## 4. Function playbook 3 — Cold email + fuzzy variables [3:43:01–4:06:22]

Economics: templated ≈1–2% reply; light personalization ≈5% (2.5x, flows
straight to revenue); best combined campaign >20%. Deliberately casual,
slightly imperfect, lowercase copy reads human (recipients associate perfect
grammar and em dashes with AI spam) [3:50:34].

Pipeline: proven human-written template with `{{curly}}` fuzzy slots
(`{{thing in common}}`, `{{qualified <ICP>}}`) → test generation on 5 sample
leads (tell Claude NOT to live-research demo leads) → heed the compliance flag:
unsubstantiated numeric claims risk account suspension / deceptive-claims
exposure — numbers must be case-study-backed → enrich every row, trim schema to
the fields the campaign needs → skill: input raw lead list, output enriched
list → extend to own sourcing via the Apify-hosted scraper MCP with dictated
role filters (founder/CEO/co-founder/owner/partner) → **ICP self-check loop**:
scrape 100, sample 20, require ≥15/20 in-ICP else auto-redo with adjusted
filters (live run converged 9/20 → 9/20 → 15/20 → 19/20) → import to Instantly,
preview merge rendering on multiple leads before sending → routine only if a
daily need exists (Nick declined — bottleneck thinking).

**Workspace delta**: Instantly rails, casualize-names, classify-leads,
personalization modules already exist. New: fuzzy-variable methodology
(directive above), ICP self-check loop → `directives/gtm_icp_filters/icp_self_check_loop.md`.

## 5. Function playbook 4 — Speed to lead [4:06:22–4:36:37]

Lead = money at an exchange rate; treating leads better (speed, personalization)
improves the rate without buying more leads. Mindset-decay: ~10min typical
response vs ~30s with S2L. Architecture: any intent event (form fill, call,
email, SMS) triggers within ~5–30s: (1) AI-personalized SMS (160-char budget
with safety margin for long names), (2) AI-personalized email (subject
"Re: <first name> <service>", body = paraphrase of their request ≤10–15 words +
"call you in 5 minutes" + persona signature), (3) optionally auto call-merge
(third-party number rings lead + rep simultaneously; first to answer connects).
Demo build: HTML form artifact + Formspree (free form→email) → Gmail connector
polling + dedup ("seconds since sent") → dictated email/SMS templates ("don't
stray from this template") → skill → routine triggered by API POST with bearer
token (event-driven beats polling). **Pacing**: instant (≤5s) reads fake —
space ~30s, allow small human imperfections ("just got back to the office,
give me 3 minutes") [4:20:56]. SMS rails: Qo (ex-OpenPhone) or Twilio; both
need US A2P 10DLC registration (2–14 days, can be rejected).
Scoped out by Nick: dispositions/CRM follow-up handoff (sales course later).

**Workspace delta**: net-new → `directives/personalization/speed_to_lead.md`
(provisioning-gated: no Formspree/Qo/Twilio accounts yet; our stack equivalent
is CF Worker webhook + Gmail poll fallback — the dual-path reply-detection
pattern we already run).

## 6. Function playbook 5 — Dashboards + follow-ups [4:36:37–5:33:38]

### Dashboards
"Dashboards are just websites" — build as a glorified website fed by an
ingestion pipeline (connectors pulling Meta/GA4/Stripe/CRM/email into one
source of truth; replaces agency "report day"). Process: assemble data (CSVs
fine) → structuring prompt for candidate page layouts → model-escalate the
structure decision (Fable 5 high reasoning chose client-centric over funnel
because anomalies were client-scoped and coverage gaps punish shared pages) →
scaffold pages (Overview / Performance / Client / Channels / Sales / Signals)
→ "data on the page first, then skin it" → 5 parallel sub-agents render 5
styles, all required to surface the SAME anomalies (comparability constraint)
→ variant-narrowing rounds → deploy (Netlify MCP, password-protected).
Signals built in: threshold anomaly detection (~5x jump/drop), CPL spike
($100→$1,100), rep win-rate vs team, client health score, funnel dead zones.
Cost exhibit: agency-analytics-class dashboard over ~50–100k rows ≈ $15 in
tokens. **Never auto-send the bad-news signals to a client** (see §1.14).

### Bottom-of-funnel follow-ups (ClickUp invoice-chase demo)
Follow-up loop: (1) query CRM + read conversation history, (2) check trigger
conditions, (3) pick from a pre-built **template pool** (10 soft one-line
nudges, varied subjects, no em dashes, no invoice numbers, fixed sign-off —
"template pool over raw generation": fewer catastrophic screw-ups), (4) send.
**Cadence**: daily run; act on 1/2/3/7/14/21/28/56/84 days outstanding; fill
merge variables with real values (never literal "first name"); check email
history so no template repeats; never two identical templates back-to-back;
84-day ceiling = stop chasing. Trigger taxonomy: no reply post-proposal /
ghosted question / "follow up next month" deferral / warm signal (multiple
opens). **Opt-out handling is mandatory**: detect stop requests, flag the CRM
record (chase stage → closed + note + comment audit trail), halt sends — and
**live-test the opt-out path with a fabricated stop-request before production**
[5:27:48]. Gmail connector gotcha: exposes only create_draft/update_draft —
verify a connector's actual tools before designing around it [5:21:00]; send
required a custom Gmail API OAuth build, tested against own inbox first.
ROI framing: follow-up alone ≈ +20–30% revenue; compounding stage lifts
multiply.

**Workspace delta**: cadence SOP + opt-out testing →
`directives/personalization/automated_followups.md`. Our existing Day-N
follow-up KV+cron pattern gains the threshold ladder, template-pool rule, and
the fabricated-stop-request test.

---

## 7. Claude Code product notes (his UI ≈ our stack)

The course runs on the Claude desktop/web app. Feature ↔ workspace mapping:
skills ↔ `.claude/skills/`; loops ↔ `/loop` / scheduled tasks; **cloud
routines ↔ claude.ai/code cloud sessions + connectors + env vars**
(`directives/infrastructure/claude_code_web.md` — our migration landed
2026-08-31, same architecture); connectors/MCP ↔ `.mcp.json` + custom MCP;
local env credentials ↔ `.env` (his: model cannot read keys back — same
prompt-injection defense rationale as our never-secrets-in-chat rule);
sub-agent spawning ↔ Agent tool / Dynamic Workflows; `/usage` ↔ cost hygiene;
context guidance: keep under ~500k of Sonnet 5's 967k window [40:08]; voice
dictation ≈ 3–4x faster input; `/btw` side-chats; fork/transcript/diff viewer;
effort slider; fast mode (~2x speed, Fable 5); usage credits top-ups
(his dashboard build: ~$12–13 USD in Fable 5 credits).
Permission modes incl. Bypass Permissions — his rule: never for anything
touching credentials/security, stay in the loop [27:30].

Local↔cloud credential boundary (stated twice [2:27:05, 3:41:23]): local env
vars do NOT carry into cloud routines — provision the cloud environment
separately. Identical to our claude.ai/code env-var setup step.

Thread-continuity tactic [3:39:49]: when a credential/connector pivot forces a
new thread, paste the entire prior conversation in, then ask for "code review
first, then a read-only verification pass" before trusting the migrated
implementation. (Workspace equivalent: conversation-memory RAG + the audit
stack — we lean on those instead, but the review-after-pivot habit carries.)

---

## 8. Gap analysis → what was implemented (2026-08-31)

| Course capability | Workspace before | Action taken |
|---|---|---|
| Five-functions / RACE framing | implicit, scattered | this doc (§1.1–1.2) |
| Prompt→skill→loop→routine ladder | equivalent ladder existed unnamed | codified §1.4 |
| Ad creative (compositing + direct-gen + UGC video) | none (only thumbnails/design-website) | **NEW** `directives/content/ad_creative_pipeline.md` + `.claude/skills/ad-creative/` |
| Fuzzy variables | ad-hoc icebreakers/personalization modules | **NEW** `directives/personalization/fuzzy_variables.md` |
| ICP self-check-and-retry | manual QA habit only | **NEW** `directives/gtm_icp_filters/icp_self_check_loop.md` |
| Speed to lead (email+SMS+voice) | none | **NEW** `directives/personalization/speed_to_lead.md` (provisioning-gated) |
| Follow-up cadence + opt-out testing | Day-N KV+cron pattern | **NEW** `directives/personalization/automated_followups.md` |
| Dashboards multi-variant build | yoga_jitendra experience, impeccable skill | doc §6 (process codified; no new artifact needed) |
| When-not-to-automate + self-healing + error channel | self-anneal + canary rules (stronger in parts) | **NEW** `.claude/rules/automation-boundaries.md` |
| Newsletter (Kit) pipeline | no Kit account | doc §3 only; adapt to Instantly/Gmail if needed |

**Provisioning gaps (external accounts we do not hold)**: Kit, Formspree,
Qo/OpenPhone or Twilio + A2P 10DLC, GPT Image 2 API budget, Meta Ads Library
scraping cadence. Each directive flags its own gaps; none block the
non-sending parts of the pipelines.

**Ambiguities inherited from auto-captions** (flagged, unresolved): the
lead-scraper branding ("Amplify"/"Ampify"/Apify actor), SMS platform spelling
("Qo"/"Kuo"/"Quo"), video model names ("Cance"≈Kling?, Gemini "Omni"≈Veo?),
his $20 vs $24-CAD plan tier. Verify against the products before building on
those specifics.
