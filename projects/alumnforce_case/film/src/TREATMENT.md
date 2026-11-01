# Trusted Segments — treatment

Style: **Archive Light Table** (`styles/archive-lighttable/STYLE.md`). English, 1920×1080, 24 fps, about 75 s.
Purpose: cold open of a 20-minute Senior PM case study for a hiring panel at AlumnForce. Every number and quote comes from `FACTS.md` (F01–F23).

Brief defaults (nobody to ask, so chosen and written down):
- No user material: no logo, no member data. The "archive object" is the client's member file, shown as 525 **schematic record cards** (anonymous ID stub, the city field, redaction bars for every personal field). Marked "schematic · IDs only" on screen. Only the London spellings (VERIFICATION.md §2, the source of F04) and member IDs are legible.
- Narrator: Kokoro `bf_emma` (British, calm), speed 0.9. Fallback edge-tts `en-GB-SoniaNeural`.
- Subtitles burned in and exported as `.srt`. No storyboard stop. −14 LUFS.

## 1. Three candidate structures

1. **The count that climbs, then turns** (chosen). A sentence typed into a search box, four empty answer slots. The table shows the file; the loupe finds what breaks the sentence (spellings, duplicates); the answer climbs 2 → 26 → 49; then the loupe reads the dates and the light goes out of most of the table; the 49 sort into three, and the fourth slot fills: 6. Close on the product line. One subject (the sentence), one goal (an honest answer), one turn (the answer was never a count, it is a trust level).
2. **One card, one case.** Follow a single duplicate pair (M0148 / M0502) like a detective story, then generalise. Rejected: it centres a person's row, too close to row-level data, and it needs explaining.
3. **The funnel 525 → 6.** A countdown that subtracts. Rejected: it hides the climb (the naive answer is too low, not too high) and makes the turn an anticlimax.

Opening image: a query strip on dark glass, the caret blinking, the table still off. Ending: the table switches off, six cards keep glowing, the sentence becomes the product line. Score shape: one felt-piano figure that gains subdivisions as the count climbs, a held silence before the dates, glass at the turn, a resolve to major on the split.

## 2. Logline and arc

A one-sentence audience request gives four different answers from the same file; under the loupe the real problem is not the filter but the age of the records.
Setup (sentence, file, defects) → turn (the dates: 68 % untouched; tenure and staleness are the same signal) → ending (the 49 split by trust; 6 usable today; Trusted Segments).

## 3. Benchmark

- *The Thin Blue Line* (Errol Morris): document inserts at macro scale, one line of a record lit at a time. **Learn**: the authority of a still record read slowly; narration that states what the paper says. **Don't take**: its score, its re-enactments, its shots.
- Forensic Architecture's annotated investigations. **Learn**: one claim, one mark, one source per screen; marks in one signal colour. **Don't take**: layouts, typefaces, map graphics.

## 4. Shot list

| # | Shot | Framing / angle | Camera move | Dur | Why |
|---|---|---|---|---|---|
| 1 | Query strip, typing | close, top-down | slow push (zoom 1.9 → 2.1) | ~8 s | hook in the first second: a sentence being typed |
| 2 | Four answer slots appear | close | hold | ~3 s | sets the promise "four answers" |
| 3 | Table switches on, 525 cards | wide | pull back to the whole table (2.1 → 0.42) + slight roll | ~6 s | scale reveal: the file as a physical thing |
| 4 | London card under the loupe | medium → insert | glide + push, loupe lands | ~6 s | "look closer": the city line lights, 8 spellings lift out |
| 5 | 25 duplicates ring up | wide | rise, slow glide | ~4 s | defects are everywhere, not one card |
| 6 | The count climbs 2 → 26 → 49 | wide | slow push in steps | ~11 s | each answer lights its cards; acceleration by subdivision |
| 7 | Near-silence, loupe on a date field | close | push, loupe lands | ~3 s | the turn |
| 8 | Develop front: 68 % of cards go dark | wide | pull back while the front spreads | ~6 s | native move at the peak: the light goes out of stale records |
| 9 | Two records held side by side | medium | hold, then pen stroke "=" | ~6 s | F22 must be read, not heard only |
| 10 | Quoted note F17 | insert | slow lateral track | ~6 s | the human cost, in the record's own words |
| 11 | The table becomes the index | wide | pull back, cards fly into three columns | ~8 s | signature shot: 49 → 1 · 5 · 43 |
| 12 | Table off, six cards glow, product line, title | wide → title | hold, gentle push | ~9 s | ending echoes the opening query strip |

