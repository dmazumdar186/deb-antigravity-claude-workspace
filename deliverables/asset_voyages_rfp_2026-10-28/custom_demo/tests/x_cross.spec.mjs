// Cross-cutting gates: X1/X2 (also enforced on every test by the fixture), X3 fictional data, X4 reset + cron, X5 Hallmark,
// security headers, console responsiveness at 390 px, hostile console input.
import { test, expect, resetSandbox, login, csrfOf, SLUG, ROOT, LIVE, BASE, d1Count, sbxOf, CTX } from './helpers.mjs';
import { execFileSync } from 'node:child_process';
import { mkdirSync, writeFileSync, copyFileSync, rmSync } from 'node:fs';
import { join } from 'node:path';

test.describe.configure({ mode: 'serial' });
// Each Playwright context is a fresh private sandbox, so every test starts from the seed.

const PUBLIC = ['/', '/?q=zzz', '/?page=2', `/congres/${SLUG.onco}`, `/congres/${SLUG.cardio}`, '/console/connexion', '/page-inconnue'];
const CONSOLE = ['/console', '/console/congres', '/console/congres/nouveau', '/console/congres/112', '/console/demandes', '/console/demandes/6', '/console/notifications', '/console/gme', '/console/gme/acces', '/console/gme/journal'];

test('X1 X2 zero console errors, zero failed and zero third-party requests on every visitor and console screen', async ({ page, watch }) => {
  for (const u of PUBLIC) await page.goto(u);
  await login(page, 'direction');
  for (const u of CONSOLE) await page.goto(u);
  // the fixture asserts at the end; make the guarantee explicit here too
  expect(watch.console).toEqual([]);
  expect(watch.thirdParty).toEqual([]);
});

test('X1 strict: a page left alone (no click) has zero failed or aborted requests, ERR_ABORTED included', async ({ browser }) => {
  // The shared fixture tolerates ERR_ABORTED only because test clicks cancel in-flight loads. Here nothing is clicked,
  // so every request, aborted ones included, must complete with a status below 400.
  const ctx = await browser.newContext(CTX);
  const page = await ctx.newPage();
  const bad = [];
  let total = 0;
  page.on('request', () => { total++; });
  page.on('requestfailed', (r) => bad.push(`${r.url()} ${r.failure()?.errorText}`));
  page.on('response', (r) => { if (r.status() >= 400) bad.push(`${r.url()} HTTP ${r.status()}`); });
  page.on('console', (m) => { if (m.type() === 'error') bad.push('console: ' + m.text()); });
  const settle = async (u) => { await page.goto(u, { waitUntil: 'networkidle' }); await page.waitForTimeout(300); };
  for (const u of PUBLIC.filter((u) => u !== '/page-inconnue')) await settle(u);
  expect(bad, 'visitor pages left alone').toEqual([]);
  // the login submit is the only interaction; let the dashboard settle fully before judging again
  await page.getByLabel('Identifiant').fill('direction');
  await page.getByLabel('Mot de passe').fill('demo-asset');
  await Promise.all([page.waitForURL(/\/console$/), page.getByRole('button', { name: 'Se connecter' }).click()]);
  await page.waitForLoadState('networkidle');
  expect(bad, 'login submit').toEqual([]);
  for (const u of CONSOLE) await settle(u);
  expect(total).toBeGreaterThan(20);
  expect(bad, 'console pages left alone').toEqual([]);
  await ctx.close();
});

