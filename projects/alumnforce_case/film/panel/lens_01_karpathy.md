# Lens 1 — Karpathy (measurement)

**Verdict: NOT CLEAR.** The facts were checked carefully, but the film's effect was never measured. All 31 metrics test the file; none tests a viewer. Nothing shows it speeds understanding or recall of 2→26→49→6.

## High

1. **Number-audibility check is vacuous.** `asr_fact_numbers_audible` = "0/0 PASS" (EVAL_REPORT_v1.md:35). Narration spells numbers out and `film_eval.py:1117` extracts digits only. *Fix:* convert number words to digits first; total == 0 means FAIL.
2. **No viewer outcome, and the teardown's duration limit was ignored.** Teardown: >45 s risks "gimmick", use 30–40 s (LEMO_TEARDOWN.md:207). The film runs 76.25 s, and no metric checks length. *Fix (a):* 6 PMs per arm, film vs a static slide with the same facts for 76 s. Score recall of the four numbers in order plus why each changes (0–8), the answer to "why 6, not 49?", and recall again at 24 h. **Falsifier:** film ≤ static, or a 35 s cut scores the same. Six per arm only catches misreadings; detecting 40%→80% recall needs about 23 per arm.
3. **Jev "supported" is uncalibrated and asks the wrong question.** F19, verbatim from the sheet, scored 0.19 (EVAL:131). The prompt (`film_eval.py:1143`) asks if the claim is true, not if it is in the sheet. The cutoffs (0.8 mean, 0.5 flag, `:76`) were set on n=16, so 0.794 vs 0.8 is noise. *Fix:* 60 hand-labelled lines: 20 verbatim, 20 paraphrased, 20 corrupted. Report AUROC, then set the cutoff at ≥95% recall on the corrupted lines. Keep it advisory until AUROC ≥ 0.9.

## Medium

4. **Thresholds are borrowed, not derived.** The wpm count (`:73`) includes silences and the tail; a number-heavy film may want slow pace. 42 chars and 17 CPS are broadcast two-line norms. Word counts disagree: 155/159/156/161 (BUILD_LOG:47,15; EVAL:98,135). *Fix:* one tokenizer, count speech time only, and cite a source for each threshold.
5. **BUILD_LOG: measured vs claimed.** *Measured:* timings, LUFS/peak, blackdetect, ASR 0.9906, readcheck, cuecheck, file size. *Claimed:* "reads well at 1080p" (:90, author's own contact sheet), "deterministic"/reproducible (:144, never rebuilt from `src/`), 15.9 dB music gap (:113, no method given). *Missing:* token cost, which is what decides adoption.
6. **Campaign A/B (b).** Use three arms: plain text / static image + link / GIF poster + video link. Use spam placement as a guardrail. Cold email, positive replies 3%→4%: about 5,300 per arm (α 0.05, power 0.8), 3–4 weeks at 500/day. LinkedIn ads, CTR 0.5%→0.65%: about 40k impressions per arm. AlumnForce customer profile-update completion within 14 days, 8%→10%: about 3,200 per arm, one send for a school with 20k alumni.

## Low

7. The fidelity FAILs are mostly false positives on S-ids, 1920×1080 and UI labels (EVAL:46–63, 78–95). One real catch: "Four answers" (L02, Jev 0.32), since no fact contains 4. *Fix:* skip metadata tokens and add "four answers = F07/F08/F09/F12" to FACTS.

## Honest gaps

I didn't watch the film. Base rates are industry-typical, not the candidate's data. I didn't find the talk's time limit. I didn't test Jev's run-to-run variance.
