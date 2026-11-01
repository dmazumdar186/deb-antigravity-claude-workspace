# Film evaluation: trusted-segments.mp4

**Overall: WARN** · film_eval 2.0.0 · run 2026-11-01T12:06:57Z · sha256 `ab1346e249bb09404c8b9d7526d9114196ac9c1686fa78b5ef9898b399313ec9`

| Group | Metric | Value | n | Source | Threshold | Basis | Verdict |
|---|---|---|---|---|---|---|---|
| technical | file_size | 19.5 MB | 1 | trusted-segments.mp4 | <= 25.0 MB | Gmail attachment limit (25 MB) | **PASS** |
| technical | duration | 61.375 s | 1 | trusted-segments.mp4 | >= last caption end | consistency check | **PASS** |
| technical | resolution | 1920x1080 | 1 | trusted-segments.mp4 | >= 1280x720 | guess (web-delivery convention) | **PASS** |
| technical | fps | 24 | 1 | trusted-segments.mp4 | 23.9-60.0 | guess | **PASS** |
| technical | video_codec | h264/yuv420p | 1 | trusted-segments.mp4 | h264/yuv420p | guess (h264/yuv420p plays everywhere) | **PASS** |
| technical | audio_present | True | 1 | trusted-segments.mp4 | audio stream present | guess | **PASS** |
| technical | audio_codec | aac 48000 Hz 2ch | 1 | trusted-segments.mp4 | aac | guess | **PASS** |
| technical | bitrate | 2541 kbps | 1 | trusted-segments.mp4 | <= 8000 kbps | guess | **PASS** |
| technical | loudness_integrated | -16 LUFS | 1 | trusted-segments.mp4 | -16.0 +/-1.0 LUFS | AES TD1004/TD1008 (-16 LUFS for streamed speech); measured per ITU-R BS.1770 / EBU R128; +/-1 LU tolerance per EBU R128 | **PASS** |
| technical | true_peak | -1.7 dBTP | 1 | trusted-segments.mp4 | <= -1.0 dBTP | EBU R128 / AES TD1008 (max -1 dBTP) | **PASS** |
| technical | loudness_range | 3 LU | 1 | trusted-segments.mp4 | <= 15.0 LU | guess | **PASS** |
| technical | black_frames | 0 s | 0 | trusted-segments.mp4 | longest black < 0.5s (FAIL >= 2.0s); first 1.0s, final 5.0s ignored | guess | **PASS** |
| technical | frozen_frames | 0 s | 1 | trusted-segments.mp4 | longest freeze <= 4.0s outside final 5.0s (FAIL > 10.0s) | guess | **PASS** |
| technical | silence | 0 s | 0 | trusted-segments.mp4 | longest silence <= 3.0s outside final 5.0s (FAIL > 6.0s) | guess | **PASS** |
| content | number_fidelity_narration | 20/20 matched | 20 | SCRIPT.md narration (sections) | every number matches a FACTS value | - | **PASS** |
| content | number_fidelity_onscreen | 30/30 matched | 30 | SCRIPT.md on-screen text | every number matches a FACTS value | - | **PASS** |
| content | number_fidelity_srt | 15/15 matched | 15 | trusted-segments_clean.captions.srt | every number matches a FACTS value | - | **PASS** |
| content | number_fidelity_drawn | 42/42 matched | 42 | drawn_text.json | every number matches a FACTS value | - | **PASS** |
| content | drawn_text_size | 28 px | 185 | drawn_text.json | no text < 28 px on screen >= 1 s | guess (28 px at 1080p, >= 1 s on screen) | **PASS** |
| content | tag_coverage | 25/26 (96%) | 26 | SCRIPT.md (narration + on-screen) | 100% of numeric lines tagged (WARN >= 80%) | guess | **WARN** |
| content | tag_validity | 0 unknown ids | 46 | SCRIPT.md (narration + on-screen) | every tagged id exists in FACTS | guess | **PASS** |
| content | tag_consistency | 1 mismatches | 26 | SCRIPT.md (narration + on-screen) | each number on a tagged line belongs to one of its tagged facts | guess | **WARN** |
| content | quote_fidelity | 14/40 exact | 40 | SCRIPT.md + trusted-segments_clean.captions.srt + drawn | quotations match FACTS exactly (smart/straight quotes and line breaks ignored) | exact match; 0.6 similarity cut = guess | **WARN** |
| content | speech_rate | 148.7 wpm | 133 | SCRIPT.md narration + SRT timing | 130-170 wpm (WARN +/-15) | guess, bounded by BBC Subtitle Guidelines (160-180 wpm subtitle rate) | **PASS** |
| content | pii_scan | 0 hits | 288 | trusted-segments_clean.captions.srt + SCRIPT.md + drawn + ASR | no e-mail, phone or denied name (Camille, Roux) | FACTS hard rules (no member data) | **PASS** |
| captions | caption_cps | 16.9 cps | 18 | trusted-segments_clean.captions.srt | max CPS <= 17 (FAIL > 21) | Netflix English Timed Text Style Guide: 17 cps = children's limit (adult 20), used as WARN; FAIL 21 = guess | **PASS** |
| captions | caption_duration | 1.42-5.06 s | 18 | trusted-segments_clean.captions.srt | 1.0-7.0 s per cue | Netflix TTSG: max 7 s; min 1.0 s = guess (Netflix minimum is 5/6 s) | **PASS** |
| captions | caption_line_length | 42 chars | 25 | trusted-segments_clean.captions.srt | <= 42 chars per line | Netflix TTSG: 42 characters per line | **PASS** |
| captions | caption_lines_per_cue | 2 lines | 18 | trusted-segments_clean.captions.srt | <= 2 | Netflix TTSG: max 2 lines | **PASS** |
| captions | caption_timing | 0 overlaps, 0 sub-2-frame gaps | 17 | trusted-segments_clean.captions.srt | no overlaps; gaps 0 or >= 2 frames; cues inside the video | Netflix TTSG timing guidelines: 2-frame minimum gap between events | **PASS** |
| ai | asr_wer | 0.72 % | 138 | trusted-segments.mp4 vs SCRIPT narration | <= 5% (WARN <= 10%) | guess | **PASS** |
| ai | asr_numbers_audible | 15/15 | 15 | trusted-segments_clean.captions.srt vs ASR transcript | every subtitle number heard in the transcript | guess | **PASS** |
| ai | jev_entailment | 0.896 | 14 | SCRIPT.md narration | entailment mean >= 0.705 per claim line (calibrated, AUROC 0.99); FAIL when flagged | calibrated on eval_data/jev_support_labels.csv (see jev_support_calibration.md) | **PASS** |
| ai | jev_contradiction | 0 flagged | 15 | SCRIPT.md narration | no line >= 0.288 (calibrated, AUROC 1.00); FAIL when flagged | calibrated on eval_data/jev_support_labels.csv (see jev_support_calibration.md) | **PASS** |
| ai | jev_claims | 14/15 claim lines | 15 | SCRIPT.md narration | claim noul >= 0.3683 or fact tag/number | calibrated on eval_data/jev_support_labels.csv (see jev_support_calibration.md) | **PASS** |

