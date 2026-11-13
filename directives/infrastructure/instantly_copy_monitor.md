# Instantly A/B Copy Monitor

**Output contract:** Daily report = Scorecard + one role table per family (+ its unattributed-replies count and missing-baseline warnings, operator order 2026-11-02, only when non-zero) + Actions (signal-mode families: a "Signal only (no actions)" block instead, operator order 2026-11-02) (+ inbox alerts); nothing else. Per-campaign tables only with `--detail`. Machine state goes to the ledger (`docs/metrics/instantly_copy_monitor_ledger.jsonl`), never into the report.

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
| `execution/infrastructure/instantly_copy_monitor.py` | CLI: `gate`, `validate [--record]`, `monitor [--live] [--detail]`, `eval [--copy] [--record]` |
| `execution/infrastructure/instantly_copy_sync.py` | Sync new-copy variants (step 1 roles B/C, steps 2-3 role `new`) from the copy file; dry run unless `--apply` |
| `execution/infrastructure/instantly_copy_tests.json` | Config: inbox `tag_ids` + `tests` list (campaigns under test) |
| `execution/infrastructure/instantly_copy_variants.json` | The live new copy (gate input, E5 input, sync source, audit trail) |
| `execution/infrastructure/instantly_add_ps.py` | Operator order 2026-11-13 "always keep a ps": appends the spintaxed opt-out P.S. ("if this isn't interesting, please let me know and i'll stop following up.") to every step/variant of campaigns sent from Debanjan accounts (status active/paused/running/unhealthy/bounce-protected; drafts and completed untouched); swaps the old "pps. if you'd rather not hear from me" line; skips French bodies; idempotent on "stop following up". Dry run unless `--apply` (backup per campaign in `.tmp/instantly_ps_backup/`, fresh GET before PATCH, re-GET verify). New copy written into `instantly_copy_variants.json` must keep the P.S. or the sync strips it from live slots. |
| `docs/metrics/instantly_copy_monitor_ledger.jsonl` | Append-only ledger: one line per `monitor --live`, `validate --record`, `eval --record` run (dry runs never write) |
| `tests/test_instantly_copy_monitor.py` | Offline unit tests: render, decisions, pooling, apply idempotency (E3), E1 on a recorded snapshot, scorecard, ledger, sync conversion |
| `tests/fixtures/instantly_reply_labels.json` | 93 redacted, hand-labelled replies (kind + preview) for E4 accuracy |
| `execution/modules/jev_client.py` | Jev (OpenRouter Decisions API) |

## Inputs

| Input | Notes |
|---|---|
| `gate --copy <file>` | JSON list of `{"id","subject","body"}`. Spintax `{{RANDOM \| a \| b}}` and bare `{{a\|b}}`, nesting and merge fields inside options allowed. |
| `--config <file>` | Default the committed `instantly_copy_tests.json`. Test entry: `campaign_id`, `name`, `family`, `started` (YYYY-MM-DD), `control_variant` (display only, optional), `roles`, `baseline_sent`. Optional top-level `families` {name: {`mode`: `act` (default) \| `signal`, `signal_min_sent`: int, default 30}}; an unknown mode or a non-positive `signal_min_sent` → `Config error`, exit 2. |
| `roles` | `{"step": {"role": variant_index}}`. Standard: `{"0": {"control":0,"B":1,"C":2}, "1": {"old":0,"new":1}, "2": {"old":0,"new":1}}`. `Recruitment Agencies GB_FR_BE_NL_DE`: `{"0": {"control":0,"legacy":1,"B":2,"C":3}, "1": {"old":0,"legacy":1,"new":2}, "2": {"old":0,"legacy":1,"new":2}}` (verified live 2026-11-02; legacy is disabled). ProdCraft subject test: `{"0": {"A":0,"B":1,"C":2}, "1": {"only":0}, "2": {"only":0}}`; A/B/C/only are new-copy roles (no control), so with `baseline_sent` 0 their replies need no thread lookup. Without `roles` every variant is its own role (`vA`, `vB`…). |
| `monitor --live` | Without it nothing is changed (dry run) and no ledger line is written. |
| `validate --record`, `eval --record` | Append the run's ledger line (scheduled runs). Without it they only print and write `.tmp/`. |
| env `INSTANTLY_API_KEY` | Instantly v2 bearer key. |
| env `OPENROUTER_API_KEY` | Jev, via `jev_client`. |

