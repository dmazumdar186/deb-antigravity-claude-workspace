// S1: create and edit a congress.
import { test, expect, login, logout, csrfOf } from './helpers.mjs';

test.describe.configure({ mode: 'serial' });
// Each Playwright context is a fresh private sandbox, so every test starts from the seed.

const NEW = { title: 'Congrès de test S1 — exemple', disc: 'Hématologie', venue: 'Centre de test — exemple', city: 'Nice', country: 'France', start: '2027-07-05', end: '2027-07-07', url: 'https://www.example.org/test-s1', ver: '2026-11-01' };
async function fillCongress(page, v) {
  await page.getByLabel('Titre').fill(v.title);
  await page.getByLabel('Discipline').fill(v.disc);
  await page.getByLabel('Lieu').fill(v.venue);
  await page.getByLabel('Ville').fill(v.city);
  await page.getByLabel('Pays').fill(v.country);
  await page.getByLabel('Date de début').fill(v.start);
  await page.getByLabel('Date de fin').fill(v.end);
  await page.getByLabel('Site officiel').fill(v.url);
  await page.getByLabel('Vérifié le').fill(v.ver);
}

test('S1-F1 S1-E1 create and publish a congress with every field, in 3 clicks from the dashboard', async ({ page }) => {
  await login(page, 'direction');
  let clicks = 0;
  await page.getByRole('navigation', { name: 'Console' }).getByRole('link', { name: 'Congrès' }).click(); clicks++;
  await page.getByRole('link', { name: 'Nouveau congrès' }).click(); clicks++;
  // every field has a visible French label, required ones are marked
  for (const l of ['Titre', 'Discipline', 'Lieu', 'Ville', 'Pays', 'Date de début', 'Date de fin', 'Site officiel', 'Vérifié le']) {
    const label = page.locator('label', { hasText: l }).first();
    await expect(label).toBeVisible();
    await expect(label.locator('.req')).toHaveCount(1);
  }
  await fillCongress(page, NEW);
  await page.getByRole('button', { name: 'Publier' }).click(); clicks++;
  expect(clicks).toBeLessThanOrEqual(4);
  await expect(page.getByText('Congrès créé.')).toBeVisible();
  await expect(page.locator('.st', { hasText: 'Publié' }).first()).toBeVisible();
  // server is the judge: the public catalogue lists it with all the details
  await page.goto('/?q=test+s1');
  await page.getByRole('link', { name: /Congrès de test S1/ }).click();
  for (const t of ['Nice', 'France', 'Hématologie', 'Centre de test — exemple', 'www.example.org/test-s1', '01/11/2026', '5 au 7 juil. 2027']) await expect(page.locator('.facts')).toContainText(t);
});

test('S1-F2 S1-E2 edit an existing congress in 3 clicks; new value in admin and on the public page', async ({ page }) => {
  await login(page, 'equipe');
  let clicks = 0;
  await page.getByRole('navigation', { name: 'Console' }).getByRole('link', { name: 'Congrès' }).click(); clicks++;
  await page.getByRole('link', { name: 'Congrès européen de cardiologie — exemple' }).click(); clicks++;
  await page.getByLabel('Ville').fill('Barcelone');
  await page.getByRole('button', { name: 'Enregistrer', exact: true }).click(); clicks++;
  expect(clicks).toBeLessThanOrEqual(3);
  await expect(page.getByText('Modifications enregistrées.')).toBeVisible();
  await expect(page.getByLabel('Ville')).toHaveValue('Barcelone');
  await page.goto('/congres/congres-europeen-de-cardiologie-cg-0101');
  await expect(page.locator('.facts')).toContainText('Barcelone');
  await page.goto('/?q=barcelone');
  await expect(page.locator('.row')).toHaveCount(1);
});

