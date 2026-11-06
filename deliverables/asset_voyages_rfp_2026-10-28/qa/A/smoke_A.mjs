// Smoke A. Usage: node smoke_A.mjs [local|hosted|both]. Hosted: opens Playground in headless Chromium, asserts inside iframe.
import { createRequire } from 'module';
const require = createRequire('/home/user/deb-antigravity-claude-workspace/deliverables/asset_voyages_rfp_2026-10-28/wp_demo/tests/');
const { chromium } = require('playwright');
const mode = process.argv[2] || 'both';
const HOST = 'https://playground.wordpress.net/?mode=seamless';
const BP = 'https://asset-voyages-redesign.pages.dev/demo-wordpress/';
const HURL = (n) => HOST + (n === 'blueprint-visitor' ? '&login=no' : '') + '&blueprint-url=' + BP + n + '.json'; // A-2xx: new hub URLs
const out = [];
const rec = (n, ok, info) => { out.push({ n, ok, info }); console.log((ok ? 'PASS ' : 'FAIL ') + n + ' ' + info); };
const browser = await chromium.launch({ args: ['--no-sandbox'] });
async function hosted(name) {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();
  const t0 = Date.now();
  const want = name === 'blueprint-visitor' ? /Catalogue des congr/i : /Demandes de devis/i;
  try {
    await page.goto(HURL(name), { waitUntil: 'domcontentloaded', timeout: 60000 });
    let txt = '', frame = null;
    while (Date.now() - t0 < 300000) {
      for (const f of page.frames()) {
        try { const t = await f.locator('body').innerText({ timeout: 2000 }); if (want.test(t)) { txt = t; frame = f; break; } } catch {}
      }
      if (frame) break;
      await page.waitForTimeout(2000);
    }
    const boot = (Date.now() - t0) / 1000;
    if (!frame) throw new Error('target text not seen within 300s');
    if (name === 'blueprint-visitor') {
      const exemple = (txt.match(/exemple/g) || []).length;
      const bonjour = /Bonjour/.test(txt); rec('SMOKE-hosted-visitor-no-Bonjour', !bonjour, 'Bonjour present=' + bonjour);
      const cards = await frame.locator('a:has-text("exemple"), h2:has-text("exemple"), h3:has-text("exemple")').count();
      const count = (txt.match(/(\d+)\s+congr/i) || [])[0];
      rec('SMOKE-hosted-visitor-12-congresses', /12/.test(count||'') || cards >= 12, `boot=${boot}s resultCountText=${count} exemple=${exemple} cards=${cards}`);
    } else {
      const li = await frame.locator('#wpadminbar').count();
      rec('SMOKE-hosted-admin-demandes-loggedin', li > 0 && /admin/i.test(txt), `boot=${boot}s adminbar=${li} url=${frame.url().slice(-60)}`);
    }
    await page.screenshot({ path: new URL('./logs/hosted-' + name + '.png', import.meta.url).pathname });
  } catch (e) { rec('SMOKE-hosted-' + name, false, `after ${(Date.now()-t0)/1000}s: ${e.message.split('\n')[0]}`); }
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
