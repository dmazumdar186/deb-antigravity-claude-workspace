// SCRIPT.md from out/timeline.json (+ out/drawn_text.json when present): a metadata header block, then "## Narration"
// and "## On-screen text", each line with time codes and fact ids. usage: node tools/script_md.mjs <film_dir> > SCRIPT.md
import fs from 'fs'; import path from 'path';
const D = path.resolve(process.argv[2] || '.');
const T = JSON.parse(fs.readFileSync(path.join(D, 'out/timeline.json'), 'utf8'));
const H = T.hit, W = T.words;
const tc = s => { const m = Math.floor(s / 60), x = s - m * 60; return `${String(m).padStart(2, '0')}:${x.toFixed(2).padStart(5, '0')}`; };
const V = Object.fromEntries(T.voice.map(v => [v.id, v]));
const nw = T.voice.reduce((a, v) => a + v.text.split(/\s+/).filter(Boolean).length, 0) - 2;
const SCREEN = [
  [H.typeOn, H.title - 0.1, 'Search box, typed: "Graduates working in finance in London for more than three years"', 'F01'],
  [H.slots, H.glideUp + 1.6, 'Four empty answer slots: ? ? ? ?', 'F01'],
  [H.lightOn + 0.4, H.off + 0.3, 'Tag (bottom right, whenever cards are on the lit table): "Schematic · no member data"', 'hard rules'],
  [V.L03.t, H.drop1 - 0.2, 'Reading: "Rows in the file" / 525 / "for 500 members"', 'F02'],
  [H.cityLit, H.lift1 + 0.4, 'Under the loupe, the one real record: "M0271" · "Londres (Royaume-Uni)", city line lit and underlined', 'F26 F04'],
  [H.spell, H.spellEnd, 'Reading: "London, as typed in the file": Greater London · LONDON · London · London - Canary Wharf · London, UK · Londres · Londres (Royaume-Uni) · london — "8 spellings"', 'F04'],
  [H.climb, W.n2 - 0.05, 'Reading: "Naive filter · file as delivered" (value lands with the word)', 'F07'],
  [W.n2 - 0.05, W.n26 - 0.05, 'Reading: "Naive filter · file as delivered" / 2 / "rows matching the sentence"; 2 cards outlined', 'F07'],
  [W.n26 - 0.05, W.n49 - 0.05, 'Reading: "Normalised · spellings and labels" / 26 / "rows matching the sentence"; 26 cards outlined', 'F08'],
  [W.dup25, H.hush1 + 0.6, '25 rings on the duplicate cards', 'F03'],
  [W.n49 - 0.05, W.n49 + 4.1, 'Reading: "Full logic · dedup + employer + job title" / 49 / "members matching the sentence"; 49 cards outlined', 'F09'],
  [H.dateLit, H.lift2 + 0.4, 'Under the loupe, an example card (no ID): "example" · "in post: 3 yrs" · "updated: 3 yrs ago", the update line underlined', 'F22'],
  [H.front, H.front + 3.4, 'Develop front: stale cards go dark across the table', 'F13'],
  [Math.max(W.n68 - 0.3, H.lift2 + 0.4), H.pair + 0.6, 'Reading: "Profiles untouched for 2+ years" / 68 % / "of 500 members · ref. 2026-10-12"', 'F13'],
  [H.pair, H.quote + 0.25, 'One plate, two records: "read as tenure" — “Three years in post” = "read as freshness" — “Three years without an update” (pen stroke "=" on "same")', 'F22'],
  [H.quote + 0.63, H.index - 0.2, 'Note on the table: “340 London expats. / Twenty had moved back years ago. / Two unsubscribed.” — "user verbatim"', 'F17'],
  [H.index + 0.45, H.six + 0.35, 'Index columns: "Current → send" · "To confirm → confirm" · "To reactivate → reactivate"; counts land on the words: 1 · 5 · 43', 'F21 F25 F11'],
  [H.six + 0.3, H.glideUp + 0.5, 'Payoff, centred, largest element: "6" / "worth contacting today:" / "1 to send, 5 to confirm."; the six cards in a row', 'F12'],
  [H.off, H.glideUp + 0.7, 'The table switches off; the six cards glow', 'F12'],
  [H.thesis, H.endCard, 'Thesis: "The administrator’s problem is not building the list." / "It is believing it."', 'F24'],
  [H.glideUp + 1.6, H.endCard, 'Answer slots fill: 2 as delivered · 26 normalised · 49 full logic · 6 worth contacting', 'F07 F08 F09 F12'],
  [H.title, H.endCard, 'Title in the search box: "Trusted Segments"', 'F23'],
  [H.endCard, T.dur, 'End card: "Trusted Segments" / Made in code by an AI agent with lemo-opuscar (MIT) / Synthetic voice: Kokoro (Apache 2.0) / Piano: Salamander Grand Piano V3 by Alexander Holm / Licence CC BY 3.0 / https://creativecommons.org/licenses/by/3.0/ / Strings and mallets: CC0, Versilian Studios / Fonts: IBM Plex (OFL) / Record cards are schematic · no member data', 'hard rules'],
];
const out = [
  '# Trusted Segments — script (v2)', '',
  '```', `version:   v2`, `duration:  ${T.dur.toFixed(2)} s (end card ${(T.dur - H.endCard).toFixed(2)} s)`, `picture:   1920×1080, 24 fps`,
  `voice:     Kokoro bf_emma (British English), speed 0.95, offline`, `narration: ${T.voice.length} lines, ${nw} words (space-separated), ${(nw / T.dur * 60).toFixed(1)} wpm over the whole film`,
  `captions:  ${T.cues.length} cues, ≤ 42 chars a line, ≤ 2 lines, ≤ 17 chars/s, 1–7 s, gaps ≥ 0.084 s (trusted-segments_clean.captions.srt)`,
  `facts:     FACTS.md ids F01–F27; numbers are spelled out for the voice and written as digits on screen`, '```', '',
  '## Narration', '', '| # | In | Out | Spoken text | Facts |', '|---|---|---|---|---|',
  ...T.voice.map(v => `| ${v.id} | ${tc(v.t)} | ${tc(v.t1)} | ${v.id === 'L16' ? 'Trusted Segments. *(rendered as "Trusted Segments, the product." and cut after "Segments")*' : v.text} | ${v.f} |`),
  '', '### Captions', '', '| Cue | In | Out | Text | Facts | Burned in |', '|---|---|---|---|---|---|',
  ...T.cues.map(c => `| ${c.id} | ${tc(c.t0)} | ${tc(c.t1)} | ${c.text.replace('\n', ' / ')} | ${V[c.line].f} | ${c.burn ? 'yes' : 'no (same words on screen as type)'} |`),
  '', '## On-screen text', '', '| In | Out | What is on screen | Facts |', '|---|---|---|---|',
  ...SCREEN.sort((a, b) => a[0] - b[0]).map(([a, b, s, f]) => `| ${tc(a)} | ${tc(b)} | ${s} | ${f} |`),
  '', 'Every glyph run drawn on screen, frame by frame, is listed in `src/out/drawn_text.json` (written by `tools/drawn_text.mjs`). Background cards carry no member ID; the only ID is F26 (M0271), with its real city.',
];
console.log(out.join('\n'));
