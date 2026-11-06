// Extra « Le lien de groupe » (EXTRA_GROUP.md, ../23_Overdeliver_Idea_Research.md §6).
// Gates: G-F function, G-E ease (clicks), G-H hostile, G-L leak, G-I isolation across browser contexts, G-X cross (Hallmark, 390 px, write cost).
import { test, expect, login, newPage, assertClean, sbxOf, d1Count, LIVE, ROOT, BASE, CODES, CODE_RE, TEST_KEY } from './helpers.mjs';
import { execFileSync } from 'node:child_process';
import { mkdirSync, writeFileSync, rmSync, copyFileSync } from 'node:fs';
import { join } from 'node:path';
import { randomBytes } from 'node:crypto';

test.describe.configure({ mode: 'serial' });
const ORIGIN = new URL(BASE).origin;
const SEED_NAMES = ['Alice Martin', 'alice.martin@example.com', 'Bruno Leroy', 'bruno.leroy@example.com', 'Chloé Petit', 'chloe.petit@example.com'];
// What a public /g/ page must never contain: other delegates, enquiry data, codes, fares, the internal threshold.
const FORBIDDEN = [...SEED_NAMES, ...CODES, 'GM&amp;E', 'GM&E', 'GME', 'DV-2026', 'Camille Laurent', 'Inès Moreau', 'Laboratoire A', 'Société B', 'camille.laurent', 'ines.moreau', '01 23 45 67', 'seuil', 'Seuil', 'répondu', 'attendu', 'tarif', 'Tarif', '/console', 'devis'];
const leakFree = (raw, where) => {
  // random base64url values (the anonymous form token, the sandbox cookie) are not page text
  const text = String(raw).replace(/name="_token" value="[^"]+"/g, '').replace(/__Host-av_sbx=[A-Za-z0-9_-]+/g, '');
  for (const f of FORBIDDEN) expect(text.includes(f), `${where} contains « ${f} »`).toBe(false);
  expect(text, where).not.toMatch(CODE_RE);
};
const randTok = () => randomBytes(32).toString('base64url'); // 43 characters, same alphabet as real tokens
const pathOf = (u) => new URL(u).pathname;

// The link shown in the console (relative path), for enquiry `id` in this browser's sandbox.
async function linkOf(page, id) {
  await page.goto(`/console/demandes/${id}/groupe`);
  return pathOf(await page.locator('[data-group-url]').inputValue());
}
async function createLink(page, id) {
  await page.goto(`/console/demandes/${id}`);
  await page.getByRole('button', { name: /Créer (le|un nouveau) lien/ }).click();
  await expect(page.locator('.ok')).toContainText('Lien créé');
  return pathOf(await page.locator('[data-group-url]').inputValue());
}
async function fillDelegate(page, o = {}) {
  const v = { name: 'Diane Morel (exemple)', email: 'diane.morel@example.com', city: 'Lyon', out: '2027-08-26', back: '2027-08-31', consent: true, ...o };
  await page.getByLabel('Nom et prénom').fill(v.name);
  await page.getByLabel('E-mail').fill(v.email);
  await page.getByLabel('Ville de départ').fill(v.city);
  await page.getByLabel('Date aller').fill(v.out);
  await page.getByLabel('Date retour').fill(v.back);
  if (v.consent) await page.locator('#g-consent').check(); else await page.locator('#g-consent').uncheck();
  return v;
}
// Raw POST with a real form token (hostile inputs a browser would not send). `request` carries its own cookies.
async function postDelegate(request, path, fields, { wait = 3100, token, headers = {} } = {}) {
  let tok = token;
  if (!tok) tok = /name="_token" value="([^"]+)"/.exec(await (await request.get(path, { headers })).text())[1];
  if (wait) await new Promise((r) => setTimeout(r, wait));
  const form = { _token: tok, name: 'Test Hostile (exemple)', email: 'hostile@example.com', departure_city: 'Lille', date_out: '2027-08-26', date_back: '2027-08-31', consent: '1', zx_confirm: '', ...fields };
  for (const k of Object.keys(form)) if (form[k] === undefined) delete form[k];
  const res = await request.post(path, { form, maxRedirects: 0, headers: { origin: ORIGIN, ...headers } });
  return { res, token: tok, text: await res.text() };
}
const counter = (page) => page.locator('[data-counter]');

