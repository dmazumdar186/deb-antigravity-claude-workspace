// Client-eye gate (qa/register/CLIENT_EYE.md, Option B rows): one regression test per REAL finding (CE-…).
import { test, expect, login, logout, newPage, assertClean, sbxOf, d1Count, LIVE, ROOT, SLUG, csrfOf, TEST_KEY } from './helpers.mjs';
import { execFileSync } from 'node:child_process';
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { d1Args } from './helpers.mjs';

const EXPIRED = 'Votre session a expiré. Reconnectez-vous.';
const nav = (page) => page.getByRole('navigation', { name: 'Console' });
const d1Exec = (sql) => execFileSync('npx', d1Args('--command', sql), { cwd: ROOT, stdio: 'ignore' });
const dropSession = async (ctx) => {
  const keep = (await ctx.cookies()).filter((c) => c.name !== '__Host-av_session');
  await ctx.clearCookies();
  await ctx.addCookies(keep);
};
async function signIn(page, user) {
  await page.getByLabel('Identifiant').fill(user);
  await page.getByLabel('Mot de passe').fill('demo-asset');
  await page.getByRole('button', { name: 'Se connecter' }).click();
}

// ---------------------------------------------------------------- C7: sessions and the nightly purge
test('CE-C7-005 session gone (cookie expired): the next click lands on the login page with « Votre session a expiré », then back to the page', async ({ page }) => {
  await login(page, 'equipe');
  await page.goto('/console/demandes/6');
  await dropSession(page.context());
  await page.goto('/console/demandes/6');
  await expect(page).toHaveURL(/\/console\/connexion\?expire=1&next=%2Fconsole%2Fdemandes%2F6/);
  await expect(page.locator('.alert')).toHaveText(EXPIRED);
  await signIn(page, 'equipe');
  await expect(page).toHaveURL(/\/console\/demandes\/6$/);
});

test('CE-C7-004 a form sent from an open tab after the session ended shows « Votre session a expiré » and writes nothing', async ({ page }) => {
  await login(page, 'equipe');
  await page.goto('/console/demandes/6');
  await dropSession(page.context());
  await page.getByLabel('Visible uniquement par l’équipe').fill('Note tapée après la fin de session.');
  await page.getByRole('button', { name: 'Ajouter la note' }).click();
  await expect(page).toHaveURL(/\/console\/connexion\?expire=1/);
  await expect(page.locator('.alert')).toHaveText(EXPIRED);
  await signIn(page, 'equipe');
  await expect(page).toHaveURL(/\/console\/demandes\/6$/); // back to the page the form was on
  await expect(page.locator('main')).not.toContainText('Note tapée après la fin de session.');
});

test('CE-C7-004 an invalid (tampered) session cookie also shows the expiry message; a first visit and a logout do not', async ({ browser }) => {
  const P = await newPage(browser);
  await P.page.goto('/console/demandes'); // never signed in: plain login page
  await expect(P.page).toHaveURL(/\/console\/connexion\?next=/);
  await expect(P.page.locator('.alert')).toHaveCount(0);
  const forged = await P.page.request.get('/console/demandes', { headers: { cookie: '__Host-av_session=abc.def' }, maxRedirects: 0 });
  expect(forged.status()).toBe(303);
  expect(forged.headers().location).toBe('/console/connexion?expire=1&next=%2Fconsole%2Fdemandes');
  await P.page.goto(forged.headers().location);
  await expect(P.page.locator('.alert')).toHaveText(EXPIRED);
  await login(P.page, 'direction');
  await logout(P.page);
  await expect(P.page.getByText('Vous êtes déconnecté.')).toBeVisible();
  await P.page.goto('/console/demandes');
  await expect(P.page.locator('.alert')).toHaveCount(0); // a deliberate logout is not an expiry
  assertClean(P.problems); await P.ctx.close();
});