## Findings

### WARN · tag_coverage
- SCRIPT.md:82 [onscreen]: no fact id -> End card: "Trusted Segments" / Made in code by an AI agent with lemo-opuscar (MIT) / Synthetic voice

### WARN · tag_consistency
- SCRIPT.md:73 [onscreen]: '500' is in F02, line tagged F13

### WARN · quote_fidelity
- SCRIPT.md:63: altered quote of F02 (72% similar): "for 500 members" vs "525 rows, 500 members"

## Info (not counted)
- quote_fidelity: SCRIPT.md:62: label "Schematic · no member data" (wording not checked; numbers are)
- quote_fidelity: SCRIPT.md:63: label "Rows in the file" (wording not checked; numbers are)
- quote_fidelity: SCRIPT.md:64: label "M0271" (wording not checked; numbers are)
- quote_fidelity: SCRIPT.md:65: label "London, as typed in the file" (wording not checked; numbers are)
- quote_fidelity: SCRIPT.md:65: label "8 spellings" (wording not checked; numbers are)
- quote_fidelity: SCRIPT.md:66: label "Naive filter · file as delivered" (wording not checked; numbers are)
- quote_fidelity: SCRIPT.md:67: label "Naive filter · file as delivered" (wording not checked; numbers are)
- quote_fidelity: SCRIPT.md:67: label "rows matching the sentence" (wording not checked; numbers are)
- quote_fidelity: SCRIPT.md:68: label "Normalised · spellings and labels" (wording not checked; numbers are)
- quote_fidelity: SCRIPT.md:68: label "rows matching the sentence" (wording not checked; numbers are)
- quote_fidelity: SCRIPT.md:70: label "Full logic · dedup + employer + job title" (wording not checked; numbers are)
- quote_fidelity: SCRIPT.md:70: label "members matching the sentence" (wording not checked; numbers are)
- quote_fidelity: SCRIPT.md:71: label "example" (wording not checked; numbers are)
- quote_fidelity: SCRIPT.md:71: label "in post: 3 yrs" (wording not checked; numbers are)
- quote_fidelity: SCRIPT.md:71: label "updated: 3 yrs ago" (wording not checked; numbers are)
- quote_fidelity: SCRIPT.md:73: label "Profiles untouched for 2+ years" (wording not checked; numbers are)
- quote_fidelity: SCRIPT.md:73: label "of 500 members · ref. 2026-10-12" (wording not checked; numbers are)
- quote_fidelity: SCRIPT.md:74: label "read as tenure" (wording not checked; numbers are)
- quote_fidelity: SCRIPT.md:74: label "read as freshness" (wording not checked; numbers are)
- quote_fidelity: SCRIPT.md:74: label "same" (wording not checked; numbers are)
- quote_fidelity: SCRIPT.md:75: label "user verbatim" (wording not checked; numbers are)
- quote_fidelity: SCRIPT.md:76: label "Current → send" (wording not checked; numbers are)
- quote_fidelity: SCRIPT.md:76: label "To confirm → confirm" (wording not checked; numbers are)
- quote_fidelity: SCRIPT.md:76: label "To reactivate → reactivate" (wording not checked; numbers are)
- quote_fidelity: SCRIPT.md:77: label "worth contacting today:" (wording not checked; numbers are)
- jev_claims: SCRIPT.md:17: Jev said no claim; checked anyway (tag/number)
- jev_claims: SCRIPT.md:18: Jev said no claim; checked anyway (tag/number)
- jev_claims: SCRIPT.md:30: Jev said no claim; checked anyway (tag/number)
- jev_claims: SCRIPT.md:31: Jev said no claim; checked anyway (tag/number)

