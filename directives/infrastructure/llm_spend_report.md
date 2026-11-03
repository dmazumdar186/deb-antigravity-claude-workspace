# LLM Spend Report

## Goal
Show where OpenRouter money went: per script, model or day, from the cost ledger that
`execution/modules/llm_client.py` appends on every successful call. Born from the
2026-11-03 audit (`docs/reference/openrouter_spend_audit_2026-11-03.md`).

## Inputs
- `.tmp/llm_ledger.jsonl` (one JSON row per call: ts, caller, model, prompt_tokens,
  completion_tokens, cost_usd, latency_ms, base_url_host). Written by `llm_client.chat_completion`.
- Flags: `--days N` (default 7), `--by script|model|day` (default script), `--json`, `--ledger PATH`.

## Tools/Scripts
- `execution/infrastructure/llm_spend_report.py` (stdlib only, no network, no key needed).
- Upstream: `execution/modules/llm_client.py` (ledger writer + `LLM_BUDGET_USD` per-process guard, default $5).

## Outputs
- Plain table on stdout: group, calls, prompt tokens, completion tokens, cost_usd, then a TOTAL line.
- `--json`: `{days, by, groups[], total}` for machines.
- Exit 0 always on a readable ledger, including empty (`no ledger rows`).

## Steps
1. After any batch run, run `python3 execution/infrastructure/llm_spend_report.py --days 7`.
2. If one script dominates, rerun with `--by model` to see which tier it used.
3. If a Fable/Opus pin shows up on per-row work, re-pin it to `anthropic/claude-sonnet-5.5`.
4. For billing truth, cross-check https://openrouter.ai/activity.

## Edge Cases
- Ledger is local to the machine/container that ran the calls; cloud sessions start empty.
- `cost_usd` is null when OpenRouter omits `usage.cost` (non-OR base_url); those rows count as $0
  here, though the budget guard estimates them from tokens via `llm_client.PRICE_TABLE`.
- Jev calls (`execution/modules/jev_client.py`, decisions endpoint) are not in this ledger; they
  have their own usage log (`jev status`).
- Malformed lines are skipped silently.
