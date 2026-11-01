// v2 cue check: every key action and voice start sits on a whole frame (1/24 s), actions are in story order, and every
// key foley hit lands on a visual action (the same timeline.json value). usage: node tools/cuecheck.mjs <film_dir>
import fs from 'fs'; import path from 'path';
const D = path.resolve(process.argv[2] || '.');
const T = JSON.parse(fs.readFileSync(path.join(D, 'out/timeline.json'), 'utf8'));
let bad = 0, worst = 0;
const chk = (name, t) => { const off = Math.abs(t * 24 - Math.round(t * 24)) / 24 * 1000; worst = Math.max(worst, off); if (off > 1) { console.log(`off frame: ${name} ${t}`); bad = 1; } };
for (const [k, t] of Object.entries(T.hit)) if (k !== 'typeOn') chk(k, t);
for (const v of T.voice) chk(v.id, v.t);
const order = ['slots', 'lightOn', 'drop1', 'cityLit', 'spell', 'climb', 'hush1', 'drop2', 'front', 'pair', 'quote', 'hush2', 'index', 'six', 'off', 'thesis', 'title', 'endCard'];
order.forEach((k, i) => { if (i && !(T.hit[k] > T.hit[order[i - 1]])) { console.log(`out of order: ${order[i - 1]} ${T.hit[order[i - 1]]} ≥ ${k} ${T.hit[k]}`); bad = 1; } });
const hits = [...Object.values(T.hit), ...Object.values(T.words)];
const fol = T.ev.filter(([, type]) => ['loupe', 'land', 'switch', 'whoosh', 'pen', 'front'].includes(type));
fol.filter(([t]) => !hits.some(h => Math.abs(h - t) < 0.06)).forEach(([t, type]) => { console.log(`foley ${type} at ${t} has no visual action`); bad = 1; });
console.log(`cuecheck: ${Object.keys(T.hit).length - 1} actions + ${T.voice.length} voice starts on whole frames (worst ${worst.toFixed(2)} ms), ${order.length} in story order, ${fol.length} key foley hits on their actions`);
process.exit(bad);
