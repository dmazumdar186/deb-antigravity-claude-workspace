// SCRIPT.md from out/timeline.json: narration and on-screen text, line by line, with time codes and fact ids.
// usage: node tools/script_md.mjs <film_dir> > SCRIPT.md
import fs from 'fs'; import path from 'path';
const D = path.resolve(process.argv[2] || '.');
const T = JSON.parse(fs.readFileSync(path.join(D, 'out/timeline.json'), 'utf8'));
const H = T.hit, W = T.words, C = Object.fromEntries(T.cues.map(c => [c.id, c]));
const tc = s => { const m = Math.floor(s / 60), x = s - m * 60; return `${String(m).padStart(2, '0')}:${x.toFixed(2).padStart(5, '0')}`; };
const SUBF = { L01: 'F01', L02: 'F01', L03: 'F02', L04: 'F04', L05: 'F03', L06: 'F07', L07: 'F08', L08: 'F09', L09: '—', L10: 'F13', L11: 'F22', L12: 'F17', L13: 'F09 F11 F21', L14: 'F12', L15: 'F19', L16: 'F23' };
const SCREEN = [
  [H.typeOn, H.title, 'Search box, typed: "Graduates working in finance in London for more than three years"', 'F01'],
  [H.slots, 65.0, 'Four empty answer slots: ? ? ? ?', 'F01'],
  [W.rec525 - 0.3, H.drop1 - 0.35, 'Reading: "Rows in the file / 525 / for 500 members announced"', 'F02'],
  [H.lightOn + 0.6, H.drop1 - 0.45, 'Tag: "Schematic · IDs and city only · no member data"', 'hard rules'],
  [H.cityLit, H.lift1, 'Under the loupe: card M0475, city line "Londres (Royaume-Uni)" lit and underlined', 'F04'],
  [H.spell, H.climb - 0.1, 'Reading: "London, as typed in the file": Greater London · LONDON · London · London - Canary Wharf · London, UK · Londres · Londres (Royaume-Uni) · london — "8 spellings"', 'F04'],
  [W.dup25 + 0.2, H.climb - 0.1, 'Reading: "Duplicate persons / 25 / IDs M0501 – M0525"; 25 rings on the table', 'F03'],
  [H.climb, W.n26 - 0.55, 'Reading: "Naive filter · file as delivered / 2" (lands on the word); 2 cards outlined', 'F07'],
  [W.n26 - 0.55, W.n49 - 0.55, 'Reading: "Normalised · 8 spellings, 3 sector labels / 26"; 26 cards outlined', 'F08'],
  [W.n49 - 0.55, H.drop2 + 0.4, 'Reading: "Full logic · dedup + employer + job title / 49"; 49 cards outlined', 'F09'],
  [H.dateLit, H.lift2, 'Under the loupe: schematic card "in post: 3 yrs / updated: 3 yrs ago", the update line underlined', 'F22'],
  [H.front, H.front + 3.6, 'Develop front: stale cards go dark across the table', 'F13'],
  [W.n68 - 0.5, H.pair + 0.2, 'Reading: "Profiles untouched for 2+ years / 68 % / of 500 members · ref. 2026-10-12"', 'F13'],
  [H.pair, H.quote + 0.3, 'Two records side by side: "read as tenure — “Three years in post”" | "read as freshness — “Three years without an update”"', 'F22'],
  [W.sameSig, H.quote + 0.3, 'Pen stroke "=" and label "the same signal"', 'F22'],
  [H.quote, H.index, 'Note on the table: “340 London expats. / Twenty had moved back years ago. / Two unsubscribed.” — "user verbatim"', 'F17'],
  [H.index + 0.45, H.off + 0.6, 'Index columns: "Current" · "To confirm" · "To reactivate"', 'F21'],
  [W.c1, H.off + 0.6, 'Counts land: 1 · 5 · 43', 'F11'],
  [W.n6, H.off + 0.5, 'Bracket around Current + To confirm: "6 can be e-mailed today"', 'F12'],
  [H.off, H.glideUp + 0.7, 'The table switches off; the six cards glow', 'F12'],
  [H.glideUp + 2.0, T.dur, 'Answer slots fill: 2 as delivered · 26 normalised · 49 full logic · 6 e-mail today', 'F07 F08 F09 F12'],
  [C.S15a.t0, T.dur, 'Product line, three lines: "Describe your audience in one sentence." / "Get a segment you can trust." / "No member record ever leaves the platform."', 'F19'],
  [H.title, T.dur, 'Title in the search box: "Trusted Segments"', 'F23'],
];
const out = [];
out.push('# Trusted Segments — script', '', `Duration ${T.dur.toFixed(2)} s · 1920×1080 · 24 fps · narrator Kokoro \`bf_emma\` (British English), speed 0.9 · 72 BPM grid.`,
  'Fact ids refer to `FACTS.md` (F01–F23). Numbers in the narration are spelled out for the voice and written as digits on screen.', '',
  '## Narration (voice-over)', '', '| # | In | Out | Spoken text | Facts |', '|---|---|---|---|---|');
T.voice.forEach(v => out.push(`| ${v.id} | ${tc(v.t)} | ${tc(v.t1)} | ${v.id === 'L16' ? 'Trusted Segments. *(rendered as "Trusted Segments, the product." and cut after "Segments")*' : v.text} | ${SUBF[v.id]} |`));
out.push('', '## Subtitles (as in trusted-segments.srt)', '', '| Cue | In | Out | Text | Facts | Burned in |', '|---|---|---|---|---|---|');
T.cues.forEach(c => out.push(`| ${c.id} | ${tc(c.t0)} | ${tc(c.t1)} | ${c.text} | ${SUBF[c.line]} | ${/^S1[456]/.test(c.id) ? 'no: the same words are on screen as type' : 'yes'} |`));
out.push('', '## On-screen text and marks', '', '| In | Out | What is on screen | Facts |', '|---|---|---|---|');
SCREEN.sort((a, b) => a[0] - b[0]).forEach(([a, b, s, f]) => out.push(`| ${tc(a)} | ${tc(b)} | ${s} | ${f} |`));
out.push('', 'Card IDs (M0001–M0525) are anonymous record stubs; cities and set membership on the cards are schematic (see `src/FACTS.md`).');
console.log(out.join('\n'));
