// Shared helpers for the EXTRA « Le lien de groupe » UX/UAT run. PREVIEW Worker only.
const NM = new URL('../../B/ux/node_modules/', import.meta.url);
export const { chromium } = await import(new URL('playwright/index.mjs', NM));
export const AxeBuilder = (await import(new URL('@axe-core/playwright/dist/index.mjs', NM))).default;
export const B = 'https://asset-voyages-demo-preview.debanjan186.workers.dev';
if (/asset-voyages-demo\.debanjan186/.test(B)) throw new Error('production target refused');
export async function ctx(br, w = 1440, opts = {}) {
  const c = await br.newContext({ locale: 'fr-FR', timezoneId: 'Europe/Paris', viewport: { width: w, height: w > 500 ? 900 : 844 }, deviceScaleFactor: 1, isMobile: w < 500, hasTouch: w < 500, ...opts });
  const p = await c.newPage(); const errs = []; const s5 = [];
  p.on('pageerror', (e) => errs.push(e.message));
  p.on('console', (m) => { if (m.type() === 'error') errs.push(m.text()); });
  p.on('response', (r) => { if (r.status() >= 500) s5.push(r.status() + ' ' + r.url()); });
  p.errs = errs; p.s5 = s5; return { c, p };
}
export async function login(p, who) {
  await p.goto(B + '/console/connexion');
  await p.getByLabel('Identifiant').fill(who); await p.getByLabel('Mot de passe').fill('demo-asset');
  await p.getByRole('button', { name: 'Se connecter' }).click(); await p.waitForURL(/\/console(\?|$|\/$)/);
}
export async function reset(p) {
  try {
    if (!p.url().includes('/console') || p.url().includes('connexion')) await login(p, 'direction');
    p.on('dialog', (d) => d.accept().catch(() => {}));
    await p.goto(B + '/console');
    const b = p.getByRole('button', { name: 'Réinitialiser la démo' });
    if (!(await b.count())) { await p.getByRole('button', { name: 'Se déconnecter' }).first().click(); await login(p, 'direction'); }
    await p.getByRole('button', { name: 'Réinitialiser la démo' }).click();
    await p.getByText('La démonstration a été réinitialisée').first().waitFor({ timeout: 8000 });
    return 'reset ok';
  } catch (e) { return 'reset FAILED ' + e.message.split('\n')[0]; }
}
// Find an enquiry with ≥ 2 passengers and no link yet (in this browser's sandbox).
export async function findCandidate(p) {
  const out = [];
  for (const id of [2, 3, 4, 5, 6, 7, 8]) {
    const r = await p.goto(B + '/console/demandes/' + id); if (!r || r.status() !== 200) continue;
    const t = await p.locator('main').innerText();
    const pax = +(t.match(/Passagers\s*\n\s*(\d+)/) || [])[1];
    const ref = (t.match(/DV-2026-\d{4}/) || [])[0];
    out.push({ id, ref, pax, hasCreate: /Créer le lien/.test(t) });
  }
  return { list: out, pick: out.find((x) => x.pax >= 2 && x.hasCreate), single: out.find((x) => x.pax === 1) };
}
export async function submitDelegate(p, url, d, { wait = 3300 } = {}) {
  await p.goto(url); const t0 = Date.now();
  await p.getByLabel('Nom et prénom').fill(d.name); await p.getByLabel('E-mail').fill(d.email);
  await p.getByLabel('Ville de départ').fill(d.city);
  if (d.out) await p.getByLabel('Date aller').fill(d.out); if (d.back) await p.getByLabel('Date retour').fill(d.back);
  if (d.consent !== false) await p.getByLabel(/J’accepte/).check();
  await p.waitForTimeout(Math.max(0, wait - (Date.now() - t0)));
  await p.getByRole('button', { name: 'Envoyer mes informations' }).click(); await p.waitForLoadState('load');
  return p.locator('body').innerText();
}
// Delegate fill helper. Dates are relative to the congress: read min / data attributes from the page.
export async function fillDelegate(p, { name, email, city, out, back, consent = true }) {
  await p.getByLabel('Nom et prénom').fill(name); await p.getByLabel('E-mail').fill(email);
  await p.getByLabel('Ville de départ').fill(city); await p.getByLabel('Date aller').fill(out); await p.getByLabel('Date retour').fill(back);
  if (consent) await p.getByLabel(/J’accepte/).check();
}
