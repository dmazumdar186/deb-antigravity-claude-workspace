# Phase 5a — OpenRouter Routing Matrix (generic AI integration)

## Goal

Add LLM functionality to the app via OpenRouter, with a cheap/premium routing matrix, cache-aware prompt caching, and response guards (max-sentence cap, max-word cap, dollar-amount stripping). Generic — applies to any text-generation use case. **NOT** the vision/video pipeline (that's phase 5b, deferred).

## Inputs

- Phase 4a + 4b complete (Worker + Modal cron) — LLM calls live in the Modal cron handler, not in the mobile app directly (avoids leaking API keys to the client)
- `OPENROUTER_API_KEY` in Modal secrets (`modal secret create <slug>-openrouter OPENROUTER_API_KEY=<key>`)
- App spec — list of LLM tasks the app needs (e.g. "summarize a note", "classify intent", "generate a draft reply")

## Tools/Scripts

- `httpx` — POST to OpenRouter's `/api/v1/chat/completions`
- New file in app repo: `C:\Users\deban\dev\mobile-apps\<slug>\backend\llm.py`
- Reference: `C:\Users\deban\dev\anneal\src\anneal\cost.py` for cache-aware pricing per CLAUDE.md hardening rule #4

## Steps

1. **Define the routing matrix.** In `backend/llm.py`:
   ```python
   ROUTES = {
     "simple": {  # classification, single-sentence outputs, short summaries
       "model": "anthropic/claude-haiku-4-5",
       "fallback": "google/gemini-flash-1.5",
       "max_tokens": 256,
     },
     "complex": {  # multi-step reasoning, long outputs, code
       "model": "anthropic/claude-sonnet-4-7",
       "fallback": "openai/gpt-4-turbo",
       "max_tokens": 2048,
     },
   }
   ```
   Each LLM task in the app declares its tier (`simple` | `complex`); never picks a model directly.
2. **Cache-aware pricing table.** Per CLAUDE.md hardening rule #4 — four entries per Claude model:
   ```python
   PRICING = {
     "anthropic/claude-haiku-4-5": {"input": 1.00, "cache_read": 0.10, "cache_write": 1.25, "output": 5.00},
     "anthropic/claude-sonnet-4-7": {"input": 3.00, "cache_read": 0.30, "cache_write": 3.75, "output": 15.00},
     # USD per 1M tokens
   }
   ```
   Flat-rate pricing over-estimates 5-10x once caching is active. Crib the formula from `anneal/src/anneal/cost.py`.
3. **Prompt caching (Anthropic-format).** For long system prompts or shared context, add `cache_control: {"type": "ephemeral"}` blocks. OpenRouter passes through to Anthropic. Read `cache_read_input_tokens` + `cache_creation_input_tokens` from the response and account for them separately.
4. **Response guards.** Wrap every LLM call:
   - **Max sentences**: regex-count `[.!?]+` post-response; truncate at limit (e.g. 5 sentences for "simple", 20 for "complex").
   - **Max words**: split on whitespace; truncate at limit (e.g. 100 words for "simple", 500 for "complex").
   - **Strip dollar amounts**: `re.sub(r'\$\s?\d[\d,]*(?:\.\d{2})?', '[amount]', text)` — avoids accidental price commitments in user-facing text.
   - **Strip exclamation enthusiasm**: collapse `!{2,}` → `!`, optional flag to remove `!` entirely.
   - **Empty-response fallback**: if the API returns empty content (`choices[0].message.content == ""`), fall through to the route's `fallback` model. If both empty, return a static safe string ("I don't have an answer right now.") — never propagate empty to the user.
5. **Voice reference in system prompt.** Embed a one-paragraph voice spec at the top of the system prompt: "Write concisely, no marketing fluff, no emojis, no all-caps." Keeps outputs consistent and reduces guard-rule firings.
6. **Implement the helper.**
   ```python
   def call_llm(tier: str, system: str, user: str, cache_system: bool = True) -> dict:
       route = ROUTES[tier]
       resp = httpx.post(
           "https://openrouter.ai/api/v1/chat/completions",
           headers={"Authorization": f"Bearer {OPENROUTER_KEY}"},
           json={...},
           timeout=60,
       )
       data = resp.json()
       text = data["choices"][0]["message"]["content"]
       text = apply_guards(text, tier)
       cost = compute_cost(data["usage"], route["model"])
       return {"text": text, "cost_usd": cost, "model_used": route["model"]}
   ```
7. **Fallback on model failure.** If primary returns 5xx or empty, swap to `route["fallback"]` and retry once. Log both attempts.
8. **Dry-run mode.** `call_llm(..., dry_run=True)` returns `{"would_call": route["model"], "estimated_cost_usd": <prefix-token-estimate>}` without an HTTP call.
9. **Integrate into Modal cron.** The Phase 4b cron handler calls `call_llm(...)` for its LLM work. Results flow into the Worker KV via the existing webhook.
10. **Commit.** `git commit -m "phase 5a — openrouter routing + cache-aware pricing + response guards"`.

## Outputs

- `backend/llm.py` — routing matrix, pricing table, guard pipeline, dry-run path
- LLM calls only happen inside Modal (never from the mobile app directly)
- Cost-per-call logged + summed into Worker KV `monthly_spend_usd`

## Edge Cases

- **OpenRouter rate limits.** Free tier is generous but rate-limited per minute. On 429, exponential backoff + fallback model.
- **Streaming responses.** Phase 5a uses non-streaming (`stream=false`); the Modal cron is fine with batch results. If the mobile app ever needs streaming, route via a Worker that proxies SSE — adds complexity, defer.
- **Cache miss on first call.** First request with `cache_control` is a write (1.25x input price). Repeats within the cache window (5 min for Anthropic ephemeral) hit at 0.1x. Don't expect savings on one-shot crons; caching pays off when the same system prompt is reused across calls.
- **Model deprecation.** OpenRouter occasionally retires models. Catch HTTP 410 + log; treat as fallback trigger.
- **JSON-mode failures.** If the app needs structured output, use OpenRouter's `response_format: {type: "json_object"}` (Anthropic/OpenAI both support). Even then, wrap `json.loads()` in try/except and fall back to text parsing.
- **PII in prompts.** Don't send user-identifying info to OpenRouter without considering retention. OpenRouter's "data policy" can be set per model; review for sensitive apps.
- **Dollar-amount stripping is regex-naive.** Catches `$5`, `$5.00`, `$1,234.56` but not `5 dollars`, `USD 5`, `five bucks`. Document the limit; expand the regex case-by-case as it bites.

## Exit Criteria

The directive is "done" when ALL of these hold (each must be machine-verifiable):

- `backend/llm.py` exists with a `ROUTES` dict defining at least `simple` and `complex` tiers (each with `model`, `fallback`, `max_tokens`).
- `backend/llm.py` contains a `PRICING` table with 4 entries per Claude model (`input`, `cache_read`, `cache_write`, `output`) — never flat-rate.
- `call_llm(..., dry_run=True)` returns a dict with `would_call` and `estimated_cost_usd` keys (no HTTP call made).
- At least one LLM task in the Modal cron (`backend/cron.py`) calls `call_llm(...)` rather than calling OpenRouter directly.
- `modal run backend/cron.py::refresh_job` (real run) logs a `cost_usd` value computed from all 4 token-count fields (`input_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens`, `output_tokens`).
- Response guards are applied: max-sentence limit and dollar-amount strip are present in `apply_guards()` (or equivalent); empty-response fallback returns the static safe string.
- `OPENROUTER_API_KEY` is present in Modal secrets (`modal secret list` shows `<slug>-openrouter`); never present in the app bundle.
- Phase 5a commit exists: `git log --oneline` includes a commit with "phase 5a".

If any predicate fails, fix before claiming Phase 5a complete. Do NOT proceed to production builds with flat-rate pricing or without the empty-response fallback.

## Notes

- This is the **generic** AI integration. Vision/video pipelines (frame dedup, OCR, 3x3 tile analysis) are Phase 5b, created on demand only when an app needs them.
- Cache-aware pricing is a CLAUDE.md hardening rule — never use flat-rate or the cost dashboard will be 5-10x wrong.
- Anneal adversarial mode runs after this phase via the `/mobile-app` skill.
