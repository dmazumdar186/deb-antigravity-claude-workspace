# ProdCraft Proposal Engine Campaign SOP

## Goal
Run the cold email campaign selling the ProdCraft "Proposal Engine" (free 72-hour rebuild of one past proposal as a live link that alerts on client open) to event production/AV, commercial fit-out and incentive/DMC firms in the US and UK. Launched 2026-11-02.

## Inputs
- Leads: `.tmp/leadocean/campaigns_by_country/` (from `leadocean_leads.py` + `reoon_verify.py`), split `{Niche}_{US|UK}_{Personalized|NoPersonalization}`, catch-alls in `catchall/`. Mirror in Drive folder `13yWvY-bsY6AjOj57HKad9UW64Z5BXkRp`.
- Env: `INSTANTLY_API_KEY`, OpenRouter key for Jev.
- Sending accounts: the 12 inboxes tagged `Deb_Oct 6 26` (tag id `cebb93b4-b98d-4948-bd99-43b0495fa93f`).

## Tools/Scripts
- `execution/lead_sourcing/prodcraft_campaign/build_copy.py`: builds the 4 copy sets (EventAV, FitoutUS, FitoutUK, DMC) into `copy.json` and gates them with Jev.
- `execution/lead_sourcing/prodcraft_campaign/launch.py`: creates draft campaigns, uploads leads (`skip_if_in_workspace`), tags them; `--activate` starts them. Idempotent via `.tmp/prodcraft_copy/launch_state.json`.

## Outputs
- 19 Instantly campaigns named `DM_{Niche} - {US|UK} - {Personalized|NoPersonalization}[ CatchAll] - 2 Nov 2026`, tagged `Deb_Oct 6 26`.

## Steps
1. Edit copy in `build_copy.py`; run it; every template must score Jev `human` >= 0.75 and `slop` <= 0.25 (the playbook Section 7 control scores 0.37 / 0.72).
2. Re-run `reoon_verify.py` if leads are older than 7 days.
3. Run `launch.py` (drafts), read back the campaigns, then `launch.py --activate`.

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
