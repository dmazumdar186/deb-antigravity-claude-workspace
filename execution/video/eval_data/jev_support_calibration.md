# Jev support calibration (film_eval)

Date 2026-11-01 · model typesafe/jev-1.13-20260917 · N=3 repeats · prompt 23ed4e21bcad3a8b · FACTS sha256 71c2e0c30625a17d · cost $0.015768

Labelled set: `jev_support_labels.csv`, 61 lines hand-labelled against the case FACTS.md (state.facts). Scores are the mean noul over the repeats. Threshold = max Youden J; a line is predicted positive when its score >= threshold.

| Question | n (pos/neg) | AUROC | Best threshold | TP | FP | FN | TN |
|---|---|---|---|---|---|---|---|
| (a) claim: makes a factual claim | 61 (43/18) | 1.000 | 0.37 | 43 | 0 | 0 | 18 |
| (b) entailed: stated in the fact sheet | 43 (21/22) | 1.000 | 0.4317 | 21 | 0 | 0 | 22 |
| (c) contradiction | 43 (12/31) | 1.000 | 0.5717 | 12 | 0 | 0 | 31 |

(b) and (c) are scored on the claim lines only (gold `claim=1`), as in the film run.

Recall-95 point for (b): flag below 0.0401 catches >= 95 % of unsupported lines with 0 supported lines falsely flagged.
Repeat stability: mean spread 0.0076, max 0.07 (noul units).

film_eval reads `jev_support_thresholds.json`: entailment flags a claim line whose mean is below the (b) threshold, contradiction flags a line at or above the (c) threshold. Flags FAIL only when that question's AUROC >= 0.9, otherwise they WARN.

## Per-category means

| Category | n | claim | entailed | contradiction |
|---|---|---|---|---|
| verbatim_supported | 11 | 0.96 | 0.95 | 0.03 |
| paraphrase_supported | 10 | 0.96 | 0.94 | 0.03 |
| wrong_number | 12 | 0.97 | 0.02 | 0.95 |
| unsupported_claim | 10 | 0.94 | 0.02 | 0.09 |
| rhetorical_no_claim | 9 | 0.03 | 0.22 | 0.04 |
| call_to_action | 9 | 0.03 | 0.13 | 0.06 |

## Entailment errors at threshold 0.4317

- none
