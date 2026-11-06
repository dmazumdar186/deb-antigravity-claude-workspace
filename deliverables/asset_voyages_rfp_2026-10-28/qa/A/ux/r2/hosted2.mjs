// Round 2 hosted check: boot time, logged-out visitor, no toolbar, admin landing, then the five stories on the hosted links.
import fs from 'fs'; import { chromium } from 'playwright';
const px = process.env.HTTPS_PROXY || process.env.https_proxy;
const EV = 'evidence'; fs.mkdirSync(EV, { recursive: true });
const br = await chromium.launch({ proxy: px ? { server: px } : undefined });
const BP = 'https://asset-voyages-redesign.pages.dev/demo-wordpress';
const URLS = {
  visitor: `https://playground.wordpress.net/?mode=seamless&login=no&blueprint-url=${BP}/blueprint-visitor.json`,
  admin: `https://playground.wordpress.net/?mode=seamless&blueprint-url=${BP}/blueprint-admin.json`,
};
const CODES = ['DEMO-GME-4KQ7','DEMO-GME-8TZ2','DEMO-GME-3MX9','DEMO-GME-6PL5','DEMO-GME-1RB8'];
const out = { boot: {}, steps: [] };
const log = (story, txt, status, ev) => { out.steps.push({ story, txt, status, ev }); console.log(story, status, txt, '|', ev); };
async function wpFrame(p, re, timeout = 240000) {
  const t0 = Date.now();
  while (Date.now() - t0 < timeout) {
    for (const f of p.frames()) { if (f === p.mainFrame()) continue;
      try { const b = await f.locator('body').innerText({ timeout: 800 }); if (re.test(b)) return f; } catch {} }
    await p.waitForTimeout(500);
  }
  throw new Error('frame not found ' + re);
}
async function step(story, txt, fn) { try { const r = await fn(); log(story, txt, 'PASS', r || ''); return true; } catch (e) { log(story, txt, 'FAIL', String(e.message).split('\n')[0].slice(0, 220)); return false; } }
const expect = (c, m) => { if (!c) throw new Error(m); };
const scopeBase = f => f.url().replace(/(\/scope:[^/]+).*/, '$1');
async function nav(f, path) { await f.goto(scopeBase(f) + path, { timeout: 120000 }); await f.waitForLoadState('load'); }
async function wpLogin(f, u) { await nav(f, '/wp-login.php'); await f.fill('#user_login', u); await f.fill('#user_pass', 'demo-asset'); await Promise.all([f.waitForURL(/wp-admin/, { timeout: 120000 }), f.click('#wp-submit')]); await f.waitForLoadState('load'); }
async function wpLogout(f) { await nav(f, '/wp-login.php?action=logout'); const l = f.getByRole('link', { name: /déconnecter|log out/i }); if (await l.count()) { await Promise.all([f.waitForLoadState('load'), l.first().click()]); } }

