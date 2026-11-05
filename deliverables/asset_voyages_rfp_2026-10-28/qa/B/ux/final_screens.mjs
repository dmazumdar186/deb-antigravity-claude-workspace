// Final eye-review screenshots (X6), Option B, from LIVE. Same screen list as custom_demo/tests/z_screens.spec.mjs.
// Run: cd qa/B/ux && LANG=fr_FR.UTF-8 LC_ALL=fr_FR.UTF-8 node final_screens.mjs
// One fresh browser context per width = a fresh private sandbox (clean seed, no test residue).
import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const BASE = process.env.BASE || 'https://asset-voyages-demo.debanjan186.workers.dev';
const OUT = join(dirname(fileURLToPath(import.meta.url)), 'final_screens');
mkdirSync(OUT, { recursive: true });
const ONCO = 'journees-d-oncologie-digestive-cg-0112';
const errs = [];

const browser = await chromium.launch({ env: { ...process.env, LANG: 'fr_FR.UTF-8', LC_ALL: 'fr_FR.UTF-8' }, args: ['--lang=fr-FR'] });
for (const [w, h] of [[1440, 900], [390, 844]]) {
  const ctx = await browser.newContext({ baseURL: BASE, locale: 'fr-FR', timezoneId: 'Europe/Paris', viewport: { width: w, height: h }, deviceScaleFactor: 1, isMobile: w < 500, hasTouch: w < 500 });
  const page = await ctx.newPage();
  page.setDefaultTimeout(15000);
  page.on('dialog', (d) => d.accept());
  page.on('pageerror', (e) => errs.push(`${w} pageerror ${e.message}`));
  page.on('console', (m) => { if (m.type() === 'error') errs.push(`${w} console ${m.text()} @ ${page.url()}`); });
  const shot = async (name) => { await page.evaluate(() => document.fonts.ready); await page.screenshot({ path: join(OUT, `${name}-${w}.png`), fullPage: true }); console.log('shot', name, w); };
  const login = async (user) => {
    await page.goto('/console/connexion');
    if (!page.url().includes('/connexion')) { await page.getByRole('button', { name: 'Se déconnecter' }).first().click(); await page.goto('/console/connexion'); }
    await page.getByLabel('Identifiant').fill(user);
    await page.getByLabel('Mot de passe').fill('demo-asset');
    await page.getByRole('button', { name: 'Se connecter' }).click();
    await page.getByRole('heading', { name: 'Tableau de bord', level: 1 }).waitFor();
  };
  const logout = async () => { await page.getByRole('button', { name: 'Se déconnecter' }).first().click(); await page.waitForURL(/connexion/); };
  const fillEnquiry = async (o) => {
    const v = { name: 'Claire Dubois (exemple)', email: 'claire.dubois@example.com', phone: '01 23 45 67 89', company: 'Société E (exemple)', city: 'Bordeaux', out: '2027-08-26', back: '2027-08-31', pax: '3', msg: 'Trois places, départ le matin.', consent: true, ...o };
    await page.getByLabel('Nom et prénom').fill(v.name);
    await page.getByLabel('E-mail').fill(v.email);
    await page.getByLabel('Téléphone').fill(v.phone);
    await page.getByLabel('Société').fill(v.company);
    await page.getByLabel('Ville de départ').fill(v.city);
    await page.getByLabel('Date aller').fill(v.out);
    await page.getByLabel('Date retour').fill(v.back);
    await page.getByLabel('Passagers').fill(v.pax);
    await page.getByLabel('Message').fill(v.msg);
    if (v.consent) await page.locator('#f-consent').check(); else await page.locator('#f-consent').uncheck();
  };

  await page.goto('/'); await shot('01-catalogue');
  await page.goto('/?discipline=Cardiologie'); await shot('02-catalogue-cardiologie');
  await page.goto('/?q=rhumatologie'); await shot('03-catalogue-aucun-resultat');
  await page.goto(`/congres/${ONCO}`); await shot('04-fiche-congres');
  await fillEnquiry({ email: 'pas-un-email', pax: '0', consent: false, out: '2027-01-27', back: '2027-01-20' });
  await page.waitForTimeout(3100);
  await page.getByRole('button', { name: 'Envoyer la demande' }).click();
  await page.locator('#form-errors').waitFor();
  await shot('05-fiche-congres-erreurs');
  await page.getByLabel('E-mail').fill('claire.dubois@example.com');
  await page.getByLabel('Passagers').fill('3');
  await page.getByLabel('Date retour').fill('2027-01-31');
  await page.locator('#f-consent').check();
  await page.waitForTimeout(3100);
  await page.getByRole('button', { name: 'Envoyer la demande' }).click();
  await page.locator('[data-ref]').waitFor();
  await shot('06-confirmation');
  await page.goto('/console/connexion'); await shot('07-connexion');
  await login('equipe'); await shot('08-tableau-de-bord-equipe');
  await page.goto('/console/demandes'); await shot('09-demandes');
  await page.locator('tbody tr').first().getByRole('link').first().click(); await page.waitForLoadState(); await shot('10-demande-detail');
  await page.getByRole('button', { name: 'Qualifiée' }).click(); await page.waitForLoadState();
  await page.getByLabel('Visible uniquement par l’équipe').fill('Rappel prévu demain matin.');
  await page.getByRole('button', { name: 'Ajouter la note' }).click();
  await page.locator('.ok', { hasText: 'Note ajoutée à l’historique.' }).waitFor();
  await shot('11-demande-historique');
  await page.goto('/console/notifications'); await shot('12-notifications');
  await page.goto('/console/gme'); await shot('13-gme-equipe-masque');
  await page.locator('.gme', { hasText: 'oncologie digestive' }).getByLabel(/Motif/).fill('Devis DV-2026-0007, trois places.');
  await page.locator('.gme', { hasText: 'oncologie digestive' }).getByRole('button', { name: 'Demander l’accès' }).click();
  await page.waitForLoadState();
  await shot('14-gme-equipe-demande-envoyee');
  await logout();
  await login('direction'); await shot('15-tableau-de-bord-direction');
  await page.goto('/console/gme/acces'); await shot('16-acces-gme-en-attente');
  await page.locator('.req', { hasText: 'oncologie digestive' }).getByRole('button', { name: 'Approuver pour 24 h' }).click();
  await page.waitForLoadState();
  await shot('17-acces-gme-accorde');
  await page.goto('/console/congres'); await shot('18-congres-liste');
  await page.goto('/console/congres/112'); await shot('19-congres-edition-gme');
  await logout();
  await login('equipe');
  await page.goto('/console/gme');
  await page.locator('.gme', { hasText: 'oncologie digestive' }).getByRole('button', { name: 'Afficher le code' }).click();
  await page.waitForLoadState();
  await shot('20-gme-code-affiche');
  await logout();
  await login('direction');
  await page.goto('/console/gme/journal'); await shot('21-journal-acces');
  await logout();
  await login('contributeur');
  await page.goto('/console/congres/nouveau'); await shot('22-congres-nouveau-contributeur');
  // extra: contributor home (EYE-B-011 plural tile)
  await page.goto('/console'); await shot('23-tableau-de-bord-contributeur');
  // reset this sandbox at the end
  await logout();
  await login('direction');
  await page.getByRole('button', { name: 'Réinitialiser la démo' }).click();
  await page.getByText('La démonstration a été réinitialisée').first().waitFor();
  console.log('reset ok', w);
  await ctx.close();
}
await browser.close();
console.log('errors', errs.length, errs.slice(0, 10));
