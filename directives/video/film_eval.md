# Film Eval — deterministic QA gate for short explainer films

## Purpose

Score a short AI-made explainer film (MP4 + SRT + SCRIPT.md + FACTS.md) before it reaches a client:
does it play everywhere, is it loud enough and clean, does every on-screen and narrated number and
quote match the fact sheet, is there no personal data, and can a viewer read the captions. Most
checks are deterministic (ffprobe/ffmpeg and regex), so the same input gives the same verdict. ASR
and Jev are optional extras.

## When to invoke

- A film render has landed (e.g. `projects/<case>/film/`) and before it is shared or committed as final.
- After any re-render or script edit (`--expect-sha256` confirms a re-render is byte-identical).
- When a worker reports a film "done": run this instead of eyeballing it.

## Inputs

- `--video`: MP4. `--srt`: captions. `--script`: SCRIPT.md. `--facts`: FACTS.md table `| id | Fact | Value | Source |`. All required.
- `--asr`: faster-whisper WER (model `--asr-model small`, `--asr-lang en`). Tries the current interpreter, then `--asr-python` (default `/tmp/ext/venv/bin/python`). SKIPPED if neither imports `faster_whisper` or the film has no audio.
- `--jev`: one `jev_client.decide_many` batch over the narration lines. Needs `OPENROUTER_API_KEY`. Costs about $0.0002 for 7 lines. Fails open (SKIPPED).
- `--deny FILE`: names, one per line. These are added to `--deny-names`, whose CLI default is `"Camille,Roux"`.
- `--hold 5`, `--max-mb 25`, `--lufs-target -16`, `--expect-sha256 HEX`.
- `--out report.json`, `--md report.md`.

SCRIPT.md is read leniently. Narration is taken from the first source found: `VO:` / `Narration:` / `**Narrator:**` labelled lines (continuation lines included), then a table column named VO/voice/narration, then prose under a "Narration"/"Voice-over"/"Script" heading, then blockquotes, then all prose lines. The report records which mode was used (`inputs.script.narration_mode`). Fact tags can be `[F07]`, `(F07, F08)`, `F07–F09` or a bare `F7`. Structural numbers are ignored for number checks: timecodes, `Scene 3`, durations and units (`6 s`, `30 fps`, `1080p`), dates, inline code, hex colours, list markers, and table columns named `#`/time/duration/facts.

## Outputs

- JSON report: every metric with `value`, `threshold`, `verdict` (PASS/WARN/FAIL/SKIPPED), `detail` lines and `note`, plus the input sha256s, thresholds, tool versions, a UTC run timestamp and the ASR transcript when there is one.
- Markdown report: a summary table, the overall verdict, findings (for FAIL/WARN), skipped metrics with reasons, and tool versions.
- stdout: one line per metric plus `OVERALL`. Exit 0 = PASS/WARN, 1 = any FAIL, 2 = usage error or missing input.

## Metrics and thresholds

