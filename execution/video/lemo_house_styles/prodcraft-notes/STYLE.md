# ProdCraft Notes — Style Prompt (house style, based on swiss-motion)

> The ProdCraft weekly-notes card, in motion: a warm paper page, a big Newsreader headline, code in a pale panel, and one gold signal that marks what fired. Every move snaps on the beat; nothing bounces.
> Base: lemo-opuscar `styles/swiss-motion` (bebbbe1). Borrows how code is shown from `styles/living-screencast` (real code, redrawn, verbatim, never a screenshot). Grammar only: no demo story, shot or melody is reused.
> Reference build: `deliverables/linkedin_posts/prodcraft_wk02_reply_triage/src/` (wk 02, "32 inboxes, 800 sends. Who replied?"). Copy it, never edit it in place.

## 1. Essence, and what it is not

- **A weekly note that moves.** Each film replaces one static card of the "ProdCraft · weekly notes" series on LinkedIn and must read as the same series: same header, footer, paper, headline face.
- **Frame 0 is the card.** LinkedIn shows the first frame before play, so frame 0 is a finished poster: header, footer and the card's headline at the card's exact size and position.
- **Silent-safe.** Most viewers autoplay muted. Everything reads with the sound off; sound is a bonus layer, never the carrier. No voice.
- **One signal: gold.** It marks what fired (a rule, a highlighted code line, a reply that was answered). Everything else is ink on paper.
- **Facts only.** Every number and quote comes from the note's `FACTS.md`, tagged by id in `SCRIPT.md`. No count-ups.

Not a keynote (no gradients, glow, device mock-ups), not kinetic type (words never fly, spin or bounce), not a screen recording (code is redrawn, never captured), not a brand sting (no logo reveal before the hook).

## 2. Materials & rendering

