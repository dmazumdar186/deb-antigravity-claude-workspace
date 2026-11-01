# Visual QA, round 2: trusted-segments.mp4 (v2)

Reviewed on 2026-11-01. I checked `trusted-segments.mp4` (61.375 s, burned captions) and `trusted-segments_clean.mp4` against `VISUAL_QA.md` (round 1), the v2 section of `BUILD_LOG.md`, `FACTS.md` (including its hard rules), `SCRIPT.md`, `trusted-segments_clean.captions.srt`, `src/out/drawn_text.json` and Archive Light Table `STYLE.md` §3–5 and §9.

**Frames I read:**
- 61 frames from each master, one per second (`/tmp/vqa2/b1/`, `/tmp/vqa2/c1/`, tiled in `/tmp/vqa2/sheets/`).
- Frames every 0.125 s across each step change on the reading plate: 8.25, 11.30, 12.67, 14.58, 16.25, 19.22, 24.06, 27.48 and 31.14 s (±0.5 s each, `/tmp/vqa2/fine/`).
- Frames every 0.125 s across the "6" payoff (47.0–51.4 s, `/tmp/vqa2/pay/`) and the end card (56.5–61.4 s, `/tmp/vqa2/end/`).
- Extra bursts over the push to the note (35.0–36.75 s), the note fade (41.25–42.5 s), the card flight (42.5–44.0 s) and the title wipe (53.75–54.75 s), in `/tmp/vqa2/x/`.
- Full-resolution stills for pixel sampling (`/tmp/vqa2/full/`). Contrast script: `/tmp/vqa2_tools/contrast.py`. Contact sheets: `/tmp/vqa2/fsheets/`.

Frame names `f<c>_NN` are at time c − 0.5 + (NN−1)·0.125 s. `p_NN` is at 47.0 + (NN−1)·0.125 s, and `e_NN` is at 56.5 + (NN−1)·0.125 s.

## Verdict: PASS-WITH-FIXES

The high-severity defect from round 1 is gone. Labels and values now switch on the same frame, and no label ever sits over another step's value. All six medium and low round-1 items I could check in pixels are closed except one (orange contrast), which is much better but still under 4.5:1 on the left-hand plates.

Other checks:
- The burned captions quote F01 exactly, without commas.
- F24 is verbatim.
- The "6" dominates for about 2.7 s.
- The end card is 36 px for its whole hold, with the AI disclosure and every credit FACTS requires, including the CC BY 3.0 piano credit and its URL.
- No member ID appears on any background card. The only ID drawn is M0271 (`drawn_text.json`: one ID entry, 11.125–15.708 s).

Two new medium defects should be fixed before the panel sees the film:
- Invented city names from neighbouring cards become readable inside the loupe while it lands and lifts.
- The thesis fades in on top of the six cards and the fading payoff.

Both are short and local, and neither changes a number.

## Round-1 closure table

| R1 # | Item | Status | Evidence |
|---|---|---|---|
| 1 (high) | Label over the previous step's value | **closed** | `fine/f19.22_04` (19.125 s) shows "Naive filter · 2"; `_05` (19.25 s) shows "Normalised · 26", so label and value change on the same frame. Same at 24.06 s (`f24.06_04` → `_05`, "Normalised · 26" → "Full logic · 49"). The first step shows its label with no value (`f14.58_06–08`, `f16.25_01–04`), and the value lands at 16.25 s. No frame pairs a label with another step's value. |
| 2 (med) | Orange values ≈ 2.5:1 | **open (largely fixed)** | Plates are now nearly opaque. Values measure **5.2–5.7:1** on the right-hand plates: 2, 26, 49, 5, 43, and the 6 slot. The left-hand plates sit under the frame's light falloff, which dims both the orange and the labels by about 10 %. There, 525 measures 4.26–4.37, "8 spellings" 4.20–4.28, "68 %" 4.41–4.80, "1" 4.25–4.53 and the payoff "6" 4.52–4.67 (bg median → p95). All are large text, so they pass 3:1, but several miss the 4.5:1 target. See N3. |
| 3 (med) | Note ghosting over darkening cards | **closed** | In `x/note_03` (41.5 s) the ink fades first. `note_04` (41.625 s) is blank paper, with no text left on the cards. The table dims after the note is gone (`note_05–08`). |
| 4 (med) | Highlighted cards hidden under the plate | **closed** | The 2 outlined cards (`b1/b16`, `b17`) and the 26 and 49 outlines plus the 25 rings (`b19`–`b24`) all sit outside the plate rectangle. None sits under the caption plate. |
| 5 (med) | SRT auto-loads over burned captions | **closed for exact-name players; one residual risk** | The file is renamed `trusted-segments_clean.captions.srt`. VLC's default fuzzy subtitle matching may still auto-load it for `trusted-segments.mp4`, because the name starts with that basename. I did not test this (see Honest gaps). Neither MP4 has an embedded subtitle stream (ffprobe: video + audio only). |
| 6 (low) | Push too fast; three layers overlap | **closed** | In `x/push_01–14` (35.0–36.6 s) the pair plate and caption are gone by about 35.4 s. The push runs about 1.2 s, the note paper appears at 35.75 s and the ink at 35.875 s. At most two layers overlap. |
| 7 (low) | Burned quote duplicates the on-screen note | **closed** | `b1/b36–b41` show no burned caption during the note. |
| 8 (low) | Secondary line 4.3:1; rings through plates | **closed** | Secondary lines measure 7.2–8.5:1 ("rows matching the sentence" 8.1, "for 500 members" 7.2, "of 500 members · ref." 8.5). The "IDs M0501–M0525" line no longer exists. Redaction bars are only faintly visible through the plates (`f16.25_*`). |
| 9 (low) | Tag outside title-safe | **closed** | The tag is now bottom right. Its plate ends at x ≈ 1824 and its text is inside (`fsheets/safe.png`). |
| 10 (low) | Flying card covers the "To reactivate" header | **closed** | `x/fly_01–06` (42.5–43.75 s): the headers are drawn above the flying cards. |
| 11 (low) | "=" on a pasted box | **closed** | `b1/b34`: the "=" sits inside the single pair plate. |
| 12 (low) | Asymmetric bracket | **closed (removed)** | The bracket is replaced by the payoff (`pay/*`). |
| 13 (low) | Query ghosts behind the title | **closed** | `x/title_04` (54.125 s): the query is faint. `title_05` (54.25 s): the box is empty. `title_06–07`: the title wipes in. |
| 14 (low) | Dates card had member-style ID; loupe touched a plate | **closed, with a new side effect** | The card reads "example" with no ID (`b1/b25`, `b26`). The loupe rim clears the 49 plate. Its neighbours' cities now leak into view, see N1. |
| 15 (low) | Wide "68 %" gap | **closed** | Set in the sans face (`b1/b28`). |

