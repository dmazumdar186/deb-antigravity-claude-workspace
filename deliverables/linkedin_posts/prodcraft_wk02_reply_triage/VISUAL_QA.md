# Visual QA: prodcraft-wk02-replies.mp4 (release gate)

Reviewed 2026-11-01 against FACTS.md, SCRIPT.md, BUILD_LOG.md, `ref/wk02_card.png` and `reply_classifier.py` lines 99–107. The film was not edited.

## Verdict: **FAIL** (do not post as rendered)

The content rules all pass: the code is verbatim, every number is in FACTS, there is no ~95%, no percentages, no PII and no model output. The film is not releasable for three reasons:

1. **Mobile readability.** The payoff line (`auto_reply_or_OOO · 0.99 · €0.00 · no model called`), the reply cards, the code and the required "illustrative replies" label all render at **5–9 pt** on a 390 pt-wide phone, against an 11 pt floor.
2. **The `_STOP_PATTERNS` / `_HOT_PATTERNS` tags never render**, because of a clip bug. The stop and hot cards light up while the only code on screen is the OOO rule, so a muted viewer can read the OOO code as the thing that classified "unsubscribe" and "call".
3. **The ProdCraft mark is a filled silhouette.** It does not match the card's detailed mark.

All fixes are in `src/`. Fix 1 changes the middle section's layout, so the film needs a fresh visual pass after the fixes (not a spot check).

## Method

- Frames are in `/tmp/wk02qa/`:
  - `half/` every 0.5 s (55 frames);
  - `sort/` every 0.1 s across 10.2–11.2, 11.3–12.2 and 12.4–13.3 (31 frames);
  - `tail/` every 0.1 s across 24.7–27.7 (31 frames);
  - `head/` every 0.1 s across 3.3–4.0 (the headline exit);
  - `first.png` (frame 0) and `last.png` (frame 831).
- I read every frame: full-resolution singles where text mattered, and labelled 2×2 sheets (`sheets/`) for the 0.1 s runs and the remaining 0.5 s frames.
- Loop check: frame 831 vs frame 0 mean abs diff is 0.9/255, so the loop is seamless. `poster.png` vs frame 0 differs by about 1.1/255 (encode only).
- Verbatim check: `src/out/code.json` lines with 4 spaces added back are equal to source lines 99–107. I also read the code visually at 9.0, 9.5 and 10.0 s: same tokens, same order.
- Contrast: I sampled the decoded frames myself (2nd-percentile text pixel vs 80th-percentile background):
  - wk 02: 6.8:1
  - footer: 7.3:1
  - gold "02": 5.3:1
  - code string on the gold highlight: 5.2:1 (lowest; the builder measured 5.87)
  - code on the panel: 6.0:1
  - "illustrative replies": 7.7:1
  - result line: 16.4:1
  - dimmed result / card text: 8.4 / 8.6:1
  - credits: 7.6:1
  - F05: 15.4:1

  **Everything is ≥ 4.5:1. PASS.**
- Mobile scale: font px × 390/1080 = effective pt, using sizes from `src/out/drawn_text.json`.

## Checklist

