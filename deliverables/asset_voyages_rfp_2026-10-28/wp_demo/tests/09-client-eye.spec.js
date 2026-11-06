// Client-eye gate fixes for Option A: one test per REAL finding in ../../qa/register/CLIENT_EYE.md
// (Option A or A+B). Labels follow ../../29_Glossary_Labels.md.
const { test, expect } = require('playwright/test');
const { asRole, BASE } = require('./helpers');

const WIDTHS = [320, 390, 768, 1280, 1440, 1920];

// Minimal RFC 4180 parser for the « ; » export (quoted cells may hold « ; », quotes and newlines).
function parseCsv(text) {
	const rows = [];
	let row = [];
	let cell = '';
	let q = false;
	for (let i = 0; i < text.length; i++) {
		const ch = text[i];
		if (q) {
			if (ch === '"' && text[i + 1] === '"') { cell += '"'; i++; } else if (ch === '"') q = false; else cell += ch;
		} else if (ch === '"') q = true;
		else if (ch === ';') { row.push(cell); cell = ''; } else if (ch === '\n' || ch === '\r') {
			if (ch === '\r' && text[i + 1] === '\n') i++;
			row.push(cell); rows.push(row); row = []; cell = '';
		} else cell += ch;
	}
	if (cell || row.length) { row.push(cell); rows.push(row); }
	return rows.filter((r) => r.some((c) => c !== ''));
}

// Every element whose own text ends in « exemple »: the dash, the word before it and « exemple » must
// sit on the same line (a Range per character, compared by top edge).
async function orphanDashes(page, selector) {
	return page.evaluate((sel) => {
		const bad = [];
		const rectTop = (node, i) => {
			const r = document.createRange();
			r.setStart(node, i);
			r.setEnd(node, i + 1);
			const rects = r.getClientRects();
			return rects.length ? Math.round(rects[0].top) : null;
		};
		for (const el of document.querySelectorAll(sel)) {
			if (!el.offsetParent && getComputedStyle(el).position !== 'fixed') continue;
			const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
			const chars = [];
			for (let n = walker.nextNode(); n; n = walker.nextNode()) for (let i = 0; i < n.data.length; i++) chars.push([n, i]);
			const text = chars.map(([n, i]) => n.data[i]).join('');
			const m = text.match(/(\S)[\s ]*—[\s ]*exempl(e)\s*$/);
			if (!m) continue;
			const dash = text.lastIndexOf('—');
			const before = text.slice(0, dash).search(/\S[\s ]*$/);
			const last = text.lastIndexOf('e');
			const tops = [before, dash, last].map((k) => rectTop(chars[k][0], chars[k][1]));
			if (new Set(tops).size !== 1) bad.push(text.trim().slice(-40) + ' ' + JSON.stringify(tops));
		}
		return bad;
	}, selector);
}

