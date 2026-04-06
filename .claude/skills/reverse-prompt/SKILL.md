---
name: reverse-prompt
description: Before implementing any non-trivial build, ask the user 5+ dynamically generated clarifying questions to surface non-obvious preferences, assumptions, and constraints. Triggers on build/implementation requests, new features, new skills, new scripts, refactors, or any task that produces code or configuration.
allowed-tools: AskUserQuestion
---

# Reverse Prompt

## When to Trigger

Invoke this skill **before starting implementation** whenever the user asks to build, create, implement, or refactor something non-trivial. Do NOT trigger for:
- Simple lookups, research, or information gathering
- Single-line fixes, typos, or obvious bugs
- Tasks where the user has given exhaustive, specific instructions

## Process

### 1. Analyze the Request

Before generating questions, silently identify:
- **Stated requirements**: What the user explicitly asked for
- **Implicit assumptions**: What you're about to assume without being told
- **Decision points**: Where there are multiple valid approaches
- **Failure modes**: What could go wrong or feel wrong to the user
- **Taste-dependent choices**: Where personal preference determines the "right" answer

### 2. Generate 5+ Questions

Questions must be:

**Non-intuitive** -- Don't ask things the user already told you or would obviously think to specify. Bad: "What language should I use?" (obvious from context). Good: "Should this fail silently or loudly when X edge case happens?"

**High-impact** -- Each question should meaningfully change the implementation. Skip questions where the answer doesn't affect the code.

**Concrete** -- Reference specific scenarios, not abstractions. Bad: "How should errors be handled?" Good: "If the API returns a 429 rate limit, should we retry with backoff, queue for later, or skip and log?"

**Opinionated** -- Offer your recommended default with each question so the user can just say "yes" to most. Frame as "I'd default to X, want something different?"

**Categories to draw from** (pick what's relevant, not all):
- Edge case behavior (what happens when things go wrong)
- Scope boundaries (what's explicitly OUT of scope)
- Integration points (how this connects to existing systems)
- Output format/style preferences
- Performance vs. simplicity tradeoffs
- Dependencies and tooling preferences
- Security/privacy considerations
- Idempotency and state management

### 3. Ask Using AskUserQuestion

Use the `AskUserQuestion` tool to present questions. For each question:
- Keep the question text short and specific
- Put your recommended default as the first option with "(Recommended)" suffix
- Include 1-2 meaningful alternatives as other options

### 4. Proceed with Build

After receiving answers, incorporate them as hard constraints for the implementation. Do not re-ask or second-guess the answers. Just build.
