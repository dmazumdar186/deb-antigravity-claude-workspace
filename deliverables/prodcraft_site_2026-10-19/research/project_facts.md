# prodcraft.fyi portfolio: verbatim project facts
Collected 2026-10-19 from /home/user/deb-antigravity-claude-workspace. Paths are repo-relative. Quoted numbers are verbatim from the cited file.
Live URLs were NOT re-curled (sandbox cannot reach *.pages.dev); they come from HANDOFFs, which state each was deployed. All are noindex concept/demo builds.
Dates are the folder or handoff dates (git history for several is squashed to one day).

## Confidentiality legend
[PII] candidate or person data. [PRICING] private pricing. [ANON] anonymise the client/prospect on the public site. [CRED] password or key.

---------------------------------------------------------------
## A. SITE REDESIGNS
---------------------------------------------------------------

### 1. gaia-talent-redesign
- Client: Gaia Talent Ltd (Keith Molony, MD), Ireland environmental recruiter. Real client relationship. Naming Gaia in public needs Keith's OK; the "/for-keith/" page is private.
- Date: 2026-09-17 (handoff). Category: site-redesign
- Built: 5-page recruiter site (`/`, `/jobs/`, `/team/`, `/for-keith/`, `/404.html`) from templates, byte-reproducible build, 63 real live jobs linked to gaiatalent.com.
- Facts:
  - "test-suite: 6 tiers, all green." and "`js/motion.test.js` (22 tests)" (deliverables/gaia_redesign_2026-09-17/HANDOFF.md)
  - "63 live roles across Ireland" (same file; dataset has 0 UK locations)
  - Audit status: "anneal-reviewer: PASS", "pipeline-auditor: WARNINGS resolved", code-reviewer pass 3 fixed 3 majors (same file)
- Live: https://gaia-talent-redesign.pages.dev/ ("done 2026-09-17", curl 200 on `/`, `/jobs/`, `/team/`, `/for-keith/`)
- Flags: [ANON optional] client name. Public pages carry no AI wording by spec; /for-keith/ discusses tooling.

### 2. greenjobs-redesign
- Client: GreenJobs (Gaia Talent Ltd, Keith Molony), greenjobs.ie and greenjobs.co.uk. Real client; a paid proposal exists. [PRICING]
- Date: 2026-09-22 build; refreshed 2026-09-28; proposal v1.0 2026-09-30. Category: site-redesign
- Built: two-edition job-board rebuild (IE + UK) with sector/region maps, salary stats, dashboard, job pages, SEO landings, on-device CV match.
- Facts:
  - "165 live roles on the 22 Sept snapshot (88 IE, 77 UK ...), 195 pages, CSS 76.9 KB, JS 107.5 KB (budgets 80/125), zero third-party requests" (deliverables/greenjobs_redesign_2026-09-22/HANDOFF.md)
  - "2,797 checks on 2026-09-28: 1,010 + 40 + 15 + 1,732 layout assertions over 202 page loads" (same file)
  - "Panel pass (11 lenses) run 2026-09-28" (same file)
  - Proposal claim: "The current pages weigh about a megabyte per visit. The rebuilt boards serve the same content in under 200 KB with no third-party requests" (deliverables/greenjobs_redesign_2026-09-22/proposal/GreenJobs_Proposal_v1.0_2026-09-30.md)
- Live: https://greenjobs-redesign.pages.dev/
- Flags: [PRICING] proposal .docx/.md and keith_costing_brief_2026-09-28.md hold costs; do not publish. "KEITH_CHANGES_CHECKLIST.md" is the client's change doc. Robots Disallow: / on the demo by design. Lighthouse was not run (stated in HANDOFF).

### 3. h2recruit-redesign
- Client: h2 Recruit (SaaS sales recruiter, London + New York). Prospect (Ian Harwood replied once to cold email, then went quiet; no engagement). [ANON]: use "a London SaaS recruiter".
- Date: 2026-09-30. Category: site-redesign
- Built: one-page, zero-dependency concept: pinned scroll-scrubbed canvas hero (360 sellers -> shortlist of 5 -> one placed hire), 7-role card stack, simulated overnight outreach feed, "Ask h2" rule engine.
- Facts:
  - "Hero: ... 360 sellers -> shortlist of 5 -> one placed hire" through "six copy states" (deliverables/h2recruit_redesign_2026-09-30/HANDOFF.md)
  - "the 7 real open roles from the site" (same file)
  - Verified "Playwright load at 1440 and 390 wide, no JS errors"; "No test suite, no human-eye-test, no audit stack." (same file; honest limits)
