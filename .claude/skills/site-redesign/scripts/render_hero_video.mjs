#!/usr/bin/env node
/* render_hero_video.mjs — render the scroll-scrubbed cover (GLM canvas backdrop) to self-hosted hero footage.
   Generalised from deliverables/misb_redesign_2026-10-15/research/render_hero_video.mjs (MISB v3) and the
   GTM People build. This is the no-key path; Kling/Higgsfield footage simply overwrites the same files.
   usage: node render_hero_video.mjs --site <dir> [--url http://localhost:8793/] [--sizes 1440x900,390x844]
                                     [--seconds 11] [--fps 30] [--stage "[data-stage]"] [--help]
   inputs:  the site served at --url (python3 -m http.server 8793 --directory <site>); main.js must honour
            ?record=1 by exposing window.__tick(frame) and drawing the cover stage only; ffmpeg with libx264 + libvpx.
   outputs: <site>/assets/hero.mp4|webm (first size), hero-m.mp4|webm (second size, portrait), hero.jpg poster
            (frame 30 of the first size), hero.json { ready:true, landscape, portrait, poster, seconds, fps, sizes }.
   No secrets read or printed. */
import { createRequire } from 'node:module';
import { mkdirSync, rmSync, writeFileSync, statSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { resolve, join } from 'node:path';

const arg = (k, d) => { const i = process.argv.indexOf(k); return i > -1 ? process.argv[i + 1] : d; };
if (process.argv.includes('--help') || process.argv.includes('-h')) {
  console.log('render_hero_video.mjs --site <dir> [--url http://localhost:8793/] [--sizes 1440x900,390x844] [--seconds 11] [--fps 30] [--stage "[data-stage]"]');
  console.log('Renders the ?record=1 cover deterministically through Chromium + ffmpeg into <site>/assets/hero.* and hero.json (Kling-ready slot).');
  process.exit(0);
}
const site = resolve(arg('--site', 'site')) + '/';
const base = arg('--url', 'http://localhost:8793/');
const sizes = arg('--sizes', '1440x900,390x844').split(',').map((s) => s.split('x').map(Number));
const FPS = Number(arg('--fps', '30')), SEC = Number(arg('--seconds', '11')), N = FPS * SEC;
const STAGE = arg('--stage', '[data-stage]');
const tmp = '/tmp/hero-render/';
process.env.PLAYWRIGHT_BROWSERS_PATH ||= '/opt/pw-browsers';
const require = createRequire(import.meta.url);
let pw; for (const p of ['/opt/node-tools/node_modules/playwright', resolve('node_modules/playwright'), '/tmp/pwtest/node_modules/playwright', 'playwright']) { try { pw = require(p); break; } catch {} }
if (!pw) { console.error('playwright not found (npm i playwright@1.56 in /tmp/pwtest or the repo)'); process.exit(2); }
const { chromium } = pw;
const ff = (args) => execFileSync('ffmpeg', ['-y', '-hide_banner', '-loglevel', 'error', ...args]);
const kb = (f) => (statSync(f).size / 1024).toFixed(0) + ' KB';
mkdirSync(join(site, 'assets'), { recursive: true });
const b = await chromium.launch();
async function record(name, [w, h], mobile) {
  const dir = tmp + name + '/'; rmSync(dir, { recursive: true, force: true }); mkdirSync(dir, { recursive: true });
  const p = await b.newPage({ viewport: { width: w, height: h }, isMobile: mobile, hasTouch: mobile, deviceScaleFactor: 1 });
  await p.goto(base + '?record=1', { waitUntil: 'load' }); await p.waitForTimeout(800);
  const stage = p.locator(STAGE); const box = await stage.boundingBox();
  if (!box) throw new Error(`stage ${STAGE} not found at ${base}?record=1`);
  for (let i = 0; i < N; i++) { await p.evaluate((f) => window.__tick(f), i); await p.waitForTimeout(8); await stage.screenshot({ path: dir + String(i).padStart(4, '0') + '.png' }); }
  await p.close();
  const mp4 = join(site, 'assets', name + '.mp4'), webm = join(site, 'assets', name + '.webm');
  ff(['-framerate', String(FPS), '-i', dir + '%04d.png', '-an', '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2', '-c:v', 'libx264', '-preset', 'slow', '-crf', '31', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', mp4]);
  ff(['-framerate', String(FPS), '-i', dir + '%04d.png', '-an', '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2', '-c:v', 'libvpx-vp9', '-b:v', '0', '-crf', '47', '-row-mt', '1', '-pix_fmt', 'yuv420p', webm]);
  if (name === 'hero') ff(['-i', dir + '0030.png', '-vf', 'scale=960:-2', '-q:v', '7', join(site, 'assets', 'hero.jpg')]);
  console.log(name, Math.round(box.width) + 'x' + Math.round(box.height), kb(mp4) + ' mp4,', kb(webm) + ' webm');
  return { mp4: statSync(mp4).size, webm: statSync(webm).size };
}
const d = await record('hero', sizes[0], false);
const m = sizes[1] ? await record('hero-m', sizes[1], true) : null;
await b.close();
console.log('hero.jpg', kb(join(site, 'assets', 'hero.jpg')));
writeFileSync(join(site, 'assets', 'hero.json'), JSON.stringify({ ready: true, landscape: 'hero.mp4', portrait: m ? 'hero-m.mp4' : 'hero.mp4', poster: 'hero.jpg', seconds: SEC, fps: FPS,
  source: 'self-rendered from js/backdrop.js via site-redesign/scripts/render_hero_video.mjs; Kling-ready: overwrite the mp4/webm pairs, keep ready:true', sizes: { hero: d, 'hero-m': m } }) + '\n');
console.log('hero.json ready = true');
