// Timeline -> out/timeline.json (page, mix.py, checks) and out/cues_srt.json (captions).
// Reads voice/out/dur.json and voice/out/words.json (tts.py, asr_check.py).
// Exits 1 on a voice overlap or any caption rule broken: ≤ 42 chars a line, ≤ 2 lines, ≤ 17 chars/s, 1–7 s, gaps ≥ 0.084 s.
// usage: node tools/export.mjs <film_dir>
import fs from 'fs'; import path from 'path'; import { pathToFileURL } from 'url';
const D = path.resolve(process.argv[2] || '.');
const TL = await import(pathToFileURL(path.join(D, 'timeline.js')).href);
const dur = JSON.parse(fs.readFileSync(path.join(D, 'voice/out/dur.json'), 'utf8'));
const words = JSON.parse(fs.readFileSync(path.join(D, 'voice/out/words.json'), 'utf8'));
const lines = Object.fromEntries(JSON.parse(fs.readFileSync(path.join(D, 'voice/lines.json'), 'utf8')).map(l => [l.id, l]));
const { V, H, DUR } = TL.layout(dur);
let bad = 0; const err = s => { console.error(s); bad = 1; };
const voice = Object.values(V).sort((a, b) => a.t - b.t).map(v => ({ ...v, text: lines[v.id].text }));
voice.forEach((v, i) => { if (i && v.t < voice[i - 1].t1 + 0.15) err(`voice overlap: ${voice[i - 1].id} ends ${voice[i - 1].t1}, ${v.id} starts ${v.t}`); });
const clean = s => s.toLowerCase().replace(/[^a-z0-9]/g, '');
const wordAt = (line, w) => { const x = words[line].find(x => clean(x[0]) === clean(w)); if (!x) throw new Error(`word ${w} not in ${line}`); return +(V[line].t + Math.max(0, x[1])).toFixed(3); };
const W = Object.fromEntries(TL.WORDS.map(([k, l, w]) => [k, wordAt(l, w)]));
// captions
const GAP = 0.084, CPS = 17, MAXD = 7, MIND = 1;
const nchar = s => s.replace(/\n/g, '').length;
const cues = [];
for (const s of TL.SUBS) {
  const pv = cues.at(-1);
  if (pv && pv.hold) pv.t1 = +(pv.t0 + pv.hold).toFixed(3);
  const t0 = s.from === '@prev' ? +(pv.t1 + GAP + 0.001).toFixed(3) : s.from ? +(wordAt(s.line, s.from) - 0.08).toFixed(3) : V[s.line].t;
  cues.push({ id: s.id, line: s.line, text: s.text, lines: s.text.split('\n'), burn: s.burn !== false, hold: s.hold, t0 });
}
cues.forEach((c, i) => {
  const nx = cues[i + 1], v = V[c.line], need = nchar(c.text) / CPS;
  const limit = nx ? nx.t0 - GAP - 0.001 : DUR;
  if (c.hold) { c.t1 = +(c.t0 + c.hold).toFixed(3); return; }
  let t1 = nx && nx.line === c.line ? nx.t0 - GAP - 0.001 : Math.max(v.t1 + 0.5, c.t0 + need + 0.05);
  t1 = Math.min(t1, limit, c.t0 + MAXD); t1 = Math.max(t1, Math.min(limit, c.t0 + Math.max(MIND, need + 0.05)));
  c.t1 = +t1.toFixed(3);
});
cues.forEach((c, i) => {
  const d = c.t1 - c.t0, cps = nchar(c.text) / d, nx = cues[i + 1];
  c.cps = +cps.toFixed(2);
  if (c.lines.length > 2) err(`caption ${c.id}: ${c.lines.length} lines`);
  for (const l of c.lines) if (l.length > 42) err(`caption ${c.id}: line of ${l.length} chars: ${l}`);
  if (cps > CPS) err(`caption ${c.id}: ${cps.toFixed(1)} chars/s`);
  if (d < MIND || d > MAXD) err(`caption ${c.id}: ${d.toFixed(2)} s`);
  if (nx && nx.t0 - c.t1 < GAP - 1e-4) err(`caption ${c.id}: gap ${(nx.t0 - c.t1).toFixed(3)} s to ${nx.id}`);
});
const ev = TL.foley(H, W);
fs.mkdirSync(path.join(D, 'out'), { recursive: true });
cues.forEach(c => delete c.hold);
fs.writeFileSync(path.join(D, 'out/cues_srt.json'), JSON.stringify(cues.map(c => ({ t0: c.t0, t1: c.t1, text: c.text })), null, 1));
fs.writeFileSync(path.join(D, 'out/timeline.json'), JSON.stringify({ dur: DUR, fps: TL.FPS, hit: H, words: W, voice, cues, ev }, null, 1));
for (const c of cues) console.log(c.id, c.t0.toFixed(2), '→', c.t1.toFixed(2), `(${(c.t1 - c.t0).toFixed(2)} s, ${c.cps} cps${c.burn ? '' : ', not burned'})`, c.text.replace('\n', ' / '));
const nw = voice.reduce((a, v) => a + v.text.split(/\s+/).filter(Boolean).length, 0) - 2;   // L16 is spoken as "Trusted Segments"
console.log(`dur ${DUR} s · ${nw} words · ${(nw / DUR * 60).toFixed(1)} wpm`);
console.log('hits', JSON.stringify(H));
process.exit(bad);