## Checks requested in the brief

| Check | Result |
|---|---|
| No label over another step's value | Pass (R1 #1 above). |
| No member ID on background cards; only M0271 + "Londres (Royaume-Uni)" in the close-up; "Schematic" tag visible whenever card text is readable | IDs: pass. The manifest has one ID entry, M0271, and the dates card reads "example". Close-up: **fail, minor**. Neighbouring cards' invented cities appear inside the loupe (N1). Tag: pass. It is on screen from 6.98 s to about 50.4 s, which covers both loupe passes (`b1/b07`–`b49`). |
| Orange contrast ≥ 4.5:1 | Partial: right-hand plates 5.2–5.7:1, left-hand plates 4.2–4.8:1 (N3). |
| "6" dominant ≥ 2.5 s | Pass. Full strength from 47.75 s (`p_07`) to 50.4 s (`p_28`), about 2.7 s. It is 330 px, the largest element on screen, and centred. The fade starts at 50.5 s. |
| F24 verbatim | Pass. "The administrator’s problem is not building the list. / It is believing it." (`b1/b51`, `b56`). The apostrophe is typographic; the wording is identical. |
| End card ≥ 28 px for its whole duration, with disclosure and credits | Pass. All lines are 36 px (`drawn_text.json`), with the title larger. It holds at full strength from 57.125 to 61.375 s (`e_06`–`e_39`); 56.875–57.0 s is a dissolve (N6). Lines on screen: "Made in code by an AI agent with lemo-opuscar (MIT)", "Synthetic voice: Kokoro (Apache 2.0)", "Piano: Salamander Grand Piano V3 by Alexander Holm", "Licence CC BY 3.0", "https://creativecommons.org/licenses/by/3.0/", "Strings and mallets: CC0, Versilian Studios", "Fonts: IBM Plex (OFL)", "Record cards are schematic · no member data". Credit text measures about 11:1. |
| Captions quote F01 exactly, no commas | Pass. "“Graduates working in finance in London / for more than three years”" (`b1/b02`–`b05`), and the same in the SRT. |
| Typos, clipping, title-safe | No typos found in any drawn string or burned cue. Nothing important is clipped; the only partial words are wipe and type-on frames by design (`b1/b54` "Trusted S"). Text sits inside the 5 % margins. The tops of the search box and title box are at y ≥ 66. Burned captions sit about y 940–1024. The 2/26/49 plate background runs to x ≈ 1840, 16 px past the safe line, but its text ends well inside (`fsheets/safe.png`). This is cosmetic only. |
| Clean master: no burned captions, no grain, nothing relied on captions | No captions in any of the 61 frames (`sheets/c1_*`). No grain shimmer: frame-to-frame MAD on static dark areas is 0.2–0.8/255, the same level as the burned file, and the end-card hold has a frame-to-frame difference of 0. It relies on captions once: "25 duplicates" (F03) is never written on screen (N4). |

## New defects

