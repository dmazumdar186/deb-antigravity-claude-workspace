const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch({ executablePath: process.env.CHROME || '/opt/pw-browsers/chromium-1194/chrome-linux/chrome', args:['--no-sandbox'] });
  const p = await b.newPage({ viewport: { width: 1280, height: 720 } });
  await p.goto('file://' + process.cwd() + '/deck.html');
  const r = await p.evaluate(() => [...document.querySelectorAll('section.slide')].map((s,i) => {
    const foot = s.querySelector('.foot'); const limit = foot ? foot.getBoundingClientRect().top - s.getBoundingClientRect().top - 6 : 720 - 18;
    let maxBottom = 0; s.querySelectorAll(':scope > *:not(.foot)').forEach(e => { const r=e.getBoundingClientRect(); maxBottom=Math.max(maxBottom, r.bottom - s.getBoundingClientRect().top); });
    // also check nested content overflow (cards with inner text beyond)
    let inner=0; s.querySelectorAll('*').forEach(e=>{ if(e.classList.contains('foot'))return; const r=e.getBoundingClientRect(); inner=Math.max(inner, r.bottom - s.getBoundingClientRect().top); });
    return { slide: i+1, contentBottom: Math.round(Math.max(maxBottom,inner)), limit: Math.round(limit), over: Math.round(Math.max(maxBottom,inner) - limit) };
  }));
  console.log(r.map(x => `${x.slide}: bottom ${x.contentBottom} / limit ${x.limit} -> ${x.over>0?'OVER '+x.over:'ok'}`).join('\n'));
  await b.close();
})();
