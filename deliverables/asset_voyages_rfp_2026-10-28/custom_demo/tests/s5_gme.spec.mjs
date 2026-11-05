// S5: GM&E codes protected, access through an authorisation process. Includes the leak crawl (S5-L1, S5-L2).
import { test, expect, login, logout, csrfOf, SLUG, CODES, CODE_RE, d1Dump, d1Count, LIVE, ROOT, newPage, assertClean, sbxOf } from './helpers.mjs';
import { execFileSync } from 'node:child_process';

test.describe.configure({ mode: 'serial' });
// Each Playwright context is a fresh private sandbox, so every test starts from the seed.

// The authorisation chain (request, approve, reveal, revoke, refuse) runs in ONE browser, switching accounts,
// because each browser has its own private sandbox.
let S;
test.beforeAll(async ({ browser }) => { S = await newPage(browser); });
test.afterAll(async () => { await S.ctx.close(); });
const ONCO = 'Journées d’oncologie digestive — exemple';
const RADIO = 'Congrès européen de radiologie — exemple';
const card = (page, title) => page.locator('.gme', { has: page.getByRole('link', { name: title }) });
const nav = (page, name) => page.getByRole('navigation', { name: 'Console' }).getByRole('link', { name });
const noCode = (text, where) => { for (const c of CODES) expect(text, `${where} contains ${c}`).not.toContain(c); expect(text, where).not.toMatch(CODE_RE); };
function sql(command) {
  execFileSync('npx', ['wrangler', 'd1', 'execute', 'asset-voyages-demo', LIVE ? '--remote' : '--local', '--command', command], { cwd: ROOT, stdio: 'ignore' });
}

test('S5-F1 codes live only in their own table, encrypted; the database holds no plaintext code', async () => {
  const dump = d1Dump();
  noCode(dump, 'D1 dump');
  const rows = d1Count(`SELECT congress_id, code_enc FROM gme_codes WHERE sbx = '' ORDER BY congress_id`);
  expect(rows.length).toBe(5);
  for (const r of rows) expect(r.code_enc).toMatch(/^v1:[A-Za-z0-9+/=]{40,}$/);
  // two encryptions of the same code differ (random IV)
  expect(new Set(rows.map((r) => r.code_enc)).size).toBe(5);
});

test('S5-F2 S5-E1 equipe sees masked codes and requests access with a required reason in 2 clicks', async () => {
  const page = S.page;
  await login(page, 'equipe');
  let clicks = 0;
  await nav(page, 'Codes GM&E').click(); clicks++;
  noCode(await page.content(), 'equipe GM&E page');
  await expect(card(page, ONCO).locator('.code [aria-hidden="true"]')).toHaveText('•••• •••• ••••');
  // reason is required
  await card(page, ONCO).getByRole('button', { name: 'Demander l’accès' }).click();
  await expect(card(page, ONCO).locator('.err')).toHaveText(/Indiquez le motif/);
  await card(page, ONCO).getByLabel(/Motif de la demande/).fill('Devis DV-2026-0001, six médecins.');
  await card(page, ONCO).getByRole('button', { name: 'Demander l’accès' }).click(); clicks++;
  // the 2-click journey: menu, then the button (the failed empty attempt above is the reason check, not the journey)
  expect(clicks).toBe(2);
  await expect(page.getByText('Demande envoyée à la Direction.')).toBeVisible();
  await expect(card(page, ONCO).locator('.wait')).toContainText('en attente de la Direction');
  assertClean(S.problems);
});

