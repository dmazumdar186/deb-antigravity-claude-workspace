---
name: linkedin-connect
description: Runs the LinkedIn connection-request script (20/day Mon Tue Thu Fri Sat via Windows Task Scheduler, one table email per run). Triggers on "linkedin connects", "send today's connection requests", /linkedin-connect.
allowed-tools: Read, Bash, Grep, Glob
---
# LinkedIn Connect

Follow `directives/personal_workflows/linkedin_connect_send.md`. The routine is a fixed script, not an AI task:

- `execution/personal_workflows/linkedin_connect_send.py run` is started by one Windows scheduled task at 10:00 on Mon, Tue, Thu, Fri and Sat (rest Wed and Sun). It sends up to 20 invitations (cap = `DAILY_CAP` in `linkedin_connect_queue.py`) from a dedicated Chrome profile, then sends ONE email: subject `LinkedIn connects <date> (<n> sent)` (plus ` — STOPPED: <reason>` if it stopped early), body = one table and nothing else.
- Do not click LinkedIn buttons yourself, and do not use the old Cowork slots, Drive sync or the 20:00 cloud report task (retired; see the directive).
- If asked to "send today's connection requests" by hand on the laptop: `python execution/personal_workflows/linkedin_connect_send.py run` (it no-ops on rest days or once today's email went out). `run --dry-run` clicks nothing and writes the email to `.tmp/`. `login` re-logs the Chrome profile in.
- Prospect lists: `linkedin_connect_queue.py consolidate --in <csvs>`; counts: `linkedin_connect_queue.py status`.
- Problems: read `data/linkedin_connect/send.log` and the STOPPED reason in the subject; the directive lists every reason and its fix.
