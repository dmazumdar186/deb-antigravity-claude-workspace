# job_search_notify.py Notes

Captured from .claude/upgrades/personal_workflows.md on 2026-06-12.

<!-- TODO: This file was seeded from the audit card's light-pass verdict.
     No deep gotchas are documented for this script yet. Extend next session if
     SMTP or notification-target issues are encountered. -->

- [pattern] SMTP-only, no LLM: This script is an SMTP-only notifier with no parallelism, no LLM calls, and no complex I/O. The audit card rates it "clean and correct." No upgrade axes apply.
- [technical] BLE001 justified: A broad `except Exception` at line 104 is intentional for non-fatal SMTP send failures — the script should not crash if the email delivery fails. The exception is caught with a log line (not a bare pass).
- [constraint] No directive: As of 2026-06-11, no `directives/personal_workflows/job_search_notify.md` exists. If the SMTP target, sender credentials, or notification format ever changes, create the directive to document the expected behavior.

## See also

- .claude/upgrades/personal_workflows.md
- .claude/notes/execution/personal_workflows/job_search_sheet.md
