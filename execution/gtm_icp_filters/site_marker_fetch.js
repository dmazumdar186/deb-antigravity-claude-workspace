// site_marker_fetch.js
// description: Headless Chromium fetch helper for medtech_510k_triggers.py (Node Playwright is the installed binding).
// inputs: one JSON job on stdin: {jobs:[{url, mode:"full"|"text", desk_png?, mob_png?}]}
// outputs: JSON on stdout: [{url, status, final_url, html?, text, mobile_viewport?, error?}]
const { chromium, devices } = require('playwright');
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36';
(async () => {
  const job = JSON.parse(require('fs').readFileSync(0, 'utf8'));
  const browser = await chromium.launch();
  const out = [];
  for (const j of job.jobs) {
    const r = { url: j.url };
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, userAgent: UA, ignoreHTTPSErrors: true });
    try {
      const page = await ctx.newPage();
      const resp = await page.goto(j.url, { waitUntil: 'domcontentloaded', timeout: 45000 });
      await page.waitForTimeout(j.mode === 'full' ? 2500 : 1500);
      r.status = resp ? resp.status() : 0; r.final_url = page.url();
      r.text = await page.innerText('body');
      if (j.mode === 'full') {
        r.html = await page.content();
        if (j.desk_png) { await page.screenshot({ path: j.desk_png }); r.desk_png = j.desk_png; }
      }
    } catch (e) { r.error = String(e).slice(0, 200); }
    await ctx.close();
    if (j.mode === 'full' && !r.error) {
      const m = await browser.newContext({ ...devices['iPhone 13'], ignoreHTTPSErrors: true });
      try {
        const p = await m.newPage();
        await p.goto(j.url, { waitUntil: 'domcontentloaded', timeout: 45000 }); await p.waitForTimeout(2000);
        r.mobile_viewport = await p.evaluate(() => !!document.querySelector('meta[name=viewport]'));
        if (j.mob_png) { await p.screenshot({ path: j.mob_png }); r.mob_png = j.mob_png; }
      } catch (e) { r.mobile_error = String(e).slice(0, 200); }
      await m.close();
    }
    out.push(r);
  }
  await browser.close();
  process.stdout.write(JSON.stringify(out));
})().catch(e => { process.stderr.write(String(e)); process.exit(1); });
