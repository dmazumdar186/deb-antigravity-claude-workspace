// S4: the team receives, views, tracks the enquiry and updates its status.
import { test, expect, login, logout, csrfOf, fillEnquiry, SLUG, newPage, assertClean } from './helpers.mjs';

test.describe.configure({ mode: 'serial' });
let REF;
// The visitor and the team use one browser: one private sandbox shared by this file's tests.
let shared;

test.beforeAll(async ({ browser }) => {
  shared = await newPage(browser);
  const page = shared.page;
  await page.goto(`/congres/${SLUG.radio}`);
  await fillEnquiry(page, { name: 'Sophie Bernard (exemple)', email: 'sophie.bernard@example.com', city: 'Strasbourg', out: '2027-02-23', back: '2027-03-01', pax: '4' });
  await page.waitForTimeout(3100);
  await page.getByRole('button', { name: 'Envoyer la demande' }).click();
  REF = (await page.locator('[data-ref]').textContent()).trim();
});
test.afterEach(() => assertClean(shared.problems));
test.afterAll(async () => { await shared.ctx.close(); });

test('S4-F1 the visitor enquiry appears in Demandes with every column and status Nouvelle', async () => {
  const page = shared.page;
  await login(page, 'equipe');
  await page.getByRole('navigation', { name: 'Console' }).getByRole('link', { name: /Demandes/ }).click();
  await expect(page.locator('h1')).toHaveText('Demandes');
  const heads = await page.locator('thead th').allTextContents();
  expect(heads).toEqual(['Réf.', 'Statut', 'Reçue', 'Congrès', 'Contact', 'Voyage', 'Responsable']); // Voyage = departure city, dates, passengers
  const row = page.locator('tbody tr', { hasText: REF });
  await expect(row).toHaveCount(1);
  for (const t of [REF, 'Congrès européen de radiologie — exemple', 'Sophie Bernard (exemple)', 'Départ de Strasbourg', '23/02/2027 au 01/03/2027', '4 passagers', 'Nouvelle', 'À attribuer']) await expect(row).toContainText(t);
  await expect(row.locator('td').nth(2)).toHaveText(/\d{2}\/\d{2}\/\d{4}/);
});

test('S4-F2 filter by status and search by name or reference', async () => {
  const page = shared.page;
  await login(page, 'equipe');
  await page.goto('/console/demandes');
  await page.getByRole('link', { name: /^Gagnée \(1\)$/ }).click();
  await expect(page.locator('tbody tr')).toHaveCount(1);
  await expect(page.locator('tbody tr')).toContainText('Camille Laurent (exemple)');
  await page.getByRole('link', { name: /^Nouvelle \(3\)$/ }).click();
  await expect(page.locator('tbody tr')).toHaveCount(3);
  await page.goto('/console/demandes');
  await page.getByLabel(/Rechercher/).fill('ines moreau'); // accent-insensitive
  await page.getByRole('button', { name: 'Rechercher' }).click();
  await expect(page.locator('tbody tr')).toHaveCount(1);
  await expect(page.locator('tbody tr')).toContainText('DV-2026-0003');
  await page.getByLabel(/Rechercher/).fill(REF);
  await page.getByRole('button', { name: 'Rechercher' }).click();
  await expect(page.locator('tbody tr')).toHaveCount(1);
  await page.getByLabel(/Rechercher/).fill('personne inconnue');
  await page.getByRole('button', { name: 'Rechercher' }).click();
  await expect(page.getByText('Aucune demande ne correspond.')).toBeVisible();
});

