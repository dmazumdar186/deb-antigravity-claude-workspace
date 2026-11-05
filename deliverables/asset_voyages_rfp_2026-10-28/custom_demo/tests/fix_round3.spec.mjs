// Fix round 3: capacity. Row-level copy-on-write; the D1 write budget is measured on a full S1-S5 journey (FIX3-n).
import { test, expect, login, logout, fillEnquiry, SLUG, LIVE, newPage, assertClean, sbxOf, d1Count, TEST_KEY } from './helpers.mjs';
import { readFileSync } from 'node:fs';
import { ROOT } from './helpers.mjs';

// Every response of a test run carries x-d1-rows-written (only when the request has the test key).
function meter(page) {
  const m = { rows: 0, requests: 0, list: [] };
  page.on('response', async (r) => { const v = r.headers()['x-d1-rows-written']; if (v !== undefined) { m.rows += Number(v); m.requests++; if (Number(v)) m.list.push(`${r.request().method()} ${new URL(r.url()).pathname} ${v}`); } });
  return m;
}
export async function journey(page) {
  // S1: Direction creates and publishes a congress, then edits a seeded one
  await login(page, 'direction');
  await page.goto('/console/congres/nouveau');
  await page.getByLabel('Titre').fill('Congrès de mesure — exemple');
  await page.getByRole('combobox', { name: 'Discipline', exact: true }).selectOption('Cardiologie');
  await page.getByLabel('Lieu').fill('Salle — exemple');
  await page.getByLabel('Ville').fill('Nice');
  await page.getByRole('combobox', { name: 'Pays', exact: true }).selectOption('France');
  await page.getByLabel('Date de début').fill('2027-07-05');
  await page.getByLabel('Date de fin').fill('2027-07-07');
  await page.getByLabel('Site officiel').fill('https://www.example.org/mesure');
  await page.getByLabel('Vérifié le').fill('2026-11-01');
  await page.getByRole('button', { name: 'Publier' }).click();
  await expect(page.getByText('Congrès créé.')).toBeVisible();
  await page.goto('/console/congres/101');
  await page.getByLabel('Ville').fill('Barcelone');
  await page.getByRole('button', { name: 'Enregistrer', exact: true }).click();
  await expect(page.getByText('Modifications enregistrées.')).toBeVisible();
  await logout(page);
  // S2 + S3: the visitor searches, opens a congress and sends an enquiry
  await page.goto('/?q=barcelone');
  await page.locator('.row__a').first().click();
  await fillEnquiry(page, { out: '2027-08-26', back: '2027-08-31' });
  await page.waitForTimeout(3100);
  await page.getByRole('button', { name: 'Envoyer la demande' }).click();
  await expect(page.locator('[data-ref]')).toHaveText('DV-2026-0007');
  // S4: the team qualifies it, takes it and adds a note
  await login(page, 'equipe');
  await page.locator('.feed li').first().getByRole('link').click();
  await page.getByRole('button', { name: 'Qualifiée' }).click();
  await page.getByRole('button', { name: 'Me l’attribuer' }).click();
  await page.getByLabel('Visible uniquement par l’équipe').fill('Rappel demain.');
  await page.getByRole('button', { name: 'Ajouter la note' }).click();
  await expect(page.locator('.ok')).toHaveText('Note ajoutée à l’historique.'); // wait for the reloaded page, never read mid-navigation
  // S5: equipe asks for a code, Direction approves, equipe reveals it
  await page.goto('/console/gme');
  const card = page.locator('.gme', { hasText: 'oncologie digestive' });
  await card.getByLabel(/Motif/).fill('Devis DV-2026-0007.');
  await card.getByRole('button', { name: 'Demander l’accès' }).click();
  await logout(page);
  await login(page, 'direction');
  await page.goto('/console/gme/acces');
  await page.locator('.req', { hasText: 'oncologie digestive' }).getByRole('button', { name: 'Approuver pour 24 h' }).click();
  await logout(page);
  await login(page, 'equipe');
  await page.goto('/console/gme');
  await page.locator('.gme', { hasText: 'oncologie digestive' }).getByRole('button', { name: 'Afficher le code' }).click();
  await expect(page.locator('[data-revealed]')).toContainText('DEMO-GME-4821');
}