const STAMP = Date.now().toString().slice(-5);
let ref = '';
// ---- Boot, visitor, at 1440 and 390 ----
for (const w of [1440, 390]) {
  const c = await br.newContext({ locale: 'fr-FR', timezoneId: 'Europe/Paris', viewport: { width: w, height: w > 500 ? 900 : 844 }, isMobile: w < 500, hasTouch: w < 500 });
  const p = await c.newPage(); const t0 = Date.now(); let f;
  await p.goto(URLS.visitor, { timeout: 90000 });
  try { f = await wpFrame(p, /Catalogue des congrès/); } catch (e) { out.boot['visitor@' + w] = { error: e.message }; await c.close(); continue; }
  await f.waitForLoadState('load'); const secs = ((Date.now() - t0) / 1000).toFixed(1);
  const body = await f.locator('body').innerText();
  const adminbar = await f.locator('#wpadminbar').count();
  const mainText = await p.locator('body').evaluate(b => [...b.querySelectorAll('*')].filter(e => !e.closest('iframe') && e.children.length === 0 && e.offsetParent && e.innerText?.trim()).map(e => e.innerText.trim()).slice(0, 20));
  const iframeBox = await p.evaluate(() => { const i = document.querySelector('iframe'); const r = i?.getBoundingClientRect(); return r ? [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)] : null; });
  const sw = await f.evaluate(() => [document.documentElement.scrollWidth, innerWidth]);
  out.boot['visitor@' + w] = { seconds: +secs, bonjour: /Bonjour/.test(body), adminbar, outerVisibleText: mainText, iframeBox, scroll: sw };
  await p.screenshot({ path: `${EV}/hosted2-visitor-${w}.png`, fullPage: false });
  await f.evaluate(() => window.scrollTo(0, document.body.scrollHeight)); await p.waitForTimeout(400);
  await p.screenshot({ path: `${EV}/hosted2-visitor-footer-${w}.png` });
  console.log('boot visitor', w, JSON.stringify(out.boot['visitor@' + w]));
  if (w === 1440) {
    await step('A2', 'hosted: logged out, no admin bar, no Playground toolbar', async () => { expect(!/Bonjour/.test(body) && adminbar === 0, 'logged in'); expect(mainText.length === 0, 'outer chrome text: ' + mainText.join(',')); return `boot ${secs}s, iframe ${iframeBox}`; });
    await step('A2', 'hosted: « Cardiologie » chip then first card', async () => { await Promise.all([f.waitForLoadState('load'), f.getByRole('link', { name: 'Cardiologie', exact: true }).first().click()]); await f.waitForTimeout(800); const t = await f.locator('body').innerText(); const m = t.match(/\d+ congrès trouvés?/); await Promise.all([f.waitForURL(/congres\//, { timeout: 60000 }), f.locator('.asset-card a').first().click()]); await f.getByText('Demander un devis vol').first().waitFor(); return (m || ['?'])[0] + '; ' + (await f.locator('h1').first().innerText()).slice(0, 60); });
    await p.screenshot({ path: `${EV}/hosted2-fiche-1440.png` });
    await step('A3', 'hosted: submit enquiry, get DV reference', async () => { await f.getByLabel('Nom et prénom').fill('Veena Fictive'); await f.getByLabel('E-mail').fill('veena.fictive@example.com'); await f.getByLabel('Téléphone').fill('+33 6 11 22 33 44'); await f.getByLabel('Ville de départ').fill('Paris'); await f.getByLabel('Date aller').fill('2027-08-26'); await f.getByLabel('Date retour').fill('2027-08-30'); await f.getByLabel('Nombre de passagers').fill('3'); await f.getByLabel(/J’accepte/).check(); await f.waitForTimeout(3500); await Promise.all([f.waitForLoadState('load'), f.getByRole('button', { name: 'Envoyer ma demande' }).click()]); await f.waitForTimeout(1500); const t = await f.locator('body').innerText(); const m = t.match(/DV-\d{4}-\d{4}/); expect(m, 'no ref: ' + t.slice(0, 200)); ref = m[0]; return ref; });
    await p.screenshot({ path: `${EV}/hosted2-confirmation-1440.png` });
  } else {
    await step('A2@390', 'hosted 390: logged out, no overflow', async () => { expect(!/Bonjour/.test(body) && adminbar === 0, 'logged in'); expect(sw[0] <= sw[1] + 1, 'overflow ' + sw); return `boot ${secs}s, scroll ${sw}`; });
  }
  await c.close();
}
// ---- Admin link ----
{
  const c = await br.newContext({ locale: 'fr-FR', timezoneId: 'Europe/Paris', viewport: { width: 1440, height: 900 } });
  const p = await c.newPage(); const t0 = Date.now(); let f;
  await p.goto(URLS.admin, { timeout: 90000 });
  try { f = await wpFrame(p, /Demandes de devis|Tableau de bord/); await f.waitForLoadState('load'); } catch (e) { out.boot.admin = { error: e.message }; }
  if (f) {
    const secs = ((Date.now() - t0) / 1000).toFixed(1);
    const who = await f.locator('#wp-admin-bar-my-account').innerText().catch(() => '?');
    const menu = await f.$$eval('#adminmenu > li > a', a => a.map(x => x.innerText.trim().replace(/\s+\d+$/, '')).filter(Boolean));
    out.boot.admin = { seconds: +secs, url: f.url().replace(/.*scope:[^/]+/, ''), who, menu };
    console.log('boot admin', JSON.stringify(out.boot.admin));
    await p.screenshot({ path: `${EV}/hosted2-admin-1440.png` });
    await step('A1', 'hosted admin: lands on Demandes as direction', async () => { expect(/Direction/.test(who), 'who ' + who); return out.boot.admin.url + ' ' + who.replace(/\s+/g, ' ').slice(0, 40); });
    const TITLE = `Congrès hébergé d’hépatologie ${STAMP} — exemple`;
    await step('A1', 'hosted: create + publish a congress as direction', async () => {
      await Promise.all([f.waitForLoadState('load'), f.locator('#adminmenu').getByRole('link', { name: 'Congrès', exact: true }).first().click()]);
      await Promise.all([f.waitForURL(/post-new/), f.getByRole('link', { name: 'Ajouter un congrès' }).first().click()]); await f.locator('#asset_congres_details').waitFor();
      await f.fill('#title', TITLE); await f.getByLabel('Date de début').fill('2027-06-14'); await f.getByLabel('Date de fin').fill('2027-06-16');
      await f.getByLabel('Ville').first().fill('Lille'); await f.getByLabel('Pays').first().fill('France'); await f.getByLabel('Discipline').first().fill('Hépatologie');
      await f.getByLabel('Lieu').fill('Grand Palais de Lille (fictif)'); await f.getByLabel('Site officiel').fill('https://example.com/h'); await f.getByLabel('Date de vérification').fill('2026-11-06');
      const tp = Date.now(); await Promise.all([f.waitForLoadState('load'), f.getByRole('button', { name: 'Publier', exact: true }).click()]);
      await f.locator('#message').waitFor({ timeout: 90000 }); const lost = await f.locator('#lost-connection-notice').isVisible().catch(() => false);
      return (await f.locator('#message').innerText()).trim().slice(0, 60) + ` in ${((Date.now() - tp) / 1000).toFixed(1)}s; lost-connection ${lost}`; });
    await p.screenshot({ path: `${EV}/hosted2-s1-published-1440.png` });
    await step('A1', 'hosted: public page shows the new congress', async () => { const href = await f.locator('#sample-permalink a').getAttribute('href'); await f.goto(href); const t = await f.locator('body').innerText(); expect(t.includes(TITLE) && t.includes('Lille'), 'missing'); return 'ok'; });
    // create an enquiry here so S4 has one in this sandbox
    await step('A4', 'hosted: equipe changes status of newest enquiry', async () => {
      await wpLogout(f); await wpLogin(f, 'equipe'); const w = f.locator('#asset_cd_demandes'); const t = await w.innerText();
      await Promise.all([f.waitForURL(/action=view/), w.getByRole('link', { name: /DV-\d{4}-\d{4}/ }).first().click()]);
      await f.getByLabel('Statut').selectOption({ label: 'Qualifiée' }); await Promise.all([f.waitForLoadState('load'), f.getByRole('button', { name: 'Enregistrer' }).click()]); await f.locator('.notice-success').waitFor();
      const h = await f.locator('table.asset-history').innerText(); expect(/→ Qualifiée/.test(h), 'no history'); return h.split('\n').slice(1, 2).join(' ').replace(/\s+/g, ' ').slice(0, 120); });
    await p.screenshot({ path: `${EV}/hosted2-s4-1440.png` });
    const NEURO = 'Congrès européen de neurologie — exemple';
    const row = () => f.locator('table.asset-gme-table tbody tr', { hasText: NEURO });
    await step('A5', 'hosted: equipe requests access (codes masked)', async () => {
      await nav(f, '/wp-admin/admin.php?page=asset-gme'); const html = await f.content(); for (const k of CODES) expect(!html.includes(k), 'code in HTML ' + k);
      const r = row(); const btn = r.getByRole('button', { name: /Demander l’accès/ }); await btn.click().catch(() => {}); const ta = r.locator('textarea'); await ta.waitFor({ timeout: 5000 }); await ta.fill('Devis groupe (hébergé).');
      await Promise.all([f.waitForLoadState('load'), r.getByRole('button', { name: /Demander l’accès|Envoyer/ }).last().click()]); await f.locator('.notice-success').waitFor(); return (await f.locator('.notice-success').innerText()).trim().slice(0, 80); });
    await p.screenshot({ path: `${EV}/hosted2-s5-request-1440.png` });
    await step('A5', 'hosted: direction approves from dashboard widget', async () => { await wpLogout(f); await wpLogin(f, 'direction'); const w = f.locator('#asset_cd_gme'); const item = w.locator('li, tr').filter({ hasText: 'neurologie' }).last(); await Promise.all([f.waitForLoadState('load'), item.getByRole('button', { name: /Approuver/ }).click()]); await f.locator('.notice-success').waitFor(); return (await f.locator('.notice-success').innerText()).trim().slice(0, 80); });
    await step('A5', 'hosted: equipe reveals once, masked after reload', async () => { await wpLogout(f); await wpLogin(f, 'equipe'); await nav(f, '/wp-admin/admin.php?page=asset-gme'); await Promise.all([f.waitForLoadState('load'), row().getByRole('button', { name: /Révéler/ }).click()]); const t = await row().innerText(); const m = t.match(/DEMO-GME-\w{4}/); expect(m, 'no code'); await p.screenshot({ path: `${EV}/hosted2-s5-reveal-1440.png` }); await nav(f, '/wp-admin/admin.php?page=asset-gme'); const html = await f.content(); for (const k of CODES) expect(!html.includes(k), 'still shown'); return 'revealed ' + m[0].slice(0, 11) + '••; masked after reload'; });
  }
  await c.close();
}
// ---- Admin link at 390 ----
{
  const c = await br.newContext({ locale: 'fr-FR', timezoneId: 'Europe/Paris', viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  const p = await c.newPage(); const t0 = Date.now();
  await p.goto(URLS.admin, { timeout: 90000 });
  try { const f = await wpFrame(p, /Demandes de devis|Tableau de bord/); await f.waitForLoadState('load'); out.boot['admin@390'] = { seconds: +((Date.now() - t0) / 1000).toFixed(1), scroll: await f.evaluate(() => [document.documentElement.scrollWidth, innerWidth]) }; await p.screenshot({ path: `${EV}/hosted2-admin-390.png` }); } catch (e) { out.boot['admin@390'] = { error: e.message }; }
  console.log('boot admin 390', JSON.stringify(out.boot['admin@390'])); await c.close();
}
fs.writeFileSync('hosted2-result.json', JSON.stringify(out, null, 1)); await br.close();
