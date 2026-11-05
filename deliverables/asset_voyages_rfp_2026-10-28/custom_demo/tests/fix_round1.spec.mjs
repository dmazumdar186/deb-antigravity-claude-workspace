// Fix round 1: one regression test per finding of the eye review and the adversarial pass (FIX-n).
import { test, expect, login, logout, csrfOf, fillEnquiry, SLUG, CODES, LIVE, BASE, CTX, newPage, assertClean, sbxOf, d1Count, resetSandbox } from './helpers.mjs';
import { execFileSync } from 'node:child_process';
import { ROOT } from './helpers.mjs';

// Independent tests: one failure does not skip the others.
const nav = (page, name) => page.getByRole('navigation', { name: 'Console' }).getByRole('link', { name });
async function createCongress(page, v) {
  await page.goto('/console/congres/nouveau');
  await page.getByLabel('Titre').fill(v.title);
  await page.getByRole('combobox', { name: 'Discipline', exact: true }).selectOption('Cardiologie');
  await page.getByLabel('Lieu').fill('Salle — exemple');
  await page.getByLabel('Ville').fill('Nice');
  await page.getByRole('combobox', { name: 'Pays', exact: true }).selectOption('France');
  await page.getByLabel('Date de début').fill('2027-07-05');
  await page.getByLabel('Date de fin').fill('2027-07-07');
  await page.getByLabel('Site officiel').fill(v.url || 'https://www.example.org/x');
  await page.getByLabel('Vérifié le').fill('2026-11-01');
  await page.getByRole('button', { name: 'Publier' }).click();
}

test('FIX-1 isolation: a browser that publishes, defaces, edits URLs, adds enquiries and approves access changes nothing for anyone else', async ({ browser }) => {
  const A = await newPage(browser); const B = await newPage(browser);
  // A: Direction defaces and publishes, edits a seed congress (title + official URL), approves the seeded GM&E request
  await login(A.page, 'direction');
  await createCongress(A.page, { title: 'DÉFACEMENT visible de tous — exemple' });
  await expect(A.page.getByText('Congrès créé.')).toBeVisible();
  await A.page.goto('/console/congres/101');
  await A.page.getByLabel('Titre').fill('Congrès piraté — exemple');
  await A.page.getByLabel('Site officiel').fill('https://phishing.example/login');
  await A.page.getByRole('button', { name: 'Enregistrer', exact: true }).click();
  await expect(A.page.getByText('Modifications enregistrées.')).toBeVisible();
  await A.page.goto('/console/gme/acces');
  await A.page.locator('.req').first().getByRole('button', { name: 'Approuver pour 24 h' }).click();
  await A.page.goto(`/congres/${SLUG.onco}`);
  await fillEnquiry(A.page, { name: 'Enquête A (exemple)', out: '2027-01-27', back: '2027-01-31' });
  await A.page.waitForTimeout(3100);
  await A.page.getByRole('button', { name: 'Envoyer la demande' }).click();
  await expect(A.page.locator('[data-ref]')).toHaveText('DV-2026-0007');
  // A sees its own changes, on the public pages too (copy-on-write)
  await A.page.goto('/?q=defacement');
  await expect(A.page.locator('.row')).toHaveCount(1);
  await A.page.goto(`/congres/${SLUG.cardio}`);
  await expect(A.page.locator('h1')).toHaveText('Congrès piraté — exemple');
  await expect(A.page.locator('.facts')).toContainText('phishing.example');
  // B, logged out: seed only
  await B.page.goto('/?q=defacement');
  await expect(B.page.locator('.row')).toHaveCount(0);
  await B.page.goto(`/congres/${SLUG.cardio}`);
  await expect(B.page.locator('h1')).toHaveText('Congrès européen de cardiologie — exemple');
  expect(await B.page.content()).not.toContain('phishing.example');
  await B.page.goto('/');
  await expect(B.page.locator('.bar__n')).toHaveText('12 congrès');
  // B, logged in with the same shared Direction login: seed only
  await login(B.page, 'direction');
  await B.page.goto('/console/congres');
  await expect(B.page.locator('tbody')).not.toContainText('DÉFACEMENT');
  await expect(B.page.locator('tbody')).toContainText('Congrès européen de cardiologie');
  await B.page.goto('/console/demandes');
  await expect(B.page.locator('tbody tr')).toHaveCount(6);
  await B.page.goto('/console/gme/acces');
  await expect(B.page.locator('.req')).toHaveCount(1);
  await expect(B.page.getByRole('button', { name: 'Approuver pour 24 h' })).toBeVisible();
  await B.page.goto('/console/notifications');
  await expect(B.page.locator('.mail')).toHaveCount(6);
  assertClean(A.problems); assertClean(B.problems);
  await A.ctx.close(); await B.ctx.close();
});

