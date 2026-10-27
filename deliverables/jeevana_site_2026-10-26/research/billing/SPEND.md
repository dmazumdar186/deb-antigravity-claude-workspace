# Jeevana site — paid spend (billable third-party costs)

Generated 2026-10-27 17:20 UTC by `research/billing/spend_report.py` from the per-call ledgers.

| Vendor | USD |
|---|---|
| Higgsfield (Kling 3.0) | 13.62 |
| OpenRouter | 9.02 |
| **Total** | **22.64** |

## Line items

| Date | Vendor | Item | USD | Source / note |
|---|---|---|---|---|
| 2026-10-26 | Higgsfield (Kling 3.0) | film: 16 video legs | 4.7040 | ok 4.704 + non-ok 0.000 |
| 2026-10-26 | Higgsfield (Kling 3.0) | film_dawn: 17 video legs | 5.0960 | ok 5.096 + non-ok 0.000 |
| 2026-10-26 | Higgsfield (Kling 3.0) | film_omni: 13 video legs | 3.8220 | ok 3.822 + non-ok 0.000 |
| 2026-10-26 | OpenRouter | z-ai/glm-5.3 initial | 0.0077 | glm_log.md |
| 2026-10-26 | OpenRouter | z-ai/glm-5.3 revision | 0.0047 | glm_log.md |
| 2026-10-26 | OpenRouter | v1/v2 GLM backdrop calls before the ledgers existed | 0.0200 | HANDOFF 2026-10-26 'OpenRouter ≈ $0.02' |
| 2026-10-27 | OpenRouter | openai/gpt-6.1-sol-pro 01 draft | 1.0311 | ledger.md |
| 2026-10-27 | OpenRouter | anthropic/claude-opus-5.5 02 critique | 0.4189 | ledger.md |
| 2026-10-27 | OpenRouter | anthropic/claude-opus-5.5 02 critique | 0.4532 | ledger.md |
| 2026-10-27 | OpenRouter | openai/gpt-6.1-sol-pro 03 revise | 0.6025 | ledger.md |
| 2026-10-27 | OpenRouter | openai/gpt-6.1-sol-pro 04 critique | 0.2921 | ledger.md |
| 2026-10-27 | OpenRouter | anthropic/claude-opus-5.5 05 revise | 2.7353 | ledger.md |
| 2026-10-27 | OpenRouter | anthropic/claude-opus-5.5 05 revise | 1.7757 | ledger.md |
| 2026-10-27 | OpenRouter | openai/gpt-6.1-sol-pro 06 critique | 0.2657 | ledger.md |
| 2026-10-27 | OpenRouter | openai/gpt-6.1-sol-pro 07 revise | 1.0478 | ledger.md |
| 2026-10-27 | OpenRouter | z-ai/glm-5.3 v5 motifs draft (refused: reasoning cannot be disabled, not billed) | 0.0000 | ledger.md |
| 2026-10-27 | OpenRouter | z-ai/glm-5.3 v5 motifs draft | 0.0090 | ledger.md |
| 2026-10-27 | OpenRouter | z-ai/glm-5.3 08 critique | 0.0187 | ledger.md |
| 2026-10-27 | OpenRouter | openai/gpt-6.1-sol-pro 08 critique | 0.3172 | ledger.md |
| 2026-10-27 | OpenRouter | openai/gpt-6-astra-pro availability probe (gen-1793121606-1ytNbdLVBYZCipboFAw6) | 0.0158 | one-word test call |

## Not itemised
- Claude subscription (Max plan) usage for this session and its sub-agents: flat-fee plan, not metered per project.
- Cloudflare Pages, Functions, KV, Web Analytics: free tier.
- Labour / design time: outside this ledger.

## Reconciliation to check

- Higgsfield: the per-leg ledgers sum to $13.62, but the 2026-10-26 handoff states "Higgsfield $16.19". The ~$2.57 gap is
  likely identity-reference / still-image calls that were not ledgered. Confirm against the Higgsfield billing page and add
  the missing line to `research/billing/manual.jsonl` if real.

## OpenRouter account snapshots (cross-check only; account-wide)

| When | Credits bought | Usage to date |
|---|---|---|
| 2026-10-27T16:39:50Z | 30 | 19.1805 |
| 2026-10-27T17:03:30Z | 30 | 19.4977 |
| 2026-10-27T17:20:15Z | 30 | 19.5164 |
