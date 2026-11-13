# Instantly campaign shell (draft only)

**Goal:** set up a sending tag over existing inbox tags and create named draft campaigns with placeholder copy. Later, push the approved copy into them. This script never activates anything.

**Script:** `execution/infrastructure/instantly_campaign_shell.py` (uses curl, because Cloudflare blocks some Python clients). Needs env `INSTANTLY_API_KEY`.

**Inputs:** `--tag` (sending tag label), `--account-tags "A,B"` (existing inbox tags whose inboxes get the new tag), `--name` (repeat for each campaign), `--daily-limit` (default 290), `--timezone` (default `America/Dawson`), `--update-sequence-from steps.json` (`{"steps":[{"delay":0,"variants":[{"subject":"..","body":".."}]}]}`), `--apply` (without it the script does a dry run), `--check` (read-only).

**Behaviour (idempotent):**
- Reuses the tag if it already exists.
- Adds the tag only to inboxes that don't have it yet. Existing tags stay on.
- Skips a campaign that already exists under the same name. With `--update-sequence-from`, it only PATCHes `sequences`, and it refuses unless the campaign status is 0 (draft) or 2 (paused).
- Campaign settings: `email_tag_list=[tag]`, text only, open and link tracking off, unsubscribe header on, stop on reply, Mon-Fri 08:00-16:30, 3 placeholder steps with delays 0/3/5 days.
- Reads the campaign back and prints its status, settings, step count and whether it has leads. Exits non-zero if the status is not draft or paused.

**Edge cases / learnings:**
- In account tag mappings, `resource_id` is the inbox **email** (`resource_type` 1). To list an inbox tag, use `GET /accounts?tag_ids=`.
- Instantly's timezone enum rejects `America/Los_Angeles`, `Vancouver`, `Tijuana` and `Santa_Isabel`. `America/Dawson` is accepted, and existing campaigns already use it. Dawson is UTC-7 all year, so during PST (Nov-Mar) the window runs 1h earlier in Pacific time. Fix it in the UI if exact Pacific time matters.
- The API returns `link_tracking` and `stop_on_auto_reply` as `null`, which means off.
