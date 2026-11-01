# ProdCraft Notes — Style Prompt (house style, based on swiss-motion)

> The ProdCraft weekly-notes card in motion: warm paper, a large Newsreader headline, verbatim code in a pale panel, and one gold signal that marks what fired. Every move snaps on the beat. Nothing bounces.
> Base: lemo-opuscar `styles/swiss-motion` (bebbbe1). From `styles/living-screencast` it borrows only how code is shown: real code, redrawn verbatim, never a screenshot. Grammar only; no demo story, shot or melody is reused.
> Reference build (wk 02, v2): `deliverables/linkedin_posts/prodcraft_wk02_reply_triage/src/`. Tokens live in `house.js` (in this folder and in the reference build). Each week's content goes in `content.json`.

## 1. Essence, and what it is not

- **A weekly note that moves.** Each film replaces one static card of the "ProdCraft · weekly notes" LinkedIn series and must read as part of it: same header, footer, paper and headline face.
- **Frame 0 is the card.** LinkedIn shows frame 0 before play, so it is a finished poster: header, footer, and the card's headline at the card's size and position. **Visible motion starts by 0.3 s** (wk 02: the first envelope fills gold at 0.13–0.27 s). A frozen opening reads as a static card and gets scrolled past.
- **Silent-safe and phone-legible.** Most viewers autoplay muted on a ~390 pt-wide phone. Everything meant to be read is ≥ 30 px at 1080 wide (≈ 11 pt). Only the series chrome and the end credits stay at card scale. There is no voice.
- **One signal: gold.** It marks what fired: the code line, the rule's pattern name, the caught card. Everything else is ink on paper.
- **Facts only, scoped honestly.** Every number and quote comes from the week's `FACTS.md`. Code shown from the operator's own repo is labelled as such ("from my own build · same rules-first pattern · verbatim"). A constant set in code is labelled as one ("0.99 (set by the rule)"). No count-ups, and nothing implies the rules are infallible.

It is not a keynote (no gradients, glow or device mock-ups), not kinetic type (words never fly, spin or bounce), not a screen recording (code is redrawn, never captured), and not a brand sting (no logo reveal before the hook).

## 2. Tokens (mirrored in `house.js`; change both together)

### Frame, grid and safe areas (px at 1080×1350)

| Token | Value | Use |
|---|---|---|
| frame | 1080 × 1350, 30 fps | LinkedIn 4:5 feed |
| text column | x 96 → 984 (888 wide) | all type flush left at x 96; right-aligned type ends at 982–984 |
| bleed column | x 44 → 1036 (992 wide) | code panel only (fits 30 px code) |
| header safe band | y 90 → 145 | logo, wordmark, "wk NN"; no other element enters it, and exits are clipped at y 145 |
| content safe area | y 145 → 1185 | everything else |
| footer band | y 1200 → 1260 | rule at y 1210, footer text baseline 1247 |
| poster grid | 8 × 4 modules, 97 × 80, gutters 16, origin (96, 500) | what the grid counts comes from FACTS (wk 02: 32 inboxes) |
| ribbon | 32 modules 23.75 × 18 at a 27.75 pitch | the grid compressed into one row |
| card | h 56 + 38 per result row (+6), gap 8, inset 24, bar 7 | reply / item cards; text baseline +38, first result row +84 |
| code panel | tab 50, top pad 14, line pitch 38, bottom pad 12, code x +20, bar 7 | wk 02: 9 lines = 418 px tall at y 222 |

### Type scale (px at 1080 wide; pt = px × 390 / 1080 on a phone)

| Role | Face | px | Tracking | ≈ pt |
|---|---|---|---|---|
| poster headline (the card) | Newsreader display 500 (opsz 72) | 93 | −2.86 | 33.6 |
| statement | Newsreader display 600 | 84 | −1.8 | 30.3 |
| numeral / range | Newsreader display 600 | 250 | −6 | 90 |
| heading | Newsreader display 600 | 64 | −1.2 | 23.1 |
| one-line statement heading | Newsreader display 500 | 34 | −0.4 | 12.3 |
| quoted line (under a gold rule) | Newsreader italic (opsz 36) | 46 | 0 | 16.6 |
| body / lead | Newsreader text (opsz 24) 400 | 44 / 40 | 0 | 15.9 / 14.4 |
| card text | Newsreader text 400 | 32 | 0 | 11.6 |
| group label | Newsreader italic | 32 | 0 | 11.6 |
| result / rule tag | JetBrains Mono 400 | 31 | 0 | 11.2 |
| code | JetBrains Mono 400 / 700 (keywords) | 30 | 0 | 10.8 (the longest verbatim line, 53 chars, fills the bleed column at 30 px) |
| code tab (provenance) | JetBrains Mono 400 | 31 | −1.6 | 11.2 |
| label ("illustrative replies") | JetBrains Mono 400 | 31 | 0.6 | 11.2 |
| wordmark "ProdCraft" (card scale) | Newsreader text 500 | 26.4 | −0.2 | 9.5 |
| chrome "wk NN", footer (card scale) | JetBrains Mono 400 | 14 | 1.6 | 5.1 |
| end credits | JetBrains Mono 400 | 18 | 0.8 | 6.5 |

