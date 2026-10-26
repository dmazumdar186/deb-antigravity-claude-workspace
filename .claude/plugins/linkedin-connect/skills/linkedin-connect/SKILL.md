---
name: linkedin-connect
description: Daily LinkedIn connection-request routine (25/day from the operator's logged-in Chrome on the laptop, ledger in Google Drive, one-table report emailed at 20:00 by a cloud task). Triggers on "linkedin connects", "send today's connection requests", /linkedin-connect. Self-contained for Cowork scheduled runs.
---
# LinkedIn Connect — self-contained runbook (v1.1, 2026-10-26)

You run as a scheduled Cowork task bound to the operator's Windows laptop ("Claude Desktop (Windows)"). Three slots fire per day (08:00, 12:00, 18:00 Europe/Paris, operator order 2026-10-26); every run is idempotent, so the first slot after the operator logs in does the day's work and later slots find nothing to do and exit. Nothing here needs a git credential or a repo checkout.

## Output contract (non-negotiable)
The operator receives one report email per day, at 20:00 Europe/Paris, sent by a separate cloud task, whose body is the table printed by `Q report` and **nothing else**. **You (a slot) never email the report.** Your job is to upload `report_<date>.md` to Drive; the 20:00 task emails it. No heading, no counts, no notes, no status lines, no ledger rows, no explanation of skipped profiles ever go in that file. Everything operational (skips, retries, counts, remaining, problems) goes in your final session reply. The only email a slot may send is `HEALTH FAIL`.

## Preconditions (check, do not assume)
- A shell that runs **on the laptop** (device shell). If only a cloud shell exists, stop: reply "No device shell; cannot run on the laptop today" and do nothing else.
- Chrome on the laptop logged in to LinkedIn, reachable through the Claude in Chrome tools. If unavailable, stop with one line saying so.
- Google Drive and Gmail connectors.

## Fixed values
- Repo folder on the laptop: `C:\Users\deban\OneDrive\Documents\AntiGravity Project Space`. Call it REPO. Python is `python`.
- Script: `REPO\execution\personal_workflows\linkedin_connect_queue.py`. Refresh it first without pulling: `git -C REPO fetch origin main` then `git -C REPO show origin/main:execution/personal_workflows/linkedin_connect_queue.py > REPO\execution\personal_workflows\linkedin_connect_queue.py` (if git is wedged by a stale `.git\index.lock` with no git process running, delete the lock and retry; if git still fails, `curl -sSL -o <that path> https://raw.githubusercontent.com/dmazumdar186/deb-antigravity-claude-workspace/main/execution/personal_workflows/linkedin_connect_queue.py`).
- Data dir: `REPO\data\linkedin_connect` (gitignored; never commit anything under it). `Q` below means `python REPO\execution\personal_workflows\linkedin_connect_queue.py --data-dir REPO\data\linkedin_connect`.
- Drive folder `linkedin_connect`, id `1y5LRuJ8qRJ2VITMS2hUDae315s7cwi06`: holds `ledger_<YYYY-MM-DDTHHMM>.csv` snapshots and `aliases.csv`.
- Report: `REPO\data\linkedin_connect\report_<YYYY-MM-DD>.md`, uploaded to the Drive folder under that name (overwrite the same day's file). The 20:00 cloud task emails it to debolshop@gmail.com, subject `LinkedIn connects <YYYY-MM-DD> (<n> sent)`.
- Caps: 25 sends/day (script-enforced), 100/7 days, 45–120 s between profiles.

## Steps
0. **Pull state.** Drive connector: search `parentId = '1y5LRuJ8qRJ2VITMS2hUDae315s7cwi06'`. Download `aliases.csv` and every `ledger_*.csv` (small files) and write them to `REPO\data\linkedin_connect\drive\`. Then `Q sync --aliases drive\aliases.csv` and `Q sync --ledger <each snapshot>`. Then rebuild the master: `Q consolidate --in <every *.csv under REPO root and under the folders "Bay Area Recruitment Campaign 13 Oct 26", "Recruitment City Wise", "Campaign 24 Sep 26 Wellness", excluding any file whose name contains bounce>`.
1. **Gate.** `Q lock acquire` (exit 4 → another slot is running: stop silently). `Q health` (UNHEALTHY → email its output to the operator with subject `LinkedIn connects <date> HEALTH FAIL`, `Q lock release`, stop). `Q plan --shuffle` → list of ≤25 people with URLs. If it prints `0 to do`: `Q lock release`, reply "Nothing to do today (already complete)", stop.
2. **Send, one profile at a time, in the printed order.** Navigate to the URL in the logged-in tab and read the primary action buttons from the accessibility tree.
   - Normal case: header shows Follow / Message / More, and **Connect is inside the More menu** → open More → Connect → in the dialog choose **Send without a note** → confirmation is the alert "Invitation sent to <First>." or the header flipping to "Pending" → `Q mark <slug> --status sent`. If LinkedIn redirected the URL to a different slug, add `--canonical <new-slug>`.
   - Connect in the header → same as above. Already "Pending" → `Q mark <slug> --status pending`. 1st-degree (Message with the 1st badge) → `--status already_connected`. Follow only, no Connect anywhere → `--status skipped --note no_connect_button`. Profile 404 → `--status skipped --note profile_gone`. Dialog "please enter their email to connect" → Escape, `--status skipped --note email_required`, continue. Page timed out or Connect clicked but no confirmation → `--status retry`.
   - Wait a random 45–120 s between profiles. After ~8 profiles open the LinkedIn feed once and scroll a few seconds. If a profile load freezes the renderer, open a new tab, close the frozen one, continue.
   - `Q mark` exit 3 means the daily cap is reached: stop sending.
3. **Stop for the day, mark nothing further**, if any of these appear: a captcha or "quick security check", "weekly invitation limit", "we've restricted your account", or two consecutive page-load failures on different profiles. Quote the text verbatim in the session reply (not in the email).
4. **Report file.** `Q report` writes `report_<date>.md` (the one table). Upload it to the Drive folder as `report_<date>.md` (text/markdown, no conversion), trashing any earlier same-day copy first so the 18:00 slot's version replaces the 08:00 one. Do not email it.
5. **Push state.** Upload `REPO\data\linkedin_connect\ledger.csv` to the Drive folder as `ledger_<YYYY-MM-DDTHHMM>.csv` (text/csv, disable conversion to Google type). If aliases changed, trash the old `aliases.csv` and upload the new one. Trash ledger snapshots beyond the newest 7. The Drive snapshot is the only state transport; if the upload fails, say so in the session reply (never in the email) and retry at the next slot.
6. `Q status` → one line **in the session reply only** (sent today, remaining, days left at 25/day; plus any skips/problems). `Q lock release`. No git commit, no git push.

## Never
Never email the report from a slot; never put anything but the `Q report` table in `report_<date>.md`; never send a note with the invitation; never exceed what `Q plan` printed; never bypass exit 3 or exit 4; never commit or push anything under `data\linkedin_connect`; never run from a cloud-only session.
