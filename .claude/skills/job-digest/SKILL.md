---
name: job-digest
description: Set up, preview, deploy, run, update, or debug a friend's shareable daily job-alert email (profile-driven, runs on their own GitHub Actions). Triggers on "job digest", "daily job email", "set up job alerts", /job-digest.
user_invocable: true
---

# Job Digest

Front door for the shareable job-digest engine. Full design and edge cases:
`directives/personal_workflows/job_digest.md`. Read it once per session before
`setup` or `deploy` if you have not already.

This skill runs in **two layouts** — resolve which one you're in before doing
anything else:

1. **Workspace layout** — this file lives at
   `.claude/skills/job-digest/SKILL.md` inside the
   `deb-antigravity-claude-workspace` repo. Engine at
   `execution/personal_workflows/job_digest/`. Module path for every command:
   `python -m execution.personal_workflows.job_digest.cli <subcommand> ...`
   run from the repo root — no `PYTHONPATH` changes needed.
2. **Standalone layout** — this file was installed into a friend's
   `~/.claude/skills/job-digest/`, bundled with the engine at
   `~/.claude/skills/job-digest/engine/job_digest/`. Every command becomes
   `python -m job_digest.cli <subcommand> ...` with
   `PYTHONPATH=~/.claude/skills/job-digest/engine` set for that invocation
   (export it once per shell, or prefix each command:
   `PYTHONPATH=<skill_dir>/engine python -m job_digest.cli ...`).

**Resolve ENGINE_DIR first, every invocation:** check whether
`execution/personal_workflows/job_digest/` exists relative to the current
working directory (workspace layout); if not, check whether
`<this skill's own directory>/engine/job_digest/` exists (standalone layout).
Use whichever is found to build the module path / `PYTHONPATH` above. If
neither exists, stop and tell the user the engine is missing.

Everything below writes `<cli>` for "the resolved command from step above"
(e.g. `python -m execution.personal_workflows.job_digest.cli` or
`PYTHONPATH=<engine_dir> python -m job_digest.cli`).

**Standing instruction — read this before `setup` or `deploy`:** a Claude Pro/
Max *subscription* does **not** provide an `ANTHROPIC_API_KEY`. API keys are
billed separately from console.anthropic.com. If the user only has a
subscription, do not set `ANTHROPIC_API_KEY` — the engine's heuristic ranker
(no key) and optional `GEMINI_API_KEY` (free tier) cover ranking without it.
The `/job-digest run` subcommand gets Claude-quality reranking for free by
using *this* session's subscription instead of a metered key — prefer it over
paying for `ANTHROPIC_API_KEY` unless the user wants the fully unattended cron
to also do LLM reranking on every run.

## Sub-commands

Parse the user's invocation as `/job-digest <subcommand> [args]`. Default to
`setup` if no subcommand was given and no `profile.yaml` exists yet in the
current directory; default to `preview` if a `profile.yaml` already exists and
no subcommand was given.

### `setup`

1. Check for an existing `profile.yaml` in the current directory; if present,
   confirm with the user before overwriting.
2. Prefer interviewing the user **conversationally** over running the wizard
   non-interactively: open `execution/personal_workflows/job_digest/profile_schema.py`
   (workspace layout) or `<engine_dir>/profile_schema.py` (standalone) and walk
   every field on `Profile` in order — `candidate.name`, `candidate.email`,
   1-3 `roles` (title + optional synonyms + seniority), `locations.countries`
   (1-5 ISO2, must be in `registry.COUNTRIES` — list the supported codes if
   the user is unsure), optional `locations.cities`, `locations.remote_ok`,
   `contracts`, `exclude`, `digest.max_jobs`/`hour_local`/`timezone`/
   `min_tier`, and `screening.summary` (40-4000 chars: what they do, years,
   domains, what they want next) plus optional `skills`/`must_have`/
   `nice_to_have`. Use sensible defaults from the schema and only ask about
   fields that materially change matching — don't force the user through
   every optional field one at a time if they'd rather give a paragraph and
   let you draft the YAML.
3. Alternative: if the user wants a scripted flow instead, run
   `<cli> setup` (the interactive `setup_wizard.py`) and let it prompt them
   directly.
4. Write the resulting `profile.yaml` to the current directory.
5. Run `<cli> validate profile.yaml`. If it reports problems, fix them with
   the user and re-validate — never hand off a profile that fails validation.

### `preview`

1. Run `<cli> preview profile.yaml` — this makes a **live** fetch against the
   real job sources (LinkedIn guest API, RemoteOK, WeWorkRemotely, and FR
   sources if selected) but has no side effects otherwise: no email sent, no
   sheet written, no state written. It is safe to run before `deploy` in that
   sense, but **run it at most once per hour** — LinkedIn's guest API blocks
   repeated identical fetches (999 responses), and other sources' per-country
   failures are isolated but still real network calls, not free to repeat.
   For an offline, no-network dry run against fixtures instead, use
   `<cli> run profile.yaml --mode dry` (writes no email/sheet/state either,
   but never touches the network).
2. Show the resulting table (roles matched, source counts, tier breakdown,
   sample rows) to the user as-is.
3. Ask explicitly: "does this look right?" Do not proceed to `deploy` until
   they confirm — a bad profile deployed to a real cron sends a friend a
   week of garbage email before anyone notices.

