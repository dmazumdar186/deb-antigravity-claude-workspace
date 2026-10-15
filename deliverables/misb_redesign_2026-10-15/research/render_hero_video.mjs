// Render the v3 cover journey (GLM canvas backdrop, js/backdrop.js) to hero.mp4 / hero-m.mp4 / hero.jpg deterministically.
// Adapted from deliverables/gtm_people_redesign_2026-10-06/research/render_hero_video.mjs.
// Usage: node render_hero_video.mjs http://localhost:8793/   (serve site_v3/ first; needs ffmpeg with libx264 + libvpx)
// The site must be served with ?record=1: main.js then exposes window.__tick(frame) and draws the cover stage only.
import { createRequire } from 'node:module'; import { mkdirSync, rmSync, writeFileSync, statSync } from 'node:fs'; import { execFileSync } from 'node:child_process';
const { chromium } = createRequire(import.meta.url)('/opt/node-tools/node_modules/playwright');
process.env.PLAYWRIGHT_BROWSERS_PATH ||= '/opt/pw-browsers';
const base = process.argv[2] || 'http://localhost:8793/';
const site = new URL('../site_v3/', import.meta.url).pathname, tmp = '/tmp/misbv3/frames/';
const FPS = 30, SEC = 11, N = FPS * SEC;
const b = await chromium.launch();
async function record(name, vp, mobile) {
  const dir = tmp + name + '/'; rmSync(dir, { recursive: true, force: true }); mkdirSync(dir, { recursive: true });
  const p = await b.newPage({ viewport: vp, isMobile: mobile, hasTouch: mobile, deviceScaleFactor: 1 });
  await p.goto(base + '?record=1', { waitUntil: 'load' }); await p.waitForTimeout(800);
  const stage = p.locator('[data-stage]'); const box = await stage.boundingBox();
  for (let i = 0; i < N; i++) { await p.evaluate((f) => window.__tick(f), i); await p.waitForTimeout(8); await stage.screenshot({ path: dir + String(i).padStart(4, '0') + '.png' }); }
  await p.close();
  const out = site + 'assets/' + name + '.mp4';
  execFileSync('ffmpeg', ['-y', '-hide_banner', '-loglevel', 'error', '-framerate', String(FPS), '-i', dir + '%04d.png', '-an', '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2', '-c:v', 'libx264', '-preset', 'slow', '-crf', '31', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out]);
  execFileSync('ffmpeg', ['-y', '-hide_banner', '-loglevel', 'error', '-framerate', String(FPS), '-i', dir + '%04d.png', '-an', '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2', '-c:v', 'libvpx-vp9', '-b:v', '0', '-crf', '47', '-row-mt', '1', '-pix_fmt', 'yuv420p', site + 'assets/' + name + '.webm']);
  if (name === 'hero') execFileSync('ffmpeg', ['-y', '-hide_banner', '-loglevel', 'error', '-i', dir + '0030.png', '-vf', 'scale=960:-2', '-q:v', '7', site + 'assets/hero.jpg']);
  const kb = (f) => (statSync(f).size / 1024).toFixed(0) + ' KB';
  console.log(name, Math.round(box.width) + 'x' + Math.round(box.height), kb(out) + ' mp4,', kb(site + 'assets/' + name + '.webm') + ' webm');
  return { mp4: statSync(out).size, webm: statSync(site + 'assets/' + name + '.webm').size };
}
const d = await record('hero', { width: 1440, height: 900 }, false);
const m = await record('hero-m', { width: 390, height: 844 }, true);
await b.close();
console.log('hero.jpg', (statSync(site + 'assets/hero.jpg').size / 1024).toFixed(0) + ' KB');
writeFileSync(site + 'assets/hero.json', JSON.stringify({ ready: true, landscape: 'hero.mp4', portrait: 'hero-m.mp4', poster: 'hero.jpg', seconds: SEC, fps: FPS, source: 'self-rendered from js/backdrop.js (GLM 5.3) via research/render_hero_video.mjs; Kling-ready: overwrite the mp4/webm pairs, keep ready:true', sizes: { hero: d, 'hero-m': m } }) + '\n');
console.log('hero.json ready = true');