Never edit a campaign that is not in `tests`. The orchestrator adds a test entry after pushing the variants.

## Outputs

- `gate`: per copy PASS/FAIL, mean/min `human`, mean `ai_tells`, lowest-scoring render. Exit 1 if any copy fails.
- `validate`: Spearman table on stdout + `.tmp/copy_monitor/validate_<date>.md`; warning line when `human` < 0.2; with `--record`, ledger line `type: validate` with Spearman per question.
- `monitor`: markdown on stdout + `.tmp/copy_monitor/report_<date>.md`: **Scorecard**, then per family a table (a signal family's heading ends "— signal only" and its **Actions** block is replaced by **Signal only (no actions)**, see Signal mode) (step, role, campaigns, sent, positive, human, unsub, auto, P(best), active in N/M), an "Unattributed replies (excluded from counts): N" line when N > 0, a "Warning:" line per campaign without `baseline_sent`, and **Actions**, then inbox alerts. Ledger line `type: monitor` only with `--live`.
- `eval`: PASS/FAIL table on stdout + `.tmp/copy_monitor/eval_<date>.md`; with `--record`, ledger line `type: eval`. Exit 1 if any eval fails.
- Exit codes: 0 OK, 1 gate/eval failed, 2 Instantly/Jev API failure or malformed config/copy JSON (one-line `Config error:` message, no traceback). No actions are taken when classification fails. Any monitor exception (API or unexpected) on a `--live` run writes a ledger line with `error` + technical counters, then the run exits non-zero.

## Steps

1. Write the variants into `instantly_copy_variants.json` (ids `<family>_s1_B`, `_s1_C`, `_s2`, `_s3`; plain-text bodies, blank line between paragraphs).
2. Run `gate --copy execution/infrastructure/instantly_copy_variants.json`; rewrite any FAIL using the printed lowest-scoring render; repeat until exit 0.
3. Push the variants: `python3 execution/infrastructure/instantly_copy_sync.py --apply` (dry run first; it must end "0 out of sync" after apply).
4. Add a test entry (campaign_id, name, family, started, roles, baseline_sent snapshot) to `instantly_copy_tests.json`; commit.
5. Run `eval`; every row must PASS.
6. Daily: run `monitor --live`; deliver the report as-is (output contract above); commit the ledger.
7. Weekly: run `validate --record` (and `eval --record` when scheduled); act on the warning line if present.
8. Remove a test entry when the campaign completes or one arm per step remains.

## Decision rules

**Gate PASS:** mean human ≥ 0.55 AND min human ≥ 0.40 AND mean ai_tells ≤ 0.40 (20 renders, seed 7). Merge fields render case-sensitively: firstName→Mark, companyName→Northbridge, location→Dallas, Location→Lyon, sendingAccountFirstName→Deb; any other field renders as its de-camelCased name (`boothSize`→"booth size") so sentences stay grammatical. Merge fields are substituted before spintax. HTML is flattened to text first.

**Reply attribution (monitor):** a received email (`ue_type == 2`, `timestamp_email ≥ started`, attributed by `step` = `seq_step_variant`) counts only if the outbound email it answers was sent on/after `started`, the same window `sent` is measured on (only control/old slots had pre-test sends, so counting every reply since `started` would credit them with replies to old sends). A slot with no pre-test sends (`baseline_sent` 0/absent while the test has a baseline) is post-test by construction: no lookup. Otherwise `GET /emails?search=thread:<thread_id>&email_type=sent&campaign_id=<campaign>&limit=100` (cached per thread+campaign, ≤ **40 lookups per family per run**, budgets reset each pass, same 20 req/min pacing) returns the thread's sends; the items are then **post-filtered to `thread_id == reply.thread_id` and `campaign_id == campaign`** (never trust the API filter alone; discards counted in ledger `thread_items_foreign`), and the latest outbound with the reply's `step` at or before the reply; its `timestamp_email` is compared to `started`. Replies to pre-test sends are excluded (ledger `replies_pre_test`); replies with no step, no thread, no matching outbound or past the family's lookup budget are excluded and reported as unattributed (report line, with "thread-lookup budget exhausted for n" when the budget ran out, + ledger `replies_unattributed`, `thread_lookups`, `thread_lookups_refused`). Applies to positive/human/unsub/auto alike.

**Lookup verified live 2026-11-02** (read-only GETs on 4 received replies across Recruitment UK `e21c42f9` and Hong Kong `81d17690`): `search=thread:<id>` IS honoured. `search+email_type=sent`: n = 2/2/3/2 items, all with the reply's `thread_id` (0 foreign) and the same `campaign_id`; adding `campaign_id` returned the identical sets; without `email_type` the reply itself (`ue_type 2`) is added. `email_type=sent` can also return a manual send (`ue_type 3`, `step` null) and sends dated after the reply; `outbound_for` ignores both. OpenAPI (`/api/v2/emails` GET) documents `search` ("thread:" prefix), `campaign_id`, `lead`, `email_type` (received/sent/manual); there is no `thread_id` param.

**Reply classification (monitor):** each attributed reply gets a Jev `kind`: interested / not_interested / unsubscribe_or_complaint / out_of_office / left_company / ticket_autoresponder / bounce_ndr / challenge_response / other. Confidence < 0.6 is low-confidence; low-confidence `interested` counts as `other`. Quoted text is stripped first.

**Metrics per (step, variant):** sent (analytics/steps, called WITHOUT `start_date`, minus `baseline_sent`), positive = interested, human = interested + not_interested + unsubscribe_or_complaint + other, unsub = unsubscribe_or_complaint, auto = out_of_office + ticket_autoresponder + challenge_response + left_company (proves a live mailbox received it: the inbox proxy).

**Family pooling:** metrics are summed by (family, step, role) across every active (status 1) campaign of the family. A role present in only one campaign (legacy) is still pooled with one member. A role disabled in every campaign is not an arm.

**Actions (pure functions `decide_arms` / `decide_family`, unit-tested):**
- At most ONE role change per family per run. Complaints beat losers.
- Complaints: pooled sent ≥ **150** and unsub/sent > 0.75 % → disable (highest rate first).
- Loser (per-arm eligibility, 2026-11-02): an active role is **eligible** once its pooled sent since test start (post-baseline) is ≥ **180**. When ≥ 2 roles of a step are eligible they are compared among themselves; roles below 180 are "warming up": never disabled as losers, never block a decision among the eligible ones, and shown in the P(best) column as `warming up (n/180)`. Metric = positives; if the eligible roles have < 5 positives in total, metric = human − unsub (floor 0). Beta(1+k, 1+n−k), 20k Monte Carlo draws (seed 7) → P(best) over eligible roles only. If max P(best) ≥ 0.90 and a role has P(best) ≤ 0.05 → disable the lowest-P role. Complaint rule unchanged (every active role).
- Never disable the last active role of a step (family "Held").
- **Attribution guard (symmetric safety):** only base-role (control/old/legacy) replies need the thread lookup, so any lookup failure undercounts control alone and would make it look like the loser. If a family has unattributed > 0 OR its lookup budget was exhausted this run, every loser decision (any role) and every complaint decision on a base role is HELD for that run ("Held: step s role r (reason): attribution incomplete (n unattributed[, thread-lookup budget exhausted for k])"). Complaint-safety on NEW roles (B/C/new: replies kept without lookup) still proceeds. Fallback `vA`-style roles count as base.
- Apply the role's variant index in EVERY campaign of the family: one PATCH per campaign. A campaign where that variant is its step's last active variant is skipped ("held"); one where it is already off is skipped. A candidate with no campaign left to change is not an action (reported held; the next candidate is tried).
- Apply: fresh `GET /api/v2/campaigns/{id}` right before each PATCH (so concurrent copy edits are never reverted), `PATCH` with `{"sequences": <fresh sequences, only that variant's v_disabled = true>}`, re-GET and verify; a failed verify is reported as FAILED.

## Signal mode (2026-11-02)

For families whose lists are too small for any arm to reach the 180-send decision minimum (ProdCraft Proposal Engine: 430 leads over 19 campaigns). Set per family in config `families.<name>.mode = "signal"`; a family not listed is `act` (everything above, unchanged).

- Pooling, metrics, attribution and P(best) are the same as act mode (`step_metric`, Beta MC, seed 7), but P(best) runs over active roles with ≥ `signal_min_sent` (default **30**) post-baseline sends, once ≥ 2 roles qualify. Roles below show `warming up (n/30)`.
- **Never an action** (pure `decide_signal`: `action` and `plan` are always None; `run_monitor` also skips apply for any non-act family). No loser disable, no complaint disable.
- Report lines, per step with ≥ 2 roles: "Signal: step s role X leading, P(best)=p on <metric> (n sends/arm), not acted on — list too small", or "No signal yet: step s needs >= 30 sends on >= 2 roles (A n, B n, C n)". If the act-mode complaint rule (≥ 150 sent, > 0.75 %) would have fired: "ALERT (not acted on): step s role X unsub rate y% (k/n)". Single-variant steps (`only`) get no signal line.
- Treat any leader as a signal for the operator only, until the lists grow; then switch the family to `act` (delete its `families` entry) and A/B/C are decided as usual.
- `instantly_copy_sync.py` skips signal-mode families ("skipped … signal-only family, copy not managed here"): their copy is not in `instantly_copy_variants.json`.

**Inbox health (alert only):** accounts tagged with any `tag_ids`; 7-day `accounts/analytics/daily`; flag sent ≥ 100 and bounced/sent > 4 %.

## Scorecard

Business and technical metrics, computed from today's ledger line. Δ = today minus the **live** monitor line (`type: monitor`, `live: true`) 6–8 days back (nearest to 7; else "n/a"); dry runs are never a baseline. Status ✅ met / ⚠️ missed / n/a not measurable (no sends yet, no validate line). Business rates use the `overall` block: step-1 roles pooled by name across all **act-mode** families (signal families are excluded from `overall`, so grading stays driven by the act-mode tests; their own numbers are in their ledger family rows). It is labelled **cross-family (reporting only)** (`overall.label`): it pools one family's control with another's, so it feeds the scorecard and never a decision.

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

**Grade** = share of measurable targets met: A ≥ 90 %, B ≥ 75 %, C ≥ 60 %, D ≥ 40 %, else F, **only when** ≥ 1 business metric (positive rate, uplift, unsub rate, auto rate) is measurable AND ≥ 7 of 9 metrics are measurable. A business metric is measurable only on ≥ **50** post-baseline sends in its underlying pool: positive rate needs a new role with ≥ 50 step-1 sends; uplift needs the best new role AND control/old ≥ 50; unsub and auto rates need ≥ 50 total sends (2026-11-02: a "Grade B" came from 55 sends and 0 replies). Otherwise the grade is `n/a (k/9 measurable)` (dropping n/a metrics from the denominator alone graded a no-data day "A" on 5/9 technical targets).

## Ledger

`docs/metrics/instantly_copy_monitor_ledger.jsonl`, one JSON object per line, append-only, `ts` added on write. Written only by `monitor --live` and by `validate` / `eval` with `--record` (those rows carry `record: true`); dry runs and ad-hoc checks never write it.

- `type: monitor`: `date`, `live` (always true), `run_seconds`, `grade`, `families.<name>` {`campaigns`, `mode` (act/signal), `p_best` {"s<step>:<role>": p}, `roles.<role>` {sent, positive_rate, human_rate, unsub_rate, auto_rate}, `best_new_role`, `uplift_metric`, `best_new_vs_control_uplift`, `p_new_beats_control` (MC P(best new > control))}, `overall` (same + `totals` + `label: "cross-family (reporting only)"`), `technical` {jev_calls, jev_cost_usd, jev_errors, jev_low_conf_share, api_retries (429/5xx), api_errors, decisions_made, replies_pre_test, replies_unattributed, thread_lookups, thread_lookups_refused, thread_items_foreign, days_since_start}. A failed run writes `live: true` + `error` + technical counters only.
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

- **`sent` is lifetime, not windowed (verified 2026-11-02).** `analytics/steps` ignores `start_date` for `sent`, and a variant slot keeps the history of any variant deleted from it. Every test carries `baseline_sent` {"step_variant": sends at test start}, which the monitor subtracts. Snapshot it the same day you add the variants. A test without `baseline_sent` gets a "Warning:" line in its family section and is counted lifetime.
- **Never pass `start_date` to `analytics/steps`: treat it as unreliable.** On 2026-11-02 a call with `start_date` = the variants' creation day omitted the new variants' rows (San Diego: no start_date → B=5, C=4; start_date=2026-11-02 → rows missing; 2026-11-01 → present). A later re-check the same day returned identical rows with and without it, so the omission was transient, not deterministic. Either way it adds nothing (`sent` ignores it; `baseline_sent` does the windowing), so the monitor keeps it omitted.
- **Lifetime-balancing routing (observed 2026-11-02).** Since the test started, Instantly routed ZERO sends to control/old in all 11 campaigns; everything went to B/C/new. Instantly appears to balance variants by lifetime send count, so control/old get no new sends until the new arms catch up with control's pre-test history (`baseline_sent`, e.g. 669 on SMB step 1). Timeline impact: B-vs-C (and new-vs-new) decisions can happen as soon as both reach 180 post-baseline sends; control/old only become eligible (and comparable to the winner) after the new arms have passed control's lifetime count and control has then accrued 180 fresh sends, i.e. weeks later on the larger campaigns. That is why eligibility is per arm, not "every active arm ≥ 180".
- **Live test started 2026-11-02:** 11 campaigns, families `recruitment` (8, identical copy), `smb`, `webagency`, `yoga_fr`. Step 1: control = old copy, B = "open for collaborating" subject, C = "idea for…" subject, sharing a new body. Steps 2 and 3: one new variant each. GB_FR carries a disabled legacy variant in every step.
- **ProdCraft Proposal Engine test, launched 2026-11-02 (signal mode):** 19 campaigns, sending tag "Deb_Oct 6 26" (`cebb93b4-…` added to `tag_ids`), families `proposal_eventav` (7: US/UK × Personalized/NoPersonalization (+CatchAll)), `proposal_fitout` (6, US+UK pooled), `proposal_dmc` (6). Each: step 1 = A/B/C subjects (A = the operator's "partnership request" subject, labelled A, not control), one shared body; steps 2-3 one variant (`only`). Verified live 2026-11-02 (GET): all status 1, layout [3,1,1], nothing disabled, step-1 bodies identical. `baseline_sent` snapshotted at add time with explicit zeros for every slot (an empty `{}` would trigger the missing-baseline warning); 7 campaigns had already sent 1-4 per step-1 arm on launch day, those are subtracted (and their slots then go through the thread lookup). 430 leads total: no arm reaches 180, hence signal mode.
- Instantly 403s urllib's default User-Agent; the scripts use `requests` with a real UA.
- `/emails` is limited to 20 req/min: 3.2 s between calls (reply pages and thread lookups share the pacing); 429 and 500/502/503/504 → sleep 20 s, retry up to 4 times (counted as `api_retries`).
- Paging (`/emails`, `/accounts`, `/campaigns`) stops after 200 pages, on an empty page, or when the cursor repeats.
- Some received emails have no `step`: not attributable, excluded and counted as unattributed (which holds that family's loser/base-complaint decisions for the run).
- Thread-lookup budget is per family (40/run), so a large family (recruitment, 8 campaigns) cannot starve the others; worst case 4 families × 40 × 3.2 s ≈ 8.5 min of lookups. If a family exhausts its budget every day its decisions stay held: raise `MAX_THREAD_LOOKUPS` rather than drop the guard.
- If Instantly ever stops honouring `search=thread:` (returns account-wide sends), the post-filter discards every foreign item, the replies become unattributed and decisions are held (fail-safe, visible as `thread_items_foreign` > 0 in the ledger).
- analytics/steps `start_date` does not bound replies; reply counts come from `/emails`.
- Campaigns with status ≠ 1 are listed as skipped and left out of the pool.
- `accounts` pagination cursor is a compound `timestamp&email` string; paging stops on an empty page.
- Any Jev classification error after one retry → exit 2, no actions.
- Copy sync converts plain-text bodies to Instantly HTML as `<div>p</div><div><br /></div>` per paragraph, last paragraph `<div>p</div>`, a single newline inside a paragraph → `<br />`, `& < >` HTML-escaped (quotes, accents, « » untouched); a dry run reporting "in sync" for all campaigns proves the conversion matches live byte-for-byte (verified 2026-11-02, 11/11, also after the escape change).
- Copy sync skips campaigns with status ≠ 1 (as the monitor does); a test entry without `roles`/`family`, a missing copy id, or a live sequence lacking a wanted slot prints an `error` line for that campaign (exit 1) instead of a traceback. After `--apply`, verification re-GETs and requires the wanted slots to match AND everything else (other variants, step-level fields such as `delay`, sequence fields) to be unchanged.
- Malformed config or copy JSON (monitor and sync) → `Config error: …` on stderr, exit 2.
- A live apply that hits a malformed campaign payload marks that campaign FAILED and continues with the others.

- **Inbox-health signals (learned in the 2026-11-02 audit):** Instantly's 100% warm-up health score only measures its own warm-up network, so never read it as cold-email inbox placement. `GET /accounts/analytics/daily` accepts at most a 31-day window per call. Out-of-office auto-replies fire only for inboxed mail; this workspace's baseline is ~1.2% per new prospect. `match_lead_esp=true` means Google and Microsoft senders reach different prospect pools, so don't compare providers directly. With `prioritize_new_leads=false`, follow-ups take the daily cap and the new-prospect count collapses (the operator turned it on 2026-11-02).
- **Placement tests:** `POST /inbox-placement-tests` (`emails` = sender inboxes, `recipients_labels` from `/email-service-provider-options`) returns 402 once the plan's free tests are used up.
- **Blacklist checks:** query SURBL through Google DoH (`dns.google/resolve`); Cloudflare DoH returns empty answers even for `test.surbl.org`. 127.0.0.64 = SURBL abuse list (prodcraftteam.co and anchorcadencegroup.co were listed on 2026-11-02).

## Exit Criteria

- `gate`: every copy PASSes (exit 0) before it is pushed.
- `monitor --live`: exit 0, report written, ledger line appended, every live action reads "Disabled" (verified on re-read), never "FAILED".
- `eval`: exit 0 (E1–E5 PASS) after any change to the decision, classification or gate logic.
- `validate`: exit 0 and no `human` Spearman warning.
- `python3 -m pytest -q tests/test_instantly_copy_monitor.py` passes.

## Schedule

- `monitor --live`: daily cloud scheduled task at 05:23 UTC, plus `validate --record` on Mondays (and `eval --record` when run on schedule), in a fresh session on branch `claude/ecstatic-curie-n8mzoj` (or `main` once merged). Its push notification is the report itself. **The scheduled run commits only `docs/metrics/instantly_copy_monitor_ledger.jsonl`.**
- `eval`: after any logic change (no `--record`), and weekly alongside `validate` with `--record` if cheap enough (≈ 3 monitor passes of Instantly reads + ~1.3k Jev calls).
- `gate`: on demand before any new copy is pushed.

## Changelog

| Date | Change |
|---|---|
| 2026-11-02 | Created. Ported render/Q/spearman from `.tmp/copy_lab/jev_copy_validate.py`; fixed merge-field-inside-spintax and `RANDOM`-as-option bugs; Spearman now uses average ranks for ties. First validate run: 55 campaigns, human +0.31, ai_tells −0.29. |
| 2026-11-02 | Operator thresholds: decision min 400 → 180 sends per arm, complaint min 200 → 150. Family pooling by role (`roles` in config) with one role change per family per run applied across all its campaigns, last-variant guard per campaign, fresh GET before each PATCH. `auto` metric. Scorecard (9 targets, A–F grade, Δ vs ~7 days) + JSONL ledger. `eval` subcommand (E1–E5) + redacted label fixture. Unknown merge fields render as neutral words. `instantly_copy_variants.json` committed; `instantly_copy_sync.py` added (dry run: 11/11 in sync). |
| 2026-11-02 | Audit fixes. (1) `analytics/steps` called without `start_date` (it dropped new-variant rows on the creation day). (2) Replies count only when the answered outbound was sent on/after `started` (thread lookup, cached, ≤ 75/run); others reported as pre-test (ledger) or unattributed (report + ledger). (3) Grade only with ≥ 1 business metric and ≥ 7/9 measurable, else `n/a (k/9 measurable)`. (4) Ledger: monitor writes only with `--live`, validate/eval only with `--record`; Δ-7d uses live monitor rows only; dry-run monitor row scrubbed, validate/eval rows from real 2026-11-02 runs kept with `record: true`. (5) Apply loop survives malformed campaign payloads per target; any monitor exception writes a technical ledger row (live only) and exits non-zero. (6) Sync: HTML-escape + single-newline `<br />`, skips status ≠ 1, friendly config/shape errors, verification covers step-level fields. (7) Page cap + repeating-cursor guard on `/emails`; 5xx retried like 429. (8) Malformed config JSON → exit 2. (9) Missing `baseline_sent` → family warning. (10) `overall` labelled cross-family (reporting only). |
| 2026-11-02 | Attribution safety (code-review HIGH/MEDIUM). (1) Thread lookup verified live (see Decision rules) and now sends `campaign_id`; items post-filtered to the reply's thread + campaign. (2) Symmetric guard: unattributed > 0 or budget exhausted in a family → hold every loser and base-role complaint decision that run; new-role complaint-safety still proceeds. (3) Lookup budget 40 per family per run (was 75 shared in config order), reset each pass incl. eval E1/E2; cache per thread+campaign. (4) Technical-only ledger row carries `live: true`; sync `to_html` strips outer whitespace before splitting paragraphs. Ledger technical adds `thread_lookups`, `thread_lookups_refused`, `thread_items_foreign`. |
| 2026-11-02 | Pipeline re-audit. (A) Loser eligibility per arm: compare roles with ≥ 180 post-baseline sends among themselves once ≥ 2 qualify; arms below are `warming up (n/180)` in the P(best) column, never disabled as losers and never blocking (Instantly routes no sends to control/old until new arms catch up). (B) Scorecard business metrics measurable only on ≥ 50 post-baseline sends. (C) `start_date` note reworded (omission was transient; keep it omitted); lifetime-balancing routing documented. |
| 2026-11-02 | Signal mode: config `families` policy (`act` default / `signal` + `signal_min_sent` 30), `decide_signal` (pooled P(best) over roles ≥ 30 sends, never an action; complaint rule → "ALERT (not acted on)"), report "— signal only" sections, ledger family rows gain `mode` + `p_best`, `overall`/scorecard pool act-mode families only. Roles A/only added to ROLE_ORDER (new-copy roles). Added the 19-campaign ProdCraft Proposal Engine test (3 signal families) + tag `cebb93b4-…`. Sync skips signal families. |
