# Directive: Note Taker

## Goal
Capture atomic, scannable learnings to `.claude/notes/` whenever something non-obvious is discovered during a session — API quirks, user preferences, patterns that worked, or errors that were fixed.

## When to Invoke
Triggered by `.claude/hooks/note-taker.sh` after edits to `directives/` or `execution/` files.
Also invokable manually when you discover something worth saving.

## Note Categories

| Tag | When to use |
|-----|------------|
| `[preference]` | User expressed a preference ("I want X", "don't do Y") |
| `[technical]` | API quirk, rate limit, undocumented behaviour |
| `[learned]` | Fixed an error and discovered root cause |
| `[pattern]` | Found a reusable approach that worked well |
| `[constraint]` | Hard limit discovered (max chars, max rows, auth scope) |

## Note Format
```
- [tag] Subject: Detail. Source/date if relevant.
```

## Where to Write

| Situation | Write to |
|-----------|---------|
| Cross-cutting (applies everywhere) | `.claude/notes/general.md` |
| Specific directive | `.claude/notes/directives/{category}/{directive_name}.md` |
| Specific script | `.claude/notes/execution/{category}/{script_name}.md` |

## Steps

1. **Identify what was learned** — Ask: "Would a future Claude benefit from knowing this without re-discovering it the hard way?"

2. **Choose the right file** — Use the table above. If the notes file doesn't exist, create it.

3. **Write one atomic note** — One line per learning. Don't write paragraphs.

4. **Update `general.md`** if the learning applies broadly across multiple directives or scripts.

## What NOT to capture
- Things already documented in the directive or script
- Things obvious from reading the code
- Temporary state or in-progress work

## Changelog
| Date | Change |
|------|--------|
| 2026-04-07 | Created |