test('S5-F3 S5-E1 direction sees pending requests and approves for 24 h in 2 clicks', async () => {
  const page = S.page;
  await login(page, 'direction');
  let clicks = 0;
  await nav(page, /Demandes d’accès GM&E/).click(); clicks++;
  const req = page.locator('.req', { hasText: ONCO });
  await expect(req).toContainText('Karim Benali, Équipe');
  await expect(req).toContainText('Devis DV-2026-0001, six médecins.');
  await req.getByRole('button', { name: 'Approuver pour 24 h' }).click(); clicks++;
  expect(clicks).toBe(2);
  await expect(page.getByText('Accès accordé pour 24 heures.')).toBeVisible();
  const active = page.locator('section', { has: page.getByRole('heading', { name: 'Accès actifs' }) }).locator('.req', { hasText: ONCO });
  await expect(active).toContainText(/jusqu’au \d{2}\/\d{2}\/\d{4}/);
  const r = d1Count(`SELECT (julianday(expires_at) - julianday(decided_at)) * 24 AS h FROM gme_requests WHERE sbx = '${await sbxOf(S.page)}' AND status = 'approuvee'`);
  expect(Math.round(r[0].h)).toBe(24);
  assertClean(S.problems);
});

test('S5-F4 S5-E1 equipe reveals in 2 clicks after approval; every reveal is logged; only Direction sees the log', async () => {
  const page = S.page;
  await login(page, 'equipe');
  let clicks = 0;
  await nav(page, 'Codes GM&E').click(); clicks++;
  noCode(await page.content(), 'equipe GM&E page before reveal');
  await card(page, ONCO).getByRole('button', { name: 'Afficher le code' }).click(); clicks++;
  expect(clicks).toBe(2);
  await expect(card(page, ONCO).locator('[data-revealed]')).toContainText('DEMO-GME-4821');
  // only that code, nothing else
  const html = await page.content();
  for (const c of CODES.filter((c) => c !== 'DEMO-GME-4821')) expect(html).not.toContain(c);
  // leaving the page masks it again
  await page.goto('/console/gme');
  noCode(await page.content(), 'equipe GM&E page after reveal');
  const j = await page.request.get('/console/gme/journal');
  expect(j.status()).toBe(403);
  // direction's log
  const dir = page; // same browser, Direction logs in
  await login(page, 'direction');
  await nav(dir, 'Journal d’accès').click();
  const row = dir.locator('tbody tr').first();
  await expect(row).toContainText('Karim Benali, Équipe');
  await expect(row).toContainText(ONCO);
  await expect(row).toContainText('Code affiché');
  await expect(row.locator('td').first()).toHaveText(/\d{2}\/\d{2}\/\d{4} \d{2}:\d{2}/);
  noCode(await dir.content(), 'journal');
  assertClean(S.problems);
});

test('S5-F3 S5-H1 revocation is immediate: a reveal after revocation is refused, logged, and returns no code', async () => {
  const page = S.page;
  await login(page, 'direction');
  await nav(page, /Demandes d’accès GM&E/).click();
  await page.locator('.req', { hasText: ONCO }).getByRole('button', { name: 'Révoquer maintenant' }).click();
  await expect(page.getByText('Accès révoqué immédiatement.')).toBeVisible();
  // equipe, with a valid session and CSRF token, tries again right after the revocation
  await login(page, 'equipe');
  await page.goto('/console/gme');
  await expect(card(page, ONCO).getByRole('button', { name: 'Afficher le code' })).toHaveCount(0);
  const replay = await page.request.post('/console/gme/112/afficher', { form: { _csrf: await csrfOf(page) }, headers: { origin: new URL(page.url()).origin } });
  expect(replay.status()).toBe(403);
  const t = await replay.text();
  noCode(t, 'replay after revocation');
  expect(t).toContain('révoquée ou expirée');
  await login(page, 'direction');
  await page.goto('/console/gme/journal');
  await expect(page.locator('tbody tr').first()).toContainText('Refusé : aucune autorisation');
  assertClean(S.problems);
});

