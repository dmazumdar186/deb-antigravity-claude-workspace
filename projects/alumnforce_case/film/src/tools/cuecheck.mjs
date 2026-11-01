// Every key action in timeline.js sits on the 72 BPM grid (half-beat resolution); voice lines start on the grid.
// Word landings (numbers) follow the narrator, and the score places its accent on the same time (mix.py reads timeline.json).
// usage: node tools/cuecheck.mjs <film_dir>   exits 1 if any action is off the grid by more than 1 ms
import path from 'path'; import { pathToFileURL } from 'url';
const D = path.resolve(process.argv[2] || '.');
const TL = await import(pathToFileURL(path.join(D, 'timeline.js')).href);
let worst = 0, bad = 0;
const chk = (name, t) => { const q = Math.round(t / (TL.BEAT / 2)) * TL.BEAT / 2, off = Math.abs(t - q) * 1000; worst = Math.max(worst, off); if (off > 1) { console.log(`off grid: ${name} ${t} (${off.toFixed(1)} ms)`); bad = 1; } };
for (const [k, t] of Object.entries(TL.HIT)) if (k !== 'typeOn' && !k.startsWith('hush')) chk(k, t);
for (const v of TL.VOICE) chk(v.id, v.t);
console.log(`cuecheck: ${Object.keys(TL.HIT).length - 1} actions + ${TL.VOICE.length} voice lines, worst offset ${worst.toFixed(2)} ms (typeOn and the two hushes are off-grid by design: the hook starts before the first beat; the silences open a quarter beat early, like a breath)`);
process.exit(bad);
