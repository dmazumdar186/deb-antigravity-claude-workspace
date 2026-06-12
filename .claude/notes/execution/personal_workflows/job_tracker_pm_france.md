# job_tracker_pm_france.py Notes

Captured from .claude/upgrades/personal_workflows.md on 2026-06-12.

- [learned] Modal cron deploy: As of 2026-05-18, the Modal cron job was deployed and 32/32 tests pass. If the job silently fails or SIRENE/Firecrawl quota expires, no alert fires — there is no `/api/health` endpoint and no synthetic canary.
- [constraint] No canary: `--dry-run` flag exists (OK), but there is no scheduled synthetic canary monitoring the Modal cron for last-success age or board counts. Add one via cron-job.org or GH Actions schedule pointing at the Modal runs log.
- [technical] Exit criteria missing: The directive `directives/personal_workflows/job_tracker_pm_france.md` has no `## Exit Criteria` block with verifiable predicates. Add: "exit 0; `run_done` JSON logged; per_board count >= 1 for each enabled board; new_candidates persisted to DB."
- [technical] Sequential board scraping: Stage A scrapes 5 job boards sequentially. Each board is independent (fan-out = 5). Dynamic Workflow threshold is >5, so parallelism is MAYBE — current sequential approach is fast enough for a daily cron but note the pattern for when boards are added.
- [pattern] Hardening verified clean: No subprocess calls, no ThreadPoolExecutor, no bare `except: pass`. All except blocks have log calls. File I/O uses `encoding="utf-8"`. Pass on all 5 Windows hardening rules.

## See also

- .claude/upgrades/personal_workflows.md
- .claude/notes/execution/personal_workflows/job_search_sheet.md
- C:\Users\deban\.claude\projects\c--Users-deban-OneDrive-Documents-AntiGravity-Project-Space\memory\project_job_tracker_pm_france.md
