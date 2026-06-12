---
name: autoresearch
description: Karpathy-style self-improving loop. Propose challenger variants of an input, deploy both via API, measure objective metric, pick winner, append learnings, repeat. Generic over any domain with a measurable metric + programmatic mutation API (cold email reply rate, ad CTR, landing page conversion, prompt eval score, etc.).
inputs:
  - baseline: any — the current input being optimized (email template, ad creative, system prompt, ...)
  - metric_fn: callable — returns a float for any deployed variant (or fetches it from the API after a wait)
  - mutate_fn: callable — LLM-driven; takes baseline + past learnings, returns one challenger variant
  - deploy_fn: callable — pushes baseline + challenger via the target API; returns deploy IDs
  - max_rounds: int — how many propose-deploy-measure cycles to run (default 10)
  - cost_cap_usd: float — hard ceiling; abort if exceeded (default 5.0)
  - metric_min_improve: float — minimum relative improvement to count as a win vs. plateau (default 0.05)
outputs:
  - winning_variant: same type as baseline
  - learnings_log_path: string — the append-only markdown trail
  - rounds_run: int
  - total_cost_usd: float
  - plateaued: bool — true if loop exited on plateau rather than max_rounds or cost_cap
---

# Autoresearch Workflow

## When to use

Use when ALL of these are true:
- You have an **objective metric** that updates within minutes-to-days (NOT subjective quality, NOT month-long sales cycles).
- You have a **programmatic API** to push variants and read the metric back.
- The cost-per-iteration is bounded (a single challenger costs less than ~$10 to deploy + measure).
- You want to run for many rounds (10+) without human-in-the-loop approval each cycle.

Do NOT use when:
- The metric is subjective and needs a human judge (use anneal with a human reviewer instead).
- The cost-per-iteration is unbounded (e.g. burns $100 per challenger via a live ad campaign).
- You only need 1-2 cycles (A/B by hand is simpler).
- The target is Accessory Masters — AM is locked, no autoresearch over AM credentials (see `CLAUDE.local.md`).

## Examples (from the video + workspace use cases)

- **Cold email reply rate**: baseline = current email template; mutate via LLM; deploy via Instantly API; measure = reply rate after N hours; winner = higher reply rate.
- **Ad creative CTR**: baseline = current image + copy; mutate via image LLM + text LLM; deploy via Meta Ads API; measure = CTR after N impressions.
- **Landing page conversion**: baseline = current page copy; mutate via LLM; deploy via Vercel preview; measure = GA4 conversion rate.
- **Prompt eval score**: baseline = current system prompt; mutate via LLM; deploy by running against test set; measure = grader output (e.g. LLM-as-judge score).

## Orchestration outline

1. **Load**: read baseline + all entries in `learnings.md` (if the file exists). This primes the mutator with accumulated knowledge.
2. **Mutate**: spawn a Sonnet-tier sub-agent with the baseline + learnings. It returns one challenger variant and a one-line hypothesis.
3. **Deploy**: call `deploy_fn(baseline, challenger)` — returns `{baseline_id, challenger_id}` for the metric-fetch step. In dry-run, this is mocked.
4. **Wait + Measure**: call `metric_fn(baseline_id)` and `metric_fn(challenger_id)`. Wait is caller-controlled (a sleep or a polling loop is in the project-specific script, not here).
5. **Pick winner**: `winner = challenger if (challenger_metric - baseline_metric) / baseline_metric >= metric_min_improve else baseline`. Ties go to baseline (stability bias).
6. **Append to learnings.md**:
   ```
   ## [YYYY-MM-DD HH:MM] Round {N}
   Baseline: <summary>
   Challenger: <summary>
   Baseline metric: <float>
   Challenger metric: <float>
   Winner: <baseline|challenger>
   Hypothesis tested: <one line>
   Outcome notes: <one line>
   ```
7. **Set new baseline = winner**. Increment round counter.
8. **Stop when**: `max_rounds` hit, `cost_cap_usd` hit, OR metric has plateaued (3 consecutive rounds with relative improvement < `metric_min_improve`).

## Prompt template

```
ultracode: run autoresearch on {baseline_description} optimizing {metric_name} via {deploy_api} for {max_rounds} rounds, cost cap ${cost_cap_usd}. Append learnings to {learnings_path}.
```

## Notes

- Default mutator model: `claude-sonnet-4-6` (copy + creative + prompt mutation).
- Default deployer/plumbing model: `claude-haiku-4-5` (API calls, logging, metric fetching — no deep reasoning needed).
- Failure mode: if `deploy_fn` raises, log `DEPLOY_FAILURE round={N} error={e}` to the learnings file, skip the round, continue. Do not crash the loop.
- In dry-run mode: mock all 3 callables, return `would_deploy`, `would_measure`, `would_learn` counts. No real API calls.
- **AM lockdown**: do NOT apply this workflow to Accessory Masters campaigns, Instantly accounts, or GHL workspaces. AM is frozen. See `CLAUDE.local.md`.

## Reference

- Karpathy autoresearch: https://github.com/karpathy/autoresearch
- Nick Saraev breakdown: `.tmp/video/4Cb_l2LJAW8/breakdown.md`
- Workspace anneal (auditor/fixer loop, code-quality variant): `C:\Users\deban\dev\anneal\`
- Python skeleton: `execution/_TEMPLATE_autoresearch.py`
- Directive template: `directives/_TEMPLATE_autoresearch.md`
