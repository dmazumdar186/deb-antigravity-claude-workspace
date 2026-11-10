# Recruiter Campaign (Candidate Outreach System) SOP

## Goal
Launch `DM_Recruitment - {Location} - {Personalized|NoPersonalization}[ CatchAll] - 10 Nov 2026`
Instantly campaigns for recruiters in New York, New Jersey, Boston and Houston, in the 2 Nov 2026 DM_ playbook shape.

## Inputs
- Leads: `.tmp/recruiters/campaigns/` from `recruiter_leads.py` (directive `recruiter_leads.md`).
- Copy: `execution/lead_sourcing/recruiter_campaign/copy.json`, written only after the operator approves the
  email copy (operator supplies the content and the link).
- Env: `INSTANTLY_API_KEY`.

## Tools/Scripts
`execution/lead_sourcing/recruiter_campaign/launch.py`: plan only by default (no network); `--apply` creates drafts,
uploads leads in 500s with `skip_if_in_workspace`, tags `Deb_Oct 6 26`; `--apply --activate` starts them.
One campaign per location x personalization; agency and in-house share copy (operator 2026-11-10). An existing campaign with the same name is reused, never duplicated; upload counts must account for every lead or the run exits. State: `.tmp/recruiters/launch_state.json`.

## Outputs
Instantly campaigns (draft, then active), tagged `Deb_Oct 6 26`; `launch_state.json` with upload counts.

## Steps
0. Launch gate (operator 2026-11-10): Reoon-safe main leads after every drop must total >= 3,000; no launch before.
1. Operator approves copy; write `copy.json` and gate it per `/redteam`.
2. Re-run Reoon if leads are older than 7 days.
3. `launch.py` (plan) and check names and counts.
4. `launch.py --apply`; read the drafts back in Instantly.
5. `launch.py --apply --activate`.

## Edge Cases
- Settings copied from the live 2 Nov campaigns (read 2026-11-10): Mon-Fri 09:00-13:00 in each location's own time zone (America/Detroit for NY/NJ/Boston: Instantly has no America/New_York; America/Chicago for Houston),
  daily_limit 30, text only, open/link tracking off, stop on reply, stop for company, unsubscribe header on,
  steps day 0 / +2 / +1 days (as stored on DM_Fitout - US - Personalized).
- The 12 tagged inboxes are shared with every active DM_ campaign (~340 sends/day total).
- Earlier DM_Recruitment campaigns (13-14 Oct, agency copy) exist: replies 0-3 per ~300-570 sends.
- Spintax `{{RANDOM|a|b}}` without spaces around pipes; `tidy()` normalises it.
