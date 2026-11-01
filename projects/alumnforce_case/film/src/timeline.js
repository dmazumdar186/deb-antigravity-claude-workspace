// Trusted Segments — the single timeline. 72 BPM, 4/4, one beat = 0.8333 s. Every line start and key action sits on
// the beat grid; number landings follow the narrator's word (Whisper word times, out/timeline.json).
// film.js (picture), tools/export.mjs (cues, subtitles, events) and mix.py (via out/timeline.json) all read it.
export const BPM = 72, BEAT = 60 / BPM;
export const b = n => +(n * BEAT).toFixed(4);
export const DUR = b(91.5);                                 // 76.25 s

// key actions [beat]
export const HIT = {
  typeOn: 0.12,        // typing starts (before the first beat: the hook)
  slots: b(7.5),       // four empty answer slots
  lightOn: b(9),       // table flickers on, camera starts the pull-back
  pullEnd: b(14.5),
  drop1: b(15.5),        // loupe lands on a London card
  cityLit: b(16.5),      // the city line lights
  spell: b(17.5),        // eight spellings lift out
  lift1: b(20),      // loupe lifts
  dups: b(20),       // 25 duplicate rings start
  climb: b(23.5),        // reading plate in, naive filter
  hush1: b(36.25),     // music out: silence 1
  drop2: b(38),      // loupe lands on a date field (first sound after the silence)
  dateLit: b(39),
  front: b(40),      // develop front: stale cards go dark
  lift2: b(40.5),
  pair: b(46.5),         // two records side by side
  quote: b(53.5),        // quoted note
  hush2: b(61.75),     // silence 2
  index: b(63),      // the table becomes the index
  six: b(72.5),          // bracket: 6 can be e-mailed today
  off: b(76),          // table switches off, six cards glow
  glideUp: b(76.5),    // camera rises to the query strip
  product: b(77),      // product line typed
  title: b(86),      // Trusted Segments
};

// narration (Kokoro bf_emma, en-gb, speed 0.9); start beat; durations from voice/out/dur.json
export const VOICE = [
  { id: 'L01', beat: 0.5, f: 'F01' }, { id: 'L02', beat: 7.5, f: 'F01' },
  { id: 'L03', beat: 10.5, f: 'F02' }, { id: 'L04', beat: 16, f: 'F04' }, { id: 'L05', beat: 20, f: 'F03' },
  { id: 'L06', beat: 23.5, f: 'F07' }, { id: 'L07', beat: 27.5, f: 'F08' }, { id: 'L08', beat: 31, f: 'F09' },
  { id: 'L09', beat: 38.5, f: '—' }, { id: 'L10', beat: 41, f: 'F13' }, { id: 'L11', beat: 46.5, f: 'F22' },
  { id: 'L12', beat: 52.5, f: 'F17' }, { id: 'L13', beat: 64, f: 'F09 F11 F21' }, { id: 'L14', beat: 72.5, f: 'F12' },
  { id: 'L15', beat: 77, f: 'F19' }, { id: 'L16', beat: 86, f: 'F23' },
].map(v => ({ ...v, t: b(v.beat) }));

// word landings: [name, line, word as Whisper wrote it]
export const WORDS = [
  ['n2', 'L06', 'two'], ['n26', 'L07', '26'], ['n49', 'L08', '49'], ['n68', 'L10', '68'],
  ['sameSig', 'L11', 'same'], ['c1', 'L13', '1'], ['c5', 'L13', '5'], ['c43', 'L13', '43'], ['n6', 'L14', 'Six'],
  ['spell8', 'L04', 'eight'], ['dup25', 'L05', '25'], ['rec525', 'L03', '525'],
];

