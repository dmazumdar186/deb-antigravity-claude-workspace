// Smoke A. Usage: node smoke_A.mjs [local|hosted|both]. Hosted: opens Playground in headless Chromium, asserts inside iframe.
import { createRequire } from 'module';
const require = createRequire('/home/user/deb-antigravity-claude-workspace/deliverables/asset_voyages_rfp_2026-10-28/wp_demo/tests/');
const { chromium } = require('playwright');
const mode = process.argv[2] || 'both';
const HOST = 'https://playground.wordpress.net/?blueprint-url=https://asset-voyages-redesign.pages.dev/demo-wordpress/';
const out = [];
const rec = (n, ok, info) => { out.push({ n, ok, info }); console.log((ok ? 'PASS ' : 'FAIL ') + n + ' ' + info); };
const browser = await chromium.launch({ args: ['--no-sandbox'] });
async function hosted(name) {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();
  const t0 = Date.now();
  try {
    await page.goto(HOST + name + '.json', { waitUntil: 'domcontentloaded', timeout: 60000 });
    const fr = page.frameLocator('iframe#playground-viewport, iframe.playground-viewport, iframe').first();
    if (name === 'blueprint-visitor') {
      await fr.locator('body').waitFor({ timeout: 240000 });
      await page.waitForFunction(() => { const f=[...document.querySelectorAll('iframe')]; return f.some(x=>{try{return x.contentDocument && /asset|catalogue|congr/i.test(x.contentDocument.body?.innerText||'')}catch(e){return false}})||false; }, null, { timeout: 240000 }).catch(()=>{});
      const boot = (Date.now() - t0) / 1000;
      const cards = await fr.locator('article, .asset-card, .asset-congres-card, li.asset-result').count();
      const txt = await fr.locator('body').innerText();
      const exemple = (txt.match(/— exemple/g) || []).length;
      rec('SMOKE-hosted-visitor-12-congresses', exemple >= 12 || cards >= 12, `boot=${boot}s cards=${cards} "— exemple" occurrences=${exemple}`);
      await page.screenshot({ path: new URL('./logs/hosted-visitor.png', import.meta.url).pathname });
    } else {
      await fr.locator('body').waitFor({ timeout: 240000 });
      await page.waitForTimeout(1000);
      await page.waitForFunction(() => [...document.querySelectorAll('iframe')].some(x=>{try{return /Demandes/i.test(x.contentDocument.body.innerText)}catch(e){return false}}), null, { timeout: 240000 }).catch(()=>{});
      const boot = (Date.now() - t0) / 1000;
      const txt = await fr.locator('body').innerText();
      rec('SMOKE-hosted-admin-demandes-loggedin', /Demandes/.test(txt) && /Howdy|Bonjour|Se déconnecter|Log Out|admin/i.test(txt), `boot=${boot}s sample=${JSON.stringify(txt.slice(0,160))}`);
      await page.screenshot({ path: new URL('./logs/hosted-admin.png', import.meta.url).pathname });
    }
  } catch (e) { rec('SMOKE-hosted-' + name, false, `after ${(Date.now()-t0)/1000}s: ${e.message.split('\n')[0]}`); try{await page.screenshot({ path: new URL('./logs/hosted-'+name+'-err.png', import.meta.url).pathname });}catch{} }
  await ctx.close();
}
if (mode !== 'local') { await hosted('blueprint-visitor'); await hosted('blueprint-admin'); }
if (mode !== 'hosted') {
  const B = process.env.WP_BASE || 'http://127.0.0.1:9400';
  for (const [p, re] of [['/', /exemple/], ['/congres/', /exemple/], ['/wp-login.php', /log|connexion/i]]) {
    const r = await fetch(B + p); const t = await r.text();
    rec('SMOKE-local ' + p, r.status === 200 && re.test(t), 'status ' + r.status);
  }
}
await browser.close();
process.exit(out.some(o => !o.ok) ? 1 : 0);