test('FIX3-1 a full S1-S5 journey writes at most ROWS_PER_SESSION D1 rows, so the daily budget allows at least 3,000 sandboxes', async ({ browser }) => {
  test.skip(!TEST_KEY, 'needs the test key to read the per-request write meter');
  // measured as a real visitor (no per-IP exemption), from a fresh spoof-free browser
  const P = await newPage(browser, { extraHTTPHeaders: { 'x-demo-test': TEST_KEY, 'x-demo-real': '1' } });
  const m = meter(P.page);
  await journey(P.page);
  await P.page.waitForTimeout(500);
  const data = readFileSync(`${ROOT}/src/data.js`, 'utf8');
  const perSession = Number(/ROWS_PER_SESSION = (\d+)/.exec(data)[1]);
  const reserve = Number(/RESERVED_ROWS = (\d+)/.exec(data)[1]);
  const daily = Math.floor((100000 - reserve) / perSession);
  expect(Number(/SBX_DAILY_LIMIT = Math\.floor\(\(100000 - RESERVED_ROWS\) \/ ROWS_PER_SESSION\)/.test(data))).toBe(1);
  console.log(m.list.join('\n'));
  console.log(`FIX3-1 measured: ${m.rows} rows written over ${m.requests} requests (budget per session ${perSession}, reserve ${reserve}, ${daily} sandboxes/day)`);
  expect(m.requests).toBeGreaterThan(20);
  expect(m.rows).toBeGreaterThan(0);
  expect(m.rows).toBeLessThanOrEqual(perSession);
  expect(daily).toBeGreaterThanOrEqual(3000);
  assertClean(P.problems); await P.ctx.close();
});

test('FIX3-2 the test key is a Worker secret: not in wrangler.toml; a wrong key gets no meter and no exemption', async ({ browser }) => {
  const toml = readFileSync(`${ROOT}/wrangler.toml`, 'utf8');
  expect(toml).not.toMatch(/DEMO_TEST_KEY/);
  expect(TEST_KEY.length).toBeGreaterThanOrEqual(43); // 32 random bytes, base64url
  const P = await newPage(browser, { extraHTTPHeaders: { 'x-demo-test': 'x'.repeat(43) } });
  const r = await P.page.goto('/');
  expect(r.headers()['x-d1-rows-written']).toBeUndefined();
  const ok = await newPage(browser);
  const r2 = await ok.page.goto('/');
  expect(r2.headers()['x-d1-rows-written']).toBe('0');
  await P.ctx.close(); await ok.ctx.close();
});

test('FIX3-3 signed sessions: logging in writes no session row; a tampered cookie is refused; logout still revokes server-side', async ({ page, request }) => {
  await login(page, 'equipe');
  const c = (await page.context().cookies()).find((x) => x.name === '__Host-av_session');
  const [payload, sig] = c.value.split('.');
  const forged = Buffer.from(JSON.stringify({ ...JSON.parse(Buffer.from(payload, 'base64url').toString()), u: 1 })).toString('base64url');
  const r = await request.get('/console', { headers: { cookie: `__Host-av_session=${forged}.${sig}` }, maxRedirects: 0 });
  expect(r.status()).toBe(303); // signature no longer matches: back to login, not Direction
  const before = await request.get('/console', { headers: { cookie: `__Host-av_session=${c.value}` }, maxRedirects: 0 });
  expect(before.status()).toBe(200);
  await page.getByRole('button', { name: 'Se déconnecter' }).click();
  const after = await request.get('/console', { headers: { cookie: `__Host-av_session=${c.value}` }, maxRedirects: 0 });
  expect(after.status()).toBe(303);
});

test('FIX3-4 lazy sandbox: browsing writes nothing; the first write creates only the rows it touches; isolation holds', async ({ browser }) => {
  const A = await newPage(browser); const B = await newPage(browser);
  const m = meter(A.page);
  for (const u of ['/', '/?q=lyon', `/congres/${SLUG.cardio}`, '/console/connexion']) await A.page.goto(u);
  expect(m.rows).toBe(0);
  const sbx = await sbxOf(A.page);
  expect(d1Count(`SELECT COUNT(*) AS n FROM sandboxes WHERE id = '${sbx}'`)[0].n).toBe(0);
  await login(A.page, 'equipe');
  await A.page.goto('/console/demandes/3');
  await A.page.getByRole('button', { name: 'Perdue' }).click();
  const rows = d1Count(`SELECT (SELECT COUNT(*) FROM congresses WHERE sbx = '${sbx}') AS c, (SELECT COUNT(*) FROM enquiries WHERE sbx = '${sbx}') AS e, (SELECT COUNT(*) FROM enquiry_events WHERE sbx = '${sbx}') AS ev, (SELECT COUNT(*) FROM options WHERE sbx = '${sbx}') AS o`)[0];
  expect(rows).toEqual({ c: 0, e: 1, ev: 1, o: 0 });
  // A sees all six enquiries (five from the seed, one its own), B the untouched seed
  await A.page.goto('/console/demandes');
  await expect(A.page.locator('tbody tr')).toHaveCount(6);
  await expect(A.page.locator('tbody tr', { hasText: 'DV-2026-0003' })).toContainText('Perdue');
  await login(B.page, 'equipe');
  await B.page.goto('/console/demandes/3');
  await expect(B.page.locator('.head .st')).toHaveText('Qualifiée');
  assertClean(A.problems); assertClean(B.problems);
  await A.ctx.close(); await B.ctx.close();
});
