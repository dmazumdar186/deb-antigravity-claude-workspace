# safety-guard-mod

Function-hooks replacement for `.claude/hooks/safety-guard.sh`.

## What it hooks / draws
- `tool.call` on `Bash`: the escalation ladder below. A `.catch` denies if the guard fails or overruns.
- `ui.render` on `AbovePrompt`: a band (rule, exact command, "Allow once" / "Block") only while a step-3 decision is pending.
- `$.ui.toast` one line per rewrite. No network, no `$.http`.

## Ladder (every Bash call; commands with no trigger word pass straight through)
1. **Hard block** (checked first so no rewrite launders it): `rm` on `/`, `rm -r /`, `git push --force`, `git push -f `, `DROP TABLE`, `DROP DATABASE`, `format c:`, `mkfs`, `dd if=`, fork bomb. Silent `{ deny }`, logged `block`. The settings.json `permissions.deny` entries are hardcoded (see comment in `hooks/register.tsx`).
2. **Silent rewrite** (simple commands only: no quotes, `;`, `|`, `$`):
   - `rm [-rf] <paths>` → `mkdir -p state/.trash/<ts> && mv <paths> state/.trash/<ts>/`
   - `git reset --hard X` → `git stash push -u -m "safety-guard <iso>" ; git reset --hard X`
   - `git checkout -- .` → `git stash push -m ... ; git checkout -- .`
   - `git clean -f...` → `git clean -n...` with an explanatory comment
   Rewritable patterns that are too complex to rewrite (e.g. `echo "rm -rf ..."`) are blocked, matching the shell script.
3. **Band**: `DELETE FROM` (flagged when no WHERE), `truncate table`, other `git clean`, `rm` on absolute/`~`/`..`/glob-only paths. Default Block, auto-selected after 20 s via `$.clock.after`. Caveat: the engine's hook budget is 10 s and a `$.clock` wait counts against it, so in a live session an unanswered band ends at ~10 s through the `.catch`, which also denies (same outcome: Block). There is no Rewrite button: every rewritable command is already handled at step 2.

## State contract (`types/index.d.ts`)
`PluginState['safety-guard-mod']`:
- `ledger: { at, kind: 'rewrite'|'block'|'ask', rule, command, rewritten?, outcome? }[]` (last 500)
- `pending: { rule, command } | null` (drives the band)

A sibling such as `session-ledger-mod` lists `"safety-guard-mod"` under `dependencies` in its plugin.json (so the engine lays this contract into its `.claude-plugin/types`) and reads:
`const { value = [] } = await $.state.get({ plugin: 'safety-guard-mod', key: 'ledger' } as const)`.
Only this mod can write it.

## Disable
`/plugin`, then select safety-guard-mod and disable it. Re-enable the shell hook in `.claude/settings.json` if you remove the mod.

## Eval (claude plugin test, 2026-10-22)
| Row | Result |
|---|---|
| Dangerous handled | 10/10 (4 rewritten, 6 blocked) |
| Handled without prompt | 10/10 |
| Safe untouched | 10/10 |
| Latency, 100 safe calls | mean ~1.1-1.4 ms |
| Band auto-default at 20 s (mock clock) | Block |