| Group | Metric | PASS | WARN | FAIL |
|---|---|---|---|---|
| technical | file_size | ≤ 25 MB (10^6 B) | — | > 25 MB |
| technical | duration | > 0 and ≥ last cue end | cue past end | 0 |
| technical | resolution / fps / video_codec / audio_codec / bitrate | ≥1280x720 / 23.9–60 / h264+yuv420p / aac / ≤ 8000 kbps | otherwise | — |
| technical | audio_present | audio stream | — | none |
| technical | loudness_integrated (ebur128) | −16 ± 2 LUFS | ± 4 | beyond |
| technical | true_peak | ≤ −1 dBTP | ≤ 0 | > 0 |
| technical | loudness_range | ≤ 15 LU | > 15 | — |
| technical | black_frames (first 1 s and final hold ignored) | < 0.5 s | < 2 s | ≥ 2 s |
| technical | frozen_frames (outside final hold) | ≤ 4 s | ≤ 10 s | > 10 s |
| technical | silence (−50 dB, outside final hold) | ≤ 3 s | ≤ 6 s | > 6 s |
| technical | encode_determinism (only with `--expect-sha256`) | equal | — | differs |
| content | number_fidelity_srt / _script | every number in FACTS (Fact or Value column) | — | any unmatched, line listed |
| content | tag_coverage | 100 % of numeric lines carry a valid id | ≥ 80 % | < 80 % |
| content | tag_validity | all ids exist | — | unknown id |
| content | tag_consistency | numbers belong to the line's tagged facts | mismatch | — |
| content | quote_fidelity | exact (smart/straight quotes ignored; exact substrings ≥ 12 chars allowed) | case-only difference, or quote not in FACTS | ≥ 60 % similar but altered |
| content | pii_scan (SRT, SCRIPT, ASR transcript) | none | — | e-mail, phone (9–15 digits) or denied name; matches masked |
| content | speech_rate (narration words / video duration) | 130–170 wpm | ± 15 | beyond |
| captions | caption_cps (characters incl. spaces, excl. line breaks) | ≤ 17 | ≤ 21 | > 21 |
| captions | caption_duration | 1–7 s | outside | — |
| captions | caption_line_length | ≤ 42 | > 42 | — |
| captions | caption_lines_per_cue | ≤ 2 | — | > 2 |
| captions | caption_timing | no overlap; gaps 0 or ≥ 0.083 s | flicker gap, cue past video end | overlap, end ≤ start |
| ai | asr_wer (`--asr`) | ≤ 5 % | ≤ 10 % | > 10 % |
| ai | asr_fact_numbers_audible | all narrated numbers heard | some missing | — |
| ai | jev_supported / jev_clarity / jev_claim_types (`--jev`) | mean ≥ 0.8, no fact/interpretation line < 0.5 | otherwise (advisory, never FAIL) | — |

Number matching rules: `68%` = `68 %` = `68 percent`. Thousands separators `,`, NBSP and narrow NBSP are tolerated; a plain space is not. Kinds must agree (`68` does not match `68 %`). A range matches the same range or two matched endpoints. A record id (`M0502`) matches a fact id-range (`M0501–M0525`). Numbers spelled as words are not checked here; ASR covers them.

WER normalisation maps digits and number words to one spoken form, so `49`, `forty-nine` and `forty nine` are equal, and so are `112` and `one hundred and twelve`. `%` becomes "percent", and dashes between numbers become "to". Case, punctuation and quote style are ignored.

## Steps

1. Confirm the four inputs exist (the script exits 2 if any is missing).
2. Run `python3 execution/video/film_eval.py --video ... --srt ... --script ... --facts ... --out <dir>/film_eval.json --md <dir>/film_eval.md`. Add `--asr` and/or `--jev` for the AI metrics.
3. Read `OVERALL`. FAIL: fix the film or script per the Findings section, re-render, then re-run.
4. WARN: read each WARN and accept it or fix it. Never change a threshold to turn a WARN green.
5. Record the video sha256 from the report. Re-renders can then be checked with `--expect-sha256`.

## Exit Criteria (declarative)

- `report.json` exists and has `overall` ∈ {PASS, WARN, FAIL} and one entry per metric above (minus the optional ones not requested).
- Every metric has a non-empty `threshold` and a `verdict`. SKIPPED metrics carry a `note` with the reason; values are never invented.
- The process exit code agrees with `overall` (1 iff FAIL).
- A film ships only when `overall` is PASS, or WARN with each WARN read and accepted.

## Scripts (Layer 3)

- `execution/video/film_eval.py`
- Tests: `tests/test_film_eval.py` (`python3 -m unittest tests.test_film_eval`)
- Jev client: `execution/modules/jev_client.py` (ledger row `caller: film_eval`)

## Edge cases

- A sine-tone or music-only fixture makes Whisper hallucinate ("a little bit of a little bit..."), so WER ≫ 100 %. That is a real result, not a bug. Test WER on a film that has speech.
- No audio stream: loudness, silence and ASR are SKIPPED, and audio_present FAILs.
- If SCRIPT.md has no recognisable narration, it falls back to `all_prose`. Speech rate and WER then also count on-screen text, so check `narration_mode`.
- Phone numbers inside a script line also appear as unmatched numbers in number fidelity. Both FAILs are intended.
- The faster-whisper model downloads on first use. With no network, ASR is SKIPPED with the reason.

## Changelog

- 2026-11-01: Created (v1.0.0). Built and tested on a synthetic ffmpeg fixture (testsrc2 + sine tone) in `/tmp/film_eval_fixture/`; first real target `projects/alumnforce_case/film/trusted-segments.mp4`.