## Notes
- loudness_integrated: 61.4s of programme measured
- drawn_text_size: 185 distinct strings from 185 draw records; video height 1080px
- speech_rate: 133 words (count_words) / 53.7s caption-covered time
- asr_wer: 1 edits over 138 normalised reference tokens; language en
- asr_numbers_audible: transcript number words converted to digits before matching
- jev_entailment: mean spread across repeats 0.019 (max 0.040); N=3 repeats; cost $0.003877; 87 calls; model typesafe/jev-1.13-20260917; prompt 23ed4e21bcad3a8b
- jev_contradiction: max 0.13
- jev_claims: Jev alone: 10; mean claim spread 0.019

## Delta vs trusted-segments_v1_r2.json (film_eval 2.0.0, sha256 dfef89b27210f025)

| Metric | Old | New | Delta | Verdict |
|---|---|---|---|---|
| file_size | 23.18 MB | 19.5 MB | -3.68 | PASS -> PASS |
| duration | 76.25 s | 61.375 s | -14.875 | PASS -> PASS |
| resolution | 1920x1080 | 1920x1080 |  | PASS -> PASS |
| fps | 24 | 24 | +0 | PASS -> PASS |
| video_codec | h264/yuv420p | h264/yuv420p |  | PASS -> PASS |
| audio_present | True | True |  | PASS -> PASS |
| audio_codec | aac 48000 Hz 2ch | aac 48000 Hz 2ch |  | PASS -> PASS |
| bitrate | 2432 kbps | 2541 kbps | +109 | PASS -> PASS |
| loudness_integrated | -14 LUFS | -16 LUFS | -2 | FAIL -> PASS |
| true_peak | -1.2 dBTP | -1.7 dBTP | -0.5 | PASS -> PASS |
| loudness_range | 3.2 LU | 3 LU | -0.2 | PASS -> PASS |
| black_frames | 0 s | 0 s | +0 | PASS -> PASS |
| frozen_frames | 4.29 s | 0 s | -4.29 | WARN -> PASS |
| silence | 0 s | 0 s | +0 | PASS -> PASS |
| number_fidelity_narration | 20/20 matched | 20/20 matched | +0 | PASS -> PASS |
| number_fidelity_onscreen | 29/30 matched | 30/30 matched | +1 | PASS -> PASS |
| number_fidelity_srt | 15/15 matched | 15/15 matched | +0 | PASS -> PASS |
| number_fidelity_drawn | (new) | 42/42 matched |  | - -> PASS |
| drawn_text_size | (new) | 28 px |  | - -> PASS |
| tag_coverage | 25/25 (100%) | 25/26 (96%) | +0 | PASS -> WARN |
| tag_validity | 0 unknown ids | 0 unknown ids | +0 | PASS -> PASS |
| tag_consistency | 2 mismatches | 1 mismatches | -1 | WARN -> WARN |
| quote_fidelity | 13/30 exact | 14/40 exact | +1 | PASS -> WARN |
| speech_rate | 137.4 wpm | 148.7 wpm | +11.3 | PASS -> PASS |
| pii_scan | 0 hits | 0 hits | +0 | PASS -> PASS |
| caption_cps | 19.5 cps | 16.9 cps | -2.6 | WARN -> PASS |
| caption_duration | 1.96-4.90 s | 1.42-5.06 s |  | PASS -> PASS |
| caption_line_length | 78 chars | 42 chars | -36 | WARN -> PASS |
| caption_lines_per_cue | 1 lines | 2 lines | +1 | PASS -> PASS |
| caption_timing | 0 overlaps, 14 sub-2-frame gaps | 0 overlaps, 0 sub-2-frame gaps | +0 | WARN -> PASS |
| asr_wer | 3.73 % | 0.72 % | -3.01 | PASS -> PASS |
| asr_numbers_audible | 15/15 | 15/15 | +0 | PASS -> PASS |
| jev_entailment | 0.868 | 0.896 | +0.028 | FAIL -> PASS |
| jev_contradiction | 0 flagged | 0 flagged | +0 | PASS -> PASS |
| jev_claims | 15/16 claim lines | 14/15 claim lines | -1 | PASS -> PASS |

## Tool versions
- film_eval: 2.0.0
- python: 3.13.18
- ffmpeg: ffmpeg version 6.1.1-3ubuntu5 Copyright (c) 2000-2023 the FFmpeg developers
- ffprobe: ffprobe version 6.1.1-3ubuntu5 Copyright (c) 2007-2023 the FFmpeg developers
- faster_whisper: 1.2.1 (/tmp/ext/venv/bin/python, model small.en)
- jev_model: typesafe/jev-1.13-20260917
