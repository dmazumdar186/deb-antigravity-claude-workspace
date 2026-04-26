---
description: Remind to run the test-suite skill after completing any new project, system, or feature build
paths:
  - "execution/**/*"
  - "tests/**/*"
  - "directives/**/*"
globs:
  - "**/*.py"
  - "**/*.sh"
  - "**/*.js"
  - "**/*.ts"
---

# Testing Rule

After completing any non-trivial build (new script, new feature, new system, new project):

1. Ask the user: "Want me to run the full test suite on this?" or invoke `/test-suite` if the user already requested testing
2. The `/test-suite` skill runs 6 tiers: Unit, Integration, E2E, Sanity, Performance, Monkey
3. Save test scripts to `tests/` so they can be re-run later
4. Fix any failures found — fix the code, not the tests (unless the test is wrong)
5. Re-run until all tiers pass

Never skip testing just because the code "looks correct." Run it.
