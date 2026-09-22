# Panel pass — GreenJobs redesign demo (2026-09-22)

Roster: `.claude/memory/panel_roster.md` (11 lenses). Inputs read: `HANDOFF.md`, `research/build_spec.md`, `src/data/{summary,brief}.md`, `src/README.md`, `src/templates/{for-keith,home,_shell}.html`, built `site/index.html`, `site/ie/index.html`, `site/ie/for-keith/index.html`, `build_site.py` (employer strip, pluralisation, before/after rows), screenshots `ie-index-1440-tall.png` and `ie-keith-1440-tall.png`.

Commercial context: Deb proposed €1,875 for a redesign. Keith (MD, Gaia Talent; owner of greenjobs.ie + greenjobs.co.uk) replied that he is considering moving the boards off the current vendor (Strategies, hosted job-board platform), that they need an upgrade, and that he is not yet convinced €1,875 is value for money.

Defects found while reading (referenced by number below):

- **D1** Home page "Employers hiring now — Organisations with live roles on greenjobs.ie this week" shows EirGrid, Power NI and Veolia. None has a live IE role (IE has 3 employers: Gaia Talent, Mattinson, Commonland). `employers_strip()` in `build_site.py` pads the strip from the scraped featured-recruiter list when fewer than 6 logos exist. The heading is false as rendered.
- **D2** "Live roles across 14 countyies" / "sectors and countyies you pick" — `units = unit + "ies"` in `build_site.py` line ~691 turns "county" into "countyies" (should strip the y). Visible in the 1440 screenshot.
- **D3** The evidence page lists the model-assistant phase as "GLM-5.3 (Z.ai) or Kimi K3 (Moonshot) via OpenRouter" and a repo path `execution/gtm_client_workflows/greenjobs_redesign/worker/`. Internal path and vendor names on a client-facing page.
- **D4** The offer box says the €1,875 includes "hosting setup" while "Migration off the current vendor" is a separately quoted phase-2 item. Keith's actual question is the migration; the page does not answer it.
- **D5** The header edition pill reads "IE UK" and the logo lockup shows "Green Jobs IE" as two words in the accessible text while the live brand is "GreenJobs". Minor, but it is his brand.
- **D6** "Requests on the home page: 44 → 11" compares an *estimated* count on the live site (brief §11 says "estimated 44") with a measured count on the demo. The table caption says "measured".

---

## 1. Andrej Karpathy — measurement

**On the deliverable.** The before/after table is the best thing on the evidence page because every "after" cell is read from build output, and the brief records the "before" bytes with byte-level precision (189,996 B measured; 1,058,725 B for scripts+styles+key images). That is a real row. What is missing is the number Keith will actually feel: time to interactive on a mid-range phone on a 4G profile, before and after. Byte counts are a proxy; Lighthouse was not run and the page admits it. Also D6: one side of the "requests" row is an estimate, the caption says "measured" — that is the kind of slip that lets a sceptic dismiss the whole table. Sparklines on sector tiles ("postings over the last eight weeks") are computed from posted dates; with 88 jobs and 10 sectors, several lines have n<5 per week and read as noise dressed as trend.

**On the commercial move.** "Not convinced it's value for money" is a measurement question: what does €1,875 buy in numbers? The reply should carry three: home page bytes (190 KB → 50 KB HTML; ~1 MB → ~80 KB assets), requests (44 est. → 11), and JobPosting schema (0 → 88 job pages with structured data, currently disabled on the live site). Do not quote a Lighthouse score you have not measured. If a headless Chrome is available locally, run it on both and put the real mobile score in the email; that single number is worth more than the whole "What was built" list.

**Honest gaps**
- No Lighthouse/WebPageTest run on either site; the claim "the inputs Lighthouse weighs most" is a belief, not a measurement.
- "Requests 44" on the live site is an estimate from HTML parsing, not a network trace (D6).
- Sparklines have no n shown; no falsification test for "trend".
- No baseline of Keith's current traffic, applications or employer conversions; the proposal cannot yet promise any business number.

## 2. Boris Cherny — tooling craft

**On the deliverable.** Deterministic string-template build, validator that fails the build, fixture data path for tests, `node --test` on the pure module, an `--out` allow-list guard, screenshot script, publish scripts. A fresh session could reproduce this from `src/README.md` and the HANDOFF. Good. Two craft gaps: (a) the validator checks banned words and asset paths but did not catch D1 or D2 — there is no test asserting "every employer in the strip has ≥1 live job in this edition" nor a pluralisation test; (b) the validator's "no third-party requests" rule is a static check, not a network trace.