test('S4-E1 from the dashboard, open the newest enquiry and change its status in 2 clicks; home counts update', async () => {
  const page = shared.page;
  await login(page, 'equipe');
  const newBefore = +(await page.locator('[data-count="nouvelle"] b').textContent());
  const qualBefore = +(await page.locator('[data-count="qualifiee"] b').textContent());
  let clicks = 0;
  await page.locator('.feed li').first().getByRole('link').click(); clicks++;
  await expect(page.locator('h1')).toHaveText(REF);
  await page.getByRole('button', { name: 'Qualifiée' }).click(); clicks++;
  expect(clicks).toBeLessThanOrEqual(3);
  await expect(page.locator('.head .st')).toHaveText('Qualifiée');
  await page.getByRole('navigation', { name: 'Console' }).getByRole('link', { name: 'Tableau de bord' }).click();
  await expect(page.locator('[data-count="nouvelle"] b')).toHaveText(String(newBefore - 1));
  await expect(page.locator('[data-count="qualifiee"] b')).toHaveText(String(qualBefore + 1));
});

test('S4-F3 S4-F4 statuses saved through the whole path, owner assigned, notes saved; history is append-only with who, when, from and to', async () => {
  const page = shared.page;
  await login(page, 'equipe');
  await page.goto('/console/demandes?q=' + REF);
  await page.getByRole('link', { name: REF }).click();
  for (const s of ['Devis envoyé', 'Gagnée', 'Perdue']) {
    await page.getByRole('button', { name: s }).click();
    await expect(page.locator('.head .st')).toHaveText(s);
  }
  await page.getByLabel('Attribuer à').selectOption({ label: 'Karim Benali, Équipe' });
  await page.getByRole('button', { name: 'Attribuer', exact: true }).click();
  await expect(page.locator('#h-o + p')).toHaveText('Karim Benali, Équipe');
  await page.getByLabel('Visible uniquement par l’équipe').fill('Client rappelé, préfère un vol direct.');
  await page.getByRole('button', { name: 'Ajouter la note' }).click();
  await expect(page.locator('.ok')).toHaveText('Note ajoutée à l’historique.'); // wait for the reloaded page, never read mid-navigation
  const hist = page.locator('.hist li');
  const lines = await hist.allTextContents();
  const joined = lines.join('\n');
  expect(joined).toContain('Demande reçue depuis le site');
  expect(joined).toContain('Statut : Nouvelle vers Qualifiée');
  expect(joined).toContain('Statut : Qualifiée vers Devis envoyé');
  expect(joined).toContain('Statut : Devis envoyé vers Gagnée');
  expect(joined).toContain('Statut : Gagnée vers Perdue');
  expect(joined).toContain('Responsable : aucun vers Karim Benali, Équipe');
  expect(joined).toContain('Client rappelé, préfère un vol direct.');
  for (const l of lines.slice(1)) { expect(l).toContain('Karim Benali, Équipe'); expect(l).toMatch(/\d{2}\/\d{2}\/\d{4} \d{2}:\d{2}/); }
  // no edit or delete control on history; the database refuses updates
  expect(await page.locator('#historique button, #historique form, #historique input').count()).toBe(0);
  // re-sending the same status is a no-op (idempotent), not a new history line
  const csrf = await csrfOf(page);
  const id = page.url().match(/demandes\/(\d+)/)[1];
  const origin = new URL(page.url()).origin;
  await page.request.post(`/console/demandes/${id}`, { form: { _csrf: csrf, action: 'status', to: 'perdue' }, headers: { origin } });
  await page.reload();
  expect(await page.locator('.hist li').count()).toBe(lines.length);
  // unknown status / unknown owner rejected
  const bad = await page.request.post(`/console/demandes/${id}`, { form: { _csrf: csrf, action: 'status', to: 'supprimee' }, headers: { origin } });
  expect(await bad.text()).toContain('Statut inconnu');
  const badOwner = await page.request.post(`/console/demandes/${id}`, { form: { _csrf: csrf, action: 'owner', owner: '3' }, headers: { origin } });
  expect(await badOwner.text()).toContain('Responsable inconnu');
});

