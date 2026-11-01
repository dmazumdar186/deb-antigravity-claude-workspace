// poster.png = frame 0 rendered losslessly from the page (the frame LinkedIn shows before play).
// usage: node tools/poster.mjs <film_dir> <out.png>
import { openDemo, closeServer } from './page.mjs';
const [dir, out] = process.argv.slice(2);
const { browser, page } = await openDemo(dir, { w: 1080, h: 1350 });
await page.evaluate(() => window.render(0));
await page.screenshot({ path: out, type: 'png' });
await browser.close(); closeServer(); console.log('poster:', out);