test('FIX-2 « Réinitialiser la démo » resets only the caller’s sandbox; the login page says the sandbox is private', async ({ browser }) => {
  const A = await newPage(browser); const B = await newPage(browser);
  for (const P of [A, B]) {
    await P.page.goto('/console/connexion');
    await expect(P.page.locator('.private')).toHaveText('Votre bac à sable est privé : vos essais ne sont visibles que dans ce navigateur.');
    await login(P.page, 'equipe');
    await P.page.goto('/console/demandes/1');
    await P.page.getByRole('button', { name: 'Perdue' }).click();
  }
  await resetSandbox(A.page);
  await A.page.goto('/console/demandes/1');
  await expect(A.page.locator('.head .st')).toHaveText('Gagnée');
  await B.page.goto('/console/demandes/1');
  await expect(B.page.locator('.head .st')).toHaveText('Perdue');
  assertClean(A.problems); assertClean(B.problems);
  await A.ctx.close(); await B.ctx.close();
});

test('FIX-3 nightly cron purges sandboxes older than 24 h and leaves recent ones', async ({ page, browser }) => {
  test.skip(LIVE, 'the scheduled handler can only be triggered on the local runtime; live, the cron registration is checked in X4');
  await login(page, 'equipe');
  await page.goto('/console/demandes/1');
  await page.getByRole('button', { name: 'Perdue' }).click();
  const oldSbx = await sbxOf(page);
  const fresh = await newPage(browser);
  await login(fresh.page, 'equipe');
  await fresh.page.goto('/console/demandes/1');
  await fresh.page.getByRole('button', { name: 'Qualifiée' }).click();
  const newSbx = await sbxOf(fresh.page);
  execFileSync('npx', ['wrangler', 'd1', 'execute', 'asset-voyages-demo', '--local', '--command', `UPDATE sandboxes SET created_at = '2026-01-01T00:00:00.000Z' WHERE id = '${oldSbx}'`], { cwd: ROOT, stdio: 'ignore' });
  expect((await page.request.get('/cdn-cgi/handler/scheduled?cron=0+3+*+*+*')).status()).toBe(200);
  await expect.poll(() => d1Count(`SELECT COUNT(*) AS n FROM enquiries WHERE sbx = '${oldSbx}'`)[0].n).toBe(0);
  expect(d1Count(`SELECT COUNT(*) AS n FROM sandboxes WHERE id = '${oldSbx}'`)[0].n).toBe(0);
  expect(d1Count(`SELECT COUNT(*) AS n FROM enquiries WHERE sbx = '${newSbx}'`)[0].n).toBe(1);
  await page.goto('/console/demandes/1'); // the purged browser falls back to the seed
  await expect(page.locator('.head .st')).toHaveText('Gagnée');
  assertClean(fresh.problems); await fresh.ctx.close();
});