test('S4-F5 CSV export holds the enquiries and neutralises =, +, - and @ at the start of a cell', async () => {
  const page = shared.page;
  // enquiries whose name starts with each dangerous character
  const v = page;
  const names = ['=cmd|\' /C calc\'!A0', '+SUM(1;2)', '-2+3', '@SUM(A1)'];
  for (const n of names) {
    await v.goto(`/congres/${SLUG.cardio}`);
    await fillEnquiry(v, { name: n, city: n });
    await v.waitForTimeout(3100);
    await v.getByRole('button', { name: 'Envoyer la demande' }).click();
    await expect(v.locator('[data-ref]')).toBeVisible();
  }
  await login(page, 'equipe');
  await page.goto('/console/demandes');
  const [dl] = await Promise.all([page.waitForEvent('download'), page.getByRole('link', { name: /Exporter/ }).click()]);
  const csv = await (await import('node:fs/promises')).readFile(await dl.path(), 'utf8');
  expect(dl.suggestedFilename()).toMatch(/^demandes-\d{4}-\d{2}-\d{2}\.csv$/);
  expect(csv.charCodeAt(0)).toBe(0xfeff);
  const rows = csv.trim().split('\r\n');
  expect(rows[0]).toContain('"Référence";"Reçue le";"Congrès"');
  expect(rows.length).toBe(1 + 11); // 6 seeded + 1 from beforeAll + 4 above
  for (const n of names) {
    expect(csv).toContain(`"'${n.replace(/"/g, '""')}"`);
    expect(csv).not.toMatch(new RegExp(`(^|;)"${n.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`, 'm'));
  }
  expect(csv).toContain('DV-2026-0001');
});

test('S4-F6 enquiries are never public: catalogue, search, sitemap, feeds, API routes', async ({ request }) => {
  const urls = ['/', '/?q=sophie', '/?q=DV-2026', '/?q=bernard', `/congres/${SLUG.radio}`, '/sitemap.xml', '/feed', '/rss', '/api/enquiries', '/api/demandes', '/demandes', '/console/demandes/export.csv', '/demande/confirmation?ref=DV-2026-0001', '/robots.txt'];
  for (const u of urls) {
    const res = await request.get(u, { maxRedirects: 0 });
    const t = await res.text();
    for (const leak of ['Sophie Bernard', 'sophie.bernard@example.com', 'Camille Laurent', 'camille.laurent@example.com', 'DV-2026-0001', REF]) expect(t, `${u} leaks ${leak}`).not.toContain(leak);
  }
});

test('S4-H1 logged-out and contributor users cannot read or change enquiries (direct URL and POST refused)', async ({ page, request }) => {
  for (const u of ['/console/demandes', '/console/demandes/1', '/console/demandes/export.csv', '/console/notifications']) {
    const r = await request.get(u, { maxRedirects: 0 });
    expect(r.status(), u).toBe(303);
    expect(r.headers().location).toContain('/console/connexion');
  }
  const anonPost = await request.post('/console/demandes/1', { form: { action: 'status', to: 'gagnee' }, maxRedirects: 0 });
  expect(anonPost.status()).toBe(401);
  await login(page, 'contributeur');
  await expect(page.getByRole('navigation', { name: 'Console' }).getByRole('link', { name: /Demandes/ })).toHaveCount(0);
  for (const u of ['/console/demandes', '/console/demandes/1', '/console/demandes/export.csv', '/console/notifications']) {
    const r = await page.request.get(u, { maxRedirects: 0 });
    expect(r.status(), u).toBe(403);
    expect(await r.text()).not.toContain('Camille Laurent');
  }
  const csrf = await csrfOf(page);
  const post = await page.request.post('/console/demandes/1', { form: { _csrf: csrf, action: 'status', to: 'perdue' }, headers: { origin: new URL(page.url()).origin } });
  expect(post.status()).toBe(403);
  await logout(page);
  await login(page, 'equipe');
  await page.goto('/console/demandes/1');
  await expect(page.locator('.head .st')).toHaveText('Gagnée');
});
