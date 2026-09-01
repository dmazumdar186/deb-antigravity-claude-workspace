---
name: prompt-contract
description: Generate a structured Prompt Contract (GOAL, CONSTRAINTS, FORMAT, FAILURE) before implementing any non-trivial task that produces code or configuration. Triggers on build/feature/refactor requests, "contract", or /prompt-contract.
allowed-tools: AskUserQuestion, Read, Grep, Glob, Bash, Edit, Write, TodoWrite, Task
user_invocable: true
---
> **Demo Library Skill** — This skill is from a demo library. Some configuration values use placeholders (e.g. `{{USER_NAME}}`, `{{COMMUNITY_ID}}`). If something doesn't work, check for placeholder values and replace them with your own information first.

# Prompt Contract

## When to Trigger

Invoke this skill **before starting implementation** whenever the user asks to build, create, implement, or refactor something non-trivial. Do NOT trigger for:
- Simple lookups, research, or information gathering
- Single-line fixes, typos, or obvious bugs
- Tasks where the user has provided an explicit contract already (GOAL/CONSTRAINTS/FORMAT/FAILURE sections)
- Pure conversational or informational requests

## Process

### 1. Analyze the Request (silent — no output to user)

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
- [Hard limit 1 — language, deps, compatibility]
- [Hard limit 2 — performance, size, complexity ceiling]
- [Hard limit 3 — integration requirements, existing patterns to follow]
- [Add more if needed, but 3-5 is typical]

FORMAT:
- [Exact files to produce, with paths]
- [What each file contains]
- [Style: type hints, tests, docstrings — only what's relevant]

FAILURE (any of these = not done):
- [Specific shortcut you'd be tempted to take]
- [Edge case that must be handled, not skipped]
- [Integration point that must actually work, not just compile]
- [The "technically works but..." outcome you must avoid]
```

### 3. Present for Approval

Show the contract to the user using `AskUserQuestion` with two options:
- **"Looks good, build it" (Recommended)** — Proceed with implementation using the contract as spec
- **"Needs changes"** — User provides feedback, you revise the contract

Keep the question concise. The contract itself is the detail — the question is just "approve or revise?"

If the user picks "Needs changes", revise and re-present. One revision cycle max — if they have more feedback after that, just incorporate it and go.

### 4. Execute Against the Contract

Once approved:
1. Create a TodoWrite task list derived directly from the contract
2. Implement against the contract as a hard spec — not a guideline
3. Before marking the task complete, verify every FAILURE condition is avoided
4. The FAILURE section is a checklist: go through each item and confirm it doesn't apply

### 5. Self-Verify

After implementation, before reporting done:
- Re-read the FAILURE section
- For each failure condition, confirm with evidence (test output, code inspection, or logic) that it's been avoided
- If any failure condition is met, fix it before reporting done
- Do NOT report "done with caveats" — either all failure conditions are clear, or you're not done

## Contract Quality Rules

**GOAL must have a number or concrete deliverable.** Not "build a rate limiter" but "rate limiter handling 50K req/sec at <1ms p99." If the task doesn't have an obvious number, use a concrete deliverable: "CLI tool that takes X input and produces Y output."

**CONSTRAINTS must be hard limits, not preferences.** Not "should be fast" but "must respond in <200ms." Not "keep it simple" but "under 150 lines total." If you can't measure it, it's not a constraint.

**FORMAT must be exact.** Not "some test files" but "5+ pytest tests in test_rate_limiter.py." Not "well-documented" but "docstring with 2 usage examples on the public class."

**FAILURE must catch shortcuts.** Think: "If I were lazy or rushed, what would I skip?" That's your failure condition. Common ones:
- No test for the unhappy path
- Hardcoded values that should be configurable
- Works for the demo case but breaks on empty/null/large input
- Missing error handling at integration boundaries
- "Works on my machine" — no consideration of deployment context

## Example

User: "Build a token bucket rate limiter"

```
## Contract

GOAL: Token bucket rate limiter handling 50K req/sec at <1ms p99 latency per check.

CONSTRAINTS:
- Pure Python, no external dependencies
- Thread-safe without asyncio
- Must work as both decorator and context manager
- Under 100 lines total including tests

FORMAT:
- Single file: active/execution/rate_limiter.py
- Includes dataclass config, implementation, and 5+ pytest tests
- Type hints on all public methods
- Docstring with usage examples

FAILURE (any of these = not done):
- No test for concurrent access
- Latency exceeds 1ms on 50K synthetic requests
- Allows >105% of rate limit through (5% tolerance)
- Missing edge case: what happens at exactly 0 remaining tokens
```
