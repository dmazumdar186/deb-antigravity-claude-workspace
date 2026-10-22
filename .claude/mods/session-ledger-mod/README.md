# session-ledger-mod

A function-hooks mod that keeps a ledger of the session in a Pane beside the conversation and writes a workspace handoff file.

## What it hooks
- `session.start`: registers `/session-ledger` and opens the pane (`$.ui.open({ id: 'session-ledger' })`).
- `command.run` (`/session-ledger`): re-opens the pane.
- `prompt.submit`: remembers the first prompt (handoff slug = kebab of its first 4 words, else `session`).
- `tool.call`: records file paths of Edit / Write / MultiEdit / NotebookEdit (`file_path` / `notebook_path`, made relative to `$.session.root()`), Read/Edit/Write of `directives/**`, and each call's outcome (`ok` / `isError` / `deny`, last 50).
- `turn.complete` (main loop only): auto-handoff when >= 5 distinct files were edited and no handoff exists yet, or the edited-file count changed since the last one.
- `ui.render` on `{ component: 'Pane', requestId: 'session-ledger' }`.

## What it draws
1. Files edited this session, grouped by `execution/`, `directives/`, `deliverables/`, `projects/`, `.claude/`, `tests/`, other (count per group; paths truncated to the viewport rows).
2. Hooks fired: per-tool ok / isError / deny counts.
3. Safety-guard rewrites/blocks (from safety-guard-mod's state).
4. Directives touched.
5. A **Write handoff now** button.

## Handoff
Writes `.claude/handoffs/HANDOFF_<YYYY-MM-DD>_<slug>.md` via `$.fs.write` and toasts the path. Headings mirror `.claude/handoffs/2026-06-15-cv-optimizer-and-workspace-hardening.md`: `# Workspace Handoff — <date>`, `## Where we ended` (grouped files, hooks summary, safety-guard ledger), then `## What was NOT done today — gap list`, `## Lessons captured today (do NOT repeat)`, `## Live endpoints (for mobile spot-checks)`, `## Recommended next-session opening` (one-line placeholders for the operator).

## Dependency: safety-guard-mod state contract
`plugin.json` lists `safety-guard-mod` under `dependencies`. The mod reads `$.state.get({ plugin: 'safety-guard-mod', key: 'ledger' })`, typed `Array<{ at, kind: 'rewrite'|'block'|'ask', rule, command, rewritten? }>`. That contract is mirrored as an ambient `PluginState['safety-guard-mod']` declaration in `types/index.d.ts` (safety-guard-mod's own types were not yet written when this was built); keep the two in sync. If the read fails (plugin not loaded), the pane shows "safety-guard-mod not loaded".

## Disable
`/plugin` -> select `session-ledger-mod` -> Disable (or remove the folder from `.claude/mods/`).

## Measured outcomes (claude plugin test, 2026-10-22)
- File list match: 5/5 grouped under the right headings; flat set equals expected set.
- Handoff on `turn.complete`: exactly 1 file written (a second turn does not rewrite), headings correct, in order: yes.
- Write handoff now button: writes 1 file (`..._session.md`).
- 4/4 tests pass; `claude plugin validate` passes; `tsc` clean.
