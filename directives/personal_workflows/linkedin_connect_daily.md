# LinkedIn Connect Daily — 25 connection requests/day from the operator's own browser

> **Status (2026-10-23):** built; audited; 21/21 evals pass; 4,959-person master loaded. **Live browser step exercised 2026-10-23 from Cowork: 14 sent, 1 skipped (no Connect button), stopped on an email-required dialog (now a skip, not a stop).** ~36 min for 15 profiles.
> **Runs in Cowork (local), never in a cloud session.** The cloud container has no LinkedIn login and a datacenter IP; a login from there trips LinkedIn's checkpoint. Cowork drives the operator's already-logged-in Chrome via the Claude in Chrome extension.
> **Risk statement (operator accepted 2026-10-23):** sending invitations with a tool is outside LinkedIn's User Agreement. Mitigation is pace and restraint, not concealment: ≤25/day, human-like gaps, stop on the first warning. No fingerprint spoofing, no proxy rotation, no multiple accounts.

## Goal

Every day, send connection requests to the next 25 unsent people from a consolidated master list, never twice to the same person, and hand the operator a four-field report (name, company, position, LinkedIn ID) in-session and by email.

## Inputs

- **Prospect CSVs** (Apollo exports; any column names work if a profile-URL column exists). They live on the operator's machine in the repo root and campaign subfolders ("Bay Area Recruitment Campaign 13 Oct 26/", "Recruitment City Wise/", "Campaign 24 Sep 26 Wellness/"). **Every run consolidates all of them again** (idempotent), so a new CSV dropped there is picked up with no further action. Files whose name contains `bounce` are email bounces, not people: skip them.
- **Shared state = Google Drive folder `linkedin_connect`** (owner's My Drive; find it with the Drive connector by title). Holds `ledger_<ISO datetime>.csv` snapshots (one per run, full copy) and `aliases.csv`. This is the only cross-machine state; **nothing under `data/linkedin_connect/` is ever committed** (repo is public; path is gitignored). No git credentials are needed in the daily loop.
- **Local working dir** `data/linkedin_connect/` (gitignored): `master.csv` rebuilt from the CSVs, `ledger.csv` synced from Drive, `queue_<date>.csv`, `report_<date>.md`.
- Operator's Chrome logged in to LinkedIn, Claude in Chrome extension connected (Cowork).

## Tools / Scripts

`execution/personal_workflows/linkedin_connect_queue.py` (no LinkedIn access, pure bookkeeping):

| Command | Does |
|---|---|
| `consolidate --in a.csv b.csv ...` | Merge into `master.csv`, slug-normalised, dedupe across files and against `aliases.csv`, fill blanks from later files. Re-runnable; new CSVs just add. |
| `sync --ledger f [--aliases f]` | Union rows from another ledger copy (a Drive snapshot, or a report `.md` with its ```ledger block) into the local ledger. Idempotent, never drops a row. Run it on every Drive snapshot before `plan`. |
| `plan [--limit 25]` | Write today's queue (or reprint the unfinished part). Hard cap 25, weekly soft cap 100 trims the day. Skips anyone with a final status; tops the queue back up after skips; `--shuffle` randomises order, seeded by date. |
| `mark <slug-or-url> --status sent\|skipped\|already_connected\|pending\|withdrawn\|retry [--note] [--canonical <slug>]` | Append to ledger; `--canonical` records the redirected slug in `aliases.csv` so consolidate and mark treat it as the same person. Refuses the 26th `sent` of the day (exit 3). Refuses a second entry for the same slug. |
| `report [--date]` | Four-field table of that day's sends followed by a ```ledger block with every row marked that day, so the emailed report alone can rebuild the ledger. |
| `status` | Counts. |
| `lock acquire\|release\|show` | Run lock; `acquire` exits 4 while a live (<120 min) lock exists. |
| `health [--json]` | Invariant check (exit 1 on breach); must be HEALTHY before any send. |

## Daily procedure (Cowork, `/linkedin-connect`)

0. **Pull state, no git.** `Q="python execution/personal_workflows/linkedin_connect_queue.py --data-dir data/linkedin_connect"`. (a) With the Drive connector, find the folder `linkedin_connect`, download every `ledger_*.csv` and `aliases.csv` into `data/linkedin_connect/drive/`, then `$Q sync --aliases drive/aliases.csv` and `$Q sync --ledger <each snapshot>`. (b) `$Q consolidate --in <every prospect CSV in the repo root and the campaign subfolders, excluding *bounce*>`. If the Drive connector is unavailable, fall back to the newest "LinkedIn connects" email: `$Q sync --ledger <saved report .md>`; the cloud reconcile task keeps Drive current.
1. `$Q lock acquire` (exit 4 → stop, another slot is running). `$Q health` (UNHEALTHY → guardrail 2). Then `$Q plan --shuffle` → list of ≤25. If it prints "0 to do", release the lock and stop quietly (a later slot on an already-finished day).
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
5. `$Q report` → paste the four-column table in the session **and** email the whole report file (table + ledger block) with the Gmail connector to the operator, subject `LinkedIn connects <date> (<n> sent)`.
6. **Push state, no git.** Upload `ledger.csv` to the Drive folder as `ledger_<YYYY-MM-DDTHHMM>.csv` (text/csv, no conversion) and, if aliases changed, upload a fresh `aliases.csv` after trashing the old one. Trash ledger snapshots older than the newest 7. If the Drive connector is unavailable, say so: the emailed ledger block is the fallback transport and the 10:27 CET cloud task uploads it.
7. `$Q status` → one line to the operator: remaining count and days left at 25/day. `$Q lock release`. No commit, no push.

## Scheduling — "runs when I log in", not "runs at 8"

The browser step can only happen while the operator's PC is awake and Chrome is logged in, and the operator logs in at unpredictable hours and time zones. So the schedule is **slots, not a time**: Cowork scheduled tasks at **08:00, 10:00, 12:00, 14:00, 16:00, 18:00, 20:00, 22:00 machine-local time**, each with the same prompt (`/linkedin-connect`). Every run is idempotent: the first slot after login does the day's work; every later slot syncs state, sees `0 to do`, and exits in under a minute. Local time follows the laptop, so CET, IST or GMT needs no change. If Cowork offers "run missed tasks when the computer wakes", turn it on; the slots still cover the case where it does not.

**Guardrails (all enforced in the script, not by the LLM):**
1. **Run lock** — step 1 begins with `$Q lock acquire`; exit 4 means another slot is mid-run → stop immediately, send nothing. Locks older than 120 min are treated as a crashed run and taken over. `lock release` is the last step of every run, success or failure.
2. **Health gate before sending** — `$Q health` must print HEALTHY before `plan`. UNHEALTHY → send nothing, email the health output to the operator with subject `LinkedIn connects <date> HEALTH FAIL`, release the lock, stop. Invariants: master present, no person with two final statuses, today's sent ≤ 25, 7-day sent ≤ 100, valid statuses, no orphan rows, lock not stale.
3. **State is Drive-first** — ledger snapshots in Drive are the truth; the local ledger is a cache rebuilt by `sync` at every run. (Validated the hard way 2026-10-23: a branch switch deleted the local `data/` dir; the Drive snapshot + emailed report rebuilt it byte-identically.)
4. **Daily cap and dedupe in code** — `mark` refuses the 26th send (exit 3) and any second final status for a slug; `plan` never queues a slug with a final status.
5. **Stop triggers** (step 3) end the day on LinkedIn's own warning signals; the email-required dialog is a skip, not a stop.
6. **Every day produces exactly one of three emails**: `LinkedIn connects <date> (<n> sent)`, `... HEALTH FAIL`, or nothing (PC never logged in). The 21:27 Europe/Paris cloud check turns "nothing" into a one-line message in the operator's Claude session, so a silent day is impossible.
7. **Pacing**: 45–120 s between profiles, feed detour every ~8, ≤25/day, ≤100/7 days. If acceptance rate falls under 25 % over two weeks, cut to 15/day.

**Failure matrix**

| Failure | Detected by | Outcome |
|---|---|---|
| PC asleep all day | 21:27 cloud check finds no email | One line in the operator's session; next login continues from the same queue |
| Two slots overlap | `lock acquire` exit 4 | Second slot exits without sending |
| Cowork crashes mid-run | stale lock (>120 min) | Next slot takes over; `retry` rows re-queue tomorrow; `sent` rows already in local ledger are re-synced to Drive by the next slot |
| Drive connector missing in Cowork | step 0 fallback | Ledger pulled from the newest emailed report; cloud check uploads to Drive |
| Local data dir lost | `health` master_present FAIL | consolidate + sync rebuild it; no sends until HEALTHY |
| Ledger corrupted / double rows | `health` FAIL | No sends; HEALTH FAIL email; operator session message |
| LinkedIn captcha / limit / restriction | step 3 stop | Day ends; verbatim text in the run email |
| Renderer freeze | navigate timeout | New tab, close old, continue |

## Monthly loop (dataset)

Export connections from LinkedIn (Settings → Data privacy → Get a copy of your data → Connections). Run `/jev-leads diff` on it against last month's export to see who accepted; join to the newest Drive ledger snapshot by slug for the acceptance rate. Save the export to the Drive folder as next month's snapshot.

## Edge cases / learnings

- Slugs are case-insensitive; the script lowercases. Numeric-suffixed slugs (`john-smith-1a2b3c`) are distinct people, keep them.
- Rows without a LinkedIn URL are dropped at consolidate time and counted in the summary; the operator gets that count, not a silent drop.
- A `sent` the browser could not confirm as `Pending`, or a profile that failed to load, is marked `retry` (non-terminal: out of today's queue, eligible from tomorrow). `skipped` is final.
- Columns are picked by content: the column whose values contain `linkedin.com/in/` wins, so Apollo exports with a separate `Company Linkedin` column and a `Company Website` column resolve correctly. `/company/`, `/pub/` and Sales Navigator URLs are not connectable and are counted as "no URL".
- Dataset loaded 2026-10-23: 15 Apollo CSVs, 11,126 rows → 4,959 unique people (6,163 cross-file duplicates removed, 4 rows without a profile URL). Five more CSVs on the operator's machine (Bay Area recruitment, recruitment_gb_fr_ne_ge_be, Recruitment_Cities CLEAN_relaunch, the two campaign folders) join automatically at the next local run via step 0b.
- Eval set: `execution/personal_workflows/tests/linkedin_connect_eval.py --data data/linkedin_connect/master.csv` (24 cases, deterministic table; results in `docs/reference/linkedin_connect/`). Run after any script change.
- **Browser hygiene (2026-10-23 run):** the Chrome renderer froze once (navigate and screenshot timed out, `find` still worked). Fix: open a new tab, close the frozen one, re-navigate; no double send resulted. The tab-group id can change mid-run ("not in Claude's tab group") → re-run the tabs-context tool. Gaps used were 59–119 s with one feed detour after profile 8.
- **Why Drive, not git (2026-10-23):** the repo is public (the first dataset commit exposed the prospect list; removed from HEAD the same day, history rewrite pending operator confirmation) and the Cowork shell has no GitHub credential. The daily loop touches git only to read the script. Code still ships via `git pull` on the operator's machine; if the local checkout is dirty, read the script from a worktree of origin/main instead of pulling.
- **Cloud reconcile task** ("LinkedIn connect: Drive ledger reconcile", daily 21:27 Europe/Paris, fires into the building session): if the Drive folder has no ledger snapshot dated today, it reads today's "LinkedIn connects" email, rebuilds the rows from its ledger block and uploads the snapshot; if there is no email either, it writes one line in the operator's session saying the PC never ran today. It never touches LinkedIn.
- The repo lives inside OneDrive on the operator's machine, which produces stale `.git/index.lock` files. Removing that file when no git process is running is safe and expected.
- Cloud session cannot run steps 2–3. If asked there, run `plan`/`report` and tell the operator to finish in Cowork.
