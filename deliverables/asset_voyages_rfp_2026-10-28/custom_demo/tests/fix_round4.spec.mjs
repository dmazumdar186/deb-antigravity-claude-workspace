// Fix round 4 (security re-check): write budget guards, per-purpose MAC keys, exact token shape (FIX4-n).
import { test, expect, login, logout, csrfOf, SLUG, LIVE, ROOT, newPage, assertClean, sbxOf, d1Count, postEnquiry, journey } from './helpers.mjs';
import { readFileSync, readdirSync } from 'node:fs';
import { execFileSync } from 'node:child_process';

const src = (f) => readFileSync(`${ROOT}/src/${f}`, 'utf8');
const sqlLocal = (q) => execFileSync('npx', ['wrangler', 'd1', 'execute', 'asset-voyages-demo', '--local', '--command', q], { cwd: ROOT, stdio: 'ignore' });
// stay inside one 10-minute throttle window for the whole test
async function freshWindow() {
  const left = 600 - (Math.floor(Date.now() / 1000) % 600);
  if (left < 90) await new Promise((r) => setTimeout(r, (left + 2) * 1000));
}

test('FIX4-1 (ADV-B-207) one browser gets 60 writes per 10 minutes; the 61st degrades to the calm banner and writes nothing', async ({ page }) => {
  test.setTimeout(240_000);
  await freshWindow();
  await login(page, 'equipe');
  await page.goto('/console/demandes/1');
  const csrf = await csrfOf(page);
  const origin = new URL(page.url()).origin;
  const codes = [];
  for (let i = 0; i < 60; i++) codes.push((await page.request.post('/console/demandes/1', { form: { _csrf: csrf, action: 'note', note: `n${i}` }, headers: { origin }, maxRedirects: 0 })).status());
  expect(codes.every((c) => c === 303)).toBe(true);
  const sbx = await sbxOf(page);
  const before = d1Count(`SELECT COUNT(*) AS n FROM enquiry_events WHERE sbx = '${sbx}'`)[0].n;
  expect(before).toBe(60);
  const r61 = await page.request.post('/console/demandes/1', { form: { _csrf: csrf, action: 'note', note: 'de trop' }, headers: { origin, referer: `${origin}/console/demandes/1` }, maxRedirects: 0 });
  expect(r61.status()).toBe(303);
  expect(r61.headers().location).toBe('/console/demandes/1?demo=pause');
  expect(d1Count(`SELECT COUNT(*) AS n FROM enquiry_events WHERE sbx = '${sbx}'`)[0].n).toBe(60);
  await page.goto('/console/demandes/1?demo=pause');
  await expect(page.locator('.busy')).toContainText('Beaucoup d’essais en peu de temps');
  // the enquiry form says so too, and keeps what was typed
  const enq = await postEnquiry(page.request, SLUG.cardio, { name: 'Après la pause (exemple)' });
  expect(enq.res.status()).toBe(200);
  expect(enq.text).toContain('Votre demande n’a pas été envoyée. Beaucoup d’essais en peu de temps');
  // another browser is not affected
  const B = await newPage(page.context().browser());
  await login(B.page, 'equipe');
  await B.page.goto('/console/demandes/1');
  await B.page.getByLabel('Visible uniquement par l’équipe').fill('Autre navigateur.');
  await B.page.getByRole('button', { name: 'Ajouter la note' }).click();
  await expect(B.page.locator('.ok')).toHaveText('Note ajoutée à l’historique.');
  assertClean(B.problems); await B.ctx.close();
});

test('FIX4-2 (ADV-B-207) at the global daily write ceiling every write path shows the read-only seed and the banner, never a 500', async ({ page }) => {
  test.skip(LIVE, 'needs to set the global counter directly, only on the local database');
  const day = new Date().toISOString().slice(0, 10);
  const limit = Number(/WALL_LIMIT = (\d+)/.exec(src('data.js'))[1]);
  expect(limit).toBeLessThanOrEqual(85000);
  sqlLocal(`INSERT INTO rate_limits (key, count, reset_at) VALUES ('wall:${day}', ${limit}, 4102444800) ON CONFLICT(key) DO UPDATE SET count = ${limit}`);
  try {
    await login(page, 'equipe');
    await page.goto('/console/demandes/1');
    await page.getByRole('button', { name: 'Perdue' }).click();
    await expect(page).toHaveURL(/\/console\/demandes\/1\?demo=complet$/);
    await expect(page.locator('.busy')).toHaveText('Démo très demandée : vous pouvez parcourir, les essais reprennent dans quelques minutes.');
    await expect(page.locator('.head .st')).toHaveText('Gagnée');
    const enq = await postEnquiry(page.request, SLUG.cardio, {});
    expect(enq.res.status()).toBe(200);
    expect(enq.text).toContain('Démo très demandée');
    await page.goto('/');
    await expect(page.locator('.bar__n')).toHaveText('12 congrès'); // reads keep working
  } finally {
    sqlLocal(`DELETE FROM rate_limits WHERE key = 'wall:${day}'`);
  }
});

