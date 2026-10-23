---
name: linkedin-connect
description: Daily LinkedIn connection-request routine (25/day from the operator's logged-in Chrome via Cowork, ledger-tracked, four-field report by email). Triggers on "linkedin connects", "send today's connection requests", /linkedin-connect.
allowed-tools: Read, Bash, Grep, Glob
---
# LinkedIn Connect

Follow `directives/personal_workflows/linkedin_connect_daily.md` exactly. Summary:

1. State comes from the Google Drive folder `linkedin_connect`, never from git: download every `ledger_*.csv` + `aliases.csv`, `sync` them in, `consolidate --in` every prospect CSV on this machine (skip `*bounce*`), then `plan --shuffle`. Script: `execution/personal_workflows/linkedin_connect_queue.py --data-dir data/linkedin_connect`.
2. In the operator's logged-in Chrome (Claude in Chrome / Cowork only; never from a cloud session): open each profile; Connect is usually inside the **More** menu → **Send without a note**; confirm via the "Invitation sent" alert or `Pending`, then `mark <slug> --status sent` (add `--canonical <slug>` if LinkedIn redirected the URL). Email-required dialog → `skipped --note email_required`, continue. Other states map to `pending` / `already_connected` / `skipped`.
3. Random 45–120 s between profiles. Stop on the first captcha, limit notice, or restriction message and report it verbatim.
4. `report` → paste in session and email the four-column table to the operator via Gmail.
5. Upload `ledger.csv` to the Drive folder as `ledger_<ISO datetime>.csv` (and `aliases.csv` if changed). `status` → one line: remaining and days left. Nothing under `data/linkedin_connect/` is ever committed.

The script enforces the 25/day cap and refuses duplicate slugs. Never bypass exit 3.
