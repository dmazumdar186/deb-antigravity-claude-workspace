# lemo-opuscar in campaigns: what it can and cannot do

lemo-opuscar is style guides plus tools: an AI agent writes a new animated film in code each time, with synthetic voice, sampled score and checks. It suits one hero film, not volume. Measured: one film took 49 minutes of agent time. A content-swap variant of a finished film (`--q content=…json`) needs about 6.5 minutes of machine time, but is untested. **Token cost is unknown: it was never logged.**

## 1. Use cases

| Use case | Fit | Why | Cost per asset | Human gate | Risk |
|---|---|---|---|---|---|
| Hiring / ABM film, one top account | good | One viewer who matters; their public data; the look is the point | 30–60 min agent (49 measured) | Fact sheet sign-off, final watch | Gimmick past 45 s; reusing AlumnForce material |
| Per-account film in cold email (Instantly) | limited | Video doesn't embed: poster or GIF linking to a hosted MP4. Per segment is fine; per prospect, a Loom wins | about 6.5 min machine per variant (untested), plus a fact sheet | Fact sheet per account, 3-min watch | Spam perception, deliverability |
| LinkedIn native video, 1080×1350 | good | `--size` renders 4:5; captions-first styles work sound-off. Author for the feed, don't crop the 16:9 film | 30–60 min agent | Final watch, platform AI label | Reads as "AI-made" |
| Paid ad creative | limited | One hero ad per angle; volume belongs to `ad-creative` | 30–60 min agent | Claims in FACTS, AI disclosure | Undisclosed AI claims |
| CS: per-school data-health film | good | The analysis is the cost; the film is nearly free on top and shows the trust layer only AlumnForce holds | template 30–60 min, then variants (untested) | Per-school fact sheet, final watch | Stale numbers broadcast; per-tenant leak |
| CS: profile-update teaser for alumni | good, with consent rules | Ends on "Confirm / Correct", so the film refreshes the data | as above | Legal review, school sign-off | Feels like surveillance; one French voice |
| CS: fundraising / dues | limited | Annual report only; every figure needs a FACTS file | 30–60 min agent | Finance signs off every figure | Wrong figure in a donor appeal |
| CS: events | good | Opener styles (Countdown, Spy Titles); few facts | 30–60 min agent | Final watch, rights to school marks | Logo rights |
| Investor or partner update | limited | A launch or annual film, yes; monthly updates belong in a template or text | 30–60 min agent | Founder signs off every number | Wrong number, spoken with confidence |
| Internal training | limited | No product screenshots (UI is redrawn from a spec), no editing UI; a screen recording is cheaper | 30–60 min agent | Product owner watch | Goes stale with the product |

## 2. Three offers (lens 5)

| Offer | Dream outcome | Proof | Metric | Kill criterion |
|---|---|---|---|---|
| "Your list, 45 s" (your ABM, top 10–20 targets) | They see their problem quantified | Their public numbers | Replies vs a text-only control | Replies under 2× control after 20 sends, or over 30 min of your time per account |
| "Your segment health" (AlumnForce QBR) | The board believes the list | The school's file: naive vs trusted count | Forwarded to leadership; pilot converts | Under 3 of 10 pilot tenants forward it, or one fact-check failure |
| "Confirm / Correct" (school campaign) | Profiles fresh before the dues drive | "Last updated 4 years ago" | Confirm/correct rate vs a static email | Lift under 10 %, the week-17 bar |

## 3. Measurement (lens 1)

**Talk test.** 6 PMs per arm: the film vs a static slide with the same facts for the same time. Score recall of the four numbers in order and why each changes (0–8), ask "why 6, not 49?", and retest at 24 h. Fail: film ≤ slide, or a 35 s cut scores the same. Six per arm only catches misreadings; detecting 40 % → 80 % recall needs about 23 per arm.

**Campaign A/B.** Arms: plain text / static image + link / GIF poster + video link, with spam placement as a guardrail. α 0.05, power 0.8, industry-typical base rates (not your data):

