# Film evaluation: prodcraft-wk02-replies.mp4

**Overall: WARN** · film_eval 2.1.0 · run 2026-11-01T14:34:36Z · sha256 `ecf6d307aff0039957ec70cdd8a32424c13971196a640bcba6f8beb507a01524`

| Group | Metric | Value | n | Source | Threshold | Basis | Verdict |
|---|---|---|---|---|---|---|---|
| technical | file_size | 3.16 MB | 1 | prodcraft-wk02-replies.mp4 | <= 25.0 MB | Gmail attachment limit (25 MB) | **PASS** |
| technical | duration | 27.733 s | 1 | prodcraft-wk02-replies.mp4 | > 0 s (no captions) | consistency check | **PASS** |
| technical | resolution | 1080x1350 | 1 | prodcraft-wk02-replies.mp4 | >= 1080x1350, 4:5 (profile linkedin_4x5) | guess (LinkedIn 4:5 feed video, 1080x1350) | **PASS** |
| technical | fps | 30 | 1 | prodcraft-wk02-replies.mp4 | 23.9-60.0 | guess | **PASS** |
| technical | video_codec | h264/yuv420p | 1 | prodcraft-wk02-replies.mp4 | h264/yuv420p | guess (h264/yuv420p plays everywhere) | **PASS** |
| technical | audio_present | True | 1 | prodcraft-wk02-replies.mp4 | audio stream present | guess | **PASS** |
| technical | audio_codec | aac 48000 Hz 2ch | 1 | prodcraft-wk02-replies.mp4 | aac | guess | **PASS** |
| technical | bitrate | 912 kbps | 1 | prodcraft-wk02-replies.mp4 | <= 8000 kbps | guess | **PASS** |
| technical | loudness_integrated | -16 LUFS | 1 | prodcraft-wk02-replies.mp4 | -16.0 +/-1.0 LUFS | AES TD1004/TD1008 (-16 LUFS for streamed speech); measured per ITU-R BS.1770 / EBU R128; +/-1 LU tolerance per EBU R128 | **PASS** |
| technical | true_peak | -1.7 dBTP | 1 | prodcraft-wk02-replies.mp4 | <= -1.0 dBTP | EBU R128 / AES TD1008 (max -1 dBTP) | **PASS** |
| technical | loudness_range | 3.7 LU | 1 | prodcraft-wk02-replies.mp4 | <= 15.0 LU | guess | **PASS** |
| technical | black_frames | 0 s | 0 | prodcraft-wk02-replies.mp4 | longest black < 0.5s (FAIL >= 2.0s); first 1.0s, final 5.0s ignored | guess | **PASS** |
| technical | frozen_frames | 0 s | 0 | prodcraft-wk02-replies.mp4 | longest freeze <= 4.0s outside final 5.0s (FAIL > 10.0s) | guess | **PASS** |
| technical | silence | 0 s | 0 | prodcraft-wk02-replies.mp4 | longest silence <= 3.0s outside final 5.0s (FAIL > 6.0s) | guess | **PASS** |
| content | number_fidelity_narration | - | 0 | SCRIPT.md narration (sections) | every number matches a FACTS value | - | **SKIPPED** |
| content | number_fidelity_onscreen | 10/10 matched | 10 | SCRIPT.md on-screen text | every number matches a FACTS value | - | **PASS** |
| content | number_fidelity_srt | - | 0 | no SRT | every number matches a FACTS value | - | **SKIPPED** |
| content | number_fidelity_drawn | 12/12 matched | 12 | drawn_text.json | every number matches a FACTS value | - | **PASS** |
| content | drawn_text_size | 14 px | 53 | drawn_text.json | no text < 28 px on screen >= 1 s | guess (28 px at 1080p, >= 1 s on screen) | **WARN** |
| content | drawn_text_mobile | 5.1 pt | 53 | drawn_text.json | no text < 11 pt at px x 390/1080 (on screen >= 1 s) | guess (mobile-feed readability proxy: px x 390/1080 = pt on a 390-pt-wide phone, 11 pt floor) | **WARN** |
| content | tag_coverage | 7/7 (100%) | 7 | SCRIPT.md (narration + on-screen) | 100% of numeric lines tagged (WARN >= 80%) | guess | **PASS** |
| content | tag_validity | 0 unknown ids | 42 | SCRIPT.md (narration + on-screen) | every tagged id exists in FACTS | guess | **PASS** |
| content | tag_consistency | 0 mismatches | 7 | SCRIPT.md (narration + on-screen) | each number on a tagged line belongs to one of its tagged facts | guess | **PASS** |
| content | quote_fidelity | 5/15 exact | 15 | SCRIPT.md + drawn | quotations match FACTS exactly (smart/straight quotes and line breaks ignored) | exact match; 0.6 similarity cut = guess | **PASS** |
| content | speech_rate | - | 0 | SCRIPT.md | 130-170 wpm (WARN +/-15) | guess, bounded by BBC Subtitle Guidelines (160-180 wpm subtitle rate) | **SKIPPED** |
| content | pii_scan | 0 hits | 139 | SCRIPT.md + drawn | no e-mail, phone or denied name (Camille, Roux) | FACTS hard rules (no member data) | **PASS** |
| captions | caption_cps | - | 0 | no SRT | max CPS <= 17 (FAIL > 21) | Netflix English Timed Text Style Guide: 17 cps = children's limit (adult 20), used as WARN; FAIL 21 = guess | **SKIPPED** |
| captions | caption_duration | - | 0 | no SRT | 1.0-7.0 s per cue | Netflix TTSG: max 7 s; min 1.0 s = guess (Netflix minimum is 5/6 s) | **SKIPPED** |
| captions | caption_line_length | - | 0 | no SRT | <= 42 chars per line | Netflix TTSG: 42 characters per line | **SKIPPED** |
| captions | caption_lines_per_cue | - | 0 | no SRT | <= 2 | Netflix TTSG: max 2 lines | **SKIPPED** |
| captions | caption_timing | - | 0 | no SRT | no overlaps; gaps 0 or >= 2 frames; cues inside the video | Netflix TTSG timing guidelines: 2-frame minimum gap between events | **SKIPPED** |

