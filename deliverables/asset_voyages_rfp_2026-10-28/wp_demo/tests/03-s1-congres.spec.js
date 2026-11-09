// S1: create and edit a congress in WordPress.
const { test, expect } = require('playwright/test');
const { asRole, clickCounter, readState, writeState } = require('./helpers');

test.describe.configure({ mode: 'serial' });

const TITLE = 'Congrès test de gastro-entérologie — exemple';

async function fillCongres(page, o) {
	if (o.title !== undefined) await page.fill('#title', o.title);
	const map = { start: 'asset-field-asset_start', end: 'asset-field-asset_end', city: 'asset-field-asset_city', pays: 'asset-field-asset_pays', discipline: 'asset-field-asset_discipline', venue: 'asset-field-asset_venue', url: 'asset-field-asset_url', source: 'asset-field-asset_source', verified: 'asset-field-asset_verified' };
	for (const [k, id] of Object.entries(map)) if (o[k] !== undefined) await page.fill('#' + id, o[k]);
}

test('S1-E1 + S1-F1 create and publish in <= 4 clicks with French labels, required fields marked', async ({ browser }) => {
	const { ctx, page } = await asRole(browser, 'admin');
	await page.goto('/wp-admin/');
	const c = clickCounter();
	await c.click(page.locator('#menu-posts-asset_congres > a'));
	await c.click(page.locator('.page-title-action').first());
	await expect(page.locator('#asset_congres_details')).toBeVisible();
	for (const l of ['Date de début', 'Date de fin', 'Ville', 'Pays', 'Discipline', 'Lieu', 'Site officiel', 'Source de l’information', 'Date de vérification']) {
		await expect(page.locator('#asset_congres_details label', { hasText: l }).first()).toBeVisible();
	}
	expect(await page.locator('#asset_congres_details .asset-req').count()).toBeGreaterThanOrEqual(5);
	await fillCongres(page, { title: TITLE, start: '2027-12-06', end: '2027-12-09', city: 'Bordeaux', pays: 'France', discipline: 'Gastro-entérologie', venue: 'Palais des congrès de Bordeaux (fictif)', url: 'https://example.com/congres/test', source: 'Site de l’organisateur (exemple)', verified: '2026-11-05' });
	await c.click(page.locator('#publish'));
	await expect(page.locator('#message')).toBeVisible();
	expect(c.n).toBeLessThanOrEqual(4);
	test.info().annotations.push({ type: 'clicks', description: String(c.n) });
	const id = new URL(page.url()).searchParams.get('post');
	const permalink = await page.locator('#sample-permalink a').getAttribute('href');
	writeState({ newCongresId: id, newCongresUrl: permalink });
	// Server is the judge: the public page shows every saved value.
	const pub = await ctx.request.get(permalink);
	const html = await pub.text();
	for (const t of ['Bordeaux', 'France', 'Gastro-entérologie', '6 décembre 2027', '9 décembre 2027', 'fictif (démonstration)', '5 novembre 2026']) expect(html).toContain(t);
	await ctx.close();
});

test('S1-E2 + S1-F2 edit in <= 3 clicks; new value shows in admin and on the public page', async ({ browser }) => {
	const { ctx, page } = await asRole(browser, 'admin');
	await page.goto('/wp-admin/');
	const c = clickCounter();
	await c.click(page.locator('#menu-posts-asset_congres > a'));
	await c.click(page.locator('a.row-title', { hasText: 'gastro-entérologie' }));
	await page.fill('#asset-field-asset_city', 'Toulouse');
	await c.click(page.locator('#publish'));
	await expect(page.locator('#asset-field-asset_city')).toHaveValue('Toulouse');
	expect(c.n).toBeLessThanOrEqual(3);
	test.info().annotations.push({ type: 'clicks', description: String(c.n) });
	await page.goto('/wp-admin/edit.php?post_type=asset_congres');
	await expect(page.locator('tr.iedit', { hasText: 'gastro-entérologie' })).toContainText('Toulouse');
	const pub = await (await browser.newContext()).request.get(readState().newCongresUrl);
	expect(await pub.text()).toContain('Toulouse');
	await ctx.close();
});

