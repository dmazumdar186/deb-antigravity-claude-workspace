// S4: the team receives, views, tracks and updates enquiries (logged in as equipe).
const { test, expect } = require('playwright/test');
const { asRole, clickCounter, readState, writeState, CODES } = require('./helpers');

test.describe.configure({ mode: 'serial' });

const widgetCount = async (page, label) => {
	const li = page.locator('#asset_cd_demandes .asset-widget li', { hasText: label });
	return parseInt(await li.locator('.asset-widget__n').innerText(), 10);
};

test('S4-F1 the S3 enquiry appears in « Demandes » with all columns and status Nouvelle', async ({ browser }) => {
	const { ctx, page } = await asRole(browser, 'equipe');
	await page.click('#toplevel_page_asset-demandes > a');
	const ref = readState().newRef;
	const row = page.locator('table.wp-list-table tbody tr', { hasText: ref });
	await expect(row).toHaveCount(1);
	for (const t of [ref, 'Congrès européen de cardiologie — exemple', 'Alice Testeur', 'alice.testeur@example.com', 'Nice', '26/08/2027', '31/08/2027', 'Nouvelle']) await expect(row).toContainText(t);
	await expect(row.locator('td.column-passagers')).toHaveText('2');
	for (const h of ['Référence', 'Date', 'Congrès', 'Contact', 'Départ', 'Dates', 'Passagers', 'Statut', 'Responsable']) {
		await expect(page.locator('table.wp-list-table thead')).toContainText(h);
	}
	await ctx.close();
});

test('S4-F2 filter by status and search by name / reference', async ({ browser }) => {
	const { ctx, page } = await asRole(browser, 'equipe');
	await page.goto('/wp-admin/admin.php?page=asset-demandes');
	await page.locator('.subsubsub a', { hasText: 'Qualifiée' }).click();
	const rows = page.locator('table.wp-list-table tbody tr');
	await expect(rows).toHaveCount(1);
	await expect(rows.first()).toContainText('DV-2026-0001');
	await page.goto('/wp-admin/admin.php?page=asset-demandes');
	await page.fill('#asset-demandes-search-input', 'Dubois');
	await page.click('#search-submit');
	await expect(rows).toHaveCount(1);
	await expect(rows.first()).toContainText('DV-2026-0002');
	await page.fill('#asset-demandes-search-input', readState().newRef);
	await page.click('#search-submit');
	await expect(rows).toHaveCount(1);
	// Sorting by passengers.
	await page.goto('/wp-admin/admin.php?page=asset-demandes&orderby=passagers&order=desc');
	await expect(rows.first()).toContainText('25');
	await ctx.close();
});

test('S4-E1 from admin home, open the newest enquiry and change its status in <= 3 clicks; counts update', async ({ browser }) => {
	const { ctx, page } = await asRole(browser, 'equipe');
	await page.goto('/wp-admin/');
	const nouvelle = await widgetCount(page, 'Nouvelle');
	const qualifiee = await widgetCount(page, 'Qualifiée');
	const c = clickCounter();
	await c.click(page.locator('#asset_cd_demandes .asset-latest-link'));
	await page.waitForURL(/action=view/);
	const ref = (await page.locator('h1').innerText()).match(/DV-2026-\d{4}/)[0];
	c.n += 1; await page.selectOption('#asset-statut', 'qualifiee');
	await c.click(page.locator('#submit'));
	await expect(page.locator('.notice-success')).toContainText('mise à jour');
	expect(c.n).toBeLessThanOrEqual(3);
	test.info().annotations.push({ type: 'clicks', description: String(c.n) });
	await page.goto('/wp-admin/');
	expect(await widgetCount(page, 'Nouvelle')).toBe(nouvelle - 1);
	expect(await widgetCount(page, 'Qualifiée')).toBe(qualifiee + 1);
	writeState({ latestRef: ref });
	await ctx.close();
});

test('S4-F3 status flow saved, owner assigned, internal note saved', async ({ browser }) => {
	const { ctx, page } = await asRole(browser, 'equipe');
	const ref = readState().newRef;
	await page.goto('/wp-admin/admin.php?page=asset-demandes&s=' + ref);
	await page.goto(await page.locator('a.row-title', { hasText: ref }).first().getAttribute('href'));
	const detail = page.url();
	for (const s of ['qualifiee', 'devis_envoye', 'gagnee']) {
		await page.selectOption('#asset-statut', s);
		await page.click('#submit');
		await expect(page.locator('#asset-statut')).toHaveValue(s);
	}
	await page.selectOption('#asset-owner', { label: 'Équipe (démo)' });
	await page.fill('#asset-note', 'Client rappelé, devis groupe envoyé (note de test).');
	await page.click('#submit');
	await expect(page.locator('#asset-owner option:checked')).toHaveText('Équipe (démo)');
	await page.goto(detail);
	await expect(page.locator('.asset-history')).toContainText('devis groupe envoyé');
	// Perdue path on another enquiry.
	await page.goto('/wp-admin/admin.php?page=asset-demandes&s=DV-2026-0005');
	await page.goto(await page.locator('a.row-title', { hasText: 'DV-2026-0005' }).first().getAttribute('href'));
	await page.selectOption('#asset-statut', 'perdue');
	await page.click('#submit');
	await expect(page.locator('#asset-statut')).toHaveValue('perdue');
	await ctx.close();
});