| Channel | Metric | Base → target (MDE) | Per arm | Duration |
|---|---|---|---|---|
| Cold email | positive reply rate | 3 % → 4 % | about 5,300 | 3 arms at 500/day ≈ 32 sending days; 2 arms ≈ 21 |
| LinkedIn ads | CTR | 0.5 % → 0.65 % | about 40,000 impressions | set by budget |
| Alumni profile update | completion within 14 days | 8 % → 10 % | about 3,200 | one send to a 20k-alumni school, read at day 14 |

## 4. Automation ladder (lens 6)

| Rung | Move up when |
|---|---|
| Prompt, one film (today) | You watched it with sound and logged a verdict; the recalibrated eval passes it |
| Skill: directive plus gates | 5 hand-briefed films, each watched; eval agrees with the human 5/5; minutes and tokens logged |
| Loop: template variants | 10 variants, 0 fact defects missed by the eval; error channel tested |
| Routine: per account into a review queue | Never publishes; an alarm fires if the queue stalls |

Gates fail closed. **Never automate:** the fact sheet, the final watch, rights clearance, real member data or faces, and publishing. A person sends.

## 5. Compounding plan (lens 11)

| Window | Build | Decision |
|---|---|---|
| Days 1–30 | House style ("Trusted Data") saved in the repo, not `~/lemo-my-styles`; toolkit pinned at `bebbbe1`. `content.json` generated from FACTS in place of hardcoded counts. Eval narrowed to narration and on-screen text. `film_ledger.jsonl`: style, stage minutes, fix rounds, first-run verdict, tokens, human minutes | Day 14: rebuilds from `content.json` and passes eval first time? If not, stop |
| Days 31–60 | Film 3 from the template; directive `directives/video/lemo_opuscar.md`; pronunciation lexicon | Day 45: ≤ 5 min authoring and ≤ 1 fix round? If not, lemo is for hero films only |
| Days 61–90 | Hosted player with analytics. lemo for the look; Remotion for templated per-recipient work once approved (100 lemo variants ≈ 8 h rendering) | Day 90: 30+ views per variant? Only then let results steer style |

## 6. Cannot do

- No live action, generated video or stock footage: everything is drawn in code.
- No real faces or photoreal people, and no real lip-sync (mouths follow loudness).
- No product screenshots, no editing of existing video, no timeline editor: every change is a re-prompt and re-render.
- No identical re-creation: the same brief gives a different film, and a rebuild from source is close but not byte-identical (compare with SSIM).
- Tuned for Opus 5.5; other models untested.
- One French voice (Kokoro `ff_siwis`). Natural French needs edge-tts, which sends text to Microsoft under unclear terms: never with member data.
- Short-form (30–60 s); Windows only through WSL; no logos without rights.

## 7. Legal and labelling duties

- **EU AI Act Art. 50:** transparency duties apply from 2 Aug 2026 50(4) covers deep fakes. A schematic film isn't one, but label every outbound film "Made with AI · synthetic voice" and use platform AI labels. French Penal Code art. 226-8 (SREN) bars publishing a real person's synthetic voice without consent unless labelled: never clone a voice without written consent.
- **CC BY credit:** Salamander piano (Alexander Holm, CC BY 3.0, with URL) on the end card and in CREDITS; MuldjordKit drums are CC BY 4.0. Ads: CC0 instruments only.
- **Alumni consent:** the school sends and is the controller. Only data the member entered; never login activity, inferred employer or city, or admin labels. One click to correct or opt out; skip the unsubscribed; no alumni photos without consent.
- **Cold email:** named sender, opt-out line, warmed domain with SPF/DKIM/DMARC, low volume (CNIL B2B rules).
- **AlumnForce case material** (the file, the 68 %, the verbatims) stays with the panel.
- **Maps:** override DIRECTOR §13; never relabel a data field.
