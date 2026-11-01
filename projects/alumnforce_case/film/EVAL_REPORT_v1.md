# Film evaluation: trusted-segments.mp4

**Overall: FAIL** · run 2026-11-01T11:16:00Z · sha256 `dfef89b27210f025`

| Group | Metric | Value | Threshold | Verdict |
|---|---|---|---|---|
| technical | file_size | 23.18 MB | <= 25.0 MB | **PASS** |
| technical | duration | 76.25 s | >= last caption end | **PASS** |
| technical | resolution | 1920x1080 | >= 1280x720 | **PASS** |
| technical | fps | 24 | 23.9-60.0 | **PASS** |
| technical | video_codec | h264/yuv420p | h264/yuv420p (web-safe) | **PASS** |
| technical | audio_present | True | audio stream present | **PASS** |
| technical | audio_codec | aac 48000 Hz 2ch | aac | **PASS** |
| technical | bitrate | 2432 kbps | <= 8000 kbps | **PASS** |
| technical | loudness_integrated | -14 LUFS | -16.0 +/-2.0 LUFS (WARN +/-4.0) | **PASS** |
| technical | true_peak | -1.2 dBTP | <= -1.0 dBTP (WARN <= 0.0) | **PASS** |
| technical | loudness_range | 3.2 LU | <= 15.0 LU | **PASS** |
| technical | black_frames | 0 s | longest black < 0.5s (FAIL >= 2.0s), first 1.0s and final 5.0s ignored | **PASS** |
| technical | frozen_frames | 4.29 s | longest freeze <= 4.0s outside final 5.0s (FAIL > 10.0s) | **WARN** |
| technical | silence | 0 s | longest silence <= 3.0s outside final 5.0s (FAIL > 6.0s) | **PASS** |
| content | number_fidelity_srt | 15/15 matched | every number matches a FACTS value | **PASS** |
| content | number_fidelity_script | 43/61 matched | every number matches a FACTS value | **FAIL** |
| content | tag_coverage | 27/30 (90%) | 100% of numeric lines tagged (WARN >= 80%) | **WARN** |
| content | tag_validity | 0 unknown ids | every tagged id exists in FACTS | **PASS** |
| content | tag_consistency | 3 mismatches | each number on a tagged line belongs to one of its tagged facts | **WARN** |
| content | quote_fidelity | 10/30 exact | quotes match FACTS exactly (smart/straight quotes ignored); unattributed quotes WARN | **FAIL** |
| content | speech_rate | 122.8 wpm | 130-170 wpm (WARN +/-15) | **WARN** |
| content | pii_scan | 0 hits | no e-mail, phone or denied name (Camille, Roux) | **PASS** |
| captions | caption_cps | 19.5 cps | max CPS <= 17 (FAIL > 21) | **WARN** |
| captions | caption_duration | 1.96-4.90 s | 1.0-7.0 s per cue | **PASS** |
| captions | caption_line_length | 78 chars | <= 42 chars per line | **WARN** |
| captions | caption_lines_per_cue | 1 lines | <= 2 | **PASS** |
| captions | caption_timing | 0 overlaps, 14 flicker gaps, max gap 1.45s | no overlaps; gaps 0 or >= 0.083s; cues inside the video | **WARN** |
| ai | asr_wer | 1.86 % | <= 5% (WARN <= 10%) | **PASS** |
| ai | asr_fact_numbers_audible | 0/0 | every narrated number heard | **PASS** |
| ai | jev_supported | 0.794 | mean supported >= 0.8, no fact line < 0.5 (advisory: max WARN) | **WARN** |
| ai | jev_clarity | confusing 2, ok 9, clear 5 | advisory | **WARN** |
| ai | jev_claim_types | call_to_action 1, fact 11, interpretation 1, none 3 | advisory | **PASS** |

## Findings

### WARN · frozen_frames
- freeze 55.67-59.96s (4.29s outside hold)

