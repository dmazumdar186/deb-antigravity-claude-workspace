# LLM Client (Claude via subscription, everything else via OpenRouter)

## Goal
One entry point for single-turn LLM calls from workspace scripts, with the operator's billing rule
(2026-11-03) enforced in code: **Claude models run on the operator's Claude subscription through
the Claude Code CLI, never OpenRouter.** OpenRouter is only for non-Claude models (GPT, GLM,
Gemini-via-OR, Jev). Born from `docs/reference/openrouter_spend_audit_2026-11-03.md`.

## Inputs
- `chat_completion(system, user_message, model=..., max_tokens=..., base_url=..., effort=..., budget_usd=...)`.
- `CLAUDE_VIA` env: `subscription` (default) or `openrouter` (escape hatch: Claude billed per call on OpenRouter).
- `OPENROUTER_API_KEY` (or `OPENROUTER_API_TOEKN` in cloud) for non-Claude models or the escape hatch.
- `LLM_BUDGET_USD` (default 5): per-process $ guard for OpenRouter calls only.
- Claude Code CLI on PATH (`claude`, or `claude.cmd` on Windows) and logged in to the subscription.

## Tools/Scripts
- `execution/modules/llm_client.py`: `chat_completion`, `_claude_cli_completion`, `CLAUDE_CHAIN`,
  `ClaudeLimitReached`, `LLMBudgetExceeded`.
- `execution/gtm_client_workflows/gaia_sourcing/core/providers.py`: `subscription` backend for every
  Claude role in every plan (tool schema put in the prompt, JSON reply parsed; 0 EUR on the ceiling).
- `execution/content/humanizer.py`: `default`/`premium` tiers use the subscription chain (plain-text reply).
- Ledger reader: `execution/infrastructure/llm_spend_report.py` (`directives/infrastructure/llm_spend_report.md`).

## Outputs
- Response text (string).
- One JSONL row per call in `.tmp/llm_ledger.jsonl`. Subscription rows: `model` (the tier actually
  used), `effort`, `"billing": "subscription"`, `cost_usd: null`, `notional_usd` (the CLI's
  `total_cost_usd`, what it would have cost on the API), `base_url_host: "claude-code-cli"`.
  OpenRouter rows: `cost_usd` from `usage.cost`, `base_url_host: "openrouter.ai"`.

## Steps
1. Routing: if the model id contains `claude` (any form: `anthropic/claude-…`, `claude-…`) and
   `CLAUDE_VIA` is not `openrouter`, the call goes to the subscription chain; otherwise OpenRouter.
2. The chain decides the model, whatever the script pinned (operator order):
   1. `claude-opus-5-5`, effort `medium`
   2. `claude-fable-5-1`, effort `low`
   3. `claude-sonnet-5-5`, effort `high`
3. Invocation per tier (prompt on stdin): `claude -p --model <m> --effort <e> --output-format json
   --no-session-persistence --setting-sources "" --strict-mcp-config --tools "" --system-prompt <system>`.
4. A tier is left only when its error mentions a usage/rate/quota limit or overload (`usage limit`,
   `limit reached`, `hit your limit`, `rate limit`, `quota`, `overloaded`, `529`, `429`). That tier is
   then marked exhausted for the rest of the process (thread-safe) and later calls skip it.
5. All three limited: `ClaudeLimitReached`. Wait for the reset, or rerun with `CLAUDE_VIA=openrouter`
   if paying per call is acceptable.
6. Check spend after batch runs: `python3 execution/infrastructure/llm_spend_report.py --days 7`.

## Edge Cases
- Any non-limit failure (CLI missing, not logged in, auth error, bad JSON, timeout) raises
  `RuntimeError` immediately; it never falls through to the next tier or to OpenRouter.
- `--bare` must not be used: it skips the subscription login (auth error).
- A positional prompt after `--tools ""` is swallowed; the prompt always goes via stdin.
- `--setting-sources ""` + `--strict-mcp-config` keep workspace hooks, plugins and MCP servers (Jev
  router etc.) from firing on every script call.
- `max_tokens` and per-call `effort` cannot be passed to the CLI; they are ignored on the
  subscription path (effort comes from the chain).
- The `$` budget guard ignores subscription calls (no money spent); `notional_usd` is informational.
- No tools/vision on the subscription path. Scripts that need images + tool-use on Claude
  (`execution/video/youtube_video_analyzer.py --provider openrouter`) still go to OpenRouter.
- Subscription usage is shared with interactive Claude Code sessions (one 5-hour + weekly pool);
  a large batch can push the session onto the next tier too.
- Anthropic-direct paths (`ANTHROPIC_API_KEY`, e.g. `model_router` client mode) are not changed by
  this rule; they bill the API account, not OpenRouter.
