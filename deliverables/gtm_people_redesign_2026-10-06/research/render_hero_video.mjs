// Render the v4 opening stage to hero.mp4 / hero-m.mp4 / hero.jpg deterministically (no external model needed).
// Usage: node render_hero_video.mjs http://localhost:8791/   (serve site/ first; needs ffmpeg with libx264)
import { createRequire } from 'node:module'; import { mkdirSync, rmSync, writeFileSync, statSync, readFileSync } from 'node:fs'; import { execFileSync } from 'node:child_process';
const { chromium } = createRequire(import.meta.url)('/opt/node-tools/node_modules/playwright');
const base = process.argv[2] || 'http://localhost:8789/';
const site = new URL('../site/', import.meta.url).pathname, tmp = new URL('../.tmp/frames/', import.meta.url).pathname;
const FPS = 30, SEC = 12, N = FPS * SEC;
const b = await chromium.launch();
async function record(name, vp, mobile, size) {
  const dir = tmp + name + '/'; rmSync(dir, { recursive: true, force: true }); mkdirSync(dir, { recursive: true });
  const p = await b.newPage({ viewport: vp, isMobile: mobile, hasTouch: mobile, deviceScaleFactor: mobile ? 2 : 1 });
  await p.goto(base + '?record=1' + (size ? '&size=' + size : ''), { waitUntil: 'load' }); await p.waitForTimeout(600);
  const stage = p.locator('[data-stage]'); const box = await stage.boundingBox();
  for (let i = 0; i < N; i++) { await p.evaluate((f) => window.__tick(f), i); await p.waitForTimeout(12); await stage.screenshot({ path: dir + String(i).padStart(4, '0') + '.png' }); }
  await p.close();
  const out = site + 'assets/' + name + '.mp4';
  execFileSync('ffmpeg', ['-y', '-hide_banner', '-loglevel', 'error', '-framerate', String(FPS), '-i', dir + '%04d.png', '-an', '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2', '-c:v', 'libx264', '-preset', 'slow', '-crf', '26', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out]);
  execFileSync('ffmpeg', ['-y', '-hide_banner', '-loglevel', 'error', '-framerate', String(FPS), '-i', dir + '%04d.png', '-an', '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2', '-c:v', 'libvpx-vp9', '-b:v', '0', '-crf', '36', '-row-mt', '1', '-pix_fmt', 'yuv420p', site + 'assets/' + name + '.webm']); // Chromium without H.264 (and Firefox) take the VP9 copy
  if (name === 'hero') execFileSync('ffmpeg', ['-y', '-hide_banner', '-loglevel', 'error', '-i', dir + '0045.png', '-vf', 'scale=720:-2', '-q:v', '6', site + 'assets/hero.jpg']);
  console.log(name, Math.round(box.width) + 'x' + Math.round(box.height), (statSync(out).size / 1024).toFixed(0) + ' KB mp4, ' + (statSync(site + 'assets/' + name + '.webm').size / 1024).toFixed(0) + ' KB webm');
}
await record('hero', { width: 1400, height: 900 }, false, 720);
await record('hero-m', { width: 390, height: 844 }, true, 0);
await b.close();
console.log('hero.jpg', (statSync(site + 'assets/hero.jpg').size / 1024).toFixed(0) + ' KB');
const mf = JSON.parse(readFileSync(site + 'assets/hero.json', 'utf8')); mf.ready = true; mf.poster = 'hero.jpg'; writeFileSync(site + 'assets/hero.json', JSON.stringify(mf) + '\n');
console.log('hero.json ready = true');
