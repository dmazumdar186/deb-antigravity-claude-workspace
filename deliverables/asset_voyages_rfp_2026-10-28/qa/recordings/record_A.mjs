// Option A (WordPress) walkthrough recording: the five stories in ONE continuous tab, on a local Playground.
// Run: node record_A.mjs   (BASE_URL defaults to http://127.0.0.1:9430; writes raw_A/walkthrough_A.webm + raw_A/marks.json)
// Same pacing, cursor dot, caption bar and encode settings as record_B.mjs. Needs a FRESH server (it mutates the seed).
import { createRequire } from 'node:module';
import { mkdirSync, writeFileSync, readdirSync, rmSync, renameSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
function loadPw() {
  for (const p of ['playwright', join(HERE, '../../wp_demo/tests/node_modules/playwright'), join(HERE, '../../custom_demo/node_modules/playwright')]) {
    try { return require(p); } catch { /* try next */ }
  }
  throw new Error('playwright not found');
}
const { chromium } = loadPw();

const BASE = process.env.BASE_URL || 'http://127.0.0.1:9430';
const PASSWORD = 'demo-asset';
const RAW = join(HERE, 'raw_A');
const W = 1440, H = 900;
const CAPTION_H = 64;

mkdirSync(RAW, { recursive: true });
for (const f of readdirSync(RAW)) if (f.endsWith('.webm')) rmSync(join(RAW, f), { force: true }); // only our own old takes

// Overlay: identical to record_B.mjs (cursor dot + caption bar, state kept across navigations in sessionStorage).
const OVERLAY = `(() => {
  const css = \`
  #rec-dot{position:fixed;left:0;top:0;width:18px;height:18px;margin:-9px 0 0 -9px;border-radius:50%;
    background:rgba(239,118,13,.45);border:2px solid #FBF8F2;box-shadow:0 0 0 1px rgba(10,31,48,.35),0 2px 8px rgba(10,31,48,.25);
    pointer-events:none;z-index:2147483647;transition:transform .18s ease}
  #rec-dot.down{transform:scale(.7)}
  .rec-ripple{position:fixed;width:44px;height:44px;margin:-22px 0 0 -22px;border-radius:50%;border:2px solid #EF760D;
    pointer-events:none;z-index:2147483646;animation:recr .6s ease-out forwards}
  @keyframes recr{from{opacity:.9;transform:scale(.4)}to{opacity:0;transform:scale(1.4)}}
  #rec-cap{position:fixed;left:0;right:0;bottom:0;height:${CAPTION_H}px;display:flex;align-items:center;justify-content:center;
    background:#0A1F30;color:#FBF8F2;font:500 20px/1.3 Inter,system-ui,sans-serif;letter-spacing:.005em;
    border-top:1px solid rgba(251,248,242,.22);z-index:2147483645;pointer-events:none;padding:0 32px;text-align:center}
  #rec-cap span{transition:opacity .35s ease}
  html{scroll-padding-bottom:${CAPTION_H + 24}px}
  body{padding-bottom:${CAPTION_H}px !important}\`;
  function mount() {
    if (document.getElementById('rec-cap')) return;
    const st = document.createElement('style'); st.textContent = css; document.head.appendChild(st);
    const cap = document.createElement('div'); cap.id = 'rec-cap'; cap.setAttribute('aria-hidden', 'true');
    const sp = document.createElement('span'); sp.textContent = sessionStorage.getItem('rec-cap') || ''; cap.appendChild(sp);
    document.body.appendChild(cap);
    const dot = document.createElement('div'); dot.id = 'rec-dot';
    const p = JSON.parse(sessionStorage.getItem('rec-pos') || '[720,450]');
    dot.style.left = p[0] + 'px'; dot.style.top = p[1] + 'px';
    document.body.appendChild(dot);
    addEventListener('mousemove', (e) => { dot.style.left = e.clientX + 'px'; dot.style.top = e.clientY + 'px';
      sessionStorage.setItem('rec-pos', JSON.stringify([e.clientX, e.clientY])); }, true);
    addEventListener('mousedown', (e) => { dot.classList.add('down'); const r = document.createElement('div'); r.className = 'rec-ripple';
      r.style.left = e.clientX + 'px'; r.style.top = e.clientY + 'px'; document.body.appendChild(r); setTimeout(() => r.remove(), 700); }, true);
    addEventListener('mouseup', () => dot.classList.remove('down'), true);
  }
  window.__recCaption = (t) => { sessionStorage.setItem('rec-cap', t); const sp = document.querySelector('#rec-cap span');
    if (!sp) return; sp.style.opacity = 0; setTimeout(() => { sp.textContent = t; sp.style.opacity = 1; }, 350); };
  // Mount as soon as <body> exists (not at DOMContentLoaded): WordPress admin pages paint before their deferred
  // scripts finish, and waiting would make the caption bar blink off on every admin navigation.
  if (document.body) mount();
  else { document.addEventListener('DOMContentLoaded', mount);
    const mo = new MutationObserver(() => { if (document.body && document.head) { mo.disconnect(); mount(); } });
    mo.observe(document, { childList: true, subtree: true }); }
})();`;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
// channel 'chromium' (full browser, new headless): the headless shell draws native date placeholders as dd/mm/yyyy;
// this one follows --lang and draws jj/mm/aaaa.
const browser = await chromium.launch({ channel: 'chromium', args: ['--lang=fr-FR', '--accept-lang=fr-FR'], env: { ...process.env, LANG: 'fr_FR.UTF-8', LANGUAGE: 'fr', TZ: 'Europe/Paris' } });
// Warm-up, not recorded: a cold Playground can take 30 s+ on its first admin page. Read-only page views, no data change.
{
  const w = await browser.newContext({ baseURL: BASE, locale: 'fr-FR' });
  const p = await w.newPage();
  for (const u of ['/', '/?q=cardiologie', '/wp-login.php']) await p.goto(u, { timeout: 120000 });
  // The very first sign-in on a cold server sometimes bounces back to the login page: retry, off camera.
  for (let i = 0; i < 4 && !/wp-admin/.test(p.url()); i++) {
    await p.goto('/wp-login.php', { timeout: 120000 });
    await p.fill('#user_login', 'direction'); await p.fill('#user_pass', PASSWORD);
    await Promise.all([p.waitForNavigation({ timeout: 120000 }), p.click('#wp-submit')]).catch(() => {});
  }
  for (const u of ['/wp-admin/edit.php?post_type=asset_congres', '/wp-admin/post-new.php?post_type=asset_congres', '/wp-admin/admin.php?page=asset-demandes', '/wp-admin/admin.php?page=asset-gme']) await p.goto(u, { timeout: 120000 });
  await w.close();
}
const ctx = await browser.newContext({
  baseURL: BASE, locale: 'fr-FR', timezoneId: 'Europe/Paris', viewport: { width: W, height: H }, deviceScaleFactor: 1, bypassCSP: true, // recording overlay only
  recordVideo: { dir: RAW, size: { width: W, height: H } },
});
await ctx.addInitScript(OVERLAY);
const t0 = Date.now();
const page = await ctx.newPage();
page.on('dialog', (d) => d.accept().catch(() => {}));
const errors = [];
page.on('pageerror', (e) => errors.push('pageerror ' + e.message));
page.on('console', (m) => { if (m.type() === 'error') errors.push('console ' + m.text()); });
page.on('response', (r) => { if (r.status() >= 400 && !/favicon/.test(r.url())) errors.push(`HTTP ${r.status()} ${r.url()}`); });
page.setDefaultTimeout(30000);

const marks = {};
const mark = (k) => { marks[k] = (Date.now() - t0) / 1000; };
let pos = [720, 450];

const beat = (ms = 1500) => sleep(Math.round(ms * 0.7)); // calm, but the whole journey stays near 4 minutes
async function caption(t) {
  await page.evaluate((x) => window.__recCaption && window.__recCaption(x), t);
  await sleep(950);
}
async function glide(x, y) {
  const [x0, y0] = pos; const d = Math.hypot(x - x0, y - y0);
  const n = Math.max(12, Math.min(40, Math.round(d / 22)));
  for (let i = 1; i <= n; i++) {
    const t = i / n; const e = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
    await page.mouse.move(x0 + (x - x0) * e, y0 + (y - y0) * e);
    await sleep(14);
  }
  pos = [x, y];
}
async function reveal(loc) {
  await loc.waitFor({ state: 'visible' });
  const moved = await loc.evaluate((el, capH) => {
    const r = el.getBoundingClientRect(); const top = 80, bottom = innerHeight - capH - 40;
    if (r.top >= top && r.bottom <= bottom) return false;
    const target = scrollY + r.top - Math.max(top, (innerHeight - capH) / 2 - r.height / 2);
    scrollTo({ top: Math.max(0, target), behavior: 'smooth' }); return true;
  }, CAPTION_H);
  if (moved) await sleep(1000);
}
async function pointAt(loc) {
  await reveal(loc);
  const b = await loc.boundingBox();
  await glide(b.x + Math.min(b.width / 2, 120), b.y + b.height / 2);
  await sleep(220);
}
async function look(loc) {
  await reveal(loc);
  const b = await loc.boundingBox();
  const y = Math.min(b.y + b.height + 16, H - CAPTION_H - 14);
  await glide(b.x + Math.min(b.width / 3, 90), y);
  await sleep(220);
}
const trace = [];
async function click(loc) {
  trace.push([((Date.now() - t0) / 1000).toFixed(1), String(loc).slice(0, 70)]);
  await pointAt(loc);
  await loc.click();
  pos = await page.evaluate(() => JSON.parse(sessionStorage.getItem('rec-pos') || '[720,450]')).catch(() => pos);
}
async function type(loc, text, delay = 42) {
  await click(loc);
  await loc.pressSequentially(text, { delay });
  await sleep(220);
}
// Park the dot just left of a table row, so it never covers the row below.
async function aside(loc) {
  await reveal(loc);
  const b = await loc.boundingBox();
  await glide(b.x - 16, b.y + b.height / 2);
  await sleep(220);
}
async function select(loc, value) {
  await pointAt(loc);
  await loc.selectOption(value);
  await sleep(400);
}
async function setDate(loc, v) { await click(loc); await loc.fill(v); await sleep(450); }
async function settle() { await page.waitForLoadState('load'); await sleep(300); }

async function login(user) {
  await page.locator('#user_login').waitFor();
  await type(page.locator('#user_login'), user, 30);
  await type(page.locator('#user_pass'), PASSWORD, 30);
  await click(page.locator('#wp-submit'));
  await page.waitForURL(/wp-admin/, { timeout: 90000 }); await settle(); await beat(900);
}
async function logout() {
  await pointAt(page.locator('#wp-admin-bar-my-account > .ab-item'));
  await page.locator('#wp-admin-bar-my-account').hover(); await sleep(500);
  await click(page.locator('#wp-admin-bar-logout a'));
  await page.waitForURL(/wp-login\.php/); await settle(); await beat(600);
}
const menu = (id) => page.locator(`#${id} > a`);

const NEW = { title: 'Congrès de cardiologie interventionnelle — exemple', desc: 'Trois jours de sessions (exemple).',
  start: '2026-12-09', end: '2026-12-11', city: 'Lyon', pays: 'France', disc: 'Cardiologie', venue: 'Centre de congrès de Lyon (fictif)',
  url: 'https://example.com/congres/cardio-lyon', source: 'Site de l’organisateur (exemple)', ver: '2026-11-05' };
const NEURO = 'Congrès européen de neurologie — exemple';
const gmeRow = () => page.locator('table.asset-gme-table tbody tr', { hasText: NEURO });

try {
  // ---------- 1 · contributor drafts and submits; direction publishes; public catalogue ----------
  await page.goto('/wp-login.php'); await settle();
  mark('start');
  await caption('1 · A contributor signs in and drafts a new congress');
  await login('contributeur');
  await click(page.locator('#wpbody-content a', { hasText: 'Ajouter un congrès' }).first()); await settle(); await beat(900);
  await type(page.locator('#title'), NEW.title);
  const f = (k) => page.locator('#asset-field-asset_' + k);
  await setDate(f('start'), NEW.start);
  await setDate(f('end'), NEW.end);
  await type(f('city'), NEW.city);
  await type(f('pays'), NEW.pays);
  await type(f('discipline'), NEW.disc);
  await type(f('url'), NEW.url);
  await setDate(f('verified'), NEW.ver);
  await page.keyboard.press('Escape'); await beat(700);
  await caption('1 · The contributor cannot publish, so the congress is sent to Direction for review');
  await click(page.locator('#publish'));
  await page.locator('#message').waitFor(); await settle();
  await look(page.locator('#post-status-display')); await beat(1300);
  // Leaving the editor through the menu lets WordPress release its edit lock (logging out from the editor does not),
  // so Direction gets no take-over dialog.
  await click(page.locator('#menu-posts-asset_congres a[href$="edit.php?post_type=asset_congres"]').first()); await settle();
  await aside(page.locator('tr', { has: page.locator('a.row-title', { hasText: 'cardiologie interventionnelle' }) })); await beat(1400);
  await logout();

  await caption('1 · Direction reviews the congress and publishes it');
  await login('direction');
  await click(menu('menu-posts-asset_congres')); await settle(); await beat(900);
  await click(page.locator('a.row-title', { hasText: 'cardiologie interventionnelle' })); await settle(); await beat(1000);
  const takeOver = page.locator('#post-lock-dialog a.button-primary');
  if (await takeOver.isVisible().catch(() => false)) { errors.push("note: post-lock dialog shown"); await click(takeOver); await settle(); }
  await click(page.locator('#publish'));
  await page.locator('#message').waitFor(); await settle();
  await look(page.locator('#post-status-display')); await beat(1600);
  await logout();
  await click(page.locator('#backtoblog a')); await settle();

  await caption('1 · The new congress is now live in the public catalogue');
  const card = page.locator('.asset-card', { hasText: 'cardiologie interventionnelle' }).first();
  await glide(1180, 330); await beat(600);
  mark('poster'); await beat(1200);
  await look(card.locator('h2')); await beat(1500);

  // ---------- 2 · visitor: search, filter, details ----------
  await page.evaluate(() => scrollTo({ top: 0, behavior: 'smooth' })); await sleep(900);
  await caption('2 · A visitor searches « cardiologie », filters by country and opens the details page');
  await type(page.locator('#asset-f-q'), 'cardiologie');
  await click(page.locator('.asset-filters button[type=submit]'));
  await page.waitForURL(/q=cardiologie/); await settle();
  await look(page.locator('.asset-count')); await beat(1500);
  await select(page.locator('#asset-f-pays'), 'espagne');
  await click(page.locator('.asset-filters button[type=submit]'));
  await page.waitForURL(/pays=espagne/); await settle();
  await look(page.locator('.asset-count')); await beat(1600);
  await click(page.locator('.asset-card h2 a').first()); await settle(); await beat(1300);
  await look(page.locator('.asset-details')); await beat(1900);

  // ---------- 3 · visitor: flight enquiry, DV reference ----------
  await caption('3 · The visitor sends a flight enquiry and receives a DV reference');
  const q = (k) => page.locator('#asset-q-' + k);
  await type(q('nom'), 'Claire Dubois (exemple)');
  await type(q('email'), 'claire.dubois@example.com');
  await type(q('telephone'), '01 23 45 67 89');
  await type(q('ville_depart'), 'Bordeaux');
  await setDate(q('date_aller'), '2027-08-26');
  await setDate(q('date_retour'), '2027-08-31');
  await click(q('passagers')); await q('passagers').fill(''); await q('passagers').pressSequentially('3', { delay: 60 }); await sleep(300);
  await type(q('message'), 'Trois places, départ le matin.');
  await click(q('consentement')); await q('consentement').check(); await beat(900);
  await click(page.locator('.asset-form button[type=submit]'));
  await page.locator('.asset-ref').waitFor(); await settle();
  const ref = (await page.locator('.asset-ref').innerText()).trim();
  await look(page.locator('.asset-ref')); await beat(2400);

  // ---------- 4 · team: Espace équipe, Demandes, status, history ----------
  await caption('4 · In the same tab, the team signs in through « Espace équipe »');
  await click(page.locator('.asset-team-link a').first()); await settle();
  await login('equipe');
  await caption('4 · The new enquiry is at the top of « Demandes »; the team updates its status');
  await click(menu('toplevel_page_asset-demandes')); await settle();
  const first = page.locator('table.wp-list-table tbody tr').first();
  await aside(first); await beat(1600);
  await click(first.locator('a.row-title')); await settle(); await beat(1200);
  await select(page.locator('#asset-statut'), 'qualifiee');
  await click(page.locator('#submit'));
  await page.locator('.notice-success').waitFor(); await settle();
  await look(page.locator('#asset-statut')); await beat(1400);
  await caption('4 · Every change is kept in the enquiry history, with who and when');
  await look(page.locator('table.asset-history')); await beat(2600);

  // ---------- 5 · GM&E codes ----------
  await caption('5 · GM&E codes are masked; the team asks Direction for access, with a reason');
  await click(menu('toplevel_page_asset-gme')); await settle(); await beat(1000);
  await look(gmeRow().locator('.asset-masked')); await beat(1500);
  await type(gmeRow().locator('textarea'), `Devis ${ref} : neurologues, client fictif.`);
  await click(gmeRow().locator('button', { hasText: 'Demander' }));
  await page.locator('.notice-success').waitFor(); await settle();
  await look(gmeRow().locator('.asset-pending-label')); await beat(1700);
  await logout();

  await caption('5 · Direction approves the request for 24 hours');
  await login('direction');
  const req = page.locator('#asset_cd_gme .asset-widget-req', { hasText: NEURO });
  await look(req); await beat(1200);
  await click(req.locator('button', { hasText: 'Approuver' }));
  await page.locator('.notice-success').waitFor(); await settle();
  await look(page.locator('.notice-success')); await beat(1800);
  await logout();

  await caption('5 · The team reveals the code once, and the journal records it');
  await login('equipe');
  await click(menu('toplevel_page_asset-gme')); await settle(); await beat(1000);
  await look(gmeRow().locator('.asset-grant')); await beat(1200);
  await click(gmeRow().locator('button', { hasText: 'Révéler' }));
  await gmeRow().locator('code.asset-revealed').waitFor(); await settle();
  mark('reveal');
  await look(gmeRow().locator('code.asset-revealed')); await beat(2400);
  await logout();
  await login('direction');
  await click(menu('toplevel_page_asset-gme')); await settle(); await beat(800);
  await click(page.locator('#toplevel_page_asset-gme a[href*="page=asset-gme-journal"]')); await settle();
  mark('journal');
  await page.locator('table.asset-log tbody tr[data-action="reveal"]').first().waitFor(); await look(page.locator('table.asset-log')); await beat(2400);
  await logout();

  await click(page.locator('#backtoblog a')); await settle();
  await caption('5 · A logged-out visitor sees only « Tarif congrès négocié disponible »');
  await click(page.locator('a.asset-chip', { hasText: 'Neurologie' })); await settle(); await beat(900);
  await click(page.locator('.asset-card h2 a', { hasText: 'neurologie' }).first()); await settle(); await beat(900);
  mark('note');
  await look(page.locator('.asset-offer')); await beat(2800);
  mark('end');
} finally {
  const video = page.video();
  await page.close();
  await ctx.close();
  await browser.close();
  renameSync(await video.path(), join(RAW, 'walkthrough_A.webm'));
  writeFileSync(join(RAW, 'marks.json'), JSON.stringify({ marks, errors, trace }, null, 2));
  console.log(JSON.stringify({ marks, errors, files: readdirSync(RAW) }, null, 2));
}