test('FIX-4 official website must be https', async ({ page }) => {
  await login(page, 'direction');
  await createCongress(page, { title: 'Test http — exemple', url: 'http://www.example.org/x' });
  await expect(page.locator('#c-url-e')).toHaveText(/Adresse invalide : elle doit commencer par https:\/\//);
  await page.getByLabel('Site officiel').fill('https://www.example.org/x');
  await page.getByRole('button', { name: 'Publier' }).click();
  await expect(page.getByText('Congrès créé.')).toBeVisible();
});

test('FIX-5 a code can only be shown or requested when vérifié or approuvé; détecté and expiré have no form and refuse the POST', async ({ page }) => {
  await login(page, 'equipe');
  await page.goto('/console/gme');
  for (const [title, msg] of [['Congrès européen de cardiologie', 'Code non vérifié'], ['Congrès européen de dermatologie', 'Code expiré']]) {
    const card = page.locator('.gme', { hasText: title });
    await expect(card.locator('.wait')).toContainText(msg);
    await expect(card.getByRole('button')).toHaveCount(0);
  }
  const origin = new URL(page.url()).origin;
  const req = await page.request.post('/console/gme/101/demande', { form: { _csrf: await csrfOf(page), reason: 'Je veux voir ce code.' }, headers: { origin } });
  expect(req.status()).toBe(403);
  await logout(page);
  await login(page, 'direction');
  await page.goto('/console/gme');
  for (const id of [101, 105]) {
    const r = await page.request.post(`/console/gme/${id}/afficher`, { form: { _csrf: await csrfOf(page) }, headers: { origin } });
    expect(r.status()).toBe(403);
    const t = await r.text();
    for (const c of CODES) expect(t).not.toContain(c);
  }
});

// FIX-6: login throttle. Demo mode (ACCOUNT_LOCKOUT=off, the deployed setting) must never lock a shared account for other
// visitors; production mode (on) adds an account-wide ceiling. Local runs check both modes (a second dev server on :8788
// runs with ACCOUNT_LOCKOUT=on); live runs check the demo mode.
const LOCKOUT_ON_URL = process.env.LOCKOUT_ON_URL || 'http://localhost:8788';
async function attempt(base, user, ip) {
  const headers = ip ? { 'cf-connecting-ip': ip } : {};
  const tok = /name="_token" value="([^"]+)"/.exec(await (await fetch(base + '/console/connexion', { headers })).text())[1];
  const r = await fetch(base + '/console/connexion', { method: 'POST', redirect: 'manual', headers: { ...headers, 'content-type': 'application/x-www-form-urlencoded', origin: base }, body: new URLSearchParams({ _token: tok, username: user, password: 'faux' }) });
  return r.status;
}

test('FIX-6a production mode (ACCOUNT_LOCKOUT=on): 40 parallel guesses from 40 addresses and browsers, at most 30 are checked; atomic counter', async () => {
  test.skip(LIVE, 'production mode is exercised on the local runtime only');
  const user = 'cible' + Date.now();
  const codes = await Promise.all(Array.from({ length: 40 }, (_, i) => attempt(LOCKOUT_ON_URL, user, `10.1.${Math.floor(i / 200)}.${i + 1}`)));
  expect(codes.filter((c) => c === 401).length).toBeLessThanOrEqual(30);
  expect(codes.filter((c) => c === 429).length).toBeGreaterThanOrEqual(10);
  // the same spread attack in demo mode is not locked account-wide (documented trade-off: shared demo accounts stay usable)
  const demo = await Promise.all(Array.from({ length: 40 }, (_, i) => attempt(new URL(BASE).origin, user, `10.2.0.${i + 1}`)));
  expect(demo.filter((c) => c === 401).length).toBe(40);
});

test('FIX-6b demo mode (ACCOUNT_LOCKOUT=off): a flood on « direction » from one browser is capped at 10 checks and never stops another browser logging in', async ({ page, browser }) => {
  await sbxOf(page); // the flooding browser has its sandbox cookie
  const html = await (await page.request.get('/console/connexion')).text();
  const tok = /name="_token" value="([^"]+)"/.exec(html)[1];
  const origin = new URL(BASE).origin;
  const res = await Promise.all(Array.from({ length: 40 }, (_, i) => page.request.post('/console/connexion', { form: { _token: tok, username: 'direction', password: 'faux' + i }, headers: { origin }, maxRedirects: 0 })));
  const codes = res.map((r) => r.status());
  expect(codes.filter((c) => c === 401).length).toBeLessThanOrEqual(10);
  expect(codes.filter((c) => c === 429).length).toBeGreaterThanOrEqual(30);
  const other = await newPage(browser);
  await login(other.page, 'direction'); // Veena's browser is not locked out
  assertClean(other.problems); await other.ctx.close();
});

test('FIX-7 a forged (no CSRF) reveal or request writes nothing, not even a journal row', async ({ page }) => {
  await login(page, 'direction');
  await page.goto('/console/gme');
  const origin = new URL(page.url()).origin;
  for (let i = 0; i < 5; i++) expect((await page.request.post('/console/gme/112/afficher', { form: {}, headers: { origin } })).status()).toBe(403);
  expect((await page.request.post('/console/gme/112/demande', { form: { reason: 'xxxxxxx' }, headers: { origin } })).status()).toBe(403);
  const sbx = await sbxOf(page);
  expect(d1Count(`SELECT (SELECT COUNT(*) FROM gme_access_log WHERE sbx = '${sbx}') AS l, (SELECT COUNT(*) FROM sandboxes WHERE id = '${sbx}') AS s`)[0]).toEqual({ l: 0, s: 0 });
  await page.goto('/console/gme/journal');
  await expect(page.getByText('Aucun affichage enregistré pour l’instant.')).toBeVisible();
});

