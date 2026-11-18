// Record the Trusted Segments concept walkthrough as an MP4 (<= 90 s).
// Usage: node projects/alumnforce_case/tools/record_demo.js
// Drives the prototype's own tour (window.tour.go(n)), then scrolls build.html.
// Output: projects/alumnforce_case/ux_concept/demo.mp4 (overwritten on re-run; idempotent).
const { chromium } = require('playwright');
const { execFileSync } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const DIR = path.resolve(__dirname, '..', 'ux_concept');
const OUT = path.join(DIR, 'demo.mp4');
const W = 1280, H = 720;
const STEP_MS = 9500;

const card = (title, sub) => `<!doctype html><meta charset="utf-8"><body style="margin:0;height:100vh;display:flex;
flex-direction:column;justify-content:center;align-items:center;background:#0f2a3d;color:#fff;
font-family:Inter,'Helvetica Neue',Arial,sans-serif;text-align:center">
<div style="font-size:15px;letter-spacing:3px;text-transform:uppercase;color:#9fc3dd">Concept · Trusted Segments</div>
<div style="font-size:44px;font-weight:700;margin:18px 40px 14px">${title}</div>
<div style="font-size:20px;color:#cfe0ec;max-width:900px">${sub}</div></body>`;

(async () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'tsdemo-'));
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: W, height: H }, recordVideo: { dir: tmp, size: { width: W, height: H } } });
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(String(e)));
  try {
    await page.setContent(card('Cleaned values, visible to admins', 'How a list shows what was cleaned, how admins review only what is uncertain, and how it gets built.'));
    await page.waitForTimeout(3500);

    await page.goto('file://' + path.join(DIR, 'index.html'));
    await page.waitForTimeout(800);
    const n = await page.evaluate(() => (window.tour && window.tour.count) || 0);
    if (!n) throw new Error('window.tour missing');
    for (let i = 1; i <= n; i++) {
      await page.evaluate(k => window.tour.go(k), i);
      await page.waitForTimeout(STEP_MS);
    }

    await page.goto('file://' + path.join(DIR, 'build.html'));
    await page.waitForTimeout(2500);
    const total = await page.evaluate(() => document.documentElement.scrollHeight - innerHeight);
    for (let s = 0; s < 10; s++) {
      await page.evaluate(y => scrollTo({ top: y, behavior: 'smooth' }), Math.round(total * (s + 1) / 10));
      await page.waitForTimeout(1000);
    }
    await page.setContent(card('Two decisions for you', 'Originals on hover, or a visible second column? Use suggested clean-ups before an admin confirms, or only after?'));
    await page.waitForTimeout(4000);
  } finally {
    const video = page.video();
    await ctx.close();
    await browser.close();
    if (errors.length) console.error('page errors:', errors);
    const webm = await video.path();
    execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-i', webm, '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
      '-preset', 'medium', '-crf', '23', '-movflags', '+faststart', OUT]);
    fs.rmSync(tmp, { recursive: true, force: true });
  }
  const dur = execFileSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', OUT], { encoding: 'utf-8' }).trim();
  console.log(`wrote ${OUT} (${(fs.statSync(OUT).size / 1e6).toFixed(1)} MB, ${Number(dur).toFixed(1)} s)`);
  if (Number(dur) > 95) { console.error('FAIL: longer than 90 s'); process.exit(2); }
})();
