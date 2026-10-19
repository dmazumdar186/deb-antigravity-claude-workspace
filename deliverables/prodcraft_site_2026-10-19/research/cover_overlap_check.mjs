// cover_overlap_check.mjs — at 19 viewports × cover progress 0/.3/.55/.8/1: visible plates, rail and headline column never intersect;
// plates inside the viewport and ≥ 6 px under the header; frame = image; rail fully inside the viewport. Exit 1 on any failure.
import pw from '/opt/node-tools/node_modules/playwright/index.js'; const { chromium } = pw;
const base = process.argv[2] || 'http://localhost:8793/'; const b = await chromium.launch(); let fail = 0, n = 0;
const VP = [[360,640],[390,844],[412,915],[844,390],[600,960],[960,600],[820,1180],[1180,820],[1024,1366],[1366,1024],[1280,720],[1366,768],[1536,864],[1440,900],[1882,832],[1920,1080],[2560,1440],[3840,2160],[1080,1920]];
for (const [w, h] of VP) {
  const p = await b.newPage({ viewport: { width: w, height: h } }); await p.goto(base + '?canvas=1', { waitUntil: 'load' }); await p.waitForTimeout(600);
  for (const f of [0, 0.3, 0.55, 0.8, 1]) {
    await p.evaluate((f) => { document.documentElement.style.scrollBehavior = 'auto'; const c = document.querySelector('[data-cover]'); scrollTo(0, c.offsetTop + (c.offsetHeight - innerHeight) * f); }, f);
    await p.waitForTimeout(650);
    const r = await p.evaluate(() => {
      const cover = document.querySelector('[data-cover]'); const errs = [];
      if (getComputedStyle(cover).visibility === 'hidden') return { skip: 'cover out', errs };
      const box = (el) => { const r = el.getBoundingClientRect(); return { l: r.left, t: r.top, r: r.right, b: r.bottom, w: r.width, h: r.height }; };
      const shown = (el) => { if (!el) return false; let e = el; while (e && e !== document.body) { const cs = getComputedStyle(e); if (cs.display === 'none' || cs.visibility === 'hidden') return false; e = e.parentElement; } return box(el).w > 0; };
      const hit = (a, c) => a.l < c.r && c.l < a.r && a.t < c.b && c.t < a.b;
      const hdr = document.querySelector('.hdr').getBoundingClientRect().bottom;
      const rail = document.querySelector('.rail'), body = document.querySelector('.cover__body');
      const parts = [];
      // headline column = the body's content (kicker, title, beats, CTAs), not its padding
      const bodyItems = [...body.querySelectorAll('.cover__kicker,.cover__title,.beat.is-on,.cover__ctas')].filter(shown).map(box);
      if (shown(rail)) { const rb = box(rail); parts.push(['rail', rb]); if (rb.t < 0 || rb.b > innerHeight + 0.5 || rb.l < 0 || rb.r > innerWidth + 0.5) errs.push('rail outside viewport ' + JSON.stringify(rb)); }
      for (const f of document.querySelectorAll('.cplate')) {
        if (!shown(f) || +getComputedStyle(f).opacity < 0.5) continue;
        const fb = box(f); parts.push(['plate' + f.dataset.plate, fb]);
        const i = f.querySelector('img'), ib = box(i), pad = parseFloat(getComputedStyle(f).paddingLeft);
        if (Math.abs(fb.w - 2 * pad - 2 - ib.w) > 1.5) errs.push('frame≠image plate' + f.dataset.plate);
        if (fb.t < hdr + 6 || fb.b > innerHeight + 0.5) errs.push('plate' + f.dataset.plate + ' outside stage ' + Math.round(fb.t) + '/' + Math.round(fb.b));
      }
      for (let x = 0; x < parts.length; x++) {
        for (const bi of bodyItems) if (hit(parts[x][1], bi)) errs.push(parts[x][0] + ' × headline column');
        for (let y = x + 1; y < parts.length; y++) if (hit(parts[x][1], parts[y][1])) errs.push(parts[x][0] + ' × ' + parts[y][0]);
      }
      return { errs };
    });
    n++; if (r.errs.length) { fail++; console.log('FAIL', w + 'x' + h, 'p' + f, r.errs.join('; ')); }
  }
  await p.close();
}
await b.close(); console.log(`${n - fail}/${n} states clean`); process.exit(fail ? 1 : 0);
