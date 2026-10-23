# LinkedIn Connect Daily — 25 connection requests/day from the operator's own browser

> **Status (2026-10-23):** built, dry-run tested on synthetic CSVs. Live browser step not yet exercised; first real run is the acceptance test.
> **Runs in Cowork (local), never in a cloud session.** The cloud container has no LinkedIn login and a datacenter IP; a login from there trips LinkedIn's checkpoint. Cowork drives the operator's already-logged-in Chrome via the Claude in Chrome extension.
> **Risk statement (operator accepted 2026-10-23):** sending invitations with a tool is outside LinkedIn's User Agreement. Mitigation is pace and restraint, not concealment: ≤25/day, human-like gaps, stop on the first warning. No fingerprint spoofing, no proxy rotation, no multiple accounts.

## Goal

Every day, send connection requests to the next 25 unsent people from a consolidated master list, never twice to the same person, and hand the operator a four-field report (name, company, position, LinkedIn ID) in-session and by email.

## Inputs

- One or more CSVs from the operator. Any column names work if a LinkedIn profile URL column exists; name (or first+last), company and title/headline are picked up by alias (`ALIASES` in the script).
- Data dir: `.tmp/linkedin_connect/` (gitignored; override with `--data-dir` or `LINKEDIN_CONNECT_DIR`). Holds `master.csv`, `ledger.csv`, `queue_<date>.csv`, `report_<date>.md`. **Back it up**: copy `master.csv` + `ledger.csv` to Google Drive weekly; losing the ledger means risking duplicate requests.
- Operator's Chrome, logged in to LinkedIn, Claude in Chrome extension connected.

## Tools / Scripts

`execution/personal_workflows/linkedin_connect_queue.py` (no LinkedIn access, pure bookkeeping):

| Command | Does |
|---|---|
| `consolidate --in a.csv b.csv ...` | Merge into `master.csv`, slug-normalised (`linkedin.com/in/<slug>` lowercased), dedupe, fill blanks from later files. Re-runnable; new CSVs just add. |
| `plan [--limit 25]` | Write today's queue (or reprint the unfinished part). Hard cap 25, weekly soft cap 100 trims the day. Skips anyone in the ledger. |
| `mark <slug-or-url> --status sent\|skipped\|already_connected\|pending\|withdrawn [--note]` | Append to ledger. Refuses the 26th `sent` of the day (exit 3). Refuses a second entry for the same slug. |
| `report [--date]` | Markdown table of that day's sends, four fields + profile link. |
| `status` | Counts. |

## Daily procedure (Cowork, `/linkedin-connect`)

1. `python execution/personal_workflows/linkedin_connect_queue.py plan` → list of ≤25. If it prints "0 still to do", go to step 6.
2. Shuffle the order. For each person:
   a. Navigate to `linkedin_url` in the logged-in tab. Wait for the profile to render; read the primary action button.
   b. `Connect` visible → click → in the dialog choose **Send without a note** → confirm the button flips to `Pending` → `mark <slug> --status sent`.
   c. `Pending` → `mark --status pending`. `Message` with the 1st-degree badge → `mark --status already_connected`. `Connect` only inside the **More** menu → open More, click Connect, then as (b). `Follow` only and no Connect anywhere → `mark --status skipped --note no_connect_button`.
   d. Profile 404 / "This page doesn't exist" → `mark --status skipped --note profile_gone`.
   e. Wait a random **45–120 s** before the next profile (`Bash sleep`). Every ~8 profiles, open the LinkedIn feed or a notifications page once and scroll for a few seconds, then continue.
3. **Stop immediately** and mark nothing further if any of these appear: a captcha or "let's do a quick security check", "you've reached the weekly invitation limit", "we've restricted your account", a dialog asking for the person's email to connect, or two consecutive page-load failures. Report the trigger verbatim to the operator. Do not retry that day.
4. Stop at 25 `sent` regardless of how many were skipped; the script enforces it, don't argue with exit 3.
5. `report` → paste the table in the session **and** send it with the Gmail connector to debolshop@gmail.com, subject `LinkedIn connects <date> (<n> sent)`. Four columns only; nothing else goes in the mail.
6. `status` → one line to the operator: remaining count and days left at 25/day.

## Scheduling

- Cowork scheduled task, daily, in the operator's working hours (vary the minute; LinkedIn traffic at 03:00 looks like a bot). Prompt: `/linkedin-connect`.
- Also runs on demand when the operator opens Claude and says so. The queue file makes a second run on the same day a no-op beyond finishing the unfinished rows.
- Weekends are allowed (operator asked Mon–Sun). If acceptance rate drops below ~25 % over two weeks, cut to 15/day or pause; LinkedIn weights low acceptance as spam.

## Monthly loop (dataset)

Export connections from LinkedIn (Settings → Data privacy → Get a copy of your data → Connections). Run `/jev-leads diff` on it against last month's export to see who accepted; join to `ledger.csv` by slug for the acceptance rate. Save the export as next month's snapshot.

## Edge cases / learnings

- Slugs are case-insensitive; the script lowercases. Numeric-suffixed slugs (`john-smith-1a2b3c`) are distinct people, keep them.
- Rows without a LinkedIn URL are dropped at consolidate time and counted in the summary; the operator gets that count, not a silent drop.
- A `sent` that the browser could not confirm as `Pending` must be marked `skipped --note unconfirmed`, never `sent`, so it is retried on a later day.
- Cloud session cannot run steps 2–3. If asked there, run `plan`/`report` and tell the operator to finish in Cowork.
