# Visual QA, round 3: trusted-segments.mp4 (v2.1)

Reviewed on 2026-11-01. I checked `trusted-segments.mp4` (burned captions) and `trusted-segments_clean.mp4` (both 1920×1080, 24 fps, 1,477 frames, 61.54 s) against `VISUAL_QA_v2.md` (round 2), the v2.1 section of `BUILD_LOG.md`, `FACTS.md` (including its hard rules), `trusted-segments_clean.captions.srt` and `src/out/drawn_text.json`. I did not edit the film or its sources.

**Frames I read:**
- One frame per second from each master, 0–61 s (`/tmp/vqa3/b1/bNN.jpg` and `/tmp/vqa3/c1/cNN.jpg`, where NN is the second). They are tiled with time labels in `/tmp/vqa3/sheets/b1_*` and `c1_*`.
- Frames every 0.125 s on the burned master across 10–17 s, 24–28 s, 45–52 s and 55.5–61.5 s (`/tmp/vqa3/fine/w<start>/fNNN.jpg`, at time start + (NNN−1)·0.125 s). They are tiled in `/tmp/vqa3/sheets/w*`.
- Full-resolution stills for zoom and pixel sampling (`/tmp/vqa3/full/`). Contrast script: `/tmp/vqa3_tools/contrast.py`.

In total I read 316 sampled frames: 62 + 62 at 1 s and 192 at 0.125 s.

## Verdict: PASS

All eight round-2 findings are closed in the pixels:
- The thesis now fades in on a clear frame.
- The end card no longer dissolves over the panel.
- The column text is gone before the six cards move.
- "25 duplicate persons" is on screen on both masters.
- Caption and voice now say "43 to reactivate".
- Every orange value, on the left and on the right, clears 4.5:1. The lowest is the payoff "6" at 4.95:1 against the brightest 5 % of its background.

No invented city appears anywhere: the manifest has no Singapore, Nantes or Milan entry. M0271 is the only ID drawn.

The fresh pass found no typos, no cut text, no label over the wrong value and no number outside FACTS. One low residual of N1 remains, together with two cosmetic notes. None of them blocks the panel.

## Round-2 closure table

