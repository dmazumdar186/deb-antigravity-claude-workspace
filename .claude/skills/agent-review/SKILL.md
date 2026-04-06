---
name: agent-review
description: Spawn a sub-agent to review, simplify, and verify output. Use after completing any non-trivial implementation task. Triggers on "review this", "agent review", "self-review", or /agent-review.
allowed-tools: Read, Grep, Glob, Bash, Edit, Write
---

# Agent-Reviews-Agent

Three-phase chain: **Implement -> Review -> Resolve**

## When to Use

After completing any non-trivial code change, refactor, or feature implementation. Skip for single-line fixes or config changes.

## Process

### Phase 1: Implement
Complete the task normally. Once done, proceed to Phase 2.

### Phase 2: Review
Spawn a reviewer agent with `subagent_type: "general-purpose"` and `model: "opus"`:

```
prompt: |
  You are a code reviewer with fresh eyes. You have NO sunk-cost bias.

  Review the following files for:
  1. **Correctness** -- bugs, logic errors, off-by-one, race conditions
  2. **Edge cases** -- null/undefined, empty inputs, boundary values, error paths
  3. **Simplification** -- unnecessary complexity, dead code, over-abstraction
  4. **Security** -- injection, XSS, secrets exposure, unsafe deserialization

  Files to review:
  {list changed files with full paths}

  Read each file carefully. For each issue found, output:
  - File and line number
  - Issue category (correctness/edge-case/simplification/security)
  - What's wrong
  - Suggested fix (concrete code, not vague advice)

  If the code is clean, say "No issues found" -- don't invent problems.
```

### Phase 3: Resolve
If the reviewer found issues:
- Apply fixes directly if they're clearly correct
- If a reviewer suggestion conflicts with the original intent, use your judgment. The reviewer has fresh eyes but lacks full context
- Re-read modified files after applying fixes to verify nothing broke

If the reviewer found no issues, you're done.

## Rules

- The reviewer agent must READ the actual files. Never pass code inline in the prompt (it may be stale)
- Don't skip Phase 2 because "the code looks fine." That's the whole point
- Keep the reviewer focused: list only the files that changed, not the entire codebase
- One review cycle is enough. Don't loop reviewers reviewing reviewers
