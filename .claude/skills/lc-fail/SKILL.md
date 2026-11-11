---
name: lc-fail
description: Repair the LinkedIn connect job when a day failed (STOPPED / MISSING email, no email). Triggers on "LC fail", "lc fail", "linkedin connect failed", "linkedin connects broke", /lc-fail.
allowed-tools: Read, Bash, Grep, Glob
---
# LC fail

The operator says "LC fail" when a LinkedIn connect day went wrong. Fix it end to end; do not ask them to run anything you can run.

1. **On the Windows laptop** (this session runs there, or the "AntiGravity Project Space" folder is attached): from the repo root run `py execution\personal_workflows\linkedin_connect_send.py fix`. It prints the diagnosis, pulls the latest job files from `main`, signs in to LinkedIn only if the profile was logged out (a Chrome window; the operator types the password), re-registers the scheduled task (10:00 + 12:00 + 14:00 catch-ups, wake-to-run) and starts today's run. A day that already emailed stays a no-op.
2. **In a cloud session:** try `list_computer_folders` / `request_computer_folder` for the laptop's "AntiGravity Project Space" folder, then do step 1 there. If the laptop cannot be reached, reply in one line: "Double-click **LC fail.cmd** in the AntiGravity Project Space folder on the laptop." Also read today's `LinkedIn connects <date>` email subject (Gmail) and say what it reports.
3. Report back in at most 3 lines: what failed (from the diagnosis), what was repaired, and whether today's run started. If the diagnosis shows a LinkedIn warning (captcha, security check, weekly limit, restricted, HTTP 999), say the job paused itself for the day on purpose and nothing should be forced.

Never click LinkedIn buttons yourself, never edit `data/linkedin_connect/ledger.csv`, never delete the `emailed_<date>.txt` marker unless the operator asks for a second report. Directive: `directives/personal_workflows/linkedin_connect_send.md`.
