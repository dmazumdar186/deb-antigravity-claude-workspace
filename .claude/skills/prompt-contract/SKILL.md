---
name: prompt-contract
description: Before implementing any non-trivial task, generate a structured Prompt Contract (GOAL, CONSTRAINTS, FORMAT, FAILURE) that defines success, limits, output shape, and explicit failure conditions. Triggers on build/implementation requests, new features, skills, scripts, refactors, or any task that produces code or configuration. Also triggers on "contract", "prompt contract", or /prompt-contract.
allowed-tools: AskUserQuestion, Read, Grep, Glob, Bash, Edit, Write, TodoWrite
---

# Prompt Contract

## When to Trigger

Invoke this skill **before starting implementation** whenever the user asks to build, create, implement, or refactor something non-trivial. Do NOT trigger for:
- Simple lookups, research, or information gathering
- Single-line fixes, typos, or obvious bugs
- Tasks where the user has provided an explicit contract already (GOAL/CONSTRAINTS/FORMAT/FAILURE sections)
- Pure conversational or informational requests

## Process

### 1. Analyze the Request (silent, no output to user)

Before generating the contract, silently identify:
- **Success metric**: What does "done" look like? Find a number or concrete deliverable.
- **Implicit assumptions**: What are you about to assume without being told?
- **Hard limits**: Language, dependencies, file count, line count, performance targets
- **Output shape**: What files, formats, structures will be produced?
- **Failure modes**: What shortcuts would you be tempted to take? What edge cases would you skip? What "technically works but..." outcomes are possible?

### 2. Draft the Contract

Write a 4-section contract based on your analysis:

```
## Contract

GOAL: [Quantifiable success. Include a number or concrete deliverable.
       "Working X" is not a goal. "X that handles Y at Z performance" is.]

CONSTRAINTS:
- [Hard limit 1 -- language, deps, compatibility]
- [Hard limit 2 -- performance, size, complexity ceiling]
- [Hard limit 3 -- integration requirements, existing patterns to follow]
- [Add more if needed, but 3-5 is typical]

FORMAT:
- [Exact files to produce, with paths]
- [What each file contains]
- [Style: type hints, tests, docstrings -- only what's relevant]

FAILURE (any of these = not done):
- [Specific shortcut you'd be tempted to take]
- [Edge case that must be handled, not skipped]
- [Integration point that must actually work, not just compile]
- [The "technically works but..." outcome you must avoid]
```

### 3. Present for Approval

Show the contract to the user with two options:
- **"Looks good, build it"** -- Proceed with implementation
- **"Needs changes"** -- User provides feedback, you revise

One revision cycle max. If they have more feedback after that, just incorporate it and go.

### 4. Execute Against the Contract

Once approved:
1. Create a TodoWrite task list derived directly from the contract
2. Implement against the contract as a hard spec, not a guideline
3. Before marking the task complete, verify every FAILURE condition is avoided
4. The FAILURE section is a checklist: go through each item and confirm it doesn't apply

### 5. Self-Verify

After implementation, before reporting done:
- Re-read the FAILURE section
- For each failure condition, confirm with evidence (test output, code inspection, or logic) that it's been avoided
- If any failure condition is met, fix it before reporting done
- Do NOT report "done with caveats." Either all failure conditions are clear, or you're not done

## Contract Quality Rules

**GOAL must have a number or concrete deliverable.** Not "build a rate limiter" but "rate limiter handling 50K req/sec at <1ms p99."

**CONSTRAINTS must be hard limits, not preferences.** Not "should be fast" but "must respond in <200ms."

**FORMAT must be exact.** Not "some test files" but "5+ pytest tests in test_rate_limiter.py."

**FAILURE must catch shortcuts.** Think: "If I were lazy or rushed, what would I skip?" That's your failure condition.
