// Trusted Segments v2 — the single timeline. Times are laid out from the real voice durations (voice/out/dur.json):
// every line starts a fixed breath after the previous one ends; key actions are placed relative to the lines; all times
// are quantised to whole frames (1/24 s). tools/export.mjs writes out/timeline.json; film.js, mix.py and the checks read it.
export const FPS = 24, BPM = 72, BEAT = 60 / BPM;
const fr = t => Math.round(t * FPS) / FPS;
export const TYPE_DT = 0.052, DUP_DT = 0.06;
export const F01 = 'Graduates working in finance in London for more than three years';

// narration: Kokoro bf_emma, en-gb, speed 0.95; fact ids per line
export const LINES = {
  L01: 'F01', L02: 'F01', L03: 'F02', L04: 'F04 F26', L06: 'F07', L07: 'F08', L08: 'F03 F09', L09: '—', L10: 'F13',
  L11: 'F22', L12: 'F17', L13: 'F09 F11 F25', L14: 'F12', L15: 'F24', L16: 'F23',
};

export function layout(dur) {
  const V = {}, H = { typeOn: 0.12 };
  const put = (id, t) => { t = fr(t); V[id] = { id, t, t1: +(t + dur[id]).toFixed(3), f: LINES[id] }; return V[id]; };
  const g = 0.2;                                                     // breath between lines
  put('L01', fr(BEAT / 2));
  H.slots = put('L02', V.L01.t1 + 0.4).t;
  H.lightOn = fr(V.L02.t + 0.45);
  put('L03', V.L02.t1 + g);
  H.pullStart = fr(H.lightOn + 0.4);
  H.drop1 = fr(V.L03.t1 - 0.3);                                       // the loupe lands on M0271 (F26)
  H.pullEnd = fr(H.drop1 - 1.4);
  put('L04', V.L03.t1 + g);
  H.cityLit = fr(H.drop1 + 0.6); H.spell = fr(H.cityLit + 0.6);
  put('L06', V.L04.t1 + g); H.climb = V.L06.t;
  H.lift1 = fr(V.L06.t + 0.7); H.spellEnd = fr(Math.max(H.spell + 3.2, H.lift1 + 0.4));
  put('L07', V.L06.t1 + g);
  put('L08', V.L07.t1 + g);
  H.hush1 = fr(V.L08.t1 + 0.05);                                      // silence 1
  H.drop2 = fr(V.L08.t1 + 0.5);                                       // first sound after it: the loupe
  put('L09', H.drop2 + 0.2); H.dateLit = fr(V.L09.t + 0.2);
  H.front = fr(V.L09.t1 - 0.2); H.lift2 = fr(H.front + 0.4);
  put('L10', V.L09.t1 + g);
  H.pair = fr(V.L10.t1 - 0.3);
  put('L11', V.L10.t1 + g);
  H.quote = fr(V.L11.t1 + 0.1);
  put('L12', H.quote + 0.4);
  H.hush2 = fr(V.L12.t1 + 0.05);                                      // silence 2
  H.index = fr(V.L12.t1 + 0.5);
  put('L13', H.index + 0.25);
  H.six = fr(V.L13.t1 + 0.05); put('L14', H.six + 0.15);               // the payoff appears with the end of L13's breath
  H.off = fr(H.six + 2.95); H.glideUp = fr(H.off + 0.2);
  put('L15', H.off - 0.3); H.thesis = fr(H.off + 0.3);             // F24
  H.title = fr(V.L15.t1 + 0.45); put('L16', H.title);                  // F23
  H.endCard = fr(Math.max(H.title + 2.55, V.L16.t1 + 0.8));
  const DUR = fr(H.endCard + 4.5);
  return { V, H, DUR };
}

// word landings: [name, line, word as Whisper wrote it]
export const WORDS = [
  ['rec525', 'L03', '525'], ['spell8', 'L04', 'eight'], ['n2', 'L06', 'two'], ['n26', 'L07', '26'], ['dup25', 'L08', '25'],
  ['n49', 'L08', '49'], ['n68', 'L10', '68'], ['sameSig', 'L11', 'same'], ['c1', 'L13', '1'], ['c5', 'L13', '5'], ['c43', 'L13', '43'],
];

