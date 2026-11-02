# Instantly A/B Copy Monitor

**Output contract:** Daily report = per-campaign variant table + actions taken; nothing else.

## Goal

Run Instantly copy A/B tests without babysitting. Three jobs in one script:

1. **gate** — before launch, Jev scores spun copy across 20 random renders; copy that reads templated or AI-written is blocked.
2. **validate** — weekly, checks the Jev scorer still tracks real reply rates (Spearman) across the workspace.
3. **monitor** — daily, scores every variant of every configured test campaign and disables at most one complaint-heavy or clearly losing variant per campaign.

## Tools/Scripts

| Script | Role |
|---|---|
| `execution/infrastructure/instantly_copy_monitor.py` | CLI: `gate`, `validate`, `monitor [--live]` |
| `execution/infrastructure/instantly_copy_tests.json` | Config: inbox `tag_ids` + `tests` list (campaigns under test) |
| `tests/test_instantly_copy_monitor.py` | Offline unit tests for render + decision logic |
| `execution/modules/jev_client.py` | Jev (OpenRouter Decisions API) |

## Inputs

| Input | Notes |
|---|---|
| `gate --copy <file>` | JSON list of `{"id","subject","body"}`. Spintax `{{RANDOM \| a \| b}}` and bare `{{a\|b}}`, nesting and merge fields inside options allowed. |
| `--config <file>` | Default the committed `instantly_copy_tests.json`. Test entry: `campaign_id`, `name`, `family`, `started` (YYYY-MM-DD, metrics count from here), `control_variant` (0-based, display only). |
| `monitor --live` | Without it nothing is changed (dry run). |
| env `INSTANTLY_API_KEY` | Instantly v2 bearer key. |
| env `OPENROUTER_API_KEY` | Jev, via `jev_client`. |

Never edit a campaign that is not in `tests`. The orchestrator adds a test entry after pushing the variants.

## Outputs

- `gate`: per copy PASS/FAIL, mean/min `human`, mean `ai_tells`, and the lowest-scoring render (so a writer can fix it). Exit 1 if any copy fails.
- `validate`: Spearman table on stdout + `.tmp/copy_monitor/validate_<date>.md`; warning line when `human` < 0.2.
- `monitor`: markdown on stdout + `.tmp/copy_monitor/report_<date>.md`. Per campaign: table (step, variant A/B/C, active, sent, positive, human, unsub, P(best)), then **Actions** (or "No changes"), then inbox alerts.
- Exit codes: 0 OK, 1 gate failed, 2 Instantly/Jev API failure (no actions are taken when classification fails).

## Steps

1. Write the variants; save them as a `gate` input file.
2. Run `python3 execution/infrastructure/instantly_copy_monitor.py gate --copy <file>`; rewrite any FAIL using the printed lowest-scoring render; repeat until exit 0.
3. Push the variants to Instantly (`instantly-campaigns` skill) and launch the campaign.
4. Add a test entry (campaign_id, name, family, started = launch date, control_variant) to `instantly_copy_tests.json`; commit.
5. Daily: run `monitor --live`; deliver the report as-is (output contract above).
6. Weekly: run `validate`; act on the warning line if present.
7. Remove a test entry when the campaign completes or one arm per step remains.

## Decision rules

**Gate PASS:** mean human ≥ 0.55 AND min human ≥ 0.40 AND mean ai_tells ≤ 0.40 (20 renders, seed 7). Merge fields render case-sensitively: firstName→Mark, companyName→Northbridge, location→Dallas, Location→Lyon, sendingAccountFirstName→Deb; anything else → empty. Merge fields are substituted before spintax (the prototype did it the other way and silently deleted options containing merge fields). HTML is flattened to text first.

**Reply classification (monitor):** each received email (`ue_type == 2`, `timestamp_email ≥ started`, attributed by `step` = `seq_step_variant`, e.g. `0_0_1`) gets a Jev `kind`: interested / not_interested / unsubscribe_or_complaint / out_of_office / left_company / ticket_autoresponder / bounce_ndr / challenge_response / other. Confidence < 0.6 is low-confidence; low-confidence `interested` counts as `other` (Jev labelled "Unsubscribe" / "Delete my email" as interested at 0.40–0.58 in testing). Quoted text below "On … wrote:" / `>` lines is stripped first.

