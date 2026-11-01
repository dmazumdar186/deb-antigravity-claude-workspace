# Film Eval: deterministic QA gate for short explainer films

## Purpose

Score a short AI-made explainer film before it reaches a client. The inputs are the MP4, the SRT, SCRIPT.md, FACTS.md and optionally the renderer's drawn-text log. The gate answers: does the film play everywhere, is it at the loudness target, and does every number a viewer hears or sees match the fact sheet? It also checks that quotations are exact, that there is no personal data, and that the captions are readable. Everything except ASR and Jev is deterministic: the same input gives the same verdict.

## When to invoke

- A film render has landed (e.g. `projects/<case>/film/`), before it is shared or marked final.
- After any re-render or script edit. Use `--compare old.json` for the per-metric delta and `--expect-sha256` to prove the re-render is byte-identical.
- When the Jev model id changes, or when the questions change (the prompt hash in the report differs from the calibration's): re-run `--calibrate`.

## Inputs

- `--video`, `--script` (SCRIPT.md) and `--facts` (FACTS.md table `| id | Fact | Value | Source |`) are required.
- `--srt` is optional. Without it, `number_fidelity_srt` and every caption metric are SKIPPED with the reason "no captions supplied"; burned-in or drawn text is still checked via `--drawn`. Do not pass an empty SRT for a caption-free film: a supplied SRT with no cues still FAILs `captions_parsed` (it usually means a broken export).
- `--profile default|linkedin_4x5` (default `default`). `linkedin_4x5` checks resolution against 1080x1350 at 4:5 instead of ≥ 1280x720, and adds `drawn_text_mobile` (needs `--drawn`).
- `--drawn drawn_text.json`: `[{text, t_start, t_end, x, y, px}, ...]`, one record per drawn string. Identical strings at the same place and size with touching time ranges are merged.
- `--asr`: faster-whisper, `--asr-model small.en` (the build's model), `--asr-lang en`. If the current interpreter lacks `faster_whisper`, it uses `--asr-python` (default: env `FILM_EVAL_ASR_PYTHON`, else the session venv path).
- `--jev`, `--jev-repeats 3`. Needs `OPENROUTER_API_KEY`. A 16-line film costs about $0.003.
- `--deny FILE`: names, one per line. These are added to `--deny-names` (CLI default `"Camille,Roux"`).
- `--hold 5`, `--max-mb 25`, `--expect-sha256 HEX`, `--compare old.json`, `--out report.json`, `--md report.md`.
- `--calibrate eval_data/jev_support_labels.csv --facts eval_data/calibration_facts.md`: calibration mode (see Steps).

### What is checked (rule 1: only what the viewer hears or sees)

SCRIPT.md is split into **sources**, and nothing outside them is checked: no title, metadata line, subtitles table or footnote.

1. **Sections** (preferred): `## Narration ...` and `## On-screen text ...`. A section is either a table or a list of lines. If it holds a table, prose around the table is commentary and is skipped.
   - In tables, structural columns are dropped: `# / cue / line / sub / row / in / out / time / duration / facts / burned in`. The narration text column is the one headed `spoken|vo|voice|narration`.
   - An unescaped `|` inside a cell is absorbed into the text column.
2. **Labelled lines**: `VO:` / `Narrator:` and `ON SCREEN:` / `SUPER:`.
3. **Narration-only fallbacks**: a table with a narration column, then blockquotes, then all prose. The report records the mode (`inputs.script.mode`).

A placeholder line, "(none)", "none", "—" (or "-", "–"), is dropped from every source. A narration section that holds only a placeholder, or nothing, means **no narration**: `number_fidelity_narration`, `speech_rate`, `asr_wer`, `asr_numbers_audible` and the Jev metrics are SKIPPED with the reason "no narration" (ASR is not run).

Number words in **narration** are converted to digits first: "forty-nine" → 49, "five hundred and twenty-five" → 525, "sixty-eight per cent" → 68 %. A lone "one" stays a word, because it is usually a determiner. On-screen text is checked as digits only, since words there describe the picture ("four empty slots"). SRT and drawn text are checked as displayed.

## Outputs

- **JSON report.** Each metric has `value`, `n` (the sample), `source` (file/section), `threshold`, `basis` (citation or "guess"), `verdict` (PASS/WARN/FAIL/SKIPPED), `detail` and `note`. The report also carries input sha256s, all thresholds and their sources, tool versions (including the Jev model id the API actually returned), a UTC timestamp, the ASR transcript, and the `compare` rows.
- **Markdown report.** The table shows value, n, source, threshold, basis and verdict. Below it come the findings, then "Info (not counted)" (record stubs, on-screen labels), skipped metrics with reasons, and the delta table.
- **Exit code**: 0 = PASS/WARN, 1 = any FAIL, 2 = usage error or missing input.
- **Calibration mode** writes `eval_data/jev_support_calibration.md` and `eval_data/jev_support_thresholds.json`, which the `--jev` run reads.

## Metrics, thresholds and sources

| Metric | PASS | WARN | FAIL | Source |
|---|---|---|---|---|
| file_size | ≤ 25 MB (10^6 B) | — | > 25 MB | Gmail attachment limit |
| resolution / fps / video_codec / audio_codec / bitrate | ≥1280x720 / 23.9–60 / h264+yuv420p / aac / ≤ 8000 kbps | otherwise | — | guess |
| resolution (`--profile linkedin_4x5`) | ≥ 1080x1350 at 4:5 (±1 %) | otherwise | — | guess (LinkedIn 4:5 feed video, 1080x1350) |
| audio_present | stream present | — | none | — |
| loudness_integrated (ebur128) | −16 ± 1 LUFS | — | outside | AES TD1004 (2015) / TD1008 (2021): −16 LUFS for streamed speech; ±1 LU tolerance per EBU R128; measured per ITU-R BS.1770 |
| true_peak | ≤ −1.0 dBTP | — | > −1.0 | EBU R128 / AES TD1008 |
| loudness_range | ≤ 15 LU | > 15 | — | guess |
| black_frames (first 1 s and final hold ignored) | < 0.5 s | < 2 s | ≥ 2 s | guess |
| frozen_frames / silence (outside final hold) | ≤ 4 s / ≤ 3 s | ≤ 10 s / ≤ 6 s | beyond | guess |
| number_fidelity_narration / _onscreen / _srt / _drawn | every number in FACTS | — | any unmatched (line listed) | FACTS.md is the source of truth |
| drawn_text_size | nothing < 28 px on screen ≥ 1 s | flagged | — | guess (28 px at 1080p) |
| drawn_text_mobile (`--profile linkedin_4x5`) | nothing on screen ≥ 1 s with px × (390/1080) < 11 pt (i.e. < 30.5 px) | flagged | — | guess (mobile-feed readability proxy: a 1080-px-wide frame shown on a 390-pt-wide phone) |
| tag_coverage | 100 % of numeric lines tagged | ≥ 80 % | < 80 % | guess |
| tag_validity | all ids exist | — | unknown id | — |
| tag_consistency | numbers belong to the tagged facts | mismatch | — | — |
| quote_fidelity | exact | case-only difference; altered label; unrelated quotation in narration/SRT | quotation ≥ 60 % similar but altered | exact match; 0.6 cut = guess |
| pii_scan (SRT, whole SCRIPT, drawn, ASR) | none | — | e-mail, phone (9–15 digits) or denied name, masked | FACTS hard rules |
| speech_rate (count_words / caption-covered time) | 130–170 wpm | ± 15 | beyond | guess, bounded by BBC Subtitle Guidelines (160–180 wpm subtitle rate) |
| caption_cps | ≤ 17 | ≤ 21 | > 21 | Netflix English Timed Text Style Guide: 17 cps is the **children's** limit, 20 the adult limit; FAIL 21 = guess |
| caption_duration | 1–7 s | outside | — | Netflix TTSG max 7 s; min 1.0 s = guess (Netflix min 5/6 s) |
| caption_line_length / lines_per_cue | ≤ 42 chars / ≤ 2 lines | > 42 | > 2 lines | Netflix TTSG |
| caption_timing | no overlap; gaps 0 or ≥ 2 frames at the video fps | sub-2-frame gap; cue past the end | overlap, end ≤ start | Netflix TTSG timing (2-frame gap) |
| asr_wer (`--asr`) | ≤ 5 % | ≤ 10 % | > 10 % | guess |
| asr_numbers_audible | every SRT number heard (transcript words → digits) | — | any missing | — ; **0 checked = SKIPPED**, never PASS |
| jev_entailment / jev_contradiction (`--jev`) | no flagged claim line | flagged while that question's AUROC < 0.9 (advisory) | flagged while AUROC ≥ 0.9 | `eval_data/jev_support_calibration.md` |

Matching rules:

- **Numbers.** `68%` = `68 %` = `68 percent`. Thousands separators `,`, NBSP and narrow NBSP are accepted; a plain space is not. Kinds must agree, so `68` ≠ `68 %`. Ranges match an equal range or two matched endpoints.
- **Record ids.** An id is checked only if its letter prefix occurs in a FACTS id (R2), so `S02` and `L01` are structure. A single id with a FACTS prefix that falls outside every FACTS range (e.g. card `M0475`) is an anonymous record stub, reported as INFO. The FACTS hard rules allow stubs.
- **Number words in FACTS** count too (R7), so "3 yrs" matches F22 "Three years". A date matches if it is written anywhere in FACTS.md, e.g. the reference date.
- **Structural numbers** are stripped from SCRIPT text (R3): timecodes, scene/cue numbers, units (`s`, `fps`, `bpm`, `px`…), `speed 0.9`, `crf 26`, resolutions `1920×1080`.
- **Quotes** (R4–R6):
  - Quotes are extracted per table cell, with smart pairs matched before straight ones.
  - ` / ` counts as a line break. A sentence-initial capital is ignored.
  - A quote counts as a **quotation** in narration and subtitles, on lines with an attribution cue (verbatim, said, put it), and on lines tagged with a fact that contains a quote. Anything else is a **label**: its numbers are checked, its wording is INFO.

## Jev (two-step, repeated, calibrated)

- **State:** `{facts: <fact sheet>, line: <narration line>}`.
- **Step 1, every line:** `claim` (does the line make a factual claim?) and `contradiction` (does it contradict facts?).
- **Step 2, claim lines only:** `entailed`, worded as entailment ("is every claim *stated in* facts?"), not truth.
- **Claim lines** are those where Jev's claim mean ≥ the calibrated threshold, **or** where the line has a fact tag or a number. Jev cannot silence a factual line.
- Each step runs `--jev-repeats` times (default 3). The report gives the mean, the per-line range and the mean/max spread.
- **Recorded:** the model id returned by the API (e.g. `typesafe/jev-1.13-20260917`), the prompt hash and the cost.
- **Staleness:** a prompt-hash or model mismatch against the calibration is flagged as "CALIBRATION STALE".

Calibration (2026-11-01, `typesafe/jev-1.13-20260917`, N=3, 67 hand-labelled lines against the case FACTS):

| Question | AUROC | Threshold |
|---|---|---|
| claim | 1.000 | 0.368 |
| entailed | 0.990 | 0.705 |
| contradiction | 1.000 | 0.288 |

The one entailment miss is H02, "Six can be e-mailed today". F12 says "worth contacting", not "can be e-mailed", and Jev scores the line 0.93. Treat F12-style wording nuance as a known blind spot. The set is easy, with wide margins, so add hard items when new failure modes appear.

## Steps

1. Confirm the inputs exist (the script exits 2 if one is missing).
2. Run `python3 execution/video/film_eval.py --video ... --srt ... --script ... --facts ... [--drawn src/out/drawn_text.json] --asr --jev --out .tmp/film_eval/<slug>.json --md .tmp/film_eval/<slug>.md`. Add `--compare <previous>.json` after a re-render.
3. Read `OVERALL`. FAIL: fix the film, script or FACTS per the findings, re-render, re-run.
4. WARN: read each WARN and accept or fix it. Never move a threshold to turn a WARN green.
5. If the Jev note says CALIBRATION STALE, re-run calibration: `python3 execution/video/film_eval.py --calibrate execution/video/eval_data/jev_support_labels.csv --facts execution/video/eval_data/calibration_facts.md`. Add labelled lines for any new failure mode first.
6. Record the video sha256 from the report, so re-renders can use `--expect-sha256`.

## Exit Criteria (declarative)

- `report.json` exists, `overall` ∈ {PASS, WARN, FAIL}, and every metric has `n`, `source`, `threshold`, `basis` and `verdict`.
- No metric reports PASS on an empty sample where emptiness means "nothing was tested". `asr_numbers_audible` with 0 checked is SKIPPED, with the reason in its `note`.
- Number fidelity covers only narration, on-screen text, SRT and drawn text. The golden test (`eval_data/golden_v1/`) has zero FAILs, and planted mutations (49→48, 43→34) FAIL.
- Jev metrics use `eval_data/jev_support_thresholds.json`, and the recorded model id matches the calibration's.
- The exit code agrees with `overall` (1 iff FAIL).

## Scripts (Layer 3)

- `execution/video/film_eval.py` (evaluate, `--compare`, `--calibrate`)
- `execution/video/eval_data/`:
  - `jev_support_labels.csv` (67 labelled lines)
  - `calibration_facts.md` (frozen case FACTS used as state)
  - `jev_support_thresholds.json`
  - `jev_support_calibration.md`
  - `golden_v1/` (v1 SCRIPT/SRT/FACTS for the regression test)
- Tests: `tests/test_film_eval.py` (`python3 -m unittest tests.test_film_eval`)
- Jev client: `execution/modules/jev_client.py` (ledger `caller: film_eval`). `modules/jev_eval.py` was not reused: it scores accuracy and confidence, not AUROC on a probability.

## Edge cases

- **Sine-tone or music-only fixtures** make Whisper hallucinate, so WER ≫ 100 %. Test WER on a film with speech.
- **No audio stream:** loudness, silence and ASR are SKIPPED; `audio_present` FAILs.
- **Silent, caption-free film** (music only, on-screen type, e.g. LinkedIn 4:5 posts): omit `--srt`, write "(none)" under `## Narration`, pass `--drawn` and `--profile linkedin_4x5`. Caption and narration metrics are SKIPPED with their reasons, not FAILed. First seen on `deliverables/linkedin_posts/prodcraft_wk02_reply_triage/` (v1 report: two false FAILs, `captions_parsed` and `speech_rate` 2.6 wpm from "(none)" counted as a word).
- **Label/value time conflicts in drawn text are not checked.** `drawn_text.json` has no label↔value link, and a spatial heuristic would bring back false positives. If the renderer adds a `group` id per label/value pair, add the check then.
- **Prose fallback:** if SCRIPT.md has neither sections nor labels, the `all_prose` fallback includes non-spoken prose. Check `inputs.script.mode`.
- **Phone numbers in a script line** also show up as unmatched numbers. Both FAILs are intended.
- **Jev rate limit:** the client retries a 429 once after ≤ 5 s, then fails open, and the metric is SKIPPED with the reason. N=3 × 2 steps × 16 lines is about 96 calls.

## Changelog

- 2026-11-01: v1.0.0 created on a synthetic ffmpeg fixture.
- 2026-11-01: v2.0.0 after the panel review of the v1 film (EVAL_REPORT_v1.md, lenses 1/2/4/8):
  - Cherny rules R1–R7 applied; number fidelity now covers sources only (narration / on-screen / SRT / drawn).
  - New `--drawn` check.
  - Spoken numbers converted to digits; audibility checked against SRT numbers, with 0 checked = SKIPPED.
  - Jev rebuilt as two steps (claim → entailment, plus contradiction), N=3, calibrated on 67 labelled lines (entailment AUROC 0.990, threshold 0.705); the model id comes from the API response.
  - Single loudness target −16 ± 1 LUFS / ≤ −1 dBTP; every threshold now carries a source or "guess".
  - `n` and `source` added per metric; `--compare`; one tokenizer (`count_words`); speech rate over caption-covered time; caption gap measured in frames at the video fps; ASR default `small.en`; ASR interpreter taken from env, not hard-coded.
  - On the v1 film, the 18 number and 20 quote false positives are gone. The FAIL that remains is loudness (−14 LUFS against the −16 ± 1 target).
- 2026-11-01: v2.1.0 after the prodcraft wk02 silent LinkedIn film: `--srt` optional ("no captions supplied" SKIPs); placeholder narration ("(none)", "none", "—", empty) = no narration (narration fidelity, speech rate, ASR, Jev SKIPPED, "no narration"); `--profile linkedin_4x5` (1080x1350 resolution PASS, `drawn_text_mobile` WARN under 11 pt, source "guess").
