# [Project Name] Autoresearch Directive

## Purpose

[One paragraph: what business outcome this optimizes and why automating it matters.
Example: "Improve cold email reply rate for the [client] campaign by iteratively testing
LLM-generated challenger copies against the live Instantly API. Each round deploys a
new variant, waits N hours for reply data, then promotes the winner as the next baseline.
Goal: reach >10% reply rate within 20 rounds while keeping total API spend under $50."]

## Pre-flight (confirm ALL before writing any code)

- [ ] **Objective metric defined**: `[metric name]`, unit `[e.g. reply_rate, CTR, eval_score]`, higher = better.
- [ ] **Metric update window**: how long after deploy until the metric stabilises? `[e.g. 4h, 24h, 7 days]`
- [ ] **Programmatic API confirmed**: `[API name + docs URL]`. Both write (deploy) and read (metric) are available via API, not just the UI.
- [ ] **Cost per round estimated**: deploy cost `$[N]` + LLM mutation cost `$[N]` = `$[total]` per round.
- [ ] **max_rounds set**: `[N]`
- [ ] **cost_cap_usd set**: `$[N]` (must be > max_rounds × cost_per_round; add 20% buffer)
- [ ] **metric_min_improve set**: `[e.g. 0.05 = 5%]` — improvement below this threshold counts as plateau.
- [ ] **Credentials available**: env vars `[LIST_ENV_VARS]` in `.env`.
- [ ] **AM lockdown respected**: this project does NOT touch Accessory Masters credentials, campaigns, or APIs.

## Inputs

- `baseline`: `string` — [describe what this is, e.g. "current email template text with {{merge_tags}}"]
- `learnings_log`: `Path` — append-only markdown file tracking all rounds (default: `.tmp/[project]_learnings.md`)
- `--max-rounds`: `int` — [your default here]
- `--cost-cap-usd`: `float` — [your default here]
- `--metric-min-improve`: `float` — [your default, typically 0.05]
- `--mode`: `{cheap, balanced, premium}` — mutator model tier (default: `balanced`)

## Outputs

- `winning_variant`: `string` — the best variant found after all rounds
- `learnings_log_path`: `string` — path to the populated markdown log
- `rounds_run`: `int`
- `total_cost_usd`: `float`
- `plateaued`: `bool`

## Mutate function

- **Model**: `claude-sonnet-4-6` (balanced) / Haiku (cheap) / Opus (premium)
- **Prompt shape**:
  ```
  You are optimizing [WHAT] to maximise [METRIC].

  Current baseline:
  <baseline>

  Past experiment learnings:
  <learnings>

  Generate ONE challenger variant. Then output a one-line hypothesis.
  ```
- **Past learnings fed in**: full text of `learnings.md` (or "" on round 1)
- **Output parsed**: challenger text + hypothesis line

## Deploy function

- **API**: `[API name]`
- **Endpoint**: `[e.g. POST https://api.instantly.ai/api/v1/campaign/create]`
- **Credentials env var**: `[e.g. INSTANTLY_API_KEY]`
- **Returns**: `{"baseline": deploy_id_A, "challenger": deploy_id_B}`
- **Rate limits**: `[known limits — e.g. 10 req/min]`

## Measure function

- **API**: `[API name]`
- **Endpoint**: `[e.g. GET https://api.instantly.ai/api/v1/campaign/{id}/stats]`
- **Field returned**: `[e.g. response["reply_rate"]]`
- **Wait strategy**: sleep `[N]` seconds / poll every `[N]` minutes until data is available
- **Dry-run mock**: return `0.50` for baseline, `0.55` for challenger

## Winner picker

Default: argmax with `metric_min_improve` threshold (challenger must beat baseline by ≥5%).
Ties go to baseline (stability bias — avoids random-walk drift on noisy metrics).

[Optional: if your metric has high variance, consider a significance test. Document it here
and implement in your project's `measure_fn` wrapper.]

## Stop conditions

Loop terminates when any of these is true:
1. `rounds_run >= max_rounds`
2. `total_cost_usd >= cost_cap_usd`
3. Plateau: 3 consecutive rounds where challenger improvement < `metric_min_improve`

## Exit Criteria (declarative — verify before claiming "done")

- `learnings.md` has >= `[N]` round entries appended (one per completed round).
- `winner_metric > baseline_metric_round_1 × [1 + target_improvement]` (e.g. `× 1.10` for 10% gain target).
- `total_cost_usd < cost_cap_usd`.
- Zero rounds report `DEPLOY_FAILURE` without a corresponding log entry.
- Script exits with code 0.

## Scripts (Layer 3)

- `execution/[category]/[project_name]_autoresearch.py` — copy from `execution/_TEMPLATE_autoresearch.py` and fill in the 3 callables.

## Edge cases

- **API rate limit**: add exponential backoff in `deploy_fn`. Log the delay, do not crash.
- **Metric fluctuation (cold start)**: for small-sample metrics, wait longer before measuring. Document the minimum sample size needed for a meaningful comparison.
- **Metric fetch failure**: if `measure_fn` errors, log `MEASURE_FAILURE` and skip the round (same as deploy failure handling).
- **Kill switch**: to stop the loop early, kill the process (Ctrl-C). The learnings log is already flushed — no data is lost.
- **AM lockdown**: if the target API belongs to Accessory Masters, STOP. Do not proceed. AM is frozen.

## AM lockdown reminder

> This directive and its execution script must NEVER be pointed at Accessory Masters
> campaigns, Instantly accounts, GHL workspaces, or any AM credential. AM is handed off
> and read-only. See `CLAUDE.local.md` for the full lockdown rules.

## Changelog

- [YYYY-MM-DD]: initial version
