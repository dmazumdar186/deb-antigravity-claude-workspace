// Scratch: what does the hosted admin Playground link show after boot? Not part of the gate.
const { chromium } = await import(new URL('../../B/ux/node_modules/playwright/index.mjs', import.meta.url));
const url = 'https://playground.wordpress.net/?mode=seamless&blueprint-url=https://asset-voyages-redesign.pages.dev/demo-wordpress/blueprint-admin.json';
const b = await chromium.launch();
const c = await b.newContext({ locale: 'fr-FR', timezoneId: 'Europe/Paris', viewport: { width: 1440, height: 900 } });
const p = await c.newPage();
const t0 = Date.now();
p.on('pageerror', (e) => console.log('pageerror', e.message.slice(0, 200)));
p.goto(url).catch((e) => console.log('goto', e.message));
for (const s of [20, 45, 90]) {
  await p.waitForTimeout(s * 1000 - (Date.now() - t0));
  console.log(`=== ${s}s`);
  for (const f of p.frames()) {
    const t = await f.evaluate(() => (document.title + ' || ' + (document.body ? document.body.innerText : '')).replace(/\s+/g, ' ').slice(0, 300)).catch((e) => 'ERR ' + e.message.slice(0, 80));
    console.log(f.url().slice(0, 120), '::', t);
  }
}
await b.close();
