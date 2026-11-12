---
id: 2026-11-07-gitignore-build-dir-override
triggers: gitignore, build folder, deliverable, node test, missing files
scope: code
strength: 1
status: active
created: 2026-11-07
confirmed: 2026-11-07
source: .claude/notes/general.md
supersedes:
---
A deliverable folder named build/ is hidden by the global gitignore and needs a `!path/build/` override; run Node tests with a quoted glob.

Why: GreenJobs build pack 2026-11-07: build/ was ignored and `node --test <dir>` failed MODULE_NOT_FOUND.