// subtitles (one line each; a cue may start at a word of its line with `from`)
export const SUBS = [
  { id: 'S01a', line: 'L01', text: 'One sentence, from the brief.' },
  { id: 'S01b', line: 'L01', from: 'Graduates', text: 'Graduates working in finance, in London, for more than three years.' },
  { id: 'S02', line: 'L02', text: 'One sentence. Four answers.' },
  { id: 'S03', line: 'L03', text: 'The file: 525 records, for 500 members.' },
  { id: 'S04', line: 'L04', text: 'Under the loupe, London is spelled 8 different ways.' },
  { id: 'S05', line: 'L05', text: 'And 25 people appear twice.' },
  { id: 'S06', line: 'L06', text: 'Filter the file as delivered: 2 members.' },
  { id: 'S07', line: 'L07', text: 'Normalise the spellings: 26.' },
  { id: 'S08', line: 'L08', text: 'Remove the duplicates, read employers and job titles: 49.' },
  { id: 'S09', line: 'L09', text: 'But look at the dates.' },
  { id: 'S10', line: 'L10', text: '68 % of profiles have not been touched in 2 years or more.' },
  { id: 'S11', line: 'L11', text: '“Three years in post” and “three years without an update” are the same signal.' },
  { id: 'S12a', line: 'L12', text: 'One user put it plainly: “340 London expats.' },
  { id: 'S12b', line: 'L12', from: '20', text: 'Twenty had moved back years ago. Two unsubscribed.”' },
  { id: 'S13a', line: 'L13', text: 'So the 49 split by trust.' },
  { id: 'S13b', line: 'L13', from: '1', text: '1 current. 5 to confirm. 43 to reactivate.' },
  { id: 'S14', line: 'L14', text: '6 can be e-mailed today.' },
  { id: 'S15a', line: 'L15', text: 'Describe your audience in one sentence.' },
  { id: 'S15b', line: 'L15', from: 'Get', text: 'Get a segment you can trust.' },
  { id: 'S15c', line: 'L15', from: 'No', text: 'No member record ever leaves the platform.' },
  { id: 'S16', line: 'L16', text: 'Trusted Segments.' },
];

// foley events [t, type, gain] (mix.py plays them; film.js draws the actions on the same times)
export function foley(H, W) {
  const E = [];
  const text = 'Graduates working in finance in London for more than three years';
  for (let i = 0; i < text.length; i++) if (text[i] !== ' ') E.push([+(H.typeOn + i * TYPE_DT).toFixed(3), 'key', 0.5]);
  for (let i = 0; i < 4; i++) E.push([+(H.slots + i * 0.12).toFixed(3), 'label', 0.6]);
  E.push([H.lightOn, 'starter', 1], [H.lightOn + 0.17, 'starter', .7], [H.lightOn + 0.4, 'starter', .8], [H.lightOn + 0.05, 'sweep', .8]);
  E.push([H.drop1, 'loupe', 1], [H.cityLit, 'paper', .6], [H.spell, 'label', .8], [H.lift1, 'lift', .6]);
  for (let i = 0; i < 25; i++) E.push([+(W.dup25 + i * DUP_DT).toFixed(3), 'tick', .45]);
  E.push([H.climb, 'label', .7], [W.n2, 'land', 1], [W.n26, 'land', 1], [W.n49, 'land', 1]);
  for (const [a, n] of [[W.n2, 2], [W.n26, 26], [W.n49, 49]]) for (let i = 0; i < Math.min(n, 26); i++) E.push([+(a - 0.5 + i * 0.5 / Math.min(n, 26)).toFixed(3), 'tick', .25]);
  E.push([H.drop2, 'loupe', 1.1], [H.dateLit, 'paper', .6], [H.front, 'front', 1], [H.lift2, 'lift', .6], [W.n68, 'land', .8]);
  E.push([H.pair, 'label', .7], [H.pair + 0.5, 'label', .7], [W.sameSig, 'pen', 1]);
  E.push([H.quote, 'sweep', .7], [H.quote + 0.4, 'paper', .5]);
  E.push([H.index, 'whoosh', 1], [W.c1, 'land', .9], [W.c5, 'land', .9], [W.c43, 'land', .9], [W.n6, 'pen', 1]);
  E.push([H.off, 'switch', 1], [H.glideUp, 'sweep', .5]);
  for (let i = 0; i < 40; i++) E.push([+(H.product + i * 0.11).toFixed(3), 'key', .35]);
  E.push([H.title, 'land', .7]);
  return E.sort((a, b) => a[0] - b[0]);
}
export const TYPE_DT = 0.052, DUP_DT = 0.07;
