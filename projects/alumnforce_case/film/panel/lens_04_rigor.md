# Lens 4: Rigor (Anthropic research team)

**Verdict: NOT CLEAR.** All 15 on-screen numbers match FACTS.md. The gaps are in definitions, provenance and how the eval is reported.

## High

1. **The model that wrote the film is not recorded.** BUILD_LOG.md:21-29 pins the toolkit (bebbbe1), Node, ffmpeg, kokoro-onnx 0.6.1 and faster-whisper 1.2.1. It never names the model, CLI version or brief that wrote `film.js`/`mix.py`/`timeline.js`. LEMO_TEARDOWN.md:28 says the same brief gives a different film, and :151 says the toolkit is "tuned for Opus 5.5". *Fix:* add the model id, CLI version and sha256 of the brief to Versions. Say that only `src/` reproduces the film; the brief does not.
2. **`asr_fact_numbers_audible` passes with no evidence.** EVAL_REPORT_v1.md:35 shows "0/0 PASS": the narration spells numbers as words, so the check found nothing to test. *Fix:* return SKIPPED when n = 0, or map number words to digits as the WER check does (film_eval.md:67).
3. **Jev nondeterminism is not recorded.** One run gave 0.794 against a 0.8 threshold (EVAL_REPORT_v1.md:36), a margin of 0.006. No repeat run, seed or temperature is recorded (jev_client.py has none), and the client pins the alias `typesafe/jev-1.13` (jev_client.py:28). Only the response gives the snapshot `-20260917`. *Fix:* run it 3 times and report mean ± range, record the prompt hash, and pin the dated snapshot.
4. **The overall FAIL is not adjudicated.** Almost all of the FAIL comes from harness false positives: cue ids `S02`, `1920×1080`, UI labels read as "quotes" (EVAL_REPORT_v1.md:46-95). The report never separates these from film defects. *Fix:* add a disposition table. The panel should not be shown a FAIL that nobody has explained.

## Medium

5. **The 68 % cannot be traced to a query.** F13 cites README:24. VERIFICATION.md has no check for it and annexB.sql does not compute it. "Touched" is ambiguous (profile update or login?), and it is not stated whether null dates count as untouched. *Fix:* commit the query and say "profile not updated" on screen.
6. **The duplicate wording is wrong against the result file.** The plate says "Duplicate persons / IDs M0501–M0525" (SCRIPT.md:63) and the deck says "apparent". But the SQL keeps the newer record (annexB.sql:114), and **M0502 is the one "current" member of the 49** (annexB_result.csv:2). *Fix:* "25 people have two records; the newer is kept".
7. **Other definitions are simplified.** "Two members" counts rows, not members, and leaves out "with tenure" (F07). "Normalise the spellings: 26" also merges 3 sector labels, which are not spellings, and has no dedup (F08). "More than three years" is `<=` in the SQL, i.e. ≥ 3 years in the current job, a proxy (annexB.sql:174). "Six can be emailed today" ignores opt-out right after the "Two unsubscribed" quote. *Fix:* say "2 rows" and "spellings and labels", and say in the talk that tenure is a proxy.
8. **Thresholds are uncited, and the loudness targets disagree.** The harness uses −16 ± 2 (film_eval.py:61). The teardown gate is [−15, −13] (LEMO_TEARDOWN.md:190). DIRECTOR asks for −14. The film is exactly −14.0, on the PASS edge. Sources: −16 is AES TD1004 (streaming), −14 is YouTube/Spotify normalisation, and −1 dBTP is EBU R128/AES. For captions, 42 chars, a 2-frame gap and ≤ 7 s are Netflix English rules. 17 cps is Netflix's *children's* limit (adults: 20), so cue 2 at 19.5 cps passes for adult content. 130–170 wpm, WER 5 %, Jev 0.8/0.5 and the freeze/silence limits are guesses. Speech rate counts the 5 s hold and the pauses. *Fix:* add a source column to film_eval.md:36 that says "guess" where there is no source.

## Low

9. **The eval and the build used different ASR models.** The eval used `small`, the build used `small.en` (EVAL_REPORT_v1.md:141, BUILD_LOG.md:27). Neither has a Hugging Face revision pin (LEMO_TEARDOWN.md:93).
10. **Four word counts for one narration.** 155 (TTS), 159 (final_asr), 156 (eval), 161 (WER reference). The tokeniser is not defined.
11. **The hash and the voice speed are unclear.** The report shows a 16-hex sha256 prefix and no JSON is committed. "0.86 → 0.9 for the last line" (BUILD_LOG.md:19) is unclear. pip has no lock file.

## Honest gaps

- I had no CSV, so I could not check whether card M0475 really reads "Londres (Royaume-Uni)". If it does not, the panel can see a real member ID shown with a city it does not have.
- I did not re-run the eval, ASR or Jev. I did not watch the film or check its frames.
- I did not check whether an opt-out field exists in the 15 columns.
