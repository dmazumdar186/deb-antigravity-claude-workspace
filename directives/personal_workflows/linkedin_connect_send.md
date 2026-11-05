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
| `... login` | Opens the job's Chrome profile on linkedin.com/login; waits (≤ 10 min) for the LinkedIn session cookie and closes the window by itself. |
| `... setup [--start]` | Windows, re-runnable: checks Gmail creds + master, runs `login` only if the profile has no session, registers the task (`-Force`, never doubled), `--start` fires it now. |
| `execution/personal_workflows/linkedin_connect_setup.cmd` | Double-click wrapper: `py -m pip install playwright python-dotenv`, then `setup --start`. |
| `execution/personal_workflows/linkedin_connect_queue.py` | Bookkeeping: `consolidate`, `plan`, `mark`, `status`, `health`. `run` calls its functions directly. Owns `DAILY_CAP = 20` (one source of truth). |
| Windows Task Scheduler | One task, registered once with the PowerShell block below. |

Constants: queue `DAILY_CAP = 20`; send script `SEND_DAYS = (0, 1, 3, 4, 5)`, `GAP_SECONDS = (45, 120)`, `MAX_CONSECUTIVE_RETRIES = 3`; queue `NO_CONNECT_DAYS = 3`, `VISIT_FACTOR = 2` (≤ 40 profiles per run), `RUN_BUDGET_S = 110 min`, `SMTP_ATTEMPTS = 3` / `SMTP_RETRY_S = 60`.

## Outputs

- **Email (the contract):** one per send day. Subject `LinkedIn connects <YYYY-MM-DD> (<n> sent)`; if the run stopped early, ` — STOPPED: <short reason>` is appended. Body = ONE HTML table (#, First name, Name, Company, Position, LinkedIn ID with link) and nothing else; the table may be empty. n = people marked `sent` that day.
- Ledger rows (and aliases for redirected slugs) via the queue module; `queue_<date>.csv`.
- `emailed_<date>.txt` marker and `send.log` in the data dir (log is for debugging; never emailed).
- `--dry-run`: no ledger writes, no marker, email written to `.tmp/linkedin_connect_<date>.eml`; n = people it would have sent to.

## One-time setup (operator, Windows)

**Double-click `execution\personal_workflows\linkedin_connect_setup.cmd`** in the repo folder on the
laptop. It installs Playwright with the `py` launcher, opens Chrome on the LinkedIn login page if the
job's profile has no session (sign in; the window closes by itself), registers the task "LinkedIn connect
send" (Mon Tue Thu Fri Sat 10:00, `StartWhenAvailable`, `IgnoreNew`, 3 h limit, Interactive logon, the
same Python that ran setup) and starts today's run. Re-running it is safe: an existing session is kept and
the task is replaced, not doubled. The only operator input is the LinkedIn sign-in (a credential).

Why a double-click and not Claude: the cloud cannot start a Windows process. The Cowork slot's "device
shell" is a Linux sandbox with the repo folder mounted (`/sessions/<id>/mnt/...`), and its only browser
path is Claude-in-Chrome, whose clicks the app's auto-mode reviewer denies (2026-11-05, again, even with
the task set to bypass permissions). The sandbox can write files into the folder, so it can deliver the
latest scripts; only Windows can run them.

Old routine: the three "LinkedIn connect slot" tasks and the 20:00 cloud report task were disabled on
11-03 (cutover step 0) and must stay disabled; the 20:00 task is now the missing-report alert below.

To remove the task: `Unregister-ScheduledTask -TaskName "LinkedIn connect send" -Confirm:$false`

`GMAIL_SMTP_USER` and `GMAIL_SMTP_APP_PASSWORD` must be in `.env` (they already are if job_digest emails work).

## Steps (what `run` does)

1. Today's local date (same as the queue module's ledger dates). Not a send day, or `emailed_<date>.txt` exists → exit 0 silently.
2. (Real run) no Gmail credentials → log, exit 3 (the only silent failure; the alert below catches it). No `master.csv` or Playwright not importable → email `STOPPED: no master list` / `STOPPED: playwright not installed`, no marker (a rerun after the fix still sends today), exit 3.
   Another run holds `send.lock` (exclusive create, < 120 min old; older = crashed run, taken over) or the retired routine's `run.lock` → exit 0 without sending; `send.lock` is deleted on every exit path.