- Live: https://h2recruit-redesign.pages.dev/
- Flags: [ANON]. Weak on metrics.

### 4. gtm-people-redesign
- Client: GTM People (H2 International Ltd), SaaS GTM recruiter, London. Same prospect as #3 (Ian Harwood). Never hired. [ANON]
- Date: 2026-10-06 (v1 to v4.1 in one day). Category: site-redesign
- Built: four cuts of a recruiter site (v1 tabbed deck, v2 scroll-story, v3 "Brief it" intent board with fee calculator, v4 cinematic brand opening) plus pitch page.
- Facts (v1 deck vs live, Playwright `research/measure.mjs`):
  - "Desktop 1440x900 page height 17,828 px (19.8 screens) -> 1,773 px (2.0 screens), 10.1x" (deliverables/gtm_people_redesign_2026-10-06/HANDOFF.md)
  - "Mobile 390x844 page height 36,490 px (43.2 screens) -> 2,941 px (3.5 screens), 12.4x" (same file)
  - "Words in DOM 4,373 -> 5,003 (all live copy + 25 role descriptions) nothing dropped"; "index+css+js ~275 KB HTML alone -> 100.1 KB" (same file)
  - v3: "Scroll to first matching role ... 3,896 px+ (then filter) -> 0 px"; "Content probe 135 live sentences / 0 missing" (v4) (same file)
  - "Third-party scripts 3 -> 0" (same file)
- Live: https://gtm-people-redesign.pages.dev/ (cuts at /deck/, /story/; pitch /for-ian/)
- Flags: [ANON]. Pitch page /for-ian/ names the prospect. Human-eye test on v2 was "FAIL 3 P1 / 12 P2 / 8 P3" (fixed in /story/); full human-eye run on v3/v4 "is the next gate" (not done). Strong measurable story.

### 5. midas-redesign
- Client: Midas France (auto-repair franchise, Mobivia group). Prospect: a local franchisee; no engagement. [ANON]: "a French auto-repair franchise"; Midas logo is a third-party trademark (Wikimedia Commons).
- Date: 2026-10-05 (v2.1 mobile fix same day). Category: site-redesign
- Built: French one-page concept with working booking widget (plate mask, 24 h slots), -30 % offer countdown, 14 filterable service rows, scroll-driven car, mobile tap-to-call breakdown block.
- Facts:
  - "59.6 KB HTML+CSS+JS" (deliverables/midas_redesign_2026-10-05/HANDOFF.md)
  - "All animations verified under iPhone 13 emulation (33/33 assertions)" (same file)
  - "Playwright at 1440x900 and 390x844 plus reduced-motion: 0 console errors" (same file)
  - Research context quoted from public sources: "375 centres in France, 712 in 10 countries" (same file; third-party facts, not our result)
- Live: https://midas-redesign.pages.dev/ (pitch /pour-midas/)
- Flags: [ANON]. Mobile bug on Pixel 8 Pro found by operator then fixed (v2.1: 3 root causes), a good "I fix what breaks" story. Trustpilot 1.7/5 deliberately not shown.

### 6. misb-redesign (site + social set)
- Client: MISB (Mash International School of Business), Paris/Lyon. NOT a client: built as a portfolio piece for the operator's application to their Social Media Marketing Manager role. [ANON]: "a Paris business school".
- Date: 2026-10-15 (v1, v2, v3 "the prospectus"). Category: site-redesign (the 20 posts are also video/creative)
- Built: scroll-scrubbed "prospectus" site (pinned cover, tri-fold chapter, tabbed deck) plus 20 social posts (10 Instagram + 10 LinkedIn) with captions and 2-week calendar.
- Facts:
  - "desktop 6,321 px vs misb.fr 9,011; mobile 5,464 px vs 14,528" (deliverables/misb_redesign_2026-10-15/HANDOFF.md; research/handoff_v3.md says 6,177 / 5,484 before polish, so use the HANDOFF figures)
  - "functional 29/29; site_check 0 failures"; eye-review rounds "fixed 13 defects" (same file)
  - "20 posts 1080x1350 rendered from HTML" and "119 usable photos downloaded; 46 kept for the site (WebP <= 1600 px, 4.2 MB)" (same file)
  - "index+css+js ~ 78 KB; backdrop 5.1 KB"; backdrop written by GLM 5.3 "in one round ($0.026, research/glm_log.md)" (deliverables/misb_redesign_2026-10-15/site_v3 notes: research/handoff_v3.md)
  - Found site contradictions: "work-study rhythm stated three ways", "10 MB hero video" (HANDOFF)
