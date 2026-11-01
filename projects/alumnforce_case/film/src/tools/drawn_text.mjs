// Drawn-text manifest: renders every frame of the page (24 fps) and records every glyph run that film.js's drawText() painted
// (it is the only fillText in the page). Writes out/drawn_text.json: [{text, t_start, t_end, x, y, px, px_max, frames}],
// one entry per distinct text and size class; x, y, px are taken at its first frame (screen pixels, baseline).
// usage: node tools/drawn_text.mjs <film_dir> [--out file]      (run from the library root)
import fs from 'fs'; import path from 'path';
import { openDemo, closeServer } from '../../../core/render/page.mjs';
const D = path.resolve(process.argv[2] || '.');
const oi = process.argv.indexOf('--out'), OUT = oi > 0 ? process.argv[oi + 1] : path.join(D, 'out/drawn_text.json');
const { browser, page } = await openDemo(D, { q: '' });
const dur = await page.evaluate(() => window.DUR), fps = 24, n = Math.round(dur * fps);
const M = new Map();
for (let i = 0; i < n; i++) {
  const t = +(i / fps).toFixed(5);
  const d = await page.evaluate(t => { window.render(t); return window.__DRAWN; }, t);
  for (const r of d) {
    if (r.y < 0 || r.y - r.px * 0.8 > 1080 || r.x < -1500 || r.x > 3400) continue;   // baseline outside the frame: nothing visible
    const key = r.text + '|' + Math.round(Math.log2(Math.max(r.px, 1)) * 2);      // size classes a half-octave apart
    const e = M.get(key);
    if (!e) M.set(key, { text: r.text, t_start: t, t_end: +(t + 1 / fps).toFixed(4), x: r.x, y: r.y, px: r.px, px_max: r.px, frames: 1 });
    else { e.t_end = +(t + 1 / fps).toFixed(4); e.px = Math.min(e.px, r.px); e.px_max = Math.max(e.px_max, r.px); e.frames++; }
  }
}
await browser.close(); closeServer();
const list = [...M.values()].sort((a, b) => a.t_start - b.t_start || a.y - b.y);
fs.writeFileSync(OUT, JSON.stringify(list, null, 1));
const small = list.filter(e => e.px < 28 && !/^[\s—]*$/.test(e.text));
console.log(`drawn_text: ${list.length} entries over ${n} frames → ${OUT}; under 28 px: ${small.length}`);
for (const e of small.slice(0, 40)) console.log(`  ${e.px}px ${e.t_start}-${e.t_end} ${JSON.stringify(e.text)}`);
