---
description: Scaffold a new directive file from the standard template
---

Ask the user for:
1. Directive name (used as filename, e.g. `scrape_reddit`)
2. One-line goal summary

Then create `directives/<name>.md` using this template — do not deviate from the structure:

```markdown
# Directive: <Name>

## Goal
<One-line summary>

## Inputs
| Input | Type | Source |
|-------|------|--------|
|       |      |        |

## Tools / Scripts
| Script | Purpose |
|--------|---------|
|        |         |

## Output
- Location:
- Format:

## Steps
1.
2.
3.

## Edge Cases & Constraints

## Changelog
| Date | Change |
|------|--------|
| <today> | Created |
```

After creating the file, confirm the path with the user. Do not populate the content — leave it for the user to fill in unless they explicitly ask you to draft it.
