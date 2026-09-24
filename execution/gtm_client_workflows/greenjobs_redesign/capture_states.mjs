// Second-act state captures for the GreenJobs demo, driven by Playwright so
// the film can be scrolled for real (chrome --screenshot cannot scroll).
// description: Captures the three film states at 1440 (plus 390 and dark), the
//   full home page at 1440/390/dark, the "Your fit" result and no-match
//   states, the ad builder with a filled form (desktop, and 390 with the
//   preview toggled), and the job salary strip. Reuses the http.server that
//   screenshot.sh already started on the given port.
// inputs: argv: site dir, out dir, port
// outputs: PNGs in the out dir; non-zero exit when a capture fails
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
const require = createRequire(import.meta.url);
let chromium;
try { ({ chromium } = require('playwright')); } catch { ({ chromium } = require('/opt/node22/lib/node_modules/playwright')); }
const [site, out, port] = process.argv.slice(2);
const base = `http://127.0.0.1:${port}/`;
const jobs = JSON.parse(readFileSync(join(site, 'ie/jobs/index.html'), 'utf8').match(/id="gj-data">(.*?)<\/script>/s)[1]).jobs;
const withSal = jobs.find((j) => j.sal_min != null && j.sal_max != null) || jobs[0];
const ukJobs = JSON.parse(readFileSync(join(site, 'uk/jobs/index.html'), 'utf8').match(/id="gj-data">(.*?)<\/script>/s)[1]).jobs;
const ukSal = ukJobs.find((j) => j.sal_min != null && j.sal_max != null) || ukJobs[0];
const browser = await chromium.launch({ args: ['--no-sandbox', '--disable-gpu'] });
let failures = 0;
async function cap(name, url, w, h, run, opts = {}) {
  const page = await browser.newPage({ viewport: { width: w, height: h }, colorScheme: opts.dark ? 'dark' : 'light', reducedMotion: opts.rm ? 'reduce' : 'no-preference' });
  try {
    await page.goto(base + url, { waitUntil: 'load' });
    await page.waitForTimeout(250);
    if (run) await run(page);
    await page.waitForTimeout(opts.settle || 900);
    await page.screenshot({ path: join(out, name + '.png'), fullPage: !!opts.full });
    console.log(`  ${name}.png (${w} x ${h}${opts.full ? ', full page' : ''})`);
  } catch (e) { failures++; console.error(`  ${name}.png FAILED: ${e.message.split('\n')[0]}`); }
  await page.close();
}
const toState = (n) => async (page) => {
  await page.evaluate((k) => { const seq = window.GJFilm.seq(); const i = seq.indexOf(k); const host = document.querySelector('[data-film]'); const r = host.getBoundingClientRect(); const last = seq.length - 1; const top = scrollY + r.top + (i * 0.92 / last) * (r.height - innerHeight) + (i === last ? (r.height - innerHeight) * 0.08 : 0); scrollTo({ top, behavior: 'instant' }); }, n);
  await page.waitForTimeout(1300);
};
const fullPage = async (page) => { /* walk the page so reveals and count-ups have fired, then return to the top */
  const h = await page.evaluate(() => document.documentElement.scrollHeight);
  for (let y = 0; y < h; y += 700) { await page.evaluate((yy) => scrollTo({ top: yy, behavior: 'instant' }), y); await page.waitForTimeout(60); }
  await page.evaluate(() => scrollTo({ top: 0, behavior: 'instant' }));
  await page.waitForTimeout(400);
};
for (const n of [0, 1, 2]) await cap(`ie-film-${n}-1440`, 'ie/index.html?theme=light', 1440, 900, toState(n));
await cap('ie-film-0-390', 'ie/index.html?theme=light', 390, 844, toState(0));
await cap('ie-film-2-390', 'ie/index.html?theme=light', 390, 844, toState(2));
await cap('uk-film-0-1440', 'uk/index.html?theme=light', 1440, 900, toState(0));
await cap('uk-film-2-1440', 'uk/index.html?theme=light', 1440, 900, toState(2));
await cap('dark-ie-film-0-1440', 'ie/index.html?theme=dark', 1440, 900, toState(0), { dark: true });
await cap('dark-ie-film-2-1440', 'ie/index.html?theme=dark', 1440, 900, toState(2), { dark: true });
await cap('dark-ie-hero-1440', 'ie/index.html?theme=dark', 1440, 900, null, { dark: true });
await cap('ie-index-1440-full', 'ie/index.html?theme=light', 1440, 900, fullPage, { full: true });
await cap('ie-index-390-full', 'ie/index.html?theme=light', 390, 844, fullPage, { full: true });
await cap('dark-ie-index-1440-full', 'ie/index.html?theme=dark', 1440, 900, fullPage, { full: true, dark: true });
const toFit = async (page) => { await page.waitForSelector('[data-fit-out] .hit, [data-fit-out] .fit__none', { timeout: 6000 }); await page.evaluate(() => document.querySelector('[data-fit]').scrollIntoView({ block: 'start', behavior: 'instant' })); };
await cap('ie-fit-1440', 'ie/jobs/index.html?theme=light#fit=ecologist.dublin', 1440, 1500, toFit);
await cap('ie-fit-390', 'ie/jobs/index.html?theme=light#fit=ecologist.dublin', 390, 2300, toFit);
await cap('ie-fit-home-1440', 'ie/index.html?theme=light#fit=solar.project.manager', 1440, 1400, toFit);
await cap('ie-fit-none-1440', 'ie/jobs/index.html?theme=light#fit=zzzz', 1440, 900, toFit);
await cap('ie-fit-empty-1440', 'ie/jobs/index.html?theme=light', 1440, 900, async (page) => { await page.evaluate(() => document.querySelector('[data-fit]').scrollIntoView({ block: 'start', behavior: 'instant' })); });
const toAd = async (page) => { await page.evaluate(() => document.querySelector('[data-adb]').scrollIntoView({ block: 'start', behavior: 'instant' })); };
await cap('ie-adbuilder-1440', 'ie/employers/index.html?theme=light&ad=demo', 1440, 1500, toAd);
await cap('ie-adbuilder-390', 'ie/employers/index.html?theme=light&ad=demo', 390, 1700, toAd);
await cap('ie-adbuilder-preview-390', 'ie/employers/index.html?theme=light&ad=demo', 390, 1500, async (page) => { await page.click('[data-adb-toggle]'); await page.waitForTimeout(400); await toAd(page); });
const toSits = async (page) => { await page.evaluate(() => document.querySelector('.sits').scrollIntoView({ block: 'start', behavior: 'instant' })); };
await cap('ie-job-sits-1440', `ie/jobs/${withSal.href}?theme=light`, 1440, 900, toSits);
await cap('uk-job-sits-390', `uk/jobs/${ukSal.href}?theme=light`, 390, 1100, toSits);
await cap('ie-keith-score-1440', 'ie/for-keith/index.html?theme=light', 1440, 1200, async (page) => { await page.evaluate(() => document.querySelector('.score').scrollIntoView({ block: 'start', behavior: 'instant' })); });
await browser.close();
process.exit(failures ? 1 : 0);
