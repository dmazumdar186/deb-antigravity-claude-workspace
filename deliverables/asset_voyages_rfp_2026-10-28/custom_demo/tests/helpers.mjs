// Shared fixtures: every page is watched for console errors, failed requests and third-party requests (X1, X2).
import { test as base, expect } from 'playwright/test';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

export const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
export const BASE = process.env.BASE_URL || 'http://localhost:8787';
export const LIVE = !BASE.includes('localhost');
export const PASSWORD = 'demo-asset';
export const CODES = ['DEMO-GME-4821', 'DEMO-GME-2954', 'DEMO-GME-7310', 'DEMO-GME-6147', 'DEMO-GME-1088'];
export const CODE_RE = /DEMO-GME-\d{4}/;
export const SLUG = {
  cardio: 'congres-europeen-de-cardiologie-cg-0101',
  onco: 'journees-d-oncologie-digestive-cg-0112',
  diab: 'journees-francaises-de-diabetologie-cg-0103',
  radio: 'congres-europeen-de-radiologie-cg-0108',
  draft: 'journees-de-rhumatologie-cg-0113',
};

export const test = base.extend({
  watch: [async ({ page }, use) => {
    const origin = new URL(BASE).origin;
    const problems = { console: [], failed: [], thirdParty: [], docErrors: new Set() };
    page.on('response', (r) => {
      if (r.request().resourceType() === 'document') { if (r.status() >= 400) problems.docErrors.add(r.url()); return; }
      if (r.status() >= 400) problems.failed.push(`${r.url()} HTTP ${r.status()}`); // a sub-resource the server failed to deliver
    });
    page.on('console', (m) => {
      if (m.type() !== 'error') return;
      const u = m.location()?.url || '';
      // A deliberate 4xx page (hostile tests) is not a page defect.
      if (/Failed to load resource/.test(m.text()) && problems.docErrors.has(u)) return;
      problems.console.push(`${m.text()} @ ${u}`);
    });
    page.on('pageerror', (e) => problems.console.push('pageerror: ' + e.message));
    page.on('requestfailed', (r) => {
      const f = r.failure()?.errorText || '';
      // ERR_ABORTED is Chromium cancelling an in-flight load because the page navigated on (a fast click) or a download began:
      // not a delivery failure. Real failures (DNS, reset, 4xx/5xx on sub-resources) are still counted.
      if (/ERR_ABORTED|NS_BINDING_ABORTED/.test(f)) return;
      if (r.url().endsWith('.csv') || r.url().includes('export.csv')) return;
      problems.failed.push(`${r.url()} ${f}`);
    });
    page.on('request', (r) => {
      const u = r.url();
      if (u.startsWith('data:') || u.startsWith('blob:') || u.startsWith('about:')) return;
      if (new URL(u).origin !== origin) problems.thirdParty.push(u);
    });
    page.on('dialog', (d) => d.accept());
    await use(problems);
    expect(problems.console, 'X1 console errors').toEqual([]);
    expect(problems.failed, 'X1 failed requests').toEqual([]);
    expect(problems.thirdParty, 'X2 third-party requests').toEqual([]);
  }, { auto: true }],
});
export { expect };

export async function login(page, user) {
  await page.goto('/console/connexion');
  if (!page.url().includes('/connexion')) { // already logged in as someone: log out first
    await page.getByRole('button', { name: 'Se déconnecter' }).click();
    await page.goto('/console/connexion');
  }
  await page.getByLabel('Identifiant').fill(user);
  await page.getByLabel('Mot de passe').fill(PASSWORD);
  await page.getByRole('button', { name: 'Se connecter' }).click();
  await expect(page.getByRole('heading', { name: 'Tableau de bord', level: 1 })).toBeVisible();
}

export async function logout(page) {
  await page.getByRole('button', { name: 'Se déconnecter' }).click();
  await expect(page).toHaveURL(/connexion/);
}

// Restores the seed through the real Direction button (X4).
export async function resetDemo(browser) {
  const ctx = await browser.newContext({ baseURL: BASE });
  const page = await ctx.newPage();
  page.on('dialog', (d) => d.accept());
  await login(page, 'direction');
  await page.getByRole('button', { name: 'Réinitialiser la démo' }).click();
  await expect(page.getByText('La démonstration a été réinitialisée')).toBeVisible();
  await ctx.close();
}

export const csrfOf = async (page) => page.locator('input[name="_csrf"]').first().inputValue();

export function future(days) {
  const d = new Date(Date.now() + days * 86400000);
  return d.toISOString().slice(0, 10);
}

export async function fillEnquiry(page, o = {}) {
  const v = { name: 'Claire Dubois (exemple)', email: 'claire.dubois@example.com', phone: '01 23 45 67 89', company: 'Société E (exemple)', city: 'Bordeaux', out: '2027-08-26', back: '2027-08-31', pax: '3', msg: 'Trois places, départ le matin.', consent: true, ...o };
  await page.getByLabel('Nom et prénom').fill(v.name);
  await page.getByLabel('E-mail').fill(v.email);
  await page.getByLabel('Téléphone').fill(v.phone);
  await page.getByLabel('Société').fill(v.company);
  await page.getByLabel('Ville de départ').fill(v.city);
  await page.getByLabel('Date aller').fill(v.out);
  await page.getByLabel('Date retour').fill(v.back);
  await page.getByLabel('Passagers').fill(v.pax);
  await page.getByLabel('Message').fill(v.msg);
  if (v.consent) await page.locator('#f-consent').check(); else await page.locator('#f-consent').uncheck();
  return v;
}

// Raw POST of the public form with a real token (for hostile inputs the browser UI would not send).
export async function postEnquiry(request, slug, fields, { wait = 3100, token } = {}) {
  let tok = token; let congress;
  const pageHtml = await (await request.get(`/congres/${slug}`)).text();
  congress = /name="congress" value="(\d+)"/.exec(pageHtml)[1];
  if (!tok) tok = /name="_token" value="([^"]+)"/.exec(pageHtml)[1];
  if (wait) await new Promise((r) => setTimeout(r, wait));
  const form = {
    _token: tok, congress, name: 'Test Hostile (exemple)', email: 'hostile@example.com', phone: '0123456789', company: '', departure_city: 'Lille',
    date_out: '2027-08-26', date_back: '2027-08-31', passengers: '2', message: '', consent: '1', website: '', ...fields,
  };
  for (const k of Object.keys(form)) if (form[k] === undefined) delete form[k];
  const res = await request.post('/demande', { form, maxRedirects: 0 });
  return { res, token: tok, text: await res.text() };
}

// D1 dump through wrangler (local state or the remote database).
export function d1Dump() {
  const out = execFileSync('npx', ['wrangler', 'd1', 'execute', 'asset-voyages-demo', LIVE ? '--remote' : '--local', '--json', '--command',
    'SELECT * FROM gme_codes; SELECT * FROM gme_access_log; SELECT * FROM gme_requests; SELECT * FROM notifications; SELECT * FROM enquiry_events; SELECT * FROM enquiries; SELECT * FROM congresses'], { cwd: ROOT, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024, stdio: ['ignore', 'pipe', 'ignore'] });
  return out;
}
export function d1Count(sql) {
  const out = execFileSync('npx', ['wrangler', 'd1', 'execute', 'asset-voyages-demo', LIVE ? '--remote' : '--local', '--json', '--command', sql], { cwd: ROOT, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] });
  return JSON.parse(out)[0].results;
}