test('S4-F4 history is append-only: who, when, from → to; no edit or delete controls', async ({ browser }) => {
	const { ctx, page } = await asRole(browser, 'equipe');
	const ref = readState().newRef;
	await page.goto('/wp-admin/admin.php?page=asset-demandes&s=' + ref);
	await page.goto(await page.locator('a.row-title', { hasText: ref }).first().getAttribute('href'));
	const h = page.locator('table.asset-history tbody tr');
	expect(await h.count()).toBeGreaterThanOrEqual(6);
	const text = await page.locator('table.asset-history').innerText();
	for (const t of ['Nouvelle → Qualifiée', 'Qualifiée → Devis envoyé', 'Devis envoyé → Gagnée', '— → Équipe (démo)', 'Formulaire public', 'Équipe (démo)']) expect(text).toContain(t);
	expect(text).toMatch(/\d{2}\/\d{2}\/\d{4} \d{2}:\d{2}/);
	expect(text).not.toMatch(/\d{4}-\d{2}-\d{2}|UTC/);
	expect(await page.locator('table.asset-history input, table.asset-history button, table.asset-history form, table.asset-history a').count()).toBe(0);
	// No generic editor for the enquiry post type.
	const id = new URL(page.url()).searchParams.get('id');
	const r = await page.request.get(`/wp-admin/post.php?post=${id}&action=edit`);
	expect(await r.text()).not.toContain('id="post"');
	await ctx.close();
});

test('S4-F5 CSV export contains enquiries; formula prefixes neutralised', async ({ browser }) => {
	const { ctx, page } = await asRole(browser, 'equipe');
	await page.goto('/wp-admin/admin.php?page=asset-demandes');
	const href = await page.locator('a.page-title-action', { hasText: 'CSV' }).getAttribute('href');
	const res = await page.request.get(href);
	expect(res.headers()['content-type']).toContain('text/csv');
	const csv = await res.text();
	for (const ref of ['DV-2026-0001', readState().newRef, readState().formulaRef]) expect(csv).toContain(ref);
	expect(csv).toContain("'=cmd|");
	expect(csv).toContain("'+SUM(1,2)");
	expect(csv).toContain("'@Lyon");
	expect(csv).not.toMatch(/(^|;)"?=cmd/m);
	expect(csv).not.toMatch(/(^|;)"?\+SUM/m);
	for (const code of CODES) expect(csv).not.toContain(code);
	writeState({ csvLines: csv.trim().split('\n').length });
	await ctx.close();
});

test('S4-H1 logged-out and contributor users cannot read or change enquiries', async ({ browser }) => {
	const anon = await browser.newContext();
	let r = await anon.request.get('/wp-admin/admin.php?page=asset-demandes', { maxRedirects: 0 });
	expect(r.status()).toBe(302);
	expect(r.headers().location).toContain('wp-login.php');
	r = await anon.request.post('/wp-admin/admin-post.php', { form: { action: 'asset_demande_update', id: '1', statut: 'perdue' } });
	expect(r.status()).toBeGreaterThanOrEqual(400);
	r = await anon.request.get('/wp-admin/admin-post.php?action=asset_demandes_export');
	expect(r.status()).toBeGreaterThanOrEqual(400);
	await anon.close();

	const { ctx, page } = await asRole(browser, 'contributeur');
	expect(await page.locator('#toplevel_page_asset-demandes').count()).toBe(0);
	r = await page.request.get('/wp-admin/admin.php?page=asset-demandes');
	expect(r.status()).toBe(403);
	expect(await r.text()).not.toContain('DV-2026-0001');
	r = await page.request.get('/wp-admin/admin.php?page=asset-notifications');
	expect(r.status()).toBe(403);
	// Find a real id via the equipe account, then try to change it as contributor.
	const eq = await asRole(browser, 'equipe');
	await eq.page.goto('/wp-admin/admin.php?page=asset-demandes&s=DV-2026-0002');
	await eq.page.goto(await eq.page.locator('a.row-title').first().getAttribute('href'));
	const id = new URL(eq.page.url()).searchParams.get('id');
	const before = await eq.page.locator('#asset-statut').inputValue();
	r = await page.request.post('/wp-admin/admin-post.php', { form: { action: 'asset_demande_update', id, statut: 'perdue', asset_nonce: 'forged' } });
	expect(r.status()).toBe(403);
	r = await page.request.get('/wp-admin/admin-post.php?action=asset_demandes_export&_wpnonce=forged');
	expect(r.status()).toBe(403);
	await eq.page.reload();
	await expect(eq.page.locator('#asset-statut')).toHaveValue(before);
	await eq.ctx.close();
	await ctx.close();
});