## Findings

### WARN · drawn_text_size
_53 distinct strings from 53 draw records; video height 1350px_
- drawn#0@0.00s: 26.4px for 27.7s "ProdCraft"
- drawn#1@0.00s: 14px for 27.7s "wk 02"
- drawn#4@0.00s: 14px for 27.7s "ProdCraft · weekly notes"
- drawn#5@0.00s: 14px for 27.7s "02"
- drawn#51@21.97s: 18px for 5.8s "Made in code with lemo-opuscar (MIT)"
- drawn#52@22.23s: 18px for 5.5s "music: original, CC0 samples (Versilian Studios)"

### WARN · drawn_text_mobile
_profile linkedin_4x5; mobile-feed readability proxy_
- drawn#0@0.00s: 26.4px = 9.5 pt "ProdCraft"
- drawn#1@0.00s: 14px = 5.1 pt "wk 02"
- drawn#4@0.00s: 14px = 5.1 pt "ProdCraft · weekly notes"
- drawn#5@0.00s: 14px = 5.1 pt "02"
- drawn#15@7.83s: 30px = 10.8 pt "ooo_hits = _matches_any(text, _OOO_PATTERNS)"
- drawn#16@7.83s: 30px = 10.8 pt "if"
- drawn#17@7.83s: 30px = 10.8 pt " }"
- drawn#19@7.87s: 30px = 10.8 pt " ooo_hits:"
- drawn#20@7.87s: 30px = 10.8 pt "return"
- drawn#21@7.87s: 30px = 10.8 pt ""class""
- drawn#22@7.87s: 30px = 10.8 pt ""confidence""
- drawn#23@7.87s: 30px = 10.8 pt ""explanation""
- drawn#24@7.87s: 30px = 10.8 pt ""detected_intent_signals""
- drawn#25@7.87s: 30px = 10.8 pt ""cost_eur_estimate""
- drawn#26@7.93s: 30px = 10.8 pt " {"
- drawn#27@7.93s: 30px = 10.8 pt ": "
- drawn#28@7.93s: 30px = 10.8 pt ""auto_reply_or_OOO""
- drawn#29@7.97s: 30px = 10.8 pt ": 0.99,"
- drawn#30@7.97s: 30px = 10.8 pt ""deterministic OOO pattern matched""
- drawn#31@7.97s: 30px = 10.8 pt ": 0.0,"
- drawn#32@8.00s: 30px = 10.8 pt ","
- drawn#33@8.00s: 30px = 10.8 pt ": ooo_hits,"
- drawn#51@21.97s: 18px = 6.5 pt "Made in code with lemo-opuscar (MIT)"
- drawn#52@22.23s: 18px = 6.5 pt "music: original, CC0 samples (Versilian Studios)"

## Info (not counted)
- quote_fidelity: SCRIPT.md:26: label "class" (wording not checked; numbers are)
- quote_fidelity: SCRIPT.md:27: label "confidence" (wording not checked; numbers are)
- quote_fidelity: SCRIPT.md:28: label "explanation" (wording not checked; numbers are)
- quote_fidelity: SCRIPT.md:29: label "detected_intent_signals" (wording not checked; numbers are)
- quote_fidelity: SCRIPT.md:30: label "cost_eur_estimate" (wording not checked; numbers are)
- quote_fidelity: drawn#21@7.87s: label "class" (wording not checked; numbers are)
- quote_fidelity: drawn#22@7.87s: label "confidence" (wording not checked; numbers are)
- quote_fidelity: drawn#23@7.87s: label "explanation" (wording not checked; numbers are)
- quote_fidelity: drawn#24@7.87s: label "detected_intent_signals" (wording not checked; numbers are)
- quote_fidelity: drawn#25@7.87s: label "cost_eur_estimate" (wording not checked; numbers are)

## Skipped
- number_fidelity_narration: no narration
- number_fidelity_srt: no captions supplied
- speech_rate: no narration
- caption_cps: no captions supplied
- caption_duration: no captions supplied
- caption_line_length: no captions supplied
- caption_lines_per_cue: no captions supplied
- caption_timing: no captions supplied

## Notes
- loudness_integrated: 27.7s of programme measured

## Tool versions
- film_eval: 2.1.0
- python: 3.13.18
- ffmpeg: ffmpeg version 6.1.1-3ubuntu5 Copyright (c) 2000-2023 the FFmpeg developers
- ffprobe: ffprobe version 6.1.1-3ubuntu5 Copyright (c) 2007-2023 the FFmpeg developers
