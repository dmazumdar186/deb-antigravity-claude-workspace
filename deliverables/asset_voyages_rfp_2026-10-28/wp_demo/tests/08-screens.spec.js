// Screenshots of key visitor and admin screens at 1440 and 390 px (deviceScaleFactor 1).
const { test, expect } = require('playwright/test');
const path = require('path');
const { asRole, readState, ROOT } = require('./helpers');

const OUT = path.join(ROOT, 'screens');
const WIDTHS = [1440, 390];

test('Screens: visitor', async ({ browser }) => {
	const s = readState();
	for (const w of WIDTHS) {
		const ctx = await browser.newContext({ viewport: { width: w, height: w === 390 ? 844 : 900 }, deviceScaleFactor: 1, isMobile: w === 390, hasTouch: w === 390 });
		const page = await ctx.newPage();
		const shot = async (name) => page.screenshot({ path: path.join(OUT, `visitor-${name}-${w}.png`), fullPage: true });
		await page.goto('/'); await shot('01-catalogue');
		await page.goto('/?discipline=cardiologie'); await shot('02-catalogue-filtre');
		await page.goto('/?q=zzzz'); await shot('03-catalogue-aucun-resultat');
		await page.goto(s.madridUrl); await shot('04-fiche-congres');
		await page.waitForTimeout(3300);
		await page.click('.asset-form button[type=submit]');
		await expect(page.locator('.asset-notice--error')).toBeVisible();
		await page.locator('#devis').screenshot({ path: path.join(OUT, `visitor-05-formulaire-erreurs-${w}.png`) });
		await page.goto(s.confirmUrl);
		await page.locator('#devis').screenshot({ path: path.join(OUT, `visitor-06-confirmation-${w}.png`) });
		await ctx.close();
	}
});

test('Screens: admin', async ({ browser }) => {
	const s = readState();
	for (const w of WIDTHS) {
		const opts = { viewport: { width: w, height: w === 390 ? 844 : 900 }, deviceScaleFactor: 1, isMobile: w === 390, hasTouch: w === 390 };
		const shots = {
			equipe: [
				['01-tableau-de-bord', '/wp-admin/'],
				['02-demandes', '/wp-admin/admin.php?page=asset-demandes'],
				['03-demande-detail', null],
				['04-gme-equipe-masque', '/wp-admin/admin.php?page=asset-gme'],
				['05-journal-notifications', '/wp-admin/admin.php?page=asset-notifications'],
				['06-congres-edition', `/wp-admin/post.php?post=${s.newCongresId}&action=edit`],
			],
			direction: [
				['07-tableau-de-bord-direction', '/wp-admin/'],
				['08-gme-direction', '/wp-admin/admin.php?page=asset-gme'],
				['09-acces-gme', '/wp-admin/admin.php?page=asset-gme-acces'],
				['10-journal-gme', '/wp-admin/admin.php?page=asset-gme-journal'],
			],
		};
		for (const [role, list] of Object.entries(shots)) {
			const { ctx, page } = await asRole(browser, role, opts);
			for (const [name, url] of list) {
				if (url) await page.goto(url);
				else {
					await page.goto('/wp-admin/admin.php?page=asset-demandes&s=' + s.newRef);
					await page.locator('a.row-title').first().click();
				}
				await page.screenshot({ path: path.join(OUT, `admin-${name}-${w}.png`), fullPage: true });
			}
			await ctx.close();
		}
	}
});
