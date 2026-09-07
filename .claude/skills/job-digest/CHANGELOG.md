# job-digest skill changelog

Scope: this file only covers changes to the skill's own instruction file
(`SKILL.md`) and this changelog, per the self-healing scope limit in
`.claude/rules/automation-boundaries.md`. Changes to the shared engine under
`execution/personal_workflows/job_digest/` are tracked in git history and
require separate operator approval — they are never made by the skill's
self-heal loop.

## 2026-09-06 — preview/deploy/update fixes

- `preview` now says explicitly that it makes a **live** fetch (not
  side-effect-free network-wise) and adds the "at most once per hour —
  LinkedIn's guest API blocks repeated fetches" caution; documents
  `run --mode dry` as the offline-fixture alternative for a true no-network
  check.
- `deploy` now copies `templates/gitignore_snippet.txt` to the friend repo's
  `.gitignore` **before** the first commit, and `git add`s only
  `profile.yaml`, `engine/`, `.github/`, `.gitignore` — never `credentials/`.
  Clarified the deploy step copies `<skill>/engine` → `<repo>/engine`.
- `update` now re-copies `<skill>/engine` over `<repo>/engine` in full
  (`engine/job_digest/` + `engine/requirements.txt`), not just the inner
  package.
- Deploy's dry-run-then-live sequencing spelled out with exact `gh workflow
  run` invocations for both.

## 2026-09-06 — initial version

- Created `SKILL.md` with sub-commands `setup`, `preview`, `deploy`, `run`,
  `update`, `doctor`, covering both the in-workspace layout (engine at
  `execution/personal_workflows/job_digest/`) and the standalone layout
  (engine bundled at `<skill_dir>/engine/job_digest/` for a friend's
  installation via `dist/job-digest-skill.zip`).
- No self-heal entries yet — `doctor` has not yet observed a recurring (>3x)
  failure signature.
