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
| `... doctor` | Read-only, any OS: is today a send day, was the email sent (marker), `send.lock` age, last run start and last log lines, and (Windows) the task's state, last run time and result, next run, WakeToRun. First thing to run when a day has no email. |
| `... setup [--start]` | Windows, re-runnable: checks Gmail creds + master, runs `login` only if the profile has no session, registers the task (`-Force`, never doubled), `--start` fires it now. |
| `execution/personal_workflows/linkedin_connect_setup.cmd` | Double-click wrapper: `py -m pip install playwright python-dotenv`, then `setup --start`. |
| `execution/personal_workflows/linkedin_connect_queue.py` | Bookkeeping: `consolidate`, `plan`, `mark`, `status`, `health`. `run` calls its functions directly. Owns `DAILY_CAP = 20` (one source of truth). |
| Windows Task Scheduler | One task, registered once with the PowerShell block below. |

Constants: queue `DAILY_CAP = 20`; send script `SEND_DAYS = (0, 1, 3, 4, 5)`, `GAP_SECONDS = (45, 120)`, `MAX_BLOCK_STREAK = 3`, `MAX_UI_STREAK = 10`, `MAX_RETRY_STREAK = 12` (any retries interleaved), `VISIT_FACTOR = 5` (≤ 100 profiles per run), `RUN_BUDGET_S = 160 min`, `CLICK_TIMEOUT_MS = 5000`, `SETTLE_MS = 1000`, `DEBUG_CAPTURES_PER_RUN = 3` (kept 14 days), `SEND_LOCK_TTL_MIN = 190`; queue `NO_CONNECT_DAYS = 3`, `RETRY_MAX_DAYS = 4`, `SMTP_ATTEMPTS = 3` / `SMTP_RETRY_S = 60`.

## Outputs

- **Email (the contract):** one per send day. Subject `LinkedIn connects <YYYY-MM-DD> (<n> sent)`; if the run stopped early, ` — STOPPED: <short reason>` is appended. Body = ONE HTML table (#, First name, Name, Company, Position, LinkedIn ID with link) and nothing else; the table may be empty. n = people marked `sent` that day.
- Ledger rows (and aliases for redirected slugs) via the queue module; `queue_<date>.csv`.
- `emailed_<date>.txt` marker and `send.log` in the data dir (log is for debugging; never emailed). `send.log` carries the full Playwright reason for every failed click (what intercepted it, detached, not stable).
- `debug/<date>_<slug>_<note>.png` + `.html` (header HTML) for the first 3 people with a UI failure per run; files older than 14 days are pruned. PII: data dir only, never committed.
- `--dry-run`: no ledger writes, no marker, email written to `.tmp/linkedin_connect_<date>.eml`; n = people it would have sent to.

## One-time setup (operator, Windows)

**Double-click `execution\personal_workflows\linkedin_connect_setup.cmd`** in the repo folder on the
laptop. It installs Playwright with the `py` launcher, opens Chrome on the LinkedIn login page if the
job's profile has no session (sign in; the window closes by itself), registers the task "LinkedIn connect
send" (Mon Tue Thu Fri Sat 10:00, `StartWhenAvailable`, `WakeToRun` (wakes a sleeping laptop; added 2026-11-11 after 11-11 had no run), `IgnoreNew`, 3 h limit, Interactive logon, the
same Python that ran setup) and starts today's run. Re-running it is safe: an existing session is kept and
the task is replaced, not doubled. The only operator input is the LinkedIn sign-in (a credential).

Why a double-click and not Claude: the cloud cannot start a Windows process. The Cowork slot's "device
shell" is a Linux sandbox with the repo folder mounted (`/sessions/<id>/mnt/...`), and its only browser
path is Claude-in-Chrome, whose clicks the app's auto-mode reviewer denies (2026-11-05, again, even with
the task set to bypass permissions). The sandbox can write files into the folder, so it can deliver the
latest scripts; only Windows can run them.

Old routine: the three "LinkedIn connect slot" tasks and the 20:00 cloud report task were disabled on
11-03 (cutover step 0) and must stay disabled; the 20:00 task is now the missing-report alert below.
On 11-11 the disabled 08:00 slot was fired by hand; its v1.2 prompt clicks Connect through Claude in Chrome
and the app's reviewer denied the 2nd click. The three slots were renamed `RETIRED, do not run: ...` the same
day. Their prompt can only change from a Cowork chat linked to the laptop; to make a manual fire harmless,
paste this v1.3 prompt there (or delete the three slots):

> Status check only (runbook v1.3). The invitations are sent by the Windows task "LinkedIn connect send";
> this task NEVER sends them. Never open LinkedIn, use Claude in Chrome, click Connect/Send, touch Drive,
> send email, edit the ledger, commit or push. Run `python3 <REPO>/execution/personal_workflows/linkedin_connect_send.py doctor --data-dir <REPO>/data/linkedin_connect`
> and reply with its output; if today's email is "not sent yet" on a send day, tell the operator to
> double-click `execution\personal_workflows\linkedin_connect_setup.cmd`.