test('X3 all data is fictional: titles end « — exemple », e-mails @example.com, codes DEMO-GME-…', async ({ page }) => {
  const titles = [];
  for (const p of ['/', '/?page=2']) { await page.goto(p); titles.push(...await page.locator('.row__t').allTextContents()); }
  expect(titles).toHaveLength(12);
  for (const t of titles) expect(t).toMatch(/\u00a0—\u00a0exemple$/); // non-breaking spaces keep « — exemple » with its title
  await login(page, 'direction');
  await page.goto('/console/demandes');
  const contacts = await page.locator('tbody tr').count();
  expect(contacts).toBe(6);
  const csv = await (await page.request.get('/console/demandes/export.csv')).text();
  const emails = [...csv.matchAll(/[\w.+-]+@[\w.-]+/g)].map((m) => m[0]);
  expect(emails.length).toBeGreaterThanOrEqual(6);
  for (const e of emails) expect(e).toMatch(/@example\.com$/);
  for (const name of await page.locator('tbody tr td[data-label="Contact"]').allTextContents()) expect(name).toContain('(exemple)');
  // every revealed code follows the dummy pattern
  await page.goto('/console/gme');
  const ids = await page.locator('form[action$="/afficher"]').evaluateAll((fs) => fs.map((f) => f.getAttribute('action').split('/')[3]));
  expect(ids.length).toBe(3); // the three checked codes (vérifié or approuvé); détecté and expiré cannot be shown
  for (const id of ids) {
    await page.goto('/console/gme');
    await page.locator(`form[action="/console/gme/${id}/afficher"] button`).click();
    await expect(page.locator('[data-revealed]')).toHaveText(/^Code : DEMO-GME-\d{4}$/);
  }
  await page.goto('/congres/' + SLUG.onco);
  await expect(page.locator('footer')).toContainText('sont des exemples');
});

test('X4 Direction reset restores the seed for this browser only; re-seeding twice creates no duplicates; only Direction can reset; nightly cron is set', async ({ page }) => {
  await login(page, 'equipe');
  await page.goto('/console/demandes/1');
  await page.getByRole('button', { name: 'Perdue' }).click();
  const sbx = await sbxOf(page);
  const csrf = await csrfOf(page);
  const denied = await page.request.post('/console/reinitialiser', { form: { _csrf: csrf }, headers: { origin: new URL(page.url()).origin } });
  expect(denied.status()).toBe(403);
  await expect(page.locator('form[action="/console/reinitialiser"]')).toHaveCount(0);
  expect(d1Count(`SELECT COUNT(*) AS n FROM enquiries WHERE sbx = '${sbx}'`)[0].n).toBe(1); // row-level copy-on-write: only the changed enquiry
  await resetSandbox(page);
  await resetSandbox(page);
  // the browser's sandbox is gone, the shared seed is intact and has no duplicates
  const mine = d1Count(`SELECT (SELECT COUNT(*) FROM sandboxes WHERE id = '${sbx}') AS s, (SELECT COUNT(*) FROM enquiries WHERE sbx = '${sbx}') AS e`)[0];
  expect(mine).toEqual({ s: 0, e: 0 });
  const seedCount = () => d1Count(`SELECT (SELECT COUNT(*) FROM congresses WHERE sbx = '') AS c, (SELECT COUNT(*) FROM enquiries WHERE sbx = '') AS e, (SELECT COUNT(*) FROM gme_codes WHERE sbx = '') AS g, (SELECT COUNT(*) FROM users) AS u, (SELECT COUNT(*) FROM gme_requests WHERE sbx = '') AS r, (SELECT COUNT(DISTINCT ref) FROM congresses WHERE sbx = '') AS cr`)[0];
  expect(seedCount()).toEqual({ c: 13, e: 6, g: 5, u: 3, r: 1, cr: 13 });
  await page.goto('/console/demandes/1');
  await expect(page.locator('.head .st')).toHaveText('Gagnée');
  // cron trigger registered (03:00 UTC daily) and the scheduled handler converges to the same seed
  const toml = (await import('node:fs')).readFileSync(join(ROOT, 'wrangler.toml'), 'utf8');
  expect(toml).toContain('crons = ["0 3 * * *"]');
  if (!LIVE) {
    const r = await page.request.get('/cdn-cgi/handler/scheduled?cron=0+3+*+*+*');
    expect(r.status()).toBe(200);
    await expect.poll(() => seedCount().e).toBe(6);
    expect(seedCount()).toEqual({ c: 13, e: 6, g: 5, u: 3, r: 1, cr: 13 });
  } else {
    const out = execFileSync('curl', ['-s', `https://api.cloudflare.com/client/v4/accounts/${process.env.CLOUDFLARE_ACCOUNT_ID}/workers/scripts/asset-voyages-demo/schedules`, '-H', `Authorization: Bearer ${process.env.CLOUDFLARE_API_TOKEN}`], { encoding: 'utf8' });
    expect(JSON.parse(out).result.schedules.map((s) => s.cron)).toContain('0 3 * * *');
  }
});

