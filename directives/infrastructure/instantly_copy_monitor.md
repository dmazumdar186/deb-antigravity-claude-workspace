# Instantly A/B Copy Monitor

**Output contract:** Daily report = Scorecard + one role table per family + Actions (+ inbox alerts); nothing else. Per-campaign tables only with `--detail`. Machine state goes to the ledger (`docs/metrics/instantly_copy_monitor_ledger.jsonl`), never into the report.

## Goal

Run Instantly copy A/B tests without babysitting. Four jobs in one script:

1. **gate**: before launch, Jev scores spun copy across 20 random renders; copy that reads templated or AI-written is blocked.
2. **validate**: weekly, checks the Jev scorer still tracks real reply rates (Spearman) across the workspace.
3. **monitor**: daily, pools every test campaign of a family by role (control / B / C / old / new / legacy), decides at family level, and disables at most one complaint-heavy or clearly losing role per family, in every campaign of that family.
4. **eval**: on demand (and after any logic change), E1–E5 idempotency and consistency evals.

Plus `instantly_copy_sync.py`: idempotent sync of the new-copy variants in live campaigns from the committed copy file.

## Tools/Scripts

| Script | Role |
|---|---|
| `execution/infrastructure/instantly_copy_monitor.py` | CLI: `gate`, `validate`, `monitor [--live] [--detail]`, `eval [--copy]` |
| `execution/infrastructure/instantly_copy_sync.py` | Sync new-copy variants (step 1 roles B/C, steps 2-3 role `new`) from the copy file; dry run unless `--apply` |
| `execution/infrastructure/instantly_copy_tests.json` | Config: inbox `tag_ids` + `tests` list (campaigns under test) |
| `execution/infrastructure/instantly_copy_variants.json` | The live new copy (gate input, E5 input, sync source, audit trail) |
| `docs/metrics/instantly_copy_monitor_ledger.jsonl` | Append-only ledger: one line per monitor / validate / eval run |
| `tests/test_instantly_copy_monitor.py` | Offline unit tests: render, decisions, pooling, apply idempotency (E3), E1 on a recorded snapshot, scorecard, ledger, sync conversion |
| `tests/fixtures/instantly_reply_labels.json` | 93 redacted, hand-labelled replies (kind + preview) for E4 accuracy |
| `execution/modules/jev_client.py` | Jev (OpenRouter Decisions API) |

## Inputs

| Input | Notes |
|---|---|
| `gate --copy <file>` | JSON list of `{"id","subject","body"}`. Spintax `{{RANDOM \| a \| b}}` and bare `{{a\|b}}`, nesting and merge fields inside options allowed. |
| `--config <file>` | Default the committed `instantly_copy_tests.json`. Test entry: `campaign_id`, `name`, `family`, `started` (YYYY-MM-DD), `control_variant` (display only), `roles`, `baseline_sent`. |
| `roles` | `{"step": {"role": variant_index}}`. Standard: `{"0": {"control":0,"B":1,"C":2}, "1": {"old":0,"new":1}, "2": {"old":0,"new":1}}`. `Recruitment Agencies GB_FR_BE_NL_DE`: `{"0": {"control":0,"legacy":1,"B":2,"C":3}, "1": {"old":0,"legacy":1,"new":2}, "2": {"old":0,"legacy":1,"new":2}}` (verified live 2026-11-02; legacy is disabled). Without `roles` every variant is its own role (`vA`, `vB`…). |
| `monitor --live` | Without it nothing is changed (dry run). |
| env `INSTANTLY_API_KEY` | Instantly v2 bearer key. |
| env `OPENROUTER_API_KEY` | Jev, via `jev_client`. |

Never edit a campaign that is not in `tests`. The orchestrator adds a test entry after pushing the variants.

## Outputs

- `gate`: per copy PASS/FAIL, mean/min `human`, mean `ai_tells`, lowest-scoring render. Exit 1 if any copy fails.
- `validate`: Spearman table on stdout + `.tmp/copy_monitor/validate_<date>.md`; warning line when `human` < 0.2; ledger line `type: validate` with Spearman per question.
- `monitor`: markdown on stdout + `.tmp/copy_monitor/report_<date>.md`: **Scorecard**, then per family a table (step, role, campaigns, sent, positive, human, unsub, auto, P(best), active in N/M) and **Actions**, then inbox alerts. Ledger line `type: monitor`.
- `eval`: PASS/FAIL table on stdout + `.tmp/copy_monitor/eval_<date>.md`; ledger line `type: eval`. Exit 1 if any eval fails.
- Exit codes: 0 OK, 1 gate/eval failed, 2 Instantly/Jev API failure (no actions are taken when classification fails; a monitor failure still writes a ledger line with `error` + technical counters).

## Steps