### Colour (sampled from `ref/wk02_card.png` flat areas and the site CSS)

| Token | Hex | Use | Contrast |
|---|---|---|---|
| paper | `#EFEDE8` | page | — |
| ink | `#16181c` | type, keywords, bars of routed items | 15.2:1 on paper |
| ink-2 | `#464951` | chrome, labels, dimmed results | 7.7:1 |
| card / card edge | `#F7F6F2` / `#CDCAC3` | cards | ink 16.4:1 |
| panel / tab | `#E6E3DC` / paper | code panel | — |
| highlight | `#DCD3C2` | the line or card that fired | ink 12.0:1, blue 4.9:1 |
| gold bar | `#A58239` | bars, rules, the dot (marks only) | — |
| gold light | `#C8A35C` | filled modules | marks only |
| gold text | `#7A5C22` | pattern names, page number | 5.3:1 on paper, 6.2 measured on cards |
| code blue | `#3A5A78` | code strings | 5.6:1 on panel |

Gold type always uses #7A5C22: the brand's `--gold-t` #8a6a2b is 4.3:1 on paper and the card's "02" is 3.1:1. Dimmed items switch to ink-2; they never fade.

### Chrome (the wk 02 card's measured positions)

Logo: the ProdCraft PNG, tone-mapped to ink (v = min(rgb) × (1 − 2 × saturation), levels 0.3–0.6, alpha kept), drawn 37 px square so that its ink spans x 98–128, y 98–133. Never flood-fill the alpha: that gives a black silhouette. Wordmark baseline (144, 124). "wk NN" right-aligned at (982, 128). Footer rule y 1210, x 96–984, #BEBDBA. Footer text at (96, 1247). Page number right-aligned at (982, 1247) in gold text.

## 3. Colour logic

Paper, ink, ink-2 and one signal (gold). Gold appears where something fired or is being read: the code line's bar, a caught card's bar, its pattern name, a reading rule that draws itself under a held statement. Code blue appears only inside code.

## 4. Type & subtitles

The faces and sizes are in §2. Text is flush left and ragged right. Fonts are self-hosted Google Fonts subsets with their OFL texts (`fonts/`, fetched once by `tools/fonts.py`). There are no subtitles because there is no voice. Instead, the reading floor (characters ÷ 15 + 1.5 s, measured by `readcheck.mjs`) is a build gate. Budget it first, then place the beats.

## 5. Motion quality

- One curve, `cubic-bezier(.7,0,.2,1)`, for every snap. Linear only for lines that draw themselves: reading rules, knife lines.
- **The grid is the beat**: 112.5 BPM at 30 fps, so a beat is 16 frames, an eighth 8 and a sixteenth 4. Every onset falls on a whole frame. A film lasts a whole number of bars; wk 02 is 52 beats = 27.73 s.
- Entrances are clip-reveals; exits rise out upward and are clipped at the header line (y 145); deletions are knife cuts.
- **Sorting without overlap.** A caught card collapses where it is, the column closes, and the card re-opens at its new slot. Then its pattern name and result stamp in (`order()` / `presence()` in the reference `film.js`). Cards never slide over each other.
- **One heading slot, one flip.** The old heading leaves in a quarter beat, then the new one rises in. They are never in the slot together.
- No static hold over 3 s before the end card: a held statement gets a gold reading rule that draws itself.
- **Seamless loop.** The last half beat dissolves into frame 0. This is the style's only dissolve.

## 6. Camera grammar

The frame is locked, because the card does not move; the page re-flows instead. Available moves: a panel sliding in from the right on the beat, drawn above the column it covers; a column re-flowing into freed space; a knife cut that clears the page for the reframe; scale contrast for the payoff. No zooms, pans or rotations.

## 7. Sound palette

- Light, dry, CC0 only. A marimba ostinato in eighths gives the grid's pulse, over soft vibraphone chords and contrabass pizzicato roots. The glockenspiel plays on each rule that fires (the signal sings). A woodblock ticks as each module or card arrives, and a soft shaker plays while things pour in. The samples are VCSL and VSCO 2 CE, played through `sampler.py`. No piano or drum kit is used, so no CC BY credit is owed.
- Foley: procedural paper slides, a "tss" plus a snick for knife cuts, a low thump when a statement lands.
- Two silences: a half-beat break before the main artifact lands, and a near-silence (−24 dB) of a beat and a half before the reframe.
- Master: −16 LUFS integrated, true peak ≤ −1.5 dBTP; low band about −4 dB under the rest.
- Export: H.264 High, CRF 14, `-maxrate 8M -bufsize 16M`, 30 fps, yuv420p, BT.709, `+faststart`, at most 30 MB (`tools/master.sh`).