Transitions are the loupe (land, lift) and table glides; no cuts or fades between objects. Moves used: push, pull, glide/pan, roll, loupe landing, lateral track, hold.

## 5. Beat sheet

Final times come from the voice durations (timeline built from `voice/dur.json`, see `timeline.mjs`); `SCRIPT.md` lists the locked time codes. Order:
L1 F01 typed + read · L2 "One sentence. Four answers." · L3 F02 · L4 F04 · L5 F03 · L6 F07 · L7 F08 · L8 F09 · (silence) · L9 "But look at the dates." · L10 F13 · L11 F22 · L12 F17 · (silence) · L13 F11/F21 · L14 F12 · L15 F19 · L16 F23.

## 6. Cue map

72 bpm (0.833 s a beat), 4/4. Line starts snap to the beat grid; each visual hit (loupe landing, count land, front start, index flight, switch-off) sits on a beat of the same grid, checked by `tools/cuecheck.py`.
- A (open, L1–L2): felt piano, single notes on beats 1 and 3, D minor colour, register mid.
- B (table + defects, L3–L5): piano on quarters, a low string pad enters.
- C (climb, L6–L8): piano eighths, register rises a step per answer.
- Silence 1 (~1.6 s) before L9: music cut, hum only.
- D (turn, L9–L12): bowed vibraphone / glass tones, low strings, piano sparse.
- Silence 2 (~1.2 s) before L13.
- E (split, L13–L14): piano resolves to F major, strings swell lightly.
- F (close, L15–L16): one glass tone, piano chord, ring-out.

## 7. Sound design

| Section | Ambience | Foley | Music |
|---|---|---|---|
| Open | room tone | key ticks while typing, soft clicks for slots | A |
| Table on | ballast hum 100 Hz + harmonics, starter clicks | paper sweep for the pull-back | B |
| Loupe / defects | hum | loupe clack with a high ring, label clicks, ticks for rings | B |
| Climb | hum | counter ticks, a click as each number lands | C |
| Turn | hum (only sound in silence 1) | loupe clack is the first sound after the silence; low paper sweep for the front | D |
| Side by side / quote | hum | pen stroke for "=" | D |
| Index | hum | paper whoosh for the flight, three soft landings | E |
| Close | hum stops with the switch-off clunk | switch clunk | F |

## 8. Subtitle and title design

- Subtitles: bottom-centre caption strip, dark plate rgba(14,15,17,0.78), 3 px signal edge on top, IBM Plex Sans 40 px, paper white. Readings stay above the bottom 160 px.
- Readings: dark caption plates, small sans label (30 px) above, mono reading (96–120 px), source line (28 px mono) below: the fact id is not shown, the record wording is.
- Query strip and product line: IBM Plex Mono 44 px on dark glass. Title "Trusted Segments": IBM Plex Serif 76 px.
- Signal colour: orange #FF5A1F, marks and readings only. Minimum text on screen ≈ 28 px; card micro-text is drawn as bars until it reaches 24 px and fades in by 30 px.

## v2 (round 2, after the panel and visual QA)

Same style, same arc, tightened to 61.4 s: the duplicates fold into the "49" line, the quote loses its attribution line, and the ending becomes payoff → thesis → name → end card. The loupe lands on the one real record (F26, M0271 · "Londres (Royaume-Uni)"); every other card is ID-less. After the split, the "6" (F12: "worth contacting today: 1 to send, 5 to confirm.") is the largest element, centred, with the six cards in a row under it; the light switches off; the search box comes back with its four answers filled; the thesis (F24) sits under it; the query gives way to "Trusted Segments"; a 4.5 s end card carries the disclosure and credits.
