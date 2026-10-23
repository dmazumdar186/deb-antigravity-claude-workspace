# LinkedIn Connect Daily — 25 connection requests/day from the operator's own browser

> **Status (2026-10-23):** built; audited; 21/21 evals pass; 4,959-person master loaded. **Live browser step exercised 2026-10-23 from Cowork: 14 sent, 1 skipped (no Connect button), stopped on an email-required dialog (now a skip, not a stop).** ~36 min for 15 profiles.
> **Runs in Cowork (local), never in a cloud session.** The cloud container has no LinkedIn login and a datacenter IP; a login from there trips LinkedIn's checkpoint. Cowork drives the operator's already-logged-in Chrome via the Claude in Chrome extension.
> **Risk statement (operator accepted 2026-10-23):** sending invitations with a tool is outside LinkedIn's User Agreement. Mitigation is pace and restraint, not concealment: ≤25/day, human-like gaps, stop on the first warning. No fingerprint spoofing, no proxy rotation, no multiple accounts.

## Goal

Every day, send connection requests to the next 25 unsent people from a consolidated master list, never twice to the same person, and hand the operator a four-field report (name, company, position, LinkedIn ID) in-session and by email.

## Inputs

- One or more CSVs from the operator. Any column names work if a LinkedIn profile URL column exists; name (or first+last), company and title/headline are picked up by alias (`ALIASES` in the script).
- Data dir: **`data/linkedin_connect/`** (repo-tracked so Cowork on the Windows machine and cloud sessions share one master + ledger; pass `--data-dir data/linkedin_connect`, or set `LINKEDIN_CONNECT_DIR`). Script default is `.tmp/linkedin_connect/` for throwaway runs. **Pull before, commit + push after every run** or two machines will double-send. Holds `master.csv`, `ledger.csv`, `queue_<date>.csv`, `report_<date>.md`. **Back it up**: copy `master.csv` + `ledger.csv` to Google Drive weekly; losing the ledger means risking duplicate requests.
- Operator's Chrome, logged in to LinkedIn, Claude in Chrome extension connected.

## Tools / Scripts

`execution/personal_workflows/linkedin_connect_queue.py` (no LinkedIn access, pure bookkeeping):

| Command | Does |
|---|---|
| `consolidate --in a.csv b.csv ...` | Merge into `master.csv`, slug-normalised (`linkedin.com/in/<slug>` lowercased), dedupe, fill blanks from later files. Re-runnable; new CSVs just add. |
| `plan [--limit 25]` | Write today's queue (or reprint the unfinished part). Hard cap 25, weekly soft cap 100 trims the day. Skips anyone with a final status; tops the queue back up after skips; `--shuffle` randomises order, seeded by date. |
| `mark <slug-or-url> --status sent\|skipped\|already_connected\|pending\|withdrawn\|retry [--note] [--canonical <slug>]` | Append to ledger; `--canonical` records the redirected slug in `aliases.csv` so consolidate and mark treat it as the same person. Refuses the 26th `sent` of the day (exit 3). Refuses a second entry for the same slug. |
| `report [--date]` | Markdown table of that day's sends, four fields + profile link. |
| `status` | Counts. |

## Daily procedure (Cowork, `/linkedin-connect`)

1. `git pull`, then `python execution/personal_workflows/linkedin_connect_queue.py --data-dir data/linkedin_connect plan --shuffle` → list of ≤25. If it prints "0 still to do", go to step 6.
2. For each person in the printed order:
   a. Navigate to `linkedin_url` in the logged-in tab. Wait for the profile to render; read the primary action button.
   b. **Normal case (13 of 14 on the first run): header shows `Follow` / `Message` / `More`, and `Connect` is inside the `More` menu.** Open More → Connect → in the dialog choose **Send without a note**. Confirmation is either the alert "Invitation sent to <First>." or the header button flipping to "Pending, click to withdraw invitation" — both are readable from the accessibility tree; no screenshot needed → `mark <slug> --status sent`.
   c. `Connect` directly in the header → same as (b). `Pending` → `mark --status pending`. `Message` with the 1st-degree badge → `mark --status already_connected`. `Follow` only and no Connect in More → `mark --status skipped --note no_connect_button`.
   c2. Dialog "To verify this member knows you, please enter their email to connect" → Escape, `mark --status skipped --note email_required`, **continue**. This is that member's privacy setting, not an account warning (observed 2026-10-23, dan-dieffenbach-909582a; it cost 10 sends when treated as a stop).
   c3. LinkedIn redirected the URL to a different slug (e.g. `karthik-achari-54b347198` → `karthikachari`) → mark with the queue slug and add `--canonical <new-slug>` so a future export carrying the new slug is recognised as the same person.
   d. Profile 404 / "This page doesn't exist" → `mark --status skipped --note profile_gone`. Page timed out or Connect clicked but no `Pending` seen → `mark --status retry`.
   e. Wait a random **45–120 s** before the next profile (`Bash sleep`). Every ~8 profiles, open the LinkedIn feed or a notifications page once and scroll for a few seconds, then continue.
