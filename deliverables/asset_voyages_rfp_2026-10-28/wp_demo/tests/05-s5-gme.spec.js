// S5: GM&E codes protected; access through an authorisation process.
const { test, expect } = require('playwright/test');
const fs = require('fs');
const path = require('path');
const { asRole, clickCounter, writeState, readState, CODES, ROOT, assertNoSecrets } = require('./helpers');

test.describe.configure({ mode: 'serial' });

const NEURO = 'Congrès européen de neurologie — exemple'; // DEMO-GME-3MX9, approved.
const CARDIO = 'Congrès européen de cardiologie — exemple'; // DEMO-GME-4KQ7, seeded pending request.
const row = (page, title) => page.locator('table.asset-gme-table tbody tr', { hasText: title });

function dbFiles() {
	const dir = fs.realpathSync(path.join(ROOT, '.tmp', `db-current-${(process.env.WP_PORT || '9400')}`));
	const out = [];
	const walk = (d) => { for (const f of fs.readdirSync(d, { withFileTypes: true })) { const p = path.join(d, f.name); if (f.isDirectory()) walk(p); else if (/\.ht\.sqlite/.test(f.name)) out.push(p); } };
	walk(dir);
	return out;
}

test('S5-F1 codes stored only in their own table, encrypted; no plaintext anywhere in the database', async () => {
	const files = dbFiles();
	expect(files.length).toBeGreaterThan(0);
	for (const f of files) {
		const buf = fs.readFileSync(f);
		for (const c of CODES) expect(buf.includes(Buffer.from(c)), `${c} in ${path.basename(f)}`).toBe(false);
		expect(buf.includes(Buffer.from('DEMO-GME-')), 'prefix in db').toBe(false);
	}
	const { DatabaseSync } = require('node:sqlite');
	const main = files.find((f) => f.endsWith('.ht.sqlite'));
	const db = new DatabaseSync(main, { readOnly: true });
	const rows = db.prepare('SELECT congres_id, code_enc, status FROM wp_asset_gme_codes').all();
	expect(rows.length).toBe(5);
	for (const r of rows) {
		expect(r.code_enc).toMatch(/^[A-Za-z0-9+/=]{60,}$/);
		expect(Buffer.from(r.code_enc, 'base64').length).toBe(24 + 16 + 13); // nonce + MAC + 13-char code
	}
	const meta = db.prepare("SELECT COUNT(*) n FROM wp_postmeta WHERE meta_value LIKE '%GME%'").get();
	const opts = db.prepare("SELECT COUNT(*) n FROM wp_options WHERE option_value LIKE '%DEMO-GME%'").get();
	expect(meta.n).toBe(0);
	expect(opts.n).toBe(0);
	db.close();
});

test('S5-F2 + S5-E1 equipe sees codes masked; requests access with a required reason in <= 2 clicks', async ({ browser }) => {
	const { ctx, page } = await asRole(browser, 'equipe');
	await page.goto('/wp-admin/');
	const c = clickCounter();
	await c.click(page.locator('#toplevel_page_asset-gme > a'));
	await expect(page.locator('table.asset-gme-table')).toBeVisible();
	assertNoSecrets(await page.content(), 'GM&E page (equipe)');
	await expect(row(page, NEURO).locator('.asset-masked')).toBeVisible();
	// Reason required (server side, bypassing the browser's required attribute).
	const nonce = await row(page, NEURO).locator('form.asset-request-form input[name=asset_nonce]').inputValue();
	const cid = await row(page, NEURO).locator('form.asset-request-form input[name=congres_id]').inputValue();
	const r = await page.request.post('/wp-admin/admin-post.php', { form: { action: 'asset_gme_request', congres_id: cid, asset_nonce: nonce, reason: '  ' } });
	expect(await r.text()).toContain('Indiquez la raison');
	await page.goto('/wp-admin/admin.php?page=asset-gme');
	await row(page, NEURO).locator('textarea').fill('Devis pour 8 neurologues, client fictif (test).');
	await c.click(row(page, NEURO).locator('button', { hasText: 'Demander' }));
	await expect(page.locator('.notice-success')).toContainText('Demande d’accès envoyée');
	await expect(row(page, NEURO)).toContainText('en attente');
	expect(c.n).toBeLessThanOrEqual(2);
	test.info().annotations.push({ type: 'clicks', description: String(c.n) });
	writeState({ neuroId: cid });
	await ctx.close();
});