- Live: https://misb-redesign.pages.dev/ (pitch /for-misb/); social https://misb-social.pages.dev/
- Flags: v3 site_v3/ is described in handoff_v3.md as "Not deployed" but HANDOFF says "LIVE at the same URL" (conflict; trust HANDOFF, recheck before linking). Photos are misb.fr's own. The 20 posts are not in a clean "client" frame.

### 7. gaia-privacy (candidate notice)
- Client: Gaia Talent (Art. 14 GDPR candidate notice, hosted on a Prodcraft domain). Category: site-redesign (utility). Part of #11.
- Live: https://gaia-privacy.pages.dev/gaia-candidate-notice (execution/gtm_client_workflows/gaia_sourcing/core/config.py:279)
- no metric published.

---------------------------------------------------------------
## B. AGENTS / SOURCING / CONSULTING FOR A CLIENT
---------------------------------------------------------------

### 8. gaia-sourcing-shortlist (Aug 20) and gaia-2026-09-10/09-14 (Radar re-cut)
- Client: Gaia Talent (Keith Molony). Real client. TOBIN/AtkinsRealis roles inside the dossier. [PII][ANON candidates]
- Dates: 2026-08-20 delivery; 2026-09-10 call; 2026-09-14 corrected cut. Category: agents/infra
- Built: evidence-verified candidate sourcing pipeline (harvest -> extract -> validate -> gate -> contact -> messages -> render) with a dossier site, verbatim-quote evidence on every claim, pool maps; then "Radar" re-design (brief contract, Brief Controls page, Recruit CRM sync adapter).
- Facts:
  - 20 Aug: "Role 1: 158 profiles assessed, 594 raw claims, 446 surviving validation, 18 passed gates, 10/10 delivered. Role 2: 21 profiles assessed, ... 4 passed gates, 3/5 delivered" (deliverables/gaia_2026-08-20/pool_map_role1.md, pool_map_role2.md; summarised in deliverables/gaia_2026-09-10/ENGAGEMENT_RECORD_2026-09-11.md)
  - "13 candidates (10 + 3) ... 117 evidence claims"; "Quote-drop rate 0.9%"; "18-check acceptance gate" (ENGAGEMENT_RECORD_2026-09-11.md)
  - "Full 20 Aug run cost: EUR 0.60 against a EUR 30 ceiling" (same file, citing execution/gtm_client_workflows/gaia_sourcing/HANDOFF.md:152)
  - Corrected cut: "471 assessed ... 2 gate-passers ... 2 of 10 delivered", Role 2 "65 assessed ... 0 of 5" (deliverables/gaia_2026-09-14/pool_map_role1.md shows 471 / 1902 raw claims / 1470 surviving / 2 / "2 of 10")
  - "Model spend EUR 25.69 of a EUR 26.50 cap" (ENGAGEMENT_RECORD; HANDOFF_SESSION_2026-09-11.md); test suite "130 -> 501 (Aug) ... 1,093" (ENGAGEMENT_RECORD)
  - Client verbatim: "I like the simplicity of the interface of what you sent me, the grading system" (deliverables/gaia_2026-09-10/transcript_2026-09-10_fathom.md); also criticism "they were too senior" (honest: first shortlist missed seniority/Ireland residence).
- Live: none for dossier (gaia-privacy only). `deliverables/gaia_site_2026-09-14/` (shortlist, brief-controls, check, for-maddie, next-30-days pages) has vercel.json, no URL recorded.
- Flags: [PII] dossier.html/candidates.csv/check.csv contain real named candidates, emails, LinkedIn quotes: NEVER publish. Transcript, RUNBOOK, call_brief, monday_send are client-confidential; the engagement record flags a "50 sent" vs 13 contradiction and an unproven Monday send. Honest framing: the 14 Sep re-run delivered only 2/10 because the brief was made stricter. Use pool-map style "honest denominator" as the story.

