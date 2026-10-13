// Overflow check: reports, per slide, the lowest content edge versus the footer line.
// Exit code 0 = no slide overflows; 2 = at least one slide overflows; 1 = the check itself failed.
const { chromium } = require('playwright');
(async () => {
  let b;
  try {
    b = await chromium.launch({ executablePath: process.env.CHROME || '/opt/pw-browsers/chromium-1194/chrome-linux/chrome', args: ['--no-sandbox'] });
    const p = await b.newPage({ viewport: { width: 1280, height: 720 } });
    await p.goto('file://' + process.cwd() + '/deck.html');
    const r = await p.evaluate(() => [...document.querySelectorAll('section.slide')].map((s, i) => {
      const top = s.getBoundingClientRect().top; const foot = s.querySelector('.foot');
      const limit = foot ? foot.getBoundingClientRect().top - top - 6 : 720 - 16;
      let bottom = 0;
      s.querySelectorAll('p,li,td,th,pre,h1,h2,h3,.big,.legend,.card,table').forEach(e => { if (e.closest('.foot')) return; bottom = Math.max(bottom, e.getBoundingClientRect().bottom - top); });
      return { slide: i + 1, bottom: Math.round(bottom), limit: Math.round(limit), over: Math.round(bottom - limit) };
    }));
    console.log(r.map(x => `${x.slide}: bottom ${x.bottom} / limit ${x.limit} -> ${x.over > 0 ? 'OVER ' + x.over : 'ok'}`).join('\n'));
    process.exitCode = r.some(x => x.over > 0) ? 2 : 0;
  } catch (e) {
    console.error('measure failed:', e.message); process.exitCode = 1;
  } finally { if (b) await b.close(); }
})();
