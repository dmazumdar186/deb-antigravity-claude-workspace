# Lens 8 — Sutskever: capability and failure modes

**Verdict: NOT CLEAR.** The film itself looks factually clean. The bounds around it don't hold: the picture has no bound at all, and the one bound on spoken numbers checks nothing.

Where the model sits in the loop: script, `film.js` (every pixel), on-screen labels, score code and `mix.py`. The audio steps are bounded (LUFS, true peak, WER on the final mix, BUILD_LOG.md:12-15). The picture is bounded only by the model reviewing its own contact sheets.

## High

1. **The picture is unchecked.** `film_eval` checks numbers in the SRT and in SCRIPT.md, never in frames. Evidence that this is a real risk: review round 1 found count-ups drawing "13" and "×2.5", numbers that are not in FACTS (BUILD_LOG.md:98). Only a self-review caught them. `window.TEXTS` (film.js:407) is a parallel list, not a record of what was drawn. It leaves out the plate source lines ("for 500 members announced", "of 500 members · ref. 2026-10-12", "IDs M0501 – M0525"; film.js:429-441), the counts 1·5·43 (film.js:323), the climb values (`climbV`, film.js:180) and the loupe card text (film.js:126-127). **Fix:** route every `fillText` through `drawText(id, s)`, which logs to `window.__drawn`, and add a lint that rejects any raw `fillText`. Export the log for every frame and have `film_eval` run number and quote fidelity on it. Then OCR one frame per second to catch pixels that the log misses (tesseract and pytesseract are not installed; install them or use a vision worker).
2. **The "numbers heard" check is empty.** `asr_fact_numbers_audible` reports 0/0 and PASS (EVAL_REPORT_v1.md:35). The narration spells numbers out, so `extract_numbers` finds none (film_eval.py:1117-1124). WER over the whole film is 1.86 %, so "forty-three" heard as "thirty-four" would still pass. **Fix:** pull numbers from the SRT or the fact tags, convert them to words, and require each one to appear in the transcript. Treat `total == 0` on a line that carries a fact tag as FAIL.
3. **Jev's own category label can silence its flags.** Low "supported" scores count only on `[fact]` and `[interpretation]` lines (film_eval.py:1182). If Jev labels a wrong-number line `none`, the flag disappears. **Fix:** decide which lines are factual without Jev (fact tag or a number present), not from `claim_type`.

## Medium

4. **Jev is asking the wrong question.** "Is every claim fully supported" (film_eval.py:1143) has no good answer for rhetoric, which explains "One sentence. Four answers." scoring 0.32. It also mixes up two things for F19: the sheet says the slide *says* that line, not that the line is *true*, so 0.19 is a defensible answer. **Fix:** ask in two steps. First, "does the line contain a checkable factual claim?". Only if yes, "is it supported?". Quotes and product lines go to exact match against FACTS, not to Jev.
5. **No calibration set.** Sixteen lines, no gold labels, and a 0.8 threshold chosen by hand. **Fix:** build a 40-line labelled set: verbatim lines, mutated numbers (49→48), near-miss misquotes, rhetoric and product claims. Re-run it whenever `jev_model` changes (currently pinned to `typesafe/jev-1.13-20260917`) and track AUROC.
6. **Too much noise hides real failures.** The run shows FAIL overall, yet the film shipped (EVAL_REPORT_v1.md:3). The 18 number misses are table metadata (S02, 1920). The 20 "quote not in FACTS" hits are UI labels. **Fix:** remove structural rows before checking and allowlist the labels, so that FAIL actually stops a release.

## Low

7. **Model drift and upstream drift.** The toolkit is tuned for Opus 5.5 (LEMO_TEARDOWN.md:151), and `setup.sh` pulls upstream `main` on every run (LEMO_TEARDOWN.md:128). Either one can change the output without anyone noticing. **Fix:** pin the toolkit SHA. Then once a month, and on every model change, render this brief again and score it with `film_eval` plus a vision reviewer with a rubric (drawn numbers, overlaps, maps or logos, typos). Plant three known-bad mutations each time to prove the harness still catches them.
8. **Mix.** The model writes `mix.py`, but LUFS, true peak and WER on the final mix cover the plausible failures (voice buried, clipping). Adequate.

## Honest gaps

I didn't watch the mp4 or open `contact_sheet.jpg`, so I can't say whether a drawn number is wrong. I read `jev_client` only through its call sites. I didn't run `film_eval` again. I didn't check whether card M0475 is really a London row (SCRIPT.md:81 says cities are schematic).