### 9. gaia-poc-check ("Shortlist Check")
- Client: Gaia Talent (internal POC). Date: 2026-09-11. Category: audit/consulting
- Built: offline re-check of the 13 August names against the 10 Sep brief.
- Facts: "0 of 13 pass; 10/13 over the seniority ceiling; 5/13 pattern-guess emails, 1 with none" (deliverables/gaia_poc_check/PLAN.md, quoted in ENGAGEMENT_RECORD)
- Flags: [PII] names. Not in your requested list but adjacent.

### 10. alumnforce-case-study (the "tender-davinci" audit deliverable)
- Folder: projects/alumnforce_case/ (branch `claude/tender-davinci-sx2g09`; merge cc28166, 2026-10-15). NOT under deliverables/.
- Client: AlumnForce (alumni-platform vendor). It was a job-application case (Senior PM Data & AI, step 2), not a paying client. [ANON]: "an alumni-network SaaS vendor". Brief PDF and input CSV are AlumnForce's and are not committed.
- Date: 2026-10-12 to 2026-10-15. Category: audit/consulting
- Built: 15-slide deck + Annex A to D (19 pages), an 8-slide live presentation, runnable SQL (Annex B), speaker guide, an 11-lens panel verdict.
- Facts:
  - "Finance in London for 3+ years: naive filter 2 (file as delivered, with tenure), normalised 26, full logic 49" ; "525 rows for 500 announced members" (projects/alumnforce_case/README.md)
  - "68 % of profiles untouched for 2+ years; 77 % no login for 12+ months" (README.md)
  - "Annex B ... Returns 49 rows"; ids "identical to annexB_result.csv True"; deck.pdf "19" pages (README.md; PANEL_VERDICT.md evidence table)
  - "Status: recruiter panel CLEAR; lenses 1-11 CLEAR; visual QA PASS (qa27: 19 pages, qa_pres3: 8 pages); pipeline audit round 2: 7/7 PASS" (PANEL_VERDICT.md, Round 5, 2026-10-15)
  - Sizing: "24-28 effective dev-weeks" and "26 dev-week core" (PANEL_VERDICT.md)
- Live: none.
- Flags: [ANON]. A demo-instance password was redacted in commit 42e9dda; PANEL_VERDICT says `grep -rl "<demo password>" .` returns 0. Honest-gaps section is excellent proof of rigor (it lists unverified claims). BRIEFING.md and SPEAKER_GUIDE.md are private notes.

---------------------------------------------------------------
## C. OUTBOUND / LEAD LISTS
---------------------------------------------------------------

### 11. bay-area-recruitment-list
- Client: internal/own outbound (recruitment agencies). Date: 2026-10-13. Category: lead-list
- Built: classified, MX-checked launch lists for 3 metros.
- Facts:
  - "Source export: 1,900 rows. 5 duplicate emails removed." (deliverables/bay_area_recruitment_2026-10-13/README.md)
  - San Francisco "rows: 839, on_target: 289, off_target: 550" (deliverables/bay_area_recruitment_2026-10-13/icp_summary.json); Seattle "rows: 289, on_target: 115"
  - Launch CSV line counts incl. header: SF 1656, San Diego 704, Seattle 548 (wc -l; SF/others may be multi-line cells, so treat as upper bounds, not row counts)
  - "Verification is domain-level only (no mailbox verifier key in the cloud session)" (README)
- Flags: [PII] business contact emails in CSVs; do not publish files.