test('G-F1 seeded group: DV-2026-0001 has a live link, 3 of 6 delegates answered; the panel needs 2+ passengers', async ({ page }) => {
  await login(page, 'equipe');
  await page.goto('/console/demandes/1');
  const card = page.locator('.card', { has: page.getByRole('heading', { name: 'Lien de groupe' }) });
  await expect(card).toBeVisible();
  await expect(card.locator('[data-group-url]')).toHaveValue(new RegExp(`^${ORIGIN}/g/[A-Za-z0-9_-]{43}$`));
  await expect(card).toContainText('Voir le groupe : 3 répondus / 6 attendus');
  await page.getByRole('link', { name: 'Groupe (3/6)' }).click();
  await expect(counter(page)).toHaveText('3 répondus / 6 attendus');
  await expect(page.locator('[data-live] tbody tr')).toHaveCount(3);
  await expect(page.locator('[data-live]')).toContainText('Départs : Lille 2, Paris 1.');
  for (const n of ['Alice Martin (exemple)', 'Bruno Leroy (exemple)', 'Chloé Petit (exemple)']) await expect(page.locator('[data-live]')).toContainText(n);
  await expect(page.getByLabel('Seuil groupe (à confirmer)')).toHaveValue('10');
  await expect(page.locator('[data-hint]')).toHaveCount(0);
  // 1 passenger: no panel, no tab, no route
  await page.goto('/console/demandes/5');
  await expect(page.getByRole('heading', { name: 'Lien de groupe' })).toHaveCount(0);
  await expect(page.getByRole('link', { name: /^Groupe/ })).toHaveCount(0);
  expect((await page.request.get('/console/demandes/5/groupe')).status()).toBe(404);
  // the seed link works on a phone and shows the congress name and dates only
  const link = await linkOf(page, 1);
  const P = await newPage(page.context().browser(), { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  await P.page.goto(link);
  await expect(P.page.locator('[data-congress]')).toHaveText('Journées d’oncologie digestive — exemple');
  await expect(P.page.locator('[data-dates]')).toHaveText('28 au 30 janv. 2027');
  leakFree(await P.page.content(), 'seed link page');
  assertClean(P.problems); await P.ctx.close();
});

test('G-F2 G-E1 G-E2 G-E3 G-I1 create in 2 clicks, delegate on a phone submits in 1 click, manifest in 2 clicks; delegates write into the creator’s sandbox', async ({ page, browser }) => {
  // staff (context A): from the list, open DV-2026-0003 (12 passengers) and create the link
  await login(page, 'equipe');
  await page.goto('/console/demandes');
  let clicks = 0;
  await page.getByRole('link', { name: 'DV-2026-0003' }).click(); clicks++;
  await page.getByRole('button', { name: 'Créer le lien' }).click(); clicks++;
  expect(clicks, 'G-E1 create link').toBeLessThanOrEqual(2);
  await expect(page.locator('.ok')).toHaveText('Lien créé : copiez-le et envoyez-le aux participants.');
  const url = await page.locator('[data-group-url]').inputValue();
  expect(url).toMatch(new RegExp(`^${ORIGIN}/g/[A-Za-z0-9_-]{43}$`));
  await expect(counter(page)).toHaveText('0 répondu / 12 attendus');
  const sbxA = await sbxOf(page);
  // a second « Créer » (double click, replayed POST) keeps the one link
  const csrf = await page.locator('input[name="_csrf"]').first().inputValue();
  const again = await page.request.post('/console/demandes/3/groupe', { form: { _csrf: csrf, action: 'create' }, maxRedirects: 0, headers: { origin: ORIGIN } });
  expect(again.headers().location).toBe('/console/demandes/3/groupe?ok=existe');
  expect(await linkOf(page, 3)).toBe(pathOf(url));

  // delegate (context B, phone): 1 click to send
  const B = await newPage(browser, { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  await B.page.goto(pathOf(url));
  await expect(B.page.locator('[data-congress]')).toHaveText('Congrès européen de cardiologie — exemple');
  await expect(B.page.locator('[data-dates]')).toHaveText('27 au 30 août 2027');
  for (const l of ['Nom et prénom', 'E-mail', 'Ville de départ', 'Date aller', 'Date retour']) await expect(B.page.getByLabel(l)).toBeVisible();
  await expect(B.page.locator('label[for="g-consent"]')).toContainText('J’accepte');
  await expect(B.page.getByText('Tels qu’indiqués sur la pièce d’identité.')).toBeVisible();
  expect(await B.page.locator('form input:not([type=hidden]):not([name=zx_confirm]), form select, form textarea').count(), 'exactly 5 fields + consent').toBe(6);
  await fillDelegate(B.page);
  await B.page.waitForTimeout(3100);
  let sendClicks = 0;
  await B.page.getByRole('button', { name: 'Envoyer mes informations' }).click(); sendClicks++;
  expect(sendClicks, 'G-E2 delegate submit').toBe(1);
  await expect(B.page.getByRole('heading', { name: 'Votre réponse a bien été reçue.' })).toBeVisible();
  await expect(B.page.locator('[data-own]')).toContainText('Diane Morel (exemple)');
  await expect(B.page.locator('[data-own]')).toContainText('26/08/2027');
  const thanksUrl = B.page.url();

  // staff: manifest from the list in 2 clicks
  await page.goto('/console/demandes');
  let mClicks = 0;
  await page.getByRole('link', { name: 'DV-2026-0003' }).click(); mClicks++;
  await page.getByRole('link', { name: /^Groupe \(1\/12\)/ }).click(); mClicks++;
  expect(mClicks, 'G-E3 manifest').toBeLessThanOrEqual(2);
  await expect(counter(page)).toHaveText('1 répondu / 12 attendus');
  await expect(page.locator('[data-live] tbody tr')).toHaveCount(1);
  await expect(page.locator('[data-live] tbody')).toContainText('Diane Morel (exemple)');

  // same e-mail again (other case, other city): the row is updated, never duplicated
  await B.page.goto(pathOf(url));
  await fillDelegate(B.page, { email: 'Diane.MOREL@example.com', city: 'Grenoble', name: 'Diane Morel-Blanc (exemple)' });
  await B.page.waitForTimeout(3100);
  await B.page.getByRole('button', { name: 'Envoyer mes informations' }).click();
  await expect(B.page.locator('[data-own]')).toContainText('Grenoble');
  await page.reload();
  await expect(counter(page)).toHaveText('1 répondu / 12 attendus');
  await expect(page.locator('[data-live] tbody tr')).toHaveCount(1);
  await expect(page.locator('[data-live] tbody')).toContainText('Grenoble');
  await expect(page.locator('[data-live] tbody')).not.toContainText('Lyon');

  // G-I1: the token resolved to sandbox A server-side; B's browser got no sandbox of its own
  const sbxB = await sbxOf(B.page);
  if (!LIVE) {
    expect(d1Count(`SELECT sbx, COUNT(*) AS n FROM group_delegates WHERE enquiry_id = 3 AND sbx IN ('${sbxA}', '${sbxB}') GROUP BY sbx`)).toEqual([{ sbx: sbxA, n: 1 }]);
    expect(d1Count(`SELECT COUNT(*) AS n FROM group_delegates WHERE email_norm = 'diane.morel@example.com' AND sbx = '${sbxA}'`)[0].n).toBe(1);
    expect(d1Count(`SELECT COUNT(*) AS n FROM sandboxes WHERE id = '${sbxB}'`)[0].n).toBe(0);
  }
  // B's own console (same phone, logged in) never sees A's group; a third browser C neither
  await login(B.page, 'equipe');
  await B.page.goto('/console/demandes/3/groupe');
  await expect(counter(B.page)).toHaveText('0 répondu / 12 attendus');
  await expect(B.page.getByRole('button', { name: 'Créer le lien' })).toBeVisible();
  const C = await newPage(browser);
  await login(C.page, 'direction');
  await C.page.goto('/console/demandes/3/groupe');
  await expect(counter(C.page)).toHaveText('0 répondu / 12 attendus');
  await expect(C.page.locator('main')).not.toContainText('Diane');
  // C opening A's link sees the form only, and A's confirmation link is personal to the delegate who got it
  await C.page.goto(pathOf(url));
  leakFree(await C.page.content(), 'A link seen from C');
  await expect(C.page.locator('main')).not.toContainText('Diane');
  const tampered = thanksUrl.replace(/\.([A-Za-z0-9_-]{43})$/, (m, s) => '.' + (s[0] === 'A' ? 'B' : 'A') + s.slice(1));
  await C.page.goto(tampered);
  await expect(C.page.locator('[data-own]')).toHaveCount(0);
  await expect(C.page.locator('main')).not.toContainText('Diane');
  for (const P of [B, C]) { assertClean(P.problems); await P.ctx.close(); }
});

test('G-F3 CSV export of the manifest: BOM, semicolons, formula cells neutralised', async ({ page, browser }) => {
  await login(page, 'equipe');
  const link = await createLink(page, 3);
  const D = await newPage(browser);
  const hostile = await postDelegate(D.page.request, link, { name: '=HYPERLINK("http://evil.example","x")', email: 'formule@example.com', departure_city: '+33 cmd|calc' });
  expect(hostile.res.status()).toBe(303);
  const ok2 = await postDelegate(D.page.request, link, { name: '@SUM(A1) (exemple)', email: 'arobase@example.com', departure_city: '-Lille' });
  expect(ok2.res.status()).toBe(303);
  await page.goto('/console/demandes/3/groupe');
  const [dl] = await Promise.all([page.waitForEvent('download'), page.getByRole('link', { name: 'Exporter pour cotation (CSV)' }).click()]);
  expect(dl.suggestedFilename()).toMatch(/^groupe-DV-2026-0003-\d{4}-\d{2}-\d{2}\.csv$/);
  const buf = (await (await page.request.get('/console/demandes/3/groupe.csv')).body());
  expect([...buf.subarray(0, 3)]).toEqual([0xef, 0xbb, 0xbf]);
  const csv = buf.toString('utf8').slice(1);
  const lines = csv.trim().split('\r\n');
  expect(lines[0]).toBe('"Demande";"Congrès";"Nom (pièce d’identité)";"E-mail";"Ville de départ";"Aller";"Retour";"Reçu le";"Mis à jour le";"Modification à vérifier"');
  expect(lines.length).toBe(3);
  expect(csv).toContain(`"'=HYPERLINK(""http://evil.example"",""x"")"`);
  expect(csv).toContain(`"'+33 cmd|calc"`);
  expect(csv).toContain(`"'@SUM(A1) (exemple)"`);
  expect(csv).toContain(`"'-Lille"`);
  expect(csv).not.toMatch(/(^|;)"[=+\-@]/m);
  // the console shows them as text
  await expect(page.locator('[data-live] tbody')).toContainText('=HYPERLINK("http://evil.example","x")');
  // contributor: no access to groups or their export
  await login(page, 'contributeur');
  expect((await page.request.get('/console/demandes/3/groupe')).status()).toBe(403);
  expect((await page.request.get('/console/demandes/3/groupe.csv')).status()).toBe(403);
  assertClean(D.problems); await D.ctx.close();
});

test('G-F4 internal threshold « seuil groupe (à confirmer) »: setting, hint near and at it, never on the public link', async ({ page }) => {
  await login(page, 'equipe');
  await page.goto('/console/demandes/1/groupe');
  const set = async (n) => { await page.getByLabel('Seuil groupe (à confirmer)').fill(String(n)); await page.getByRole('button', { name: 'Enregistrer', exact: true }).click(); };
  await set(5);
  await expect(page.locator('.ok')).toHaveText('Seuil groupe enregistré.');
  await expect(page.getByLabel('Seuil groupe (à confirmer)')).toHaveValue('5');
  await expect(page.locator('[data-hint]')).toContainText('Proche du seuil groupe : 3 réponses sur 5 (à confirmer).');
  await expect(page.locator('[data-hint]')).toContainText('Indication interne');
  await set(3);
  await expect(page.locator('[data-hint]')).toContainText('Seuil groupe atteint : 3 réponses pour un seuil de 3 (à confirmer).');
  await set(20);
  await expect(page.locator('[data-hint]')).toHaveCount(0);
  for (const bad of ['1', '100', 'dix', '2.5']) {
    const csrf = await page.locator('input[name="_csrf"]').first().inputValue();
    const r = await page.request.post('/console/demandes/1/groupe', { form: { _csrf: csrf, action: 'seuil', seuil: bad }, maxRedirects: 0, headers: { origin: ORIGIN } });
    expect(r.headers().location, bad).toBe('/console/demandes/1/groupe?err=seuil');
  }
  await page.goto('/console/demandes/1/groupe?err=seuil');
  await expect(page.locator('.alert[role=alert]')).toContainText('nombre entier de 2 à 99');
  await expect(page.getByLabel('Seuil groupe (à confirmer)')).toHaveValue('20');
  // no airline rule cited anywhere on the tab
  expect(await page.locator('main').textContent()).not.toMatch(/Air France|KLM|AF-KLM|Lufthansa|compagnie aérienne|GM&E/);
  await set(10);
  const link = await linkOf(page, 1);
  leakFree(await (await page.request.get(link)).text(), 'public link after setting');
});

test('G-F5 revoke and copy: a revoked link stops at once, a new one works; « Copier le lien » copies it', async ({ page, browser }) => {
  await page.context().grantPermissions(['clipboard-read', 'clipboard-write'], { origin: ORIGIN });
  await login(page, 'equipe');
  const first = await createLink(page, 6);
  await page.getByRole('button', { name: 'Copier le lien' }).click();
  await expect(page.getByRole('button', { name: 'Lien copié' })).toBeVisible();
  expect(pathOf(await page.evaluate(() => navigator.clipboard.readText()))).toBe(first);
  const D = await newPage(browser);
  expect((await D.page.request.get(first)).status()).toBe(200);
  await page.getByRole('button', { name: 'Révoquer le lien' }).click();
  await expect(page.locator('.ok')).toContainText('Lien révoqué');
  await D.page.goto(first);
  await expect(D.page.getByRole('heading', { name: 'Ce lien n’est plus actif' })).toBeVisible();
  expect((await D.page.request.get(first)).status()).toBe(410);
  const late = await postDelegate(D.page.request, first, {}, { wait: 0, token: '1.x.y' });
  expect(late.res.status()).toBe(410);
  await expect(page.getByText(/Le lien précédent a été révoqué le/)).toBeVisible();
  await page.getByRole('button', { name: 'Créer un nouveau lien' }).click();
  const second = pathOf(await page.locator('[data-group-url]').inputValue());
  expect(second).not.toBe(first);
  expect((await D.page.request.get(second)).status()).toBe(200);
  expect([404, 410]).toContain((await D.page.request.get(first)).status());
  // the seed link can be revoked in this sandbox only: other browsers keep it
  const seed = await linkOf(page, 1);
  await page.getByRole('button', { name: 'Révoquer le lien' }).click();
  await expect(page.locator('.ok')).toContainText('Lien révoqué');
  expect((await page.request.get(seed)).status()).toBe(410);
  expect((await D.page.request.get(seed)).status()).toBe(200);
  assertClean(D.problems); await D.ctx.close();
});

test('G-H1 expired link: a polite closed page, no form, nothing stored', async ({ page }) => {
  test.skip(LIVE, 'needs a direct write to the local D1 state');
  await login(page, 'equipe');
  const link = await createLink(page, 2);
  const sbx = await sbxOf(page);
  d1Count(`UPDATE group_links SET expires_at = '2020-01-01T00:00:00Z' WHERE sbx = '${sbx}' AND enquiry_id = 2`);
  await page.goto(link);
  await expect(page.getByRole('heading', { name: 'Ce lien a expiré' })).toBeVisible();
  await expect(page.locator('form[action^="/g/"]')).toHaveCount(0);
  expect((await page.request.get(link)).status()).toBe(410);
  const r = await postDelegate(page.request, link, {}, { wait: 0, token: '1.x.y' });
  expect(r.res.status()).toBe(410);
  await page.goto('/console/demandes/2');
  await expect(page.getByText(/Le lien précédent a expiré le 01\/01\/2020/)).toBeVisible();
  await expect(page.getByRole('button', { name: 'Créer un nouveau lien' })).toBeVisible();
  expect(d1Count(`SELECT COUNT(*) AS n FROM group_delegates WHERE sbx = '${sbx}' AND enquiry_id = 2`)[0].n).toBe(0);
});

test('G-H2 guessed or malformed tokens: « Lien introuvable », the stored MAC is not a key', async ({ page }) => {
  const paths = [...Array.from({ length: 25 }, () => `/g/${randTok()}`), '/g/', '/g', '/g/abc', `/g/${'A'.repeat(43)}`, `/g/${randTok()}/merci`, `/g/${randTok()}x`, '/g/..%2f..%2fconsole', '/g/%252e%252e%252fsrc%252fdata.js', `/g/${randTok()}?d=x.1.y`, '/g/<script>alert(1)</script>'];
  if (!LIVE) for (const r of d1Count('SELECT token_mac FROM group_links LIMIT 5')) paths.push(`/g/${r.token_mac}`);
  for (const p of paths) {
    const r = await page.request.get(p);
    const t = await r.text();
    // Deployed, Cloudflare's edge refuses an encoded-slash traversal (%2f with ..) with its own 400 before the Worker runs.
    if (LIVE && p.includes('..%2f') && r.status() === 400) { leakFree(t, p); continue; }
    expect(r.status(), p).toBe(404);
    // dot segments (%2e%2e) are resolved by the URL parser before the request leaves: they reach the site-wide 404
    expect(t, p).toMatch(/Lien introuvable|Page introuvable/);
    expect(t, p).not.toContain('<script>alert(1)');
    leakFree(t, p);
  }
  const post = await page.request.post(`/g/${randTok()}`, { form: { name: 'x' }, maxRedirects: 0, headers: { origin: ORIGIN } });
  expect(post.status()).toBe(404);
});

test('G-H3 hostile delegate input: XSS as text, oversized, missing consent, reversed dates, forged or fast token, honeypot, cross-site', async ({ page, browser }) => {
  await login(page, 'equipe');
  const link = await createLink(page, 4);
  const D = await newPage(browser);
  const req = D.page.request;
  const cases = [
    [{ consent: undefined }, 'Cochez cette case'], [{ date_out: '2027-02-27', date_back: '2027-02-20' }, 'date retour doit être le jour de l’aller ou après'],
    [{ name: 'x'.repeat(121) }, '120 caractères'], [{ departure_city: 'y'.repeat(81) }, '80 caractères'], [{ email: 'pas-un-email' }, 'n’est pas valide'],
    [{ email: 'x@example.com\r\nBcc: v@example.com' }, 'n’est pas valide'], [{ date_out: '2025-01-10', date_back: '2025-01-12' }, 'ne peut pas être passée'],
    [{ date_out: '2027-06-01', date_back: '2027-06-03' }, 'proche du congrès'], [{ name: '' }, 'Indiquez vos nom et prénom'], [{ date_out: 'demain' }, 'Date invalide'],
  ];
  const toks = [];
  for (let i = 0; i < cases.length; i++) toks.push(/name="_token" value="([^"]+)"/.exec(await (await req.get(link)).text())[1]);
  await new Promise((r) => setTimeout(r, 3100));
  for (let i = 0; i < cases.length; i++) {
    const [fields, msg] = cases[i];
    const { res, text } = await postDelegate(req, link, { date_out: '2027-02-23', date_back: '2027-02-28', ...fields }, { wait: 0, token: toks[i] });
    expect(res.status(), JSON.stringify(fields)).toBe(200);
    expect(text, JSON.stringify(fields)).toContain(msg);
    expect(text).toContain('rien n’a été enregistré');
  }
  const big = await req.post(link, { form: { name: 'x'.repeat(40000) }, maxRedirects: 0, headers: { origin: ORIGIN } });
  expect(big.status()).toBe(413);
  const fast = await postDelegate(req, link, { date_out: '2027-02-23', date_back: '2027-02-28' }, { wait: 0 });
  expect(fast.text).toContain('validé trop vite');
  const forged = await postDelegate(req, link, {}, { wait: 0, token: `${Date.now() - 10000}.abcdefghijkl.forgedforgedforgedforged` });
  expect(forged.res.status()).toBe(403);
  // a token minted for another link is refused (the form kind is signed with the link)
  const other = /name="_token" value="([^"]+)"/.exec(await (await req.get(await linkOf(page, 1))).text())[1];
  await new Promise((r) => setTimeout(r, 3100));
  expect((await postDelegate(req, link, { date_out: '2027-02-23', date_back: '2027-02-28' }, { wait: 0, token: other })).res.status()).toBe(403);
  const cross = await postDelegate(req, link, { date_out: '2027-02-23', date_back: '2027-02-28' }, { headers: { origin: 'https://evil.example' } });
  expect(cross.res.status()).toBe(403);
  const hp = await postDelegate(req, link, { date_out: '2027-02-23', date_back: '2027-02-28', zx_confirm: 'http://spam.example' });
  expect(hp.res.status()).toBe(303);
  await page.goto('/console/demandes/4/groupe');
  await expect(counter(page)).toHaveText('0 répondu / 3 attendus');
  // XSS payloads are stored and shown as text only, on the delegate's page and in the console
  let dialogs = 0; D.page.on('dialog', () => { dialogs++; }); page.on('dialog', () => { dialogs++; });
  const evil = '<img src=x onerror=alert(1)><script>alert(2)</script>';
  await D.page.goto(link);
  await fillDelegate(D.page, { name: `${evil} (exemple)`, email: 'xss@example.com', city: '"><svg onload=alert(3)>', out: '2027-02-23', back: '2027-02-28' });
  await D.page.waitForTimeout(3100);
  await D.page.getByRole('button', { name: 'Envoyer mes informations' }).click();
  await expect(D.page.locator('[data-own]')).toContainText(evil);
  expect(await D.page.locator('main img, main svg').count()).toBe(0);
  await page.reload();
  await expect(page.locator('[data-live] tbody')).toContainText(evil);
  expect(await page.locator('main img, main svg').count()).toBe(0);
  expect(dialogs).toBe(0);
  await expect(counter(page)).toHaveText('1 répondu / 3 attendus');
  assertClean(D.problems); await D.ctx.close();
});

test('G-H4 rate limits of the public route: 20 submissions per IP per 10 min, then a French refusal; a crawl of misses is cut off', async ({ page, browser }) => {
  test.skip(LIVE, 'the per-IP header can only be set on a local run (Cloudflare sets cf-connecting-ip live)');
  await login(page, 'equipe');
  const link = await createLink(page, 3);
  // a real visitor (no test key) behind one IP
  const ip = `198.51.100.${Math.floor(Math.random() * 200) + 20}`;
  const ctx = await browser.newContext({ baseURL: BASE, extraHTTPHeaders: { 'cf-connecting-ip': ip } });
  const req = ctx.request;
  const toks = [];
  for (let i = 0; i < 21; i++) toks.push(/name="_token" value="([^"]+)"/.exec(await (await req.get(link)).text())[1]);
  await new Promise((r) => setTimeout(r, 3100));
  const statuses = []; let last;
  for (let i = 0; i < 21; i++) { last = await postDelegate(req, link, { email: `rafale${i}@example.com`, name: `Rafale ${i} (exemple)` }, { wait: 0, token: toks[i] }); statuses.push(last.res.status()); }
  expect(statuses).toEqual([...Array(20).fill(303), 429]);
  expect(last.text).toContain('trop d’envois depuis cette connexion en 10 minutes');
  await page.goto('/console/demandes/3/groupe');
  await expect(counter(page)).toHaveText('20 répondus / 12 attendus');
  // misses (unknown tokens) from one IP: cut off after 60 in 10 minutes, without a database write
  const ip2 = `203.0.113.${Math.floor(Math.random() * 200) + 20}`;
  const got = [];
  for (let i = 0; i < 62; i++) got.push((await req.get(`/g/${randTok()}`, { headers: { 'cf-connecting-ip': ip2 } })).status());
  expect(got.slice(0, 60).every((s) => s === 404)).toBe(true);
  expect(got.slice(60)).toEqual([429, 429]);
  const blocked = await req.get(link, { headers: { 'cf-connecting-ip': ip2 } });
  expect(blocked.status()).toBe(429);
  expect(await blocked.text()).toContain('Trop d’essais');
  expect((await req.get(link)).status()).toBe(200); // another IP is not affected
  await ctx.close();
});

test('G-H5 no silent overwrite: an existing e-mail from another browser becomes « Modification à vérifier »; the creator’s browser may update; staff accept or refuse', async ({ page, browser }) => {
  await login(page, 'equipe');
  const link = await createLink(page, 3);
  const B = await newPage(browser); // the delegate's own phone
  const C = await newPage(browser); // a colleague holding the same link
  const dlg = async (P) => (await P.ctx.cookies()).find((c) => c.name === '__Host-av_dlg');
  const first = await postDelegate(B.page.request, link, { name: 'Diane Morel (exemple)', email: 'diane.morel@example.com', departure_city: 'Lyon' });
  expect(first.res.status()).toBe(303);
  expect(await dlg(B)).toBeTruthy();
  expect((await dlg(B)).httpOnly).toBe(true);
  // C: one new e-mail and one existing e-mail. Same status, same redirect shape, same cookie, same page: nothing tells them apart.
  const fresh = await postDelegate(C.page.request, link, { name: 'Hugo Blanc (exemple)', email: 'hugo.blanc@example.com', departure_city: 'Rennes' });
  const overwrite = await postDelegate(C.page.request, link, { name: 'Diane Usurpée (exemple)', email: 'DIANE.morel@example.com', departure_city: 'Brest' });
  for (const x of [fresh, overwrite]) {
    expect(x.res.status()).toBe(303);
    expect(x.res.headers().location).toMatch(/^\/g\/[A-Za-z0-9_-]{43}\/merci\?d=[A-Za-z0-9_-]{12}\.\d{10}\.[A-Za-z0-9_-]{43}$/);
    expect(x.res.headers()['set-cookie']).toMatch(/^__Host-av_dlg=[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}; Path=\/; HttpOnly; Secure; SameSite=Lax; Max-Age=\d+$/);
  }
  const shape = async (x, name, city) => (await (await C.page.request.get(x.res.headers().location)).text()).replace(name, 'NOM').replace(/[a-zA-Z.]+@example\.com/, 'MAIL').replace(city, 'VILLE').replace(/\/g\/[A-Za-z0-9_-]{43}/g, '/g/T');
  const s1 = await shape(fresh, 'Hugo Blanc (exemple)', 'Rennes');
  const s2 = await shape(overwrite, 'Diane Usurpée (exemple)', 'Brest');
  expect(s2).toBe(s1);
  expect(s1).toContain('Votre réponse a bien été reçue.');
  expect(s2).not.toContain('Lyon');
  // the console: original kept, the change waits with its badge
  await page.goto('/console/demandes/3/groupe');
  await expect(counter(page)).toHaveText('2 répondus / 12 attendus');
  const row = page.locator('[data-live] tbody tr', { hasText: 'Diane Morel (exemple)' });
  await expect(row).toContainText('Lyon');
  await expect(row).toContainText('Modification à vérifier');
  await expect(page.locator('[data-live] tbody')).not.toContainText('Brest');
  const pend = page.locator('[data-pending-row]');
  await expect(pend).toHaveCount(1);
  await expect(pend).toContainText('Actuel : Diane Morel (exemple)');
  await expect(pend).toContainText('Proposé : Diane Usurpée (exemple)');
  await expect(pend).toContainText('Brest');
  // the creator's browser updates directly, the pending change stays for staff
  const own = await postDelegate(B.page.request, link, { name: 'Diane Morel (exemple)', email: 'diane.morel@example.com', departure_city: 'Grenoble' });
  expect(own.res.status()).toBe(303);
  // a forged delegate cookie is ignored: still a pending change
  const E = await browser.newContext({ baseURL: BASE, extraHTTPHeaders: { ...(TEST_KEY ? { 'x-demo-test': TEST_KEY } : {}), cookie: `__Host-av_dlg=${'A'.repeat(22)}.${'B'.repeat(43)}` } });
  expect((await postDelegate(E.request, link, { name: 'Diane Faux (exemple)', email: 'diane.morel@example.com', departure_city: 'Nice' })).res.status()).toBe(303);
  await E.close();
  await page.reload();
  await expect(row).toContainText('Grenoble');
  await expect(pend).toHaveCount(1);
  await expect(pend).toContainText('Nice'); // the latest proposal replaces the earlier one
  if (!LIVE) expect(d1Count(`SELECT COUNT(*) AS n FROM group_delegates WHERE email_norm = 'diane.morel@example.com' AND sbx = '${await sbxOf(page)}'`)[0].n).toBe(1);
  // Refuser: the entry stays as it was
  await pend.getByRole('button', { name: 'Refuser' }).click();
  await expect(page.locator('.ok')).toHaveText('Modification refusée : l’inscription d’origine est conservée.');
  await expect(pend).toHaveCount(0);
  await expect(row).toContainText('Grenoble');
  await expect(row).not.toContainText('Modification à vérifier');
  // Accepter: the entry takes the proposal, keeps one row and its creator, who can still correct it
  await postDelegate(C.page.request, link, { name: 'Diane Morel-Blanc (exemple)', email: 'diane.morel@example.com', departure_city: 'Annecy' });
  await page.reload();
  await pend.getByRole('button', { name: 'Accepter' }).click();
  await expect(page.locator('.ok')).toHaveText('Modification acceptée : la liste est à jour.');
  await expect(counter(page)).toHaveText('2 répondus / 12 attendus');
  const accepted = page.locator('[data-live] tbody tr', { hasText: 'Diane Morel-Blanc (exemple)' });
  await expect(accepted).toContainText('Annecy');
  await postDelegate(B.page.request, link, { name: 'Diane Morel (exemple)', email: 'diane.morel@example.com', departure_city: 'Valence' });
  await page.reload();
  await expect(page.locator('[data-live] tbody tr', { hasText: 'Diane Morel (exemple)' })).toContainText('Valence');
  await expect(pend).toHaveCount(0);
  // a seeded delegate's e-mail sent from any browser is a pending change too (the seed has no owner)
  await postDelegate(C.page.request, await linkOf(page, 1), { name: 'Usurpateur (exemple)', email: 'alice.martin@example.com', date_out: '2027-01-27', date_back: '2027-01-31' });
  // decisions need a staff session and its CSRF token
  const anon = await C.page.request.post('/console/demandes/3/groupe', { form: { action: 'accepter', email: 'diane.morel@example.com' }, maxRedirects: 0, headers: { origin: ORIGIN } });
  expect([302, 303, 401, 403]).toContain(anon.status());
  for (const P of [B, C]) { assertClean(P.problems); await P.ctx.close(); }
});

// Fresh form tokens for one link, aged past the 3 s minimum together (one wait for the batch).
async function tokensFor(request, link, n) {
  const out = [];
  for (let i = 0; i < n; i++) out.push(/name="_token" value="([^"]+)"/.exec(await (await request.get(link)).text())[1]);
  await new Promise((r) => setTimeout(r, 3100));
  return out;
}
const FEB = { date_out: '2027-02-23', date_back: '2027-02-28' }; // DV-2026-0004, radiology congress 24 to 28 Feb. 2027