test('CE-B4-004 « — exemple » never wraps onto its own line (catalogue, congress page, quote form, admin lists) at six widths', async ({ browser }) => {
	const v = await asRole(browser, null);
	await v.page.goto('/');
	expect(await v.page.locator('.asset-card__title .asset-nowrap').count()).toBe(9);
	const t = await v.page.locator('.asset-card__title a').first().innerText();
	const raw = await v.page.locator('.asset-card__title a').first().evaluate((e) => e.textContent);
	expect(raw, t).toMatch(/ — exemple$/);
	const single = await v.page.locator('.asset-card__title a').first().getAttribute('href');
	const d = await asRole(browser, 'direction');
	const c = await asRole(browser, 'contributeur');
	await d.page.goto('/wp-admin/admin.php?page=asset-demandes');
	const detail = await d.page.locator('#the-list a.row-title').first().getAttribute('href');
	for (const w of WIDTHS) {
		for (const [p, url, sel] of [
			[v.page, '/', '.asset-card__title a'],
			[v.page, '/?pg=2', '.asset-card__title a'],
			[v.page, single, 'h1.wp-block-post-title, .asset-quote__for'],
			[d.page, '/wp-admin/admin.php?page=asset-gme', 'table.asset-gme-table td strong, table.asset-pending td'],
			[d.page, '/wp-admin/edit.php?post_type=asset_congres', '#the-list .row-title'],
			[d.page, '/wp-admin/admin.php?page=asset-demandes', '#the-list td.column-congres'],
			[c.page, '/wp-admin/edit.php?post_type=asset_congres', '#the-list .column-title strong'],
			[d.page, '/wp-admin/index.php', '.asset-widget-latest a, .asset-widget-req p'],
			[d.page, '/wp-admin/admin.php?page=asset-gme-journal', 'table.asset-log td'],
			[d.page, '/wp-admin/admin.php?page=asset-gme-acces', 'table.asset-access-history td'],
			[d.page, detail, 'table.asset-kv td'],
		]) {
			await p.setViewportSize({ width: w, height: 900 });
			await p.goto(url);
			expect(await orphanDashes(p, sel), `${url} @ ${w}px`).toEqual([]);
		}
	}
	await expect(v.page.locator('.asset-quote__for .asset-nowrap')).toHaveCount(1);
	await expect(v.page.locator('h1.wp-block-post-title .asset-nowrap')).toHaveCount(1);
	for (const x of [v, d, c]) await x.ctx.close();
});

test('CE-B4-005 no word is split across lines in the Demandes table (1280, 1440, 1920 px)', async ({ browser }) => {
	const { ctx, page } = await asRole(browser, 'direction');
	for (const w of [1280, 1440, 1920]) {
		await page.setViewportSize({ width: w, height: 900 });
		await page.goto('/wp-admin/admin.php?page=asset-demandes');
		const split = await page.evaluate(() => {
			const out = [];
			for (const td of document.querySelectorAll('#the-list td')) {
				const walker = document.createTreeWalker(td, NodeFilter.SHOW_TEXT);
				for (let n = walker.nextNode(); n; n = walker.nextNode()) {
					const re = /[^\s @]+/g;
					let m;
					while ((m = re.exec(n.data))) {
						if (m[0].length < 2) continue;
						const r = document.createRange();
						r.setStart(n, m.index);
						r.setEnd(n, m.index + m[0].length);
						const tops = new Set([...r.getClientRects()].filter((x) => x.width > 0).map((x) => Math.round(x.top)));
						if (tops.size > 1) out.push(m[0]);
					}
				}
			}
			return out;
		});
		expect(split, `${w}px`).toEqual([]);
	}
	await ctx.close();
});