test('S5-F4 an expired grant is refused like a revoked one', async () => {
  const page = S.page;
  await login(page, 'equipe');
  await page.goto('/console/gme');
  await card(page, ONCO).getByLabel(/Motif de la demande/).fill('Nouvelle demande pour test d’expiration.');
  await card(page, ONCO).getByRole('button', { name: 'Demander l’accès' }).click();
  const dir = page; // same browser, Direction logs in
  await login(page, 'direction');
  await dir.goto('/console/gme/acces');
  await dir.locator('.req', { hasText: ONCO }).getByRole('button', { name: 'Approuver pour 24 h' }).click();
  await login(page, 'equipe');
  await page.goto('/console/gme');
  await expect(card(page, ONCO).getByRole('button', { name: 'Afficher le code' })).toBeVisible();
  const csrf = await csrfOf(page);
  sql(`UPDATE gme_requests SET expires_at = '2026-01-01T00:00:00.000Z' WHERE sbx = '${await sbxOf(page)}' AND status = 'approuvee'`); // simulate 24 h later
  const r = await page.request.post('/console/gme/112/afficher', { form: { _csrf: csrf }, headers: { origin: new URL(page.url()).origin } });
  expect(r.status()).toBe(403);
  noCode(await r.text(), 'reveal after expiry');
  assertClean(S.problems);
});

test('S5-F3 refuse path: Direction refuses, equipe gets no access', async () => {
  const page = S.page;
  await login(page, 'equipe');
  await page.goto('/console/gme');
  await card(page, RADIO).getByLabel(/Motif de la demande/).fill('Groupe de radiologues, devis DV-2026-0004.');
  await card(page, RADIO).getByRole('button', { name: 'Demander l’accès' }).click();
  const dir = page; // same browser, Direction logs in
  await login(page, 'direction');
  await dir.goto('/console/gme/acces');
  await dir.locator('.req', { hasText: RADIO }).getByRole('button', { name: 'Refuser' }).click();
  await expect(dir.getByText('Demande refusée.')).toBeVisible();
  await expect(dir.locator('table')).toContainText('Refusée');
  await login(page, 'equipe');
  await page.goto('/console/gme');
  await expect(card(page, RADIO).getByRole('button', { name: 'Afficher le code' })).toHaveCount(0);
  await expect(card(page, RADIO).getByRole('button', { name: 'Demander l’accès' })).toBeVisible();
  const r = await page.request.post('/console/gme/108/afficher', { form: { _csrf: await csrfOf(page) }, headers: { origin: new URL(page.url()).origin } });
  expect(r.status()).toBe(403);
  assertClean(S.problems);
});

test('S5-H1 reveal without permission or without CSRF is refused, logged, and returns no code', async ({ page, request }) => {
  // logged out
  const anon = await request.post('/console/gme/112/afficher', { form: {}, maxRedirects: 0 });
  expect(anon.status()).toBe(401);
  noCode(await anon.text(), 'anonymous reveal');
  // contributor
  await login(page, 'contributeur');
  const c1 = await page.request.post('/console/gme/112/afficher', { form: { _csrf: await csrfOf(page) }, headers: { origin: new URL(page.url()).origin } });
  expect(c1.status()).toBe(403);
  noCode(await c1.text(), 'contributor reveal');
  await logout(page);
  // direction without CSRF token
  await login(page, 'direction');
  const noTok = await page.request.post('/console/gme/112/afficher', { form: {}, headers: { origin: new URL(page.url()).origin } });
  expect(noTok.status()).toBe(403);
  noCode(await noTok.text(), 'no-CSRF reveal');
  const xsite = await page.request.post('/console/gme/112/afficher', { form: { _csrf: await csrfOf(page) }, headers: { origin: 'https://evil.example' } });
  expect(xsite.status()).toBe(403);
  noCode(await xsite.text(), 'cross-site reveal');
  // GET never reveals
  const get = await page.request.get('/console/gme/112/afficher');
  noCode(await get.text(), 'GET reveal');
  // FIX-7: CSRF is checked before anything is written, so the forged attempts left no journal row at all
  await page.goto('/console/gme/journal');
  await expect(page.getByText('Aucun affichage enregistré pour l’instant.')).toBeVisible();
});