test('S5-F3 + S5-E1 direction sees pending requests, approves in <= 2 clicks from admin home, refuses another', async ({ browser }) => {
	const { ctx, page } = await asRole(browser, 'direction');
	await page.goto('/wp-admin/');
	const w = page.locator('#asset_cd_gme');
	await expect(w).toContainText(NEURO);
	await expect(w).toContainText(CARDIO);
	const c = clickCounter();
	await c.click(w.locator('.asset-widget-req', { hasText: NEURO }).locator('button', { hasText: 'Approuver' }));
	await expect(page.locator('.notice-success')).toContainText('approuvé pour 24 heures');
	expect(c.n).toBeLessThanOrEqual(2);
	test.info().annotations.push({ type: 'clicks', description: String(c.n) });
	// Refuse path (seeded request on the cardiology congress).
	await page.click('#toplevel_page_asset-gme > a');
	await page.locator('table.asset-pending tr', { hasText: CARDIO }).locator('button', { hasText: 'Refuser' }).click();
	await expect(page.locator('.notice-success')).toContainText('refusée');
	await page.goto('/wp-admin/admin.php?page=asset-gme-acces');
	const hist = page.locator('table.asset-access-history');
	await expect(hist.locator('tr', { hasText: NEURO }).first()).toContainText('Approuvée');
	await expect(hist.locator('tr', { hasText: CARDIO }).first()).toContainText('Refusée');
	// Expiry is 24 h after approval.
	const exp = await hist.locator('tr', { hasText: NEURO }).first().locator('td').nth(6).innerText();
	const [d, m, y, hh, mm] = exp.match(/(\d{2})\/(\d{2})\/(\d{4}) (\d{2}):(\d{2})/).slice(1).map(Number);
	// Displayed in Europe/Paris: convert back to UTC with the current Paris offset.
	const now = new Date();
	const parisOffsetMs = new Date(now.toLocaleString('en-US', { timeZone: 'Europe/Paris' })).getTime() - new Date(now.toLocaleString('en-US', { timeZone: 'UTC' })).getTime();
	const diffH = (Date.UTC(y, m - 1, d, hh, mm) - parisOffsetMs - Date.now()) / 3600e3;
	expect(diffH).toBeGreaterThan(23);
	expect(diffH).toBeLessThan(25);
	await ctx.close();
});

test('S5-F4 + S5-E1 equipe reveals in <= 2 clicks; reveal logged; journal is Direction-only', async ({ browser }) => {
	const { ctx, page } = await asRole(browser, 'equipe');
	await page.goto('/wp-admin/');
	const c = clickCounter();
	await c.click(page.locator('#toplevel_page_asset-gme > a'));
	// Before reveal: still masked in HTML.
	assertNoSecrets(await page.content(), 'GM&E page before reveal');
	const reqP = page.waitForRequest((r) => r.method() === 'POST' && r.url().includes('page=asset-gme'));
	await c.click(row(page, NEURO).locator('button', { hasText: 'Afficher le code' }));
	const req = await reqP;
	await expect(row(page, NEURO).locator('code.asset-revealed')).toHaveText('DEMO-GME-3MX9');
	expect(c.n).toBeLessThanOrEqual(2);
	test.info().annotations.push({ type: 'clicks', description: String(c.n) });
	// Only the requested congress is revealed.
	for (const other of CODES.filter((x) => x !== 'DEMO-GME-3MX9')) expect(await page.content()).not.toContain(other);
	writeState({ revealBody: req.postData() });
	// Journal not reachable by equipe.
	const r = await page.request.get('/wp-admin/admin.php?page=asset-gme-journal');
	expect(r.status()).toBe(403);
	await ctx.close();
	const d = await asRole(browser, 'direction');
	await d.page.goto('/wp-admin/admin.php?page=asset-gme-journal');
	const first = d.page.locator('table.asset-log tbody tr[data-action="reveal"]').first();
	await expect(first).toContainText('Équipe (démo)');
	await expect(first).toContainText(NEURO);
	await expect(first.locator('td').first()).toHaveText(/\d{2}\/\d{2}\/\d{4} \d{2}:\d{2}/);
	assertNoSecrets(await d.page.content(), 'GM&E journal');
	await d.ctx.close();
});

