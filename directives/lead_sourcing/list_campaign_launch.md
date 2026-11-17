# List Campaign Launch (Instantly) SOP

## Goal
Turn segment/tier lead CSVs plus an approved copy JSON into ready-to-fire Instantly campaigns (draft), deduped
against the whole workspace, with a separate one-command activation step run only on the operator's word.

## Inputs
- Plan JSON (`--campaigns`, kept with the client's private material): `tag_id`, `timezone` (Instantly enum;
  `America/Los_Angeles` is rejected, use `America/Dawson`), `window`, `allow_list` (CSV with `website`),
  `drop_list` (`{"domains": [], "names": []}`), `leads_dir`, `state`, `contacted_window_days`,
  `campaigns[{name, id?, segment, tier, daily_limit, daily_max_leads}]`.
- Copy JSON (`--copy`): `{"approved": bool, "verticals": {segment: {"steps": [{subject, body, delay}]}}}`.
  Bodies are plain text; follow-up steps use an empty subject (same thread). `delay` is days before the NEXT step
  (Instantly v2), so "email 2 three days later, email 3 five days after that" is `3, 5, 0`.
- Lead CSVs `<leads_dir>/<segment>_<bucket>.csv`: first_name, last_name, email, company_casual, website,
  email_tier, personalization_type, first_line.
- Env `INSTANTLY_API_KEY`.

## Tools/Scripts
`execution/lead_sourcing/list_campaign_launch.py` (HTTP via `execution/infrastructure/instantly_campaign_shell.py`'s curl client).
- default: filters + workspace dedupe, prints per-campaign counts and skip reasons, no writes.
- `--check`: read back campaigns (status, lead count, settings, rendered step-1 preview) and tagged inbox health.
- `--apply`: PATCH existing drafts (refuses unless status draft 0 / paused 2) or create new ones, upload leads
  (500/batch, `skip_if_in_workspace`), re-sync custom variables of leads already in the campaign when the CSV
  changed, tag the campaign, read back, exit non-zero unless every campaign is draft/paused.
- `--apply --activate --i-mean-it`: also starts them; refuses unless the copy JSON has `"approved": true`
  and each campaign has leads. Run only on the operator's explicit word.

## Filters and dedupe (in order, counted per campaign)
no personalization (type none / empty first_line) -> not on the batch allow list -> drop list (domain or name)
-> already in this campaign (no-op; re-run safe) -> email already anywhere in the workspace (every campaign and
lead list, fully paginated) -> company domain contacted within `contacted_window_days`. Max 2 contacts per company
is asserted on the input (exit if violated).

## Edge Cases
- Large JSON bodies must go to curl on stdin (`--data-binary @-`): 500 leads on argv hits E2BIG.
- New campaigns created by POST can come back with `link_tracking: null`; a second `--apply` PATCHes it to false.
  Always re-run `--apply` once and confirm the read-back shows explicit `false`.
- `{{company}}'s` renders "Solutions's" for names ending in s; handle in copy (or a possessive variable) before firing.
- Merge tags: `{{firstName}}`, `{{lastName}}`, `{{companyName}}` (built-in), plus custom `{{first_line}}`, `{{company}}`.