- **Frame**: 1080×1350 (4:5 feed), 30 fps. Margins 96 px left and right (text column x 96–984); code panel and highlight bars may bleed to x 72–1008, as on the card.
- **Chrome (fixed, every frame, card positions)**: logo top-left (the ProdCraft mark tinted to ink, ink box x 98–128, y 98–133); wordmark "ProdCraft" Newsreader text 500 26.4 px, baseline y 124 at x 144; "wk NN" JetBrains Mono 14 px, letter-spacing 1.6 px, right-aligned at x 982, baseline 128. Footer: 1 px rule #BEBDBA at y 1210 from x 96 to 984; "ProdCraft · weekly notes" mono 14 px (ls 1.6) at x 96, baseline 1247; page number "NN" in gold text, right-aligned at x 982.
- **Surfaces**: flat paper, no grain, no shadows. Cards are a lighter paper (#F7F6F2) with a 1 px edge (#CDCAC3). The code panel copies the card: panel #E6E3DC, tab bar #E7E4DD, a paper-coloured tab with a gold dot and `folder / file.py`, 1 px border #B8B6B1, "verbatim" small at the tab bar's right.
- **Code**: JetBrains Mono 24 px, line pitch 33 px, strings blue #3A5A78, keywords (`if`, `return`) bold ink, the rest ink. A fired line gets the highlight fill #DCD3C2 across the panel and a 7 px gold bar (#A58239) at the panel's left edge. Lines are byte-identical to the source; only the common indent may be removed (generate them from the file, never retype them).
- **The grid means something**: modules stand for a counted quantity from FACTS (wk 02: 32 envelope tiles = 32 inboxes).

## 3. Colour logic

Sampled from `ref/wk02_card.png` (mean of flat areas) and `site/css/styles.css`:

| Token | Hex | Use | Contrast on paper |
|---|---|---|---|
| paper | `#EFEDE8` | page (card mean #EFEDE8) | — |
| ink | `#16181c` | headlines, body, card text | 15.2:1 |
| ink-2 | `#464951` | mono chrome, labels, dimmed results | 7.7:1 |
| panel / tab bar | `#E6E3DC` / `#E7E4DD` | code panel | — |
| highlight | `#DCD3C2` | a fired code line or card | ink 12.0:1 |
| gold bar | `#A58239` | bars, rules, the dot (marks only) | — |
| gold light | `#C8A35C` | filled modules (site `--gold`) | marks only |
| gold text | `#7A5C22` | the page number and any gold type | 5.3:1 |
| code blue | `#3A5A78` | code strings | 5.6:1 on panel, 4.9:1 on highlight |

- Gold is a mark colour. The brand's `--gold-t` #8a6a2b reaches only 4.3:1 on paper and the card's "02" (#A48139) 3.1:1, so gold **type** uses #7A5C22. Every text ≥ 4.5:1, measured on the encoded film (`src/out/contrast.txt`).
- One signal colour; ink-2 is the only secondary voice. Dimmed elements switch to ink-2 (still 7.7:1), they never fade to grey.

## 4. Type & subtitles

- **Newsreader** (OFL) for headlines and statements: display optical size (opsz 72), weight 500, tight tracking (−2.86 px at 93 px; about −3 %). The card headline is 93 px, baselines 231 and 327. Statements 46–84 px; a giant range or numeral up to 250 px (scale contrast).
- **Newsreader italic** (opsz 36) for the quoted problem line, under a short gold rule (as on the wk 01 card).
- **JetBrains Mono** (OFL) for code, labels, chrome and results; letter-spaced 1.2–1.6 px at 14–15 px.
- **Geist** (OFL) 500 for small body text such as reply cards (25 px).
- Flush left, ragged right. Fonts are self-hosted subsets from Google Fonts with their OFL texts (`fonts/`, fetched by `src/tools/fonts.py`).
- **No subtitles** (no voice). Reading time is the caption rule: every text stays fully on screen ≥ characters ÷ 15 + 1.5 s (`readcheck.mjs`), asserted by the build.

## 5. Motion quality

- One curve, `cubic-bezier(.7,0,.2,1)`, for every snap; linear only for a line that draws itself (a reading rule under a held statement, a knife line).
- **The grid is the beat**: 112.5 BPM at 30 fps, so a beat is 16 frames, an eighth 8, a sixteenth 4. Every snap starts and lands on a whole frame.
- Entrances are clip-reveals (a line rises out of its own slot); exits rise out upward; deletions are knife cuts (a line through the midline, then the element collapses onto it); re-orders are re-flows (rows slide to their new slots, the moving rows drawn on top). No fades, except the loop dissolve.
- **No static hold over 3 s before the end card**: hold a statement with a reading rule drawing itself, or lights stepping on sixteenths.
- **Seamless loop**: the film is a whole number of bars and its last half beat dissolves into frame 0.

## 6. Camera grammar

Locked frame (the card does not move); the page re-flows instead. Moves available: a panel sliding in from the right edge on the beat; a column re-flow up or down into freed space; a knife cut that clears the page for the reframe; scale contrast (giant range beside small text) for the payoff. No zooms, pans or rotations: the card must stay the card.

## 7. Sound palette

- Light, dry, CC0 only: marimba ostinato in eighths (the grid's pulse), soft vibraphone chords, contrabass pizzicato roots, glockenspiel on each rule that fires (the signal sings), woodblock / claves for sorting ticks, a soft shaker while things pour in. VCSL + VSCO 2 CE via `sampler.py`; no piano or drum kit (no CC BY credit needed).
- Foley: procedural paper slides, a ruling-pen "tss" plus snick for knife cuts, a low thump when a statement lands.
- Two silences: a half-beat break before the main artifact lands, and a near-silence (−24 dB) for a beat and a half before the reframe.
- Master: −16 LUFS integrated, true peak ≤ −1.5 dBTP, LRA ≈ 3–4 LU; low band (20–120 Hz) about −4 dB under the rest.

## 8. Native moves

- **The card wakes up.** Frame 0 is the static card; the first beat turns one of its elements into the system (wk 02: the inbox grid snaps into a ribbon and starts to emit replies).
- **The rule fires.** A verbatim code line lights with the gold bar, and the items it catches stamp their result in mono, left to right.
- **Sort by re-flow.** Caught items rise to the top in the order the code checks them; what is left sinks to the bottom and goes to a person.
- **Knife cut to the reframe.** The working page is cut away, and one big Newsreader statement replaces it.
- **Scale contrast payoff.** The real target as a giant numeral or range with small text under it and a gold reading rule drawing itself.
- **The loop closes.** The end card rebuilds the poster's grid and dissolves into frame 0.

## 9. Pitfalls of the medium

- Gold type at the brand tint fails contrast → gold text only at #7A5C22; gold elsewhere is a mark.
- `core/render/video.mjs` writes limited-range BT.601 (tagged bt470bg) intermediates; converting with `scale=in_range=pc` darkens the paper to #DADAD3 and `scale=…:out_color_matrix=bt709` still shifts it 3–5 levels. Master with `colorspace=all=bt709:iall=bt601-6-625:irange=tv:range=tv` (`src/tools/master.sh`), then check a decoded frame against the poster.
- Readcheck margins are tight in a 4:5 film under 28 s: budget reading time first (chars ÷ 15 + 1.5 s per text), then place beats; overlap statements rather than shortening windows.
- Code tokens drawn per colour show up as fragments in `drawn_text.json`; prove verbatim code from the source (`src/tools/code.py`), not from the manifest.
- A title of SCRIPT.md that starts with "Script" makes `film_eval.py` read every section under it as narration; start it with the series name.
- Header, footer and code sizes (14–25 px) follow the card and trigger `film_eval`'s `drawn_text_size` WARN (28 px at 1080p); that is the series' scale, accepted.

## 10. Engine

Reference build in `deliverables/linkedin_posts/prodcraft_wk02_reply_triage/src/`: `timeline.js` (beat sheet in beats, cards, texts with fact ids), `film.js` (Canvas 2D; `drawText()` is the only `fillText` and logs every glyph run; `line()` clip-reveals; `chrome()` draws the card's header and footer; `panel()` draws verbatim code with the gold bar; `readable()` feeds `window.TEXTS` for readcheck), `mix.py` (score + foley from `events.json`), `tools/` (`fonts.py`, `code.py`, `master.sh`, `drawn_text.mjs`, `poster.mjs`, `script_md.mjs`, `contact_sheet.py`), `build.sh` (one command, pinned SHA, atomic writes). Fonts and OFL texts are also kept here in `fonts/`; the logo stays at `deliverables/prodcraft_site_2026-10-19/site/assets/logo-prodcraft.png` (the build copies it). `styleframe.png` is the wk 02 poster (frame 0).

## 11. Variation space

Per weekly note, change only: the headline and week number (frame 0 = that week's card), what the grid counts, the artifact (code panel, a table, a message thread), the facts, the payoff numeral, and the key of the score. Keep: chrome, palette, faces, the beat grid, the gold-marks-what-fired rule, silent-safe, the loop.