test('X5 Hallmark sloplint: zero FAIL on the visitor pages and the console pages', async ({ page }) => {
  const dir = join(ROOT, '.lint', LIVE ? 'live' : 'local');
  rmSync(dir, { recursive: true, force: true });
  mkdirSync(join(dir, 'pub'), { recursive: true }); mkdirSync(join(dir, 'con'), { recursive: true });
  copyFileSync(join(ROOT, 'public/assets/app.css'), join(dir, 'app.css'));
  const save = async (sub, name, url) => {
    const html = (await (await page.request.get(url)).text()).replace(/href="\/assets\/app\.css[^"]*"/, 'href="../app.css"');
    writeFileSync(join(dir, sub, name + '.html'), html);
  };
  for (const [i, u] of PUBLIC.entries()) await save('pub', `p${i}`, u);
  await login(page, 'direction');
  for (const [i, u] of CONSOLE.entries()) await save('con', `c${i}`, u);
  const lint = (args) => {
    try { return execFileSync('node', [join(ROOT, '../../../.claude/skills/hallmark/scripts/sloplint.mjs'), ...args], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] }); } catch (e) { return (e.stdout || '') + (e.stderr || ''); }
  };
  const pub = lint([join(dir, 'pub'), join(dir, 'app.css'), '--genre', 'editorial']);
  const con = lint([join(dir, 'con'), join(dir, 'app.css'), '--scope', 'app']);
  writeFileSync(join(dir, 'sloplint.txt'), pub + '\n=====\n' + con);
  const fails = (t) => +((/sloplint: (\d+) FAIL/.exec(t) || [0, 'NaN'])[1]);
  expect(fails(pub), pub.split('\n').filter((l) => l.includes('FAIL')).join('\n')).toBe(0);
  expect(fails(con), con.split('\n').filter((l) => l.includes('FAIL')).join('\n')).toBe(0);
});

test('X security headers: CSP self only, noindex, nosniff, frame-ancestors none, referrer policy; robots.txt disallows all', async ({ request }) => {
  for (const u of ['/', `/congres/${SLUG.onco}`, '/console/connexion', '/assets/app.css', '/robots.txt', '/nope']) {
    const h = (await request.get(u)).headers();
    expect(h['content-security-policy'], u).toContain("default-src 'self'");
    expect(h['content-security-policy']).toContain("frame-ancestors 'none'");
    expect(h['content-security-policy']).not.toMatch(/https?:\/\//);
    expect(h['x-robots-tag']).toBe('noindex, nofollow');
    expect(h['x-content-type-options']).toBe('nosniff');
    expect(h['referrer-policy']).toBe('same-origin');
    expect(h['x-frame-options']).toBe('DENY');
  }
  expect(await (await request.get('/robots.txt')).text()).toContain('Disallow: /');
  const login = await request.get('/console/connexion');
  expect(login.headers()['cache-control']).toContain('no-store');
});

test('X session cookie is HttpOnly, Secure, SameSite=Strict; logout invalidates it server-side; brute force is throttled', async ({ page, request }) => {
  await login(page, 'equipe');
  const c = (await page.context().cookies()).find((x) => x.name === '__Host-av_session');
  expect(c.httpOnly).toBe(true);
  expect(c.secure).toBe(true);
  expect(c.sameSite).toBe('Strict');
  const csrf = await csrfOf(page);
  await page.getByRole('button', { name: 'Se déconnecter' }).click();
  // replay the old cookie and token after logout
  const replay = await request.post('/console/demandes/1', { form: { _csrf: csrf, action: 'status', to: 'perdue' }, headers: { cookie: `__Host-av_session=${c.value}` }, maxRedirects: 0 });
  expect(replay.status()).toBe(401);
  // wrong passwords: generic message, then throttled after 10 for that account (other accounts unaffected)
  let last;
  for (let i = 0; i < 11; i++) {
    const html = await (await request.get('/console/connexion')).text();
    const tok = /name="_token" value="([^"]+)"/.exec(html)[1];
    last = await request.post('/console/connexion', { form: { _token: tok, username: 'intrus', password: 'mauvais' + i }, maxRedirects: 0 });
  }
  expect(last.status()).toBe(429);
  expect(await last.text()).toContain('Trop d’essais');
  await login(page, 'equipe');
});

