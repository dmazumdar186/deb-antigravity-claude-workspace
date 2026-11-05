// S3-H2 (rate limit). Runs last: once triggered, this IP cannot submit for an hour.
const { test, expect } = require('playwright/test');
const { asRole, readState, FILL_WAIT, formTokens, validEnquiry, postEnquiry, countEnquiries } = require('./helpers');

test('S3-H2 rapid repeat submissions from one address are rate-limited', async ({ page, browser }) => {
	const { ctx, page: admin } = await asRole(browser, 'admin');
	const before = await countEnquiries(admin);
	const tokens = [];
	for (let i = 0; i < 11; i++) {
		await page.goto(readState().madridUrl);
		tokens.push(await formTokens(page));
	}
	await page.waitForTimeout(FILL_WAIT);
	let accepted = 0;
	let blocked = false;
	for (const t of tokens) {
		const r = await postEnquiry(page, t, validEnquiry({ nom: `Rafale ${accepted}`, email: `rafale${accepted}@example.com` }));
		if (r.html.includes('Trop de demandes')) { blocked = true; break; }
		expect(r.url).toContain('asset_ok=');
		accepted += 1;
	}
	expect(blocked).toBe(true);
	expect(accepted).toBeLessThanOrEqual(10);
	const after = await countEnquiries(admin);
	expect(after).toBe(before + accepted);
	test.info().annotations.push({ type: 'accepted-before-block', description: String(accepted) });
	await ctx.close();
});