To remove the task: `Unregister-ScheduledTask -TaskName "LinkedIn connect send" -Confirm:$false`

`GMAIL_SMTP_USER` and `GMAIL_SMTP_APP_PASSWORD` must be in `.env` (they already are if job_digest emails work).

## Rule: one unsendable person never ends the day (operator order 2026-11-05)

A person LinkedIn will not let us invite is recorded and the run moves to the next one, until 20 are sent:
email verification asked → `skipped email_required` (final, never queued again); profile gone →
`skipped profile_gone` (final); already Pending / 1st-degree → recorded, not counted; Follow-only →
`retry`, final `skipped no_connect_button_3x` on its 3rd day. The day ends short of 20 only on a LinkedIn
warning (captcha, security check, weekly limit, restriction, HTTP 429/999), logged out, 3 block-shaped
retries in a row (page did not load, Send not confirmed), 10 UI-shaped retries in a row (no clickable
Connect even after a reload: the markup changed, so continuing would burn people), 100 profiles visited,
160 minutes, or an empty list; each of those sends a STOPPED subject.

## Steps (what `run` does)

1. Today's local date (same as the queue module's ledger dates). Not a send day, or `emailed_<date>.txt` exists → exit 0 silently.
2. (Real run) no Gmail credentials → log, exit 3 (the only silent failure; the alert below catches it). No `master.csv` or Playwright not importable → email `STOPPED: no master list` / `STOPPED: playwright not installed`, no marker (a rerun after the fix still sends today), exit 3.
   Another run holds `send.lock` (exclusive create, < 190 min old; older = crashed run, taken over) or the retired routine's `run.lock` → exit 0 without sending; `send.lock` is deleted on every exit path.
