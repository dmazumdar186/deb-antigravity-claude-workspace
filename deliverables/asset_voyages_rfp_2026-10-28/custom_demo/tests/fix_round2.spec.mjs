// Fix round 2 (independent battery: security, flakes, UX/a11y/eye, monkey gap): one regression test per item (FIX2-n).
import { test, expect, login, logout, csrfOf, fillEnquiry, SLUG, CODES, CODE_RE, LIVE, BASE, CTX, ROOT, newPage, assertClean, sbxOf, d1Count, resetSandbox, TEST_KEY } from './helpers.mjs';
import { execFileSync } from 'node:child_process';

const ORIGIN = new URL(BASE).origin;
const uniqIp = (n) => `10.${(Date.now() >> 8) % 250}.${(Date.now() >> 16) % 250}.${n}`;
const local = (t) => test.skip(LIVE, `${t}: needs a spoofable client IP or the local cron trigger, only possible on the local runtime`);
const sqlLocal = (q) => execFileSync('npx', ['wrangler', 'd1', 'execute', 'asset-voyages-demo', '--local', '--command', q], { cwd: ROOT, stdio: 'ignore' });
async function token(ip, cookie) {
  const headers = { 'cf-connecting-ip': ip, ...(cookie ? { cookie } : {}) };
  return /name="_token" value="([^"]+)"/.exec(await (await fetch(`${ORIGIN}/congres/${SLUG.cardio}`, { headers })).text())[1];
}
async function postEnquiryRaw(ip, tok, extra = {}) {
  const body = new URLSearchParams({ _token: tok, congress: '101', name: 'Cap (exemple)', email: 'cap@example.com', phone: '0123456789', company: '', departure_city: 'Lille', date_out: '2027-08-26', date_back: '2027-08-31', passengers: '2', message: '', consent: '1', zx_confirm: '', ...extra });
  const r = await fetch(`${ORIGIN}/demande`, { method: 'POST', redirect: 'manual', headers: { 'cf-connecting-ip': ip, 'content-type': 'application/x-www-form-urlencoded', origin: ORIGIN }, body });
  return { status: r.status, text: await r.text(), location: r.headers.get('location') };
}

test('FIX2-1 FIX2-2 (ADV-B-009/010) at most 20 new sandboxes per IP a day; beyond, a calm banner on the read-only seed, never a bare 429', async ({ browser }) => {
  local('FIX2-1');
  const ip = uniqIp(1);
  const toks = [];
  for (let i = 0; i < 21; i++) toks.push(await token(ip)); // cookieless: every write would be a new sandbox
  await new Promise((r) => setTimeout(r, 3100));
  const res = [];
  for (let i = 0; i < 21; i++) res.push(await postEnquiryRaw(ip, toks[i], { name: `Cap ${i} (exemple)` }));
  expect(res.slice(0, 20).map((r) => r.status)).toEqual(Array(20).fill(303));
  expect(res[20].status).toBe(200);
  expect(res[20].text).toContain('Votre demande n’a pas été envoyée. Démo très demandée : vous pouvez parcourir, les essais reprennent dans quelques minutes.');
  // console path from the same capped IP: redirected back to the page, seed shown, banner, nothing written
  const P = await newPage(browser, { extraHTTPHeaders: { 'cf-connecting-ip': ip } });
  await login(P.page, 'equipe');
  await P.page.goto('/console/demandes/1');
  await P.page.getByRole('button', { name: 'Perdue' }).click();
  await expect(P.page).toHaveURL(/\/console\/demandes\/1\?demo=complet$/);
  await expect(P.page.locator('.busy')).toHaveText('Démo très demandée : vous pouvez parcourir, les essais reprennent dans quelques minutes.');
  await expect(P.page.locator('.head .st')).toHaveText('Gagnée');
  assertClean(P.problems); await P.ctx.close();
  // the global cap is computed from the D1 free write budget (see README)
  const data = (await import('node:fs')).readFileSync(`${ROOT}/src/data.js`, 'utf8');
  expect(data).toMatch(/SBX_DAILY_LIMIT = Math\.floor\(\(100000 - RESERVED_ROWS\) \/ ROWS_PER_SESSION\)/);
});

