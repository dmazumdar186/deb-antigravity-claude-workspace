# Jev support calibration (film_eval)

Date 2026-11-01 · model typesafe/jev-1.13-20260917 · N=3 repeats · prompt 23ed4e21bcad3a8b · FACTS sha256 71c2e0c30625a17d · cost $0.017322

Labelled set: `jev_support_labels.csv`, 67 lines hand-labelled against the case FACTS.md (state.facts). Scores are the mean noul over the repeats. Threshold = max Youden J; a line is predicted positive when its score >= threshold.

| Question | n (pos/neg) | AUROC | Best threshold | TP | FP | FN | TN |
|---|---|---|---|---|---|---|---|
| (a) claim: makes a factual claim | 67 (49/18) | 1.000 | 0.3683 | 49 | 0 | 0 | 18 |
| (b) entailed: stated in the fact sheet | 49 (24/25) | 0.990 | 0.705 | 24 | 1 | 0 | 24 |
| (c) contradiction | 49 (14/35) | 1.000 | 0.2883 | 14 | 0 | 0 | 35 |

(b) and (c) are scored on the claim lines only (gold `claim=1`), as in the film run. Separation margin (lowest positive score vs highest negative): claim 0.6867 vs 0.05; entailed 0.8167 vs 0.93; contradiction 0.35 vs 0.2267

Recall-95 point for (b): flag below 0.5934 catches >= 95 % of unsupported lines with 0 supported lines falsely flagged.
Repeat stability: mean spread 0.0084, max 0.1 (noul units).

film_eval reads `jev_support_thresholds.json`: entailment flags a claim line whose mean is below the (b) threshold, contradiction flags a line at or above the (c) threshold. Flags FAIL only when that question's AUROC >= 0.9, otherwise they WARN.

## Per-category means

| Category | n | claim | entailed | contradiction |
|---|---|---|---|---|
| verbatim_supported | 11 | 0.96 | 0.95 | 0.03 |
| paraphrase_supported | 10 | 0.96 | 0.94 | 0.03 |
| wrong_number | 12 | 0.97 | 0.02 | 0.95 |
| unsupported_claim | 10 | 0.94 | 0.02 | 0.09 |
| rhetorical_no_claim | 9 | 0.03 | 0.23 | 0.04 |
| call_to_action | 9 | 0.03 | 0.14 | 0.06 |
| hard_mixed | 6 | 0.93 | 0.73 | 0.25 |

## Entailment errors at threshold 0.705

- H02 [hard_mixed] gold supported=0 score 0.93: Six can be e-mailed today.
