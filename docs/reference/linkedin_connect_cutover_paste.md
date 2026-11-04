Paste everything below the line into Claude Code on the Windows laptop, opened in the repo folder. It has no at-signs, and no line starts with a slash, hash or exclamation mark, so Claude Code will not treat it as a file mention, command or shell escape.

---

Task: switch the LinkedIn connect job to the Windows scheduled-task sender. The old Cowork slots are already disabled. Do not open LinkedIn yourself, and do not click anything on LinkedIn. Real invitations are sent only by Windows Task Scheduler, never by you.

Why: on 2026-10-30 and again on 2026-11-04, the app's safety reviewer blocked the "Send without a note" click, even with permissions fully bypassed. That click cannot be done by an AI agent. The deterministic replacement is execution/personal_workflows/linkedin_connect_send.py, and its directive is directives/personal_workflows/linkedin_connect_send.md. Read that directive first and follow its "One-time setup" section. The steps below are the same, with gates added.

Rules: every step is idempotent and safe to re-run. Stop at the first failed gate and tell me which gate failed, with the last 20 lines of output. Use the py launcher for every Python call.

1. Update the code. Run git fetch origin main, then git merge --ff-only origin/main. If the merge refuses, run git stash push -u -m "linkedin-connect cutover stash", then merge again. Never reset --hard. If a stale .git index.lock exists and no git process is running, delete it first.
   Gate: execution/personal_workflows/linkedin_connect_send.py exists.

2. Install the dependencies: py -m pip install playwright python-dotenv. Google Chrome must be installed. Do not run playwright install.
   Gate: py -c "import playwright, dotenv" exits 0.

3. Check the email settings. Confirm that .env has non-empty GMAIL_SMTP_USER and GMAIL_SMTP_APP_PASSWORD. Print only whether each one is set, never the values.
   Gate: both are set. If either is missing, stop and tell me. I will create a Gmail App Password myself.

4. Run the offline tests: py -m pytest tests/test_linkedin_connect_send.py -q
   Gate: all tests pass.

5. Log in to LinkedIn. Run py execution/personal_workflows/linkedin_connect_send.py login and tell me: "Log in to LinkedIn in the window that just opened, then close it." Wait until I say done. If data/linkedin_connect/chrome_profile already exists and I say I am already logged in, skip this step.

6. Dry run, the sandbox gate: py execution/personal_workflows/linkedin_connect_send.py run --dry-run
   This writes nothing to the ledger and sends no email. Wednesday and Sunday are rest days, so on those days it may just exit. In that case report the exit, then go to step 7 anyway.
   Gate: exit code 0. If a .tmp/linkedin_connect_<date>.eml file was written, its body is exactly one HTML table with nothing else around it, and it lists people who are not yet sent.

7. Register the Windows task. In PowerShell, from the repo folder, run the block in the directive's step 4. It uses -Force, so re-running replaces the task instead of duplicating it.
   Gate: Get-ScheduledTask -TaskName "LinkedIn connect send" shows the task, triggered weekly on Monday, Tuesday, Thursday, Friday and Saturday at 10:00.

8. Do not start the task now and do not run without --dry-run. The first real run is the next send day at 10:00.

When you finish, reply in one line: which gates passed, and the date of the next real run.