test('S5-F3 revoke at once; S5-H1 reveal after revocation, without nonce or without permission is refused and logged', async ({ browser }) => {
	// Equipe opens the page while the grant is active and keeps the (valid, session-bound) reveal form.
	const { ctx, page } = await asRole(browser, 'equipe');
	await page.goto('/wp-admin/admin.php?page=asset-gme');
	const form = row(page, NEURO).locator('form', { has: page.locator('button', { hasText: 'Afficher le code' }) });
	const body = new URLSearchParams({
		asset_gme_action: 'reveal',
		congres_id: await form.locator('input[name=congres_id]').inputValue(),
		asset_nonce: await form.locator('input[name=asset_nonce]').inputValue(),
		_wp_http_referer: '/wp-admin/admin.php?page=asset-gme',
	}).toString();

	const d = await asRole(browser, 'direction');
	await d.page.goto('/wp-admin/admin.php?page=asset-gme-acces');
	await d.page.locator('table.asset-access-history tr', { hasText: NEURO }).first().locator('button', { hasText: 'Retirer l’accès' }).click();
	await expect(d.page.locator('.notice-success')).toContainText('retiré');

	// Same-session replay after revocation: valid nonce, no grant -> refused.
	let r = await page.request.post('/wp-admin/admin.php?page=asset-gme', { data: body, headers: { 'content-type': 'application/x-www-form-urlencoded' } });
	let html = await r.text();
	expect(html).toContain('aucune autorisation active');
	assertNoSecrets(html, 'replayed reveal');
	// Replay of the reveal captured in an earlier session (nonce bound to that session) -> refused.
	r = await page.request.post('/wp-admin/admin.php?page=asset-gme', { data: readState().revealBody, headers: { 'content-type': 'application/x-www-form-urlencoded' } });
	html = await r.text();
	expect(html).toMatch(/aucune autorisation active|jeton de sécurité invalide/);
	assertNoSecrets(html, 'old-session replay');
	// UI no longer offers reveal.
	await page.goto('/wp-admin/admin.php?page=asset-gme');
	expect(await row(page, NEURO).locator('button', { hasText: 'Afficher le code' }).count()).toBe(0);
	await expect(row(page, NEURO)).toContainText('Accès retiré');
	// Without nonce.
	r = await page.request.post('/wp-admin/admin.php?page=asset-gme', { form: { asset_gme_action: 'reveal', congres_id: readState().neuroId } });
	html = await r.text();
	expect(html).toContain('jeton de sécurité invalide');
	assertNoSecrets(html, 'reveal without nonce');
	await ctx.close();
	// Without permission (contributor has no GM&E capability at all).
	const k = await asRole(browser, 'contributeur');
	r = await k.page.request.post('/wp-admin/admin.php?page=asset-gme', { data: readState().revealBody, headers: { 'content-type': 'application/x-www-form-urlencoded' } });
	expect(r.status()).toBe(403);
	assertNoSecrets(await r.text(), 'reveal as contributor');
	await k.ctx.close();
	// Logged.
	await d.page.goto('/wp-admin/admin.php?page=asset-gme-journal');
	expect(await d.page.locator('tr[data-action="reveal_refused"]').count()).toBeGreaterThanOrEqual(3);
	await expect(d.page.locator('tr[data-action="revoke"]').first()).toContainText(NEURO);
	await d.ctx.close();
});

test('S5-F5 public pages say only « Tarif congrès négocié disponible », never the code', async ({ browser }) => {
	const anon = await browser.newContext();
	const page = await anon.newPage();
	await page.goto('/?q=madrid');
	await expect(page.locator('.asset-card__offer')).toHaveText('Tarif congrès négocié disponible');
	await page.goto(await page.locator('.asset-card h2 a').first().getAttribute('href'));
	await expect(page.locator('.asset-offer')).toHaveText('Tarif congrès négocié disponible : appliqué à votre devis');
	assertNoSecrets(await page.content(), 'approved congress page');
	// Verified-but-not-approved (Berlin) and expired (Londres) show nothing.
	for (const q of ['berlin', 'londres', 'milan']) {
		await page.goto('/?q=' + q);
		expect(await page.locator('.asset-card__offer').count(), q).toBe(0);
		await page.goto(await page.locator('.asset-card h2 a').first().getAttribute('href'));
		expect(await page.locator('.asset-offer').count(), q).toBe(0);
	}
	await anon.close();
});

test('S5-L2 codes never in HTML for authorised users until reveal; never in logs, CSV or notifications', async ({ browser }) => {
	const { ctx, page } = await asRole(browser, 'direction');
	for (const url of ['/wp-admin/', '/wp-admin/admin.php?page=asset-gme', '/wp-admin/admin.php?page=asset-gme&edit=' + readState().neuroId, '/wp-admin/admin.php?page=asset-gme-acces', '/wp-admin/admin.php?page=asset-gme-journal', '/wp-admin/admin.php?page=asset-notifications', '/wp-admin/admin.php?page=asset-demandes']) {
		await page.goto(url);
		assertNoSecrets(await page.content(), url);
	}
	await expect(page.locator('body')).toBeVisible();
	await page.goto('/wp-admin/admin.php?page=asset-demandes');
	const href = await page.locator('a.page-title-action', { hasText: 'CSV' }).getAttribute('href');
	assertNoSecrets(await (await page.request.get(href)).text(), 'CSV');
	// Edit form never pre-fills the code.
	await page.goto('/wp-admin/admin.php?page=asset-gme&edit=' + readState().neuroId);
	await expect(page.locator('#asset-gme-code')).toHaveValue('');
	// Direction reveal also works and is logged.
	await row(page, NEURO).locator('button', { hasText: 'Afficher le code' }).click();
	await expect(row(page, NEURO).locator('code.asset-revealed')).toHaveText('DEMO-GME-3MX9');
	await page.goto('/wp-admin/admin.php?page=asset-gme-journal');
	await expect(page.locator('tr[data-action="reveal"]').first()).toContainText('Direction (démo)');
	assertNoSecrets(await page.content(), 'journal after reveal');
	await ctx.close();
});
