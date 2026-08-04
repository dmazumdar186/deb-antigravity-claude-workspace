# TEMPLATE_CHANGES.md

How to keep this template in sync with the evolving workspace rules.

## When to update

- A new always-active rule lands in `~/.claude/rules/`.
- An existing rule adds an exhibit that names a specific failure the
  template should structurally prevent.
- A new SAST rule ships in `execution/infrastructure/workspace_sast.py`.
- A new LLM tier / provider is added to `model_registry.py`.
- Astro / Cloudflare / Wrangler major-version bumps.

## What to check on each update

- Does the new rule require a new file in the template? (e.g. new hook,
  new test tier, new HANDOFF section)
- Does it require a change to `HARDENING.md`'s compliance list?
- Does it require a change to `.github/workflows/ci.yml`?
- Does the scaffolder (`../scaffold_web_app.py`) need to touch a new
  file / regex / env var?
- Do existing scaffolded projects need a backport? File a
  `HARDENING_BACKLOG.md` entry per `~/.claude/rules/rule-backport-cadence.md`.

## Template version

Bump `TEMPLATE_VERSION` in `scaffold_web_app.py` when this template
changes in a way that breaks existing scaffolded projects. Semver:

- **patch** — new optional file, doc-only change
- **minor** — new required file, new CI step (existing projects should
  backport but won't break)
- **major** — file rename, breaking layout change (existing projects
  need a migration guide in this file)

## Version history

- **v0.1.0** (2026-08-04) — initial scaffold, phase-4a of workspace hardening.

## Do NOT

- Do NOT auto-upgrade existing scaffolded projects when the template
  changes. Template version is pinned per-project in `.template-version`.
- Do NOT put project-specific logic into the template (goes in the
  scaffolded project instead).
- Do NOT skip a rule's compliance line in `HARDENING.md` because "it
  doesn't apply" — mark it explicitly as "N/A because ..." so the audit
  loop can verify.