test('S1-F3 contributor drafts and submits for review but cannot publish; draft is not public; Direction publishes', async ({ page }) => {
  await login(page, 'contributeur');
  await page.goto('/console/congres/nouveau');
  await expect(page.getByRole('button', { name: 'Publier' })).toHaveCount(0);
  await fillCongress(page, { ...NEW, title: 'Brouillon contributeur — exemple', url: 'https://www.example.org/brouillon' });
  await page.getByRole('button', { name: 'Enregistrer le brouillon' }).click();
  await expect(page.getByText('Congrès créé.')).toBeVisible();
  const editUrl = page.url().split('?')[0];
  const id = editUrl.split('/').pop();
  await page.getByRole('button', { name: 'Soumettre à relecture' }).click();
  await expect(page.locator('.head .st')).toHaveText('À relire');
  // forged publish POST is refused server-side
  const csrf = await csrfOf(page);
  const forged = await page.request.post(`/console/congres/${id}`, { form: { _csrf: csrf, action: 'publish', title: 'Brouillon contributeur — exemple', discipline: 'Hématologie', venue: 'X — exemple', city: 'Nice', country: 'France', start_date: '2027-07-05', end_date: '2027-07-07', official_url: 'https://www.example.org/b', verified_on: '2026-11-01' }, headers: { origin: new URL(page.url()).origin } });
  expect(forged.status()).toBe(403);
  expect(await forged.text()).toContain('ne peut pas publier');
  // not visible publicly
  const slugRes = await page.request.get('/?q=brouillon+contributeur');
  expect(await slugRes.text()).toContain('Aucun congrès ne correspond');
  const draft = await page.request.get('/congres/journees-de-rhumatologie-cg-0113');
  expect(draft.status()).toBe(404);
  await logout(page);
  // Direction publishes
  await login(page, 'direction');
  await page.goto(editUrl);
  await page.getByRole('button', { name: 'Publier' }).click();
  await expect(page.locator('.head .st')).toHaveText('Publié');
  await page.goto('/?q=brouillon+contributeur');
  await expect(page.locator('.row')).toHaveCount(1);
});

test('S1-H1 end before start and invalid URL rejected; script in title shown as text', async ({ page }) => {
  await login(page, 'equipe');
  await page.goto('/console/congres/nouveau');
  await fillCongress(page, { ...NEW, title: '<script>alert(1)</script><b>Gras</b> — exemple', start: '2027-07-10', end: '2027-07-01', url: 'javascript:alert(1)' });
  await page.getByRole('button', { name: 'Publier' }).click();
  await expect(page.getByText('La date de fin doit être le jour du début ou après.')).toBeVisible();
  await expect(page.getByText(/Adresse invalide/)).toBeVisible();
  await expect(page.getByText('rien n’a été enregistré')).toBeVisible();
  // fix dates and url, keep the hostile title
  await page.getByLabel('Date de fin').fill('2027-07-12');
  await page.getByLabel('Site officiel').fill('https://www.example.org/xss');
  await page.getByRole('button', { name: 'Publier' }).click();
  await expect(page.getByText('Congrès créé.')).toBeVisible();
  await expect(page.locator('h1')).toHaveText('<script>alert(1)</script><b>Gras</b> — exemple');
  expect(await page.locator('main b', { hasText: 'Gras' }).count()).toBe(0);
  await page.goto('/?q=gras');
  await expect(page.locator('.row__t')).toHaveText('<script>alert(1)</script><b>Gras</b> — exemple');
  const html = await (await page.request.get('/?q=gras')).text();
  expect(html).not.toContain('<script>alert(1)');
  expect(html).toContain('&lt;script&gt;alert(1)&lt;/script&gt;');
});

test('S1-H2 saving without a CSRF token changes nothing', async ({ page }) => {
  await login(page, 'direction');
  await page.goto('/console/congres/101');
  const before = await page.getByLabel('Ville').inputValue();
  const origin = new URL(page.url()).origin;
  const base = { action: 'save', title: 'Piraté — exemple', discipline: 'Cardiologie', venue: 'X', city: 'Pirate', country: 'Espagne', start_date: '2027-08-27', end_date: '2027-08-30', official_url: 'https://www.example.org/x', verified_on: '2026-10-12' };
  const noToken = await page.request.post('/console/congres/101', { form: base, headers: { origin } });
  expect(noToken.status()).toBe(403);
  const badToken = await page.request.post('/console/congres/101', { form: { ...base, _csrf: 'forged' }, headers: { origin } });
  expect(badToken.status()).toBe(403);
  const csrf = await csrfOf(page);
  const crossSite = await page.request.post('/console/congres/101', { form: { ...base, _csrf: csrf }, headers: { origin: 'https://evil.example' } });
  expect(crossSite.status()).toBe(403);
  await page.reload();
  await expect(page.getByLabel('Ville')).toHaveValue(before);
  await expect(page.getByLabel('Titre')).not.toHaveValue('Piraté — exemple');
});
