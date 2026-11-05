// S2: public catalogue, search, filters, details page.
import { test, expect, login, logout, SLUG, CTX } from './helpers.mjs';

test.describe.configure({ mode: 'serial' });
// Each Playwright context is a fresh private sandbox, so every test starts from the seed.

const SEEDED = ['CG-0101', 'CG-0102', 'CG-0103', 'CG-0104', 'CG-0105', 'CG-0106', 'CG-0107', 'CG-0108', 'CG-0109', 'CG-0110', 'CG-0111', 'CG-0112'];

test('S2-F1 all 12 published upcoming congresses listed; past and draft ones are not', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('.bar__n')).toHaveText('12 congrès');
  const hrefs = [];
  for (const p of [1, 2]) {
    await page.goto(p === 1 ? '/' : '/?page=2');
    hrefs.push(...await page.locator('.row__a').evaluateAll((as) => as.map((a) => a.getAttribute('href'))));
  }
  expect(hrefs).toHaveLength(12);
  for (const ref of SEEDED) expect(hrefs.some((h) => h.endsWith(ref.toLowerCase()))).toBeTruthy();
  expect(hrefs.some((h) => h.endsWith('cg-0113'))).toBeFalsy(); // seeded draft
  // a past published congress (created through the console, in this same browser's sandbox) is hidden
  const admin = page;
  await login(admin, 'direction');
  await admin.goto('/console/congres/nouveau');
  await admin.getByLabel('Titre').fill('Congrès passé — exemple');
  await admin.getByLabel('Discipline').fill('Cardiologie');
  await admin.getByLabel('Lieu').fill('Salle — exemple');
  await admin.getByLabel('Ville').fill('Rome');
  await admin.getByLabel('Pays').fill('Italie');
  await admin.getByLabel('Date de début').fill('2026-03-01');
  await admin.getByLabel('Date de fin').fill('2026-03-03');
  await admin.getByLabel('Site officiel').fill('https://www.example.org/passe');
  await admin.getByLabel('Vérifié le').fill('2026-02-01');
  await admin.getByRole('button', { name: 'Publier' }).click();
  await expect(admin.getByText('Congrès créé.')).toBeVisible();
  await logout(admin);
  await page.goto('/?q=passe');
  await expect(page.locator('.row')).toHaveCount(0);
  await page.goto('/');
  await expect(page.locator('.bar__n')).toHaveText('12 congrès');
});

test('S2-F2 keyword search on title, city and discipline, accent-insensitive', async ({ page }) => {
  const cases = [['vienne', ['CG-0104', 'CG-0108']], ['diabetologie', ['CG-0103']], ['DIABÉTOLOGIE', ['CG-0103']], ['marseille', ['CG-0112']], ['oncologie', ['CG-0102', 'CG-0112']], ['sommet rh', ['CG-0109']], ['zzzz', []]];
  for (const [q, refs] of cases) {
    await page.goto('/');
    await page.getByLabel('Recherche').fill(q);
    await page.getByRole('button', { name: 'Rechercher' }).click();
    const got = await page.locator('.row__a').evaluateAll((as) => as.map((a) => a.getAttribute('href').slice(-7).toUpperCase()));
    expect(got.sort(), `query ${q}`).toEqual(refs.sort());
  }
});

test('S2-F3 discipline, country and month filters alone and combined, count shown, no-result message and reset', async ({ page }) => {
  await page.goto('/');
  await page.locator('.chips').getByRole('link', { name: 'Cardiologie' }).click();
  await expect(page.locator('.bar__n')).toHaveText('2 congrès trouvés');
  await page.waitForLoadState('load'); // the enhancement script that auto-submits is loaded (without it, the Rechercher button does the same)
  await page.getByLabel('Pays').selectOption('Espagne'); // auto-submits
  await expect(page).toHaveURL(/pays=Espagne/);
  await expect(page.locator('.bar__n')).toHaveText('1 congrès trouvé');
  await expect(page.locator('.row__t')).toHaveText('Congrès européen de cardiologie — exemple');
  await page.goto('/');
  await page.getByLabel('Mois').selectOption('2027-09');
  await expect(page.locator('.bar__n')).toHaveText('2 congrès trouvés'); // Amsterdam 29 sept, Milan 4 sept
  await page.goto('/');
  await page.getByLabel('Pays').selectOption('Autriche');
  await expect(page.locator('.bar__n')).toHaveText('2 congrès trouvés');
  await page.waitForLoadState('load');
  await page.getByLabel('Mois').selectOption('2027-06');
  await expect(page.locator('.bar__n')).toHaveText('1 congrès trouvé');
  await page.locator('.chips').getByRole('link', { name: 'Oncologie' }).click();
  await expect(page.locator('.bar__n')).toHaveText('Aucun congrès trouvé');
  await expect(page.getByRole('heading', { name: 'Aucun congrès ne correspond.' })).toBeVisible();
  await page.getByRole('link', { name: 'Réinitialiser la recherche' }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.locator('.bar__n')).toHaveText('12 congrès');
});

test('S2-F4 pagination (9 per page) keeps the active filters', async ({ page }) => {
  await page.goto('/?q=exemple');
  await expect(page.locator('.row')).toHaveCount(9);
  await page.getByRole('link', { name: 'Page suivante' }).click();
  await expect(page).toHaveURL(/q=exemple/);
  await expect(page).toHaveURL(/page=2/);
  await expect(page.locator('.row')).toHaveCount(3);
  await expect(page.getByLabel('Recherche')).toHaveValue('exemple');
  // date order across pages
  const p2 = await page.locator('.row__a').evaluateAll((as) => as.map((a) => a.getAttribute('href').slice(-7)));
  expect(p2).toEqual(['cg-0102', 'cg-0111', 'cg-0110']);
});