const lum = (rgb) => { const [r, g, b] = rgb.match(/[\d.]+/g).slice(0, 3).map((v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
const contrast = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((m, n) => n - m); return (x + 0.05) / (y + 0.05); };

test('FIX-8 typed text in the dark enquiry panel is ink on white; placeholders reach 4.5:1', async ({ page }) => {
  await page.goto(`/congres/${SLUG.cardio}`);
  await page.getByLabel('Nom et prénom').fill('Texte saisi');
  const st = await page.evaluate(() => {
    const i = document.getElementById('f-name'); const cs = getComputedStyle(i);
    const ph = getComputedStyle(document.getElementById('q') || i, '::placeholder');
    return { color: cs.color, bg: cs.backgroundColor, ph: getComputedStyle(i, '::placeholder').color };
  });
  expect(contrast(st.color, st.bg)).toBeGreaterThanOrEqual(7);
  expect(contrast(st.ph, st.bg)).toBeGreaterThanOrEqual(4.5);
  await page.goto('/');
  const q = await page.evaluate(() => { const i = document.getElementById('q'); return { ph: getComputedStyle(i, '::placeholder').color, bg: getComputedStyle(i).backgroundColor }; });
  expect(contrast(q.ph, q.bg)).toBeGreaterThanOrEqual(4.5);
});

test('FIX-9 dates read jj/mm/aaaa or « 28 au 30 janv. 2027 »; the notification e-mail uses jj/mm/aaaa and a full URL', async ({ page }) => {
  await page.goto(`/congres/${SLUG.onco}`);
  await expect(page.locator('.facts')).toContainText('28 au 30 janv. 2027');
  await expect(page.locator('.facts')).toContainText('12/10/2026');
  const text = await page.locator('main').innerText();
  expect(text).not.toMatch(/\b20\d\d-\d\d-\d\d\b/);
  await fillEnquiry(page, { out: '2027-01-27', back: '2027-01-31' });
  await page.waitForTimeout(3100);
  await page.getByRole('button', { name: 'Envoyer la demande' }).click();
  await login(page, 'equipe');
  await page.goto('/console/notifications');
  const mail = await page.locator('.mail pre').first().innerText();
  expect(mail).toContain('aller le 27/01/2027, retour le 31/01/2027');
  expect(mail).toMatch(/Ouvrir dans la console : https?:\/\/[^\s]+\/console\/demandes\/7/);
  if (LIVE) expect(mail).toContain(`${new URL(BASE).origin}/console/demandes/7`);
  for (const u of ['/console', '/console/demandes', '/console/demandes/7', '/console/gme']) {
    await page.goto(u);
    expect(await page.locator('main').innerText(), u).not.toMatch(/\b20\d\d-\d\d-\d\d\b/);
  }
});

test('FIX-10 skip link only appears on keyboard focus; after an error or a redirect focus moves to the message', async ({ page }) => {
  await page.goto('/');
  expect((await page.locator('.skip').boundingBox()).y).toBeLessThan(0);
  await page.keyboard.press('Tab');
  await expect(page.locator('.skip')).toBeFocused();
  expect((await page.locator('.skip').boundingBox()).y).toBeGreaterThanOrEqual(0);
  await page.goto(`/congres/${SLUG.cardio}`);
  await page.waitForTimeout(3100);
  await page.getByRole('button', { name: 'Envoyer la demande' }).click();
  await expect(page.locator('#form-errors')).toBeFocused();
  await login(page, 'equipe');
  await page.goto('/console/demandes/1');
  await page.getByRole('button', { name: 'Qualifiée' }).click();
  await expect(page.locator('.ok')).toBeFocused();
});

test('FIX-11 FIX-12 at 390 px the console menu wraps with the active tab visible, and table rows become cards with every field labelled', async ({ browser }) => {
  const P = await newPage(browser, { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  const page = P.page;
  await login(page, 'direction');
  for (const u of ['/console/demandes', '/console/congres', '/console/gme/journal']) {
    await page.goto(u);
    const nav = await page.evaluate(() => {
      const side = document.querySelector('.side');
      const links = [...side.querySelectorAll('a')].map((a) => a.getBoundingClientRect());
      const cur = side.querySelector('[aria-current]').getBoundingClientRect();
      return { scroll: side.scrollWidth - side.clientWidth, outside: links.filter((r) => r.right > innerWidth || r.left < 0).length, cur: cur.right <= innerWidth && cur.left >= 0 };
    });
    expect(nav, u).toEqual({ scroll: 0, outside: 0, cur: true });
  }
  await page.goto('/console/demandes');
  const card = await page.evaluate(() => {
    const tr = document.querySelector('.tbl tbody tr');
    const tds = [...tr.querySelectorAll('td')];
    return { display: getComputedStyle(tr).display, labels: tds.map((td) => getComputedStyle(td, '::before').content), right: tr.getBoundingClientRect().right };
  });
  expect(card.display).toBe('block');
  expect(card.labels).toEqual(['"Réf."', '"Statut"', '"Reçue"', '"Congrès"', '"Contact"', '"Voyage"', '"Responsable"']);
  expect(card.right).toBeLessThanOrEqual(390);
  assertClean(P.problems); await P.ctx.close();
});

test('FIX-13 the audit trail names a person: history, approvals and the access journal', async ({ page }) => {
  await login(page, 'equipe');
  await page.goto('/console/demandes/2');
  await expect(page.locator('.hist')).toContainText('Karim Benali, Équipe');
  await page.getByRole('button', { name: 'Gagnée' }).click();
  await expect(page.locator('.hist li').last()).toContainText('Karim Benali, Équipe');
  await logout(page);
  await login(page, 'direction');
  await page.goto('/console/gme/acces');
  await expect(page.locator('.req').first()).toContainText('Karim Benali, Équipe');
  await page.locator('.req').first().getByRole('button', { name: 'Approuver pour 24 h' }).click();
  await expect(page.locator('.req').first()).toContainText('Accordé par Hélène Martin, Direction');
  await page.goto('/console/gme');
  await page.locator('form[action="/console/gme/112/afficher"] button').click();
  await page.goto('/console/gme/journal');
  await expect(page.locator('tbody tr').first()).toContainText('Hélène Martin, Direction');
});

test('FIX-14 FIX-15 the prefilled congress is plain text, not truncated, and « — exemple » never breaks from its title', async ({ browser }) => {
  for (const w of [1440, 390]) {
    const P = await newPage(browser, { viewport: { width: w, height: 900 } });
    await P.page.goto(`/congres/${SLUG.onco}`);
    const el = P.page.locator('[data-congress]');
    await expect(el).toHaveText('Journées d’oncologie digestive — exemple, 28 au 30 janv. 2027');
    expect(await el.evaluate((e) => e.tagName)).toBe('P');
    expect(await el.evaluate((e) => e.scrollWidth <= e.clientWidth)).toBe(true);
    const html = await P.page.content();
    expect(html).not.toMatch(/digestive — exemple/);
    expect(html).toContain('digestive&nbsp;—&nbsp;exemple');
    assertClean(P.problems); await P.ctx.close();
  }
});

test('FIX-16 dashboard tiles use the plural when the count is above one', async ({ page }) => {
  await login(page, 'equipe');
  await expect(page.locator('[data-count="nouvelle"]')).toContainText('2Nouvelles');
  await expect(page.locator('[data-count="gagnee"]')).toContainText('1Gagnée');
});

test('FIX-17 at 390 px a cross-month congress reads « 29 sept. au 2 oct. 2027 »', async ({ browser }) => {
  const P = await newPage(browser, { viewport: { width: 390, height: 844 }, isMobile: true });
  await P.page.goto('/?q=dermatologie');
  await expect(P.page.locator('.row__line')).toBeVisible();
  await expect(P.page.locator('.row__line')).toHaveText('29 sept. au 2 oct. 2027');
  await expect(P.page.locator('.row__date')).toBeHidden();
  assertClean(P.problems); await P.ctx.close();
});

test('FIX-18 the no-result state offers « Nous écrire »', async ({ page }) => {
  await page.goto('/?q=zzzz');
  const a = page.getByRole('link', { name: 'Nous écrire' });
  await expect(a).toBeVisible();
  expect(await a.getAttribute('href')).toMatch(/^mailto:congres@example\.com/);
});

test('FIX-19 after a reveal « Masquer le code » hides it again', async ({ page }) => {
  await login(page, 'direction');
  await page.goto('/console/gme');
  await page.locator('form[action="/console/gme/112/afficher"] button').click();
  await expect(page.locator('[data-revealed]')).toContainText('DEMO-GME-4821');
  await page.getByRole('link', { name: 'Masquer le code' }).click();
  await expect(page.locator('[data-revealed]')).toHaveCount(0);
  for (const c of CODES) expect(await page.content()).not.toContain(c);
});

test('FIX-20 status badges have room around their text', async ({ page }) => {
  await login(page, 'direction');
  await page.goto('/console/congres/112');
  const st = await page.locator('.gme .st').first().evaluate((e) => { const cs = getComputedStyle(e); return { pl: parseFloat(cs.paddingLeft), pt: parseFloat(cs.paddingTop), h: e.getBoundingClientRect().height }; });
  expect(st.pl).toBeGreaterThanOrEqual(12);
  expect(st.pt).toBeGreaterThanOrEqual(4);
  expect(st.h).toBeGreaterThanOrEqual(26);
});

// ---- blind QA follow-up (D1 to D6) ----

test('FIX-21 (D1) Discipline and Pays come from managed lists; Direction adds a value; duplicates and free text are refused', async ({ page }) => {
  await login(page, 'direction');
  await page.goto('/console/congres/nouveau');
  expect(await page.getByRole('combobox', { name: 'Discipline', exact: true }).evaluate((e) => e.tagName)).toBe('SELECT');
  expect(await page.getByRole('combobox', { name: 'Pays', exact: true }).evaluate((e) => e.tagName)).toBe('SELECT');
  await page.getByLabel('Ajouter une discipline').fill('Hématologie');
  await page.locator('form[action="/console/listes"]').first().getByRole('button', { name: 'Ajouter' }).click();
  await expect(page.getByText('Valeur ajoutée à la liste.')).toBeVisible();
  await page.getByRole('combobox', { name: 'Discipline', exact: true }).selectOption('Hématologie');
  await page.getByLabel('Ajouter une discipline').fill('hematologie');
  await page.locator('form[action="/console/listes"]').first().getByRole('button', { name: 'Ajouter' }).click();
  await expect(page.getByText('Cette valeur existe déjà dans la liste')).toBeVisible();
  // a forged free-text value is refused server-side
  await logout(page);
  await login(page, 'equipe');
  await page.goto('/console/congres/nouveau');
  const origin = new URL(page.url()).origin;
  const csrf = await csrfOf(page);
  const free = await page.request.post('/console/congres/nouveau', { form: { _csrf: csrf, action: 'publish', title: 'Faute — exemple', discipline: 'Cardiolgie', venue: 'X — exemple', city: 'Nice', country: 'Frnace', start_date: '2027-07-05', end_date: '2027-07-07', official_url: 'https://www.example.org/x', verified_on: '2026-11-01' }, headers: { origin } });
  const t = await free.text();
  expect(t).toContain('Choisissez une discipline de la liste.');
  expect(t).toContain('Choisissez un pays de la liste.');
  expect((await page.request.post('/console/listes', { form: { _csrf: csrf, kind: 'discipline', value: 'Cardiolgie' }, headers: { origin } })).status()).toBe(403);
  await expect(page.locator('form[action="/console/listes"]')).toHaveCount(0);
});

test('FIX-22 (D2) the sidebar groups the GM&E items under « Codes GM&E »: Codes, Demandes d’accès, Journal', async ({ page }) => {
  await login(page, 'direction');
  const side = page.getByRole('navigation', { name: 'Console' });
  await expect(side.locator('.side__h')).toHaveText('Codes GM&E');
  await expect(side.locator('a.side__sub')).toHaveText([/^Codes/, /^Demandes d’accès/, /^Journal/]);
  await logout(page);
  await login(page, 'equipe');
  await expect(page.getByRole('navigation', { name: 'Console' }).locator('a.side__sub')).toHaveText([/^Codes/]);
});

test('FIX-23 FIX-24 (D3, D4) failed enquiry: 200 page, top banner lists each error as a link to its field, focus on the banner, visible on a phone', async ({ browser }) => {
  for (const w of [1440, 390]) {
    const P = await newPage(browser, { viewport: { width: w, height: w > 500 ? 900 : 844 }, isMobile: w < 500 });
    const page = P.page;
    await page.goto(`/congres/${SLUG.cardio}`);
    await fillEnquiry(page, { out: '2027-08-30', back: '2027-08-20', email: 'x@y' });
    await page.waitForTimeout(3100);
    const [resp] = await Promise.all([page.waitForResponse((r) => r.url().endsWith('/demande')), page.getByRole('button', { name: 'Envoyer la demande' }).click()]);
    expect(resp.status()).toBe(200);
    const banner = page.locator('#form-errors');
    await expect(banner).toBeFocused();
    await expect(banner).toBeInViewport();
    await expect(banner.getByRole('link', { name: /^Date retour : La date retour doit être le jour de l’aller ou après\.$/ })).toBeVisible();
    await expect(banner.getByRole('link', { name: /^E-mail : / })).toBeVisible();
    await banner.getByRole('link', { name: /^Date retour/ }).click();
    await expect(page.locator('#f-back')).toBeFocused();
    assertClean(P.problems); await P.ctx.close();
  }
});

test('FIX-24 (D4) a failed congress save re-renders with 200 and the linked summary', async ({ page }) => {
  await login(page, 'equipe');
  await page.goto('/console/congres/nouveau');
  const [resp] = await Promise.all([page.waitForResponse((r) => r.url().endsWith('/console/congres/nouveau') && r.request().method() === 'POST'), page.getByRole('button', { name: 'Publier' }).click()]);
  expect(resp.status()).toBe(200);
  await expect(page.locator('#form-errors')).toBeFocused();
  await expect(page.locator('#form-errors').getByRole('link', { name: 'Titre : Indiquez le titre.' })).toBeVisible();
});

test('FIX-25 (D5) ten enquiries in ten minutes are accepted per browser; the eleventh gets a clear French message, never a silent no-op', async ({ browser }) => {
  const A = await newPage(browser);
  const page = A.page;
  for (let i = 0; i < 11; i++) {
    await page.goto(`/congres/${SLUG.cardio}`);
    await fillEnquiry(page, { name: `Bureau ${i} (exemple)` });
    await page.waitForTimeout(3100);
    await page.getByRole('button', { name: 'Envoyer la demande' }).click();
    if (i < 10) await expect(page.locator('[data-ref]'), `submission ${i + 1}`).toHaveText(/^DV-2026-\d{4}$/);
  }
  const msg = page.locator('.alert--top');
  await expect(msg).toBeFocused();
  await expect(msg).toBeInViewport();
  await expect(msg).toContainText('Votre demande n’a pas été envoyée : trop de demandes depuis ce navigateur en 10 minutes');
  await expect(page.getByLabel('Nom et prénom')).toHaveValue('Bureau 10 (exemple)');
  // a colleague's browser behind the same IP is not blocked
  const B = await newPage(browser);
  await B.page.goto(`/congres/${SLUG.cardio}`);
  await fillEnquiry(B.page, { name: 'Collègue (exemple)' });
  await B.page.waitForTimeout(3100);
  await B.page.getByRole('button', { name: 'Envoyer la demande' }).click();
  await expect(B.page.locator('[data-ref]')).toHaveText('DV-2026-0007');
  assertClean(A.problems); assertClean(B.problems);
  await A.ctx.close(); await B.ctx.close();
});

test('FIX-26 (D6) the date line reads « 29 sept. au 2 oct. 2027 » on desktop and phone', async ({ browser }) => {
  for (const w of [1440, 390]) {
    const P = await newPage(browser, { viewport: { width: w, height: 900 } });
    await P.page.goto('/?q=dermatologie');
    const row = P.page.locator('.row__a');
    await expect(row.locator('.row__line')).toHaveText('29 sept. au 2 oct. 2027'); // read by screen readers at every width
    if (w > 500) await expect(row.locator('.row__date')).toHaveText('29 sept. au 2 oct.2027');
    else await expect(row.locator('.row__line')).toBeVisible();
    await P.page.goto('/?q=madrid');
    await expect(P.page.locator('.row__line')).toHaveText('27 au 30 août 2027');
    assertClean(P.problems); await P.ctx.close();
  }
});
