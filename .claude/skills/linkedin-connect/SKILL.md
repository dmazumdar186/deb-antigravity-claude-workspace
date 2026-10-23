---
name: linkedin-connect
description: Daily LinkedIn connection-request routine (25/day from the operator's logged-in Chrome via Cowork, ledger-tracked, four-field report by email). Triggers on "linkedin connects", "send today's connection requests", /linkedin-connect.
allowed-tools: Read, Bash, Grep, Glob
---
# LinkedIn Connect

Follow `directives/personal_workflows/linkedin_connect_daily.md` exactly. Summary:

1. `python execution/personal_workflows/linkedin_connect_queue.py plan` (new CSVs first: `consolidate --in ...`).
2. In the operator's logged-in Chrome (Claude in Chrome / Cowork only; never from a cloud session): open each profile, click **Connect → Send without a note**, confirm `Pending`, then `mark <slug> --status sent`. Other button states map to `pending` / `already_connected` / `skipped`.
3. Random 45–120 s between profiles. Stop on the first captcha, limit notice, or restriction message and report it verbatim.
4. `report` → paste in session and email the four-column table to the operator via Gmail.
5. `status` → one line: remaining and days left.

The script enforces the 25/day cap and refuses duplicate slugs. Never bypass exit 3.