### FAIL · number_fidelity_script
- SCRIPT.md:3: '1920' not in FACTS -> Duration · 1920×1080 · · narrator Kokoro (British English), speed 0.9 · 72 BPM grid.
- SCRIPT.md:3: '1080' not in FACTS -> Duration · 1920×1080 · · narrator Kokoro (British English), speed 0.9 · 72 BPM grid.
- SCRIPT.md:3: '0.9' not in FACTS -> Duration · 1920×1080 · · narrator Kokoro (British English), speed 0.9 · 72 BPM grid.
- SCRIPT.md:3: '72' not in FACTS -> Duration · 1920×1080 · · narrator Kokoro (British English), speed 0.9 · 72 BPM grid.
- SCRIPT.md:33: 'S02' not in FACTS -> S02 | One sentence. Four answers. | yes
- SCRIPT.md:34: 'S03' not in FACTS -> S03 | The file: 525 records, for 500 members. | yes
- SCRIPT.md:35: 'S04' not in FACTS -> S04 | Under the loupe, London is spelled 8 different ways. | yes
- SCRIPT.md:36: 'S05' not in FACTS -> S05 | And 25 people appear twice. | yes
- SCRIPT.md:37: 'S06' not in FACTS -> S06 | Filter the file as delivered: 2 members. | yes
- SCRIPT.md:38: 'S07' not in FACTS -> S07 | Normalise the spellings: 26. | yes
- SCRIPT.md:39: 'S08' not in FACTS -> S08 | Remove the duplicates, read employers and job titles: 49. | yes
- SCRIPT.md:40: 'S09' not in FACTS -> S09 | But look at the dates. | yes
- SCRIPT.md:41: 'S10' not in FACTS -> S10 | 68 % of profiles have not been touched in 2 years or more. | yes
- SCRIPT.md:42: 'S11' not in FACTS -> S11 | “Three years in post” and “three years without an update” are the same signal. | yes
- SCRIPT.md:47: 'S14' not in FACTS -> S14 | 6 can be e-mailed today. | no: the same words are on screen as type
- SCRIPT.md:51: 'S16' not in FACTS -> S16 | Trusted Segments. | no: the same words are on screen as type
- SCRIPT.md:61: 'M0475' not in FACTS -> Under the loupe: card M0475, city line "Londres (Royaume-Uni)" lit and underlined
- SCRIPT.md:81: 'M0001–M0525' not in FACTS -> Card IDs (M0001–M0525) are anonymous record stubs; cities and set membership on the cards are schematic (see ).

### WARN · tag_coverage
- SCRIPT.md:3: no fact id -> Duration 76.25 s · 1920×1080 · 24 fps · narrator Kokoro `bf_emma` (British English), speed 0.9 · 72 
- SCRIPT.md:40: no fact id -> | S09 | 00:32.08 | 00:34.13 | But look at the dates. | — | yes |
- SCRIPT.md:81: no fact id -> Card IDs (M0001–M0525) are anonymous record stubs; cities and set membership on the cards are schema

### WARN · tag_consistency
- SCRIPT.md:67: '3' is in F05,F08, line tagged F22
- SCRIPT.md:67: '3' is in F05,F08, line tagged F22
- SCRIPT.md:69: '500' is in F02, line tagged F13