**On the commercial move.** The build pipeline *is* the migration story: JSON in, 204 static pages out, nightly deploy on free hosting. That is what makes leaving Strategies cheap. The reply should say this in one sentence rather than list features.

**Honest gaps**
- No test for the employer strip's claim (D1) or for `units` pluralisation (D2).
- `publish_gh_pages.sh` / `deploy_cloudflare.sh` have not been run in this session; the public URLs are placeholders until they are.
- Lighthouse harness absent; no `--mock` path for the screenshot script documented.

## 3. Dario Amodei — safety, honesty, legal

**On the deliverable.** The honesty discipline is unusually good: brief-sourced facts only, no invented prices, B Corp mark shown with existing alt text and no added claim, forms that say "nothing was sent". But D1 is a false statement about third parties on the home page: EirGrid, Power NI and Veolia are presented as "hiring now on greenjobs.ie". If a screenshot circulates, those companies did not consent to that. Fix before publishing. Second: the demo republishes 186 employer job descriptions and 28 employer logos on a public URL that is not greenjobs.ie. Keith owns the boards, so he can authorise it, but the pages are live *before* he has. `noindex` + `robots Disallow` reduce, not remove, the exposure. Third: the site names "GreenJobs Ltd", Ennis address and phone numbers in the footer — Keith's real business contact details on a demo he has not approved. Fourth: the brief itself flags that the public sites never say Keith/Gaia owns GreenJobs; the demo's `for-keith` page is public-by-URL, so anyone with the link learns it.

**On the commercial move.** Do not claim the redesign "will" improve rankings, applications or speed scores; say what was measured. Do not disparage Strategies by name in the email; the evidence page already says "2013-era hosted platform", which is factual.

**Honest gaps**
- D1 is a live false claim about named companies until fixed.
- Republished job descriptions and logos on a non-GreenJobs domain before written consent.
- Real contact details and a candid ownership page reachable by anyone with the URL; consider a passphrase or a short-lived URL for `for-keith/`.
- Copyright of the scraped hero/employer logos was not checked beyond "they are on his site".

## 4. Anthropic research team — rigor

**On the deliverable.** Definitions are mostly pinned: fetch date, byte counts to the byte, taxonomy keywords in code, region aliases in JSON. Not pinned: the sector taxonomy has no stated precision — "individual roles can be mis-tagged" is a caveat, not a number. Sampling 20 roles by hand and reporting "17/20 correct" would take ten minutes and makes the caveat quantitative. The "before" figures come from one fetch with one UA; no repeat run to show variance. The phase-2 model section names two models but gives no eval set or accuracy for the TF-IDF matcher that ships today.

**On the commercial move.** Precision on what €1,875 covers is the whole negotiation. "As shown here" is not a scope. Enumerate: 9 page types × 2 editions, build pipeline, tests, deploy scripts, one round of revisions, hand-over. Say what is *not* in: content migration from Strategies, admin UI, ATS, model assistant, DNS cutover.

**Honest gaps**
- No measured taxonomy accuracy.
- Single-sample "before" measurement.
- No accuracy figure for the shipped smart-match.
- Scope stated as "as shown here" rather than an enumerated list.

## 5. Alex Hormozi — offer & unit economics

**On the deliverable.** Dream outcome is not stated anywhere Keith can see it. The evidence page sells bytes and stack; Keith's dream is "own my boards, stop paying a vendor, stop being embarrassed by a 2013 site, get more employers posting". Perceived likelihood: high — the demo is the proof, that is its job. Time delay: not stated (when could it be live?). Effort: not stated (what does Keith have to do?). Risk reversal: none. Scarcity: none, and don't fake it.

**On the commercial move.** Keith just told you he has a bigger problem than a redesign: vendor exit. €1,875 for a face-lift on a platform he wants to leave *is* poor value; he is right. Re-anchor: the demo is not a redesign, it is the front end of the migration. Offer two lines: (1) €1,875 — the demo as shown, live on his domains, static, his data, his hosting, delivered in N days; this replaces the front end and is the first step of leaving Strategies. (2) A separately scoped phase 2 (admin/posting flow, ATS, alerts, cutover) — quote it as a range only after a 30-minute call where he says what Strategies does for him today. Do not lower the €1,875; if anything the number is low for what was built, and lowering it confirms his doubt. Add one guarantee that costs you nothing: "if it isn't live and faster than the current site by the agreed date, you don't pay." Ask for one thing: the call.

**Honest gaps**
- No delivery date in the offer.
- No guarantee/risk reversal.
- Phase-2 is unpriced, so Keith cannot see total cost of leaving the vendor — the thing he actually asked about.
- LTV: recurring hosting/maintenance is not proposed; a small monthly retainer is the real economics here and is missing.

