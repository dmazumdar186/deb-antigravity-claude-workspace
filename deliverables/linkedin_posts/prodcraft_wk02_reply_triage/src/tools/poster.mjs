// poster.png = frame 0 rendered losslessly (the frame LinkedIn shows before play).  usage: node tools/poster.mjs <film_dir> <out.png>
import path from 'path';
const LIB = process.env.LIB || path.resolve(path.dirname(new URL(import.meta.url).pathname), '../../..');
const { openDemo, closeServer } = await import(path.join(LIB, 'core/render/page.mjs'));   // works inside or outside the clone
const [dir, out] = process.argv.slice(2);
const { browser, page } = await openDemo(dir, { w: 1080, h: 1350 });
await page.evaluate(() => window.render(0));
await page.screenshot({ path: out, type: 'png' });
await browser.close(); closeServer(); console.log('poster:', out);