test('G-H6 (SEC-X-008) at the cap, a new and a registered e-mail get the same answer: both pending, then both refused alike', async ({ page, browser }) => {
  await login(page, 'equipe');
  const link = await createLink(page, 4); // 3 passengers: cap max(10, 2 x 3) = 10
  const D = await newPage(browser); // fills the list
  const C = await newPage(browser); // someone else holding the link
  let toks = await tokensFor(D.page.request, link, 10);
  for (let i = 0; i < 10; i++) expect((await postDelegate(D.page.request, link, { ...FEB, name: `Plein ${i} (exemple)`, email: `plein${i}@example.com` }, { wait: 0, token: toks[i] })).res.status()).toBe(303);
  await page.goto('/console/demandes/4/groupe');
  await expect(counter(page)).toHaveText('10 répondus / 3 attendus');
  // list full: a new e-mail and a registered one, from C
  toks = await tokensFor(C.page.request, link, 2);
  const fresh = await postDelegate(C.page.request, link, { ...FEB, name: 'Nouveau (exemple)', email: 'nouveau@example.com', departure_city: 'Rennes' }, { wait: 0, token: toks[0] });
  const known = await postDelegate(C.page.request, link, { ...FEB, name: 'Connu (exemple)', email: 'plein3@example.com', departure_city: 'Brest' }, { wait: 0, token: toks[1] });
  for (const x of [fresh, known]) {
    expect(x.res.status()).toBe(303);
    expect(x.res.headers().location).toMatch(/^\/g\/[A-Za-z0-9_-]{43}\/merci\?d=[A-Za-z0-9_-]{12}\.\d{10}\.[A-Za-z0-9_-]{43}$/);
    expect(x.res.headers()['set-cookie']).toMatch(/^__Host-av_dlg=[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}; /);
  }
  const shape = async (x, name, mail, city) => (await (await C.page.request.get(x.res.headers().location)).text()).replace(name, 'NOM').replace(mail, 'MAIL').replace(city, 'VILLE').replace(/\/g\/[A-Za-z0-9_-]{43}/g, '/g/T');
  expect(await shape(fresh, 'Nouveau (exemple)', 'nouveau@example.com', 'Rennes')).toBe(await shape(known, 'Connu (exemple)', 'plein3@example.com', 'Brest'));
  await page.reload();
  await expect(counter(page)).toHaveText('10 répondus / 3 attendus');
  await expect(page.locator('[data-pending-row]')).toHaveCount(2);
  await expect(page.locator('[data-pending-row]', { hasText: 'Nouveau (exemple)' })).toContainText('aucune inscription');
  // fill the pending list to the cap too (8 more new e-mails), then both kinds are refused with the same page
  toks = await tokensFor(C.page.request, link, 10);
  for (let i = 0; i < 8; i++) expect((await postDelegate(C.page.request, link, { ...FEB, name: `Attente ${i} (exemple)`, email: `attente${i}@example.com` }, { wait: 0, token: toks[i] })).res.status()).toBe(303);
  const r1 = await postDelegate(C.page.request, link, { ...FEB, name: 'Encore (exemple)', email: 'encore@example.com', departure_city: 'Rennes' }, { wait: 0, token: toks[8] });
  const r2 = await postDelegate(C.page.request, link, { ...FEB, name: 'Encore (exemple)', email: 'plein5@example.com', departure_city: 'Rennes' }, { wait: 0, token: toks[9] });
  expect([r1.res.status(), r2.res.status()]).toEqual([200, 200]);
  const strip = (t) => t.replace(/name="_token" value="[^"]+"/, '').replace(/encore@example\.com|plein5@example\.com/, 'MAIL');
  expect(strip(r1.text)).toBe(strip(r2.text));
  expect(r1.text).toContain('la liste de ce groupe est complète');
  // the owner's own update is never blocked by the cap
  const own = await postDelegate(D.page.request, link, { ...FEB, name: 'Plein 2 (exemple)', email: 'plein2@example.com', departure_city: 'Annecy' });
  expect(own.res.status()).toBe(303);
  await page.reload();
  await expect(page.locator('[data-pending-row]')).toHaveCount(10);
  await expect(page.locator('[data-live] tbody tr', { hasText: 'Plein 2 (exemple)' })).toContainText('Annecy');
  for (const P of [C, D]) { assertClean(P.problems); await P.ctx.close(); }
});