test('CE-B6-001…008 labels follow the glossary (menu, buttons, headings)', async ({ browser }) => {
	const { ctx, page } = await asRole(browser, 'direction');
	await page.goto('/wp-admin/index.php');
	const top = page.locator('#toplevel_page_asset-gme');
	await expect(top.locator('> a .wp-menu-name')).toHaveText('Codes GM&E');
	const subs = (await top.locator('.wp-submenu li a').allInnerTexts()).map((s) => s.trim());
	expect(subs).toEqual(['Codes', 'Demandes d’accès', 'Journal d’accès GM&E']);
	await expect(page.locator('#menu-posts-asset_congres .wp-submenu')).toContainText('Ajouter un congrès');
	await expect(page.locator('#toplevel_page_asset-demandes .wp-submenu')).toContainText('Journal des notifications');
	const menu = await page.locator('#adminmenu').innerText();
	for (const old of ['Accès GM&E', 'Journal GM&E']) expect(menu).not.toContain(old);

	await page.goto('/wp-admin/admin.php?page=asset-gme');
	await expect(page.locator('h1')).toHaveText('Codes GM&E');
	await expect(page.locator('table.asset-pending button', { hasText: 'Approuver pour 24 h' }).first()).toBeVisible();
	const neuro = page.locator('table.asset-gme-table tbody tr', { hasText: 'neurologie' });
	await Promise.all([page.waitForNavigation(), neuro.locator('button', { hasText: 'Afficher le code' }).click()]);
	await expect(neuro.locator('code.asset-revealed')).toBeVisible();
	await expect(page.locator('.notice')).toContainText('journal d’accès GM&E');
	await Promise.all([page.waitForNavigation(), neuro.locator('a', { hasText: 'Masquer le code' }).click()]);
	await expect(neuro.locator('code.asset-revealed')).toHaveCount(0);
	const body = await page.locator('#wpbody').innerText();
	for (const old of ['Révéler', 'Révoquer', 'Approuver (24 h)']) expect(body).not.toContain(old);

	await page.goto('/wp-admin/admin.php?page=asset-gme-journal');
	await expect(page.locator('h1')).toHaveText('Journal d’accès GM&E');
	await expect(page.locator('table.asset-log')).toContainText('Code affiché');
	await page.goto('/wp-admin/admin.php?page=asset-gme-acces');
	expect(await page.locator('table.asset-access-history button', { hasText: 'Révoquer' }).count()).toBe(0);
	await page.goto('/wp-admin/admin.php?page=asset-demandes');
	await expect(page.locator('a.page-title-action')).toHaveText('Exporter en CSV');

	const v = await asRole(browser, null);
	await v.page.goto('/');
	await v.page.locator('.asset-card__title a').first().click();
	await expect(v.page.locator('#asset-quote-title')).toHaveText('Demander un devis vol');
	await expect(v.page.locator('form.asset-form button[type=submit]')).toHaveText('Envoyer ma demande');
	await expect(v.page.locator('.asset-team-link').first()).toContainText('Espace équipe');
	await v.ctx.close();
	await ctx.close();
});

test('CE-D1-001 Direction edits, publishes and deletes pages (its own and others\'), without admin powers', async ({ browser }) => {
	const { ctx, page } = await asRole(browser, 'direction');
	const bad = [];
	page.on('response', (r) => { if (r.status() >= 400) bad.push(r.status() + ' ' + r.url()); });
	page.on('console', (m) => { if (m.type() === 'error') bad.push('console ' + m.text()); });
	const list = await page.goto('/wp-admin/edit.php?post_type=page');
	expect(list.status()).toBe(200);
	await expect(page.locator('#the-list')).toContainText('Catalogue des congrès');
	await expect(page.locator('#menu-pages')).toBeVisible();
	expect(await page.locator('#menu-posts').count()).toBe(0); // no blog menu
	expect((await page.goto('/wp-admin/post-new.php?post_type=page')).status()).toBe(200);
	await page.waitForFunction(() => window.wp && wp.data && wp.data.select('core/editor') && wp.data.select('core/editor').getCurrentPostId(), null, { timeout: 60000 });
	await page.waitForTimeout(4000); // let the editor's REST reads finish
	expect(bad, 'editor loads without 4xx or console errors').toEqual([]);
	const res = await page.evaluate(async () => {
		const mine = await wp.apiFetch({ path: '/wp/v2/pages', method: 'POST', data: { title: 'Page de test — exemple', content: 'Texte fictif.', status: 'publish' } });
		const edited = await wp.apiFetch({ path: '/wp/v2/pages/' + mine.id, method: 'POST', data: { title: 'Page de test modifiée — exemple' } });
		const others = (await wp.apiFetch({ path: '/wp/v2/pages?context=edit&per_page=100&status=publish' })).filter((p) => p.author !== mine.author);
		let otherEdit = null;
		if (others.length) otherEdit = (await wp.apiFetch({ path: '/wp/v2/pages/' + others[0].id, method: 'POST', data: { excerpt: 'Résumé (test).' } })).id;
		const del = await wp.apiFetch({ path: '/wp/v2/pages/' + mine.id + '?force=true', method: 'DELETE' });
		return { status: mine.status, edited: edited.title.raw, others: others.length, otherEdit, deleted: del.deleted };
	});
	expect(res.status).toBe('publish');
	expect(res.edited).toBe('Page de test modifiée — exemple');
	expect(res.others).toBeGreaterThan(0);
	expect(res.otherEdit).not.toBeNull();
	expect(res.deleted).toBe(true);
	// Least privilege: no users, plugins, themes, options; unfiltered HTML is stripped.
	for (const u of ['/wp-admin/users.php', '/wp-admin/plugins.php', '/wp-admin/themes.php', '/wp-admin/options-general.php', '/wp-admin/user-new.php']) {
		expect((await page.goto(u)).status(), u).toBe(403);
	}
	await page.goto('/wp-admin/post-new.php?post_type=page');
	await page.waitForFunction(() => window.wp && wp.apiFetch, null, { timeout: 60000 });
	const html = await page.evaluate(async () => {
		const p = await wp.apiFetch({ path: '/wp/v2/pages', method: 'POST', data: { title: 'Script — exemple', content: '<p>ok</p><script>alert(1)</script>', status: 'draft' } });
		const raw = (await wp.apiFetch({ path: '/wp/v2/pages/' + p.id + '?context=edit' })).content.raw;
		await wp.apiFetch({ path: '/wp/v2/pages/' + p.id + '?force=true', method: 'DELETE' });
		return raw;
	}).catch((e) => 'error ' + e.message);
	expect(html).not.toContain('<script');
	await ctx.close();
});

