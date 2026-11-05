// S3: flight enquiry from a congress details page (logged out).
const { test, expect } = require('playwright/test');
const { asRole, clickCounter, readState, writeState, FILL_WAIT, formTokens, validEnquiry, postEnquiry, countEnquiries } = require('./helpers');

test.describe.configure({ mode: 'serial' });

async function openMadrid(page) {
	const s = readState();
	await page.goto(s.madridUrl || '/?q=madrid');
	if (!s.madridUrl) await page.locator('.asset-card h2 a').first().click();
}

async function fill(page, d) {
	for (const k of ['nom', 'email', 'telephone', 'societe', 'ville_depart', 'date_aller', 'date_retour', 'passagers', 'message']) {
		if (d[k] !== undefined) await page.fill('#asset-q-' + k, d[k]);
	}
	if (d.consentement) await page.check('#asset-q-consentement');
}

test('S3-F1 all fields present, congress prefilled', async ({ page }) => {
	await openMadrid(page);
	for (const k of ['nom', 'email', 'telephone', 'societe', 'ville_depart', 'date_aller', 'date_retour', 'passagers', 'message', 'consentement']) {
		await expect(page.locator('#asset-q-' + k)).toBeVisible();
		await expect(page.locator(`label[for="asset-q-${k}"]`)).toBeVisible();
	}
	await expect(page.locator('label[for="asset-q-societe"]')).toContainText('facultatif');
	await expect(page.locator('.asset-quote__for')).toContainText('cardiologie');
	const t = await formTokens(page);
	expect(Number(t.congres_id)).toBeGreaterThan(0);
});

test('S3-E1 errors appear next to fields in French and keep typed values (1 click)', async ({ page }) => {
	await openMadrid(page);
	await fill(page, validEnquiry({ email: 'pas-un-email', passagers: '0', date_aller: '2027-08-31', date_retour: '2027-08-26', consentement: '' }));
	await page.waitForTimeout(FILL_WAIT);
	const c = clickCounter();
	await c.click(page.locator('.asset-form button[type=submit]'));
	await expect(page.locator('.asset-notice--error')).toBeVisible();
	await expect(page.locator('#asset-q-email-err')).toContainText('adresse e-mail valide');
	await expect(page.locator('#asset-q-passagers-err')).toContainText('entre 1 et 50');
	await expect(page.locator('#asset-q-date_retour-err')).toContainText('postérieure');
	await expect(page.locator('#asset-q-consentement-err')).toContainText('accord');
	await expect(page.locator('#asset-q-nom')).toHaveValue('Alice Testeur');
	await expect(page.locator('#asset-q-ville_depart')).toHaveValue('Nice');
	await expect(page.locator('#asset-q-email')).toHaveAttribute('aria-invalid', 'true');
	expect(c.n).toBe(1);
});

test('S3-F2 valid submission stored, linked to congress, reference shown', async ({ page, browser }) => {
	const { ctx, page: admin } = await asRole(browser, 'admin');
	const before = await countEnquiries(admin);
	await openMadrid(page);
	await fill(page, validEnquiry({ nom: 'Alice Testeur', email: 'alice.testeur@example.com', consentement: '1' }));
	await page.waitForTimeout(FILL_WAIT);
	await page.click('.asset-form button[type=submit]');
	const ref = (await page.locator('.asset-ref').innerText()).trim();
	expect(ref).toMatch(/^DV-2026-\d{4}$/);
	expect(page.url()).toContain('asset_ok=');
	writeState({ newRef: ref, confirmUrl: page.url() });
	expect(await countEnquiries(admin)).toBe(before + 1);
	await admin.goto('/wp-admin/admin.php?page=asset-demandes&s=' + ref);
	await expect(admin.locator('table.wp-list-table tbody')).toContainText('Congrès européen de cardiologie — exemple');
	await ctx.close();
});

test('S3-F3 team notified (notification journal entry)', async ({ browser }) => {
	const { ctx, page } = await asRole(browser, 'admin');
	await page.goto('/wp-admin/admin.php?page=asset-notifications');
	await expect(page.locator('table')).toContainText(readState().newRef);
	await expect(page.locator('table')).toContainText('Non distribué');
	await ctx.close();
});

test('S3-F4 reloading the confirmation, or replaying the POST, creates no second enquiry', async ({ page, browser }) => {
	const { ctx, page: admin } = await asRole(browser, 'admin');
	const before = await countEnquiries(admin);
	await page.goto(readState().confirmUrl);
	await page.reload();
	await expect(page.locator('.asset-ref')).toHaveText(readState().newRef);
	// Replay: submit a form, capture its body, send it again.
	await openMadrid(page);
	await fill(page, validEnquiry({ nom: 'Rejeu Test', email: 'rejeu@example.com', consentement: '1' }));
	await page.waitForTimeout(FILL_WAIT);
	const reqP = page.waitForRequest((r) => r.url().includes('admin-post.php') && r.method() === 'POST');
	await page.click('.asset-form button[type=submit]');
	const req = await reqP;
	const ref1 = (await page.locator('.asset-ref').innerText()).trim();
	const body = req.postData();
	const res = await page.request.post('/wp-admin/admin-post.php', { data: body, headers: { 'content-type': 'application/x-www-form-urlencoded' } });
	const html = await res.text();
	expect(html).toContain(ref1);
	expect(await countEnquiries(admin)).toBe(before + 1);
	await ctx.close();
});

