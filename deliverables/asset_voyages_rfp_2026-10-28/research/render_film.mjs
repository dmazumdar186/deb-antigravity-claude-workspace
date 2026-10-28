#!/usr/bin/env node
/* render_film.mjs — render the « Du brief au retour » film (site/js/film.js via index.html?record=1) to the
   scrubbable hero files. Adapted from .claude/skills/site-redesign/scripts/render_hero_video.mjs:
   time = frame / FPS over 30 s, short GOP (-g 6) so seeking is instant, poster = frame 0.
   usage: node render_film.mjs --site ../site --url http://localhost:8793/ [--fps 24]
   outputs: assets/hero.mp4|webm (1920x1080), hero-m.mp4|webm (1080x1350), hero.jpg, hero-m.jpg, hero.json */
import { createRequire } from 'node:module';
import { mkdirSync, rmSync, writeFileSync, statSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { resolve, join } from 'node:path';
const arg = (k, d) => { const i = process.argv.indexOf(k); return i > -1 ? process.argv[i + 1] : d; };
const site = resolve(arg('--site', '../site')), base = arg('--url', 'http://localhost:8793/');
const FPS = Number(arg('--fps', '24')), SEC = 30, N = FPS * SEC + 1;
process.env.PLAYWRIGHT_BROWSERS_PATH ||= '/opt/pw-browsers';
const require = createRequire(import.meta.url);
let pw; for (const p of ['/opt/node-tools/node_modules/playwright', '/tmp/pwtest/node_modules/playwright', 'playwright']) { try { pw = require(p); break; } catch {} }
const ff = (a) => execFileSync('ffmpeg', ['-y', '-hide_banner', '-loglevel', 'error', ...a]);
const kb = (f) => (statSync(f).size / 1024).toFixed(0) + ' KB';
const b = await pw.chromium.launch();
async function record(name, w, h) {
  const dir = `/tmp/film-render/${name}/`; rmSync(dir, { recursive: true, force: true }); mkdirSync(dir, { recursive: true });
  const p = await b.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: 1 });
  await p.goto(base + '?record=1&fps=' + FPS, { waitUntil: 'load' }); await p.evaluate(() => window.__ready); await p.waitForTimeout(300);
  for (let i = 0; i < N; i++) { await p.evaluate((f) => window.__tick(f), i); await p.screenshot({ path: dir + String(i).padStart(4, '0') + '.png', type: 'png' }); }
  await p.close();
  const a = join(site, 'assets', name);
  ff(['-framerate', String(FPS), '-i', dir + '%04d.png', '-an', '-c:v', 'libx264', '-preset', 'slow', '-crf', '30', '-g', '6', '-keyint_min', '6', '-sc_threshold', '0', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', a + '.mp4']);
  ff(['-framerate', String(FPS), '-i', dir + '%04d.png', '-an', '-c:v', 'libvpx-vp9', '-b:v', '0', '-crf', '38', '-g', '6', '-row-mt', '1', '-deadline', 'good', '-cpu-used', '2', '-pix_fmt', 'yuv420p', a + '.webm']);
  ff(['-i', dir + '0000.png', '-q:v', '4', a + '.jpg']);
  console.log(name, w + 'x' + h, kb(a + '.mp4'), 'mp4,', kb(a + '.webm'), 'webm,', kb(a + '.jpg'), 'poster');
  return { mp4: statSync(a + '.mp4').size, webm: statSync(a + '.webm').size };
}
const d = await record('hero', 1920, 1080);
const m = await record('hero-m', 1080, 1350);
await b.close();
writeFileSync(join(site, 'assets', 'hero.json'), JSON.stringify({ ready: true, landscape: 'hero.mp4', portrait: 'hero-m.mp4', poster: 'hero.jpg', posterPortrait: 'hero-m.jpg', seconds: SEC, fps: FPS, keyframes: [0, 5, 10, 15, 20, 25, 30],
  source: 'self-rendered from js/film.js via research/render_film.mjs; overwrite the mp4/webm pairs with produced footage, keep ready:true', sizes: { hero: d, 'hero-m': m } }) + '\n');
console.log('hero.json written');