// captions: ≤ 42 characters a line, ≤ 2 lines, ≤ 17 characters a second, 1–7 s, gaps ≥ 0.084 s (checked by export.mjs).
// `from` = the Whisper word a cue starts on. `burn: false` = the same words are already on screen as type.
export const SUBS = [
  { id: 'C01', line: 'L01', hold: 1.7, text: 'One sentence from the brief:' },
  { id: 'C02', line: 'L01', from: '@prev', text: '“Graduates working in finance in London\nfor more than three years”' },
  { id: 'C03', line: 'L02', text: 'One sentence. Four answers.' },
  { id: 'C04', line: 'L03', text: '525 rows, for 500 members.' },
  { id: 'C05', line: 'L04', text: 'Under the loupe, London is spelled 8 ways.' },
  { id: 'C06', line: 'L06', text: 'Filter the file as delivered: 2 rows.' },
  { id: 'C07', line: 'L07', text: 'Normalise spellings and labels: 26.' },
  { id: 'C08', line: 'L08', text: 'Merge 25 duplicates, read employers\nand job titles: 49.' },
  { id: 'C09', line: 'L09', text: 'But look at the dates.' },
  { id: 'C10', line: 'L10', text: '68 % of profiles: untouched\nfor 2 years or more.' },
  { id: 'C11', line: 'L11', text: 'Three years in post and three years\nwithout an update: the same signal.' },
  { id: 'C12', line: 'L12', text: '“340 London expats.\nTwenty had moved back years ago.', burn: false },
  { id: 'C13', line: 'L12', from: 'two', text: 'Two unsubscribed.”', burn: false },
  { id: 'C14', line: 'L13', text: 'The 49 split by trust:' },
  { id: 'C15', line: 'L13', from: '1', text: '1 to send, 5 to confirm,\n43 to win back.' },
  { id: 'C16', line: 'L14', text: '6 worth contacting today.', burn: false },
  { id: 'C17', line: 'L15', text: 'The administrator’s problem is not\nbuilding the list. It is believing it.', burn: false },
  { id: 'C19', line: 'L16', text: 'Trusted Segments.', burn: false },
];

// foley events [t, type, gain] (mix.py plays them; film.js draws the actions on the same times)
export function foley(H, W) {
  const E = [];
  for (let i = 0; i < F01.length; i++) if (F01[i] !== ' ') E.push([+(H.typeOn + i * TYPE_DT).toFixed(3), 'key', 0.5]);
  for (let i = 0; i < 4; i++) E.push([+(H.slots + i * 0.12).toFixed(3), 'label', 0.6]);
  E.push([H.lightOn, 'starter', 1], [H.lightOn + 0.17, 'starter', .7], [H.lightOn + 0.4, 'starter', .8], [H.pullStart, 'sweep', .8]);
  E.push([W.rec525, 'label', .6], [H.drop1, 'loupe', 1], [H.cityLit, 'paper', .6], [H.spell, 'label', .8], [H.lift1, 'lift', .6]);
  E.push([H.climb, 'label', .7], [W.n2, 'land', 1], [W.n26, 'land', 1], [W.n49, 'land', 1]);
  for (let i = 0; i < 25; i++) E.push([+(W.dup25 + i * DUP_DT).toFixed(3), 'tick', .4]);
  E.push([H.drop2, 'loupe', 1.1], [H.dateLit, 'paper', .6], [H.front, 'front', 1], [H.lift2, 'lift', .6], [W.n68, 'land', .8]);
  E.push([H.pair, 'label', .7], [W.sameSig, 'pen', 1]);
  E.push([H.quote, 'sweep', .7], [H.quote + 0.5, 'paper', .5]);
  E.push([H.index, 'whoosh', 1], [W.c1, 'land', .9], [W.c5, 'land', .9], [W.c43, 'land', .9], [H.six, 'land', 1.1], [H.six + 0.05, 'pen', .8]);
  E.push([H.off, 'switch', 1], [H.glideUp, 'sweep', .5]);
  for (let i = 0; i < 4; i++) E.push([+(H.glideUp + 1.6 + i * 0.3).toFixed(3), 'tick', .5]);
  E.push([H.title, 'land', .7], [H.endCard, 'paper', .4]);
  return E.sort((a, b) => a[0] - b[0]);
}