3. **Stop immediately** and mark nothing further if any of these appear: a captcha or "let's do a quick security check", "you've reached the weekly invitation limit", "we've restricted your account", or two consecutive page-load failures on different profiles. Report the trigger verbatim to the operator. Do not retry that day. (The email-required dialog is **not** a stop trigger; see 2c2.)
4. Stop at 25 `sent` regardless of how many were skipped; the script enforces it, don't argue with exit 3.
5. `report` → paste the table in the session **and** send it with the Gmail connector to debolshop@gmail.com, subject `LinkedIn connects <date> (<n> sent)`. Four columns only; nothing else goes in the mail.
6. `status` → one line to the operator: remaining count and days left at 25/day. Then `git add data/linkedin_connect && git commit -m "linkedin connects <date>" && git push`.

## Scheduling

- Cowork scheduled task, daily, in the operator's working hours (vary the minute; LinkedIn traffic at 03:00 looks like a bot). Prompt: `/linkedin-connect`.
- Also runs on demand when the operator opens Claude and says so. The queue file makes a second run on the same day a no-op beyond finishing the unfinished rows.
- Weekends are allowed (operator asked Mon–Sun). If acceptance rate drops below ~25 % over two weeks, cut to 15/day or pause; LinkedIn weights low acceptance as spam.

## Monthly loop (dataset)

Export connections from LinkedIn (Settings → Data privacy → Get a copy of your data → Connections). Run `/jev-leads diff` on it against last month's export to see who accepted; join to `ledger.csv` by slug for the acceptance rate. Save the export as next month's snapshot.

## Edge cases / learnings

- Slugs are case-insensitive; the script lowercases. Numeric-suffixed slugs (`john-smith-1a2b3c`) are distinct people, keep them.
- Rows without a LinkedIn URL are dropped at consolidate time and counted in the summary; the operator gets that count, not a silent drop.
- A `sent` the browser could not confirm as `Pending`, or a profile that failed to load, is marked `retry` (non-terminal: out of today's queue, eligible from tomorrow). `skipped` is final.
- Columns are picked by content: the column whose values contain `linkedin.com/in/` wins, so Apollo exports with a separate `Company Linkedin` column and a `Company Website` column resolve correctly. `/company/`, `/pub/` and Sales Navigator URLs are not connectable and are counted as "no URL".
- Dataset loaded 2026-10-23: 15 Apollo CSVs, 11,126 rows → 4,959 unique people (6,163 cross-file duplicates removed, 4 rows without a profile URL). At 25/day that is ~199 days.
- Eval set: `execution/personal_workflows/tests/linkedin_connect_eval.py --data data/linkedin_connect/master.csv` (20 cases, deterministic table). Run after any script change.
- **Browser hygiene (2026-10-23 run):** the Chrome renderer froze once (navigate and screenshot timed out, `find` still worked). Fix: open a new tab, close the frozen one, re-navigate; no double send resulted. The tab-group id can change mid-run ("not in Claude's tab group") → re-run the tabs-context tool. Gaps used were 59–119 s with one feed detour after profile 8.
- **Dirty local checkout:** if `git pull --ff-only` fails on local modifications, do not stash the operator's files. Use a worktree of origin/main (`git worktree add --detach <dir> origin/main`), run there, and remove it afterwards (`git worktree remove <dir>`). The ledger commit lives in the shared `.git` either way.
- **Push from Cowork needs a credential.** The Cowork shell has no credential helper or `gh`. Until a fine-grained GitHub token (contents: read/write on this repo) is set as `GH_TOKEN` in Cowork's environment and `git config credential.helper` points at it, step 6 ends with the commit local and the run report tells the operator; the next cloud session reconciles the ledger from the report. Never skip the commit.
- The repo lives inside OneDrive on the operator's machine, which produces stale `.git/index.lock` files. Removing that file when no git process is running is safe and expected.
- Cloud session cannot run steps 2–3. If asked there, run `plan`/`report` and tell the operator to finish in Cowork.