| # | Time code | Frame | Sev. | What's wrong | Fix |
|---|---|---|---|---|---|
| N1 | 11.1–15.9 s (M0271 loupe) and 25.0–27.5 s (dates loupe), most visible while landing and lifting (11.2, 15.0, 27.0–27.2 s) | `fine/f11.30_04` ("…don" under M0271), `b1/b15` ("…ndon", "L"), `fine/f27.48_03–04` and `b1/b27` ("…pore", "Milan", "Na…") | **medium** | `film.js:74–75` gives background cards invented cities (Singapore, Nantes, Milan, "London, UK"…). Inside the loupe these render at 34–42 px (`drawn_text.json`: "London, UK", "London", "Singapore", "Nantes", "Milan"), so they become readable next to the real record and the example card. The brief allows only M0271 + "Londres (Royaume-Uni)" in the close-up. A city printed beside M0271 can also be read as part of its record. | In `lodText` (`film.js:149`), draw the city as a redaction bar (or `cityA = 0`) for every card except `T1` and `T2`. Alternatively, clip the lens interior to the target card's rectangle while it lands and lifts. |
| N2 | 50.5–51.1 s | `pay/p_29–p_33` | **medium** | The thesis fades in while the "6 / worth contacting today: / 1 to send, 5 to confirm." block and the six glowing cards are still fading out. "It is believing it." crosses the card row (`p_30`, `p_31`). This is the same half-faded text over objects that round 1 flagged for the note. | Start the thesis fade at about 51.0 s, after the payoff block and cards reach 0. Or fade the payoff out over 0.25 s first, then bring the thesis in. |
| N3 | 8.25–11.3 s (525), 12.7–15.9 s (8 spellings), 27.5–31.4 s (68 %), 44–47 s ("1"), 47.75–50.4 s (6) | `full/b_9.5`, `b_14.0`, `b_29.0`, `b_46.5`, `b_49.0` | low | Values on plates at the left of the frame, and the payoff "6", render about 10 % darker than the same tint at the right. They measure 4.2–4.8:1 against the 4.5:1 target. Measured glyph colour is #D1683C on the left and #ED7542 on the right, not the #FF7A45 in the source; labels on the same plates dim the same way. | Draw the plates and their text after the frame's light falloff / vignette pass so they are not darkened. Or lift the value tint to about #FF8A55 so the darkest case still clears 4.5:1. |
| N4 | 20.6–25.5 s | `b1/b21–b24`, `c1/c21–c23` | low | The 25 duplicate rings appear with no on-screen number or legend. On the clean master, F03 ("25 duplicates") exists only in the voice. From 20.6 to 24.06 s the rings also sit under the "Normalised · 26" plate, before the step they belong to. | Add a source line or small legend, "○ 25 duplicates", tied to the 49 step. Or start the rings at 24.06 s together with the "Full logic" label. |
| N5 | 47.0–47.5 s | `b1/b47`, `pay/p_03–p_05` | low | The index columns fade over about 0.4 s while the six cards fly out. Ghost text ("Current → send 1", "43") sits at roughly 25 % behind the moving cards. | Fade the column text out before the cards start to move, or lift the columns out with the cards. |
| N6 | 56.875–57.0 s | `end/e_04`, `e_05` | low | The end card dissolves in over the search panel and thesis, so two frames show credits overlapping the "2 26 49 6" slots and the thesis. | Fade the closing frame to the dark ground first (about 0.2 s), then fade the card in, or hard-cut. |
| N7 | 44.2–47.3 s (burned C15), voice L13 | `b1/b44–b46` | low | The caption and voice say "43 to win back" while the column and F25 say "reactivate". This is a small wording mismatch on the screen's core split. | Caption and voice: "43 to reactivate". If "win back" stays for the ear, keep it out of the caption. |
| N8 | delivery | — | low | VLC's default fuzzy subtitle matching may auto-load `trusted-segments_clean.captions.srt` for `trusted-segments.mp4`, because its name starts with that basename. That would give double captions on the burned master (residual of R1 #5). Not verified. | Rename it so it does not start with `trusted-segments` (for example `captions_for_clean_master.srt`), or move it into a subfolder. |

## Honest gaps

- I read sampled frames: 1 s intervals for both masters and 0.125 s bursts at every listed transition, not all 1,473 frames. A one-frame flash between samples could be missed. For text visibility between samples I relied on `drawn_text.json`, which is where the N1 cities showed up.
- Contrast comes from pixel sampling of the encoded burned master (CRF 26) and the clean master (CRF 23), not the source canvas, so treat the ratios as ±0.2. I did not test on a projector.
- I could not measure grain directly. The burned master's grain (strength 1) is below what I can separate from encoder noise and slow camera drift, and both masters show 0.2–0.8/255 frame-to-frame change on static dark areas. "No shimmer on the clean master" therefore means nothing visible and nothing measurably different from the burned master.
- I did not test VLC or IINA subtitle auto-loading (N8 is inferred from VLC's documented fuzzy-match behaviour).
- I did not review audio or lip-to-caption sync, apart from caption cue times against `SCRIPT.md`. I did not re-verify the eight London spellings against `VERIFICATION.md`; I checked them only against `SCRIPT.md` and the F04 count.
- Glyph sizes come from `drawn_text.json` (the builder's own manifest) plus visual estimates, not an independent per-glyph measurement.