test('X console at 390 px: no horizontal page overflow, inputs at least 16 px, tap targets at least 44 px', async ({ browser }) => {
  const ctx = await browser.newContext({ ...CTX, viewport: { width: 390, height: 844 }, deviceScaleFactor: 1, isMobile: true, hasTouch: true });
  const page = await ctx.newPage();
  await login(page, 'direction');
  for (const url of CONSOLE) {
    await page.goto(url);
    const r = await page.evaluate(() => {
      const bad = []; const small = [];
      document.querySelectorAll('input:not([type=hidden]),select,textarea').forEach((el) => { if (parseFloat(getComputedStyle(el).fontSize) < 16) small.push(el.name || el.id); });
      document.querySelectorAll('a,button,select,input:not([type=hidden]),textarea,summary').forEach((el) => {
        const b = el.getBoundingClientRect();
        if (!b.width || !b.height || el.closest('.skip,.hp')) return;
        if (b.height < 44 || b.width < 44) bad.push(`${el.tagName} ${(el.textContent || el.name || '').trim().slice(0, 30)} ${Math.round(b.width)}x${Math.round(b.height)}`);
      });
      return { overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth, bad, small };
    });
    expect(r.overflow, url).toBeLessThanOrEqual(0);
    expect(r.small, url).toEqual([]);
    expect(r.bad, url).toEqual([]);
  }
  await ctx.close();
});

test('X hostile console input: oversized body, wrong content type, unknown routes and methods fail safely', async ({ page }) => {
  await login(page, 'direction');
  const origin = new URL(page.url()).origin;
  const csrf = await csrfOf(page);
  const big = await page.request.post('/console/demandes/1', { form: { _csrf: csrf, action: 'note', note: 'x'.repeat(40000) }, headers: { origin } });
  expect(big.status()).toBe(413);
  const json = await page.request.post('/console/demandes/1', { data: { _csrf: csrf, action: 'status', to: 'perdue' }, headers: { origin } });
  expect(json.status()).toBe(415);
  const put = await page.request.put('/console/demandes/1', { headers: { origin } });
  expect(put.status()).toBe(405);
  const sqlish = await page.request.post('/console/demandes/1', { form: { _csrf: csrf, action: 'note', note: "'); DELETE FROM enquiries; --" }, headers: { origin } });
  expect(sqlish.status()).toBe(200);
  await page.goto('/console/demandes/1');
  await expect(page.locator('.hist')).toContainText("'); DELETE FROM enquiries; --");
  await page.goto('/console/demandes?q=' + encodeURIComponent("' OR 1=1 --"));
  await expect(page.getByText('Aucune demande ne correspond.')).toBeVisible();
  expect((await page.request.get('/console/demandes/999999')).status()).toBe(404);
  expect((await page.request.get('/console/demandes/abc')).status()).toBe(404);
  expect((await page.request.get('/congres/' + 'a'.repeat(400))).status()).toBe(404);
  expect((await page.request.get('/congres/../../wrangler.toml')).status()).toBe(404);
});