test('G-H7 (SEC-X-016) the public form token is single-use: a replay stores nothing', async ({ page, browser }) => {
  await login(page, 'equipe');
  const link = await createLink(page, 4);
  const D = await newPage(browser);
  const [t1, t2] = await tokensFor(D.page.request, link, 2);
  const first = await postDelegate(D.page.request, link, { ...FEB, name: 'Unique (exemple)', email: 'unique@example.com' }, { wait: 0, token: t1 });
  expect(first.res.status()).toBe(303);
  for (const fields of [{ name: 'Unique (exemple)', email: 'unique@example.com' }, { name: 'Rejeu (exemple)', email: 'rejeu@example.com' }]) {
    const again = await postDelegate(D.page.request, link, { ...FEB, ...fields }, { wait: 0, token: t1 });
    expect(again.res.status()).toBe(200);
    expect(again.text).toContain('Ce formulaire a déjà été envoyé');
  }
  // another page load's token still works once
  expect((await postDelegate(D.page.request, link, { ...FEB, name: 'Second (exemple)', email: 'second@example.com' }, { wait: 0, token: t2 })).res.status()).toBe(303);
  expect((await postDelegate(D.page.request, link, { ...FEB, name: 'Second (exemple)', email: 'second@example.com' }, { wait: 0, token: t2 })).res.status()).toBe(200);
  await page.goto('/console/demandes/4/groupe');
  await expect(counter(page)).toHaveText('2 répondus / 3 attendus');
  await expect(page.locator('[data-live]')).not.toContainText('Rejeu');
  await expect(page.locator('[data-pending-row]')).toHaveCount(0);
  assertClean(D.problems); await D.ctx.close();
});

