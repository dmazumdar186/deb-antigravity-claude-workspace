# Jev Validation Set (use case 8)

## Goal
Verify Jev's categorization before trusting it: run Jev over a few dozen to a few hundred examples whose
right answer you already know, without showing it the answers, count matches, then read the misses —
that is where you calibrate the criteria descriptions and the confidence threshold.

## Operator prompt
"Validate Jev on <labelled csv> using <spec>"

## Inputs
- **Spec** (JSON): `{"state_fields": [...], "question_name": "category", "question": {"type": "choice|noul|score",
  "instructions": "...", "criteria": {...}}, "label_field": "label", "id_field": "id"}` — `question` is exactly
  what `jev_client.choice()/noul()/score()` build. Examples: `execution/infrastructure/jev_specs/inquiry_triage.json`,
  `comment_intent.json`.
- **Data**: CSV or JSON list; one row per example with the state fields plus the label. Only `state_fields`
  are sent to Jev. Labels: choice = option key; noul = true/false (yes/no/1/0 ok); score = level index.
- Env `OPENROUTER_API_KEY` (cloud alias `OPENROUTER_API_TOEKN`).

## Tools
- `execution/infrastructure/jev_validate.py` — CLI.
- `execution/modules/jev_eval.py` — `evaluate`, `threshold_sweep`, `suggestions`, `format_report`.

```
python3 execution/infrastructure/jev_validate.py --spec execution/infrastructure/jev_specs/inquiry_triage.json \
  --data .tmp/labelled.csv --sweep --output .tmp/jev_validation.md --json .tmp/jev_validation.json
```
Flags: `--threshold 0.6` (report coverage/accuracy at that cut), `--limit`, `--workers 8`, `--dry-run` (no API call).

## Calibration loop
1. **Build the set** — 30-300 real examples, labelled by a human, covering every class (≥5 each) and some hard cases.
2. **Run** with `--sweep`.
3. **Read the mismatches** (sorted by confidence). High-confidence misses usually mean a wrong label or two
   overlapping descriptions; low-confidence misses mean a vague description.
4. **Edit the criteria** in the spec — sharpen descriptions, say what a class is NOT, add short examples.
   Fix wrong labels in the set.
5. **Re-run** and compare accuracy/F1. Stop when accuracy plateaus.
6. **Pick the threshold** from the sweep: the lowest threshold whose accuracy-on-covered meets your bar
   (e.g. 95%) — that is the production `--min-confidence`; items below it go to a human.
7. Copy the final criteria back into the production script (e.g. `jev_inquiry_triage.py` DEFAULT_CATEGORIES).

## Outputs
Markdown report (stdout / `--output`): accuracy, per-class P/R/F1, confusion matrix, top 20 mismatches,
threshold sweep, rule-based "what to fix". `--json` holds full per-item results. Ledger row `caller=jev_validate`.

## Edge cases
- Rows with empty labels are skipped. API errors count as wrong (`<error>`) and are reported; re-run.
- Score questions: exact-level accuracy plus MAE; no sweep (no confidence).
- Noul confidence = max(p, 1-p).
- Cost is input-only (~$0.042/MTok); 100 rows ≈ fractions of a cent.

## Changelog
- 2026-10-07: Created (RoboNuggets use case 8). Generalizes the ad-hoc `--validate` flags in
  `jev_inquiry_triage.py` and `jev_customer_health.py`.
