# Directive: Workspace Sync

## Goal
Keep the GitHub repo (`dmazumdar186/deb-antigravity-claude-workspace`) in sync with local work so any machine can pick up where the last left off.

## What Gets Committed
| Include | Exclude |
|---------|---------|
| `CLAUDE.md` | `.env` |
| `.claude/` (agents, skills, commands, memory) | `credentials/` |
| `execution/` scripts and `REGISTRY.md` | `.venv/` |
| `directives/` | `.tmp/` |
| `campaigns/` configs | `.archive/` |
| `personalizers/` | `*.pyc`, `__pycache__/` |
| `docs/`, `assets/`, `blueprints/` | WhatsApp images, zip files |

## Sync Rhythm
- Commit after every meaningful unit of work (new script, updated directive, new campaign config)
- Never commit broken code — scripts must pass `qa` agent before committing
- Never force-push to `main`

## Commit Message Format
```
<type>: <short summary>

<optional body>
```
Types: `feat` (new script/directive), `fix` (bug fix), `update` (changes to existing), `docs` (directive/readme updates), `config` (campaign/env changes)

Examples:
- `feat: add reddit scraper script for SaaS niche`
- `fix: handle empty response in instantly_upload.py`
- `update: directive for lead enrichment updated with pagination notes`

## Steps to Sync
1. Check status: `git status`
2. Stage specific files (never `git add .` blindly): `git add <files>`
3. Commit: `git commit -m "type: message"`
4. Push: `git push origin main`

## Changelog
| Date | Change |
|------|--------|
| 2026-04-06 | Created |