| R2 item | Status | Evidence |
|---|---|---|
| N1: invented cities legible in the loupe | **closed as re-scoped; low residual** | No invented city is drawn: `drawn_text.json` has no Singapore, Nantes, Milan or "London, UK" next to an ID. The dates loupe shows only "example / london / in post: 3 yrs / updated: 3 yrs ago", and its neighbours are bars (`fine/w24/f009`, 25.0 s; `f026–f028`, 27.125–27.375 s lift). **Residual:** while the M0271 loupe lands and lifts, two real F04 spellings on ID-less neighbouring cards become readable inside the lens: "London" under M0271 and "Lor…" ("London, UK") to its right (`full/b_11.125.png`, `full/b_15.625.png`, `fine/w10/f010`, `f045–f046`). The hard rules allow this (no ID, real spelling), and v2.1 chose it on purpose. It is still more than the round-2 brief's "only M0271 + Londres (Royaume-Uni) in the close-up". See R1 below. |
| N2: thesis faded in over the payoff | **closed** | The payoff block and the six cards fade from 50.625 s (`fine/w45/f046`) and are near zero at 50.875 s (`f048`). 51.0 s is an empty dark frame (`f049`). The thesis starts at 51.125 s (`f050`) with nothing under it. The "6" is at full strength from 47.875 s (`f024`) to about 50.625 s, roughly 2.75 s. |
| #2 / N3: left-hand orange contrast | **closed** | The value tint is now uniform across the frame: #EE8353 on the left ("525") and #EF8351 on the right ("26"), against round 2's #D1683C / #ED7542. Measured contrast (glyph core against the plate median, then against the brightest 5 % of plate pixels): 525 **5.94 / 5.79**, 8 spellings **5.66 / 5.48**, 68 % **6.32 / 5.81**, "1" **6.35 / 6.04**, "5" 6.06 / 5.85, 2 5.75 / 5.65, 26 5.80 / 5.70, 49 5.81 / 5.68, 43 6.37 / 5.89, legend "25" 5.93 / 5.78, payoff "6" **5.10 / 4.95**, end-panel "6" slot 6.03 / 5.87. The clean master matches within ±0.07. All are ≥ 4.5:1. |
| N4: 25 duplicates missing on screen | **closed** | A legend plate, "○ 25 duplicate persons", sits bottom left from 20.58 to 25.33 s on both masters (`b1/b21–b24`, `c1/c21–c24`, `full/b_25.0.png`). Its left edge is at x = 100, inside title-safe, and it does not touch the caption plate (32 px gap). As in round 2, the rings and the legend appear about 3.5 s before the plate switches to 49, while the caption already narrates the merge. That follows the voice and is not a label/value mismatch. |
| N5: ghost column text at about 47.0 s | **closed** | The headers and the counts 1 / 5 / 43 fade at 47.125–47.25 s while every card is still parked (`fine/w45/f018–f019`). By 47.375 s the columns and the 43 dark cards are gone (`f020`). The six cards start to move at about 47.5 s over a clean table (`f021–f023`). The "6" appears at 47.875 s after they have passed under it (`f024`). No text sits behind a moving card. |
| N6: ghost text at the end-card dissolve | **closed** | The panel, title and thesis fade to the dark ground at 56.875 s (`fine/w55.5/f012`). 57.0 s is an empty dark frame (`f013`). The card fades in from 57.125 s (`f014`) and reaches full strength at 57.25 s (`f015`). No frame shows credits over the slots or the thesis. |
| N7: "win back" vs "reactivate" | **closed** | Burned caption C15 reads "1 to send, 5 to confirm, / 43 to reactivate." (`b1/b44–b46`, `fine/w45/f001–f019`). SRT cue 15 matches. In `EVAL_REPORT_v2_1.json`, the ASR transcript reads "…five to confirm, 43 to reactivate". "win back" appears 0 times. |
| N8: sidecar SRT name | **unchanged (accepted)** | The only caption file is still `trusted-segments_clean.captions.srt`, and neither MP4 has a subtitle stream. VLC fuzzy auto-load for the burned file is still untested (see Honest gaps). |

## Fresh pass: hard rules and brief checks

| Check | Result |
|---|---|
| Label over the wrong value | Pass. Every step label switches on the same frame as its value: 2 lands at 16.25 s (`fine/w10/f051`), 26 at 19.25 s, and "Normalised · 26" → "Full logic · 49" at 24.125 s (`fine/w24/f001–f002`). The 68 % plate lands with its own label at 27.5–27.625 s (`f029–f030`). Before a value lands, a plate shows its label alone (`fine/w10/f038–f050`, 14.625–16.125 s). The 43 column shows its label and cards before its count (`fine/w45/f001–f005`). |
| IDs other than M0271 | None. The manifest regex `M\d{3,4}` finds only `M0271`. The dates card reads "example". |
| Readable invented data | None. Every readable string is in FACTS or the credits. The schematic "in post: 3 yrs / updated: 3 yrs ago" on the example card illustrates F22. The only readable card-level cities are M0271's "Londres (Royaume-Uni)", the example card's "london", and the two F04 spellings in the N1 residual. |
| Numbers | Every drawn number is in FACTS: 525, 500, 8, 2, 26, 25, 49, 68 %, 2026-10-12, 340 / Twenty / Two (F17), 1, 5, 43, 6, "2+ years" (F13). Credit-line version numbers (V3, 2.0, 3.0) are required by the hard rules. |
| Typos / cut text | None found in any of the 76 distinct full strings in `drawn_text.json` or in the 18 SRT cues. The only partial words are type-on and wipe frames by design (search box 0–3 s, title wipe at about 54.5 s). |
| Overlaps | None outside short, intended transitions. The loupe passes under the "Naive filter" plate as it lifts (15.375–15.625 s), and the plate is drawn on top (`full/b_15.625.png`). The 525 plate fades while the loupe lands (`full/b_11.125.png`), but they do not overlap. |
| "Schematic" tag | On screen from 7.0 s to about 50.7 s, covering both loupe passes and every frame where card text is readable. |
| Captions | F01 is quoted exactly with no commas (`b1/b02–b05`). F24 is verbatim (`b1/b51–b56`). On the burned master, cues 16–18 ("6 worth contacting today.", the thesis, "Trusted Segments.") are not burned because the same words are drawn on screen. The clean master has no burned caption in any of its 62 frames. |
| End card | Readable. Title 13.8:1, credit lines 11.4–11.5:1, all 36 px. It holds from 57.25 s to 61.5 s (about 4.3 s) with every credit FACTS requires: lemo-opuscar (MIT); Kokoro (Apache 2.0); Salamander Grand Piano V3 by Alexander Holm, CC BY 3.0, plus its URL; strings and mallets CC0, Versilian Studios; IBM Plex (OFL); "Record cards are schematic · no member data". All text sits between y ≈ 240 and 850, centred, well inside the safe area. |
| Title-safe (5 % = 96 px / 54 px) | All text is inside. Plates start at x = 100. The tag plate ends at about x 1824, exactly on the safe line. The step plate background (2 / 26 / 49) runs to x = 1839, 15 px past the line, but its text ends at about x 1700 (R3). |