### 12. recruitment-cities-relaunch (bounce fix)
- Client: internal outbound campaign "Recruitment Cities 30 Sep 26". Dates: 2026-10-09 runbook, 2026-10-14 relaunch. Category: outbound
- Built: bounce root-cause fix and a cleaned relaunch list split by city; plus campaign cleanup and guard scripts.
- Facts:
  - "Input ... (2501 rows) ... Output ... (977 rows, same columns, ready to upload as-is)" (deliverables/recruitment_cities_2026-10-14_relaunch/README.md)
  - "12 of 18 hard bounces were `catch_all` rows, 5 were rows the verifier had already marked `invalid`" (same file)
  - Filter table: catch_all 721, unknown 229, invalid 109, blank 272, dup 24 dropped (same file)
  - City split: Dubai 287, Singapore 248, Seattle 147, San Diego 125, Hong Kong 120, Kuala Lumpur 28, Shanghai 22 (= 977) (same file)
  - Earlier runbook (deliverables/recruitment_cities_30_sep_26/RUNBOOK.md): "Instantly Bounce Protect (status -2)"; "SAFE upload 978", "CATCHALL hold 842", "1,208 emails to remove"
  - "expect a small residual rate (~0.5-1%), well under Instantly's 3% pause threshold" (README; an estimate, not measured)
- Discrepancy: RUNBOOK says 978 safe leads, relaunch README says 977 (after MX/dedupe pass). Cite one with its source.
- Flags: [CRED] campaign id f161ac21-... in RUNBOOK (internal); [PII] CSVs. Good "I diagnosed a paused campaign" story.

### 13. yoga-teachers-france-list
- Client: internal/own outbound (yoga studios, France). Date: 2026-10-14. Category: lead-list
- Facts:
  - "229 rows, 10 cities" in -> 195 out; "duplicates_removed: 34"; "names_found: 113, names_blank: 82" (deliverables/yoga_teachers_france_2026-10-14/README.md, report.json)
  - Upload split: 83 named+sendable, 62 no-name sendable, 50 excluded (README)
  - "34 rows shared an email with another row (21 emails)" (README)
- Flags: [PII] studio emails. Name confidence "<=0.6 = not corroborated".

### 14. self-outbound-system (research input only)
- Folder deliverables/self_outbound_system/ holds ONE file: a 3:59:11 video analysis ("8029 transcript segments, 279,000 characters", "~EUR 2 in Anthropic API tokens (4 parallel Sonnet 4.6 calls)"; deliverables/self_outbound_system/nick_saraev_cold_email_full_analysis.md). It is a third-party source book (Nick Saraev). Do NOT present it as a delivered project; its own outbound-engine results live in the CV/banners below.
- Category: outbound (research). Live: none.
- Self-reported outbound-engine claims (from the ProdCraft banners manifest, linkedin_banners/prodcraft/2026-10-01/manifest.json): "48,000 cold emails / month", "4%+ reply rate. $1M+ pipeline. A 4-SDR team replaced at roughly a tenth of the cost." These are the operator's own claims, not checked against raw data in this folder; the CV states "32 inboxes, 3-hour hot-lead SLA", "$1M+ qualified pipeline, ~$200K/yr SDR cost replaced" (deliverables/cv_ai_pm/*.pdf).

### 15. jev-leads (pipeline) and jev-install (see D)
- Directive: directives/gtm_icp_filters/jev_leads.md; skill .claude/skills/jev-leads; script execution/gtm_icp_filters/jev_leads.py; playbook docs/reference/jev_leads_playbook.md. Built 2026-10-16. Category: outbound / agents-infra
- Built: Jev-gated lead pipeline: scenarios `qualify | signals | hygiene | suppress | replies | inbound | diff | factcheck | message_score`.
- Facts:
  - "9 scenarios" (listed in the directive Inputs section); "Default 0.6 is a starting point" min-confidence; workers 8 (directive)
  - "a 78-issue thin-context test matched only ~10 labels" (directive Edge cases; honest negative)
  - "Thresholds not yet validated on a labelled set." (Run log, 2026-10-16)
  - Jev cost basis: "$0.042 / MTok, output free", "~100-700 ms" (directives/infrastructure/jev.md)
- Flags: model pinned to jev-1.13; prompt text goes to OpenRouter, strip PII.

---------------------------------------------------------------
## D. AGENTS / INFRA
---------------------------------------------------------------

