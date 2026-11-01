// Timeline -> out/timeline.json (page, mix.py, checks), out/cues_srt.json (subtitles).
// Reads voice/out/dur.json and voice/out/words.json (tts.py, asr_check.py). Exits 1 on voice overlap or a cue under its minimum.
// usage: node tools/export.mjs <film_dir>
import fs from 'fs'; import path from 'path'; import { pathToFileURL } from 'url';
const D = path.resolve(process.argv[2] || '.');
const TL = await import(pathToFileURL(path.join(D, 'timeline.js')).href);
const dur = JSON.parse(fs.readFileSync(path.join(D, 'voice/out/dur.json'), 'utf8'));
const words = JSON.parse(fs.readFileSync(path.join(D, 'voice/out/words.json'), 'utf8'));
const lines = Object.fromEntries(JSON.parse(fs.readFileSync(path.join(D, 'voice/lines.json'), 'utf8')).map(l => [l.id, l]));
let bad = 0;
const voice = TL.VOICE.map(v => ({ ...v, text: lines[v.id].text, dur: dur[v.id], t1: +(v.t + dur[v.id]).toFixed(3) }));
voice.forEach((v, i) => { if (i && v.t < voice[i - 1].t1 + 0.25) { console.error(`voice overlap: ${voice[i - 1].id} ends ${voice[i - 1].t1}, ${v.id} starts ${v.t}`); bad = 1; } });
if (voice.at(-1).t1 > TL.DUR - 2) { console.error('last line ends too close to the end'); bad = 1; }
const V = Object.fromEntries(voice.map(v => [v.id, v]));
const clean = s => s.toLowerCase().replace(/[^a-z0-9]/g, '');
const wordAt = (line, w) => { const x = words[line].find(x => clean(x[0]) === clean(w)); if (!x) throw new Error(`word ${w} not in ${line}`); return +(V[line].t + Math.max(0, x[1])).toFixed(3); };
const W = Object.fromEntries(TL.WORDS.map(([k, l, w]) => [k, wordAt(l, w)]));
const cues = TL.SUBS.map(s => ({ id: s.id, line: s.line, text: s.text, t0: s.from ? +(wordAt(s.line, s.from) - 0.08).toFixed(3) : V[s.line].t }));
cues.forEach((c, i) => {
  const nx = cues[i + 1], v = V[c.line];
  c.t1 = nx && nx.line === c.line ? nx.t0 : +(v.t1 + 0.6).toFixed(3);
  if (nx && c.t1 > nx.t0 - 0.04) c.t1 = +(nx.t0 - 0.04).toFixed(3);
  // a cue must hold max(1.8 s, its speech + 0.6 s); stretch into the gap when the next line allows it
  if (c.t1 - c.t0 < 2.2 && (!nx || nx.line !== c.line)) c.t1 = +Math.min(c.t0 + 2.2, nx ? nx.t0 - 0.04 : TL.DUR).toFixed(3);
  if (c.t1 - c.t0 < 1.8) { console.error(`cue ${c.id} only ${(c.t1 - c.t0).toFixed(2)} s`); bad = 1; }
});
const ev = TL.foley(TL.HIT, W);
fs.mkdirSync(path.join(D, 'out'), { recursive: true });
fs.writeFileSync(path.join(D, 'out/cues_srt.json'), JSON.stringify(cues.map(c => ({ t0: c.t0, t1: c.t1, text: c.text })), null, 1));
fs.writeFileSync(path.join(D, 'out/timeline.json'), JSON.stringify({ dur: TL.DUR, bpm: TL.BPM, beat: TL.BEAT, hit: TL.HIT, words: W, voice, cues, ev }, null, 1));
for (const c of cues) console.log(c.id.padEnd(5), c.t0.toFixed(2), '→', c.t1.toFixed(2), `(${(c.t1 - c.t0).toFixed(2)} s)`, c.text);
console.log('words', JSON.stringify(W));
process.exit(bad);
