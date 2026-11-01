# Visual QA round 2 (release gate): prodcraft-wk02-replies.mp4 v2

Reviewed 2026-11-01 against `VISUAL_QA.md` (round 1), the v2 section of `BUILD_LOG.md`, `FACTS.md`, `SCRIPT.md`, `src/out/drawn_text.json`, `ref/wk02_card.png`, `v1/`, and `reply_classifier.py` lines 99–107. I did not edit the film.

## Verdict: **PASS-WITH-FIXES**

All eleven round-1 defects are closed, and none regressed. The content rules all pass:
- the code is verbatim;
- no 0.90 appears, and no "sequence stopped";
- no model output is shown;
- every rule that fires is named on its own card;
- the logo now matches the card's detailed mark;
- every text ≥ 4.5:1 contrast;
- no card-on-card overlap.

**One fix is required before posting (N1):** the code lines are 30 px, which is **10.8 pt** on a phone. That is under the 11 pt floor. It is a one-line fix that keeps the same line width. The alternative is for the coordinator to accept it explicitly; the argument for that is in N1.

N2–N5 are low-severity polish and do not block release.

## Method

- **Frames**, all in `/tmp/wk02qa2/`. I read every one, as labelled 2×2 sheets in `sheets/` plus full-resolution singles where text or size mattered:
  - `half/`: every 0.5 s, 56 frames.
  - `head/`: 0–1.0 s every 0.1 s.
  - `sort/`: 8.6–12.6 s and 13.2–14.2 s every 0.1 s, covering all three sorts, the heading flip, panel exit and routing.
  - `extra/`: 2.2–3.6 s (quote and pour), 7.6–8.6 s (panel entry) and 17.2–18.4 s (knife and reframe), every 0.1 s.
  - `tail/`: 24.7–27.73 s every 0.1 s.
  - `seam/`: frames 0, 1, 2, 829, 830 and 831.
- **Header band scan.** I decoded all 832 frames for y 88–147. Only frames 111–112 (3.70–3.73 s) and 361–362 (12.03–12.07 s) change there. I read both pairs (`crop/hdr_sheet.png`): the exits are clipped at about y 145, under the wordmark, and never touch it.
- **Loop seam.** Frame 831 vs frame 0 has a mean absolute difference of 0.84/255. The steps just before it are 830→831 = 0.63 and 829→830 = 0.60, so the seam is one more step of the closing headline fade-in and credits fade-out (headline ink 31 → 10). **Seamless.**
- **Motion onset.** Envelope 2 starts filling gold at **0.20 s (frame 6)** and is full at 0.30 s. More envelopes follow every 0.25 s. This **passes** the 0.3 s requirement.
- **Verbatim check.** In `src/out/code.json`, `lines` with 4 spaces added back equals source lines 99–107 exactly. `shown`, stripped, equals the source stripped. I also read the code in frames 8.6–12.6 s: same tokens, same order.
- **Contrast.** I sampled the decoded frames myself: text is the 2nd-percentile pixel, background the 80th. The blue code string is sampled from the blue pixels only.
- **Size.** Cap or ascender heights were measured in pixels from ink extents on full-resolution frames. Effective pt = font px × 390/1080.

## 1. Round-1 defects: closure table