test('CE-C7-003 an expired session lands on the login page with « Votre session a expiré. Reconnectez-vous. »', async ({ browser }) => {
	const { ctx, page } = await asRole(browser, 'equipe');
	await page.goto('/wp-admin/admin.php?page=asset-demandes');
	await ctx.clearCookies(); // the session ends
	await page.reload();
	await expect(page).toHaveURL(/wp-login\.php.*reauth=1/);
	await expect(page.locator('#login .asset-session-expired')).toHaveText('Votre session a expiré. Reconnectez-vous.');
	// Signing in again goes back to the page that was open.
	await page.fill('#user_login', 'equipe');
	await page.fill('#user_pass', 'demo-asset');
	await Promise.all([page.waitForURL(/page=asset-demandes/), page.click('#wp-submit')]);
	// A plain visit to the login page says nothing about a session.
	await ctx.clearCookies();
	await page.goto('/wp-login.php');
	expect(await page.locator('.asset-session-expired').count()).toBe(0);
	await ctx.close();
});

test('CE-D2-002 seed: no real congress name, phones in the fictional 01 99 00 range', async ({ browser }) => {
	const v = await asRole(browser, null);

	await v.page.goto('/?q=imagerie');
	await expect(v.page.locator('.asset-grid')).toContainText('Rencontres européennes d’imagerie médicale');
	for (const u of ['/', '/?pg=2', '/?passes=1']) {
		await v.page.goto(u);
		expect((await v.page.content()).toLowerCase()).not.toContain('congrès européen de radiologie');
	}
	await v.ctx.close();
	const { ctx, page } = await asRole(browser, 'direction');
	await page.goto('/wp-admin/admin.php?page=asset-demandes');
	const csv = await (await page.request.get(await page.locator('a.page-title-action').getAttribute('href'))).text();
	const rows = parseCsv(csv.replace(/^﻿/, ''));
	const col = rows[0].findIndex((h) => /t[ée]l[ée]phone/i.test(h));
	expect(col).toBeGreaterThan(-1);
	const phones = rows.slice(1).map((r) => r[col]).filter(Boolean);
	expect(phones.length).toBeGreaterThanOrEqual(6);
	for (const p of phones) expect(p, p).toMatch(/^(01 99 00|\+33 1 99 00) \d\d \d\d$/);
	await ctx.close();
});