test('S2-F5 details page shows every fact and the enquiry form prefilled with this congress', async ({ page }) => {
  await page.goto(`/congres/${SLUG.cardio}`);
  await expect(page.locator('h1')).toHaveText('Congrès européen de cardiologie — exemple');
  const facts = page.locator('.facts');
  for (const [k, v] of [['Dates', '27 au 30 août 2027'], ['Ville', 'Madrid'], ['Pays', 'Espagne'], ['Discipline', 'Cardiologie'], ['Lieu', 'Centre de congrès de Madrid — exemple'], ['Site officiel', 'www.example.org/congres/cg-0101'], ['Vérifié le', '12/10/2026']]) {
    await expect(facts.locator('div', { has: page.locator('dt', { hasText: new RegExp(`^${k}$`) }) }).locator('dd')).toContainText(v);
  }
  await expect(page.locator('[data-congress]')).toHaveText(/Congrès européen de cardiologie\s— exemple, 27 au 30 août 2027/);
  await expect(page.locator('input[name="congress"]')).toHaveValue('101');
  // GM&E mention only when approved: CG-0101 code is only « Détecté »
  await expect(page.locator('.gme-note')).toHaveCount(0);
});

test('S2-F6 works with JavaScript off (server-rendered GET form)', async ({ browser }) => {
  const ctx = await browser.newContext({ ...CTX, javaScriptEnabled: false });
  const page = await ctx.newPage();
  await page.goto('/');
  await page.getByLabel('Recherche').fill('lyon');
  await page.getByLabel('Pays').selectOption('France');
  await page.getByRole('button', { name: 'Rechercher' }).click();
  await expect(page).toHaveURL(/q=lyon/);
  await expect(page.locator('.bar__n')).toHaveText('1 congrès trouvé');
  await page.locator('.row__a').first().click();
  await expect(page.locator('h1')).toHaveText('Journées françaises de diabétologie — exemple');
  await expect(page.locator('form[action="/demande"]')).toBeVisible();
  await ctx.close();
});

test('S2-E1 find Cardiologie congresses and open one in 2 clicks', async ({ page }) => {
  await page.goto('/');
  let clicks = 0;
  await page.locator('.chips').getByRole('link', { name: 'Cardiologie' }).click(); clicks++;
  await page.locator('.row__a').first().click(); clicks++;
  expect(clicks).toBeLessThanOrEqual(2);
  await expect(page.locator('.facts')).toContainText('Cardiologie');
});

test('S2-E2 at 390 px: no horizontal scroll, inputs at least 16 px, tap targets at least 44 px', async ({ browser }) => {
  const ctx = await browser.newContext({ ...CTX, viewport: { width: 390, height: 844 }, deviceScaleFactor: 1, isMobile: true, hasTouch: true });
  const page = await ctx.newPage();
  for (const url of ['/', '/?q=zzz', '/?page=2', `/congres/${SLUG.onco}`, `/congres/${SLUG.cardio}`, '/console/connexion', '/page-inconnue']) {
    await page.goto(url);
    const r = await page.evaluate(() => {
      const de = document.documentElement;
      const bad = [];
      const small = [];
      document.querySelectorAll('input:not([type=hidden]),select,textarea').forEach((el) => {
        const fs = parseFloat(getComputedStyle(el).fontSize);
        if (fs < 16) small.push(el.name || el.id);
      });
      document.querySelectorAll('a,button,select,input:not([type=hidden]),textarea,summary').forEach((el) => {
        const b = el.getBoundingClientRect();
        if (!b.width || !b.height || b.right < 0 || b.left > innerWidth || el.closest('.skip,.hp')) return;
        if (el.type === 'checkbox') { const l = el.closest('label'); const lb = l.getBoundingClientRect(); if (lb.height < 44) bad.push('label ' + el.id); return; }
        if (b.height < 44 || b.width < 44) bad.push(`${el.tagName} ${(el.textContent || el.name || '').trim().slice(0, 30)} ${Math.round(b.width)}x${Math.round(b.height)}`);
      });
      return { overflow: de.scrollWidth - de.clientWidth, bodyOverflow: document.body.scrollWidth - innerWidth, bad, small };
    });
    expect(r.overflow, `${url} horizontal overflow`).toBeLessThanOrEqual(0);
    expect(r.bodyOverflow, `${url} body overflow`).toBeLessThanOrEqual(0);
    expect(r.small, `${url} inputs under 16px`).toEqual([]);
    expect(r.bad, `${url} tap targets under 44px`).toEqual([]);
  }
  await ctx.close();
});

test('S2-H1 script in the search box is escaped; a 5,000-character query does not error; SQL-ish input is inert', async ({ page }) => {
  let dialogs = 0;
  page.on('dialog', () => { dialogs++; });
  await page.goto('/?q=' + encodeURIComponent('<script>alert(1)</script>"><img src=x onerror=alert(2)>'));
  await expect(page.getByLabel('Recherche')).toHaveValue(/<script>alert\(1\)/);
  const body = await (await page.request.get('/?q=' + encodeURIComponent('<script>alert(1)</script>'))).text();
  expect(body).not.toContain('<script>alert(1)');
  const long = await page.request.get('/?q=' + 'a'.repeat(5000));
  expect(long.status()).toBe(200);
  const sql = await page.request.get('/?q=' + encodeURIComponent("' OR 1=1 --") + '&pays=' + encodeURIComponent("x' OR '1'='1") + '&page=' + encodeURIComponent('1;DROP TABLE congresses'));
  expect(sql.status()).toBe(200);
  expect(await sql.text()).toContain('Aucun congrès trouvé');
  await page.goto('/');
  await expect(page.locator('.bar__n')).toHaveText('12 congrès');
  expect(dialogs).toBe(0);
});
