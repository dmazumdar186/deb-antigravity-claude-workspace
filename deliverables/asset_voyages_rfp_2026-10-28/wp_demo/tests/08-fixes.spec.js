// Fix round A: one test per finding (FIX-A-1 … FIX-A-17; FIX-A-18 lives in screens.spec.js).
const { test, expect } = require('playwright/test');
const { execFileSync, spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const { asRole, login, ROOT, FILL_WAIT, formTokens, validEnquiry, postEnquiry } = require('./helpers');

const KEY = JSON.parse(fs.readFileSync(path.join(ROOT, 'blueprints', 'visitor.template.json'), 'utf8')).steps[0].consts.ASSET_GME_KEY;
const php = (arg) => JSON.parse(execFileSync('php', [path.join(__dirname, 'unit', 'gme_crypto.php'), arg], { encoding: 'utf8' }));

// A second, throwaway Playground: visitor blueprint WITHOUT ASSET_GME_KEY, booted with --login
// (the same auto-login playground.wordpress.net applies when the URL lacks login=no).
const ALT = 'http://127.0.0.1:9410';
let alt;
async function startAlt() {
	if (alt) return;
	const log = fs.openSync(path.join(ROOT, '.tmp', 'pg-nokey.log'), 'w');
	const dbdir = path.join(ROOT, '.tmp', 'db-runs', 'nokey-' + Date.now());
	fs.mkdirSync(dbdir, { recursive: true });
	alt = spawn('npx', ['-y', '@wp-playground/cli@3.1.62', 'server', '--blueprint=.tmp/blueprint-nokey.local.json', '--port=9410', '--login', `--mount-before-install=${dbdir}:/wordpress/wp-content/database`], { cwd: ROOT, stdio: ['ignore', log, log], detached: true });
	for (let i = 0; i < 120; i++) {
		if (fs.readFileSync(path.join(ROOT, '.tmp', 'pg-nokey.log'), 'utf8').includes('Ready!')) return;
		await new Promise((r) => setTimeout(r, 3000));
	}
	throw new Error('second Playground did not start');
}
test.afterAll(() => { if (alt) { try { process.kill(-alt.pid); } catch (e) { /* already gone */ } } });

test.describe('needs the second Playground (no key, forced auto-login)', () => {
	test.describe.configure({ mode: 'serial', timeout: 600000 });

	test('FIX-A-10 visitor demo is logged out even when Playground forces its auto-login; blueprints set login', async ({ browser }) => {
		const vis = JSON.parse(fs.readFileSync(path.join(ROOT, 'blueprint-visitor.json'), 'utf8'));
		const adm = JSON.parse(fs.readFileSync(path.join(ROOT, 'blueprint-admin.json'), 'utf8'));
		expect(vis.login).toBe(false);
		expect(vis.steps.some((s) => s.step === 'login')).toBe(false);
		expect(vis.steps[0].consts.ASSET_DEMO_VISITOR).toBe(true);
		expect(adm.steps.find((s) => s.step === 'login').username).toBe('direction');
		await startAlt();
		const ctx = await browser.newContext({ baseURL: ALT, locale: 'fr-FR' });
		const page = await ctx.newPage();
		await page.goto('/');
		await page.goto('/');
		await expect(page.locator('.asset-count')).toBeVisible();
		expect(await page.locator('#wpadminbar').count()).toBe(0);
		expect(await page.locator('body').innerText()).not.toMatch(/Bonjour|Modifier le site/);
		const cookies = (await ctx.cookies()).map((c) => c.name);
		expect(cookies.some((c) => c.startsWith('wordpress_logged_in'))).toBe(false);
		// A real login through wp-login.php still works.
		await login(page, 'admin');
		await page.goto('/');
		await expect(page.locator('#wpadminbar')).toHaveCount(1);
		await ctx.close();
	});

	test('FIX-A-1 without ASSET_GME_KEY the plugin fails closed: no code stored, no save, admin notice', async ({ browser }) => {
		await startAlt();
		const ctx = await browser.newContext({ baseURL: ALT, locale: 'fr-FR' });
		const page = await ctx.newPage();
		await page.goto('/');
		await login(page, 'direction');
		await expect(page.locator('.asset-notice-nokey')).toBeVisible(); // dashboard
		await page.goto('/wp-admin/admin.php?page=asset-gme');
		await expect(page.locator('.asset-notice-nokey')).toContainText('ASSET_GME_KEY');
		expect(await page.locator('table.asset-gme-table').count()).toBe(0); // the seed refused to store codes
		await page.fill('#asset-gme-code', 'DEMO-GME-ZZZZ');
		await page.click('.asset-gme-edit #submit');
		await expect(page.locator('.asset-notice-nokey')).toBeVisible();
		expect(await page.locator('table.asset-gme-table').count()).toBe(0);
		await ctx.close();
	});
});

test('FIX-A-1 key handling and congress binding (unit): malformed key refused, ciphertext bound to its congress', () => {
	const ok = php(KEY);
	expect(ok).toMatchObject({ key_ok: true, encrypted: true, roundtrip: 'DEMO-GME-ABCD', other_congres: null, tampered: null, plaintext_in_enc: false });
	for (const bad of ['none', KEY.slice(0, 63), 'pas-une-cle!!', KEY + '00']) {
		expect(php(bad), bad.slice(0, 10)).toMatchObject({ key_ok: false, encrypted: false, roundtrip: null });
	}
	const plugin = fs.readFileSync(path.join(ROOT, 'plugin/asset-congres-demo/includes/class-gme.php'), 'utf8');
	expect(plugin).not.toContain('wp_salt');
});

test('FIX-A-2 login throttle per IP + username (10 / 15 min) and one generic error message', async ({ browser }) => {
	const ctx = await browser.newContext();
	// Same flow as a browser: load the form (test cookie), then post it.
	const tryLogin = async (log, pwd) => {
		await ctx.request.get('/wp-login.php');
		return (await ctx.request.post('/wp-login.php', { form: { log, pwd, 'wp-submit': 'Se connecter', testcookie: '1', redirect_to: '' } })).text();
	};
	const unknown = await tryLogin('personne-inconnue', 'x');
	const known = await tryLogin('contributeur', 'mauvais');
	for (const html of [unknown, known]) {
		expect(html).toContain('identifiant ou mot de passe incorrect');
		expect(html).not.toMatch(/n’est pas enregistré|pas inscrit|contributeur<\/strong>|pour l’identifiant/);
	}
	for (let i = 0; i < 10; i++) await tryLogin('qa-throttle', 'x'); // 10 allowed, the 11th is refused
	const blocked = await tryLogin('qa-throttle', 'x');
	expect(blocked).toContain('trop de tentatives');
	// No global lockout: another username from the same address still logs in.
	const page = await ctx.newPage();
	await login(page, 'equipe');
	await expect(page).toHaveURL(/wp-admin\/(index\.php)?$/);
	await ctx.close();
});

test('FIX-A-3 approve / refuse / revoke use separate nonces', async ({ browser }) => {
	const eq = await asRole(browser, 'equipe');
	await eq.page.goto('/wp-admin/admin.php?page=asset-gme');
	const row = eq.page.locator('table.asset-gme-table tbody tr', { hasText: 'oncologie' }).filter({ hasText: 'Vérifié' });
	if (await row.locator('textarea').count()) {
		await row.locator('textarea').fill('Test des jetons séparés (FIX-A-3).');
		await row.locator('button', { hasText: 'Demander' }).click();
		await expect(eq.page.locator('.notice-success')).toBeVisible();
	}
	await eq.ctx.close();
	const { ctx, page } = await asRole(browser, 'direction');
	await page.goto('/wp-admin/admin.php?page=asset-gme-acces');
	const pending = page.locator('table.asset-pending tr', { hasText: 'oncologie' }).first();
	const approve = pending.locator('form', { has: page.locator('input[name=decision][value=approve]') });
	const rid = await approve.locator('input[name=request_id]').inputValue();
	const approveNonce = await approve.locator('input[name=asset_nonce]').inputValue();
	const refuseNonce = await pending.locator('form', { has: page.locator('input[name=decision][value=refuse]') }).locator('input[name=asset_nonce]').inputValue();
	expect(refuseNonce).not.toBe(approveNonce);
	for (const decision of ['refuse', 'revoke']) {
		const r = await page.request.post('/wp-admin/admin-post.php', { form: { action: 'asset_gme_decide', request_id: rid, decision, asset_nonce: approveNonce, back: 'asset-gme-acces' } });
		expect(r.status(), decision).toBe(403);
	}
	const ok = await page.request.post('/wp-admin/admin-post.php', { form: { action: 'asset_gme_decide', request_id: rid, decision: 'refuse', asset_nonce: refuseNonce, back: 'asset-gme-acces' } });
	expect(await ok.text()).toContain('Demande refusée');
	await ctx.close();
});

test('FIX-A-4 REST user list and author archives are hidden from visitors', async ({ browser }) => {
	const anon = await browser.newContext();
	let r = await anon.request.get('/wp-json/wp/v2/users');
	expect(r.status()).toBe(404);
	r = await anon.request.get('/wp-json/wp/v2/users/1');
	expect(r.status()).toBe(404);
	r = await anon.request.get('/?author=1', { maxRedirects: 0 });
	expect(r.status()).toBe(404);
	const idx = await (await anon.request.get('/wp-json/')).json();
	expect(Object.keys(idx.routes).some((k) => k.startsWith('/wp/v2/users'))).toBe(false);
	await anon.close();
	const { ctx, page } = await asRole(browser, 'admin');
	await page.goto('/wp-admin/');
	const nonce = await page.evaluate(() => window.wpApiSettings && window.wpApiSettings.nonce);
	r = await ctx.request.get('/wp-json/wp/v2/users/me', { headers: { 'X-WP-Nonce': nonce || '' } });
	expect(r.status()).toBe(200);
	await ctx.close();
});

test('FIX-A-5 translations load on init (no "too early" notice for the plugin text domain)', async ({ browser }) => {
	const anon = await browser.newContext();
	for (const u of ['/', '/congres/', '/wp-login.php']) await anon.request.get(u);
	const r = await anon.request.get('/wp-content/debug.log');
	if (r.status() === 200) expect(await r.text()).not.toMatch(/asset-congres-demo.{0,200}too early|_load_textdomain_just_in_time.{0,200}asset-congres-demo/s);
	const main = fs.readFileSync(path.join(ROOT, 'plugin/asset-congres-demo/asset-congres-demo.php'), 'utf8');
	expect(main).toMatch(/'init',\s*static function \(\) \{\s*load_plugin_textdomain/);
	await anon.close();
});

test('FIX-A-6 front-end security headers', async ({ browser }) => {
	const anon = await browser.newContext();
	for (const u of ['/', '/?q=lyon', '/congres/']) {
		const h = (await anon.request.get(u)).headers();
		expect(h['x-content-type-options'], u).toBe('nosniff');
		expect(h['x-frame-options'], u).toBe('SAMEORIGIN');
		expect(h['content-security-policy'], u).toContain("frame-ancestors 'self'");
		expect(h['referrer-policy'], u).toBe('strict-origin-when-cross-origin');
	}
	await anon.close();
});

test('FIX-A-7 semgrep echoed-request hits: request data no longer reaches output (selected state is a literal)', () => {
	const src = fs.readFileSync(path.join(ROOT, 'plugin/asset-congres-demo/includes/class-gme-admin.php'), 'utf8');
	expect(src).not.toMatch(/selected\(\s*\$edit/);
	expect(src).toMatch(/\$edit = isset\( \$_GET\['edit'\] \) \? absint/);
	// Every remaining exemption states its reason.
	for (const line of src.split('\n').filter((l) => l.includes('nosemgrep'))) expect(line).toMatch(/nosemgrep: [\w.-]+ -- .{20,}/);
	// Semgrep itself (PHP pack) when available: 0 findings.
	let sg = null;
	try { execFileSync('semgrep', ['--version'], { stdio: 'ignore' }); sg = true; } catch (e) { sg = false; }
	if (sg) {
		const out = execFileSync('semgrep', ['scan', '--config', 'p/php', '--json', '-q', path.join(ROOT, 'plugin/asset-congres-demo')], { encoding: 'utf8', timeout: 300000, maxBuffer: 50e6 });
		expect(JSON.parse(out).results.map((r) => `${r.path}:${r.start.line} ${r.check_id}`)).toEqual([]);
	}
});

test('FIX-A-19 no cross-document view transitions in wp-admin (no "Transition was aborted" page errors)', async ({ browser }) => {
	const { ctx, page } = await asRole(browser, 'direction');
	const errors = [];
	page.on('pageerror', (e) => errors.push(e.message));
	await page.goto('/wp-admin/');
	expect(await page.content()).not.toContain('wp-view-transitions-admin');
	// Rapid admin ↔ front navigation, interrupted on purpose.
	for (const u of ['/wp-admin/admin.php?page=asset-gme', '/', '/wp-admin/admin.php?page=asset-demandes', '/?q=lyon', '/wp-admin/']) {
		page.goto(u).catch(() => {});
		await page.waitForTimeout(150);
	}
	await page.goto('/wp-admin/');
	await page.waitForLoadState('networkidle');
	expect(errors.filter((m) => /Transition|ViewTransition/.test(m))).toEqual([]);
	await ctx.close();
});

test('FIX-A-8 code format check rejects a trailing newline', () => {
	expect(php(KEY)).toMatchObject({ valid_plain: true, valid_newline: false, valid_lower: false, valid_array: false });
});

test('FIX-A-9 expected 404s are tested on their own (not counted by the X1 sweep)', async ({ browser }) => {
	const anon = await browser.newContext();
	const page = await anon.newPage();
	const res = await page.goto('/congres/congres-inexistant-qa/');
	expect(res.status()).toBe(404);
	await expect(page.locator('h1')).toContainText('Page introuvable');
	await expect(page.locator('main a.asset-link')).toContainText('Retour au catalogue');
	const x1 = fs.readFileSync(path.join(__dirname, '07-cross.spec.js'), 'utf8');
	expect(x1).not.toMatch(/inexistant|\/congres\/x/);
	await anon.close();
});

test('FIX-A-11 bundled theme: clean header/footer, no Twenty Twenty-Five leftovers, no byline or related posts', async ({ browser }) => {
	const anon = await browser.newContext();
	const page = await anon.newPage();
	for (const u of ['/', '/?q=madrid']) {
		await page.goto(u);
		await expect(page.locator('.asset-brand')).toHaveText('ASSET Voyages — démonstration');
		await expect(page.locator('header nav a')).toHaveText('Catalogue des congrès');
		await expect(page.locator('footer')).toContainText('Démonstration ASSET Voyages');
		await expect(page.locator('footer')).toContainText('fictives');
		const text = await page.locator('body').innerText();
		expect(text).not.toMatch(/Twenty Twenty-Five|Boutique|Conçu avec WordPress|Auteurs\/autrices/);
		expect(await page.locator('nav ul > :not(li)').count()).toBe(0);
		expect(await page.locator('.wp-block-navigation').count()).toBe(0);
	}
	await page.goto(await page.locator('.asset-card h2 a').first().getAttribute('href'));
	const text = await page.locator('body').innerText();
	expect(text).not.toMatch(/Écrit par|Plus de publications|PLUS DE PUBLICATIONS/);
	expect(await page.locator('.wp-block-post-author, .wp-block-post-terms, .wp-block-post-date, .wp-block-query').count()).toBe(0);
	expect(await page.locator('html').innerHTML()).toContain('asset-header-band');
	await anon.close();
});

test('FIX-A-12 keyboard only: create and publish a congress (Tab / type / Enter); description field is labelled', async ({ browser }) => {
	const { ctx, page } = await asRole(browser, 'admin');
	await page.goto('/wp-admin/post-new.php?post_type=asset_congres');
	await expect(page.locator('label[for="content"]')).toHaveText('Description du congrès');
	expect(await page.locator('.mce-tinymce').count()).toBe(0);
	const tabTo = async (sel) => {
		for (let i = 0; i < 150; i++) {
			if (await page.evaluate((s) => document.activeElement && document.activeElement.matches(s), sel)) return i;
			await page.keyboard.press('Tab');
		}
		throw new Error('not reachable by Tab: ' + sel);
	};
	await tabTo('#title');
	await page.keyboard.type('Congrès clavier de rhumatologie — exemple');
	await tabTo('#content');
	await page.keyboard.type('Description fictive saisie au clavier.');
	// Date inputs follow the browser locale's segment order: type, then check, retype if needed.
	const typeDate = async (sel, iso) => {
		await tabTo(sel);
		const [y, m, d] = iso.split('-');
		await page.keyboard.type(d + m + y);
		if ((await page.inputValue(sel)) !== iso) {
			await page.keyboard.press('Shift+Tab'); await page.keyboard.press('Shift+Tab');
			await tabTo(sel);
			await page.keyboard.type(m + d + y);
		}
		expect(await page.inputValue(sel)).toBe(iso);
	};
	await typeDate('#asset-field-asset_start', '2027-12-06');
	await typeDate('#asset-field-asset_end', '2027-12-09');
	for (const [sel, txt] of [['#asset-field-asset_city', 'Genève'], ['#asset-field-asset_pays', 'Suisse'], ['#asset-field-asset_discipline', 'Rhumatologie']]) {
		await tabTo(sel);
		await page.keyboard.type(txt);
	}
	await tabTo('#publish');
	expect(await page.locator('#publish').getAttribute('class')).not.toContain('disabled');
	const nav = page.waitForURL(/post\.php\?post=\d+&action=edit/);
	await page.keyboard.press('Enter');
	await nav;
	await expect(page.locator('#message')).toBeVisible();
	await expect(page.locator('#post-status-display')).toContainText(/Publié/i);
	await ctx.close();
});

test('FIX-A-13 dates in jj/mm/aaaa, Europe/Paris time, never ISO or UTC (enquiry detail, history, journal, CSV)', async ({ browser }) => {
	const { ctx, page } = await asRole(browser, 'equipe');
	await page.goto('/wp-admin/admin.php?page=asset-demandes&s=DV-2026-0001');
	await page.goto(await page.locator('a.row-title').first().getAttribute('href'));
	const detail = await page.locator('#wpbody-content').innerText();
	expect(detail).toMatch(/Reçue le\s+\d{2}\/\d{2}\/\d{4} \d{2}:\d{2}/);
	expect(detail).toContain('14/10/2027');
	expect(detail).not.toMatch(/\d{4}-\d{2}-\d{2}|UTC/);
	await page.goto('/wp-admin/admin.php?page=asset-notifications');
	const journal = await page.locator('#wpbody-content').innerText();
	expect(journal).not.toMatch(/\d{4}-\d{2}-\d{2}|\(UTC\)/);
	await page.goto('/wp-admin/admin.php?page=asset-demandes');
	const href = await page.locator('a.page-title-action', { hasText: 'CSV' }).getAttribute('href');
	const csv = await (await page.request.get(href)).text();
	expect(csv).not.toMatch(/\d{4}-\d{2}-\d{2}/);
	expect(csv).toContain('14/10/2027');
	// Times are Paris time: a fresh enquiry's « Reçue le » equals the Europe/Paris clock (±5 min; UTC would be 60 min off).
	const visitor = await browser.newContext();
	const vp = await visitor.newPage();
	await vp.goto('/?q=lisbonne');
	await vp.goto(await vp.locator('.asset-card h2 a').first().getAttribute('href'));
	const tokens = await formTokens(vp);
	await vp.waitForTimeout(FILL_WAIT);
	const r = await postEnquiry(vp, tokens, validEnquiry({ nom: 'Horloge Paris', email: 'horloge@example.com', date_aller: '2027-04-12', date_retour: '2027-04-15' }));
	const ref = r.html.match(/DV-2026-\d{4}/)[0];
	await visitor.close();
	await page.goto('/wp-admin/admin.php?page=asset-demandes&s=' + ref);
	await page.goto(await page.locator('a.row-title').first().getAttribute('href'));
	const got = (await page.locator('.asset-kv').innerText()).match(/Reçue le\s+(\d{2})\/(\d{2})\/(\d{4}) (\d{2}):(\d{2})/).slice(1).map(Number);
	const paris = new Date(new Date().toLocaleString('en-US', { timeZone: 'Europe/Paris' }));
	const shown = new Date(got[2], got[1] - 1, got[0], got[3], got[4]);
	expect(Math.abs(paris - shown) / 60000).toBeLessThan(5);
	await ctx.close();
});

test('FIX-A-14 admin screens fit 390 px (no horizontal overflow)', async ({ browser }) => {
	const { ctx, page } = await asRole(browser, 'direction', { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
	const urls = ['/wp-admin/admin.php?page=asset-gme', '/wp-admin/admin.php?page=asset-gme-acces', '/wp-admin/admin.php?page=asset-gme-journal', '/wp-admin/admin.php?page=asset-notifications', '/wp-admin/admin.php?page=asset-demandes', '/wp-admin/'];
	for (const u of urls) {
		await page.goto(u);
		const sw = await page.evaluate(() => document.documentElement.scrollWidth);
		expect(sw, u).toBeLessThanOrEqual(390);
	}
	await page.goto('/wp-admin/admin.php?page=asset-demandes');
	await page.goto(await page.locator('a.row-title').first().getAttribute('href'));
	await page.waitForSelector('.asset-history');
	expect(await page.evaluate(() => document.documentElement.scrollWidth), 'detail').toBeLessThanOrEqual(390);
	await ctx.close();
});

test('FIX-A-15 heading order: card titles are h2 under the page h1', async ({ browser }) => {
	const anon = await browser.newContext();
	const page = await anon.newPage();
	await page.goto('/');
	const levels = await page.$$eval('h1, h2, h3, h4, h5, h6', (els) => els.map((e) => Number(e.tagName[1])));
	expect(levels[0]).toBe(1);
	for (let i = 1; i < levels.length; i++) expect(levels[i] - levels[i - 1]).toBeLessThanOrEqual(1);
	expect(await page.locator('.asset-card h2.asset-card__title').count()).toBe(9);
	await anon.close();
});

test('FIX-A-16 congress editor: no autosave lock, calm heartbeat, « Publier » stays usable', async ({ browser }) => {
	const { ctx, page } = await asRole(browser, 'admin');
	await page.goto('/wp-admin/post-new.php?post_type=asset_congres');
	await page.fill('#title', 'Congrès heartbeat — exemple');
	await page.locator('#title').blur();
	await page.evaluate(() => window.jQuery && window.jQuery(document).trigger('heartbeat-connection-lost', ['timeout', 0]));
	const st = await page.evaluate(() => ({ autosave: !!(window.wp && window.wp.autosave), interval: window.heartbeatSettings ? Number(window.heartbeatSettings.minimalInterval) : null, disabled: document.getElementById('publish').classList.contains('disabled') }));
	expect(st.autosave).toBe(false);
	expect(st.interval).toBeGreaterThanOrEqual(60);
	expect(st.disabled).toBe(false);
	await ctx.close();
});

test('FIX-A-17 minor UX defects: actionable rows only, unbroken reference, consent error under its box, sort label, e-mails, search label, menu', async ({ browser }) => {
	// USAB-A-006: expired / detected codes offer no request; expired offers no reveal, even to Direction.
	const eq = await asRole(browser, 'equipe');
	await eq.page.goto('/wp-admin/admin.php?page=asset-gme');
	for (const label of ['Expiré', 'Détecté']) {
		const r = eq.page.locator('table.asset-gme-table tbody tr', { has: eq.page.locator('td', { hasText: new RegExp('^' + label + '$') }) });
		await expect(r).toHaveCount(1);
		expect(await r.locator('textarea, button').count(), label).toBe(0);
	}
	// EYE-A-012: the collapse button sits below the last menu item.
	const ov = await eq.page.evaluate(() => {
		const items = [...document.querySelectorAll('#adminmenu > li.menu-top')].filter((e) => e.offsetParent);
		const last = items[items.length - 1].getBoundingClientRect();
		const col = document.querySelector('#collapse-menu').getBoundingClientRect();
		return col.top - last.bottom;
	});
	expect(ov).toBeGreaterThanOrEqual(-0.5);
	await eq.ctx.close();
	const d = await asRole(browser, 'direction');
	await d.page.goto('/wp-admin/admin.php?page=asset-gme');
	const exp = d.page.locator('table.asset-gme-table tbody tr', { has: d.page.locator('td', { hasText: /^Expiré$/ }) });
	expect(await exp.locator('button', { hasText: 'Révéler' }).count()).toBe(0);
	await d.ctx.close();

	// EYE-A-008 / 009 / 010 on the visitor side.
	const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, locale: 'fr-FR' });
	const page = await ctx.newPage();
	await page.goto('/?q=madrid');
	await page.goto(await page.locator('.asset-card h2 a').first().getAttribute('href'));
	await page.waitForTimeout(FILL_WAIT);
	await page.click('.asset-form button[type=submit]');
	await page.waitForSelector('#asset-q-consentement-err');
	const geo = await page.evaluate(() => {
		const box = document.getElementById('asset-q-consentement').getBoundingClientRect();
		const label = document.querySelector('label[for="asset-q-consentement"]').getBoundingClientRect();
		const err = document.getElementById('asset-q-consentement-err').getBoundingClientRect();
		return { errTop: err.top, boxBottom: box.bottom, labelBottom: label.bottom, errWidth: err.width };
	});
	expect(geo.errTop).toBeGreaterThanOrEqual(Math.max(geo.boxBottom, geo.labelBottom) - 1);
	expect(geo.errWidth).toBeGreaterThan(200);
	const ws = await page.evaluate(() => { const s = document.createElement('span'); s.className = 'asset-ref'; document.body.appendChild(s); return getComputedStyle(s).whiteSpace; });
	expect(ws).toBe('nowrap');
	await ctx.close();
	const wide = await browser.newContext({ viewport: { width: 1440, height: 900 } });
	const wp = await wide.newPage();
	await wp.goto('/');
	const clip = await wp.$eval('#asset-f-tri', (el) => { const c = document.createElement('canvas').getContext('2d'); c.font = getComputedStyle(el).font; return c.measureText(el.options[el.selectedIndex].text).width + 40 <= el.clientWidth; });
	expect(clip).toBe(true);
	await wide.close();

	// EYE-A-011: e-mails wrap at « @ », search box labelled at 390 px.
	const m = await asRole(browser, 'equipe', { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
	await m.page.goto('/wp-admin/admin.php?page=asset-demandes');
	await expect(m.page.locator('label[for="asset-demandes-search-input"]')).toBeVisible();
	await expect(m.page.locator('#asset-demandes-search-input')).toHaveAttribute('placeholder', /référence/);
	expect(await m.page.locator('.asset-email wbr').count()).toBeGreaterThan(0);
	await m.ctx.close();
});

test('FIX-A-20 admin bar « Ctrl + K » no longer throws "wp is not defined" when clicked before scripts load', async ({ browser }) => {
	const { ctx, page } = await asRole(browser, 'contributeur');
	await page.goto('/wp-admin/post-new.php?post_type=asset_congres');
	const onclick = await page.locator('#wp-admin-bar-command-palette > a').getAttribute('onclick');
	expect(onclick).toContain('window.wp && wp.data');
	// Simulate the early click: run the handler with wp undefined.
	const err = await page.evaluate((code) => { const saved = window.wp; try { window.wp = undefined; new Function(code)(); return null; } catch (e) { return e.message; } finally { window.wp = saved; } }, onclick);
	expect(err).toBeNull();
	await ctx.close();
});