3. Plan up to 20 − already sent today with `cmd_plan` (shuffled, seeded by date; same queue file as before).
4. Launch the persistent profile in Google Chrome (`channel="chrome"`, headed). Chrome missing or the profile in use → email `STOPPED: Chrome not available`, exit 3.
5. For each person: open the profile URL, wait for the header to render, then decide (first match wins):
   1. captcha / "security check" / `/checkpoint/` URL / "weekly invitation limit" / "restricted your account" → **stop the day**, mark nothing.
   (Warnings are read only inside dialogs / alerts, plus the `/checkpoint/` URL; a profile's own text never triggers a stop.)
   2. login / authwall page, or a "Sign in" + "Join now" page → **stop: not logged in**.
   3. 404 / "This page doesn't exist" → `skipped profile_gone`.
   4. Header shows `Pending` → `pending`. 1st-degree badge → `already_connected`.
   5. `Connect` in the header, else open `More` and look for `Connect` in the menu. Neither → `retry no_connect_button` (not final: a markup change must not burn people).
   6. Click Connect. Dialog asking for the member's email → Escape, `skipped email_required` (continue). Otherwise click **Send without a note** (or a plain `Send`; never "Add a note").
   7. Confirmed by the alert "Invitation sent…" or the header flipping to `Pending` → `sent`. No confirmation in 10 s → `retry` (eligible tomorrow).
   8. Page failed to load → `retry`. Three `retry` outcomes in a row (no Connect / unconfirmed / page load failed) → **stop** (`3 profiles in a row without Connect or confirmation`).
   9. Redirected to another `/in/` slug → the mark carries `--canonical`, so the alias is recorded.
6. Random 45–120 s pause between profiles. When the queue runs out after skips, re-plan until 20 are sent or nobody is left, but never past 40 profiles (`STOPPED: 40 profiles visited, cap not reached`) or 110 minutes (`STOPPED: time budget reached`).
7. Build the subject; if 0 were sent while people remained, the subject says `STOPPED: 0 sent while people remained`.
8. Send the email (3 attempts, 60 s apart), write the marker, exit (2 if stopped early).

## Edge Cases & Constraints

- **Overlap:** the task uses `MultipleInstances IgnoreNew`, and `run` takes `send.lock` (O_EXCL), so a manual `run` (or `setup --start`) while the task runs exits 0 without sending.
- **Missing report alert:** the cloud scheduled task "LinkedIn connect: missing-report alert" checks Gmail at 15:07 Europe/Paris on send days; no `LinkedIn connects <date>` email by then → it emails `LinkedIn connects <date> — MISSING: no run by 15:00`. Fail loud on delivery: a job that never starts (task missing, PC off, Gmail creds gone) can no longer look like a quiet day.
- **PC off at 10:00:** `StartWhenAvailable` runs it at the next logon the same day. The task runs only while the operator is logged on (Chrome needs the desktop session). A day the PC never wakes produces no email.
- **Run crashed:** still emails, subject `STOPPED: run failed (<error type>)`, exit 3, and writes no marker (same for `Chrome not available`), so a rerun after the fix sends the rest of today's batch. SMTP failing 3 times → no marker, exit 3, details in `send.log`.
- **Run length:** worst case ~3 min per profile (120 s gap + 45 s load + 10 s render + 10 s confirm); the 110-minute budget plus email retries ends every run well inside the task's 3 h `ExecutionTimeLimit`.
- **`no_connect_button` is `retry`:** a Follow-only profile comes back on a later day; on the 3rd different day `Q.mark` records it as final `skipped no_connect_button_3x`. If LinkedIn moves the Connect button, the run stops after 3 in a row instead of marking hundreds of people final.
- **Marker:** written only after the email succeeds; rerunning on the same day after that is a no-op. Delete the marker to force a second report.
- **Cap:** counted from the ledger, so a crashed run resumed the same day only tops up to 20. `Q.mark` refuses a 21st `sent` the same day (exit 3).
- **Date:** the laptop's local date, for gating and the ledger alike. A long stay in another time zone shifts the 10:00 start with the clock; nothing else changes.
- **Selectors are accessibility-based** (button names "Connect" / "Invite X to connect", "Pending…", "More actions", dialog "Send without a note", role=alert). The header is scoped to the first `<section>` in `<main>` so "People also viewed" Connect buttons are never clicked. If LinkedIn changes its markup, the symptom is a run of `no_connect_button` skips or `retry`s → check `send.log`, update the regexes at the top of the script and the fixtures in `tests/fixtures/linkedin/`.
- **Logged out:** the session cookie lives in `chrome_profile/`; if LinkedIn logs the profile out, the email says `STOPPED: not logged in` — rerun `login` (or the setup .cmd). `login`/`setup` trust the cookie only after `/feed` loads without a login/authwall/checkpoint bounce, so a revoked cookie still opens the sign-in page.
- **Python:** `setup` registers the resolved `sys.executable`; it refuses the Microsoft Store Python (`\WindowsApps\`), which Task Scheduler cannot start.
- The old runbook's "every ~8 profiles, open the feed" detour is not carried over (not in the operator's requirements).
- Tests: `python -m pytest tests/test_linkedin_connect_send.py` (offline; fixtures driven in Playwright Chromium).

## Retired

**Disabled before the first run** (setup step 0); **deleted** only after the first real email is
confirmed, so they can be re-enabled if the first run fails:

- The three device-bound Claude scheduled tasks "LinkedIn connect slot 08:00 / 12:00 / 18:00".
- The cloud task "LinkedIn connect: 20:00 daily report".
- Google Drive state sync (folder `linkedin_connect`: ledger snapshots, `aliases.csv`, `report_<date>.md`). The local data dir is now the only state; sync the newest Drive snapshot once before the first run (`linkedin_connect_queue.py sync --ledger <snapshot> --aliases <aliases.csv>`).
- TODO after cutover: delete `cmd_report`, `cmd_sync`, `cmd_lock`, `cmd_health` from `linkedin_connect_queue.py` (kept while the old routine still runs).

## Changelog

| Date | Change |
|------|--------|
| 2026-11-05 | Job had never run (setup not done; operator fired the disabled Cowork slot, click denied again). Added `setup [--start]` + `linkedin_connect_setup.cmd` (one double-click), auto-closing login, STOPPED email for missing master/Playwright, queue lock, optional dotenv; 20:00 report task repurposed as the 15:07 missing-report alert. |
| 2026-11-03 | Review round 1: `no_connect_button` → `retry` + stop after 3 retries in a row; ≤ 2× cap visits and a 110-min budget; SMTP 3 tries; local date (no Europe/Paris layer); Chrome only; install/uninstall moved to a PowerShell block here; cap moved to queue `DAILY_CAP = 20`; stop checks read dialogs/alerts only. |
| 2026-11-03 | Created. Replaces the Cowork/AI routine: Playwright script + one Windows scheduled task + Gmail SMTP; 20/day on Mon Tue Thu Fri Sat; STOPPED suffix on early stop. |
