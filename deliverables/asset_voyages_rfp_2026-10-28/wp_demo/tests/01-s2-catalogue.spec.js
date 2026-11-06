// S2: public catalogue, search, filters, details page (logged out).
const { test, expect } = require('playwright/test');
const { clickCounter, writeState, BASE } = require('./helpers');

test.describe.configure({ mode: 'serial' });

const cards = (page) => page.locator('.asset-grid .asset-card');
const count = async (page) => parseInt((await page.locator('.asset-count').innerText()).match(/\d+/)[0], 10);

test('S2-F1 all 12 published upcoming congresses are listed; past and draft are not', async ({ page }) => {
	await page.goto('/');
	expect(await count(page)).toBe(12);
	await expect(cards(page)).toHaveCount(9);
	await page.goto('/?pg=2');
	await expect(cards(page)).toHaveCount(3);
	for (const p of ['/', '/?pg=2']) {
		await page.goto(p);
		const html = await page.content();
		expect(html).not.toContain('hématologie, édition passée');
		expect(html).not.toContain('rhumatologie, brouillon');
	}
	// Past one appears only when explicitly asked.
	await page.goto('/?passes=1');
	expect(await count(page)).toBe(13);
});

test('S2-F2 keyword search: title, city, discipline, accent-insensitive', async ({ page }) => {
	const cases = { vienne: 2, diabetologie: 1, 'Diabétologie': 1, cardio: 2, lyon: 1, 'ressources humaines': 1, MARSEILLE: 1 };
	for (const [q, n] of Object.entries(cases)) {
		await page.goto('/?q=' + encodeURIComponent(q));
		expect(await count(page), q).toBe(n);
		await expect(cards(page)).toHaveCount(n);
	}
	await page.goto('/?q=vienne');
	await expect(page.locator('.asset-grid')).toContainText('Vienne');
});

test('S2-F3 filters alone and combined, result count, no-result message and reset', async ({ page }) => {
	await page.goto('/');
	await page.selectOption('#asset-f-discipline', 'oncologie');
	await Promise.all([page.waitForNavigation(), page.click('.asset-filters button[type=submit]')]);
	expect(await count(page)).toBe(2);
	await page.selectOption('#asset-f-pays', 'france');
	await Promise.all([page.waitForNavigation(), page.click('.asset-filters button[type=submit]')]);
	expect(await count(page)).toBe(1);
	await expect(cards(page).first()).toContainText('Marseille');
	await page.goto('/?pays=france');
	expect(await count(page)).toBe(3);
	await page.goto('/?mois=2027-09');
	expect(await count(page)).toBe(2);
	await page.goto('/?pays=autriche&mois=2027-06');
	expect(await count(page)).toBe(1);
	await page.goto('/?q=zzzzzz');
	expect(await count(page)).toBe(0);
	await expect(page.locator('.asset-empty')).toContainText('Aucun congrès ne correspond');
	await Promise.all([page.waitForNavigation(), page.click('.asset-filters .asset-link')]); // Réinitialiser
	expect(await count(page)).toBe(12);
});

test('S2-F4 pagination works and keeps active filters', async ({ page }) => {
	await page.goto('/?passes=1&tri=date_desc');
	expect(await count(page)).toBe(13);
	const next = page.locator('.asset-pagination a[rel=next]');
	const href = await next.getAttribute('href');
	expect(href).toContain('passes=1');
	expect(href).toContain('tri=date_desc');
	await Promise.all([page.waitForNavigation(), next.click()]);
	await expect(cards(page)).toHaveCount(4);
	await expect(page.locator('#asset-f-passes')).toBeChecked();
	await expect(page.locator('#asset-f-tri')).toHaveValue('date_desc');
});

test('S2-F5 details page shows all facts and the prefilled enquiry form', async ({ page }) => {
	await page.goto('/?q=madrid');
	await cards(page).first().locator('a').click();
	const d = page.locator('.asset-details');
	for (const t of ['Dates', 'Ville', 'Pays', 'Discipline', 'Lieu', 'Site officiel', 'Madrid', 'Espagne', 'Cardiologie', '27 août 2027', '30 août 2027', 'vérifiée le 15 octobre 2026']) {
		await expect(d).toContainText(t);
	}
	await expect(page.locator('.asset-quote__for')).toContainText('Congrès européen de cardiologie — exemple');
	writeState({ madridUrl: page.url() });
});

