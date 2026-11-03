# OpenRouter spend audit — 2026-11-03

**Trigger.** Operator reports >€30 OpenRouter spend in 10 days; expectation was "<1 cent per Jev call".
**Verified from the key itself** (`GET /api/v1/auth/key`): `usage: $30.20`, **`limit: None`**, not free tier.
**Verdict: Jev is not the spender.** Jev bills ~$0.0001/call (input-only). $30 would be ~300,000 Jev
calls. The spend is **Claude Fable/Opus calls routed through OpenRouter** by the execution scripts.

> OpenRouter refuses a per-model breakdown to a normal key (403: management keys only). The per-model
> truth lives in the dashboard: **https://openrouter.ai/activity**. Everything below is reconstructed
> from the code paths that can bill this key.

## Findings (ranked by $ exposure)

| # | Finding | Evidence | Exposure | Fix |
|---|---|---|---|---|
| 1 | **No spend limit on the key.** Nothing caps runaway spend. | `limit: None` from the key endpoint | Unbounded | Operator: set a credit limit on the key (dashboard, 1 min). See "Operator actions". |
| 2 | **`llm_client.chat()` defaults to Fable 5.1** — the premium tier — for every call that doesn't name a model. | `execution/modules/llm_client.py:65` `model: str = "anthropic/claude-fable-5.1"` | Every unspecified call pays premium | Default → Sonnet (bulk tier). Fable only when explicitly passed. |
| 3 | **Bulk/per-row scripts pin Fable.** Lead sourcing, per-lead personalization and reply classification — mechanical per-row work — run on the judgement model. Violates CLAUDE.md "Fable never grinds". | `gaia_sourcing/core/providers.py` ×11, `personalization/variant_generator.py` ×4, `personalization/ai_opener_generator.py` ×4, `self_outbound_system/reply_classifier.py` ×1 | Per-row × premium price = the likely bulk of the $30 | Re-pin to `anthropic/claude-sonnet-5.5`. |
| 4 | **Zero cost visibility for OpenRouter calls.** `llm_client` logs no cost; `token_usage_report.py` only scans Claude Code transcripts (Max plan). Jev has a ledger; the expensive path has none. This is *why* the operator was blindsided. | `llm_client.py` (no usage/cost logging); `token_usage_report.py:4` | Blind spot, not spend | Per-call JSONL ledger `.tmp/llm_ledger.jsonl` + `llm_spend_report.py`. |
| 5 | **No per-run budget guard.** A looping script can spend without bound inside one run. | `llm_client.py` (no cap) | Unbounded per run | `LLM_BUDGET_USD` env (default $5/process); fail-closed `LLMBudgetExceeded`. |
| 6 | OpenRouter margin on models the operator can reach directly. | `_OR_BASE_URL` is the default for all Claude calls | Few % | Noted, not changed now (OR gives one key + fallbacks; keep). |
| 7 | Unattended daily task `Instantly copy A/B monitor` holds the OR key. | `list_triggers`; created 2026-11-02; script has no `chat()` call | Low (verify) | Worker verifying what it does with the key; cap if needed. |

**Not a cause:** thinking-token explosion. `reasoning.effort=low` is already sent for Fable (`llm_client.py:84-86`).
**Not a cause:** retry storms on billing errors — only 429/5xx are retried; 402 is not.
**Not a cause:** the Jev router/advisor (`/jev on`) — it fails open on 402 and bills ~nothing when up.

## Fixes applied (this session)

- [ ] `llm_client.chat()` default model → `anthropic/claude-sonnet-5.5`
- [ ] Re-pin the four per-row scripts in finding 3 → Sonnet
- [ ] Per-call cost ledger (`.tmp/llm_ledger.jsonl`, via OpenRouter `usage.include`)
- [ ] `execution/infrastructure/llm_spend_report.py` + directive (spend by script / model / day)
- [ ] `LLM_BUDGET_USD` per-process guard, fail-closed
- [ ] Tests: default model, ledger row, budget trip, 402 not retried
(Boxes ticked in the commit that lands them.)

## Operator actions (the only two things code cannot do)

1. **Cap the key** so this cannot recur: https://openrouter.ai/settings/keys → this key → set a credit limit
   (e.g. $10/month). From then on the pipeline hits a hard stop instead of your card.
2. **Top up:** https://openrouter.ai/settings/credits (URL verified from OpenRouter's own 402 response).
3. Per-model breakdown of the $30 that already went: https://openrouter.ai/activity

## How to never do this dance again

`python3 execution/infrastructure/llm_spend_report.py --days 7` after any batch run; the budget guard
stops a runaway script at $5 by default (`LLM_BUDGET_USD` to change per run); the key cap stops
everything else. Three layers, each independent.