test('CE-A4-002 « Site officiel : fictif (démonstration) » as text, no example.com link; every link on a congress page answers', async ({ browser }) => {
	const v = await asRole(browser, null);
	await v.page.goto('/');
	const hrefs = await v.page.locator('.asset-card__title a').evaluateAll((as) => as.map((a) => a.href));
	for (const h of hrefs) {
		await v.page.goto(h);
		await expect(v.page.locator('.asset-site-fictif')).toHaveText(/^Site officiel\s: fictif \(démonstration\)$/);
		expect(await v.page.locator('a[href*="example.com"], a[href*="example.org"], a[href*="example.net"]').count(), h).toBe(0);
	}
	const links = [...new Set(await v.page.locator('a[href]').evaluateAll((as) => as.map((a) => a.href.split('#')[0])))];
	for (const l of links) {
		expect(l.startsWith(BASE), l).toBe(true);
		const r = await v.page.request.get(l, { maxRedirects: 5 });
		expect(r.status(), l).toBeLessThan(400);
	}
	await v.ctx.close();
});

test('CE-B2-001 CSV file name carries the Paris date, not UTC', async ({ browser }) => {
	const { ctx, page } = await asRole(browser, 'direction');
	await page.goto('/wp-admin/admin.php?page=asset-demandes');
	const r = await page.request.get(await page.locator('a.page-title-action').getAttribute('href'));
	const paris = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Paris', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date()).replace(/-/g, '');
	expect(r.headers()['content-disposition']).toContain(`demandes-asset-${paris}.csv`);
	await ctx.close();
});

test('CE-C1-001 admin pages: no wp-compression-test request, no 4xx/5xx, no console errors (direction, equipe)', async ({ browser }) => {
	for (const role of ['direction', 'equipe']) {
		const { ctx, page } = await asRole(browser, role);
		const bad = [];
		page.on('request', (q) => { if (q.url().includes('wp-compression-test')) bad.push('request ' + q.url()); });
		page.on('response', (r) => { if (r.status() >= 400) bad.push(r.status() + ' ' + r.url()); });
		page.on('console', (m) => { if (m.type() === 'error') bad.push('console ' + m.text()); });
		for (const u of ['/wp-admin/index.php', '/wp-admin/admin.php?page=asset-gme', '/wp-admin/admin.php?page=asset-demandes', '/wp-admin/edit.php?post_type=asset_congres']) {
			await page.goto(u);
			await page.waitForTimeout(1500);
		}
		expect(bad, role).toEqual([]);
		await ctx.close();
	}
});

test('CE-C4-001 plugin screens do not shift after load (CLS ≤ 0.02), notices stay where they are printed', async ({ browser }) => {
	const measure = async (page, url) => {
		await page.goto(url);
		await page.waitForTimeout(3000);
		return page.evaluate(() => window.__cls);
	};
	const init = () => {
		window.__cls = 0;
		new PerformanceObserver((l) => { for (const e of l.getEntries()) if (!e.hadRecentInput) window.__cls += e.value; }).observe({ type: 'layout-shift', buffered: true });
	};
	const e = await asRole(browser, 'equipe');
	await e.ctx.addInitScript(init);
	const d = await asRole(browser, 'direction');
	await d.ctx.addInitScript(init);
	await d.page.goto('/wp-admin/admin.php?page=asset-demandes');
	const detail = await d.page.locator('#the-list a.row-title').first().getAttribute('href');
	for (const [p, u] of [
		[e.page, '/wp-admin/admin.php?page=asset-gme'],
		[e.page, '/wp-admin/admin.php?page=asset-gme&msg=requested'],
		[d.page, detail + '&updated=1'],
		[d.page, '/wp-admin/index.php?msg=approve'],
		[d.page, '/wp-admin/admin.php?page=asset-gme&msg=saved'],
	]) {
		expect(await measure(p, u), u).toBeLessThanOrEqual(0.02);
	}
	await e.page.goto('/wp-admin/admin.php?page=asset-gme&msg=requested');
	await expect(e.page.locator('.notice.inline.asset-notice-requested')).toHaveCount(1);
	await e.ctx.close();
	await d.ctx.close();
});