### 16. jev-decision-model-install
- Directive: directives/infrastructure/jev.md. Installed 2026-10-06, all 21 use cases built by 2026-10-16. Category: agents/infra
- Built: Jev (TypeSafe decision model via OpenRouter) as a prompt router hook plus 21 classify/pick/score use cases, each with script + directive + offline test + one live run.
- Facts:
  - "All 21 built (1-19 on 2026-10-06/07, #20 2026-10-07, #21 jev-leads 2026-10-16), each with script + directive + offline test + one live run."
  - "Measured 2026-10-06: 10 prompts, 6.8 s, $0.00099, all tiers correct, skill picks ... at 0.99."
  - "~$0.0001 per prompt (33-skill menu ~2.3k input tokens), ~600 ms."
  - "$0.042 / MTok, output free" ; "in ~100-700 ms"
  - Exit criterion: "`jev_router.py test` returns 10 rows, 0 errors, < 15 s."
  (all from directives/infrastructure/jev.md)
- Use cases (the 21): Sheets categorize, inquiry triage, ad-library tagger, clip finder, customer health, backlinks, comment buyers, validation harness, skill pick, model pick, email gate, Chrome feed filter, search by meaning, image search, live speech meter, zero-LLM chatbot, icon pick, page assembler, use-case finder, audit-stack confidence gate, lead pipeline gates.
- Flags: "Haiku is banned" policy and OPENROUTER key env quirk are internal. Router sends prompt text (<= 6000 chars) to a third party, so `/jev off` for confidential work.

### 17. prodcraft-medspa-outbound-pipeline
- Folder: execution/personal_workflows/prodcraft_medspa/ ; audits docs/audits/prodcraft_medspa_panel_pass_2026-09-10.md, ..._audit_stack_2026-09-16.md, ..._2026-09-21.md; directive directives/personal_workflows/prodcraft_medspa_pipeline.md. Dates 2026-09-10 spec, 09-16/17 build, 09-21 round 4. Category: outbound (agents/infra)
- Client: own productised offer ("0.5 Website" for med-spas). No client; no live send yet. Prospects are real spas (anonymise).
- Built: end-to-end pipeline: Google Places discovery -> site audit/score (PSI + vision) -> owner lookup -> email verify -> per-spa preview site hosted on `*.preview.prodcraft.fyi` -> CAN-SPAM-linted 4-touch email -> reply classify -> takedown/DNC; GitHub Actions cron, Telegram alerts, dashboard.
- Facts:
  - "python3 -m pytest tests/prodcraft_medspa -q: 405 passed, 35 skipped" (09-16 audit) -> "674 passed, 35 skipped (184 s)" (09-21 audit)
  - Mock funnel: "22 found -> 16 kept -> 16 audited -> 6 qualified -> 6 owner -> 4 verified -> 4 previews -> 4 approved -> queue 4 drafted, 0 lint failures" (09-16 audit); rerun "previews 4 (skipped_unchanged 4)" (idempotent)
  - Panel: eleven lenses as sub-agents; code-reviewer "FAIL before fixes, all four criticals closed" (09-16 audit); pipeline-auditor "PASS with warnings"
  - Reply gold set: "keyword classifier 22/24 = 91.7%" (execution/personal_workflows/prodcraft_medspa/HANDOFF.md, gap pass)
  - Capacity maths (spec): "Phase 0: 5/day x 30 = 150 sends -> ~37 prospects -> ... 0.4-1.9 closes/month" (execution/personal_workflows/prodcraft_medspa/PROJECT_SPEC.md)
  - Guards: "warmup ramp (2/day rising ... over 14 days)", "2 percent bounce halt" (HANDOFF.md)
- Live: none. Everything "fixture-verified"; HANDOFF honest gap: "Still no live path has run from code" (09-21 audit, Honest gaps). A "first-5 dry run" sent 5 emails only to the operator's own address.
- Flags: [PRICING] offer tiers "Starter $2,500 + $99/mo - Growth $4,500 + $199/mo - Premium $8,000 + $299/mo" and a 60-day guarantee are in PROJECT_SPEC.md (own pricing; decide before publishing). Do NOT claim pipeline results/closes. Spec cites "$536 avg visit, $8,700 3-yr LTV" (third-party niche research, unverified).

---------------------------------------------------------------
## E. VIDEO / CREATIVE
---------------------------------------------------------------