test('FIX2-3 (ADV-B-011) the per-IP login counter is incremented first and atomically: 60 parallel failures over 60 usernames, at most 50 checked', async () => {
  local('FIX2-3');
  const ip = uniqIp(3);
  const attempt = async (i) => {
    const t = /name="_token" value="([^"]+)"/.exec(await (await fetch(`${ORIGIN}/console/connexion`, { headers: { 'cf-connecting-ip': ip } })).text())[1];
    const r = await fetch(`${ORIGIN}/console/connexion`, { method: 'POST', redirect: 'manual', headers: { 'cf-connecting-ip': ip, 'content-type': 'application/x-www-form-urlencoded', origin: ORIGIN }, body: new URLSearchParams({ _token: t, username: `essai${i}`, password: 'faux' }) });
    return r.status;
  };
  const codes = await Promise.all(Array.from({ length: 60 }, (_, i) => attempt(i)));
  expect(codes.filter((c) => c === 401).length).toBeLessThanOrEqual(50);
  expect(codes.filter((c) => c === 429).length).toBeGreaterThanOrEqual(10);
});

test('FIX2-4 (ADV-B-012) the nightly purge removes orphan rows; a first write over a leftover row never collides', async ({ page }) => {
  local('FIX2-4');
  const orphan = 'orphan' + Date.now().toString(36).padEnd(14, 'x');
  sqlLocal(`INSERT INTO enquiry_events (sbx, enquiry_id, id, at, user_id, kind, from_val, to_val) VALUES ('${orphan}', 1, '2026-01-01-x', '2026-01-01', 1, 'note', NULL, 'orpheline')`);
  // a leftover row under a browser's id before its sandbox exists (a write that raced a reset): the first write upserts
  const sbx = await sbxOf(page);
  sqlLocal(`INSERT INTO enquiries (sbx, id, ref, congress_id, name, email, phone, departure_city, date_out, date_back, passengers, consent_at, status, created_at, updated_at) VALUES ('${sbx}', 2, 'DV-2026-0002', 103, 'Restante (exemple)', 'r@example.com', '0100000000', 'Lille', '2027-08-26', '2027-08-31', 1, '2026-01-01', 'nouvelle', '2026-01-01', '2026-01-01')`);
  await login(page, 'equipe');
  await page.goto('/console/demandes/2');
  await page.getByRole('button', { name: 'Perdue' }).click();
  await expect(page.locator('.ok')).toHaveText('Statut mis à jour : Perdue.');
  expect(d1Count(`SELECT COUNT(*) AS n FROM enquiries WHERE sbx = '${sbx}'`)[0].n).toBe(1);
  expect((await page.request.get('/cdn-cgi/handler/scheduled?cron=0+3+*+*+*')).status()).toBe(200);
  await expect.poll(() => d1Count(`SELECT COUNT(*) AS n FROM enquiry_events WHERE sbx = '${orphan}'`)[0].n).toBe(0);
  expect(d1Count(`SELECT COUNT(*) AS n FROM enquiries WHERE sbx = '${sbx}'`)[0].n).toBe(1); // live sandboxes untouched
});

test('FIX2-5 (X4 flake) reset is fast and idempotent: five resets in a row, each answered in under 3 s with the banner; tables clustered on sbx', async ({ page }) => {
  // Root cause of the live X4 failure: the page body was « upstream request failed », the agent egress proxy's own error
  // text (the Worker never emits it). The reset itself is idempotent; the indexes keep it a few milliseconds at any data size.
  await login(page, 'direction');
  for (let i = 0; i < 5; i++) {
    await page.goto('/console');
    const t0 = Date.now();
    await page.getByRole('button', { name: 'Réinitialiser la démo' }).click();
    await expect(page.getByText('La démonstration a été réinitialisée')).toBeVisible();
    expect(Date.now() - t0).toBeLessThan(3000);
  }
  // every sandbox-scoped table is clustered on its sandbox id (WITHOUT ROWID, primary key starting with sbx)
  const clustered = d1Count(`SELECT COUNT(*) AS n FROM sqlite_master WHERE type = 'table' AND name IN ('congresses','enquiries','enquiry_events','congress_events','gme_codes','gme_requests','gme_access_log','options') AND sql LIKE '%PRIMARY KEY (sbx,%' AND sql LIKE '%WITHOUT ROWID%'`)[0].n;
  expect(clustered).toBe(8);
});

test('FIX2-6 (S2-F2 flake) search is deterministic while sandboxes are being copied: 30 parallel « sommet rh » searches all find CG-0109', async ({ browser }) => {
  // Root cause: the old test read the rows right after clicking « Rechercher », before the results page had loaded
  // (it saw the blank page between documents). The server answer never varied; S2-F2 now waits for the results URL.
  const writers = await Promise.all(Array.from({ length: 5 }, () => newPage(browser)));
  const copying = writers.map(async (w) => { await login(w.page, 'equipe'); await w.page.goto('/console/demandes/2'); await w.page.getByRole('button', { name: 'Perdue' }).click(); });
  const searches = Array.from({ length: 30 }, async () => {
    const ctx = await browser.newContext(CTX);
    const body = await (await ctx.request.get('/?q=sommet+rh')).text();
    await ctx.close();
    return /href="\/congres\/[^"]*cg-0109"/.test(body);
  });
  const [found] = await Promise.all([Promise.all(searches), Promise.all(copying)]);
  expect(found.every(Boolean)).toBe(true);
  for (const w of writers) { assertClean(w.problems); await w.ctx.close(); }
});

