// Scratch exploration of Option A (local) labels. Not part of the gate.
const { chromium } = await import(new URL('../../B/ux/node_modules/playwright/index.mjs', import.meta.url));
const A = process.env.A_BASE || 'http://127.0.0.1:9431';
const b = await chromium.launch();
const c = await b.newContext({ locale: 'fr-FR', timezoneId: 'Europe/Paris', viewport: { width: 1440, height: 900 } });
const p = await c.newPage();
p.setDefaultTimeout(60000);
const dump = async (label) => {
  const t = await p.evaluate(() => document.body.innerText);
  const links = await p.evaluate(() => [...document.querySelectorAll('a,button,input[type=submit]')].filter((e) => e.offsetParent).map((e) => (e.innerText || e.value || '').trim().replace(/\s+/g, ' ') + ' -> ' + (e.getAttribute('href') || e.type)).slice(0, 120));
  console.log('=====', label, p.url(), await p.title());
  console.log(t.slice(0, 2500));
  console.log('--links', links.join('\n'));
};
await p.goto(A + '/'); await dump('home');
const first = p.locator('a[href*="congres"]').filter({ hasText: /exemple/i }).first();
if (await first.count()) { await first.click(); await p.waitForLoadState(); await dump('congress'); }
for (const who of (process.argv[2] || 'equipe').split(',')) {
  await c.clearCookies();
  await p.goto(A + '/wp-login.php');
  await p.fill('#user_login', who); await p.fill('#user_pass', 'demo-asset'); await p.click('#wp-submit');
  await p.waitForLoadState();
  await dump('admin ' + who);
}
await b.close();
