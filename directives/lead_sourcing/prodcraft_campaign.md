# ProdCraft Proposal Engine Campaign SOP

## Goal
Run the cold email campaign selling the ProdCraft "Proposal Engine" (free 72-hour rebuild of one past proposal as a live link that alerts on client open) to event production/AV, commercial fit-out and incentive/DMC firms in the US and UK. Launched 2026-11-02.

## Inputs
- Leads: `.tmp/leadocean/campaigns_by_country/` (from `leadocean_leads.py` + `reoon_verify.py`), split `{Niche}_{US|UK}_{Personalized|NoPersonalization}`, catch-alls in `catchall/`. Mirror in Drive folder `13yWvY-bsY6AjOj57HKad9UW64Z5BXkRp`.
- Env: `INSTANTLY_API_KEY`, OpenRouter key for Jev.
- Sending accounts: the 12 inboxes tagged `Deb_Oct 6 26` (tag id `cebb93b4-b98d-4948-bd99-43b0495fa93f`).

## Tools/Scripts
- `execution/lead_sourcing/prodcraft_campaign/build_copy.py`: builds the 4 copy sets (EventAV, FitoutUS, FitoutUK, DMC) into `copy.json` and gates them with Jev.
- `execution/lead_sourcing/prodcraft_campaign/launch.py`: default prints the plan only (campaign, file, lead count, pending steps; no Instantly call, no key needed). `--apply` creates draft campaigns, uploads leads (`skip_if_in_workspace`), tags them; `--apply --activate` also starts them (`--activate` alone is rejected). `--only-first` limits to the first campaign. Idempotent via `.tmp/prodcraft_copy/launch_state.json`.

## Outputs
- 19 Instantly campaigns named `DM_{Niche} - {US|UK} - {Personalized|NoPersonalization}[ CatchAll] - 2 Nov 2026`, tagged `Deb_Oct 6 26`.

## Steps
1. Edit copy in `build_copy.py`; run it; every template must score Jev `human` >= 0.75 and `slop` <= 0.25 (the playbook Section 7 control scores 0.37 / 0.72).
2. Re-run `reoon_verify.py` if leads are older than 7 days.
3. Run `launch.py` (plan only) and check it, then `launch.py --apply` (drafts), read back the campaigns, then `launch.py --apply --activate`.

## Copy rules (operator, 2026-11-02)
- Voice: Siva's best performers since Sept 2026 (personality opener, one hard proof, tiny ask, risk in a PS; lowercase; no signature).
- Proof only from the CV / workspace: 6 concept redesigns from the prospect's own photos and words, **48 hours each** (CV; no source supports 24 h); 12+ AI products shipped for clients in 2026; proposal system sends a tracked link that alerts on open.
- Offer: send one past proposal/deck/tender/program proposal, rebuilt free as a live link in 72 hours (playbook).
- Personalized step 1 uses `{{project_reference}}`, never `{{icebreaker}}` (icebreaker sentences fail the human gate).
- 3 steps: day 0 (3 subject variants), +3 days, +4 days; follow-ups have empty subjects (same thread).

## Edge Cases
- Instantly timezone is an enum: `Europe/London` is rejected; UK uses `Europe/Isle_of_Man` (same clock incl. BST); US uses `America/Chicago` 09:00-12:00 (= 10-1 ET, 7-10 PT). Spec: `https://api.instantly.ai/openapi/api_v2.json`.
- Spintax must be `{{RANDOM|a|b}}` without spaces around pipes, matching existing campaigns.
- Campaigns share the 12 inboxes with other active DM_ campaigns; total inbox capacity ~340/day. Catch-all campaigns cap at 5/day.
- No postal address in the copy: CAN-SPAM (US) requires one; the unsubscribe header is on. Add an address line if the operator provides one.

## v2 (applied 2026-11-03; supersedes the v1 copy rules above)
- v1 failed the buyer-fit test: proof was website redesigns, not the proposal pain (Jev pain 0.12, fit 0.41). Lesson: the gate must check pain + offer-fit + plain language, not only truth and human tone.
- Copy: `build_copy_v2.py` -> `copy_v2.json`. Step 1 = playbook pain + dated trigger + done-for-you offer + "want me to send over an example?" + money-back guarantee (halve deck/bid/proposal time over next 5, from playbook section 4) + "lmk and i'll stop". Variant A prospect-first, variant B adds "my friends say i talk too much" (A/B test, not assumed).
- Gate (Jev, calibrated on Siva's proven winners: human 0.74-0.81, slop 0.45-0.51, plain 0.87-0.91, 82-97 words): human >= 0.70, slop <= ~0.6, pain >= 0.55, fit >= 0.55, plain >= 0.70 (industry words count as plain), step 1 <= ~100 words.
- Settings with evidence (`.tmp/prodcraft_copy/benchmarks.md`, `siva_analysis.md`): Mon-Fri (Siva sends Fri); US 09:00-13:00 Chicago, UK 08:00-12:00 Isle_of_Man; steps day 0/2/4 (Siva); daily_limit 30 for all incl. catch-all (no evidence for 5/day; pause any campaign above 3% bounce); plain text, tracking off; no signature; lowercase (Siva; confounded).
- Operator commitments: honour the money-back guarantee; keep one sample per niche (deck, bid/tender proposal, trip proposal) ready to send on "yes".
- Kill/keep: pause >3% bounce; rewrite if reply < 1% after 500 sends; target >= 0.3% positive per lead (Siva 0.28-0.89%).

## GTM v3 (2026-11-10; supersedes the Proposal Engine pitch for the not-yet-contacted leads)
- Operator switched the offer to GTM pipelines ("option 1") with the wk04 video (https://prodcraft.fyi/gtm/, credit line
  removed; emails link https://prodcraft.fyi/new-clients, a 301 to /gtm/ because Jev read "gtm" as jargon).
- Copy: `build_copy_gtm.py` -> `copy_gtm.json`. Offer from web research (30MPC/Gong 85M emails: offer CTA +28%, meeting
  ask -44%): step 1 = referral pain + Accessory Masters proof (about a dozen emails a day by hand -> 800 a day) + yes/no
  "want me to pull the first 20 for you? <titles> at mid-size companies, emails checked. free, no call needed";
  step 2 = video + how it works; step 3 = prospect names how many clients a month would matter. 50 ruled out by the
  operator; no guarantee (no data). The $128K figure is never used in emails (FACTS.md: not credited to the system alone).
- Red-team 4/4 PASS in 3 rounds (round 3 operator-authorised), sha 96f5414f995c. Fixed on the way: no intent/location
  claims about the free list, "every day" not "a few a day", no free-build ask, name the thing built.
- Launch: `launch_gtm.py` creates `DM_{Niche} - {US|UK} - {Pers} - 10 Nov 2026` per 2 Nov source with not-contacted
  leads, moves them (`/leads/move`, FILTER_VAL_NOT_CONTACTED; no new lead slots), tags `Deb_Oct 6 26`, activates.
  `--audit` checks no already-emailed lead sits in a new campaign (activation refuses otherwise). 2026-11-10: 517 leads
  moved into 8 active campaigns; analytics "contacted" over-counts, so leads - contacted under-estimates the move.
- Mid-sequence leads finish the old v2 sequence in the 2 Nov campaigns; finished leads are not re-contacted.