## New or residual defects

| # | Time code | Frame | Sev. | What's wrong | Fix (optional) |
|---|---|---|---|---|---|
| R1 | 11.1–11.3 s (land), 15.4–15.7 s (lift) | `full/b_11.125.png`, `full/b_15.625.png`, `fine/w10/f010`, `f045–f046` | low | Neighbouring ID-less cards show "London" (about 34–38 px) directly under M0271 and a cut "Lor…" to its right inside the lens. Both are real F04 spellings and no rule is broken. But a viewer can read "London" as a second city line belonging to M0271, and the cut "Lor…" looks clipped. | Render neighbour cities as bars inside the M0271 lens (keep glyphs only on the left-hand spelling list), or clip the lens to the M0271 card while it lands and lifts. |
| R2 | 12.75–12.9 s | `fine/w10/f023–f024` | cosmetic | "8 spellings" lands while only two spellings are typed in the list. The value comes ahead of its evidence for about 0.3 s. It is correctly labelled, so this is not a rule breach. | Optional: land "8 spellings" after the eighth line (about 13.33 s). |
| R3 | 14.6–28.2 s | `full/b_25.0.png` | cosmetic | The step plate background extends 15 px past the right title-safe line. Its text is inside. This was carried over from round 2. | Optional: inset the plate by 16 px. |

## Honest gaps

- I read 316 sampled frames: 1 s across both masters, plus 0.125 s on the burned master over the four requested windows. I did not read all 1,477 frames. A one-frame flash between samples could be missed. I used `drawn_text.json` to check for text between samples, but it is the builder's own manifest.
- Contrast comes from pixel sampling of the encoded masters (`ffmpeg` stills), not the source canvas. Treat the ratios as ±0.2. The glyph colour is the mean of the top 3 % of pixels by orange strength, and the background is plate pixels only. I did not test on a projector.
- I did not listen to the audio. The "reactivate" wording in the voice is confirmed only through the ASR transcript in `EVAL_REPORT_v2_1.json`.
- I did not test VLC or IINA subtitle auto-loading (N8).
- I did not count the 26 outlines, 25 rings or 49 highlights card by card. I counted the 2 outlines, the 1 / 5 / 43 column cards (43 = 7 × 6 + 1) and the six payoff cards.
- I read the fine windows on the burned master only. On the clean master I checked them at 1 s intervals and with full-resolution stills at 9.5, 14.0, 16.75, 22.0, 29.0, 46.5 and 49.0 s.
