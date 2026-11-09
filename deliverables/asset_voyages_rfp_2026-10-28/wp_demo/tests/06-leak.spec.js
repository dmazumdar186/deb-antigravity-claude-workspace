// Leak tests: S5-L1 (crawl logged out and as equipe without a grant), S4-F6 (enquiries never public),
// S5-F1 re-checked on the database after every reveal.
const { test, expect } = require('playwright/test');
const fs = require('fs');
const path = require('path');
const { asRole, CODES, PEOPLE, ROOT, readState, writeState } = require('./helpers');

test.describe.configure({ mode: 'serial', timeout: 900000 });

const BASE = process.env.WP_BASE || 'http://127.0.0.1:9400';
const extraPeople = () => ['Alice Testeur', 'alice.testeur@example.com', 'rejeu@example.com', 'formule@example.com', 'Rejeu Test', readState().newRef, readState().formulaRef, readState().hostileRef].filter(Boolean);

async function crawl(request, seeds, { allowAdmin = false, max = 450, maxDepth = 2 } = {}) {
	const seen = new Map();
	const depth = new Map(seeds.map((u) => [u, 0]));
	const queue = [...seeds];
	while (queue.length && seen.size < max) {
		const url = queue.shift();
		if (seen.has(url)) continue;
		const d = depth.get(url) || 0;
		let res;
		try { res = await request.get(url, { maxRedirects: 5, timeout: 60000 }); } catch (e) { seen.set(url, { status: 'ERR', body: '' }); continue; }
		const ct = res.headers()['content-type'] || '';
		const body = /text|json|xml|javascript/.test(ct) ? await res.text() : '';
		seen.set(url, { status: res.status(), body });
		// Follow same-origin links found in HTML, XML (sitemaps, feeds) and JSON (REST links).
		const found = new Set();
		for (const m of body.matchAll(/(?:href|src)="([^"#]+)"|<loc>([^<]+)<\/loc>|<link>([^<]+)<\/link>|"href":"([^"]+)"/g)) {
			let u = (m[1] || m[2] || m[3] || m[4] || '').replace(/\\\//g, '/').replace(/&amp;/g, '&').replace(/&#038;/g, '&');
			if (!u) continue;
			try { u = new URL(u, url).toString(); } catch (e) { continue; }
			if (!u.startsWith(BASE)) continue;
			if (/\.(css|js|png|jpe?g|svg|woff2?|ico|webp|gif)(\?|$)/.test(u)) continue;
			if (/wp-login\.php|action=logout|\/wp-admin\/(?!admin-ajax)/.test(u) && !allowAdmin) continue;
			if (/action=logout|customize\.php|wp-login\.php|admin-post\.php|post-new\.php|action=trash|action=delete|_wpnonce=/.test(u)) continue;
			found.add(u);
		}
		if (d >= maxDepth) continue;
		for (const u of found) {
			if (seen.has(u) || depth.has(u)) continue;
			if ([...new URL(u).searchParams.keys()].length > 2) continue; // filter combos are seeded explicitly
			depth.set(u, d + 1);
			queue.push(u);
		}
	}
	return seen;
}

function publicSeeds(restRoutes) {
	const s = [
		'/', '/?pg=2', '/?passes=1', '/?passes=1&pg=2', '/?q=cardio', '/?q=DEMO', '/?q=GME', '/?discipline=oncologie&pays=france', '/?mois=2027-09&tri=date_desc',
		'/?discipline=cardiologie&mois=2027-11', '/?pays=autriche', '/congres/', '/feed/', '/comments/feed/', '/congres/feed/', '/?feed=rss2&post_type=asset_congres',
		'/?post_type=asset_demande', '/?post_type=asset_demande&feed=rss2', '/?s=Bernard', '/?s=DEMO-GME', '/?s=example.com', '/?s=DV-2026', '/wp-sitemap.xml',
		'/wp-json/', '/?rest_route=/', '/wp-json/wp/v2/types', '/wp-json/wp/v2/taxonomies', '/wp-json/wp/v2/users', '/wp-json/wp/v2/search?search=Bernard',
		'/wp-json/wp/v2/search?search=DEMO', '/wp-json/wp/v2/search?search=DV-2026&subtype=any', '/wp-json/wp/v2/asset_congres?per_page=100&status=any',
		'/wp-json/wp/v2/asset_demande', '/wp-json/wp/v2/posts?per_page=100', '/wp-json/wp/v2/pages?per_page=100', '/wp-json/wp/v2/asset_discipline', '/wp-json/wp/v2/asset_pays',
		'/wp-admin/admin-ajax.php', '/wp-admin/admin-ajax.php?action=heartbeat', '/wp-admin/admin-ajax.php?action=asset_gme_reveal', '/wp-admin/admin-ajax.php?action=query-attachments',
		'/?author=1', '/?author=2', '/?author=3',
	];
	for (const r of restRoutes) s.push('/wp-json' + r);
	return s.map((u) => BASE + u);
}

async function restRoutes(request) {
	const idx = await (await request.get(BASE + '/wp-json/')).json();
	return Object.keys(idx.routes).filter((r) => !r.includes('(?P') && r !== '/');
}

function assertClean(seen, extra, label) {
	const needles = [...CODES, 'DEMO-GME-', ...PEOPLE, ...extra];
	const hits = [];
	for (const [url, { body }] of seen) for (const n of needles) if (body.includes(n)) hits.push(`${n} @ ${url}`);
	expect(hits, label).toEqual([]);
}

test('S5-L1 + S4-F6 logged-out crawl: pages, filters, every congress, feeds, sitemaps, search, every REST route, admin-ajax', async ({ browser }) => {
	const ctx = await browser.newContext();
	const routes = await restRoutes(ctx.request);
	expect(routes.some((r) => r.startsWith('/wp/v2/asset_congres'))).toBe(true);
	expect(routes.some((r) => r.includes('asset_demande'))).toBe(false);
	const seen = await crawl(ctx.request, publicSeeds(routes));
	const congresPages = [...seen.keys()].filter((u) => /\/congres\/[^/?]+\/$/.test(u));
	expect(congresPages.length).toBeGreaterThanOrEqual(13);
	expect([...seen.keys()].some((u) => u.includes('wp-sitemap-posts-asset_congres'))).toBe(true);
	expect([...seen.keys()].some((u) => u.includes('asset_demande') && u.includes('sitemap'))).toBe(false);
	assertClean(seen, extraPeople(), 'logged-out crawl');
	// The enquiry post type is not exposed as a REST type or a sitemap.
	const types = JSON.parse(seen.get(BASE + '/wp-json/wp/v2/types').body);
	expect(Object.keys(types)).not.toContain('asset_demande');
	writeState({ crawlCount: seen.size });
	test.info().annotations.push({ type: 'urls', description: String(seen.size) });
	await ctx.close();
});

test('S5-L1 crawl as equipe without an active grant (public + reachable admin screens)', async ({ browser }) => {
	const { ctx, page } = await asRole(browser, 'equipe');
	const routes = await restRoutes(ctx.request);
	const adminSeeds = ['/wp-admin/', '/wp-admin/admin.php?page=asset-gme', '/wp-admin/admin.php?page=asset-demandes', '/wp-admin/admin.php?page=asset-notifications', '/wp-admin/edit.php?post_type=asset_congres', '/wp-admin/profile.php'].map((u) => BASE + u);
	const seen = await crawl(ctx.request, [...adminSeeds, ...publicSeeds(routes)], { allowAdmin: true, max: 500 });
	const hits = [];
	for (const [url, { body }] of seen) for (const c of [...CODES, 'DEMO-GME-']) if (body.includes(c)) hits.push(`${c} @ ${url}`);
	expect(hits).toEqual([]);
	// Also via REST with the logged-in nonce.
	await page.goto('/wp-admin/');
	const nonce = await page.evaluate(() => (window.wpApiSettings && window.wpApiSettings.nonce) || '');
	if (nonce) {
		for (const r of ['/wp/v2/asset_congres?context=edit&per_page=100&status=any', '/wp/v2/search?search=DEMO', '/wp/v2/users/me?context=edit']) {
			const res = await ctx.request.get(BASE + '/wp-json' + r, { headers: { 'X-WP-Nonce': nonce } });
			const body = await res.text();
			for (const c of CODES) expect(body.includes(c), r).toBe(false);
		}
	}
	test.info().annotations.push({ type: 'urls', description: String(seen.size) });
	await ctx.close();
});

test('S5-F1 (after reveals) database still holds no plaintext code', async () => {
	const dir = fs.realpathSync(path.join(ROOT, '.tmp', `db-current-${(process.env.WP_PORT || '9400')}`));
	const files = [];
	const walk = (d) => { for (const f of fs.readdirSync(d, { withFileTypes: true })) { const p = path.join(d, f.name); if (f.isDirectory()) walk(p); else if (/\.ht\.sqlite/.test(f.name)) files.push(p); } };
	walk(dir);
	for (const f of files) {
		const buf = fs.readFileSync(f);
		for (const c of CODES) expect(buf.includes(Buffer.from(c)), `${c} in ${f}`).toBe(false);
	}
});
