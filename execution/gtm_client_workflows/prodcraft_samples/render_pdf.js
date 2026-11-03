// render_pdf.js
// description: Print an HTML sample to PDF with Playwright Chromium and report any page whose
//   content overflows its box (vertical or horizontal). Exit 2 if any overflow is found.
// inputs: argv[2] = input .html, argv[3] = output .pdf
// outputs: PDF file; JSON line on stdout {pages, overflow:[...]}
const { chromium } = require('playwright');
const path = require('path');

(async () => {
  const [inp, out] = process.argv.slice(2);
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto('file://' + path.resolve(inp), { waitUntil: 'load' });
  await page.emulateMedia({ media: 'print' });
  const report = await page.evaluate(() => {
    const res = [];
    document.querySelectorAll('.page').forEach((pg, i) => {
      const c = pg.querySelector('.content');
      if (c.scrollHeight > c.clientHeight + 1) res.push({ page: i + 1, kind: 'vertical', by: c.scrollHeight - c.clientHeight });
      if (c.scrollWidth > c.clientWidth + 1) res.push({ page: i + 1, kind: 'horizontal', by: c.scrollWidth - c.clientWidth });
      c.querySelectorAll('table').forEach((t) => {
        if (t.scrollWidth > t.parentElement.clientWidth + 1) res.push({ page: i + 1, kind: 'table-wide' });
      });
    });
    return { pages: document.querySelectorAll('.page').length, overflow: res };
  });
  await page.pdf({ path: out, preferCSSPageSize: true, printBackground: true });
  await browser.close();
  console.log(JSON.stringify(report));
  process.exit(report.overflow.length ? 2 : 0);
})().catch((e) => { console.error(e); process.exit(1); });
