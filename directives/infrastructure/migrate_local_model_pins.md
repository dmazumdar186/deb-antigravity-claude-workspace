# Migrate Local Model Pins (one-shot, Fable 5 → 5.1)

## Goal
Finish the 2026-09-01 Fable 5.1 migration on the Windows machine with zero operator
action: the two local files that override the repo's model pin —
`~/.claude/settings.json` and the workspace's `.claude/settings.local.json` — still
say `claude-fable-5` and must move to `claude-fable-5-1`; `~/.claude/rules/model-tier.md`
gets the tier-doctrine note appended.

## Inputs
- No CLI args. Windows detection via `os.name` / `OS` / `USERPROFILE`; `HOME` for the
  user `.claude` directory. Cloud/Linux containers are a silent no-op by design.

## Tools / Scripts
- `execution/infrastructure/migrate_local_model_pins.py`

## Outputs
- Rewrites the `"model"` pin in the two settings files (text-level replace of the
  exact quoted ID, result re-validated as JSON before writing — an unparsable or
  differently-pinned file is left alone).
- Appends the doctrine note to `model-tier.md` when it doesn't mention the new ID.
- One-shot stamp `.tmp/model_pin_migrated_fable51` (so the documented revert in
  `.claude/SETTINGS_NOTES.md` is never flipped back) and append-only log
  `.tmp/model_pin_migration.log`; one summary line on stdout, empty when a no-op.

## Steps
1. The standing instruction in CLAUDE.md (Environment section) has the first local
   Windows session run `py execution/infrastructure/migrate_local_model_pins.py`
   once, then remove that instruction line and re-mirror AGENTS.md/GEMINI.md.
2. Nothing else. Repeat runs no-op on the stamp.

## Edge Cases
- **Revert stays a revert:** after the stamp exists, setting `"model":
  "claude-fable-5"` back (the documented rollback) is respected forever. A wiped
  `.tmp/` removes the stamp — if you reverted deliberately, keep the stamp file or
  delete this script.
- The cloud permission layer (2026-09-01) declined to auto-wire this into
  `session-start.sh`; the hook already carries the display plumbing for
  `MIGRATION_NOTE`, so a single line calling this script (exporting
  `MIGRATION_NOTE`) can be added locally later if hook-driven execution is wanted.
- Cloud sessions must never touch `~/.claude` — the Windows gate enforces this and
  the no-op path is verified; the Windows write path is exercised on first local run.

## Changelog
- 2026-09-01: Created (operator-ordered zero-HITL local follow-up of the Fable 5.1
  migration; logic in execution/ per the 3-layer architecture).