test('S1-F3 contributor drafts and submits for review, cannot publish; draft is not public; Direction publishes', async ({ browser }) => {
	const { ctx, page } = await asRole(browser, 'contributeur');
	await page.goto('/wp-admin/post-new.php?post_type=asset_congres');
	await expect(page.locator('#publish')).toHaveValue(/Soumettre/);
	await fillCongres(page, { title: 'Congrès contributeur de néphrologie — exemple', start: '2027-10-01', end: '2027-10-03', city: 'Nantes', pays: 'France', discipline: 'Cardiologie', url: 'https://example.com/congres/nephro' });
	await page.click('#save-post');
	await expect(page.locator('#message')).toBeVisible();
	const id = new URL(page.url()).searchParams.get('post');
	await page.click('#publish');
	await expect(page.locator('#post-status-display')).toContainText(/attente/i);
	// Forged publish attempt is downgraded by WordPress core.
	const anon = await browser.newContext();
	let r = await anon.request.get(`/?post_type=asset_congres&p=${id}`);
	expect(r.status()).toBe(404);
	r = await anon.request.get('/?q=nephrologie');
	expect(await r.text()).not.toContain('néphrologie');
	// Contributor cannot reach publish capability screens.
	await page.goto(`/wp-admin/post.php?post=${id}&action=edit`);
	expect(await page.locator('#publish').getAttribute('value')).not.toMatch(/^Publier$/);
	await ctx.close();
	// Direction publishes.
	const d = await asRole(browser, 'direction');
	await d.page.goto(`/wp-admin/post.php?post=${id}&action=edit`);
	// WordPress post lock: the contributor was just editing; Direction takes over (standard WP dialog).
	const takeOver = d.page.locator('#post-lock-dialog a.button-primary');
	if (await takeOver.isVisible()) await takeOver.click();
	await d.page.click('#publish');
	await expect(d.page.locator('#post-status-display')).toContainText(/Publié/i);
	r = await anon.request.get(`/?post_type=asset_congres&p=${id}`);
	expect(r.status()).toBe(200);
	writeState({ contribCongresId: id });
	await d.ctx.close();
	await anon.close();
});

test('S1-H1 end before start and invalid URL rejected with a message; HTML in title shown as text', async ({ browser }) => {
	const { ctx, page } = await asRole(browser, 'admin');
	const id = readState().newCongresId;
	await page.goto(`/wp-admin/post.php?post=${id}&action=edit`);
	await fillCongres(page, { start: '2027-12-10', end: '2027-12-01', url: 'pas une url' });
	await page.click('#publish');
	const notice = page.locator('.asset-save-errors');
	await expect(notice).toContainText('date de fin');
	await expect(notice).toContainText('Site officiel');
	await expect(page.locator('#asset-field-asset_start')).toHaveValue('2027-12-06');
	await expect(page.locator('#asset-field-asset_end')).toHaveValue('2027-12-09');
	await expect(page.locator('#asset-field-asset_url')).toHaveValue('https://example.com/congres/test');
	// Script in title.
	let dialog = false;
	page.on('dialog', async (dg) => { dialog = true; await dg.dismiss(); });
	await page.fill('#title', 'Titre <script>alert(1)</script><img src=x onerror=alert(2)> — exemple');
	await page.click('#publish');
	await expect(page.locator('#message')).toBeVisible();
	const url = await page.locator('#sample-permalink a').getAttribute('href');
	await page.goto(url);
	expect(await page.locator('h1 script, h1 img, .wp-block-post-title script').count()).toBe(0);
	await page.goto('/?q=titre');
	expect(await page.locator('.asset-card script, .asset-card img').count()).toBe(0);
	expect(dialog).toBe(false);
	// Restore a clean title.
	await page.goto(`/wp-admin/post.php?post=${id}&action=edit`);
	await page.fill('#title', TITLE);
	await page.click('#publish');
	await expect(page.locator('#message')).toBeVisible();
	writeState({ newCongresUrl: await page.locator('#sample-permalink a').getAttribute('href') });
	await ctx.close();
});

test('S1-H2 saving without a valid nonce changes nothing', async ({ browser }) => {
	const { ctx, page } = await asRole(browser, 'admin');
	const id = readState().newCongresId;
	const res = await page.request.post('/wp-admin/post.php', {
		form: { action: 'editpost', post_ID: id, post_type: 'asset_congres', post_title: 'Piraté', 'asset_meta[_asset_city]': 'Pirate', asset_congres_nonce: 'bad', _wpnonce: 'bad' },
	});
	expect([403, 200]).toContain(res.status());
	expect(await res.text()).toMatch(/expiré|expired/i);
	await page.goto(`/wp-admin/post.php?post=${id}&action=edit`);
	await expect(page.locator('#asset-field-asset_city')).toHaveValue('Toulouse');
	await expect(page.locator('#title')).toHaveValue(TITLE);
	await ctx.close();
});