1. Write the variants into `instantly_copy_variants.json` (ids `<family>_s1_B`, `_s1_C`, `_s2`, `_s3`; plain-text bodies, blank line between paragraphs).
2. Run `gate --copy execution/infrastructure/instantly_copy_variants.json`; rewrite any FAIL using the printed lowest-scoring render; repeat until exit 0.
3. Push the variants: `python3 execution/infrastructure/instantly_copy_sync.py --apply` (dry run first; it must end "0 out of sync" after apply).
4. Add a test entry (campaign_id, name, family, started, roles, baseline_sent snapshot) to `instantly_copy_tests.json`; commit.
5. Run `eval`; every row must PASS.
6. Daily: run `monitor --live`; deliver the report as-is (output contract above); commit the ledger.
7. Weekly: run `validate`; act on the warning line if present.
8. Remove a test entry when the campaign completes or one arm per step remains.

## Decision rules

**Gate PASS:** mean human ≥ 0.55 AND min human ≥ 0.40 AND mean ai_tells ≤ 0.40 (20 renders, seed 7). Merge fields render case-sensitively: firstName→Mark, companyName→Northbridge, location→Dallas, Location→Lyon, sendingAccountFirstName→Deb; any other field renders as its de-camelCased name (`boothSize`→"booth size") so sentences stay grammatical. Merge fields are substituted before spintax. HTML is flattened to text first.

**Reply classification (monitor):** each received email (`ue_type == 2`, `timestamp_email ≥ started`, attributed by `step` = `seq_step_variant`) gets a Jev `kind`: interested / not_interested / unsubscribe_or_complaint / out_of_office / left_company / ticket_autoresponder / bounce_ndr / challenge_response / other. Confidence < 0.6 is low-confidence; low-confidence `interested` counts as `other`. Quoted text is stripped first.

**Metrics per (step, variant):** sent (analytics/steps minus `baseline_sent`), positive = interested, human = interested + not_interested + unsubscribe_or_complaint + other, unsub = unsubscribe_or_complaint, auto = out_of_office + ticket_autoresponder + challenge_response + left_company (proves a live mailbox received it: the inbox proxy).

**Family pooling:** metrics are summed by (family, step, role) across every active (status 1) campaign of the family. A role present in only one campaign (legacy) is still pooled with one member. A role disabled in every campaign is not an arm.

**Actions (pure functions `decide_arms` / `decide_family`, unit-tested):**
- At most ONE role change per family per run. Complaints beat losers.
- Complaints: pooled sent ≥ **150** and unsub/sent > 0.75 % → disable (highest rate first).
- Loser: only when every active role in the step has pooled sent ≥ **180** since test start. Metric = positives; if the step has < 5 positives in total, metric = human − unsub (floor 0). Beta(1+k, 1+n−k), 20k Monte Carlo draws (seed 7) → P(best). If max P(best) ≥ 0.90 and a role has P(best) ≤ 0.05 → disable the lowest-P role.
- Never disable the last active role of a step (family "Held").
- Apply the role's variant index in EVERY campaign of the family: one PATCH per campaign. A campaign where that variant is its step's last active variant is skipped ("held"); one where it is already off is skipped. A candidate with no campaign left to change is not an action (reported held; the next candidate is tried).
- Apply: fresh `GET /api/v2/campaigns/{id}` right before each PATCH (so concurrent copy edits are never reverted), `PATCH` with `{"sequences": <fresh sequences, only that variant's v_disabled = true>}`, re-GET and verify; a failed verify is reported as FAILED.

**Inbox health (alert only):** accounts tagged with any `tag_ids`; 7-day `accounts/analytics/daily`; flag sent ≥ 100 and bounced/sent > 4 %.

## Scorecard

Business and technical metrics, computed from today's ledger line. Δ = today minus the monitor line 6–8 days back (nearest to 7; else "n/a"). Status ✅ met / ⚠️ missed / n/a not measurable (no sends yet, no validate line). Business rates use the `overall` block: step-1 roles pooled by name across all families.

| Metric | Definition | Target |
|---|---|---|
| Positive reply rate | best new step-1 role (B/C) positives / sent | ≥ 1.0 % |
| Uplift vs control | (best new rate / control rate) − 1 on positive rate; human rate when step-1 positives < 5 | > 0 |
| Unsub/complaint rate | unsub / sent, all steps and roles | ≤ 0.5 % |
| Auto (OOO) rate | auto / sent, all steps and roles (inbox proxy) | ≥ 0.8 % |
| Jev low-confidence share | replies with confidence < 0.6 / replies classified | ≤ 15 % |
| Jev errors | Jev calls that errored (incl. ones that succeeded on retry) | = 0 |
| API errors | Instantly calls that failed (HTTP ≥ 400, network, non-JSON, retries exhausted) | = 0 |
| Human-score Spearman | `human` vs reply rate, latest `validate` line | ≥ 0.25 |
| Run time | monitor wall clock | ≤ 600 s |

**Grade** = share of measurable targets met: A ≥ 90 %, B ≥ 75 %, C ≥ 60 %, D ≥ 40 %, else F.

## Ledger

`docs/metrics/instantly_copy_monitor_ledger.jsonl`, one JSON object per line, append-only, `ts` added on write.