### `deploy`

Checklist, in order — stop and report if any step fails:

1. Verify `python3 --version` is 3.12+; if a `requirements.txt` is bundled
   with the engine, run `pip install -r requirements.txt` and confirm it
   succeeds.
2. Decide the repo name: `job-digest-<firstname>` (from `candidate.name`,
   lowercased, first token only). If `gh` is available
   (`gh auth status` succeeds), run
   `gh repo create <name> --private --confirm` (or the current gh syntax);
   otherwise print the manual steps (create a private repo on github.com,
   `git remote add origin ...`) and wait for the user to do it.
3. Copy into the new repo, in this order:
   a. `<engine_dir>` (this skill bundle's `engine/`, standalone layout) or
      `execution/personal_workflows/job_digest/` (workspace layout) →
      `<repo>/engine/job_digest/`, plus `<repo>/engine/requirements.txt`.
   b. The user's `profile.yaml` → `<repo>/profile.yaml`.
   c. `templates/gitignore_snippet.txt` → `<repo>/.gitignore` — **do this
      before the first commit**, so `credentials/`, `.tmp/`, and `__pycache__/`
      are never accidentally staged.
   d. The rendered workflow from `<cli> render-workflow profile.yaml`
      (standalone layout — the default) → `<repo>/.github/workflows/job_digest.yml`
      (cron converted from `digest.hour_local` + `digest.timezone` to UTC —
      GitHub Actions cron has no timezone support).
   Then `git add` **only** `profile.yaml`, `engine/`, `.github/`, and
   `.gitignore` — never `credentials/` (it holds the decoded service-account
   JSON at runtime, not at commit time, but never stage it if it happens to
   exist locally) and never anything not in this explicit list.
4. Set secrets with `gh secret set <NAME>` for each of: `GMAIL_SMTP_USER`,
   `GMAIL_SMTP_APP_PASSWORD` (required — needs 2-step verification enabled on
   the friend's Google account), and, only if the user opted in during setup,
   `GOOGLE_SERVICE_ACCOUNT_JSON_B64`, `SHEETS_SPREADSHEET_ID`,
   `GEMINI_API_KEY`, `ANTHROPIC_API_KEY` (see standing instruction above),
   `FRANCE_TRAVAIL_CLIENT_ID`, `FRANCE_TRAVAIL_CLIENT_SECRET`. **Never echo,
   log, or print a secret value** — read it from the user via a prompt the
   terminal doesn't echo back if possible, and never include it in a Bash
   command that gets logged in scrollback if a `gh secret set --body-file`
   or piped-stdin form is available instead.
5. Commit and push the repo.
6. Trigger a dry run first — `gh workflow run job_digest.yml -f dry_run=true`
   — and watch it succeed (check the Actions tab or `gh run watch`). Only
   after that dry run is green, confirm with the user and trigger a real run:
   `gh workflow run job_digest.yml` (no `dry_run` input, or `-f dry_run=false`).
   Never skip straight to a live run.

### `run`

Ad-hoc, local, one-off:

1. Run `<cli> run profile.yaml --mode live` in the current directory (needs
   the engine's dependencies installed locally; if a source needs a key that
   is not set, tell the user which one and continue with the sources that
   work).
2. Take the top 25 rows the engine produced and **review them yourself, in
   this session** — re-order by genuine fit and give each a one-line reason.
   This uses the user's Claude subscription, not an API key; do not ask them
   for `ANTHROPIC_API_KEY` for this step.
3. Show the re-ordered shortlist to the user.

### `update`

1. Locate the friend's deployed repo (ask if not obvious from context).
2. Re-copy `<engine_dir>` (this skill bundle's `engine/`) over the friend
   repo's `engine/` directory entirely (`<repo>/engine/`, i.e. both
   `engine/job_digest/` and `engine/requirements.txt`) — profile.yaml, state,
   and secrets are untouched.
3. Commit and push. Note in the commit message what changed if known.

### `doctor`

1. Run `<cli> doctor profile.yaml` and report what it finds.
2. Check the run log for the same failure signature recurring **more than 3
   times**. If so, per `.claude/rules/automation-boundaries.md`'s self-healing
   scope limit: investigate with full autonomy, propose (and, once the user
   agrees, apply) a fix, and append a change-log entry to **this skill's own**
   `.claude/skills/job-digest/CHANGELOG.md` — problem, solution, what was
   changed. Never rewrite workspace directives, rules, or the engine's
   execution scripts without separate operator approval; a skill doctoring
   itself is in scope, doctoring the shared engine is not.

## Friend-facing prose

Don't duplicate the friend's own setup narrative here — it lives (and should
be edited) in `templates/README_FRIEND.md` in the engine, which gets copied
into the deployed repo as `README.md` in the `deploy` step. Point the user at
the deployed repo's `README.md` for anything about running their own copy day
to day.

## When NOT to use this skill

- The user wants job alerts on the *operator's* own account/cron — that is a
  separate, isolated internal pipeline; do not touch it from here and do not
  import between the two.
- The user has no Google account for SMTP and does not want a Sheet — the
  engine still needs Gmail App Password delivery; there is currently no other
  delivery channel.