test('FIX2-7 (USAB-B-011) console tables fit their box at 1440, 1280 and 1024: no hidden horizontal scroll, every key field visible', async ({ browser }) => {
  for (const w of [1440, 1280, 1024]) {
    const P = await newPage(browser, { viewport: { width: w, height: 900 } });
    await login(P.page, 'direction');
    for (const u of ['/console/demandes', '/console/congres', '/console/gme/journal']) {
      await P.page.goto(u);
      const r = await P.page.evaluate(() => [...document.querySelectorAll('.wrap')].map((el) => ({ sw: el.scrollWidth, cw: el.clientWidth })));
      for (const x of r) expect(x.sw, `${u} at ${w}`).toBeLessThanOrEqual(x.cw + 1);
    }
    await P.page.goto('/console/demandes');
    const row = P.page.locator('tbody tr').first();
    for (const label of ['Statut', 'Contact', 'Voyage', 'Responsable']) await expect(row.locator(`td[data-label="${label}"]`)).toBeInViewport();
    assertClean(P.problems); await P.ctx.close();
  }
});

test('FIX2-8 FIX2-9 (A11Y-B-001/002) sidebar links have no aria-label (names start with the visible text); the masked code uses hidden text, not aria-label on <p>', async ({ page }) => {
  await login(page, 'direction');
  await page.goto('/console/gme');
  expect(await page.locator('.side a[aria-label]').count()).toBe(0);
  const link = page.locator('.side a', { hasText: 'Demandes d’accès' });
  expect((await link.evaluate((a) => a.textContent)).replace(/\s+/g, ' ').trim()).toBe('Demandes d’accès GM&E 1 en attente');
  await expect(page.getByRole('link', { name: 'Demandes d’accès GM&E 1 en attente' })).toBeVisible();
  expect(await page.locator('p.code[aria-label]').count()).toBe(0);
  const masked = page.locator('.gme', { hasText: 'oncologie digestive' }).locator('p.code');
  await expect(masked.locator('[aria-hidden="true"]')).toHaveText('•••• •••• ••••');
  await expect(masked.locator('.sr')).toHaveText('Code masqué');
});

test('FIX2-10 (EYE-B-011) contributor home: « 12 Publiés », « 1 Brouillon »', async ({ page }) => {
  await login(page, 'contributeur');
  const tiles = await page.locator('.tile').allInnerTexts();
  expect(tiles.map((t) => t.replace(/\s+/g, ' ').trim())).toEqual(['1 Brouillon', '0 À relire', '12 Publiés']);
});