## 8. Native moves

- **The card wakes up**: frame 0 is the static card; by 0.3 s one of its modules starts to fill.
- **The rule fires**: a verbatim code line lights with the gold bar, the caught card moves to the top of the column, and its pattern name and result stamp in.
- **Name the limit**: one line before routing says that rules catch the obvious and that everything else goes to a person.
- **The routed group**: one label and one shared "CRM updated" tick for everything no rule caught.
- **Knife cut to the reframe**, then a **scale-contrast payoff**, then **the loop closes** (the end card rebuilds the poster grid and dissolves into frame 0).

## 9. Pitfalls of the medium

- **Small type** fails on phones: 15–25 px in wk 02 v1 measured 5–9 pt. Use the §2 scale. Only chrome and credits may stay small.
- **Clipped text in the manifest.** Text drawn inside a clip rect but outside its area was still logged in v1 (`_STOP_PATTERNS`). `drawText()` now logs a run only when part of its box lies inside the current clip and alpha > 0, and each entry carries `vis`. Keep every clip in `pushClip` / `popClip` so the tracker knows about it.
- **A highlight that lies**: when a rule fires that is not in the code shown, remove the code panel's bar and show that rule's pattern name on the card instead.
- **Colour pipeline**: `core/render/video.mjs` writes limited-range BT.601 intermediates. Convert them with `colorspace=all=bt709:iall=bt601-6-625:irange=tv:range=tv` (`tools/master.sh`); `scale=` shifted the paper by 3–5 levels in v1.
- **Readcheck margins** are tight in a 4:5 film under 28 s. Overlap statements rather than shortening their windows. Keep at most 5 cards.
- SCRIPT.md must not start its title with "Script" (`film_eval` would read every section as narration).
- `*.png` is gitignored repo-wide. Force-add `src/assets/logo-prodcraft.png` and `poster.png` (`git add -f`), or add a `!` rule.

## 10. Engine

The reference build is `deliverables/linkedin_posts/prodcraft_wk02_reply_triage/src/`:

- `house.js`: the tokens above.
- `content.json`: everything week-specific.
- `film.js`: Canvas 2D. It reads only `house.js`, `content.json` and `out/code.json`, and contains:
  - `drawText()`, the only `fillText`, which logs what is visible;
  - `line()` (clip-reveal);
  - `chrome()`, `panel()` and `ledger()` (sort without overlap);
  - `group()`, `reframe()`;
  - `readable()`, which feeds readcheck.
- `mix.py`: the score and foley, from `out/events.json` and `content.json`.
- `tools/`:
  - `code.py` (verbatim proof, re-indent);
  - `master.sh`;
  - `drawn_text.mjs`;
  - `poster.mjs`;
  - `script_md.mjs`;
  - `contact_sheet.py`;
  - `page.mjs` (finds the toolkit through `LEMO_OPUSCAR_HOME`);
  - `fonts.py`.
- `build.sh`: one command. It checks the pin, then renders, mixes and masters everything into `src/out/stage.*`. It runs the black-frame check and `film_eval --profile linkedin_4x5`, writes `src/out/hashes.txt`, and only then moves the whole set into the deliverable folder. Nothing in `src/` outside `src/out/` is written.

## 11. Making the next week (wk 03)

1. Make the static card first: it is the fallback if the film misses its gate.
2. `cp -r deliverables/linkedin_posts/prodcraft_wk02_reply_triage/src deliverables/linkedin_posts/prodcraft_wk03_<slug>/src`, add the week's `FACTS.md` (signed off) and `ref/wk03_card.png`, then delete the copied `src/out/`.
3. Edit only `src/content.json`:
   - `meta`: week, name, title, comment, `dur_beats` (a multiple of 4);
   - `chrome`: wk, page;
   - `poster`: head lines (the card's headline), tiles, cols;
   - the remaining blocks: `quote`, `label`, `cards` (≤ 5; text, kind, tile, facts), `rules` (kind, tag, code_lines, result rows, facts, note), `code` (file, from, to, dedent, reindent, tab, forbid), `headings`, `routing`, `reframe`, `payoff`, `credits`, `sound.fire_notes`, `contact_sheet`;
   - `beats`: rebudget with the reading floor; every text needs chars ÷ 15 + 1.5 s fully on screen.
4. Re-fit the poster headline to the new card if its size differs: the tokens give 93 px at baselines 231 and 327. Check bounding box and ink count against the card, as done for wk 02.
5. `export LEMO_OPUSCAR_HOME=<pinned clone>`, then `sh src/build.sh`. Fix anything the readcheck or eval rejects.
6. Do your own 0.1 s frame check of every changed beat. Then the visual QA, then the operator watch.

What does not change week to week: `house.js`, the chrome, the palette, the faces, the beat grid, the "gold marks what fired" rule, silent-safe, the loop. A new kind of beat (for example a table instead of code) is a new component in `film.js`. It uses the §2 tokens; it never adds new ones ad hoc.
