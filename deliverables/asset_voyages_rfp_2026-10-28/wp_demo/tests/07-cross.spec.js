// Cross-cutting gates X1-X4.
const { test, expect } = require('playwright/test');
const { asRole, readState, CODES } = require('./helpers');

// Independent tests: one failure must not stop the others (no serial mode).

const ORIGIN = 'http://127.0.0.1:9400';

function watch(page, bucket, label) {
	page.on('console', (m) => { if (m.type() === 'error') bucket.push(`${label} console: ${m.text()}`); });
	page.on('pageerror', (e) => bucket.push(`${label} pageerror on ${page.url()}: ${e.message} :: ${(e.stack || '').split('\n').slice(1, 4).join(' | ')}`));
	page.on('requestfailed', (r) => bucket.push(`${label} failed: ${r.url()} ${r.failure() && r.failure().errorText}`));
	page.on('response', (r) => { if (r.status() >= 400) bucket.push(`${label} HTTP ${r.status()}: ${r.url()}`); });
}

test('X1 zero console errors and zero failed requests on every tested screen', async ({ browser }) => {
	const problems = [];
	const s = readState();
	const visitor = await browser.newContext();
	const vp = await visitor.newPage();
	watch(vp, problems, 'visitor');
	for (const u of ['/', '/?discipline=cardiologie', '/?q=zzzz', '/?passes=1&pg=2', s.madridUrl, s.confirmUrl, '/congres/']) await vp.goto(u);
	await vp.goto(s.madridUrl);
	await vp.waitForTimeout(3300);
	await vp.click('.asset-form button[type=submit]');
	await expect(vp.locator('.asset-notice--error')).toBeVisible();
	await visitor.close();
	const screens = {
		equipe: ['/wp-admin/', '/wp-admin/admin.php?page=asset-demandes', '/wp-admin/admin.php?page=asset-demandes&statut=nouvelle', '/wp-admin/admin.php?page=asset-gme', '/wp-admin/admin.php?page=asset-notifications', '/wp-admin/edit.php?post_type=asset_congres', `/wp-admin/post.php?post=${s.newCongresId}&action=edit`],
		direction: ['/wp-admin/', '/wp-admin/admin.php?page=asset-gme', '/wp-admin/admin.php?page=asset-gme-acces', '/wp-admin/admin.php?page=asset-gme-journal'],
		contributeur: ['/wp-admin/', '/wp-admin/post-new.php?post_type=asset_congres'],
		admin: ['/wp-admin/', '/wp-admin/tools.php?page=asset-demo-tools'],
	};
	for (const [role, urls] of Object.entries(screens)) {
		const { ctx, page } = await asRole(browser, role);
		watch(page, problems, role);
		for (const u of urls) { await page.goto(u); await page.waitForLoadState('networkidle'); }
		if (role === 'equipe') {
			await page.goto('/wp-admin/admin.php?page=asset-demandes');
			await page.locator('a.row-title').first().click();
			await page.waitForLoadState('networkidle');
		}
		await ctx.close();
	}
	expect(problems).toEqual([]);
});

test('X2 visitor pages load no third-party scripts or requests', async ({ browser }) => {
	const ctx = await browser.newContext();
	const page = await ctx.newPage();
	const foreign = [];
	page.on('request', (r) => { if (!r.url().startsWith(ORIGIN) && !r.url().startsWith('data:')) foreign.push(r.url()); });
	for (const u of ['/', '/?discipline=oncologie', readState().madridUrl, readState().confirmUrl]) {
		await page.goto(u);
		await page.waitForLoadState('networkidle');
		const srcs = await page.$$eval('script[src]', (els) => els.map((e) => e.src));
		for (const src of srcs) expect(src.startsWith(ORIGIN), src).toBe(true);
	}
	expect(foreign).toEqual([]);
	await ctx.close();
});

test('X3 all data fictional: titles end « — exemple », emails @example.com, codes DEMO-GME-…', async ({ browser }) => {
	const anon = await browser.newContext();
	const list = await (await anon.request.get(ORIGIN + '/wp-json/wp/v2/asset_congres?per_page=100')).json();
	expect(list.length).toBeGreaterThanOrEqual(13);
	for (const c of list) {
		const t = c.title.rendered.replace(/&#8212;/g, '—').replace(/&#8217;/g, '’');
		expect(t, t).toMatch(/— exemple$/);
		if (c.content.rendered.trim()) expect(c.content.rendered).toMatch(/fictive|fictif|exemple|test/i);
	}
	await anon.close();
	const { ctx, page } = await asRole(browser, 'direction');
	await page.goto('/wp-admin/admin.php?page=asset-demandes');
	const csv = await (await page.request.get(await page.locator('a.page-title-action', { hasText: 'CSV' }).getAttribute('href'))).text();
	const emails = [...csv.matchAll(/[\w.+-]+@[\w.-]+\.[a-z]{2,}/gi)].map((m) => m[0]);
	expect(emails.length).toBeGreaterThan(5);
	for (const e of emails) expect(e, e).toMatch(/@example\.com$/);
	// Reveal each code as Direction: all are dummy DEMO-GME-XXXX.
	await page.goto('/wp-admin/admin.php?page=asset-gme');
	const n = await page.locator('table.asset-gme-table tbody tr').count();
	expect(n).toBe(5);
	let revealed = 0;
	for (let i = 0; i < n; i++) {
		const btn = page.locator('table.asset-gme-table tbody tr').nth(i).locator('button', { hasText: 'Révéler' });
		if (!(await btn.count())) continue; // expired code: closed to everyone
		await btn.click();
		await expect(page.locator('code.asset-revealed')).toHaveText(/^DEMO-GME-[A-Z0-9]{4}$/);
		revealed += 1;
	}
	expect(revealed).toBe(4);
	await ctx.close();
});

test('X4 re-seeding is idempotent (no duplicates)', async ({ browser }) => {
	const { ctx, page } = await asRole(browser, 'admin');
	const countAll = async () => {
		await page.goto('/wp-admin/admin.php?page=asset-demandes');
		const d = parseInt((await page.locator('.subsubsub li').first().innerText()).match(/\((\d+)\)/)[1], 10);
		await page.goto('/wp-admin/edit.php?post_type=asset_congres');
		const c = parseInt((await page.locator('.subsubsub .all .count').innerText()).replace(/\D/g, ''), 10);
		await page.goto('/wp-admin/admin.php?page=asset-gme');
		const g = await page.locator('table.asset-gme-table tbody tr').count();
		await page.goto('/wp-admin/users.php');
		const u = parseInt((await page.locator('.subsubsub .all .count').innerText()).replace(/\D/g, ''), 10);
		return { d, c, g, u };
	};
	const before = await countAll();
	await page.goto('/wp-admin/tools.php?page=asset-demo-tools');
	await page.click('#submit');
	await expect(page.locator('.asset-seeded')).toContainText('0 élément(s) créé(s)');
	await page.click('#submit');
	await expect(page.locator('.asset-seeded')).toContainText('0 élément(s) créé(s)');
	expect(await countAll()).toEqual(before);
	await ctx.close();
});