test('FIX2-11 (USAB-B-012) on a phone, a filter jumps to the results', async ({ browser }) => {
  const P = await newPage(browser, { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  await P.page.goto('/');
  expect(await P.page.locator('.chips a', { hasText: 'Cardiologie' }).getAttribute('href')).toMatch(/#resultats$/);
  expect(await P.page.locator('form.filters').getAttribute('action')).toBe('/#resultats');
  await P.page.locator('.chips a', { hasText: 'Cardiologie' }).click();
  await expect(P.page.locator('.bar__n')).toHaveText('2 congrès trouvés');
  await expect(P.page.locator('.bar__n')).toBeInViewport();
  await P.page.getByLabel('Recherche').fill('lyon');
  await P.page.getByRole('button', { name: 'Rechercher' }).click();
  await P.page.waitForURL(/q=lyon/);
  await expect(P.page.locator('.bar__n')).toBeInViewport();
  assertClean(P.problems); await P.ctx.close();
});

test('FIX2-12 cosmetics: unbroken password, refs, phones and dates; contact stays in its card column; badge inside its column; one-line sidebar; specific messages', async ({ browser }) => {
  // desktop checks
  const D = await newPage(browser);
  const page = D.page;
  await page.goto('/console/connexion');
  expect(await page.locator('.login__demo code').first().evaluate((e) => getComputedStyle(e).whiteSpace)).toBe('nowrap');
  await page.goto('/?q=dermatologie');
  const days = page.locator('.row__days');
  await expect(days).toHaveText('29 sept. au 2 oct.');
  const lines = await days.evaluate((e) => Math.round(e.getBoundingClientRect().height / parseFloat(getComputedStyle(e).lineHeight)));
  expect(lines).toBeLessThanOrEqual(2);
  await login(page, 'direction');
  const side = await page.locator('.side a', { hasText: 'Demandes d’accès' }).evaluate((e) => e.getBoundingClientRect().height);
  expect(side).toBeLessThanOrEqual(48);
  await page.goto('/console/gme');
  const fit = await page.locator('.gme', { hasText: 'oncologie digestive' }).locator('dd .st').evaluate((e) => e.getBoundingClientRect().right <= e.closest('dd').getBoundingClientRect().right + 0.5);
  expect(fit).toBe(true);
  await page.goto('/console/congres/112');
  expect(await page.locator('.manage summary').getAttribute('class')).toContain('btn');
  await page.goto('/console/demandes/3');
  await page.getByRole('button', { name: 'Devis envoyé' }).click();
  await expect(page.locator('.ok')).toHaveText('Statut mis à jour : Devis envoyé.');
  await page.goto('/console/congres/101');
  await page.getByRole('button', { name: 'Archiver' }).click();
  await expect(page.locator('.ok')).toHaveText('Archivé : la fiche n’est plus sur le site.');
  assertClean(D.problems); await D.ctx.close();
  // phone checks
  const M = await newPage(browser, { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  const m = M.page;
  await m.goto('/');
  const titles = await m.locator('.row__t').allTextContents();
  for (const t of titles) expect(t).toMatch(/ — exemple$/);
  await login(m, 'equipe');
  await m.goto('/console/demandes');
  const card = await m.locator('tbody tr').first().evaluate((tr) => {
    const contact = tr.querySelector('td[data-label="Contact"]');
    const ref = tr.querySelector('td[data-label="Réf."] a');
    return { kids: contact.children.length, refLines: Math.round(ref.getBoundingClientRect().height / 44) };
  });
  expect(card.kids).toBe(1); // both contact lines live inside the value column
  expect(card.refLines).toBe(1);
  await m.goto('/console/demandes/6');
  expect(await m.locator('.facts dd .nw').first().evaluate((e) => getComputedStyle(e).whiteSpace)).toBe('nowrap');
  await m.goto('/console/notifications');
  const pre = m.locator('.mail pre').first();
  expect(await pre.locator('.nw').count()).toBeGreaterThanOrEqual(2);
  expect(await pre.innerHTML()).toContain('/<wbr>');
  const nav = await m.locator('.side a').last().evaluate((a) => ({ w: a.getBoundingClientRect().width, side: a.parentElement.getBoundingClientRect().width }));
  expect(nav.w).toBeGreaterThan(nav.side * 0.8); // « Voir le site public » on its own row
  await expect(m.locator('.ctop__who')).toBeVisible();
  assertClean(M.problems); await M.ctx.close();
  // confirmation rhythm
  const C = await newPage(browser);
  await C.page.goto(`/congres/${SLUG.cardio}`);
  await fillEnquiry(C.page);
  await C.page.waitForTimeout(3100);
  await C.page.getByRole('button', { name: 'Envoyer ma demande' }).click();
  await expect(C.page.locator('[data-ref]')).toBeVisible();
  const gap = await C.page.evaluate(() => { const h = document.querySelector('.thanks h1').getBoundingClientRect(); const l = document.querySelector('.thanks .lead').getBoundingClientRect(); return l.top - h.bottom; });
  expect(gap).toBeGreaterThanOrEqual(32);
  expect(await C.page.locator('.thanks p .lnk').evaluate((e) => getComputedStyle(e).display)).toBe('inline');
  assertClean(C.problems); await C.ctx.close();
});

test('FIX2-13 (monkey gap) no seeded code in any input or textarea value, typed or rendered, for any role before an explicit reveal', async ({ page }) => {
  const scan = async (where) => {
    const vals = await page.evaluate(() => [...document.querySelectorAll('input, textarea, select')].map((e) => e.value));
    for (const v of vals) { expect(v, where).not.toMatch(CODE_RE.source ? new RegExp(CODE_RE.source) : /DEMO-GME-/); expect(v, where).not.toContain('DEMO-GME-'); }
  };
  const pages = ['/console', '/console/gme', '/console/congres/112', '/console/congres/103', '/console/congres/nouveau', '/console/demandes/1', '/console/notifications', '/console/gme/acces', '/console/gme/journal'];
  for (const role of ['direction', 'equipe', 'contributeur']) {
    await login(page, role);
    for (const u of pages) { const r = await page.goto(u); if (r.status() === 200) await scan(`${role} ${u}`); }
    await logout(page);
  }
  for (const u of ['/', `/congres/${SLUG.onco}`, '/console/connexion']) { await page.goto(u); await scan(`anon ${u}`); }
});
