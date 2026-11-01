# Lens 8 — Sutskever: capability and failure modes

**Verdict: NOT CLEAR.** The film looks factually clean. The bounds around it don't hold: the picture has no bound, and the spoken-number check checks nothing.

The model writes the script, every pixel, the score and the mix. Audio is bounded (BUILD_LOG.md:12-15). The picture is bounded only by self-review.

## High

1. **The picture is unchecked.** `film_eval` reads the SRT and SCRIPT.md, never the frames. This has already happened once: review round 1 found count-ups drawing "13" and "×2.5", which are not in FACTS (BUILD_LOG.md:98). `window.TEXTS` (film.js:407) is a hand-kept list that misses the plate source lines (film.js:429-441), the counts 1·5·43 (:323), the climb values (:180) and the loupe card (:126). **Fix:** send every `fillText` through `drawText(id, s)`, which logs to `window.__drawn`. Lint against raw `fillText`. Have `film_eval` run fidelity on the exported log. Add OCR on one frame per second (tesseract is not installed) or a vision worker.
2. **The "numbers heard" check is empty.** It reports 0/0 PASS (EVAL_REPORT_v1.md:35) because the narration spells numbers out (film_eval.py:1117-1124). WER is 1.86 % for the whole film, so "thirty-four" heard in place of "forty-three" would pass. **Fix:** take the numbers from the SRT, convert them to words, and require each one in the transcript. A line with a fact tag and zero numbers found is a FAIL.
3. **Jev's own category label can silence its flags.** Low scores count only on `[fact]` and `[interpretation]` lines (film_eval.py:1182). A wrong number that Jev labels `none` disappears. **Fix:** decide which lines are factual without Jev, from the fact tag or a number in the line.

## Medium

4. **Jev is asking the wrong question.** "Every claim fully supported" (:1143) cannot be answered for rhetoric, hence 0.32. For F19, the sheet says the slide *says* the line, not that it is *true*, so 0.19 is a defensible answer. **Fix:** ask two questions: "contains a checkable factual claim?", then "supported?" only if it does. Quotes go to exact match against FACTS.
5. **There is no calibration set:** 16 lines, no gold labels, and a hand-picked 0.8 threshold. **Fix:** a 40-line labelled set (verbatim lines, 49→48 mutations, misquotes, rhetoric), re-run on every `jev_model` change, with AUROC tracked.
6. **Noise hides the FAIL.** The overall result is FAIL, yet the film shipped (EVAL_REPORT_v1.md:3). The misses are table metadata (S02, 1920) and UI labels. **Fix:** remove structural rows and allowlist the labels, so that FAIL blocks the release.

## Low

7. **Drift.** The toolkit is tuned for Opus 5.5 (LEMO_TEARDOWN.md:151) and pulls upstream `main` on every run (:128). **Fix:** pin the SHA. Monthly, and on every model change, render this brief again and score it with `film_eval` plus a vision reviewer with a rubric. Plant three known-bad mutations to prove the harness still catches them.
8. **Mix.** LUFS, true peak and WER on the final mix cover voice burial and clipping. Adequate.

## Honest gaps

I didn't watch the mp4 or open the contact sheet, didn't read `jev_client` itself, didn't run `film_eval` again, and didn't check whether M0475 is really a London row.
