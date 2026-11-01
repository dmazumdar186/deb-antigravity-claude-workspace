# Film evaluation: prodcraft-wk02-replies.mp4

**Overall: WARN** · film_eval 2.1.0 · run 2026-11-01T14:13:31Z · sha256 `82338647cd8820c64ea9a2893532e57ed57da1434f0a7f3409bc65da6411fa6d`

| Group | Metric | Value | n | Source | Threshold | Basis | Verdict |
|---|---|---|---|---|---|---|---|
| technical | file_size | 2.4 MB | 1 | prodcraft-wk02-replies.mp4 | <= 25.0 MB | Gmail attachment limit (25 MB) | **PASS** |
| technical | duration | 27.733 s | 1 | prodcraft-wk02-replies.mp4 | > 0 s (no captions) | consistency check | **PASS** |
| technical | resolution | 1080x1350 | 1 | prodcraft-wk02-replies.mp4 | >= 1080x1350, 4:5 (profile linkedin_4x5) | guess (LinkedIn 4:5 feed video, 1080x1350) | **PASS** |
| technical | fps | 30 | 1 | prodcraft-wk02-replies.mp4 | 23.9-60.0 | guess | **PASS** |
| technical | video_codec | h264/yuv420p | 1 | prodcraft-wk02-replies.mp4 | h264/yuv420p | guess (h264/yuv420p plays everywhere) | **PASS** |
| technical | audio_present | True | 1 | prodcraft-wk02-replies.mp4 | audio stream present | guess | **PASS** |
| technical | audio_codec | aac 48000 Hz 2ch | 1 | prodcraft-wk02-replies.mp4 | aac | guess | **PASS** |
| technical | bitrate | 693 kbps | 1 | prodcraft-wk02-replies.mp4 | <= 8000 kbps | guess | **PASS** |
| technical | loudness_integrated | -16 LUFS | 1 | prodcraft-wk02-replies.mp4 | -16.0 +/-1.0 LUFS | AES TD1004/TD1008 (-16 LUFS for streamed speech); measured per ITU-R BS.1770 / EBU R128; +/-1 LU tolerance per EBU R128 | **PASS** |
| technical | true_peak | -1.6 dBTP | 1 | prodcraft-wk02-replies.mp4 | <= -1.0 dBTP | EBU R128 / AES TD1008 (max -1 dBTP) | **PASS** |
| technical | loudness_range | 3.6 LU | 1 | prodcraft-wk02-replies.mp4 | <= 15.0 LU | guess | **PASS** |
| technical | black_frames | 0 s | 0 | prodcraft-wk02-replies.mp4 | longest black < 0.5s (FAIL >= 2.0s); first 1.0s, final 5.0s ignored | guess | **PASS** |
| technical | frozen_frames | 0 s | 0 | prodcraft-wk02-replies.mp4 | longest freeze <= 4.0s outside final 5.0s (FAIL > 10.0s) | guess | **PASS** |
| technical | silence | 0 s | 0 | prodcraft-wk02-replies.mp4 | longest silence <= 3.0s outside final 5.0s (FAIL > 6.0s) | guess | **PASS** |
| content | number_fidelity_narration | 0 numbers | 0 | SCRIPT.md narration (sections) | every number matches a FACTS value | - | **PASS** |
| content | number_fidelity_onscreen | 11/11 matched | 11 | SCRIPT.md on-screen text | every number matches a FACTS value | - | **PASS** |
| content | number_fidelity_srt | - | 0 | no SRT | every number matches a FACTS value | - | **SKIPPED** |
| content | number_fidelity_drawn | 13/13 matched | 13 | drawn_text.json | every number matches a FACTS value | - | **PASS** |
| content | drawn_text_size | 14 px | 54 | drawn_text.json | no text < 28 px on screen >= 1 s | guess (28 px at 1080p, >= 1 s on screen) | **WARN** |
| content | drawn_text_mobile | 5.1 pt | 54 | drawn_text.json | no text < 11 pt at px x 390/1080 (on screen >= 1 s) | guess (mobile-feed readability proxy: px x 390/1080 = pt on a 390-pt-wide phone, 11 pt floor) | **WARN** |
| content | tag_coverage | 8/8 (100%) | 8 | SCRIPT.md (narration + on-screen) | 100% of numeric lines tagged (WARN >= 80%) | guess | **PASS** |
| content | tag_validity | 0 unknown ids | 43 | SCRIPT.md (narration + on-screen) | every tagged id exists in FACTS | guess | **PASS** |
| content | tag_consistency | 0 mismatches | 8 | SCRIPT.md (narration + on-screen) | each number on a tagged line belongs to one of its tagged facts | guess | **PASS** |
| content | quote_fidelity | 5/15 exact | 15 | SCRIPT.md + drawn | quotations match FACTS exactly (smart/straight quotes and line breaks ignored) | exact match; 0.6 similarity cut = guess | **PASS** |
| content | speech_rate | - | 0 | SCRIPT.md | 130-170 wpm (WARN +/-15) | guess, bounded by BBC Subtitle Guidelines (160-180 wpm subtitle rate) | **SKIPPED** |
| content | pii_scan | 0 hits | 144 | SCRIPT.md + drawn | no e-mail, phone or denied name (Camille, Roux) | FACTS hard rules (no member data) | **PASS** |
| captions | caption_cps | - | 0 | no SRT | max CPS <= 17 (FAIL > 21) | Netflix English Timed Text Style Guide: 17 cps = children's limit (adult 20), used as WARN; FAIL 21 = guess | **SKIPPED** |
| captions | caption_duration | - | 0 | no SRT | 1.0-7.0 s per cue | Netflix TTSG: max 7 s; min 1.0 s = guess (Netflix minimum is 5/6 s) | **SKIPPED** |
| captions | caption_line_length | - | 0 | no SRT | <= 42 chars per line | Netflix TTSG: 42 characters per line | **SKIPPED** |
| captions | caption_lines_per_cue | - | 0 | no SRT | <= 2 | Netflix TTSG: max 2 lines | **SKIPPED** |
| captions | caption_timing | - | 0 | no SRT | no overlaps; gaps 0 or >= 2 frames; cues inside the video | Netflix TTSG timing guidelines: 2-frame minimum gap between events | **SKIPPED** |