test('S3-H1 invalid values rejected with a message and no data change', async ({ page, browser }) => {
	const { ctx, page: admin } = await asRole(browser, 'admin');
	const before = await countEnquiries(admin);
	await openMadrid(page);
	const tokens = await formTokens(page);
	await page.waitForTimeout(FILL_WAIT);
	const cases = [
		[{ passagers: '0' }, 'entre 1 et 50'],
		[{ passagers: '51' }, 'entre 1 et 50'],
		[{ passagers: 'abc' }, 'entre 1 et 50'],
		[{ passagers: '2.5' }, 'entre 1 et 50'],
		[{ date_aller: '2027-08-31', date_retour: '2027-08-26' }, 'postérieure'],
		[{ date_aller: '2025-01-10', date_retour: '2025-01-12' }, 'dans le passé'],
		[{ date_aller: '2027-02-30' }, 'date aller valide'],
		[{ email: 'alice@' }, 'adresse e-mail valide'],
		[{ consentement: undefined }, 'Votre accord'],
		[{ nom: 'x'.repeat(5000) }, 'trop long'],
		[{ message: 'y'.repeat(2001) }, 'trop long'],
	];
	for (const [over, msg] of cases) {
		const r = await postEnquiry(page, tokens, validEnquiry(over));
		expect(r.url, JSON.stringify(over).slice(0, 60)).toContain('asset_err=');
		expect(r.html, JSON.stringify(over).slice(0, 60)).toContain(msg);
	}
	expect(await countEnquiries(admin)).toBe(before);
	await ctx.close();
});

test('S3-H2 honeypot, too-fast and missing-nonce submissions are not stored', async ({ page, browser }) => {
	const { ctx, page: admin } = await asRole(browser, 'admin');
	const before = await countEnquiries(admin);
	await openMadrid(page);
	const tokens = await formTokens(page);
	// Too fast (immediately after render).
	let r = await postEnquiry(page, tokens, validEnquiry());
	expect(r.html).toContain('trop rapidement');
	await page.waitForTimeout(FILL_WAIT);
	// Honeypot filled: fake success, nothing stored.
	r = await postEnquiry(page, tokens, validEnquiry({ site_web: 'http://spam.example.com' }));
	expect(r.url).toContain('asset_ok=');
	expect(r.html).not.toContain('asset-ref');
	// Missing / forged nonce.
	r = await postEnquiry(page, { ...tokens, asset_nonce: undefined }, validEnquiry());
	expect(r.html).toContain('expiré ou est invalide');
	r = await postEnquiry(page, { ...tokens, asset_nonce: 'deadbeef00' }, validEnquiry());
	expect(r.html).toContain('expiré ou est invalide');
	// Forged timestamp.
	r = await postEnquiry(page, { ...tokens, form_ts: '1000.abc' }, validEnquiry());
	expect(r.html).toContain('invalide');
	expect(await countEnquiries(admin)).toBe(before);
	await ctx.close();
	// Rate limiting is asserted in 99-s3-ratelimit.spec.js (it must run last: it blocks this IP for an hour).
});

test('S3-H3 script/HTML in any field is stored and shown as text only', async ({ page, browser }) => {
	await openMadrid(page);
	const tokens = await formTokens(page);
	await page.waitForTimeout(FILL_WAIT);
	const hostile = validEnquiry({
		nom: 'Zoé <script>alert(1)</script><b>Gras</b>',
		societe: '"><img src=x onerror=alert(2)>',
		ville_depart: "Paris<svg onload=alert(3)>",
		message: '<iframe src="javascript:alert(4)"></iframe> Bonjour',
	});
	const r = await postEnquiry(page, tokens, hostile);
	expect(r.url).toContain('asset_ok=');
	const ref = r.html.match(/DV-2026-\d{4}/)[0];
	writeState({ hostileRef: ref });
	// Formula-injection name for the CSV gate (S4-F5).
	await openMadrid(page);
	const t2 = await formTokens(page);
	await page.waitForTimeout(FILL_WAIT);
	const r2 = await postEnquiry(page, t2, validEnquiry({ nom: "=cmd|' /C calc'!A0", email: 'formule@example.com', societe: '+SUM(1,2)', ville_depart: '@Lyon' }));
	expect(r2.url).toContain('asset_ok=');
	writeState({ formulaRef: r2.html.match(/DV-2026-\d{4}/)[0] });

	const { ctx, page: admin } = await asRole(browser, 'admin');
	let dialog = false;
	admin.on('dialog', async (d) => { dialog = true; await d.dismiss(); });
	await admin.goto('/wp-admin/admin.php?page=asset-demandes&s=' + ref);
	await admin.locator('a.row-title', { hasText: ref }).click();
	const kv = admin.locator('.asset-kv');
	await expect(kv).toContainText('Zoé');
	await expect(kv).toContainText('Gras');
	expect(await admin.locator('.asset-kv script, .asset-kv img, .asset-kv svg, .asset-kv iframe, .asset-kv b').count()).toBe(0);
	await admin.goto('/wp-admin/admin.php?page=asset-demandes');
	expect(await admin.locator('.wp-list-table img[src="x"], .wp-list-table svg').count()).toBe(0);
	await admin.goto('/wp-admin/admin.php?page=asset-notifications');
	expect(await admin.locator('.asset-pre script, .asset-pre img, .asset-pre svg').count()).toBe(0);
	expect(dialog).toBe(false);
	await ctx.close();
});
