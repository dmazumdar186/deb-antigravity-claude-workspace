# ProdCraft Notes: changes from swiss-motion

| Section | Base (swiss-motion) | Now (prodcraft-notes) | Why |
|---|---|---|---|
| §2 frame | 1920×1080, 24 fps, 12 columns | 1080×1350, 30 fps, one 888 px text column (x 96–984), card margins | LinkedIn 4:5 feed; must match the static weekly card |
| §2 chrome | none | the card's header (logo, wordmark, "wk NN") and footer (rule, "ProdCraft · weekly notes", page number) on every frame | series identity; frame 0 is the poster |
| §3 colour | page/paper/ink + one saturated signal (red, orange, blue or green) | warm paper #EFEDE8, ink #16181c, gold as the one signal (marks), gold text #7A5C22, code blue only inside code | ProdCraft brand (site CSS, cards); contrast ≥ 4.5:1 |
| §4 type | one neo-grotesque family | Newsreader (headlines, cards), JetBrains Mono (code, labels, results); Geist dropped in v2 (QA D9) | the series' faces |
| §4 subtitles | layout captions on whisper timestamps | none (no voice); reading-time rule enforced by readcheck | personal feed, silent-safe |
| §5 motion | snaps on beats, wipes, knife cuts, no dissolves | same, on a 112.5 BPM grid of whole frames at 30 fps; one dissolve allowed: the loop | loops on LinkedIn |
| §6 camera | 2D camera matrix, pans, rotations, pull-outs | locked frame; the page re-flows | the card must stay the card |
| §7 sound | motorik / techno / marimba options, voice ≥ 6 dB over music, −14 LUFS | light marimba + vibraphone + glockenspiel, CC0 only, no voice, −16 LUFS / TP ≤ −1.5 dBTP | personal brand, autoplay muted |
| §8 native moves | grid means something, snap = beat, programme, exception, knife cut, re-flow | kept: grid means something, knife cut, re-flow; added: the card wakes up, the rule fires, scale-contrast payoff, the loop closes | the weekly-note arc: claim → code → reframe |
| borrowed | — | living-screencast: real code redrawn verbatim, never a screenshot | the notes are about code in this repo |
| v2 (2026-11-01) | — | motion by 0.3 s; ≥ 30 px for everything read; sort without overlap; pattern name on caught cards; tokens in house.js; content.json per week | panel lenses 2/3/4/8/9/10 and VISUAL_QA |