## Findings

### WARN · drawn_text_size
_54 distinct strings from 54 draw records; video height 1350px_
- drawn#0@0.00s: 26.4px for 27.7s "ProdCraft"
- drawn#1@0.00s: 14px for 27.7s "wk 02"
- drawn#4@0.00s: 14px for 27.7s "ProdCraft · weekly notes"
- drawn#5@0.00s: 14px for 27.7s "02"
- drawn#7@2.67s: 15px for 14.5s "illustrative replies"
- drawn#8@2.67s: 25px for 14.5s "Tell me more."
- drawn#10@2.97s: 25px for 14.2s "I’m out of the office until Monday."
- drawn#11@3.20s: 25px for 14.0s "Please unsubscribe me."
- drawn#12@3.47s: 25px for 13.7s "What does pricing look like?"
- drawn#13@3.77s: 25px for 13.4s "Automatic reply: on vacation."
- drawn#14@4.00s: 25px for 13.2s "Can we jump on a call next week?"
- drawn#15@4.27s: 25px for 12.9s "Not interested, thanks."
- drawn#16@8.27s: 14px for 5.5s "verbatim"
- drawn#17@8.27s: 18px for 5.5s "self_outbound_system / "
- drawn#18@8.27s: 18px for 5.5s "reply_classifier.py"
- drawn#20@8.27s: 24px for 5.5s "ooo_hits = _matches_any(text, _OOO_PATTERNS)"
- drawn#21@8.27s: 24px for 5.5s "if"
- drawn#22@8.27s: 24px for 5.5s " ooo_hits:"
- drawn#23@8.27s: 24px for 5.6s "return"
- drawn#24@8.27s: 24px for 5.6s " {"
- drawn#25@8.27s: 24px for 5.6s ""class""
- drawn#26@8.27s: 24px for 5.6s ": "
- drawn#27@8.27s: 24px for 5.6s ""auto_reply_or_OOO""
- drawn#28@8.27s: 24px for 5.6s ","
- drawn#29@8.27s: 24px for 5.6s ""confidence""
- ... 16 more in the JSON report

