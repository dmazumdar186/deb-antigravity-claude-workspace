#!/usr/bin/env node
// Cache busting + film install. Idempotent. Run before every check/deploy and again when the final film lands.
// 1. (after research/fit_film.py) copies poster.jpg into site/assets/film/, hashes hero.mp4 + hero-phone.mp4, and writes site/assets/film/hero.json
//    = research/film/hero.json + "v" {file: short hash} (the scrub engine appends ?v= to each file);
// 2. rewrites ?v=<hash> on css/styles.css, js/*.js, assets/film/hero.json and assets/film/poster.jpg in every shipped HTML.
// usage: node research/stamp.mjs
import { readFileSync, writeFileSync, copyFileSync, mkdirSync } from 'node:fs'; import { createHash } from 'node:crypto'; import { join } from 'node:path';
const site = new URL('../site/', import.meta.url).pathname; const film = new URL('./film/', import.meta.url).pathname;
const hf = (p) => createHash('sha256').update(readFileSync(p)).digest('hex').slice(0, 8);
mkdirSync(join(site, 'assets/film'), { recursive: true });
const meta = JSON.parse(readFileSync(join(film, 'hero.json'), 'utf8')); meta.v = {};
// mp4s are re-encoded for scrubbing by research/fit_film.py (3:4 on all devices; hero-m.mp4 is not shipped)
copyFileSync(join(film, meta.poster), join(site, 'assets/film', meta.poster)); meta.v.poster = hf(join(film, meta.poster));
meta.phone = 'hero-phone.mp4'; delete meta.portrait;
for (const k of ['landscape', 'phone']) meta.v[k] = hf(join(site, 'assets/film', meta[k]));
// figure extents per keyframe (top, bottom as fraction of the 3:4 frame) for the portrait layout
try { meta.fig = JSON.parse(readFileSync(join(film, 'figure_boxes.json'), 'utf8')).landscape.map((b) => [b.box[1], b.box[3]]); } catch { /* engine falls back to global extents */ }
writeFileSync(join(site, 'assets/film/hero.json'), JSON.stringify(meta, null, 1) + '\n');
const assets = ['css/styles.css', 'js/main.js', 'js/i18n.js', 'js/breath.js', 'assets/film/hero.json', 'assets/film/' + meta.poster];
const h = (a) => hf(join(site, a));
for (const page of ['index.html', 'privacy/index.html', '404.html']) {
  let s = readFileSync(join(site, page), 'utf8');
  for (const a of assets) s = s.replace(new RegExp('(["/])' + a.replace(/[.]/g, '\\.') + '(\\?v=[0-9a-f]+)?"', 'g'), `$1${a}?v=${h(a)}"`);
  writeFileSync(join(site, page), s);
}
console.log('stamped', assets.map((a) => a + '=' + h(a)).join(' '), 'film', JSON.stringify(meta.v));