test('CE-C7-006 the 03:00 purge deletes sandboxes IDLE for more than 24 h, not those CREATED more than 24 h ago', async ({ page, browser }) => {
  test.skip(LIVE, 'the scheduled handler can only be triggered on the local runtime');
  await login(page, 'equipe');
  await page.goto('/console/demandes/1');
  await page.getByRole('button', { name: 'Perdue' }).click();
  const oldButActive = await sbxOf(page);
  const I = await newPage(browser);
  await login(I.page, 'equipe');
  await I.page.goto('/console/demandes/1');
  await I.page.getByRole('button', { name: 'Qualifiée' }).click();
  const idle = await sbxOf(I.page);
  const now = new Date().toISOString();
  d1Exec(`UPDATE sandboxes SET created_at = '2026-01-01T00:00:00.000Z', last_seen = '${now}' WHERE id = '${oldButActive}'; UPDATE sandboxes SET last_seen = '2026-01-01T00:00:00.000Z' WHERE id = '${idle}'`);
  expect((await page.request.get('/cdn-cgi/handler/scheduled?cron=0+3+*+*+*')).status()).toBe(200);
  await expect.poll(() => d1Count(`SELECT COUNT(*) AS n FROM sandboxes WHERE id = '${idle}'`)[0].n).toBe(0);
  expect(d1Count(`SELECT COUNT(*) AS n FROM enquiries WHERE sbx = '${idle}'`)[0].n).toBe(0);
  expect(d1Count(`SELECT COUNT(*) AS n FROM sandboxes WHERE id = '${oldButActive}'`)[0].n).toBe(1); // a trial in use at 03:00 survives
  await page.goto('/console/demandes/1');
  await expect(page.locator('.head .st')).toHaveText('Perdue');
  assertClean(I.problems); await I.ctx.close();
});

test('CE-C7-006 activity is tracked cheaply: at most one write per sandbox per hour', async ({ page }) => {
  test.skip(LIVE || !TEST_KEY, 'needs the local D1 and the test-key write meter');
  await login(page, 'equipe');
  await page.goto('/console/demandes/1');
  await page.getByRole('button', { name: 'Perdue' }).click();
  const sbx = await sbxOf(page);
  const seen = () => d1Count(`SELECT last_seen FROM sandboxes WHERE id = '${sbx}'`)[0].last_seen;
  const first = seen();
  for (let i = 0; i < 3; i++) expect((await page.request.get('/')).headers()['x-d1-rows-written']).toBe('0'); // fresh: no write
  expect(seen()).toBe(first);
  const twoHoursAgo = new Date(Date.now() - 2 * 3600 * 1000).toISOString();
  d1Exec(`UPDATE sandboxes SET last_seen = '${twoHoursAgo}' WHERE id = '${sbx}'`);
  expect((await page.request.get('/')).headers()['x-d1-rows-written']).toBe('1'); // one refresh
  expect(seen() > twoHoursAgo).toBe(true);
  expect((await page.request.get('/')).headers()['x-d1-rows-written']).toBe('0'); // and no second one within the hour
});