// ---------------------------------------------------------------- UX round (../qa/register/EXTRA_ux.md)
// Words of a text element that the browser split over two lines (a « word » is a run without regular spaces, so a
// title joined to « — exemple » by non-breaking spaces counts as one).
const brokenWords = (loc) => loc.evaluate((el) => {
  const node = el.firstChild; const text = node.textContent; const out = []; let i = 0;
  for (const w of text.split(' ')) {
    const r = document.createRange(); r.setStart(node, i); r.setEnd(node, i + w.length);
    const tops = new Set([...r.getClientRects()].filter((x) => x.width > 0).map((x) => Math.round(x.top)));
    if (tops.size > 1) out.push(w);
    i += w.length + 1;
  }
  return out;
});

test('G-U1 (EYE-X-001) the delegate page title never breaks inside a word, at 1440 and 390; (USAB-X-005) all answered: « Tous les participants ont répondu »', async ({ page, browser }) => {
  await login(page, 'equipe');
  const link = await createLink(page, 2); // Journées françaises de diabétologie — exemple, 2 passengers
  for (const vp of [{ width: 1440, height: 900 }, { width: 1280, height: 800 }, { width: 390, height: 844 }]) {
    const P = await newPage(browser, { viewport: vp });
    await P.page.goto(link);
    const h1 = P.page.locator('h1[data-congress]');
    await expect(h1).toHaveText('Journées françaises de diabétologie — exemple');
    expect(await brokenWords(h1), `${vp.width}px`).toEqual([]);
    const right = await h1.evaluate((el) => { const r = document.createRange(); r.selectNodeContents(el); return Math.max(...[...r.getClientRects()].map((x) => x.right)); });
    expect(right, `${vp.width}px title inside the window`).toBeLessThanOrEqual(vp.width);
    assertClean(P.problems); await P.ctx.close();
  }
  // 2 of 2 answered, threshold 3: near the threshold, and everyone has answered
  const D = await newPage(browser);
  const toks = await tokensFor(D.page.request, link, 2);
  for (let i = 0; i < 2; i++) expect((await postDelegate(D.page.request, link, { date_out: '2027-03-22', date_back: '2027-03-26', email: `tous${i}@example.com`, name: `Tous ${i} (exemple)` }, { wait: 0, token: toks[i] })).res.status()).toBe(303);
  await page.goto('/console/demandes/2/groupe');
  await page.getByLabel('Seuil groupe (à confirmer)').fill('3');
  await page.getByRole('button', { name: 'Enregistrer', exact: true }).click();
  await expect(page.locator('[data-hint]')).toContainText('Proche du seuil groupe : 2 réponses sur 3 (à confirmer). Tous les participants ont répondu.');
  await expect(page.locator('[data-hint]')).not.toContainText('Relancez');
  await page.getByLabel('Seuil groupe (à confirmer)').fill('10');
  await page.getByRole('button', { name: 'Enregistrer', exact: true }).click();
  await expect(page.locator('[data-hint]')).toContainText('Tous les participants ont répondu.');
  assertClean(D.problems); await D.ctx.close();
});