| # | Round-1 defect | Status | Evidence (frame) |
|---|---|---|---|
| D1 | Payoff, cards and code at 5–9 pt | **Closed**, except the code at 10.8 pt (see N1) | `half/f_0450.png` (15.0 s). Measured: cards 32 px (cap 21), results, tags and CRM 31 px (cap 22–23), code 30 px. Table in §2. |
| D2 | "illustrative replies" at 5.4 pt | **Closed** | `extra/f_0093.png` (3.1 s), `half/f_0450.png`. 31 px = 11.2 pt (ascender 22–24 px). Shown once, 3.03–17.47 s. |
| D3 | `_STOP/_HOT_PATTERNS` tags never rendered; OOO code highlighted while stop and hot fired | **Closed** | `sort/f_0327.png` (10.9 s, `_STOP_PATTERNS`), `sort/f_0363.png` (12.1 s, `_HOT_PATTERNS`). The gold bar is on line 99 at 8.6–8.7 s (`sort/f_0258`, `f_0261`), then on line 102 at 8.8–9.8 s. It is gone from 9.9 s (`sort/f_0297`) when the stop card lights. |
| D4 | Logo was a filled silhouette | **Closed** | `crop/logo_cmp.png` (card / v1 / v2 at 6×). v2 shows the compass, box and interior hatching. Mean absolute difference vs the card's logo region: v1 27.5 → v2 14.3. Small residual noted under N5. |
| D5 | Sort overlap, text-on-text | **Closed** | 0.1 s through every sort (`sheets/sort_00`–`sort_12`). A caught card collapses in place (9.0, 10.4, 11.6 s), the column closes, and the card re-opens at the top. No frame has one card over another. |
| D6 | Headline exit crossed the header | **Closed** | Frames 111–112: the headline is clipped at y ≈ 145, below the wordmark (`crop/hdr_sheet.png`). |
| D7 | F05 quote competed with 7 cards | **Closed** | F05 is complete at 2.5 s. The label arrives at 3.03 s and the first card at 3.3 s. Five short cards settle by 4.6 s, then the quote holds alone with the cards to 7.5 s. (The envelope pour, 2.5–2.9 s, overlaps the quote's first 0.4 s. Acceptable.) |
| D8 | F15 and F19 exit residue under the header | **Closed** | `extra/f_0525.png` (17.5 s) and `tail/f_0756.png` (25.2 s): the slices sit below y 145 and are 1–2-frame clip wipes, by design. |
| D9 | Third typeface; top-aligned card text | **Closed** | Geist is gone. Cards are set in Newsreader text and are single-line cards that grow when a result stamps. |
| D10 | 1 px sliver before the stamp | **Closed** | The 1-frame glyph edge at 9.4 s and 10.7 s (`crop/tagstart.png`) is the tag's right-to-left wipe starting, not the old empty-clip sliver. |
| D11 | Chrome at card scale (accepted) | **Accepted, unchanged** | Header and footer are 14 px = 5.1 pt, allowed at card size. Credits went from 15 px to 18 px = 6.5 pt ("small" per directive). |

**Regressions: none found.**

## 2. Legibility (effective pt at 390/1080 = 0.361)

| Text class | Font px (manifest) | Measured on frame (px) | Effective pt | ≥ 11 pt? |
|---|---|---|---|---|
| Poster headline | 93 | digit "3": 69 | 33.6 | ✓ |
| Reframe (F19) | 84 | cap "T" + ascender: 63 | 30.3 | ✓ |
| 30–60 | 250 | 185 | 90.3 | ✓ |
| "Rules first." | 64 | cap + ascender: 49 | 23.1 | ✓ |
| Quote (F05, italic) | 46 | ascender 34 / x 22 | 16.6 | ✓ |
| F18 lines | 44 | ascender 31 / x 21 | 15.9 | ✓ |
| "It was" | 40 | cap "I": 27 | 14.4 | ✓ |
| Limits heading | 34 | cap "R": 25 | 12.3 | ✓ |
| Reply cards; group label (italic) | 32 | cap "I": 21; italic x 15 | 11.6 | ✓ |
| Results, pattern tags, "CRM updated" | 31 | cap "C"/"O"/"0": 22–23 | 11.2 | ✓ |
| "illustrative replies"; code tab | 31 | ascender 22–24 / x 17 | 11.2 | ✓ |
| **Code lines** | **30** | cap "O": 22–23 | **10.8** | **✗ by 0.2 pt (N1)** |
| Wordmark | 26.4 | cap "P": 18 | 9.5 | chrome, allowed |
| "wk 02", footer, gold "02" | 14 | 10 | 5.1 | chrome, allowed |
| End credits | 18 | cap "M": 14 | 6.5 | small by design (D11) |

The measured heights match the manifest sizes:
- Newsreader caps measure 0.66 em.
- JetBrains Mono caps measure 0.72–0.74 em.

So the manifest does not under-report any size.

## 3. Drawn text vs screen

**Every logged string was seen on screen inside its logged window.** Spot timings:
- `_OOO_PATTERNS` 9.37 s
- `_STOP_PATTERNS` 10.67 s
- `_HOT_PATTERNS` 11.87 s
- heading 2 at 12.23 s
- group label 13.43 s
- CRM 13.77 s
- reframe 17.70 s
- credits 21.97 s

**Nothing readable on screen is missing from the log, with one exception:** the **✓** before "CRM updated". It is drawn as a path by `check()` in `film.js`, so neither the manifest nor SCRIPT row 30 has it (N4).

Two manifest quirks, neither visible on screen:
- Whitespace-only indent runs are logged.
- `frames` counts draw calls, not frames: the indent run `"   "` shows 809 for a 5.4 s window, and `": "` shows 316.

## 4. Highlight and label vs the rule that fired

| Sort | Card | Panel highlight | Card label |
|---|---|---|---|
| OOO (8.6–9.8 s) | "I'm out of the office until Monday." | Line 99, then line 102 | `_OOO_PATTERNS` · `auto_reply_or_OOO · 0.99 (set by the rule)` / `€0.00 · no model called` |
| Stop (9.9–11.0 s) | "Please unsubscribe me." | None (removed) | `_STOP_PATTERNS` · `negative · stop rule · 0.99 · €0.00` |
| Hot (11.1–12.2 s) | "Can we jump on a call next week?" | None | `_HOT_PATTERNS` · `hot · meeting request · to a person` |
| Routed (13.4 s →) | "Not interested, thanks." and "What does pricing look like?" | Panel gone | "to the right person, with context" · one "✓ CRM updated" |

**All four match.** I checked each card against `_STOP_PATTERNS` and `_HOT_PATTERNS` in the classifier:
- "Not interested, thanks." matches no stop pattern, so routing it is correct.
- "Can we jump on a call" matches `\bcan we (?:jump on|hop on|do) a call\b`.

## 5. Logo

**Matches the card's mark.** The interior detail is present and placed at the card's position (`crop/logo_cmp.png`). The residual difference: v2's arrow and pencil are a little darker and crisper than on the card, where they are softer and greyer. That is only visible at 6× (N5).

## 6. Code and tab

- **Code:** verbatim to lines 99–107, with a 1-space-per-level re-indent, which FACTS allows. Line 98 (`~95%`) is never shown.
- **Tab:** reads exactly **"from my own build · same rules-first pattern · verbatim"**. At rest it fits inside the panel: text ends at x ≈ 1010, the panel edge is at 1035.

## 7. Banned content

- **0.90:** absent in every frame I read and in `drawn_text.json`. The only hits are SCRIPT staging notes and `content.json` notes, which are not on screen.
- **"sequence stopped":** absent on screen and in the manifest.
- **Model output:** none. The routed cards show no class, model or confidence. "no model called" is F14 wording.

## 8. Fresh pass

- **Typos:** none. I read every string listed in §3. The apostrophe in "I'm" is curly. The en dash in "30–60" is correct.
- **Overlaps:** no card-on-card. Two transient layering moments (N2, N3).
- **Clipping:** only intended wipe and exit slices, 1–2 frames each. No resting text is clipped.
- **Ghosting:** none. The 27.4–27.73 s headline fade-in and credits fade-out are the loop dissolve, and they are clean.
- **Contrast:** all PASS ≥ 4.5:1, sampled myself:

  | Text | Contrast |
  |---|---|
  | Headline | 15.4 |
  | "wk 02" | 6.7 |
  | Gold "02" | 5.3 |
  | Footer | 7.5 |
  | Tab | 8.0 |
  | Blue code string on gold highlight (lowest) | 5.3 |
  | Code on panel | 13.5 |
  | `_OOO_PATTERNS` gold tag | 6.1 (core 5.8) |
  | Result lines | 8.5 |
  | Card text | 8.5–16.3 |
  | Group label | 16.4 |
  | "CRM updated" | 15.4 |
  | Credits | 7.6 |
  | F18 / 30–60 | 15.3 |

- **Title-safe** (90 % = x 54–1026, y 67–1283): dark ink spans x 66–1010 and y 98–1249 at the widest moment (12.5 s, code panel), so all text is inside. Only the panel's fill and border (x 44–1035) reach the action-safe band, and that is decoration.
- **Muted phone viewer: followable.** The film reads in order:
  1. The question, with 32 inboxes lighting up.
  2. Replies pour into a ribbon.
  3. "the bottleneck … reading".
  4. Five labelled illustrative replies.
  5. "Rules first." and the real code.
  6. Each rule catches one reply and names itself.
  7. "Rules catch the obvious. Anything else goes to a person."
  8. The rest are routed, with one "✓ CRM updated".
  9. The 30–60 reframe.

  All results are on screen together during a 3.3 s hold (13.8–17.1 s), so a slower reader can catch up.

## New defects

| # | Time | Frame | Severity | Defect | Fix |
|---|---|---|---|---|---|
| N1 | 7.9–13.3 s | `sort/f_0375.png` | **Minor (required, or accept explicitly)** | Code lines are `30 px` = **10.8 pt**, under the 11 pt floor. For context: their cap height (22 px → 7.9 pt on the phone) is larger than the reply cards' (21 px → 7.6 pt), which pass at 11.6 pt. So perceptually the code is no smaller than text that passes, but it misses the stated rule. | Set code to `31 px` with `letterSpacing -0.6 px`. JetBrains Mono advance: 31 × 0.6 − 0.6 = 18.0 px per char, the same as 30 px now. The 53-char line stays 954 px and the panel layout is unchanged. Re-run `tools/code.py` and the readcheck. |
| N2 | 7.9–8.15 s | `extra/f_0240.png` (8.0), `extra/f_0243.png` (8.1) | Low | The code panel slides in over the card column before the column has moved down. It occludes "I'm out of the office until Monday." and slices "illustrative replies" through its middle for about 7 frames. The panel is opaque (layering, not ghosting), but it is the busiest moment. | Start the column's move-down half a beat before `K.panel`, so the panel lands in empty space. Alternatively, drop the panel in from the top, behind the heading. |
| N3 | 17.2–17.35 s | `extra/f_0516.png`, `f_0519.png` | Low | The exit knife draws a 2 px ink line through the vertical middle of every card and through "to the right person … ✓ CRM updated". For about 5 frames the results read as struck through, as if the claims were being cancelled. | Draw the knife on the card's bottom edge (`r.y + r.h`, `y + GROUP_H`) instead of `h/2`, or as a paper-coloured wipe. |
| N4 | 13.77–17.43 s | `half/f_0450.png` | Low (documentation) | The ✓ is drawn by `check()` and is not in `drawn_text.json` or SCRIPT row 30. The manifest's `frames` field counts draw calls, not frames. | Log the tick (for example, push "✓ CRM updated" as one entry) and make `frames` a count of distinct frames, or rename it `draws`. |
| N5 | whole film | `crop/logo_cmp.png` | Low (cosmetic) | Compared with the card, the logo's arrow and pencil are a little too dark and crisp. Only visible at 6×. | Optional: lift the upper level to about 0.65 for the light strokes. No action needed at phone size. |
| N6 | 9.9–12.3 s | `sort/f_0300.png` | Info | During the stop and hot sorts the panel still shows only the OOO rule, unhighlighted. The rule is named only by the 11.2 pt card tag. This is honest and nothing on screen claims otherwise. | Optional: dim the panel to about 60 % while stop and hot fire, so the tag is the only rule cue. |

## Honest gaps

- I judged size by arithmetic and from 1080-wide frames (plus 2×2 sheets at half scale). I did not watch on a phone or in the LinkedIn app, and did not check whether LinkedIn's mute or caption badges cover the bottom-right "02" or the credits.
- Sampling was 0.5 s outside the 0.1 s windows. The 3.6–7.6 s card build-in and the 18.4–24.7 s hold were seen only at 0.5 s, apart from the every-frame header-band scan, so a 1–2-frame glitch there could be missed.
- Contrast was sampled on 4:2:0 decoded frames with a percentile method. Thin mono strokes will lighten after LinkedIn re-encoding and phone downscaling.
- I could not read the fonts' OS/2 cap heights (no fontTools). The ratios above are measured from the rendered frames.
- Audio was not reviewed. I did not re-run `film_eval.py` or the readcheck.
- Brand comparison is against `ref/wk02_card.png` only.
- FACTS.md still has no `Signed off:` line. The film stays a draft until the operator has watched it.
