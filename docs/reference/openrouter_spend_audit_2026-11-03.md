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

- [x] `llm_client.chat()` default model → `anthropic/claude-sonnet-5.5`
- [x] Re-pin the four per-row scripts in finding 3 → Sonnet (OpenRouter slugs only; `premium` --mode and Anthropic-direct pins left on Fable)
- [x] Per-call cost ledger (`.tmp/llm_ledger.jsonl`, via OpenRouter `usage.include`)
- [x] `execution/infrastructure/llm_spend_report.py` + directive (spend by script / model / day)
- [x] `LLM_BUDGET_USD` per-process guard, fail-closed
- [x] Tests: default model, ledger row, budget trip, 402 not retried
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

## Judgement call on finding 3 (orchestrator, 2026-11-03)

The implementer moved `gaia_sourcing` **judge** (adversarial critique) and **message** (copy that goes out
under the client's name) to Sonnet along with the per-row roles. Reverted those two to Fable in the
default/hybrid/openrouter plans: the file's own 2026-09-21 comment names Fable as the right model for
L8/L11, and downgrading client-facing copy is an output-contract change the operator must order — a
cost audit is not that order. The $ leak was the high-volume **extract** role; it stays on Sonnet.
The explicit all-Sonnet `budget` plan is unchanged and remains the opt-in for a thin balance.
**Operator may lower judge/message by word; cost delta is small (low-volume per campaign).**

**Still unverified until credits exist:** whether OpenRouter returns `usage.cost` where the ledger reads
it (402 blocks a live call). If not, rows show `cost_usd: null` and the budget guard falls back to the
token-price estimate — the guard still trips. First live run confirms it.

## Correction after the operator's receipt (OpenRouter activity screenshot, 2026-11-03)

The receipt ($30.17 over 10 models) shows the ranking above was wrong:

| Model | Total | Most likely source (from code + git) |
|---|---|---|
| Claude Sonnet 5.5 | $14.82 | `lead_sourcing/leadocean_leads.py` (built 2026-11-02 by a Claude session, `e1f2dad`): one icebreaker call per lead (max_tokens 600) plus a repair call, waves 1+2 on 2026-11-02/03. Matches "started a week ago". |
| Claude Opus 5.5 | $6.46 | Almost all in one day ($6.43). `model_registry` maps OpenRouter `default` to Opus 5.5; exact job not identifiable without per-call records. |
| GPT-6.1 Sol Pro | $3.91 | One day. No pin in `execution/`; an ad-hoc run by a session. Not identifiable. |
| Claude Fable 5.1 | $3.21 | One day. |
| Jev 1.13 | $1.31 | Router + Jev gates. Jev is only sold through OpenRouter. |
| Others | $0.46 | Gemini, GLM, GPT small calls. |

**Root cause (process, not code):** Claude sessions building pipelines routed Claude calls through
OpenRouter because scripts cannot use the Claude Code subscription login and the direct Anthropic API
balance was zero (`providers.py`: "Default plan under a zero Anthropic balance"). That routing was
never put to the operator as a money decision. Operator rule, restated 2026-11-03: **OpenRouter only for
non-Claude models (GPT, GLM, Jev), never for Claude.** Re-pinning Fable→Sonnet (commit 65e6c25) does
not address the largest line; moving Claude calls off OpenRouter does. Pending operator go-ahead.