## 6. Nick Saraev — automation maturity & boundaries

**On the deliverable.** Rung: skill/script (scrape → JSON → build → validate → screenshot). Manual output was checked in three look-and-fix rounds before scripting the screenshots — right order. Bottleneck is not the build, it is Keith's decision; nothing downstream of that should be automated yet (no deploy, no DNS, correct). Fuzzy variables (taxonomy keywords, region aliases, brief facts) are few, named, and sit in code/JSON with a human-written template around them. Error channel: the build exits non-zero with a message, but there is no `service / environment / error / count` log and no self-healing change log yet — acceptable for a one-off demo, needed before phase 2's nightly build.

**On the commercial move.** The customer-felt step is the email. Write it by hand, not from a template. Do not automate follow-ups to Keith.

**Honest gaps**
- No structured error channel for the nightly build proposed in phase 2.
- Scrape is a one-shot; freshness will drift the moment jobs close (the demo will show stale roles within days — say so or rebuild before sending).

## 7. Daniela Amodei — operations, people & trust

**On the deliverable.** Who is on the receiving end: Keith, then possibly his staff and Strategies' account manager if he forwards it. Would Strategies feel respected? The evidence page says "2013-era hosted platform… IE8 shims, classic ASP" — factual, not sneering; keep it that way. Would the three employers named in D1 feel respected? No. Keith's own reputation: his real address and phones are on a demo he has not seen. The "For Keith" link appears in the public footer ("Explore … For Keith") and nav ("The evidence page") on every page; a candidate landing on the demo sees a private note. Move it off the public shell and reach it only by direct URL.

**On the commercial move.** Tone of the reply: respect that he pushed back. Do not argue; agree that a redesign alone is not the problem, then show the path. Owner for follow-up: Deb, one nudge after 7 days, then stop.

**Honest gaps**
- "For Keith" is discoverable from every public page.
- No quiet path for Keith to say "take it down"; put one line in the email: "say the word and the demo comes down the same day".
- D1 names third parties falsely.

## 8. Ilya Sutskever — capability & failure modes

**On the deliverable.** Where does a model sit in the loop today? Nowhere at runtime: the shipped "Ask GreenJobs" is TF-IDF, deterministic, bounded by the dataset. Good. Worst plausible output: a mis-ranked role; harmless. At build time the taxonomy is regex, not a model — the failure mode is silent mis-tagging (a "Wind energy" role tagged "Water & flood"), and nobody would notice because no eval set exists. Phase 2 proposes a hosted model behind a Worker with a schema (ranked IDs + one-line "why"); the schema bounds it, the rate-limit bounds cost, but the "why" string is free text on a public page — needs an allowlist/length cap and a "no employer names not in the dataset" check.

**On the commercial move.** Do not lead with the model assistant. Keith did not ask for it and it introduces the only part of the proposal that can produce a wrong sentence on his site. Mention it as optional, last.

**Honest gaps**
- No eval set for taxonomy or matcher; drift undetectable.
- Phase-2 "why" text unbounded on the public page.
- Model names (D3) are on a client page; they will be stale in months.

## 9. Mira Murati — product & UX

**On the deliverable.** At 1440 the home page is genuinely good: one accent, real counts, honest "3 employers" line, sector tiles with numbers, the county map, an alert form that admits it is a demo. On a phone at 11pm the things that will read wrong: "countyies" (D2) in two places; the eight "Latest roles" are 5 Gaia Talent + 2 Commonland + 1 Mattinson, so the board looks like Gaia's careers page — true, but Keith knows it and will wince; the employer strip (D1) padded with logos he knows are not hiring on IE. The `IE | UK` pill next to a moon icon and "Post a job" is clean. The evidence page reads as one voice; "Notes on honesty" at the end is the right place. One person wrote this — yes.

**On the commercial move.** Send *two* links, not one: the IE home (the feeling) and the evidence page (the numbers). Tell him which to open first. Keep the email under his thumb: 150 words, no bullets.

**Honest gaps**
- Screenshots were not checked at 360 (spec lists it) — only 390.
- The "Latest roles" concentration is real data; consider "Latest from each employer" or leave and say so.
- Empty-state and 404 copy were not reviewed in this pass.

## 10. Greg Brockman — engineering execution & reliability