- `type: monitor`: `date`, `live`, `run_seconds`, `grade`, `families.<name>` {`campaigns`, `roles.<role>` {sent, positive_rate, human_rate, unsub_rate, auto_rate}, `best_new_role`, `uplift_metric`, `best_new_vs_control_uplift`, `p_new_beats_control` (MC P(best new > control))}, `overall` (same + `totals`), `technical` {jev_calls, jev_cost_usd, jev_errors, jev_low_conf_share, api_retries (429s), api_errors, decisions_made, days_since_start}. A failed run writes `error` + technical counters only.
- `type: validate`: `campaigns`, `spearman.<question>`, `jev_cost_usd`.
- `type: eval`: `results.E1..E5` {pass + numbers}, Jev/API counters.

## Evals (`eval`)

| Eval | What | Pass |
|---|---|---|
| E1 decision determinism | one snapshot (campaigns, step analytics, emails); classify + aggregate + decide twice | identical actions and identical report text (incl. per-campaign detail) |
| E2 re-run stability | two full dry-run monitor passes back to back | identical action list (table line changes reported, they mean sends moved) |
| E3 apply idempotency | offline mock: decide → apply → re-decide; apply twice | no second action for the role, never a step with zero active variants, PATCH body = fetched except the targeted `v_disabled`, twice == once |
| E4 classification | same live replies + fixture classified 3×; fixture accuracy vs hand labels | per-email agreement ≥ 0.95; accuracy ≥ 0.80 |
| E5 gate stability | gate the copy file with seeds 7, 11, 13 | PASS/FAIL identical per copy; per-copy mean-human std ≤ 0.03 |

E1 (on a recorded synthetic snapshot) and E3 also run in pytest.

## Edge Cases

- **`sent` is lifetime, not windowed (verified 2026-11-02).** `analytics/steps` ignores `start_date` for `sent`, and a variant slot keeps the history of any variant deleted from it. Every test carries `baseline_sent` {"step_variant": sends at test start}, which the monitor subtracts. Snapshot it the same day you add the variants.
- **Live test started 2026-11-02:** 11 campaigns, families `recruitment` (8, identical copy), `smb`, `webagency`, `yoga_fr`. Step 1: control = old copy, B = "open for collaborating" subject, C = "idea for…" subject, sharing a new body. Steps 2 and 3: one new variant each. GB_FR carries a disabled legacy variant in every step.
- Instantly 403s urllib's default User-Agent; the scripts use `requests` with a real UA.
- `/emails` is limited to 20 req/min: 3.2 s between calls; 429 → sleep 20 s, retry up to 4 times (counted as `api_retries`).
- Some received emails have no `step`: not attributable, ignored.
- analytics/steps `start_date` does not bound replies; reply counts come from `/emails`.
- Campaigns with status ≠ 1 are listed as skipped and left out of the pool.
- `accounts` pagination cursor is a compound `timestamp&email` string; paging stops on an empty page.
- Any Jev classification error after one retry → exit 2, no actions.
- Copy sync converts plain-text bodies to Instantly HTML as `<div>p</div><div><br /></div>` per paragraph, last paragraph `<div>p</div>`; a dry run reporting "in sync" for all campaigns proves the conversion matches live byte-for-byte (verified 2026-11-02, 11/11).

## Exit Criteria

- `gate`: every copy PASSes (exit 0) before it is pushed.
- `monitor`: exit 0, report written, ledger line appended, every live action reads "Disabled" (verified on re-read), never "FAILED".
- `eval`: exit 0 (E1–E5 PASS) after any change to the decision, classification or gate logic.
- `validate`: exit 0 and no `human` Spearman warning.
- `python3 -m pytest -q tests/test_instantly_copy_monitor.py` passes.

## Schedule

- `monitor --live`: daily cloud scheduled task at 05:23 UTC, plus `validate` on Mondays, in a fresh session on branch `claude/ecstatic-curie-n8mzoj` (or `main` once merged). Its push notification is the report itself. **The scheduled run commits only `docs/metrics/instantly_copy_monitor_ledger.jsonl`.**
- `eval`: after any logic change, and weekly alongside `validate` if cheap enough (≈ 3 monitor passes of Instantly reads + ~1.3k Jev calls).
- `gate`: on demand before any new copy is pushed.

## Changelog

| Date | Change |
|---|---|
| 2026-11-02 | Created. Ported render/Q/spearman from `.tmp/copy_lab/jev_copy_validate.py`; fixed merge-field-inside-spintax and `RANDOM`-as-option bugs; Spearman now uses average ranks for ties. First validate run: 55 campaigns, human +0.31, ai_tells −0.29. |
| 2026-11-02 | Operator thresholds: decision min 400 → 180 sends per arm, complaint min 200 → 150. Family pooling by role (`roles` in config) with one role change per family per run applied across all its campaigns, last-variant guard per campaign, fresh GET before each PATCH. `auto` metric. Scorecard (9 targets, A–F grade, Δ vs ~7 days) + JSONL ledger. `eval` subcommand (E1–E5) + redacted label fixture. Unknown merge fields render as neutral words. `instantly_copy_variants.json` committed; `instantly_copy_sync.py` added (dry run: 11/11 in sync). |
