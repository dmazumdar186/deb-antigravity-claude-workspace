// fact_gate_render.js
// description: Headless Chromium render helper for fact_gate.py. Deliberately separate from the finder's
//              site_marker_fetch.js so the gate never shares a fetch path (or its bugs) with the finder.
// inputs:  one JSON job on stdin: {jobs:[{url, timeout_ms?}]}
// outputs: JSON on stdout: [{url, status, final_url, html, text, all_text, links:[{href,text,region}],
//          imgs:[{alt,title,src}], viewport_meta, error?}]
//          text = visible innerText; all_text = textContent (includes collapsed menus / hidden dropdowns)
const { chromium } = require('playwright');
const UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36';
(async () => {
  const job = JSON.parse(require('fs').readFileSync(0, 'utf8'));
  const browser = await chromium.launch();
  const out = [];
  for (const j of job.jobs) {
    const r = { url: j.url };
    const ctx = await browser.newContext({ viewport: { width: 1366, height: 900 }, userAgent: UA, ignoreHTTPSErrors: true });
    try {
      const page = await ctx.newPage();
      const resp = await page.goto(j.url, { waitUntil: 'domcontentloaded', timeout: j.timeout_ms || 40000 });
      try { await page.waitForLoadState('networkidle', { timeout: 6000 }); } catch (e) { /* busy pages: keep what rendered */ }
      r.status = resp ? resp.status() : 0;
      r.final_url = page.url();
      r.html = await page.content();
      r.text = await page.innerText('body').catch(() => '');
      const d = await page.evaluate(() => {
        const reg = (el) => el.closest('nav,header,footer,[role=navigation],[role=contentinfo],[class*=menu],[id*=menu],[class*=footer],[id*=footer],[class*=nav]') ? 'navfoot' : 'body';
        const links = [...document.querySelectorAll('a[href]')].slice(0, 1500).map(a => ({ href: a.href, text: (a.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 200), region: reg(a) }));
        const imgs = [...document.querySelectorAll('img')].slice(0, 500).map(i => ({ alt: i.alt || '', title: i.title || '', src: i.currentSrc || i.src || '' }));
        return { all_text: (document.body ? document.body.textContent : '').replace(/\s+/g, ' '), links, imgs,
                 viewport_meta: !!document.querySelector('meta[name=viewport i]') };
      });
      Object.assign(r, d);
    } catch (e) { r.error = String(e).slice(0, 300); }
    await ctx.close();
    out.push(r);
  }
  await browser.close();
  process.stdout.write(JSON.stringify(out));
})().catch(e => { process.stderr.write(String(e)); process.exit(1); });