### 18. linkedin-banners-prodcraft
- Folder: deliverables/linkedin_banners/prodcraft/2026-10-01 ; four-offers set deliverables/linkedin_banners/four_offers/2026-10-05. Category: video/creative
- Client: ProdCraft own brand. Built: 20 HTML-rendered LinkedIn banners + captions + clickable carousel PDF + 3 animated variants (mp4 + gif) for set 1; 20 more banners for four offers (web, outbound, inbound voice, speed-to-lead).
- Facts:
  - "20" variants in each manifest (linkedin_banners/prodcraft/2026-10-01/manifest.json; four_offers/2026-10-05/manifest.json); 3 animated pairs (`01_receipts`, `02_48k-emails`, `03_latency` .mp4/.gif)
  - Banner copy numbers are the operator's own claims: "$1M+", "+45%", "<30 days", "-55% p95 latency", "14 days from idea to TestFlight", "Topic prompt to public YouTube video in eight minutes" (manifest.json / captions.md). Not independently verified here.
- Pixel size of banners is not stated in the files I read (no metric published).
- Flags: links in captions: cal.com booking page (public), github.com/dmazumdar186, prodcraft.fyi (public).

### 19. ad-creative (batch generator)
- Folder: deliverables/ad_creative/prodcraft/2026-08-31 and yoga_jitendra/2026-08-31 ; skill .claude/skills/ad-creative/SKILL.md. Date 2026-08-31. Category: video/creative
- Built: Tier-1 procedural HTML/CSS/SVG ad variants with review page and tuner. ProdCraft set: 20 variants (variant_01..20.html), Yoga avec Jitendra set: 16 variants.
- Facts:
  - Canvas "1080 x 1080"; font Manrope; headline 88 px, sub 30 px (ad_creative/prodcraft/2026-08-31/profile.json)
  - Skill: "default 20 variants (Tier 1)"; "Tier 1 ... ~80% usable, near-free"; "Tier 2 ... ~25% usable, plan 4x overgeneration" (.claude/skills/ad-creative/SKILL.md)
- Flags: yoga set copy was fact-checked against yogaavecjitendra.fr ("Do not add claims beyond these"); real small-business client name; 5/5 from 10 testimonials is their claim (ad_creative/yoga_jitendra/2026-08-31/copy_pool.json).

### 20. higgsfield-demos
- Folder: deliverables/higgsfield_demos/hummingbird_macro_2026-07-08.mp4 (single 2.8 MB file, 2026-07-08 in filename). Category: video/creative
- Facts: "no metric published" (no README; file size only: 2,816,032 bytes). Not referenced in any markdown. Presumably an AI-generated (Higgsfield) test clip; unverified.
- Related (not in your list): site-redesign pipeline can drop Kling/Higgsfield footage (`hero.mp4`); no footage was generated in the redesigns (h2recruit: "no video key was available").

---------------------------------------------------------------
## F. PERSONAL / DOC
---------------------------------------------------------------

### 21. cv-ai-pm
- Folder deliverables/cv_ai_pm/ (CV EN + FR PDFs). Operator's own CV. Not a client project. Category: audit/consulting (self marketing)
- Facts (CV text, EN): "15 years B2B SaaS"; "12+ AI products shipped at a <30-day median"; "+45% adoption - -55% p95 latency - ~$200K/yr costs automated - $1M+ qualified pipeline"; "Stripe Connect marketplace ... $85K processed in the first 3 months" (deliverables/cv_ai_pm/CV MAZUMDAR Debanjan EN.pdf)
- Flags: [PII] CV contains personal email and phone number; do NOT publish the PDF. Reuse only the aggregate claims. Sibling folders cv_generic_pm and cv_dior_itlead exist (the Dior one names an employer target; not for public).

---------------------------------------------------------------
## Summary for the site (editor notes)
- Live URL list: gaia-talent-redesign, greenjobs-redesign, h2recruit-redesign, gtm-people-redesign, midas-redesign, misb-redesign, misb-social, gaia-privacy (notice only). Others in docs but out of scope: evolution-exhibits-v4.pages.dev, agentup-iag.pages.dev.
- Most metric-rich: gtm-people (10.1x / 12.4x page height), greenjobs (2,797 checks, 195 pages, 165 roles), alumnforce case (2 -> 26 -> 49 sizing, 11-lens verdict), recruitment-cities relaunch (2,501 -> 977, bounce root cause), medspa (674 tests, mock funnel), jev (21 use cases, $0.0001/prompt), gaia sourcing (honest 0.9% quote-drop, 158 -> 10).
- Never claim client results for sites: all redesigns are unsolicited or demo builds, no client reported lift.