| Check | Result |
|---|---|
| Typos | PASS. None found in any frame. |
| Code verbatim (F21, lines 99–107) | PASS. Byte-identical apart from the permitted 4-space dedent. Line 98 ("~95%") is never shown. |
| Numbers vs FACTS | PASS. 32, 800 (F01/F02/F19), 0.99 and €0.00 (F08/F09/F14), 0.90 (F10), 30–60 (F18). Nothing else. |
| No real names / companies / e-mails / phones | PASS. 7 generic replies. "Monday" is the only proper noun. |
| "illustrative replies" label visible | Present 2.7–17.2 s, but at 15 px = **5.4 pt**, which is illegible on a phone. See D2. |
| No "~95%", no percentages | PASS (drawn-text manifest and every frame). |
| No model output / name / confidence | PASS. The uncaught cards get only "✓ CRM updated". "no model called" is F14 wording. |
| Contrast ≥ 4.5:1 | PASS (see Method). |
| Mobile readability (≥ ~11 pt) | **FAIL.** See D1 and D2. |
| Poster as a still | PASS. The headline is 33.6 pt effective and the 32 envelopes read as "inboxes". Lower quarter (y 880–1200) is empty but acceptable. Carries the logo defect (D4). |
| Motion pacing, sound off | Mostly PASS. Headline 3.6 s, F05 5 s, F15 4.3 s, F19/F18 7 s, 30–60 held 6.4 s. Weak spots: D7 (5 s with the quote and 7 cards competing) and D1 (results too small to read at any speed). |
| Sort overlap (builder's 0.3 s) | Confirmed, about 0.2–0.3 s per sort, text-on-text. See D5. |
| Ghosting / cut text / title-safe | No ghosting; the loop dissolve is clean. Cut-text transients: D6 and D8. Margins ≥ 72 px (inside 90 % title-safe). See the honest gap on LinkedIn's mute badge. |
| Brand match to card | Matches: Newsreader headline (size, place and tracking match the card), JetBrains Mono chrome/code, paper #EEECE7 vs #EFEDE8, gold, header (wordmark + "wk 02"), footer ("ProdCraft · weekly notes" + gold "02"), code-panel tab. **Logo mismatch: D4.** New sans for the cards (D9). |

## Defects

| # | Time | Frame | Severity | Defect | Fix (src terms) |
|---|---|---|---|---|---|
| D1 | 9.9–17.2 s | `half/h_020.png`, `h_024.png`, `h_030.png` | **Major** | The payoff is unreadable on mobile. Result lines are `F.mono(19)` = 6.9 pt, reply cards `F.sans(25)` = 9.0 pt, code `F.mono(24)` = 8.7 pt, `_STOP/_HOT` tags 17 px = 6.1 pt, "CRM updated" 19 px = 6.9 pt. The film's argument (0.99 · €0.00 · no model called) lives in the 6.9 pt line. | In `film.js` card drawing (around lines 191–206):<br>• result and CRM lines → `F.mono(31)` or larger;<br>• card text → `F.sans(34)`;<br>• `ROWH` about 63 → about 96, with matching `lay.pitch`.<br>The ledger will not fit with 7 cards plus the panel. Cut to 5 cards (one OOO, stop, hot, two rest) or split section C into two beats: the code panel alone, then the ledger. For code: give the panel the full frame for its beat at ≥ 30 px, with 2-space re-indent (FACTS allows re-indent to fit). |
| D2 | 2.7–17.2 s | `half/h_010.png` | **Major** | The required "illustrative replies" label is 15 px = 5.4 pt, legible only on desktop. | `F.mono(15)` → ≥ `F.mono(30)` (or `F.text(32)`) at `lay.lab`. Keep it once. |
| D3 | 11.2–17.2 s | `sort/` 11.3–12.1, `half/h_024.png` | **Major** | `_STOP_PATTERNS` / `_HOT_PATTERNS` are never visible. The tag is drawn inside the result's stamp clip `ctx.rect(x+22, y+36, (rw+6)*p, 24)`, which is only as wide as the result text; the right-aligned tag at `x+w-20` is outside it. `drawn_text.json` logs it anyway (pre-clip), so SCRIPT.md rows 26/28 and the eval's drawn-text check are wrong. Meanwhile the panel's gold bar stays on `"class": "auto_reply_or_OOO"` while the stop and hot cards light. | Move `drawText(RULE_TAG…)` after `ctx.restore()` of the stamp clip (still inside the card clip) and give it its own wipe. Size it ≥ 30 px per D1. While a stop or hot card is lit, dim or remove the panel's gold line bar so the OOO line is not read as the cause. Make `drawText` logging respect the clip, or add a pixel probe, so the manifest cannot report invisible text. |
| D4 | whole film, poster | `logo_cmp.png` (card vs film, 4×) | **Major (brand)** | The mark is a solid black silhouette. `LOGO_INK` uses `source-in` with `#16181c` (film.js line 13), which floods all ~27.9k opaque *light* pixels (the interior detail) to ink. The card shows the detailed mark. | Tint by luminance instead of alpha, so only dark pixels become ink and light pixels stay paper. One way: `multiply` the logo onto an ink-coloured layer, or use a pre-tinted asset matching the card. Re-render `poster.png`. |
| D5 | 10.5–10.85, 11.65–11.85, 12.6–12.95 s | `sheets/sort_01.png` (10.6, 10.8), `sort_03.png` (11.7), `sort_04.png` (11.8), `sort_06.png` (12.7, 12.9) | Minor | The sort overlap is real: about 0.2–0.3 s per sort. Caught cards slide over the rest cards. The under-card's text is visibly clipped ("Tell me more" sliced at 10.6) or butts against the moving card's result line (10.8, 11.8, 12.9). It reads as a shuffle at speed, but each sort has 6–9 frames of text-on-text. | In `slot()` (film.js line 118): stagger so the displaced cards move first (start 1/8 beat earlier), so the slot is open before the caught card arrives. Alternatively, fade the displaced cards' text to about 0.3 during their move, or lift the caught card +16 px x with a 1 px shadow so the overlap reads as layering. |
| D6 | 3.65–3.75 s | `half/h_007.png`, `sheets/headexit.png` (3.7) | Minor | The headline exits upward through the header row and touches or overlaps the ProdCraft wordmark and logo for about 3 frames. | Clip the headline's exit at the header's bottom (y ≈ 145) in the `headOut` draw. Same treatment for the F15 exit (D8). |
| D7 | 2.9–8.0 s | `half/h_008.png`, `h_010.png` | Minor | Reading load: the F05 quote (49 chars) arrives while 7 cards (≈ 160 chars) wipe in and the ribbon lights. A muted viewer reads one or the other. The cards stay until 17 s, so nothing is lost, but the quote is the line that is meant to land. | Delay `card0` by 1–2 beats after F05 is fully read (5.5 beats), or start F05 half a beat earlier, before the ribbon. |
| D8 | 17.0 s, 26.0 s | `half/h_034.png`, `h_050.png` | Low | Exit residue: F15 descenders ("g p") peek under the header, and at 25.2–25.4 F19/F18 leave as horizontally sliced glyph fragments. Each lasts 1–3 frames. | Same header-bottom clip as D6. Fine to leave the slice if it is intentional. |
| D9 | 2.7–17.2 s | `half/h_010.png` | Low | Reply cards use Geist sans, a third typeface the card does not have. Text sits top-aligned in each card with an empty lower half until a result arrives. | Accept, or set the cards in Newsreader text (`F.text`), which is on-series. Vertically centre the text until the result line arrives. |
| D10 | 11.0 s | `half/h_022.png` (x≈121, y≈929) | Low | A 1 px vertical sliver appears in the stop card before its result stamps, from the stamp clip starting at width 6 px with `p≈0`. | Start the clip at width `rw*p` (drop the +6 at p=0), or skip drawing while `p < 0.02`. |
| D11 | 0–27.7 s | header and footer | Low (accepted) | Header/footer chrome is 14 px = 5.1 pt, and credits 15 px = 5.4 pt. Same scale as the card (series fidelity, logged as a deviation). Credits are "small" per the directive. | None required. If D1 is reworked, consider 18 px chrome. |

## Honest gaps

- I judged mobile size arithmetically (font px × 0.361) and from 1080-wide frames. I did not watch the film on a phone or in the LinkedIn app, and did not check whether LinkedIn's in-video mute/caption badges cover the bottom-right "02" or the credits.
- Sampling was every 0.5 s outside the four 0.1 s windows, so a 1–2 frame glitch elsewhere (e.g. the ribbon snap at 2.4–2.9 s, the panel entry at 8.3–8.8 s, the knife at 16.8 s) could be missed. The 0.25 s sheets in the build log cover some of this.
- Audio was not reviewed (out of scope). Silent-safe is judged on picture only.
- Contrast was sampled on 4:2:0 decoded frames with a percentile method. The thin 14–15 px mono glyphs will render lighter after LinkedIn re-encoding and phone downscaling than the sampled core stroke.
- I did not re-run `film_eval.py` or the readcheck. Readcheck's "36/36 OK" is a time budget only and says nothing about size. Its drawn-text manifest is unreliable for clipped text (D3).
- Brand comparison is against the single wk 02 card. I did not check `wk01_card.webp` or the house-style `styleframe.png`.
