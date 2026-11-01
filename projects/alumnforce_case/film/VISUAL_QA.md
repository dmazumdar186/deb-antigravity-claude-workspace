# Visual QA: trusted-segments.mp4

Reviewed 2026-11-01 against `SCRIPT.md`, `FACTS.md`, `trusted-segments.srt`, `BUILD_LOG.md` and Archive Light Table `STYLE.md` §1–6, 8–9. The style file has no section titled "look" or "self-check", so I used the essence, colour, type, motion and pitfalls sections in their place.

**Frames read:** 51 frames at 1.5 s intervals (`/tmp/vqa/base/`), 9 frames over the push at 44.0–46.0 s (`/tmp/vqa/push/`) and 7 over the fade at 52.0–53.5 s (`/tmp/vqa/fade/`). Scene detection at `gt(scene,0.3)` found no cuts. At 0.15 it found 3 changes (7.71 s, 8.00 s, 44.54 s), saved in `/tmp/vqa/scene/`. I also tiled crops of the reading plate at 0.125 s steps (`/tmp/vqa/fine/`) and built motion strips for the glide, the push, the fade and the switch-off (`/tmp/vqa/strips/`). Contrast numbers come from pixel sampling of the encoded frames (`/tmp/vqa_tools/contrast.py`).

## Verdict: PASS-WITH-FIXES

Every number on screen matches FACTS.md, and each one stays legible for at least 2 s. There is no personal data and no logo, and I found no typos. The film reads as the style. Five defects should be fixed before the panel sees it. The most important is that the reading plate shows a step label next to the previous step's number for half a second, twice. It is a one-line fix.

## Defects

