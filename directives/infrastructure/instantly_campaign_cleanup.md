# Instantly Campaign Cleanup

## Purpose

Recover a campaign paused by Bounce Protect after an unfiltered lead upload: delete every lead not on a verified-safe allowlist, blocklist domains that already bounced, and resume the campaign.

## When to invoke

- Bounce Protect paused a campaign, or a CSV was uploaded without filtering on `status`, `is_safe_to_send`, `is_catch_all`.
- You have a filtered "safe" CSV of the leads that should remain.

## Inputs

- `campaign_id`: positional UUID.
- `--keep-csv`: CSV whose `Email` column is the allowlist (case-insensitive). Required.
- `--bounces-csv`: Instantly bounce export, `Lead` column. Optional.
- `--also-remove`: text file, one email per line, forced deletions. Optional.
- `--resume`: activate the campaign after cleanup.
- `--no-dry-run`: actually write. Default is dry run (counts only).
- `--api-key-env` (default `INSTANTLY_NOTIFIER_API_KEY`), `--env-file` (default `./.env`).
- `--out`: optional JSON summary path.

## Outputs

- JSON summary on stdout (and `--out`): `would_delete`/`deleted`, `would_blocklist`/`blocklisted`, `spared_replied`, `campaign_status`.
- One human line on stderr. Exit 0 ok, 1 API failure, 2 bad args.

## Exit Criteria (declarative — read this before claiming "done")

- Every remaining campaign lead's email is on the allowlist, or the lead replied / shows positive interest.
- Every bounced domain appears on the workspace blocklist.
- With `--resume`, `GET /campaigns/{id}` reports active status (1).

## Scripts (Layer 3)

- `execution/infrastructure/instantly_campaign_cleanup.py` (reuses `instantly_guard.py` client)
- Tests: `tests/test_instantly_campaign_cleanup_unit.py`

## Edge cases

- Always dry-run first and sanity-check `would_delete` against `campaign_leads - allowlist_size`.
- Leads with `reply_count` truthy or `lt_interest_status > 0` are never deleted (`spared_replied`).
- Leads with no `email` are skipped, never deleted.
- `--also-remove` overrides the allowlist.
- Malformed bounce addresses (no local part, bad domain) are ignored, never blocklisted.
- Deletes chunk at 100 IDs; blocklist bulk-create chunks at 1000.

## Changelog

- 2026-10-09: Created after a Bounce Protect pause caused by an unfiltered CSV upload.