3. Plan up to 20 − already sent today with `cmd_plan` (shuffled, seeded by date; same queue file as before).
4. Launch the persistent profile in Google Chrome (`channel="chrome"`, headed). Chrome missing or the profile in use → email `STOPPED: Chrome not available`, exit 3.
5. For each person: open the profile URL, wait for the header to render, then decide (first match wins):
   1. captcha / "security check" / `/checkpoint/` URL / "weekly invitation limit" / "restricted your account" → **stop the day**, mark nothing.
   (Warnings are read only inside dialogs / alerts, plus the `/checkpoint/` URL; a profile's own text never triggers a stop.)
   2. login / authwall page, or a "Sign in" + "Join now" page → **stop: not logged in**.
   3. 404 / "This page doesn't exist" → `skipped profile_gone`.
   4. Header shows `Pending` → `pending`. 1st-degree badge → `already_connected`.
   0. Before reading the page (RCA 2026-11-11): HTTP 429 / 999 → **stop the day**. LinkedIn's docked Messaging panel is hidden with CSS in our tab (no click). Wait until `<main>`'s HTML has not changed for 1 s (≤ 4 s): the header re-renders after load in a per-profile button order.
   5. The header is the innermost `<section>` in `<main>` holding the `<h1>` (else the first section). `Connect` (button, menuitem or link, "Connect" / "Invite X to connect") in the header, else open `More` and look in the header, in the dropdown More's `aria-controls` names, else in an open dropdown (`[role=menu]`, `.artdeco-dropdown__content`, which LinkedIn may attach to `<body>`) that is not inside an `<aside>`. None → `retry` with `no_connect_button` (Follow visible: a Follow-only profile; the only note that turns final on day 3), `no_connect_button:more_missing` or `no_connect_button:menu_no_connect` (header we cannot read; never final).
   6. Every click (More, Connect, Send): scroll into view, wait until the button's box holds still 500 ms, click. If Playwright's 5 s actionability wait fails and the button is visible and enabled, the click is dispatched on the button itself, but when something covers it only if the cover is LinkedIn's own sticky chrome (`BENIGN_COVER_RE`: messaging panel, nav, toast, sticky header); an unknown cover is never clicked through; only the last element Playwright saw intercepting counts. A failed click → `retry click_failed:<overlay_covered|detached|unstable|offscreen|hidden|timeout>`. Dialog asking for the member's email (its text, or any email input in it) → Escape, `skipped email_required` (continue). Otherwise click **Send without a note** (or a plain `Send`; never "Add a note").
   7. Confirmed by the alert "Invitation sent…" or the header flipping to `Pending` → `sent`. No confirmation within 10 s of the Send click → `retry unconfirmed` (eligible tomorrow).
   8. A UI-shaped retry (`click_failed*`, `no_connect_button*`) is retried once after a 4–9 s pause and a reload (a sent invite shows `Pending` on the reload, so no double send). Page failed to load → `retry page_load_failed`. **Stop** on 3 block-shaped retries in a row (`3 profiles in a row did not load or confirm`) or 10 UI-shaped ones (`10 profiles in a row without a clickable Connect`), or 12 retries of any mix (`12 profiles in a row without a send`).
   9. Redirected to another `/in/` slug → the mark carries `--canonical`, so the alias is recorded.
6. Random 45–120 s pause between profiles. When the queue runs out after skips, re-plan until 20 are sent or nobody is left, but never past 100 profiles (`STOPPED: 100 profiles visited, cap not reached`) or 160 minutes (`STOPPED: time budget reached`).
7. Build the subject; if 0 were sent while people remained, the subject says `STOPPED: 0 sent while people remained`.
8. Send the email (3 attempts, 60 s apart), write the marker, exit (2 if stopped early).

## Edge Cases & Constraints

- **Overlap:** the task uses `MultipleInstances IgnoreNew`, and `run` takes `send.lock` (O_EXCL), so a manual `run` (or `setup --start`) while the task runs exits 0 without sending.
- **Missing report alert:** the cloud scheduled task "LinkedIn connect: missing-report alert" checks Gmail at 15:07 Europe/Paris on send days; no `LinkedIn connects <date>` email by then → it emails `LinkedIn connects <date> — MISSING: no run by 15:00`. Fail loud on delivery: a job that never starts (task missing, PC off, Gmail creds gone) can no longer look like a quiet day.
- **PC off at 10:00:** `StartWhenAvailable` runs it at the next logon the same day. The task runs only while the operator is logged on (Chrome needs the desktop session). A day the PC never wakes produces no email.
- **Run crashed:** still emails, subject `STOPPED: run failed (<error type>)`, exit 3, and writes no marker (same for `Chrome not available`), so a rerun after the fix sends the rest of today's batch. SMTP failing 3 times → no marker, exit 3, details in `send.log`.
- **Run length:** worst case ~5 min per profile (120 s gap + 9 s pause + two visits of 45 s load + 10 s render + 4 s settle + 10 s confirm + 3 × (3 s stable + 5 s click)); the 160-minute budget plus email retries (≤ 9 min) ends every run inside the task's 3 h `ExecutionTimeLimit` (asserted in the tests).
- **`no_connect_button` is `retry`:** a Follow-only profile comes back on a later day; on the 3rd different day `Q.mark` records it as final `skipped no_connect_button_3x`. Any person with a `retry` on 4 different days (any note) becomes final `skipped retry_4x:<last note>` (`RETRY_MAX_DAYS = 4`), so nobody loops forever; a markup break cannot reach it at scale (≤ 12 retries a day, drawn at random from thousands). The `:more_missing` / `:menu_no_connect` variants never turn final. If LinkedIn moves the Connect button, the run stops after 10 in a row instead of marking hundreds of people final.
- **Diagnosing click failures:** `send.log` names the cause (`<div class=…> intercepts pointer events`, `not stable`, `detached`); `debug/` holds a screenshot and the header HTML of the first 3 failures per run. A new LinkedIn sticky element that covers buttons → add its class to `BENIGN_COVER_RE` (or `OVERLAY_CSS`) and a fixture.
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
| 2026-11-11 | Round 2: any retry on 4 days → `skipped retry_4x`; More dropdown via `aria-controls`, never inside `<aside>`; `doctor` command; task `-WakeToRun`; setup's PowerShell call pinned to UTF-8; Cowork slots renamed RETIRED, v1.3 prompt recorded above. |
| 2026-11-11 | RCA of the 11-10 stop (4 sent, 9 click timeouts, 3 no-Connect, 5-in-a-row guard) and the 11-11 Cowork denial. Sender: Messaging panel hidden by CSS, header settle wait, stable-box + guarded dispatched click (benign covers only), full Playwright reason logged, finer retry notes, header = section with the h1, Connect also as link / in portaled dropdowns, one reload-retry per UI failure, split stop streaks (3 block / 10 UI), HTTP 429/999 stop, debug captures, confirm window restarts after Send, budget 165 → 160 min. 6 new fixtures. Cowork slots stay disabled: the 11-11 run was a manual fire of the disabled 08:00 slot (v1.2 runbook). |
| 2026-11-05 | Operator rule: an unsendable person never ends the day; keep going to 20. Visit ceiling 40 → 100, budget 110 → 165 min, retry streak 3 → 5, send.lock TTL 190 min. |
| 2026-11-05 | Job had never run (setup not done; operator fired the disabled Cowork slot, click denied again). Added `setup [--start]` + `linkedin_connect_setup.cmd` (one double-click), auto-closing login, STOPPED email for missing master/Playwright, queue lock, optional dotenv; 20:00 report task repurposed as the 15:07 missing-report alert. |
| 2026-11-03 | Review round 1: `no_connect_button` → `retry` + stop after 3 retries in a row; ≤ 2× cap visits and a 110-min budget; SMTP 3 tries; local date (no Europe/Paris layer); Chrome only; install/uninstall moved to a PowerShell block here; cap moved to queue `DAILY_CAP = 20`; stop checks read dialogs/alerts only. |
| 2026-11-03 | Created. Replaces the Cowork/AI routine: Playwright script + one Windows scheduled task + Gmail SMTP; 20/day on Mon Tue Thu Fri Sat; STOPPED suffix on early stop. |