test('S2-F6 works with JavaScript off (server-rendered GET form)', async ({ browser }) => {
	const ctx = await browser.newContext({ javaScriptEnabled: false, baseURL: BASE });
	const page = await ctx.newPage();
	await page.goto('/');
	await page.fill('#asset-f-q', 'oncologie');
	await Promise.all([page.waitForNavigation(), page.click('.asset-filters button[type=submit]')]);
	expect(page.url()).toContain('q=oncologie');
	expect(await count(page)).toBe(2);
	await ctx.close();
});

test('S2-E1 find Cardiologie and open one in <= 2 clicks', async ({ page }) => {
	await page.goto('/');
	const c = clickCounter();
	await c.click(page.locator('.asset-chip', { hasText: 'Cardiologie' }));
	await expect(cards(page)).toHaveCount(2);
	await c.click(cards(page).first().locator('h2 a'));
	await expect(page.locator('.asset-details')).toContainText('Cardiologie');
	expect(c.n).toBeLessThanOrEqual(2);
	test.info().annotations.push({ type: 'clicks', description: String(c.n) });
});

test('S2-E2 at 390 px: no horizontal scroll, inputs >= 16 px, tap targets >= 44 px', async ({ browser }) => {
	const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1, baseURL: BASE, isMobile: true, hasTouch: true });
	const page = await ctx.newPage();
	for (const url of ['/', '/?discipline=cardiologie', '/?q=zzzz']) {
		await page.goto(url);
		const r = await page.evaluate(() => {
			const bad = [];
			const sw = document.documentElement.scrollWidth;
			for (const el of document.querySelectorAll('.asset-cd input:not([type=hidden]):not([type=checkbox]), .asset-cd select, .asset-cd textarea')) {
				if (el.closest('.asset-hp')) continue;
				const fs = parseFloat(getComputedStyle(el).fontSize);
				if (fs < 16) bad.push('font ' + (el.id || el.name) + ' ' + fs);
			}
			const targets = '.asset-cd button, .asset-cd input:not([type=hidden]):not([type=checkbox]), .asset-cd select, .asset-chip, .asset-pagination a, .asset-btn, .asset-link, .asset-card, .asset-field--check';
			for (const el of document.querySelectorAll(targets)) {
				if (el.closest('.asset-hp')) continue;
				const b = el.getBoundingClientRect();
				if (b.width === 0) continue;
				if (b.height < 44 - 0.5) bad.push('target ' + el.className + ' ' + b.height);
			}
			return { sw, bad };
		});
		expect(r.sw, url).toBeLessThanOrEqual(390);
		expect(r.bad, url).toEqual([]);
	}
	// Details page + form.
	await page.goto('/?q=madrid');
	await page.goto(await page.locator('.asset-card h2 a').first().getAttribute('href'));
	await page.waitForSelector('.asset-form button');
	const r = await page.evaluate(() => ({
		sw: document.documentElement.scrollWidth,
		small: [...document.querySelectorAll('.asset-form input:not([type=hidden]):not([type=checkbox]), .asset-form textarea')].filter((e) => !e.closest('.asset-hp') && parseFloat(getComputedStyle(e).fontSize) < 16).length,
		btn: document.querySelector('.asset-form button').getBoundingClientRect().height,
	}));
	expect(r.sw).toBeLessThanOrEqual(390);
	expect(r.small).toBe(0);
	expect(r.btn).toBeGreaterThanOrEqual(44);
	await ctx.close();
});

test('S2-H1 script/HTML in search is escaped; 5,000-char query does not error', async ({ page }) => {
	let dialog = false;
	page.on('dialog', async (d) => { dialog = true; await d.dismiss(); });
	await page.goto('/?q=' + encodeURIComponent('<script>alert(1)</script><img src=x onerror=alert(2)>'));
	expect(await page.locator('script:has-text("alert(1)")').count()).toBe(0);
	expect(await page.locator('img[src="x"]').count()).toBe(0);
	expect(dialog).toBe(false);
	const res = await page.goto('/?q=' + 'a'.repeat(5000));
	expect(res.status()).toBe(200);
	await expect(page.locator('.asset-count')).toBeVisible();
});
