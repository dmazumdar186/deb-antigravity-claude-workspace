// Option B walkthrough recording: the five stories, visitor and team sides, on the live demo.
// Run: node record_B.mjs   (writes raw_B/*.webm and raw_B/marks.json; post-process with encode_B.sh)
// Calm pacing: ~60 ms per typed character, 1.2–2 s beats after each change, eased cursor moves, a visible click dot,
// and an English caption bar. One fresh browser context = one fresh private sandbox (clean seed data).
import { createRequire } from 'node:module';
import { mkdirSync, writeFileSync, readdirSync, rmSync, renameSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
function loadPw() {
  for (const p of ['playwright', join(HERE, '../../custom_demo/node_modules/playwright')]) {
    try { return require(p); } catch { /* try next */ }
  }
  throw new Error('playwright not found');
}
const { chromium } = loadPw();

const BASE = process.env.BASE_URL || 'https://asset-voyages-demo.debanjan186.workers.dev';
const PASSWORD = 'demo-asset';
const RAW = join(HERE, 'raw_B');
const W = 1440, H = 900;
const CAPTION_H = 64;

mkdirSync(RAW, { recursive: true });
for (const f of readdirSync(RAW)) if (f.endsWith('.webm')) rmSync(join(RAW, f), { force: true }); // only our own old takes

// Overlay: cursor dot + caption bar, re-created on every page load; state survives navigations via sessionStorage.
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
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount); else mount();
})();`;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const browser = await chromium.launch({ args: ['--lang=fr-FR', '--accept-lang=fr-FR'], env: { ...process.env, LANG: 'fr_FR.UTF-8', LANGUAGE: 'fr' } });
const ctx = await browser.newContext({
  baseURL: BASE, locale: 'fr-FR', timezoneId: 'Europe/Paris', viewport: { width: W, height: H }, deviceScaleFactor: 1, bypassCSP: true, // lets the recording overlay (caption, cursor dot) apply its styles
  recordVideo: { dir: RAW, size: { width: W, height: H } },
});
await ctx.addInitScript(OVERLAY);
const t0 = Date.now();
const page = await ctx.newPage();
page.on('dialog', (d) => d.accept().catch(() => {}));
const errors = [];
page.on('pageerror', (e) => errors.push('pageerror ' + e.message));
page.on('console', (m) => { if (m.type() === 'error') errors.push('console ' + m.text()); });
page.on('response', (r) => { if (r.status() >= 400) errors.push(`HTTP ${r.status()} ${r.url()}`); });
page.setDefaultTimeout(15000);

const marks = {};
const mark = (k) => { marks[k] = (Date.now() - t0) / 1000; };
let pos = [720, 450];

const beat = (ms = 1500) => sleep(ms);
async function caption(t) {
  await page.evaluate((x) => window.__recCaption && window.__recCaption(x), t);
  await sleep(1300);
}
// Eased cursor glide to a point.
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
// Smoothly bring an element into the visible band (above the caption bar) if it is not already there.
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
// Draw the eye to a result without covering it: the dot parks just below the element's left part.
async function look(loc) {
  await reveal(loc);
  const b = await loc.boundingBox();
  const y = Math.min(b.y + b.height + 16, H - CAPTION_H - 14);
  await glide(b.x + Math.min(b.width / 3, 90), y);
  await sleep(220);
}
async function click(loc, { nav = false } = {}) {
  await pointAt(loc);
  if (nav) await Promise.all([page.waitForLoadState('load'), loc.click({ position: undefined })]);
  else await loc.click();
  pos = await page.evaluate(() => JSON.parse(sessionStorage.getItem('rec-pos') || '[720,450]'));
}
async function type(loc, text) {
  await click(loc);
  await loc.pressSequentially(text, { delay: 60 });
  await sleep(250);
}
async function select(loc, value) {
  await pointAt(loc);
  await loc.selectOption(value);
  await sleep(400);
}
async function settle() { await page.waitForLoadState('load'); await sleep(300); }

async function login(user) {
  await page.goto('/console/connexion'); await settle();
  await beat(700);
  await type(page.getByLabel('Identifiant'), user);
  await type(page.getByLabel('Mot de passe'), PASSWORD);
  await click(page.getByRole('button', { name: 'Se connecter' }));
  await page.getByRole('heading', { name: 'Tableau de bord', level: 1 }).waitFor();
  await settle(); await beat(1300);
}
async function logout() {
  await click(page.getByRole('button', { name: 'Se déconnecter' }));
  await page.waitForURL(/connexion/); await settle(); await beat(800);
}
const nav = (name) => page.getByRole('navigation', { name: 'Console' }).getByRole('link', { name });

const NEW = { title: 'Congrès de cardiologie interventionnelle — exemple', disc: 'Cardiologie', venue: 'Centre des congrès de Lyon — exemple', city: 'Lyon', country: 'France', start: '2026-12-09', end: '2026-12-11', url: 'https://www.example.org/cardio-lyon', ver: '2026-11-05' };

try {
  // ---------- 1 · congress: contributor drafts, submits; direction publishes; public catalogue ----------
  await page.goto('/console/connexion'); await settle();
  mark('start');
  await caption('1 · A contributor drafts a congress and sends it for review');
  await type(page.getByLabel('Identifiant'), 'contributeur');
  await type(page.getByLabel('Mot de passe'), PASSWORD);
  await click(page.getByRole('button', { name: 'Se connecter' }));
  await page.getByRole('heading', { name: 'Tableau de bord', level: 1 }).waitFor(); await settle(); await beat(1300);
  await click(nav('Congrès')); await settle(); await beat(1000);
  await click(page.getByRole('link', { name: 'Nouveau congrès' })); await settle(); await beat(900);
  await type(page.getByLabel('Titre'), NEW.title);
  await select(page.getByRole('combobox', { name: 'Discipline', exact: true }), NEW.disc);
  await type(page.getByLabel('Lieu'), NEW.venue);
  await type(page.getByLabel('Ville'), NEW.city);
  await select(page.getByRole('combobox', { name: 'Pays', exact: true }), NEW.country);
  for (const [l, v] of [['Date de début', NEW.start], ['Date de fin', NEW.end], ['Vérifié le', NEW.ver]]) {
    await click(page.getByLabel(l)); await page.getByLabel(l).fill(v); await sleep(500);
  }
  await type(page.getByLabel('Site officiel'), NEW.url);
  await beat(900);
  await click(page.getByRole('button', { name: 'Enregistrer le brouillon' }));
  await page.getByText('Congrès créé.').waitFor(); await settle(); await beat(1600);
  const editUrl = page.url().split('?')[0];
  await click(page.getByRole('button', { name: 'Soumettre à relecture' }));
  await page.locator('.head .st', { hasText: 'À relire' }).waitFor(); await settle();
  await look(page.locator('.head .st')); await beat(1800);
  await logout();

  await caption('1 · Direction reviews the draft and publishes it');
  await type(page.getByLabel('Identifiant'), 'direction');
  await type(page.getByLabel('Mot de passe'), PASSWORD);
  await click(page.getByRole('button', { name: 'Se connecter' }));
  await page.getByRole('heading', { name: 'Tableau de bord', level: 1 }).waitFor(); await settle(); await beat(1200);
  await click(nav('Congrès')); await settle(); await beat(1000);
  const link = page.getByRole('link', { name: NEW.title });
  if (await link.count()) { await click(link.first()); } else { await page.goto(editUrl); }
  await settle(); await beat(1400);
  await click(page.getByRole('button', { name: 'Publier' }));
  await page.locator('.head .st', { hasText: 'Publié' }).waitFor(); await settle();
  await look(page.locator('.head .st')); await beat(1800);
  await logout();

  await page.goto('/'); await settle();
  await caption('1 · The new congress is now live in the public catalogue');
  const row = page.locator('.row', { hasText: 'cardiologie interventionnelle' });
  await look(row.locator('.row__t').first()); await beat(2000);

  // ---------- 2 · visitor: search, filter, details ----------
  await glide(1100, 300);
  await page.evaluate(() => scrollTo({ top: 0, behavior: 'smooth' })); await sleep(900);
  mark('poster'); await beat(1200);
  await caption('2 · A visitor searches « cardiologie », filters by country and opens the details');
  await type(page.getByLabel('Recherche'), 'cardiologie');
  await click(page.getByRole('button', { name: 'Rechercher' }));
  await page.waitForURL(/q=cardiologie/); await settle();
  await look(page.locator('.bar__n')); await beat(1800);
  await select(page.getByLabel('Pays'), 'Espagne');
  await page.waitForURL(/pays=Espagne/); await settle();
  await look(page.locator('.bar__n')); await beat(1700);
  await click(page.locator('.row__a').first()); await settle();
  await page.locator('h1').waitFor(); await beat(1600);
  await look(page.locator('.facts')); await beat(1800);

  // ---------- 3 · visitor: flight enquiry, DV reference ----------
  await caption('3 · The visitor sends a flight enquiry and receives a DV reference');
  await type(page.getByLabel('Nom et prénom'), 'Claire Dubois (exemple)');
  await type(page.getByLabel('E-mail'), 'claire.dubois@example.com');
  await type(page.getByLabel('Téléphone'), '01 23 45 67 89');
  await type(page.getByLabel('Ville de départ'), 'Bordeaux');
  for (const [l, v] of [['Date aller', '2027-08-26'], ['Date retour', '2027-08-31']]) {
    await click(page.getByLabel(l)); await page.getByLabel(l).fill(v); await sleep(500);
  }
  await click(page.getByLabel('Passagers')); await page.getByLabel('Passagers').fill(''); await page.getByLabel('Passagers').pressSequentially('3', { delay: 60 });
  await type(page.getByLabel('Message'), 'Trois places, départ le matin.');
  await click(page.locator('#f-consent')); await page.locator('#f-consent').check(); await beat(900);
  await click(page.getByRole('button', { name: 'Envoyer la demande' }));
  await page.getByRole('heading', { name: 'Merci, votre demande est enregistrée.' }).waitFor(); await settle();
  const ref = (await page.locator('[data-ref]').textContent()).trim();
  await look(page.locator('[data-ref]')); await beat(2200);

  // ---------- 4 · team: dashboard, open, status, history ----------
  await caption('4 · The team opens the new enquiry from its dashboard and updates its status');
  await login('equipe');
  await look(page.locator('.feed li').first()); await beat(1200);
  await click(page.locator('.feed li').first().getByRole('link')); await settle();
  await page.locator('h1', { hasText: ref }).waitFor(); await beat(1500);
  await click(page.getByRole('button', { name: 'Qualifiée' }));
  await page.locator('.head .st', { hasText: 'Qualifiée' }).waitFor(); await settle();
  await look(page.locator('.head .st')); await beat(1600);
  await caption('4 · Every change is kept in the enquiry history, with who and when');
  await look(page.locator('.hist li').last()); await beat(2400);

  // ---------- 5 · GM&E codes ----------
  await caption('5 · The team sees the GM&E code masked and asks for access with a reason');
  await click(nav('Codes GM&E')); await settle(); await beat(1200);
  const card = page.locator('.gme', { hasText: 'oncologie digestive' });
  await look(card.locator('.code')); await beat(1600);
  await type(card.getByLabel(/Motif/), `Devis ${ref}, trois médecins.`);
  await click(card.getByRole('button', { name: 'Demander l’accès' }));
  await page.getByText('Demande envoyée à la Direction.').waitFor(); await settle();
  await look(page.locator('.gme', { hasText: 'oncologie digestive' }).locator('.wait')); await beat(1700);
  await logout();

  await caption('5 · Direction approves the request for 24 hours');
  await type(page.getByLabel('Identifiant'), 'direction');
  await type(page.getByLabel('Mot de passe'), PASSWORD);
  await click(page.getByRole('button', { name: 'Se connecter' }));
  await page.getByRole('heading', { name: 'Tableau de bord', level: 1 }).waitFor(); await settle(); await beat(1000);
  await click(nav(/Demandes d’accès GM&E/)); await settle(); await beat(1300);
  await click(page.locator('.req', { hasText: 'oncologie digestive' }).getByRole('button', { name: 'Approuver pour 24 h' }));
  await page.getByText('Accès accordé pour 24 heures.').waitFor(); await settle();
  const active = page.locator('section', { has: page.getByRole('heading', { name: 'Accès actifs' }) }).locator('.req', { hasText: 'oncologie digestive' });
  await look(active); await beat(1800);
  await logout();

  await caption('5 · The team reveals the code, and the access journal records it');
  await type(page.getByLabel('Identifiant'), 'equipe');
  await type(page.getByLabel('Mot de passe'), PASSWORD);
  await click(page.getByRole('button', { name: 'Se connecter' }));
  await page.getByRole('heading', { name: 'Tableau de bord', level: 1 }).waitFor(); await settle(); await beat(1000);
  await click(nav('Codes GM&E')); await settle(); await beat(1000);
  mark('reveal');
  await click(page.locator('.gme', { hasText: 'oncologie digestive' }).getByRole('button', { name: 'Afficher le code' }));
  await page.locator('[data-revealed]').waitFor(); await settle();
  await look(page.locator('[data-revealed]')); await beat(2200);
  await logout();
  await type(page.getByLabel('Identifiant'), 'direction');
  await type(page.getByLabel('Mot de passe'), PASSWORD);
  await click(page.getByRole('button', { name: 'Se connecter' }));
  await page.getByRole('heading', { name: 'Tableau de bord', level: 1 }).waitFor(); await settle(); await beat(900);
  await click(nav('Journal d’accès')); await settle();
  await look(page.locator('tbody tr').first()); await beat(2200);
  await logout();

  await page.goto('/congres/journees-d-oncologie-digestive-cg-0112'); await settle();
  await caption('5 · A logged-out visitor sees only « Tarif congrès négocié disponible »');
  await look(page.locator('.gme-note')); await beat(2600);
  mark('end');
} finally {
  const video = page.video();
  await page.close();
  // Reset this browser's sandbox through the real Direction button (not part of the recording).
  const p2 = await ctx.newPage();
  p2.on('dialog', (d) => d.accept().catch(() => {}));
  let reset = false;
  try {
    await p2.goto('/console/connexion');
    if (!p2.url().includes('/connexion')) { await p2.getByRole('button', { name: 'Se déconnecter' }).click(); await p2.goto('/console/connexion'); }
    await p2.getByLabel('Identifiant').fill('direction');
    await p2.getByLabel('Mot de passe').fill(PASSWORD);
    await p2.getByRole('button', { name: 'Se connecter' }).click();
    await p2.getByRole('button', { name: 'Réinitialiser la démo' }).click();
    await p2.getByText('La démonstration a été réinitialisée').first().waitFor();
    reset = true;
  } catch (e) { errors.push('reset failed: ' + e.message); }
  const v2 = p2.video();
  await p2.close();
  await ctx.close();
  await browser.close();
  const main = await video.path();
  renameSync(main, join(RAW, 'walkthrough_B.webm'));
  try { rmSync(await v2.path(), { force: true }); } catch { /* ignore */ }
  writeFileSync(join(RAW, 'marks.json'), JSON.stringify({ marks, reset, errors }, null, 2));
  console.log(JSON.stringify({ marks, reset, errors, files: readdirSync(RAW) }, null, 2));
}