test('G-U2 (USAB-X-001) a replaced link says « Ce lien n’est plus actif. Demandez le nouveau lien à votre agence. », not « Lien introuvable »', async ({ page, browser }) => {
  await login(page, 'equipe');
  const old = await createLink(page, 6);
  await page.getByRole('button', { name: 'Révoquer le lien' }).click();
  await page.getByRole('button', { name: 'Créer un nouveau lien' }).click();
  const fresh = pathOf(await page.locator('[data-group-url]').inputValue());
  expect(fresh).not.toBe(old);
  const D = await newPage(browser);
  await D.page.goto(old);
  await expect(D.page.getByRole('heading', { name: 'Ce lien n’est plus actif' })).toBeVisible();
  await expect(D.page.locator('main')).toContainText('Ce lien n’est plus actif. Demandez le nouveau lien à votre agence.');
  await expect(D.page.locator('main')).not.toContainText('introuvable');
  expect((await D.page.request.get(old)).status()).toBe(410);
  expect((await D.page.request.get(fresh)).status()).toBe(200);
  // a third link replaces the second: both old ones say « plus actif »
  await page.getByRole('button', { name: 'Révoquer le lien' }).click();
  await page.getByRole('button', { name: 'Créer un nouveau lien' }).click();
  for (const l of [old, fresh]) expect(await (await D.page.request.get(l)).text()).toContain('Demandez le nouveau lien à votre agence.');
  // a guessed token is still « introuvable »
  expect(await (await D.page.request.get(`/g/${randTok()}`)).text()).toContain('Lien introuvable');
  assertClean(D.problems); await D.ctx.close();
});