### WARN · drawn_text_mobile
_profile linkedin_4x5; mobile-feed readability proxy_
- drawn#0@0.00s: 26.4px = 9.5 pt "ProdCraft"
- drawn#1@0.00s: 14px = 5.1 pt "wk 02"
- drawn#4@0.00s: 14px = 5.1 pt "ProdCraft · weekly notes"
- drawn#5@0.00s: 14px = 5.1 pt "02"
- drawn#7@2.67s: 15px = 5.4 pt "illustrative replies"
- drawn#8@2.67s: 25px = 9.0 pt "Tell me more."
- drawn#10@2.97s: 25px = 9.0 pt "I’m out of the office until Monday."
- drawn#11@3.20s: 25px = 9.0 pt "Please unsubscribe me."
- drawn#12@3.47s: 25px = 9.0 pt "What does pricing look like?"
- drawn#13@3.77s: 25px = 9.0 pt "Automatic reply: on vacation."
- drawn#14@4.00s: 25px = 9.0 pt "Can we jump on a call next week?"
- drawn#15@4.27s: 25px = 9.0 pt "Not interested, thanks."
- drawn#16@8.27s: 14px = 5.1 pt "verbatim"
- drawn#17@8.27s: 18px = 6.5 pt "self_outbound_system / "
- drawn#18@8.27s: 18px = 6.5 pt "reply_classifier.py"
- drawn#20@8.27s: 24px = 8.7 pt "ooo_hits = _matches_any(text, _OOO_PATTERNS)"
- drawn#21@8.27s: 24px = 8.7 pt "if"
- drawn#22@8.27s: 24px = 8.7 pt " ooo_hits:"
- drawn#23@8.27s: 24px = 8.7 pt "return"
- drawn#24@8.27s: 24px = 8.7 pt " {"
- drawn#25@8.27s: 24px = 8.7 pt ""class""
- drawn#26@8.27s: 24px = 8.7 pt ": "
- drawn#27@8.27s: 24px = 8.7 pt ""auto_reply_or_OOO""
- drawn#28@8.27s: 24px = 8.7 pt ","
- drawn#29@8.27s: 24px = 8.7 pt ""confidence""
- ... 16 more in the JSON report

## Info (not counted)
- quote_fidelity: SCRIPT.md:28: label "class" (wording not checked; numbers are)
- quote_fidelity: SCRIPT.md:29: label "confidence" (wording not checked; numbers are)
- quote_fidelity: SCRIPT.md:30: label "explanation" (wording not checked; numbers are)
- quote_fidelity: SCRIPT.md:31: label "detected_intent_signals" (wording not checked; numbers are)
- quote_fidelity: SCRIPT.md:32: label "cost_eur_estimate" (wording not checked; numbers are)
- quote_fidelity: drawn#25@8.27s: label "class" (wording not checked; numbers are)
- quote_fidelity: drawn#29@8.27s: label "confidence" (wording not checked; numbers are)
- quote_fidelity: drawn#31@8.27s: label "explanation" (wording not checked; numbers are)
- quote_fidelity: drawn#33@8.27s: label "detected_intent_signals" (wording not checked; numbers are)
- quote_fidelity: drawn#35@8.27s: label "cost_eur_estimate" (wording not checked; numbers are)

## Skipped
- number_fidelity_srt: no captions supplied
- speech_rate: no narration
- caption_cps: no captions supplied
- caption_duration: no captions supplied
- caption_line_length: no captions supplied
- caption_lines_per_cue: no captions supplied
- caption_timing: no captions supplied

## Notes
- loudness_integrated: 27.7s of programme measured
- number_fidelity_narration: no numbers in this source

## Tool versions
- film_eval: 2.1.0
- python: 3.13.18
- ffmpeg: ffmpeg version 6.1.1-3ubuntu5 Copyright (c) 2000-2023 the FFmpeg developers
- ffprobe: ffprobe version 6.1.1-3ubuntu5 Copyright (c) 2007-2023 the FFmpeg developers