| # | Time code | Frame file | Sev. | What's wrong | Suggested fix |
|---|---|---|---|---|---|
| 1 | 23.625–24.125 and 28.25–28.75 | `fine/plate_23.jpg`, `fine/plate_28.jpg`, `base/t24.00.jpg`, `base/t28.50.jpg` | **high** | The reading plate pairs a label with the wrong value: "Normalised · 8 spellings, 3 sector labels" over **2**, then "Full logic · dedup + employer + job title" over **26**, for 0.5 s each. A viewer who catches it, or a paused frame, shows a wrong fact pairing in the film's core data claim. | `film.js:401` switches the label at `WD.nXX - 0.55`, but `climbV()` (`film.js:180`) switches the value at `WD.nXX - 0.05`. Use one threshold for both, either -0.05 everywhere or -0.55 everywhere. |
| 2 | 9.97–38.95 (every reading plate) | `base/t12.00.jpg`, `t16.50.jpg`, `t24.00.jpg`, `t34.50.jpg` | medium | The signal-orange numbers (525, 25, 2, 26, 49, 68 %) measure about **2.4–2.6:1** against the translucent plate over the lit table. That is below 3:1 even for large text, and a projector will wash it out further. The "8 spellings" line (about 30 px) is also about 2.6:1. Redaction bars show through every plate behind the text. | `film.js:14`: raise the `PLATE` alpha from 0.80 to about 0.92 for `reading()`. Alternatively, draw values on dark plates in a lighter signal tint (for example #FF7A45) or put a solid backing under the value line. The index plates at 55–63 s already reach about 3.8:1 because the table is dark behind them. |
| 3 | 52.25–52.95 | `fade/t52.50.jpg`, `fade/t52.75.jpg`, `strips/fade_grid.jpg` | medium | As the quoted note fades, the paper goes transparent while the darkening cards show through. Ghost italic text then sits on top of the cards for about 0.4 s, which is half-faded text left on screen. | `film.js:234`: shorten the out-fade (`HT.index - 0.2 → HT.index + 0.35`) to about 0.2 s, and finish it before the table dims. Fading the ink first, or lifting the note out with the index whoosh instead of an opacity fade, would also work. |
| 4 | 19.6–32.0 | `base/t22.50.jpg`, `base/t25.50.jpg`, `base/t30.00.jpg` | medium | Outlined matching cards sit under the reading plate (1150–1840 × 70–320). In the "2" beat, one of the two outlined cards is hidden behind it. Four to six of the 26/49 outlines are also covered. The evidence for the number is partly hidden by the number. | `film.js:48`: choose the `in2` and `in26` cards, and preferably all `in49` cards, from positions outside the plate's screen rectangle at camera `HT.climb`. Moving the climb plate to an emptier area would also work. |
| 5 | whole film (delivery) | — | medium | `trusted-segments.srt` has the same basename as the MP4, so VLC and IINA load it automatically. Cues S01–S13 are already burned in, so the panel would see two identical caption blocks stacked or overlapping at the bottom. A two-line player caption at 64–74 s would also touch product line 3 (y ≈ 855–900). | Ship the SRT only with a clean (non-burned) master, or rename it (for example `trusted-segments.captions.srt`) and say "do not enable with the burned-in file" in the hand-off. |
| 6 | 44.40–45.60 | `push/t44.50.jpg`, `push/t44.75.jpg`, `strips/push.jpg` | low | The push takes the zoom from 0.375 to 1.0 (2.7×) in about 1.05 s, and scene detection reads it as a near-cut at 44.54. The pair plates and "the same signal" are still fading (until `HT.quote + 0.3`) while the note fades in (from `HT.quote - 0.2`), so three layers overlap for about 0.5 s. The note is readable from about 45.0 s and holds for about 7 s, so nothing is lost, but the move is abrupt and leaves the loupe out of the style's dive grammar. | `film.js:76–77`: stretch the key `HT.quote + 0.95` to about `+1.5`, and start the note fade at `HT.quote + 0.3` so it begins after the pair plates are gone. |
| 7 | 43.75–51.88 | `base/t48.00.jpg` | low | Burned-in S12a/S12b repeat the quote that is already on screen as the note. This is inconsistent with the decision to drop S14–S16 for the same reason, and it doubles the reading load. | Burn S12a only for "One user put it plainly:", or drop both cues from the burn-in the same way as S14–S16. |
| 8 | 17.05–19.48 | `base/t18.00.jpg` | low | The secondary line "IDs M0501 – M0525" measures about 4.3:1 at about 28 px, just under 4.5. Several duplicate rings show through both the "25" plate and the spellings plate. | Change `film.js:295` source colour from `#aeb3ba` to about `#c4c8ce`. The plate-alpha change in defect 2 fixes the rings showing through. |
| 9 | 8.1–12.5 | `base/t09.00.jpg` | low | The text of the "Schematic · IDs and city only · no member data" tag starts at x = 80. That is outside the 5 % title-safe margin of 96 px, and the plate starts at x = 60. | `film.js:394/430`: move the plate x to 100 and the text x to 120. |
| 10 | about 53.9–54.2 | `base/t54.00.jpg` | low | A card in flight passes over the "To reactivate" header ("To reac▭te"). | Route the flight below y = 200, or draw the column headers above the flying cards. |
| 11 | 42.2–44.9 | `base/t43.50.jpg` | low | The "=" pen stroke sits on a separate dark box (`film.js:364`) that covers a card and looks pasted on. | Drop the box, or merge it into one plate with the two records. |
| 12 | 60.4–63.8 | `base/t61.50.jpg` | low | The bracket is asymmetric: the top rule starts at x ≈ 122 and the bottom rule at x ≈ 217, so it reads as unfinished. | Align both rules at the same start x, or draw a proper "]" with end ticks. |
| 13 | 71.6–72.2 | `base/t72.00.jpg` | low | The query ghosts behind the "Trusted Segments" title during the crossfade, which is half-faded text. | Fade the query out before the title fades in, or wipe the title in. |
| 14 | 31.5–33.75 | `base/t31.50.jpg` | low | The F22 card carries a member-style ID (M0205) and is outlined as one of the 49, but FACTS.md says it "is not a member record". The loupe rim also touches the 49 plate's corner. | Give it a neutral stub ID (for example "M····"), and move the loupe slightly left or down. |
| 15 | 34–39 | `base/t34.50.jpg` | low | "68 %" in 104 px monospace leaves a wide gap between 68 and %. | Use a thin space or render the % in the sans face. |

## Pacing and number legibility

Each number holds long enough to read: 525 for 2.6 s, "8 spellings" for about 4.5 s, 25 for 2.4 s, 2 for 2.25 s with the correct label, 26 for about 4.1 s, 49 for about 3.3 s, 68 % for about 5 s, the 340/Twenty/Two quote for about 7 s, 1·5·43 for 5 s or more, 6 for 3.4 s, and the four answer slots for more than 4 s. Strips: the opening glide (7.6–9.2 s) and the switch-off (63.1–64.7 s) run at a comfortable pace. The only move that is too fast is the push in defect 6.

## Safe areas and captions

Burned captions sit in a bottom-centre plate at about y 945–1028, which is just inside the bottom title-safe line at y 1026. They do not collide with readings: the plates stay at y ≤ 925, and the bottom 140 px is clear of reading text. The only important element outside the 5 % margin is the Schematic tag (defect 9). The other edge items are decorative: the search-panel frame, the table frame, and the rings and outlines at the table edge. The SRT risk is covered in defect 5.

## What works

- Every on-screen number and quote matches FACTS.md exactly: 525/500, 8, 25 (M0501–M0525), 2, 26, 49, 68 %, ref. 2026-10-12, the F17 quote word for word, 1/5/43, 6, and F19/F23. I counted 25 rings, 1, 5 and 43 cards (5×8+3), and 8 spellings.
- There is no personal data. Personal fields are redaction bars, and only anonymous IDs appear (M0475, M0205, and partial M0474/M0136). There is no logo, and I found no typos.
- It reads as Archive Light Table: a backlit cool table, a loupe that lands with a rim and acrylic skirt and lights the city line, one signal orange, dark caption plates with a 3 px signal edge, and the mono, sans and serif roles as specified.
- The arc is legible without sound. The four "?" slots filling to 2 · 26 · 49 · 6 at the end close the opening's question cleanly.
- The quote note (serif italic, ink on paper, about 13:1) and the closing product lines (about 10:1) are the most legible frames in the film.

## Honest gaps

- I reviewed sampled frames (1.5 s intervals plus 0.25 s and 0.125 s bursts), not every frame. A flicker of one or two frames between samples could be missed. Scene detection at 0.15 found nothing beyond the three changes listed above.
- Contrast was measured on the CRF 26 encode with grain, so it reads slightly low compared with the source canvas. The ranking of problems holds, but the exact ratios are ±0.3. I did not test on a projector.
- Glyph sizes are estimated from the source code (`F.mono(28)`, `F.sans(30)`, subtitles at 40 px) and on-frame cap heights, not measured per glyph. Secondary text sits at the 28 px threshold rather than above it.
- I did not check the eight London spellings against VERIFICATION.md itself, only against SCRIPT.md and the count in FACTS.md (F04 = 8).
- I did not review audio, sync or narration timing, apart from noting that "26" lands at 24.125 s, slightly before the spoken word.
