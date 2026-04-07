# Directive: Documenter Agent

## Goal
After any script in `execution/` is created or significantly modified, sync the corresponding directive in `directives/` to reflect what the script actually does, any constraints discovered, and any edge cases handled.

## When to Invoke
Spawn this agent after:
- Creating a new execution script
- Fixing a bug that revealed an API constraint or edge case
- Refactoring a script in a way that changes its inputs, outputs, or behaviour

## Inputs
- Script name and category (e.g. `lead_sourcing/scrape_apollo.py`)
- Description of what changed and what was learned

## Steps

1. **Read the script** — Understand what it actually does, its inputs, outputs, and any error handling added.

2. **Find or create the directive** — The directive lives at `directives/{same_category}/{same_name}.md`. If it doesn't exist, create it using the standard directive template.

3. **Sync the directive** — Update the following sections to match reality:
   - **Inputs** — Reflect actual args, env vars, and data shapes the script expects
   - **Tools / Scripts** — Reference the script by path
   - **Output** — Reflect what the script actually produces
   - **Edge Cases & Constraints** — Add any API limits, timing quirks, or error conditions discovered
   - **Steps** — Update to match the actual flow of the script

4. **Update the Changelog** — Add a dated entry describing what changed.

5. **Update the notes file** — If a non-obvious constraint was discovered, also add it to `.claude/notes/execution/{category}/{script_name}.md`.

## Output
- Updated `directives/{category}/{name}.md`
- Optionally updated `.claude/notes/execution/{category}/{script_name}.md`

## Rules
- Do NOT rewrite the directive from scratch unless it's brand new. Preserve existing content and append/update.
- Do NOT add information you're not certain about. If the script doesn't handle a case, don't claim it does.
- Keep directive language in plain English — write like you're explaining to a smart colleague, not writing API docs.

## Changelog
| Date | Change |
|------|--------|
| 2026-04-07 | Created |