**On the deliverable.** Runs unattended for 30 days? As a static site, yes — nothing to fall over. As a *demo*, no: the dataset is a 2026-09-22 snapshot; in 30 days every closing date is in the past and "88 live roles" is a lie. Either add "Snapshot of 22 Sep 2026" next to every live count (the footer already has it; the hero does not) or wire the scrape+build+deploy as a cron before the link goes out. One-command redeploy exists (`deploy_cloudflare.sh`). Runbook: `src/README.md` is enough for a stranger. Secrets: none in the page; the Worker stub holds the key pattern correctly.

**On the commercial move.** The most credible thing you can say to a man leaving a hosted vendor is "here is what hosting costs and here is the failure mode": Cloudflare Pages free tier, a nightly build, a status email if it fails. Put that in the phase-2 line.

**Honest gaps**
- Snapshot staleness not surfaced in the hero.
- No cron, no dead-man alarm for a nightly build (phase 2, but say it).
- Deploy scripts untested on this branch this session.

## 11. Demis Hassabis — systems & long horizon

**On the deliverable.** Does this compound? Yes, if it is framed as the first module of a platform, not a redesign: the scrape is the migration importer; the build is the CMS; the JSON is the data model for the ATS; the same pipeline serves the other eight network sites (conservationjobsuk.com … windjobsuk.com) from one codebase with a `--edition` flag. That is the 12-month shape: ten boards, one build, one hosting bill near zero, employer self-serve, and a data asset (salary disclosure, sector trends) nobody in the Irish/UK green-jobs niche publishes. The "Salary explorer" is the seed of that asset. Dead ends: the model assistant (nice, non-compounding); the wind-field hero (delightful, non-compounding).

**On the commercial move.** Keith's reply is the opening you want. The €1,875 conversation is small; the vendor-exit conversation is the account. Price the first step to be an easy yes, keep it at €1,875, and make it explicit that phase 2 is scoped after he shares what Strategies costs him per year — that number sets the ceiling for everything after. Ask for it.

**Honest gaps**
- Network-wide (10-site) build not tested; only IE/UK editions exist.
- No knowledge of Keith's Strategies contract terms, costs, notice period, data-export rights — the actual constraints on migration.
- 12-month shape is a hypothesis with no numbers behind it yet.

---

## Synthesis

### Five changes before sending

1. **Fix D1 (false employer claim).** In `build_site.py` `employers_strip()`, only pad the strip with employers that have ≥1 live job in the edition, or change the heading to "Employers on the GreenJobs network" when padding is used. Add a validator/test assertion so it cannot regress. This is the only item that is a correctness/legal issue, not polish.
2. **Fix D2 ("countyies").** Pluralise properly (`county` → `counties`) at the `units` line; rebuild; add a one-line test.
3. **Make the offer answer Keith's actual question.** Replace the offer box text with an enumerated scope for €1,875 (both editions, all 9 page types, build pipeline, tests, deploy on his domains, one revision round, delivery date) and a one-paragraph "Leaving your current vendor" line: what the demo already does towards it, what remains (posting/admin flow, alerts, applicant handling, DNS cutover), and that it is quoted after one call. Remove the repo path and model vendor names (D3); say "a hosted model behind a small server-side function".
4. **Take `for-keith/` out of the public shell.** Remove "For Keith"/"The evidence page" from the footer and nav so it is reachable only by direct URL; add a hero-level "Snapshot of 22 Sep 2026" caption next to the live counts so the demo does not lie in a week; correct the "requests" row caption to "estimated (live) / measured (demo)" (D6).
5. **Publish and verify, then send two links.** Run `deploy_cloudflare.sh`, open both editions and the evidence page on a phone, fill `{IE_URL}` `{UK_URL}` `{EVIDENCE_URL}`. If a headless Chrome is available locally, run Lighthouse mobile on live vs demo and put the two numbers in the email; otherwise leave them out rather than estimate.

### Draft reply to Keith (≤180 words)

Subject: GreenJobs — the redesign, built

Keith,

Fair point. A redesign on a platform you want to leave isn't value for money. So I built the front end of the migration instead, on your live data.

Ireland: {IE_URL}
UK: {UK_URL}
Numbers and scope: {EVIDENCE_URL}

Both editions, 186 live roles, every page static, no vendor, no framework. Home page HTML drops from 190 KB to 50 KB; first-paint requests from about 44 to 11; every job page gets the Google JobPosting schema your current site disables. It's a 22 September snapshot, so some roles will have closed.

€1,875 stands. It covers what you see, live on your domains, within 15 working days of go-ahead. If it isn't live and faster than the current site by then, don't pay.

Leaving the vendor fully (posting flow, alerts, applications, cutover) is a second job. Could you send me what the current platform costs per year and what it does for you day to day? Thirty minutes on a call would settle the scope.

If you'd rather the demo came down, say so and it's gone the same day.

Deb