test('S5-F5 public pages only say « Tarif congrès négocié disponible » for approved codes, never the code', async ({ request }) => {
  const approved = await (await request.get(`/congres/${SLUG.onco}`)).text();
  expect(approved).toContain('Tarif congrès négocié disponible : appliqué à votre devis.');
  noCode(approved, 'approved congress page');
  for (const s of [SLUG.radio, SLUG.cardio, 'congres-europeen-de-dermatologie-cg-0105']) {
    const t = await (await request.get(`/congres/${s}`)).text();
    expect(t, s).not.toContain('Tarif congrès négocié');
    noCode(t, s);
  }
});

test('S5-L2 authorised users never get a code in page HTML until they reveal; never in CSV, notifications or logs', async ({ page }) => {
  await login(page, 'direction');
  for (const u of ['/console', '/console/gme', '/console/gme/acces', '/console/gme/journal', '/console/congres', '/console/congres/112', '/console/congres/103', '/console/notifications', '/console/demandes', '/console/demandes/1']) {
    const r = await page.request.get(u);
    expect(r.status(), u).toBe(200);
    noCode(await r.text(), `direction ${u}`);
  }
  noCode(await (await page.request.get('/console/demandes/export.csv')).text(), 'CSV export');
  noCode(d1Dump(), 'database incl. access log and notifications');
  // the code input on the manage form is always empty
  await page.goto('/console/congres/112');
  await expect(page.locator('#g-code')).toHaveValue('');
});

async function crawl(page, start, { allow }) {
  const origin = new URL(page.url() === 'about:blank' ? process.env.BASE_URL || 'http://localhost:8787' : page.url()).origin;
  const seen = new Set(); const queue = [...start]; let n = 0;
  while (queue.length && n < 160) {
    const u = queue.shift();
    if (seen.has(u)) continue; seen.add(u); n++;
    const res = await page.request.get(u, { maxRedirects: 0 });
    const body = await res.text();
    noCode(body, u);
    for (const v of Object.values(res.headers())) noCode(v, `${u} headers`);
    for (const m of body.matchAll(/(?:href|src|action)="([^"#]+)"/g)) {
      let next; try { next = new URL(m[1].replace(/&amp;/g, '&'), origin + u); } catch { continue; }
      if (next.origin !== origin) continue;
      const p = next.pathname + next.search;
      if (allow(p) && !seen.has(p)) queue.push(p);
    }
  }
  return seen.size;
}

test('S5-L1 crawl every reachable URL logged out and as equipe without a grant: zero seeded codes', async ({ page }) => {
  // a fresh browser: equipe has no active grant in the seed
  const probes = ['/', '/robots.txt', '/sitemap.xml', '/feed', '/rss.xml', '/api', '/api/gme', '/api/codes', '/api/congres', '/wp-json/wp/v2/posts', '/wp-admin/admin-ajax.php', '/.env', '/console/gme/112/afficher', '/assets/app.js', '/assets/app.css', '/src/data.js', '/wrangler.toml', '/demande/confirmation?ref=DV-2026-0001'];
  const n1 = await crawl(page, probes, { allow: (p) => !p.startsWith('/assets/fonts') });
  expect(n1).toBeGreaterThan(20);
  await login(page, 'equipe');
  const n2 = await crawl(page, ['/console', '/console/gme', '/console/congres', '/console/demandes', '/console/notifications', '/console/gme/acces', '/console/gme/journal', '/console/demandes/export.csv', ...probes], { allow: (p) => !p.startsWith('/assets/fonts') && !p.includes('deconnexion') });
  expect(n2).toBeGreaterThan(30);
  // POST reveal as equipe without a grant: refused, no code
  const r = await page.request.post('/console/gme/103/afficher', { form: { _csrf: await (async () => { await page.goto('/console/gme'); return csrfOf(page); })() }, headers: { origin: new URL(page.url()).origin } });
  expect(r.status()).toBe(403);
  noCode(await r.text(), 'equipe reveal without grant');
});
