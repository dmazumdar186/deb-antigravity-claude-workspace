# Instantly Prune Finished Leads

## Goal
Free lead slots in the Instantly workspace (Hyper Growth plan, 25,000-lead cap) by deleting leads that finished
their sequence without replying, only in Debanjan's campaigns. Operator 2026-11-10: "just from campaigns under Deb
or Debanjan, nothing else, never touch other campaigns".

## Inputs
- Env `INSTANTLY_API_KEY`.
- Scope: campaigns that carry a custom tag starting with `Deb` (`Deb_03Sep26`, `Deb_Oct 6 26`, `Deb_16 Oct 26`,
  `Debanjan`) as a campaign tag. 2026-11-10: 44 campaigns; all 25 owned by the Debanjan workspace user are among them.

## Tools/Scripts
`execution/lead_sourcing/instantly_prune_finished.py` (dry run by default; `--apply --max N` deletes).

## Outputs
Backup CSV of every candidate lead (`.tmp/instantly_prune/backup_<ts>.csv`, written before any delete), ledger row.

## Steps
1. Dry run; read per-campaign counts and the backup path.
2. `--apply --max <slots needed>`.
3. Check `/workspace-billing/plan-details` `current_lead_count`.

## Edge Cases
- Deleted leads no longer count for `skip_if_in_workspace`, so a later campaign can re-contact them; unsubscribes
  stay blocked. Repliers, any interest status, bounced, unsubscribed and active leads are never deleted.
- The 2 Nov and 10 Nov 2026 campaigns are excluded by default (`--exclude`) while their performance is measured.
- 2026-11-10: status 3 (Completed) also covers colleagues of a replier stopped by stop_for_company ("domain_complete"), never emailed; 7 were deleted before the script required timestamp_last_contact and excluded domain_complete. They are in backup_20261110T105725Z.csv and were restored the same day into the lead list "Restored - stopped for company (do not contact)" with `instantly_restore_leads.py` (list, never a campaign: counts as in-workspace, nobody emails them).
- Bulk DELETE /leads removes at most 50 ids per call (asked 500, got 50); the script sends 50 at a time.
- Inline Bash calls to the Instantly leads API are blocked by the redteam hook; run this committed script.
