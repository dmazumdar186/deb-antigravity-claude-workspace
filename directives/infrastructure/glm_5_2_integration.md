# GLM 5.2 Integration

Workspace-local source-of-truth for calling Z.AI's GLM 5.2 model. Cross-references the global cost-constraint clause + sensitivity guardrail in `~/.claude/rules/model-tier.md` (Exhibit C, 2026-06-22).

---

## Prior-art pass (per `~/.claude/rules/prior-art-first.md`)

**Trigger inspection**: Nick Saraev's 14:34 video [KAnDbJhNJ4E](https://www.youtube.com/watch?v=KAnDbJhNJ4E) demonstrates the full integration pattern end-to-end against three Claude-Code-shaped harnesses (Claude Code, Open Code, Crush).

**Public API check**: ✅ found. `https://openrouter.ai/api/v1/models` lists 11 Z.AI / GLM models. Flagship is `z-ai/glm-5.2`, 1,048,576 context, $0.000001/tok input. Anthropic-compatible spec — drops in via `ANTHROPIC_BASE_URL=https://openrouter.ai/api/v1` swap (Nick demo, 7:18).

**GitHub prior-art**: Z.AI publishes their own Anthropic-compatible endpoint at `https://api.z.ai/api/anthropic` — drop-in for Claude Code without an OpenRouter hop. Nick uses OR in his demo (cheaper at the moment for our usage), but Z.AI direct is one fewer middleman and a legitimate alternative if OR becomes a bottleneck.

**Best existing approach**: route via OpenRouter using the existing `OPENROUTER_API_KEY` and the existing `chat_completion()` function in `execution/modules/llm_client.py`. Pass `model="z-ai/glm-5.2"`. No new SDK, no new client, no new wrapper function.

**Recommended architecture**: thin path through `model_registry.py` `LAST_KNOWN_GOOD["openrouter"]["glm"]` + `chat_completion(..., model="z-ai/glm-5.2")`. Z.AI direct is a one-line `base_url` override if/when needed.

---

## When to use GLM 5.2

Use it for:

- 3D WebGL / Three.js scenes (Nick's nebula spiral, terrain flyover examples)
- Interactive HTML explainers (Nick's "how rainbows form" pattern)
- Landing pages and visual marketing artifacts
- Dashboards (Chart.js / D3 visual code)
- Mini-games (vanilla JS / Canvas)
- Slide decks (Reveal.js / static)
- Generic creative HTML/CSS/JS where visual taste matters more than precision

**DO NOT use it for:**

- Anything involving PII (names, emails, phones, addresses of real individuals)
- Cold-email leads or recipient data
- Recruiter-facing CV content (the CV Optimizer pipeline stays on Anthropic/Gemini)
- AM-scoped data (Accessory Masters / Elite Broker / Hedgestone per `CLAUDE.local.md` lockdown)
- Client / customer data of any kind
- Code touching production secrets, auth flows, payment processing, or PII-handling
- Tasks where deterministic correctness matters more than visual quality (parsers, validators, schema work)

**When in doubt: route through Anthropic Sonnet 4.6 or Gemini 2.5 Flash instead.**

Z.AI is a Chinese-jurisdiction company. Treat data sent to GLM 5.2 as if you were posting it to a public forum.

---

## How to call

### Standard path (OpenRouter, recommended)

```python
from execution.modules.llm_client import chat_completion

response = chat_completion(
    system="You are a creative coder. Output a single self-contained HTML file with no external dependencies except CDN.",
    user_message="How rainbows form, interactive explainer with a sun-angle slider.",
    model="z-ai/glm-5.2",
    max_tokens=4000,
)
```

Or via the registry tier:

```python
from execution.modules.model_registry import resolve_model
from execution.modules.llm_client import chat_completion

model_id = resolve_model("openrouter", "glm")  # → "z-ai/glm-5.2"
response = chat_completion(system="...", user_message="...", model=model_id, max_tokens=4000)
```

### Alternative: Z.AI direct (anthropic-compatible)

Only if OpenRouter is unavailable or rate-limited. Requires a `Z_AI_API_KEY` in `.env`.

```python
response = chat_completion(
    system="...",
    user_message="...",
    model="glm-5.2",  # Z.AI native naming, no provider prefix
    base_url="https://api.z.ai/api/anthropic",
    max_tokens=4000,
)
```

This requires the `OPENROUTER_API_KEY` env-var to be temporarily set to the Z.AI key, OR a small refactor to `_get_client()` to accept a per-base-url key. Deferred until needed.

---

## Web search caveat

GLM 5.2 does NOT have native web-search built into the model. In a Claude Code session driven by GLM 5.2 (when/if we set that up), web-search tool calls fail unless an Exa.ai MCP server is wired in. Per Nick's video at 7:49: integrating Exa solves this. Deferred — not wired into the workspace today.

---

## Revert procedure

Three things to undo to fully back out the GLM 5.2 integration:

1. **Global rule**: `mv ~/.claude/rules/model-tier.md.bak-2026-06-20 ~/.claude/rules/model-tier.md`
2. **Registry**: revert the two edits in `execution/modules/model_registry.py` —
   - `ALLOWED_FAMILIES = ("anthropic/", "openai/", "google/")` (drop `"z-ai/"`)
   - Remove the `"glm"` key from `LAST_KNOWN_GOOD["openrouter"]`
3. **Client**: revert `execution/modules/llm_client.py` to the bare `_client = None` singleton (the `dict[str, OpenAI]` keyed by base_url was added to enable per-base-url routing without cross-talk; reverting drops the Z.AI-direct option but keeps OR working).

All three are independent — partial revert (e.g. drop the global rule but keep the registry entry) is valid if only the policy-level rollback is needed.

---

## Owed work

- **SAST grep** (per `~/.claude/rules/rule-backport-cadence.md`): add a check in workspace_sast for `chat_completion(model=..."z-ai/...")` callsites that also handle PII keywords in the same function. Tracked in `HARDENING_BACKLOG.md`.
- **Exa MCP shim**: if the operator later switches to a GLM-driven Claude Code session as default, an Exa.ai MCP server registration is needed for web search. Not built today; the policy is "GLM 5.2 alongside Anthropic, not as default driver."
- **Z.AI direct key**: if OR becomes a bottleneck, sign up for a Z.AI key and add `Z_AI_API_KEY` to `.env`. Then refactor `_get_client()` to look up the key per-base-url. Operator-action gated.

---

## Calling-pattern summary table

| Scenario | Function call |
|---|---|
| Creative HTML/JS, public/non-sensitive | `chat_completion(system, user, model="z-ai/glm-5.2", max_tokens=4000)` |
| Same, via registry tier | `chat_completion(..., model=resolve_model("openrouter", "glm"))` |
| Sensitive content (PII, CV, leads, AM) | **DO NOT use GLM.** Use `model="anthropic/claude-sonnet-4.6"` or Gemini direct. |
| Z.AI direct (deferred) | `chat_completion(..., model="glm-5.2", base_url="https://api.z.ai/api/anthropic")` |
