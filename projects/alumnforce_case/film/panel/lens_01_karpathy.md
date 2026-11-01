# Lens 1 — Karpathy (measurement)

**Verdict: NOT CLEAR.** The film's facts were checked carefully. Whether it does its job was never measured. All 31 eval metrics test the artefact (codec, LUFS, subtitle CPS, string matches). None tests a viewer. No result in the folder could show that the film helps the panel understand or remember 2→26→49→6.

## High

1. **The number check passes with nothing to check.** `asr_fact_numbers_audible` reads "0/0 PASS" (EVAL_REPORT_v1.md:35). The narration spells numbers out ("forty-nine"), and `film_eval.py:1117` pulls out digits only, so the denominator is zero. BUILD_LOG.md:15 says "every number is heard correctly", but that rests only on `final_asr.py`. *Fix:* convert number words to digits before extraction, and report FAIL when total == 0.
2. **No viewer outcome, and the one duration guide was ignored.** The teardown says over 45 s risks looking like a gimmick and advises a 30–40 s open (LEMO_TEARDOWN.md:207). The film runs 76.25 s, and no metric checks length. *Fix (a), minimum experiment:* two arms with 6 people each (PMs, not panel members). One arm sees the film; the other sees a static slide with the same facts for the same 76 s. Measure: free recall of the four numbers in order plus why each changed (0–8), the answer to "why 6, not 49?", and the same recall 24 h later. **Falsifier:** film arm ≤ static arm, or a 35 s cut scores the same. Be honest about power: 6 per arm only catches viewers who misunderstand. Detecting 40%→80% recall needs about 23 per arm.
3. **Jev "supported" is uncalibrated and asks the wrong question.** F19, copied word for word from the fact sheet, scored 0.19 (EVAL:131). The prompt (`film_eval.py:1143`) asks whether the claim is *true*. For a product promise ("no record leaves the platform"), that differs from *is it in the sheet*. The pass mark (mean ≥ 0.8, flag < 0.5, `film_eval.py:76`) comes from n = 16, and 0.794 vs 0.8 is noise. *Fix:* a labelled set of 60 lines: 20 copied word for word, 20 paraphrased, 20 corrupted (wrong number, swapped fact, invented quote), each labelled by hand as supported or not. Report AUROC, then set the cutoff where corrupted lines are caught ≥ 95% of the time. Keep it advisory until AUROC ≥ 0.9.

## Medium

4. **The thresholds are borrowed, not derived.** 130–170 wpm (`:73`): the denominator counts silences and the 3 s tail, and a slow pace may suit a film full of numbers. 42 chars per line and 17 CPS are broadcast two-line norms. −16 LUFS doesn't matter in a meeting room. Word counts disagree: 155 / 159 / 156 / 161 (BUILD_LOG:47,15; EVAL:98,135). *Fix:* use one tokenizer, time speech only, and record where each threshold comes from.
5. **Measured vs claimed in BUILD_LOG.** *Measured:* stage timings, LUFS/peak, blackdetect, the ASR ratio 0.9906, readcheck, cuecheck, file size. *Claimed:* "reads well at 1080p" (:90, author's own contact sheet), "deterministic" and "reproducible" (:144, the build was never rerun from `src/`), the 15.9 dB music gap (:113, method not stated), and token cost (not recorded at all). That last one is the input that decides whether to adopt the toolkit.
6. **Campaign A/B (b).** Use three arms, not two: plain text / static image + link / GIF poster + video link. Otherwise "has a link and an image" is confounded with "is a video". Track deliverability (spam placement) as a guardrail. Detecting cold-email positive replies going from 3%→4% needs about 5,300 per arm (α 0.05, power 0.8), which is 3–4 weeks at 500 sends a day. LinkedIn ads, CTR 0.5%→0.65%: about 40k impressions per arm, using Campaign Manager's split test (to avoid divergent delivery). The cheapest test is for AlumnForce customers: profile updates completed within 14 days going from 8%→10% needs about 3,200 per arm, which is one send for a school of 20k.

## Low

7. The "number_fidelity_script" and "quote_fidelity" FAILs are mostly false positives on S-ids, 1920×1080 and UI labels (EVAL:46–63, 78–95). The only real catch is "Four answers" (L02, Jev 0.32): no fact contains "4". *Fix:* skip metadata/ID tokens, and add "four answers = F07/F08/F09/F12" to FACTS.
8. A 4.29 s freeze during the 1/5/43 split (EVAL:42) is probably a deliberate hold. Confirm it.

## Honest gaps

I did not watch the film or listen to it. Base rates (3% reply, 0.5% CTR, 8% update) are typical industry figures, not the candidate's data. I didn't find the talk's time limit. I didn't rerun Jev to check how much its scores vary between runs.
