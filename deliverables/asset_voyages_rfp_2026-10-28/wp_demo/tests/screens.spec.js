// Screenshots on a FRESH seed (run alone: tests/run_screens.sh). fr-FR locale, Europe/Paris, 1440 and 390 px,
// deviceScaleFactor 1, reduced motion (no view-transition ghosting). Checks the screens hold only clean
// fictional seed data before shooting.
const { test, expect } = require('playwright/test');
const path = require('path');
const { asRole, ROOT, FILL_WAIT } = require('./helpers');

test.describe.configure({ mode: 'serial' });

const OUT = path.join(ROOT, 'screens');
const WIDTHS = [1440, 390];
const DIRTY = ['=cmd', '+SUM', '@Lyon', '<script', 'gastro-entérologie', 'néphrologie', 'Rafale', 'Alice Testeur', 'Zoé'];
const ctxOpts = (w) => ({ viewport: { width: w, height: w === 390 ? 844 : 900 }, deviceScaleFactor: 1, isMobile: w === 390, hasTouch: w === 390, locale: 'fr-FR', timezoneId: 'Europe/Paris', reducedMotion: 'reduce' });
const state = {};

async function shot(page, file, locator) {
	await page.waitForLoadState('networkidle');
	const text = await page.locator('body').innerText();
	for (const d of DIRTY) expect(text.includes(d), `${d} visible in ${file}`).toBe(false);
	if (locator) await page.locator(locator).screenshot({ path: path.join(OUT, file), animations: 'disabled' });
	else await page.screenshot({ path: path.join(OUT, file), fullPage: true, animations: 'disabled' });
}

test('FIX-A-18 screens are taken on a fresh seed (12 upcoming congresses, 6 enquiries)', async ({ browser }) => {
	const ctx = await browser.newContext(ctxOpts(1440));
	const page = await ctx.newPage();
	await page.goto('/');
	await expect(page.locator('.asset-count')).toContainText('12 congrès trouvés');
	await page.goto('/?q=madrid');
	await page.locator('.asset-card h2 a').first().click();
	state.madridUrl = page.url();
	// One clean, fictional enquiry for the confirmation screen.
	await page.fill('#asset-q-nom', 'Claire Fontaine');
	await page.fill('#asset-q-email', 'claire.fontaine@example.com');
	await page.fill('#asset-q-telephone', '+33 6 00 00 00 07');
	await page.fill('#asset-q-societe', 'Clinique Exemple Bordeaux');
	await page.fill('#asset-q-ville_depart', 'Bordeaux');
	await page.fill('#asset-q-date_aller', '2027-08-26');
	await page.fill('#asset-q-date_retour', '2027-08-31');
	await page.fill('#asset-q-passagers', '4');
	await page.check('#asset-q-consentement');
	await page.waitForTimeout(FILL_WAIT);
	await page.click('.asset-form button[type=submit]');
	await expect(page.locator('.asset-ref')).toHaveText('DV-2026-0007');
	state.confirmUrl = page.url();
	await ctx.close();
	const { ctx: a, page: p } = await asRole(browser, 'equipe');
	await p.goto('/wp-admin/admin.php?page=asset-demandes');
	await expect(p.locator('.subsubsub li').first()).toContainText('(7)');
	await a.close();
});

test('Screens: visitor', async ({ browser }) => {
	for (const w of WIDTHS) {
		const ctx = await browser.newContext(ctxOpts(w));
		const page = await ctx.newPage();
		await page.goto('/'); await shot(page, `visitor-01-catalogue-${w}.png`);
		await page.goto('/?discipline=cardiologie'); await shot(page, `visitor-02-catalogue-filtre-${w}.png`);
		await page.goto('/?q=zzzz'); await shot(page, `visitor-03-catalogue-aucun-resultat-${w}.png`);
		await page.goto(state.madridUrl); await shot(page, `visitor-04-fiche-congres-${w}.png`);
		await page.waitForTimeout(FILL_WAIT);
		await page.click('.asset-form button[type=submit]');
		await expect(page.locator('.asset-notice--error')).toBeVisible();
		await shot(page, `visitor-05-formulaire-erreurs-${w}.png`, '#devis');
		await page.goto(state.confirmUrl);
		await shot(page, `visitor-06-confirmation-${w}.png`, '#devis');
		await ctx.close();
	}
});

test('Screens: admin', async ({ browser }) => {
	for (const w of WIDTHS) {
		const shots = {
			equipe: [
				['01-tableau-de-bord', '/wp-admin/'],
				['02-demandes', '/wp-admin/admin.php?page=asset-demandes'],
				['03-demande-detail', null],
				['04-gme-equipe-masque', '/wp-admin/admin.php?page=asset-gme'],
				['05-journal-notifications', '/wp-admin/admin.php?page=asset-notifications'],
				['06-congres-edition', 'EDIT'],
			],
			direction: [
				['07-tableau-de-bord-direction', '/wp-admin/'],
				['08-gme-direction', '/wp-admin/admin.php?page=asset-gme'],
				['09-acces-gme', '/wp-admin/admin.php?page=asset-gme-acces'],
				['10-journal-gme', '/wp-admin/admin.php?page=asset-gme-journal'],
			],
		};
		for (const [role, list] of Object.entries(shots)) {
			const { ctx, page } = await asRole(browser, role, ctxOpts(w));
			for (const [name, url] of list) {
				if (url === 'EDIT') {
					await page.goto('/wp-admin/edit.php?post_type=asset_congres');
					await page.locator('a.row-title', { hasText: 'cardiologie' }).first().click();
				} else if (url) {
					await page.goto(url);
				} else {
					await page.goto('/wp-admin/admin.php?page=asset-demandes&s=DV-2026-0007');
					await page.locator('a.row-title').first().click();
				}
				await page.waitForTimeout(400);
				await shot(page, `admin-${name}-${w}.png`);
			}
			await ctx.close();
		}
	}
});