**Metrics per step, per variant:** sent (analytics/steps), positive = interested, human = interested + not_interested + unsubscribe_or_complaint + other, unsub = unsubscribe_or_complaint.

**Actions (pure function `decide_campaign`, unit-tested):**
- Active arms = variants with `v_disabled` false. Never disable the last active arm of a step (reported as "Held").
- At most ONE change per campaign per run. Complaints beat losers.
- Complaints: sent ≥ 200 and unsub/sent > 0.75 % → disable (highest rate first).
- Loser: only when every active arm in the step has sent ≥ 400. Metric = positives; if the step has < 5 positives in total, metric = human − unsub (floor 0). Beta(1+k, 1+n−k), 20k Monte Carlo draws (seed 7) → P(best). If max P(best) ≥ 0.90 and an arm has P(best) ≤ 0.05 → disable the lowest-P arm.
- P(best) in the table covers active arms that have sent; unsent arms show `-`.
- Apply: `PATCH /api/v2/campaigns/{id}` with `{"sequences": <fetched sequences, only that variant's v_disabled = true>}`, then re-GET and verify; a failed verify is reported as FAILED.

**Inbox health (alert only):** accounts tagged with any `tag_ids`; 7-day `accounts/analytics/daily`; flag sent ≥ 100 and bounced/sent > 4 %.

## Edge Cases

- **`sent` is lifetime, not windowed (verified 2026-11-02).** `analytics/steps` ignores `start_date` for `sent`, and a variant slot keeps the history of any variant that was deleted from it (Recruitment UK slot B started at 187 sends). Every test in the config carries `baseline_sent` {"step_variant": sends at test start}, which the monitor subtracts. When you add a new test, snapshot the baseline the same day you add the variants.
- **Schedule:** a daily cloud scheduled task runs `monitor --live` at 05:23 UTC, plus `validate` on Mondays. It runs in a fresh session on branch `claude/ecstatic-curie-n8mzoj`, or `main` once merged. Its push notification is the report itself.
- **Live test started 2026-11-02:** 11 campaigns (8 recruitment, SMB USA, Web Agency USA, Yoga France). Step 1: A = old copy (control), B = "open for collaborating" subject, C = "idea for…" subject, B and C sharing a new body. Steps 2 and 3: one new variant each. Gate scores were human 0.56–0.70 vs 0.25–0.33 for the old copy.

- Instantly 403s urllib's default User-Agent; the script uses `requests` with a real UA.
- `/emails` is limited to 20 req/min: 3.2 s between calls; 429 → sleep 20 s, retry up to 4 times. Uses `email_type=received` + `min_timestamp_created` and filters `ue_type == 2` locally.
- Some received emails have no `step` (and analytics/steps returns a `null` step row): they are not attributable and are ignored.
- analytics/steps `start_date` does not strictly bound replies (an August reply still showed under a mid-September start date); reply counts therefore come from `/emails`, sent counts from analytics/steps.
- Campaigns with status ≠ 1 (active) are reported as skipped, not analysed.
- `accounts` pagination cursor is a compound `timestamp&email` string; paging stops on an empty page.
- Any Jev classification error after one retry → exit 2, no actions (deciding on partial labels is unsafe).

## Exit Criteria

- `gate`: every copy PASSes (exit 0) before it is pushed to Instantly.
- `monitor`: exit 0, report written to `.tmp/copy_monitor/report_<date>.md`, and every live action reads "Disabled" (verified on re-read), never "FAILED".
- `validate`: exit 0 and no `human` Spearman warning; otherwise the gate thresholds are re-tuned before the next launch.
- `python3 -m pytest -q tests/test_instantly_copy_monitor.py` passes after any change to the decision logic.

## Schedule

- `monitor --live`: daily (one run per day; decisions need fresh sends between runs).
- `validate`: weekly. If `human` Spearman drops below 0.2, stop trusting the gate thresholds until re-tuned.
- `gate`: on demand before any new copy is pushed to Instantly.

## Changelog

| Date | Change |
|---|---|
| 2026-11-02 | Created. Ported render/Q/spearman from `.tmp/copy_lab/jev_copy_validate.py`; fixed merge-field-inside-spintax and `RANDOM`-as-option bugs; Spearman now uses average ranks for ties. First validate run: 55 campaigns, human +0.31, ai_tells −0.29. |
