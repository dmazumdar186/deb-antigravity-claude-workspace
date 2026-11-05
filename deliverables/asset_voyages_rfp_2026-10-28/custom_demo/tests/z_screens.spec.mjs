// Screenshots of the key visitor and console screens at 1440 and 390 (deviceScaleFactor 1) for the eye review (X6).
import { test, expect, login, fillEnquiry, SLUG, ROOT, CTX } from './helpers.mjs';
import { join } from 'node:path';
import { mkdirSync } from 'node:fs';

test.describe.configure({ mode: 'serial' });
const OUT = join(ROOT, 'screens');
mkdirSync(OUT, { recursive: true });

for (const [w, h] of [[1440, 900], [390, 844]]) {
  test(`screens at ${w}px`, async ({ browser }) => {
    const ctx = await browser.newContext({ ...CTX, viewport: { width: w, height: h }, deviceScaleFactor: 1, isMobile: w < 500, hasTouch: w < 500 });
    const page = await ctx.newPage();
    page.on('dialog', (d) => d.accept());
    // the screens are taken in one browser, so every step lands in that browser's private sandbox
    const shot = async (name) => { await page.evaluate(() => document.fonts.ready); await page.screenshot({ path: join(OUT, `${name}-${w}.png`), fullPage: true }); };
    await page.goto('/'); await shot('01-catalogue');
    await page.goto('/?discipline=Cardiologie'); await shot('02-catalogue-cardiologie');
    await page.goto('/?q=rhumatologie'); await shot('03-catalogue-aucun-resultat');
    await page.goto(`/congres/${SLUG.onco}`); await shot('04-fiche-congres');
    await fillEnquiry(page, { email: 'pas-un-email', pax: '0', consent: false, out: '2027-01-27', back: '2027-01-20' });
    await page.waitForTimeout(3100);
    await page.getByRole('button', { name: 'Envoyer la demande' }).click();
    await expect(page.locator('#form-errors')).toBeVisible();
    await shot('05-fiche-congres-erreurs');
    await page.getByLabel('E-mail').fill('claire.dubois@example.com');
    await page.getByLabel('Passagers').fill('3');
    await page.getByLabel('Date retour').fill('2027-01-31');
    await page.locator('#f-consent').check();
    await page.waitForTimeout(3100);
    await page.getByRole('button', { name: 'Envoyer la demande' }).click();
    await expect(page.locator('[data-ref]')).toBeVisible();
    await shot('06-confirmation');
    await page.goto('/console/connexion'); await shot('07-connexion');
    await login(page, 'equipe'); await shot('08-tableau-de-bord-equipe');
    await page.goto('/console/demandes'); await shot('09-demandes');
    await page.locator('tbody tr').first().getByRole('link').click(); await shot('10-demande-detail');
    await page.getByRole('button', { name: 'Qualifiée' }).click();
    await page.getByLabel('Visible uniquement par l’équipe').fill('Rappel prévu demain matin.');
    await page.getByRole('button', { name: 'Ajouter la note' }).click();
    await shot('11-demande-historique');
    await page.goto('/console/notifications'); await shot('12-notifications');
    await page.goto('/console/gme'); await shot('13-gme-equipe-masque');
    await page.locator('.gme', { hasText: 'oncologie digestive' }).getByLabel(/Motif/).fill('Devis DV-2026-0007, trois places.');
    await page.locator('.gme', { hasText: 'oncologie digestive' }).getByRole('button', { name: 'Demander l’accès' }).click();
    await shot('14-gme-equipe-demande-envoyee');
    await page.getByRole('button', { name: 'Se déconnecter' }).click();
    await login(page, 'direction'); await shot('15-tableau-de-bord-direction');
    await page.goto('/console/gme/acces'); await shot('16-acces-gme-en-attente');
    await page.locator('.req', { hasText: 'oncologie digestive' }).getByRole('button', { name: 'Approuver pour 24 h' }).click();
    await shot('17-acces-gme-accorde');
    await page.goto('/console/congres'); await shot('18-congres-liste');
    await page.goto('/console/congres/112'); await shot('19-congres-edition-gme');
    await page.getByRole('button', { name: 'Se déconnecter' }).click();
    await login(page, 'equipe');
    await page.goto('/console/gme');
    await page.locator('.gme', { hasText: 'oncologie digestive' }).getByRole('button', { name: 'Afficher le code' }).click();
    await shot('20-gme-code-affiche');
    await page.getByRole('button', { name: 'Se déconnecter' }).click();
    await login(page, 'direction');
    await page.goto('/console/gme/journal'); await shot('21-journal-acces');
    await page.getByRole('button', { name: 'Se déconnecter' }).click();
    await login(page, 'contributeur');
    await page.goto('/console/congres/nouveau'); await shot('22-congres-nouveau-contributeur');
    await ctx.close();
  });
}
