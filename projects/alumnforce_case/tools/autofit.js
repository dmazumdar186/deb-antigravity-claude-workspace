// Per-slide auto-fit: measures an UNBAKED copy of deck.html, finds the largest zoom per slide at which no content
// crosses the footer, then bakes data-zoom attributes + CSS into deck.html. Idempotent: strips any previous bake first.
const { chromium } = require('playwright'); const fs = require('fs'); const os = require('os'); const path = require('path');
const strip = h => h.replace(/\/\*autofit\*\/[\s\S]*?(?=<\/style>)/, '').replace(/ data-zoom="[0-9.]+"/g, '');
(async () => {
  const src = strip(fs.readFileSync('deck.html', 'utf8'));
  const tmp = path.join(os.tmpdir(), 'deck_unbaked_' + process.pid + '.html'); fs.writeFileSync(tmp, src);
  const b = await chromium.launch({ executablePath: process.env.CHROME || '/opt/pw-browsers/chromium-1194/chrome-linux/chrome', args: ['--no-sandbox'] });
  const p = await b.newPage({ viewport: { width: 1280, height: 720 } });
  await p.goto('file://' + tmp);
  const zooms = await p.evaluate(() => {
    const out = [];
    document.querySelectorAll('section.slide').forEach((s, i) => {
      const top = () => s.getBoundingClientRect().top; const foot = s.querySelector('.foot');
      const limit = () => (foot ? foot.getBoundingClientRect().top - top() - 6 : 720 - 16);
      const bottom = () => { let m = 0; s.querySelectorAll('p,li,td,th,pre,h1,h2,h3,.big,.legend,.card,table').forEach(e => { if (e.closest('.foot')) return; m = Math.max(m, e.getBoundingClientRect().bottom - top()); }); return m; };
      const setz = v => s.querySelectorAll(':scope > *:not(.foot)').forEach(e => e.style.zoom = v.toFixed(2));
      let z = 1.0; while (bottom() > limit() && z > 0.6) { z -= 0.02; setz(z); }
      while (z < 1) { const t = +(z + 0.01).toFixed(2); setz(t); if (bottom() > limit()) { setz(z); break; } z = t; }
      out.push({ slide: i + 1, zoom: +z.toFixed(2), bottom: Math.round(bottom()), limit: Math.round(limit()) });
    });
    return out;
  });
  await b.close(); fs.unlinkSync(tmp);
  console.log(zooms.map(x => `${x.slide}: zoom ${x.zoom} bottom ${x.bottom}/${x.limit}`).join('\n'));
  const secs = src.split(/(?=<section class="slide)/); let k = 0;
  for (let i = 1; i < secs.length; i++) { const z = zooms[k++].zoom; if (z < 1) secs[i] = secs[i].replace(/^<section class="slide([^"]*)"([^>]*)>/, (m, c, rest) => `<section class="slide${c}"${rest} data-zoom="${z}">`); }
  const rules = [...new Set(zooms.filter(z => z.zoom < 1).map(z => z.zoom))].map(z => `section[data-zoom="${z}"] > *:not(.foot){zoom:${z}}`).join('\n');
  fs.writeFileSync('deck.html', secs.join('').replace('</style>', `/*autofit*/\n${rules}\n</style>`));
})();
