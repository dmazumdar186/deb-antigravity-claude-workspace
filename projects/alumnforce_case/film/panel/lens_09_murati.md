# Lens 9 · Mira Murati · product and viewer experience

**Verdict: NOT CLEAR.** The craft is real: the loupe on M0475 (poster, 15.5 s) is a strong signature shot, and the 2 → 26 → 49 climb reads without sound. Two cheap defects stand between this and the room: it misquotes the panel's own sentence, and nobody has planned how it plays over a call.

## High

1. **The film misquotes the brief to the people who wrote it.** S01b (2.78–6.21 s) reads "Graduates working in finance, in London, for more than three years." The brief, the search box on screen and slide 3 all have no commas. The burned-in caption and the typed box disagree in the same frame (frame at 3.0 s), and the commas change the parse, which is the very ambiguity the talk is about. *Fix:* drop the commas in the SRT and the burned cue, and narrate it without pauses (or leave the audio and fix only the text).
2. **There is no playback plan for a video call.** Neither SPEAKER_GUIDE.md nor presentation.html mentions the film. Zoom and Teams screen-share re-encode at a low frame rate. A 2.4 Mbps CRF 26 file with grain will turn to mush on the slow pans across ~500 cards (frames at 29 s and 36 s: 2–3 px bars, which alias once downscaled to 720p). The audio is lost unless "share sound" is ticked. *Fix:* add a 3-line block to SPEAKER_GUIDE: Zoom "Optimize for video clip" + "Share sound" / Teams "Include computer sound", full screen at 100 %, then cut straight to slide 1. Make a no-grain encode for sharing, and keep a link to the mp4 as the fallback.

## Medium

3. **The payoff "6" is the smallest number in its own scene.** At 61.5 s, 1 · 5 · 43 sit at ~60 px, while "6 can be e-mailed today" is a bottom-left plate with the 6 at about the same size. The eye goes to the 43 grid. "6" holds as a hero for ~3.4 s (60.42–63.83). On the end card it is one slot of four, set apart only by colour. *Fix:* after the bracket, scale the 6 to the size of the 49 plate (110 px), centred, and hold it for 1 beat before the switch-off.
4. **Captions are too long for a phone or a shrunken video tile.** Every cue is one line: 78 chars (S11), 67 (S01b), 58 (S10). In a 360 px-wide Teams tile they render at ~8 px. *Fix:* split into 2 lines of ≤ 42 chars, broken at the clause boundary. S01b is also 19.5 cps, so give it the 0.4 s of slack before S02.
5. **The hand-off to slide 1 is a change of brand.** The film is charcoal, IBM Plex and orange #FF5A1F. Slide 1 is navy #0f3b7a, Inter and blue/green. The words match exactly (title + the three product lines), which is good. The jump in look, though, feels like two authors. *Fix:* end the film on a 12-frame fade to #0f3b7a, or recolour the last end card (71.7–76.2 s) as slide 1 so the cut is invisible.

## Low

6. **Freeze at 55.67–59.96 s (4.3 s) while the narration continues.** Over a share it reads as a stalled stream. *Fix:* a 2 % slow push-in on the index columns.
7. **First 5 s.** There is a hook only for this audience: dark screen, typing "Graduat…" (0.5 s). Tension arrives at 6.25 s with "Four answers". That works live. Muted or cold, it does not. *Fix (optional):* show the four "?" slots from 0.4 s.
8. **The end card has no name or deck pointer.** That is fine live, because the talk follows. If the film is ever sent alone, add "Debanjan Mazumdar · deck.pdf".

## Derivatives

- **Worth it:** `src/poster.jpg` as the email thumbnail linking to the mp4 (already exists; crop to 1200×630).
- **Not worth it this week:** a 15 s teaser, 1080×1350 / 1080×1920 LinkedIn cuts, a GIF (a dense grid makes a heavy GIF that dithers badly). These are post-interview assets, not interview assets.

## Honest gaps

- I watched seven stills. I did not watch in motion at 1×, so shimmer is inferred from bar width, not observed.
- I did not test an actual Zoom/Teams share, and did not listen to the mix.
- BUILD_LOG has no "known leftovers" section. I worked from "What failed" and "Deviations" instead.
