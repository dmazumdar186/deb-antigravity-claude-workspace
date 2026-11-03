# Directive: LinkedIn Connect Send

> Replaces `linkedin_connect_daily.md` (AI agent clicking each button through Cowork). Why: `docs/reference/linkedin_connect_audit_2026-11-03.md` — the app's safety reviewer started blocking the Send click on 10-30; the fix is to move the deterministic clicking into a script (audit fix B) and make a blocked day loud (fix C).
> **Risk statement (operator accepted 2026-10-23, unchanged):** sending invitations with a tool is outside LinkedIn's User Agreement. Mitigation is pace and restraint, not concealment: ≤20/day, 45–120 s gaps, stop on the first warning. No fingerprint spoofing, no proxy rotation, no multiple accounts.

## Goal

On each send day (Mon, Tue, Thu, Fri, Sat; rest Wed and Sun) send connection requests to the next 20 unsent people in the master list (≈100/week, LinkedIn's observed free-account weekly limit), never twice to the same person, and email the operator one table when the run finishes.

## Inputs

| Input | Type | Source |
|-------|------|--------|
| `master.csv`, `ledger.csv`, `aliases.csv` | CSV | data dir (default `<repo>/data/linkedin_connect`, env `LINKEDIN_CONNECT_DIR`; gitignored, PII). Built by `linkedin_connect_queue.py consolidate`. |
| `chrome_profile/` | Chrome user-data dir | data dir; logged in to LinkedIn once with `login`. Dedicated to this job (nothing else is logged in there). |
| `GMAIL_SMTP_USER` | env (`.env`) | Gmail address that sends the report (same var as job_digest). |
| `GMAIL_SMTP_APP_PASSWORD` | env (`.env`) | Gmail App Password for that address (Google Account → Security → App passwords). |
| `LINKEDIN_CONNECT_EMAIL_TO` | env (optional) | Recipient; defaults to `GMAIL_SMTP_USER`. |

## Tools / Scripts

| Script | Purpose |
|--------|---------|
| `execution/personal_workflows/linkedin_connect_send.py run [--dry-run]` | The whole day: gate, plan, open each profile, act, mark, email, marker. Exit 0 ok / 2 stopped early / 3 config error. |
| `... login` | Opens the persistent profile on linkedin.com/login; log in, then close the window. |
| `... install` / `uninstall` | Registers / removes the one Windows scheduled task. |
| `execution/personal_workflows/linkedin_connect_queue.py` | Unchanged bookkeeping: `consolidate`, `plan`, `mark`, `status`, `health`. `run` calls its functions directly. |

Constants (top of the send script): `SEND_DAYS = (0, 1, 3, 4, 5)`, `DAILY_SEND_CAP = 20`, `RUN_AT = "10:00"`, `GAP_SECONDS = (45, 120)`.

## Outputs

- **Email (the contract):** one per send day. Subject `LinkedIn connects <YYYY-MM-DD> (<n> sent)`; if the run stopped early, ` — STOPPED: <short reason>` is appended. Body = ONE HTML table (#, First name, Name, Company, Position, LinkedIn ID with link) and nothing else; the table may be empty. n = people marked `sent` that day.
- Ledger rows (and aliases for redirected slugs) via the queue module; `queue_<date>.csv`.
- `emailed_<date>.txt` marker and `send.log` in the data dir (log is for debugging; never emailed).
- `--dry-run`: no ledger writes, no marker, email written to `.tmp/linkedin_connect_<date>.eml`; n = people it would have sent to.

## One-time setup (operator, Windows)

1. `pip install playwright python-dotenv tzdata` (Google Chrome must be installed; no `playwright install` needed).
2. `python execution/personal_workflows/linkedin_connect_send.py login` — log in to LinkedIn in the window that opens, then close it.
3. `python execution/personal_workflows/linkedin_connect_send.py install` — registers the task "LinkedIn connect send".

`GMAIL_SMTP_USER` and `GMAIL_SMTP_APP_PASSWORD` must be in `.env` (they already are if job_digest emails work).

## Steps (what `run` does)

1. Today's date in Europe/Paris. Not a send day, or `emailed_<date>.txt` exists → exit 0 silently.
2. No `master.csv` or (real run) no Gmail credentials → log, exit 3 before opening a browser.
3. Plan up to 20 − already sent today with `cmd_plan` (shuffled, seeded by date; same queue file as before).
4. Launch the persistent Chrome profile (`channel="chrome"`, headed; falls back to bundled Chromium with a log line).
5. For each person: open the profile URL, wait for the header to render, then decide (first match wins):
   1. captcha / "security check" / `/checkpoint/` URL / "weekly invitation limit" / "restricted your account" → **stop the day**, mark nothing.
   2. login / authwall page, or a "Sign in" + "Join now" page → **stop: not logged in**.
   3. 404 / "This page doesn't exist" → `skipped profile_gone`.
   4. Header shows `Pending` → `pending`. 1st-degree badge → `already_connected`.
   5. `Connect` in the header, else open `More` and look for `Connect` in the menu. Neither → `skipped no_connect_button`.
   6. Click Connect. Dialog asking for the member's email → Escape, `skipped email_required` (continue). Otherwise click **Send without a note** (or a plain `Send`; never "Add a note").
   7. Confirmed by the alert "Invitation sent…" or the header flipping to `Pending` → `sent`. No confirmation in 10 s → `retry` (eligible tomorrow).
   8. Page failed to load → `retry`; two consecutive load failures → **stop**.
   9. Redirected to another `/in/` slug → the mark carries `--canonical`, so the alias is recorded.
6. Random 45–120 s pause between profiles. When the queue runs out after skips, re-plan (≤5 passes) until 20 are sent or nobody is left.
7. Build the subject; if 0 were sent while people remained, the subject says `STOPPED: 0 sent while people remained`.
8. Send the email, write the marker, exit (2 if stopped early).

## Edge Cases & Constraints

- **Overlap:** the task uses `MultipleInstances IgnoreNew`; no lock file. A manual `run` while the task runs is not guarded — don't.
- **PC off at 10:00:** `StartWhenAvailable` runs it at the next logon the same day. The task runs only while the operator is logged on (Chrome needs the desktop session). A day the PC never wakes produces no email.
- **Run crashed / browser could not start:** still emails, subject `STOPPED: run failed (<error type>)`, exit 3. SMTP failure → no marker, exit 3, details in `send.log`.
- **Marker:** written only after the email succeeds; rerunning on the same day after that is a no-op. Delete the marker to force a second report.
- **Cap:** counted from the ledger, so a crashed run resumed the same day only tops up to 20. The queue module still enforces its own hard 25.
- **Time zone:** ledger dates use the Europe/Paris date (the run sets the queue module's day). Without `tzdata` on Windows the local date is used, with a warning in `send.log`.
- **Selectors are accessibility-based** (button names "Connect" / "Invite X to connect", "Pending…", "More actions", dialog "Send without a note", role=alert). The header is scoped to the first `<section>` in `<main>` so "People also viewed" Connect buttons are never clicked. If LinkedIn changes its markup, the symptom is a run of `no_connect_button` skips or `retry`s → check `send.log`, update the regexes at the top of the script and the fixtures in `tests/fixtures/linkedin/`.
- **Logged out:** the session cookie lives in `chrome_profile/`; if LinkedIn logs the profile out, the email says `STOPPED: not logged in` — rerun `login`.
- The old runbook's "every ~8 profiles, open the feed" detour is not carried over (not in the operator's requirements).
- Tests: `python -m pytest tests/test_linkedin_connect_send.py` (offline; fixtures driven in Playwright Chromium).

## Retired

Retired after the first verified run of this script (operator confirms the first real email):

- The three device-bound Claude scheduled tasks "LinkedIn connect slot 08:00 / 12:00 / 18:00".
- The cloud task "LinkedIn connect: 20:00 daily report".
- Google Drive state sync (folder `linkedin_connect`: ledger snapshots, `aliases.csv`, `report_<date>.md`). The local data dir is now the only state; sync the newest Drive snapshot once before the first run (`linkedin_connect_queue.py sync --ledger <snapshot> --aliases <aliases.csv>`).

## Changelog

| Date | Change |
|------|--------|
| 2026-11-03 | Created. Replaces the Cowork/AI routine: Playwright script + one Windows scheduled task + Gmail SMTP; 20/day on Mon Tue Thu Fri Sat; STOPPED suffix on early stop. |