test('G-U3 (EYE-X-002) short public pages keep the footer at the bottom; (EYE-X-003) e-mails wrap only at @ and dots, cities stay on one line', async ({ page, browser }) => {
  for (const vp of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) {
    const P = await newPage(browser, { viewport: vp });
    for (const p of [`/g/${randTok()}`, '/page-inconnue']) {
      await P.page.goto(p);
      const bottom = await P.page.locator('footer.foot').evaluate((f) => f.getBoundingClientRect().bottom);
      expect(bottom, `${p} at ${vp.width}`).toBeGreaterThanOrEqual(vp.height - 1);
    }
    assertClean(P.problems); await P.ctx.close();
  }
  await login(page, 'equipe');
  const link = await createLink(page, 3);
  const D = await newPage(browser);
  const toks = await tokensFor(D.page.request, link, 2);
  await postDelegate(D.page.request, link, { name: 'Gaëlle Dupont-Lefèvre de la Roche (exemple)', email: 'gaelle.dupont-lefevre.54050@sous-domaine.example.com', departure_city: 'Saint-Étienne' }, { wait: 0, token: toks[0] });
  await postDelegate(D.page.request, link, { name: 'Jean (exemple)', email: 'j@example.com', departure_city: 'Clermont-Ferrand' }, { wait: 0, token: toks[1] });
  for (const width of [1440, 1366, 1100, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto('/console/demandes/3/groupe');
    for (const city of ['Saint-Étienne', 'Clermont-Ferrand']) {
      const lines = await page.locator('[data-live] tbody .nw', { hasText: city }).evaluate((el) => new Set([...el.getClientRects()].map((x) => Math.round(x.top))).size);
      expect(lines, `${city} at ${width}`).toBe(1);
    }
    // each part between break points (<wbr> before @ and dots) stays on one line, hyphens included
    const parts = await page.locator('[data-live] tbody tr', { hasText: 'Gaëlle' }).locator('.em').evaluate((el) => [...el.querySelectorAll(':scope > span')].map((n) => ({ t: n.textContent, lines: new Set([...n.getClientRects()].map((x) => Math.round(x.top))).size })));
    expect(parts.every((p, i) => i === 0 || /^[@.]/.test(p.t))).toBe(true);
    expect(parts.map((p) => p.t).join('')).toBe('gaelle.dupont-lefevre.54050@sous-domaine.example.com');
    for (const p of parts) expect(p.lines, `« ${p.t} » at ${width}`).toBe(1);
  }
  await page.setViewportSize({ width: 1440, height: 900 });
  assertClean(D.problems); await D.ctx.close();
});

test('G-U4 phone: the first field is visible without scrolling; « Aller au lien de groupe » near the top; pending changes highlight what differs', async ({ page, browser }) => {
  await login(page, 'equipe');
  const seed = await linkOf(page, 1);
  const P = await newPage(browser, { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  await P.page.goto(seed);
  const box = await P.page.locator('#g-name').boundingBox();
  expect(box.y + box.height, 'first field above the fold at 390 x 844').toBeLessThanOrEqual(844);
  await expect(P.page.locator('.grp__steps')).toBeVisible(); // the steps now follow the form
  expect((await P.page.locator('.grp__steps').boundingBox()).y).toBeGreaterThan(box.y);
  assertClean(P.problems); await P.ctx.close();
  // the enquiry page offers a shortcut to the group card, above the enquiry details
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/console/demandes/1');
  const jump = page.getByRole('link', { name: 'Aller au lien de groupe' });
  await expect(jump).toHaveAttribute('href', '#lien-groupe');
  expect((await jump.boundingBox()).y).toBeLessThan((await page.getByRole('heading', { name: 'Détail de la demande' }).boundingBox()).y);
  await jump.click();
  await expect(page.locator('#lien-groupe')).toBeInViewport();
  await page.goto('/console/demandes/5');
  await expect(page.getByRole('link', { name: 'Aller au lien de groupe' })).toHaveCount(0);
  await page.setViewportSize({ width: 1440, height: 900 });
  // pending change: the differing fields are marked, the others are not
  const link = await createLink(page, 3);
  const B = await newPage(browser); const C = await newPage(browser);
  await postDelegate(B.page.request, link, { name: 'Marc Petit (exemple)', email: 'marc.petit@example.com', departure_city: 'Lyon' });
  await postDelegate(C.page.request, link, { name: 'Marc Petitjean (exemple)', email: 'MARC.petit@example.com', departure_city: 'Dijon' });
  await page.reload();
  const marks = await page.locator('[data-pending-row] mark.diff').allTextContents();
  expect(marks).toEqual(['Marc Petitjean (exemple)', 'Dijon']);
  for (const X of [B, C]) { assertClean(X.problems); await X.ctx.close(); }
});

test('G-L1 leak: form, confirmation and closed pages never show other delegates, enquiry data, codes or the threshold', async ({ page, browser }) => {
  await login(page, 'direction'); // Direction sees everything, codes included: none of it may reach the public link
  const seed = await linkOf(page, 1);
  const created = await createLink(page, 3);
  const D = await newPage(browser);
  for (const l of [seed, created]) {
    const r = await D.page.request.get(l);
    expect(r.status()).toBe(200);
    leakFree(await r.text(), l);
    for (const [k, v] of Object.entries(r.headers())) leakFree(`${k}: ${v}`, `${l} header`);
    expect(r.headers()['cache-control']).toContain('no-store');
  }
  // a new delegate on the seed link: the confirmation shows their own entry only
  const sent = await postDelegate(D.page.request, seed, { name: 'Emma Faure (exemple)', email: 'emma.faure@example.com', date_out: '2027-01-27', date_back: '2027-01-31' });
  expect(sent.res.status()).toBe(303);
  const thanks = await (await D.page.request.get(sent.res.headers().location)).text();
  expect(thanks).toContain('Emma Faure (exemple)');
  leakFree(thanks, 'confirmation');
  // a seeded delegate's e-mail typed by someone else: the confirmation shows what was typed, never the stored seed entry
  const over = await postDelegate(D.page.request, seed, { name: 'Usurpateur (exemple)', email: 'alice.martin@example.com', departure_city: 'Brest', date_out: '2027-01-27', date_back: '2027-01-31' });
  const t2 = await (await D.page.request.get(over.res.headers().location)).text();
  expect(t2).toContain('Usurpateur (exemple)');
  expect(t2).not.toContain('Alice Martin');
  // closed pages
  for (const p of [`/g/${randTok()}`, `/g/${randTok()}/merci`]) leakFree(await (await D.page.request.get(p)).text(), p);
  // the public link never mentions GM&E in the DOM, inputs included
  await D.page.goto(seed);
  const values = await D.page.locator('input, textarea').evaluateAll((els) => els.map((e) => e.value).join(' '));
  expect(values).not.toMatch(/GM&E|DEMO-GME|DV-2026/);
  assertClean(D.problems); await D.ctx.close();
});

test('G-L2 crawl: /g/* with random tokens and probes yields nothing; other sandboxes’ links stay private', async ({ page, browser }) => {
  const probes = [...Array.from({ length: 40 }, () => `/g/${randTok()}`), ...Array.from({ length: 5 }, () => `/g/${randTok()}/merci?d=seedA0000001.9999999999.${randTok()}`), '/g/sitemap.xml', '/g/index', '/g/.env', '/g/api', '/g/robots.txt'];
  for (const p of probes) {
    const r = await page.request.get(p);
    expect(r.status(), p).toBe(404);
    const t = await r.text();
    leakFree(t, p);
    expect(t, p).not.toContain('data-own');
    expect(t, p).not.toContain('name="_token"');
  }
  // a link from sandbox A is not listed or reachable from sandbox C's console
  const A = await newPage(browser);
  await login(A.page, 'equipe');
  const aLink = await createLink(A.page, 6);
  await login(page, 'equipe');
  await page.goto('/console/demandes/6/groupe');
  await expect(page.getByRole('button', { name: 'Créer le lien' })).toBeVisible();
  expect(await page.content()).not.toContain(aLink.slice(3));
  assertClean(A.problems); await A.ctx.close();
});

test('G-X1 write cost: one delegate submission writes at most 2 rows and counts against the creating sandbox', async ({ page, browser }) => {
  test.skip(!TEST_KEY, 'the row meter needs the test key');
  await login(page, 'equipe');
  const link = await createLink(page, 3);
  const D = await newPage(browser);
  const r = await postDelegate(D.page.request, link, { email: 'mesure@example.com' });
  expect(r.res.status()).toBe(303);
  expect(+r.res.headers()['x-d1-rows-written']).toBeLessThanOrEqual(2);
  const again = await postDelegate(D.page.request, link, { email: 'mesure@example.com', departure_city: 'Nice' });
  expect(+again.res.headers()['x-d1-rows-written']).toBeLessThanOrEqual(2);
  assertClean(D.problems); await D.ctx.close();
});

test('G-X2 phone width: the delegate form and its confirmation fit 390 px with 44 px targets', async ({ page, browser }) => {
  await login(page, 'equipe');
  const link = await linkOf(page, 1);
  const P = await newPage(browser, { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  await P.page.goto(link);
  expect(await P.page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  for (const sel of ['#g-name', '#g-email', '#g-city', '#g-out', '#g-back', 'button[type=submit]']) {
    const b = await P.page.locator(sel).boundingBox();
    expect(b.height, sel).toBeGreaterThanOrEqual(44);
    expect(b.x + b.width, sel).toBeLessThanOrEqual(390);
  }
  expect(await P.page.locator('#g-name').evaluate((e) => parseFloat(getComputedStyle(e).fontSize))).toBeGreaterThanOrEqual(16);
  await fillDelegate(P.page, { email: 'mobile@example.com', out: '2027-01-27', back: '2027-01-31' });
  await P.page.waitForTimeout(3100);
  await P.page.getByRole('button', { name: 'Envoyer mes informations' }).click();
  await expect(P.page.locator('[data-own]')).toBeVisible();
  expect(await P.page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  assertClean(P.problems); await P.ctx.close();
});

test('G-X3 Hallmark sloplint: zero FAIL on the new public pages and console pages', async ({ page }) => {
  const dir = join(ROOT, '.lint', LIVE ? 'live' : 'local', 'group');
  rmSync(dir, { recursive: true, force: true });
  mkdirSync(join(dir, 'pub'), { recursive: true }); mkdirSync(join(dir, 'con'), { recursive: true });
  copyFileSync(join(ROOT, 'public/assets/app.css'), join(dir, 'app.css'));
  const fix = (h) => h.replace(/href="\/assets\/app\.css[^"]*"/, 'href="../app.css"');
  await login(page, 'equipe');
  const link = await linkOf(page, 1);
  await postDelegate(page.request, link, { name: 'Alice Martin-Roy (exemple)', email: 'alice.martin@example.com', date_out: '2027-01-27', date_back: '2027-01-31' }); // a pending change on screen
  await page.goto('/console/demandes/1/groupe');
  await expect(page.locator('[data-pending-row]')).toHaveCount(1);
  writeFileSync(join(dir, 'con', 'groupe.html'), fix(await page.content()));
  await page.goto('/console/demandes/1');
  writeFileSync(join(dir, 'con', 'demande.html'), fix(await page.content()));
  await page.goto('/console/demandes/3');
  writeFileSync(join(dir, 'con', 'demande-sans-lien.html'), fix(await page.content()));
  const sent = await postDelegate(page.request, link, { email: 'lint@example.com', date_out: '2027-01-27', date_back: '2027-01-31' });
  for (const [name, u] of [['form', link], ['merci', sent.res.headers().location], ['introuvable', `/g/${randTok()}`]]) {
    writeFileSync(join(dir, 'pub', name + '.html'), fix(await (await page.request.get(u)).text()));
  }
  const lint = (args) => { try { return execFileSync('node', [join(ROOT, '../../../.claude/skills/hallmark/scripts/sloplint.mjs'), ...args], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] }); } catch (e) { return (e.stdout || '') + (e.stderr || ''); } };
  const pub = lint([join(dir, 'pub'), join(dir, 'app.css'), '--genre', 'editorial']);
  const con = lint([join(dir, 'con'), join(dir, 'app.css'), '--scope', 'app']);
  writeFileSync(join(dir, 'sloplint.txt'), pub + '\n=====\n' + con);
  const fails = (t) => +((/sloplint: (\d+) FAIL/.exec(t) || [0, 'NaN'])[1]);
  expect(fails(pub), pub.split('\n').filter((l) => l.includes('FAIL')).join('\n')).toBe(0);
  expect(fails(con), con.split('\n').filter((l) => l.includes('FAIL')).join('\n')).toBe(0);
});