### FAIL · quote_fidelity
- SCRIPT.md:72: misquote of F17 (97% similar): "340 London expats. / Twenty had moved back years ago. / Two unsubscribed." vs "340 London expats. Twenty had moved back years ago. Two unsubscribed."
- SCRIPT.md:70: case differs from F22: "Three years without an update" vs "three years without an update"
- SCRIPT.md:59: quote not in FACTS: "Schematic · IDs and city only · no member data"
- SCRIPT.md:60: quote not in FACTS: "Rows in the file / 525 / for 500 members announced"
- SCRIPT.md:61: quote not in FACTS: "Londres (Royaume-Uni)"
- SCRIPT.md:62: quote not in FACTS: "London, as typed in the file"
- SCRIPT.md:62: quote not in FACTS: "8 spellings"
- SCRIPT.md:63: quote not in FACTS: "Duplicate persons / 25 / IDs M0501 – M0525"
- SCRIPT.md:64: quote not in FACTS: "Naive filter · file as delivered / 2"
- SCRIPT.md:65: quote not in FACTS: "Normalised · 8 spellings, 3 sector labels / 26"
- SCRIPT.md:66: quote not in FACTS: "Full logic · dedup + employer + job title / 49"
- SCRIPT.md:67: quote not in FACTS: "in post: 3 yrs / updated: 3 yrs ago"
- SCRIPT.md:69: quote not in FACTS: "Profiles untouched for 2+ years / 68 % / of 500 members · ref. 2026-10-12"
- SCRIPT.md:70: quote not in FACTS: "read as tenure —"
- SCRIPT.md:70: quote not in FACTS: "|"
- SCRIPT.md:71: quote not in FACTS: "and label"
- SCRIPT.md:72: quote not in FACTS: "user verbatim"
- SCRIPT.md:73: quote not in FACTS: "Current"
- SCRIPT.md:73: quote not in FACTS: "To confirm"
- SCRIPT.md:75: quote not in FACTS: "6 can be e-mailed today"

### WARN · speech_rate
_156 narration words / 76.2s; narration detected via 'table_column'_

### WARN · caption_cps
- cue 2 (2.78s): 19.5 cps "Graduates working in finance, in London, for more than three"

### WARN · caption_line_length
- cue 2: 67 chars "Graduates working in finance, in London, for more than three"
- cue 5: 52 chars "Under the loupe, London is spelled 8 different ways."
- cue 9: 57 chars "Remove the duplicates, read employers and job titles: 49."
- cue 11: 58 chars "68 % of profiles have not been touched in 2 years or more."
- cue 12: 78 chars "“Three years in post” and “three years without an update” ar"
- cue 13: 44 chars "One user put it plainly: “340 London expats."
- cue 14: 51 chars "Twenty had moved back years ago. Two unsubscribed.”"

### WARN · caption_timing
- cue 1->2: gap 0.040s (< 0.083s flickers)
- cue 2->3: gap 0.040s (< 0.083s flickers)
- cue 3->4: gap 0.040s (< 0.083s flickers)
- cue 4->5: gap 0.040s (< 0.083s flickers)
- cue 5->6: gap 0.040s (< 0.083s flickers)
- cue 7->8: gap 0.053s (< 0.083s flickers)
- cue 8->9: gap 0.040s (< 0.083s flickers)
- cue 10->11: gap 0.040s (< 0.083s flickers)
- cue 11->12: gap 0.040s (< 0.083s flickers)
- cue 13->14: gap 0.040s (< 0.083s flickers)
- cue 15->16: gap 0.040s (< 0.083s flickers)
- cue 18->19: gap 0.040s (< 0.083s flickers)
- cue 19->20: gap 0.040s (< 0.083s flickers)
- cue 20->21: gap 0.040s (< 0.083s flickers)

### WARN · jev_supported
_cost $0.000701; 16/16 lines answered_
- SCRIPT.md:11: supported 0.32 [none] One sentence. Four answers.
- SCRIPT.md:24: supported 0.19 [call_to_action] Describe your audience in one sentence. Get a segment you can trust. No member record ever

## Notes
- asr_wer: 3 edits over 161 reference words; language en

## Tool versions
- film_eval: 1.0.0
- python: 3.13.18
- ffmpeg: ffmpeg version 6.1.1-3ubuntu5 Copyright (c) 2000-2023 the FFmpeg developers
- ffprobe: ffprobe version 6.1.1-3ubuntu5 Copyright (c) 2007-2023 the FFmpeg developers
- faster_whisper: 1.2.1 (/tmp/ext/venv/bin/python, model small)
- jev_model: typesafe/jev-1.13-20260917
