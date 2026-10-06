# Jev Customer Health

## Purpose

Find the customers who are about to leave before they cancel. Jev (TypeSafe, via OpenRouter's
Decisions API) reads each customer's record — tenure, plan, MRR, usage, tickets, NPS, billing,
cancel notes — and in ONE call returns a health group, a 90-day churn probability, an expansion
probability and the primary risk driver. Code ranks everyone by revenue at risk so the operator
knows who to reach out to this week. (RoboNuggets "19 Jev use cases", #5.)

## When to invoke

- Operator asks to "score", "profile" or "health-check" the customer base, or "who might churn".
- Weekly retention review (recommended cadence: every Monday on a fresh export; append to the
  same Sheet tab so week-over-week drift is visible).
- Before a renewal or pricing change, to find expansion candidates and at-risk accounts.

Operator copy-paste prompt:

```
Score my customer base for churn risk from <csv> (directives/gtm_icp_filters/jev_customer_health.md).
Give me the summary, MRR at risk and the top 20 reach-out list.
```

## Inputs

- `--input`: `path` — CSV or JSON list (or `{"customers": [...]}`). Column guide (case-insensitive):

| Field | Accepted columns | Notes |
|---|---|---|
| id | `id`, `customer_id`, `account_id` | falls back to email, name, row number |
| email / name | `email` / `name`, `company`, `account_name` | shown in the reach-out list |
| plan | `plan`, `tier`, `subscription` | |
| mrr | `mrr`, `monthly_revenue`, `revenue` | `$1,250` ok; drives priority |
| tenure | `tenure_days` or `signup_date` (YYYY-MM-DD) | date converted to days |
| recency | `last_login_days` or `last_active` (YYYY-MM-DD) | |
| usage | `logins_30d`, `feature_usage` (number or free text) | |
| support | `support_tickets_30d`, `tickets` | |
| sentiment | `nps` | |
| billing | `payment_failed` (yes/no/true/false/1/0) | |
| intent | `cancel_intent`, `notes` (free text, 2k chars) | strongest signal |

  Any other non-empty column is passed to Jev as-is (e.g. `seats`, `csm`).
- `--min-confidence` (0.55) → `review` flag; `--workers` (8); `--limit`; `--dry-run`; `--top` (20).
- `--validate labels.csv` (`id,health`) — accuracy + mismatches.
- `--sheet-id` / `--tab` (default `customer_health`) — optional append via
  `execution/google/google_sheets_writer.get_client()`; skipped gracefully without creds.
- env `OPENROUTER_API_KEY` (also `OPENROUTER_API_TOKEN` / `OPENROUTER_API_TOEKN`).

## Outputs

- `--output` JSON (default `<input>.health.json`): `summary` + `rows[]` sorted by priority
  (health, confidence, probabilities, churn_90d, expansion, reason, priority, review, cost, error).
- `--csv-out` flat CSV; `--md` "Reach out this week" list (non-healthy rows, top N by priority,
  with reason) plus expansion candidates.
- stdout: counts per health group, MRR at risk, expansion candidates, cost, wall time.
- Ledger row in `.tmp/jev_ledger.jsonl` (`caller: jev_customer_health`).

## Rules (code-side)

- `priority = churn_90d × mrr` (monthly revenue at risk); rows sorted descending.
- `review = confidence(health) < --min-confidence`; failed calls are `review` with priority 0.
- Expansion candidate: `expansion >= 0.5`.

## Exit Criteria (declarative)

- Output JSON exists; `len(rows) == min(input_count, --limit)`; rows sorted by priority.
- Every errored row has `review: true`; `summary.errors / count <= 0.05` on a live run.
- With `--validate`: accuracy printed and every mismatch listed.

## Scripts (Layer 3)

- `execution/gtm_icp_filters/jev_customer_health.py`
- `execution/modules/jev_client.py` (shared client; the only way to call Jev)
- `tests/test_jev_customer_health.py` (offline, monkeypatched `decide_many`)

## Edge cases

- Sparse rows (only name/plan) correctly come back `insufficient_data`; priority still uses
  churn × MRR, so they can rank above healthy accounts — check them manually.
- Missing MRR → priority 0 (sorted to the bottom); add MRR to the export for useful ranking.
- Unparseable numbers/dates are dropped, not guessed.
- Cost: ~$0.00004 per customer (8 customers = $0.0003, 0.75 s on 2026-10-06).

## Changelog

- 2026-10-06: Created (RoboNuggets Jev use case 5). First live run on 8 synthetic customers:
  3 at_risk, 1 churning, 3 healthy, 1 insufficient_data; $1,345.84 MRR at risk; 1 expansion.
