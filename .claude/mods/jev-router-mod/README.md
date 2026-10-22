# jev-router-mod

A function-hooks mod that replaces the `.claude/hooks/jev-router.sh` UserPromptSubmit command hook with an in-engine equivalent.

## What it hooks

`prompt.submit`, main-loop prompts only (skips `origin.kind === 'plugin'`, slash commands, and text starting with `/`).
It reads `.claude/jev/state.json` with `$.fs.read` (absent = enabled; `"enabled": false` = pass through), then runs
`python3 execution/infrastructure/jev_router.py hook` through `$.process.run` with cwd = `$.session.root()`, a 10 s
timeout, and stdin `{"prompt": <text>, "session_id": <id>}`, the same JSON shape the shell hook pipes in.
If stdout carries `hookSpecificOutput.additionalContext`, the text is attached with
`next({ ...e, context: [...(e.context ?? []), additionalContext] })`. The types document `PromptSubmitInput.context` as
"what the model reads beside the prompt and the user never sees", which is how a UserPromptSubmit `additionalContext`
reaches the model. The prompt text is not changed. On any failure (non-zero exit, timeout, bad JSON, python missing)
it calls `next(e)` with the event untouched. It never drops or denies a prompt.

## What it draws

It draws a dimmed one-line AbovePrompt band, `jev → <tier>/<skill> · <first 80 chars of the routing line>`, with a **Hide** button.
The last decision is kept in the atom `last: { route, context, prompt, at } | null`.

## Network

The mod makes no network call and does not use `$.http`. The wrapped Python script still calls Jev on OpenRouter, the same way the shell hook did.

## Parity

`python3 tests/mods/jev_router_parity.py` runs each prompt in `tests/mods/jev-samples.json` through both
`bash .claude/hooks/jev-router.sh` and the mod's exact argv, then compares stdout. It prints two counts: an exact one and one with confidence digits masked. Jev is a live sampled model, so two runs of the shell hook against each other differ just as often (about 5/10 exact), and the masked count is the real gate.
`tests/register.test.tsx` stubs `process.run` and checks that the context reaches the engine and that the band renders.

## Disable

Disable the mod in `/plugin`, or run `/jev off`, which the mod honours too. If you use this mod, remove the shell hook
from settings so routing does not run twice.