// ---------------------------------------------------------------- B2: « today » is the Paris date
test('CE-B2-002 at 00:05 Paris every « today » is the Paris date (lib, enquiry and traveller validation, link expiry)', async () => {
  const RealDate = Date;
  const AT = RealDate.parse('2026-11-06T23:05:00Z'); // 7 Nov 2026, 00:05 in Paris
  class FakeDate extends RealDate { constructor(...a) { super(...(a.length ? a : [AT])); } static now() { return AT; } }
  globalThis.Date = FakeDate;
  try {
    const lib = await import('../src/lib.js');
    const pub = await import('../src/public.js');
    const grp = await import('../src/group.js');
    expect(lib.parisToday()).toBe('2026-11-07');
    expect(lib.today()).toBe('2026-11-07');
    const form = (o) => (k) => ({ name: 'A (exemple)', email: 'a@example.com', phone: '01 99 00 00 01', departure_city: 'Lille', date_back: '2027-01-10', passengers: '2', consent: '1', ...o })[k] ?? '';
    expect(pub.validateEnquiry(form({ date_out: '2026-11-06' })).e.date_out).toBe('La date aller ne peut pas être passée.');
    expect(pub.validateEnquiry(form({ date_out: '2026-11-07' })).e.date_out).toBeUndefined();
    expect(grp.linkExpiry()).toBe(`${lib.addDays('2026-11-07', grp.LINK_DAYS)}T23:59:59Z`);
    expect(pub.gmeOnSale({ gme_status: 'approuve', gme_from: '2026-11-07', gme_to: null })).toBe(true);
  } finally { globalThis.Date = RealDate; }
  // No user-facing code path calls a UTC « today » any more (utcDay is the D1 quota day, UTC by definition).
  const src = join(ROOT, 'src');
  for (const f of readdirSync(src)) {
    const lines = readFileSync(join(src, f), 'utf8').split('\n');
    lines.forEach((l, i) => { if (/\btoday\(\)/.test(l) && !/^\s*\/\//.test(l)) throw new Error(`${f}:${i + 1} calls today(): ${l.trim()}`); });
  }
});

test('CE-B2-002 both CSV file names carry the Paris date', async ({ page }) => {
  await login(page, 'equipe');
  const paris = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Paris', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
  const a = await page.request.get('/console/demandes/export.csv');
  expect(a.headers()['content-disposition']).toContain(`demandes-${paris}.csv`);
  const b = await page.request.get('/console/demandes/1/groupe.csv');
  expect(b.headers()['content-disposition']).toContain(`-${paris}.csv`);
});

// ---------------------------------------------------------------- B6 and C10: glossary labels
test('CE-B6-001…008 the console and the public form use the glossary labels (29_Glossary_Labels.md) and no old variant', async ({ page }) => {
  const OLD = ['Nouveau congrès', 'Notifications', 'Demande de devis vol', 'Envoyer la demande', 'Révéler le code', 'Journal', 'Journal d’accès', 'Exporter (tableur CSV)', 'Exporter', 'Ajouter', 'Approuver'];
  const noOld = async () => {
    const texts = await page.locator('h1, h2, h3, a, button, summary, label').allInnerTexts();
    for (const t of texts.map((x) => x.trim())) expect(OLD, `old label « ${t} » on ${page.url()}`).not.toContain(t);
  };
  await page.goto(`/congres/${SLUG.onco}`);
  await expect(page.getByRole('heading', { name: 'Demander un devis vol', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Envoyer ma demande', exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Espace équipe', exact: true }).first()).toBeVisible();
  await noOld();
  await login(page, 'direction');
  await expect(nav(page).getByRole('link', { name: 'Journal des notifications', exact: true })).toBeVisible();
  await expect(nav(page).getByRole('link', { name: 'Codes GM&E', exact: true })).toBeVisible();
  await expect(nav(page).getByRole('link', { name: 'Codes', exact: true })).toBeVisible();
  await expect(nav(page).getByRole('link', { name: 'Journal d’accès GM&E', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Réinitialiser la démo', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Se déconnecter', exact: true })).toBeVisible();
  await noOld();
  for (const [url, check] of [
    ['/console/congres', () => page.getByRole('link', { name: 'Ajouter un congrès', exact: true })],
    ['/console/congres/nouveau', () => page.getByRole('heading', { name: 'Ajouter un congrès', exact: true })],
    ['/console/demandes', () => page.getByRole('link', { name: 'Exporter en CSV', exact: true })],
    ['/console/notifications', () => page.getByRole('heading', { name: 'Journal des notifications', exact: true, level: 1 })],
    ['/console/gme/acces', () => page.getByRole('button', { name: 'Approuver pour 24 h', exact: true })],
    ['/console/gme/journal', () => page.getByRole('heading', { name: 'Journal d’accès GM&E', exact: true, level: 1 })],
    ['/console/gme', () => page.getByRole('button', { name: 'Afficher le code', exact: true }).first()],
    ['/console/demandes/1', () => page.getByRole('heading', { name: 'Lien de groupe', exact: true })],
  ]) {
    await page.goto(url);
    await expect(check()).toBeVisible();
    await noOld();
  }
  await page.goto('/console/gme');
  await page.locator('.gme', { hasText: 'oncologie digestive' }).getByRole('button', { name: 'Afficher le code' }).click();
  await expect(page.getByRole('link', { name: 'Masquer le code', exact: true })).toBeVisible();
});

test('CE-C10-002 « Codes GM&E » in the console menu is a link that opens the codes (hub B task 5 step 1)', async ({ page }) => {
  await login(page, 'equipe');
  await nav(page).getByRole('link', { name: 'Codes GM&E', exact: true }).click();
  await expect(page).toHaveURL(/\/console\/gme$/);
  await expect(page.locator('h1')).toHaveText('Codes GM&E');
  await expect(page.locator('.gme', { hasText: 'oncologie digestive' }).getByRole('button', { name: 'Demander l’accès' })).toBeVisible();
});

// ---------------------------------------------------------------- D2 and A4: fictional seed data
test('CE-D2-003 CE-D2-005 the seed has no real congress name and every seeded phone is in the fiction range 01 99 00', async ({ page }) => {
  expect(d1Count(`SELECT v FROM meta WHERE k = 'schema'`)[0].v).toBe('11'); // schema bumped: the seed reloaded
  await page.goto('/');
  const cat = (await page.locator('main').innerText()).normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  const seedTitles = d1Count("SELECT title FROM congresses WHERE sbx = ''").map((r) => r.title.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()).join(' | ');
  for (const real of ['congres europeen de radiologie', 'congres mondial de neurologie']) { expect(cat).not.toContain(real); expect(seedTitles).not.toContain(real); }
  await expect(page.locator('.row__t', { hasText: 'Rencontres européennes d’imagerie médicale' })).toHaveCount(1);
  await login(page, 'direction');
  await page.goto('/console/notifications');
  const text = await page.locator('main').innerText();
  const phones = text.match(/(?<!\d)0\d(?:[\s.]?\d{2}){4}(?!\d)/g) || [];
  expect(phones.length).toBeGreaterThanOrEqual(6);
  for (const p of phones) expect(p.replace(/\D/g, '')).toMatch(/^019900/);
  expect(text.toLowerCase()).not.toContain('radiologie — exemple');
  for (const id of [1, 6]) {
    await page.goto(`/console/demandes/${id}`);
    await expect(page.locator('main')).toContainText(`01 99 00 00 0${id}`);
  }
});

test('CE-D2-006 the e-mail error gives an @example.com example', async ({ page }) => {
  await page.goto(`/congres/${SLUG.onco}`);
  await page.getByLabel('E-mail').fill('pas-une-adresse');
  await page.getByRole('button', { name: 'Envoyer ma demande' }).click();
  await expect(page.locator('#f-email-e')).toHaveText('Cette adresse e-mail n’est pas valide (exemple : prenom.nom@example.com).');
  expect(await page.content()).not.toContain('societe.fr');
});

test('CE-A4-003 « Site officiel » of a fictional congress is plain text « fictif (démonstration) », never a link to a 404', async ({ page }) => {
  for (const slug of [SLUG.onco, SLUG.radio, SLUG.cardio]) {
    await page.goto(`/congres/${slug}`);
    const row = page.locator('.facts > div', { hasText: 'Site officiel' });
    await expect(row.locator('dd')).toHaveText('fictif (démonstration)');
    await expect(row.locator('a')).toHaveCount(0);
    await expect(page.locator('a[href*="example."]')).toHaveCount(0);
  }
  // a real https address entered by the team is still a link
  await login(page, 'direction');
  await page.goto('/console/congres/101');
  await page.getByLabel('Site officiel').fill('https://www.asset-voyages-congres-demo.fr/programme');
  await page.getByRole('button', { name: 'Enregistrer', exact: true }).click();
  await expect(page.getByText('Modifications enregistrées.')).toBeVisible();
  await page.goto(`/congres/${SLUG.cardio}`);
  await expect(page.locator('.facts a[href="https://www.asset-voyages-congres-demo.fr/programme"]')).toHaveText('www.asset-voyages-congres-demo.fr/programme');
});

// ---------------------------------------------------------------- B4 and C5: layout and type
test('CE-B4-006 the « Lien de groupe » card never starts a line with « : » at 390 px (no-break space before the colon)', async ({ browser }) => {
  const P = await newPage(browser, { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  await login(P.page, 'equipe');
  await P.page.goto('/console/demandes/6');
  const p = P.page.locator('section#lien-groupe > p.quiet').first();
  const t = await p.textContent();
  expect(t).toContain('participants : chacun');
  expect(t).not.toMatch(/ [:;!?]/);
  const lineStarts = await p.evaluate((el) => {
    const n = el.firstChild; const r = document.createRange(); const out = []; let top = null;
    for (let i = 0; i < n.textContent.length; i++) { r.setStart(n, i); r.setEnd(n, i + 1); const rc = r.getClientRects()[0]; if (!rc) continue; if (top === null || rc.top > top + 2) { top = rc.top; out.push(n.textContent[i]); } }
    return out;
  });
  for (const c of lineStarts) expect(':;!?»').not.toContain(c);
  assertClean(P.problems); await P.ctx.close();
});

test('CE-C5-002 the console uses one display family: login heading and notification headings are both EB Garamond', async ({ page }) => {
  const fam = (loc) => loc.evaluate((el) => getComputedStyle(el).fontFamily.split(',')[0].replace(/["']/g, '').trim());
  await page.goto('/console/connexion');
  const loginFam = await fam(page.locator('h1'));
  expect(loginFam).toBe('EB Garamond');
  await signIn(page, 'direction');
  await page.goto('/console/notifications');
  expect(await fam(page.locator('h1'))).toBe(loginFam);
  const hs = page.locator('.mail h2');
  expect(await hs.count()).toBeGreaterThanOrEqual(6);
  for (let i = 0; i < await hs.count(); i++) expect(await fam(hs.nth(i))).toBe(loginFam);
});