test('FIX4-3 (ADV-B-207) refused POSTs create nothing: wrong role, missing CSRF, invalid form', async ({ page }) => {
  await login(page, 'contributeur');
  const origin = new URL(page.url()).origin;
  const csrf = await csrfOf(page);
  expect((await page.request.post('/console/demandes/1', { form: { _csrf: csrf, action: 'note', note: 'x' }, headers: { origin } })).status()).toBe(403);
  expect((await page.request.post('/console/listes', { form: { _csrf: csrf, kind: 'pays', value: 'Islande' }, headers: { origin } })).status()).toBe(403);
  expect((await page.request.post('/console/congres/nouveau', { form: { action: 'review' }, headers: { origin } })).status()).toBe(403);
  const invalid = await page.request.post('/console/congres/nouveau', { form: { _csrf: csrf, action: 'review', title: '' }, headers: { origin } });
  expect(await invalid.text()).toContain('rien n’a été enregistré');
  await logout(page);
  await login(page, 'equipe');
  const c2 = await csrfOf(page);
  expect((await page.request.post('/console/gme/acces/1', { form: { _csrf: c2, decision: 'approuver' }, headers: { origin } })).status()).toBe(403);
  const sbx = await sbxOf(page);
  expect(d1Count(`SELECT (SELECT COUNT(*) FROM sandboxes WHERE id = '${sbx}') AS s, (SELECT COUNT(*) FROM congresses WHERE sbx = '${sbx}') AS c, (SELECT COUNT(*) FROM enquiry_events WHERE sbx = '${sbx}') AS e`)[0]).toEqual({ s: 0, c: 0, e: 0 });
});

test('FIX4-4 a full S1-S5 journey stays far below the per-sandbox throttle (at most a third of it)', async ({ browser }) => {
  const P = await newPage(browser);
  let writes = 0;
  P.page.on('request', (r) => { if (r.method() === 'POST' && !/connexion|deconnexion/.test(r.url())) writes++; });
  await journey(P.page);
  const limit = Number(/SBX_WRITE_LIMIT = (\d+)/.exec(src('data.js'))[1]);
  expect(limit).toBe(60);
  expect(writes).toBeLessThanOrEqual(limit / 3);
  console.log(`FIX4-4: the S1-S5 journey makes ${writes} write requests (throttle ${limit} per 10 minutes)`);
  assertClean(P.problems); await P.ctx.close();
});

test('FIX4-5 (SEC-B-201) one HKDF-derived key per purpose: session-v1, form-v1, confirm-v1, iphash-v1; no shared key with prefixes', async ({ page }) => {
  const lib = src('lib.js');
  expect(lib).toContain("export const MAC_PURPOSES = ['session-v1', 'form-v1', 'confirm-v1', 'iphash-v1'];");
  expect(lib).toMatch(/info: enc\.encode\(info\)/);
  expect(lib).not.toContain('form-and-ip-hmac');
  for (const f of readdirSync(`${ROOT}/src`)) {
    const s = src(f);
    expect(s, f).not.toMatch(/hmac\(env, '(session|confirm|ip)\|/);
    expect(s, f).not.toMatch(/hmac\(env, `\$\{purpose\}\|/);
    for (const m of s.matchAll(/hmac\(env, '([^']+)'/g)) expect(['session-v1', 'form-v1', 'confirm-v1', 'iphash-v1'], f).toContain(m[1]);
  }
  // behaviour: a session signature is not a valid confirmation signature, and the other way round
  await login(page, 'equipe');
  const sig = (await page.context().cookies()).find((x) => x.name === '__Host-av_session').value.split('.')[1];
  const forged = await (await page.request.get(`/demande/confirmation?ref=DV-2026-0001&k=${sig.slice(0, 22)}`)).text();
  expect(forged).not.toContain('DV-2026-0001');
});

test('FIX4-6 (SEC-B-203) tokens must have exactly the expected parts: an extra segment is refused', async ({ page, request }) => {
  await login(page, 'equipe');
  const c = (await page.context().cookies()).find((x) => x.name === '__Host-av_session');
  expect((await request.get('/console', { headers: { cookie: `__Host-av_session=${c.value}` }, maxRedirects: 0 })).status()).toBe(200);
  for (const bad of [`${c.value}.x`, `${c.value}.`, `.${c.value}`, c.value.replace('.', '..')]) {
    expect((await request.get('/console', { headers: { cookie: `__Host-av_session=${bad}` }, maxRedirects: 0 })).status(), bad.slice(-8)).toBe(303);
  }
  const html = await (await request.get('/console/connexion')).text();
  const tok = /name="_token" value="([^"]+)"/.exec(html)[1];
  const r = await request.post('/console/connexion', { form: { _token: tok + '.x', username: 'equipe', password: 'demo-asset' }, maxRedirects: 0 });
  expect(r.status()).toBe(403);
});
