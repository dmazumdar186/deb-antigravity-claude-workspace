// Shared helpers for the ASSET demo suite.
const fs = require('fs');
const path = require('path');
const { expect } = require('playwright/test');

const BASE = process.env.WP_BASE || 'http://127.0.0.1:9400';
const ROOT = path.resolve(__dirname, '..');
const STATE = path.join(ROOT, '.tmp', 'suite-state.json');

// Seeded dummy codes (must never leak).
const CODES = ['DEMO-GME-4KQ7', 'DEMO-GME-8TZ2', 'DEMO-GME-3MX9', 'DEMO-GME-6PL5', 'DEMO-GME-1RB8'];
// Seeded enquiry contacts (must never be public).
const PEOPLE = [
	'Julien Bernard', 'julien.bernard@example.com', 'Sophie Dubois', 'sophie.dubois@example.com',
	'Thomas Petit', 'thomas.petit@example.com', 'Léa Moreau', 'lea.moreau@example.com',
	'Hugo Laurent', 'hugo.laurent@example.com', 'Camille Martin', 'camille.martin@example.com',
];
const USERS = {
	admin: ['admin', 'password'],
	direction: ['direction', 'demo-asset'],
	equipe: ['equipe', 'demo-asset'],
	contributeur: ['contributeur', 'demo-asset'],
};

function readState() {
	try { return JSON.parse(fs.readFileSync(STATE, 'utf8')); } catch (e) { return {}; }
}
function writeState(patch) {
	const s = { ...readState(), ...patch };
	fs.mkdirSync(path.dirname(STATE), { recursive: true });
	fs.writeFileSync(STATE, JSON.stringify(s, null, 2));
	return s;
}

async function login(page, role) {
	const [user, pass] = USERS[role];
	await page.goto('/wp-login.php');
	await page.fill('#user_login', user);
	await page.fill('#user_pass', pass);
	await Promise.all([page.waitForURL(/wp-admin/), page.click('#wp-submit')]);
	await page.waitForLoadState('load');
}

async function asRole(browser, role, opts = {}) {
	const ctx = await browser.newContext({ baseURL: BASE, locale: 'fr-FR', deviceScaleFactor: 1, viewport: { width: 1440, height: 900 }, ...opts });
	const page = await ctx.newPage();
	if (role) await login(page, role);
	return { ctx, page };
}

// Counts clicks for the E (ease) gates.
function clickCounter() {
	const c = { n: 0 };
	c.click = async (locator) => { c.n += 1; await locator.click(); };
	return c;
}

function assertNoSecrets(text, where, extra = []) {
	for (const s of [...CODES, ...extra]) {
		expect(text.includes(s), `${s} leaked in ${where}`).toBe(false);
	}
}

// The public form enforces a minimum fill time of 3 s.
const FILL_WAIT = 3300;

// Reads the hidden fields of the enquiry form on a congress page.
async function formTokens(page) {
	return page.evaluate(() => {
		const f = document.querySelector('form.asset-form');
		const out = {};
		for (const el of f.querySelectorAll('input[type=hidden]')) out[el.name] = el.value;
		return out;
	});
}

function validEnquiry(overrides = {}) {
	return {
		nom: 'Alice Testeur', email: 'alice.testeur@example.com', telephone: '+33 6 11 22 33 44', societe: 'Société Test (exemple)',
		ville_depart: 'Nice', date_aller: '2027-08-26', date_retour: '2027-08-31', passagers: '2', message: 'Merci (test).', consentement: '1',
		...overrides,
	};
}

// Posts the public form directly (tokens taken from a rendered form) and returns the final URL + page text.
async function postEnquiry(page, tokens, data) {
	const form = { ...tokens, ...data };
	for (const k of Object.keys(form)) if (form[k] === undefined) delete form[k];
	const res = await page.request.post('/wp-admin/admin-post.php', { form, maxRedirects: 5 });
	return { url: res.url(), status: res.status(), html: await res.text() };
}

async function countEnquiries(page) {
	await page.goto('/wp-admin/admin.php?page=asset-demandes');
	const txt = await page.locator('.subsubsub li').first().innerText();
	return parseInt((txt.match(/\((\d+)\)/) || [])[1], 10);
}

module.exports = { BASE, ROOT, CODES, PEOPLE, USERS, readState, writeState, login, asRole, clickCounter, assertNoSecrets, FILL_WAIT, formTokens, validEnquiry, postEnquiry, countEnquiries };
