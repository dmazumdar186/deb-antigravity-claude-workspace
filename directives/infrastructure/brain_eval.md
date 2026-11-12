# Brain eval: weekly, independent, no cover-ups

## Goal

Every week, measure whether the workspace brain (`directives/infrastructure/brain.md`) actually prevents repeat mistakes, at what token cost, and what changed since last week. The verdict comes from an algorithm and an independent judge, never from the model that runs the brain. Every fault line is printed first, and a run cannot quietly rewrite an earlier one.

## Tools/Scripts

`execution/infrastructure/brain_eval.py` (evaluator, read-only towards lessons) · evidence capture in `execution/infrastructure/brain.py` (`hook_prompt` / `hook_stop` → `log_observation`, `judge_turn`) · tests `tests/test_brain_eval.py`.

## Inputs

- `.claude/brain/eval/benchmark.jsonl`: 48 operator prompts (24 tasks, 12 corrections, 12 negatives). A worker that never saw the lessons wrote them on 2026-11-12. They are frozen: editing them raises `goalposts_moved` and suspends benchmark deltas for that run.
- `.claude/brain/eval/thresholds.json`: floors, ceilings, regression tolerances, which alarms FAIL, and the budget. Editing it also raises `goalposts_moved`.
- `.claude/brain/eval/observations/*.jsonl`: live evidence. The Stop hook writes one row per turn that had an injection, a correction or an admission. A row holds lesson ids, sources (kw/jev/both), judge probabilities and flags only. **It never contains prompt text.**
- `.claude/brain/eval/labels.json`: the judge's labels, cached per (judge model, prompt, lesson id, rule-text hash). Week-on-week deltas therefore measure the brain, not judge drift, and an edited rule is re-labelled.

## Outputs

- `.claude/brain/eval/reports/<date>.md`, in this order: verdict, fault lines, KPI table (this run / last run / delta), evidence (misses, noise, repeat mistakes, growth), standing caveats.
- `.claude/brain/eval/history.jsonl`: one hash-chained row per run (`prev_hash`, `row_hash`), holding the KPIs, a lesson-strength snapshot, the hashes of the benchmark, thresholds and evaluator, and the observation count.
- At session start, `brain.py eval_lines()` prints a due or OVERDUE line, and tells Claude to report any WARN or FAIL to the operator in one line in its first reply.

## Steps

1. **Weekly trigger.** Session start shows "Brain eval due" when the last run is 7 or more days old, and "OVERDUE" (reported to the operator) at 9 or more days.
2. **Run.** In a background worker: `python3 execution/infrastructure/brain_eval.py run --label`. The judge is Claude Sonnet on the subscription ($0, at most 60 calls); the retriever replay is one Jev call per prompt (about $0.01). Plain `run` is offline and spends nothing: unlabelled metrics show as unmeasured. `--dry-run` writes nothing.
3. **Independence.** `assert_independent()` refuses to run if the judge is Jev, the model that picks lessons. Live rows are judged by Jev only for keyword-picked lessons; Jev-picked injections are recorded but never self-graded.
4. **Score the benchmark** against the judge's labels (relevant means label ≥ 0.5):
   - **Primary, the deployed hybrid retriever** (keywords + Jev): `precision`, `recall`, `f1`, `effective_recall` (counting core lessons, which are always loaded), `noise_rate` (prompts with no relevant lesson that still got an injection), `avg_inject_chars`.
   - **Keyword-only baseline:** the same metrics with a `kw_` prefix.
   - **Data quality:** `judge_sanity` is the share of the author's negative prompts that the judge left empty; low means every number is suspect. `label_coverage_gap` is the share of unlabelled pairs.
5. **Score live outcomes** over the last 7 days:
   - `live_precision`, `corrections` and `capture_leak` (misses admitted but not recorded).
   - `repeat_mistakes_week`: a correction that an **existing** lesson covered, judged against the lessons as they stood when the prompt arrived. It splits into **never shown** (a trigger or recall gap) and **shown and ignored** (the rule's wording or force is the problem).
6. **Growth and health.** Compare against last run's snapshot for lessons added, strengthened and retired. Also report lint issues, dead lessons (relevant to no benchmark prompt and never injected), and sources that are missing or can't be verified in this clone.
7. **Verdict** (`judge()`, a pure function of the numbers and `thresholds.json`):
   - **FAIL** on `history_tampered`, `evidence_deleted`, an F1 regression, core over cap, or the recall floor.
   - **WARN** on any other breach.
   - **PASS-PARTIAL** when anything is unmeasured.
   - **PASS** only when everything is measured and clean.
8. Commit `.claude/brain/eval/` and fix the top fault line, if there is one, in the same or the next unit of work.

## Edge Cases

- **Tampering.** Editing or reordering a past history row breaks the chain, and every later run FAILs until the operator rules on it. A missing history after a chain existed shows up as `evidence_deleted`, because the observation count is compared with the last row. A wiped repository can't be detected from inside it; git history is the backstop.
- **Overfitting.** The benchmark is visible, so triggers could be tuned to it. The keyword-only baseline, live precision and repeat mistakes are the checks; a widening gap between benchmark and live numbers is the signal.
- **Statistics.** The configured tolerance is 0.05, widened to 2 standard errors of the smaller sample (about 0.10 for F1 on the current 109 relevant pairs); drift since the first baseline tolerates double. The floors still catch absolute drops.
- **Ephemeral cloud.** Observation rows only survive if the session commits them. Live numbers cover committed turns only, and the report says so.
- **`/jev off`.** No retrieval or live-judge call sends prompt text while it is off. The weekly replay sends only the benchmark prompts.
- **Judge failure.** A judge reply without valid JSON leaves the pair unlabelled. It counts toward `label_coverage_gap` and the run is not a PASS.
- **Baseline (2026-11-12, first committed history row): WARN.** Hybrid precision 0.689, recall 0.468, F1 0.557, noise 0.091. Keyword-only: F1 0.229, recall 0.138, noise 0.0. judge_sanity 0.917. Live KPIs are unmeasured (1 logged turn). Two earlier same-day development runs were discarded and are disclosed in that report's run notes: one used Jev as the judge (self-grading), the other ran before the audit fixes. Hybrid numbers vary between runs because Jev's picks are recomputed each time; the `kw_*` numbers are deterministic.
