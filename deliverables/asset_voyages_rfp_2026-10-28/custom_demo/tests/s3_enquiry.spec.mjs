// S3: flight enquiry from a congress page.
import { test, expect, login, fillEnquiry, postEnquiry, SLUG, d1Count, sbxOf } from './helpers.mjs';

test.describe.configure({ mode: 'serial' });
// Each Playwright context is a fresh private sandbox, so every test starts from the seed.

// Visitor and staff share one browser here (one private sandbox): a second tab logs in to count.
const countEnquiries = async (page) => {
  const p = await page.context().newPage();
  await login(p, 'direction');
  await p.goto('/console/demandes');
  const n = parseInt((await p.locator('.chips .chip').first().textContent()).match(/\((\d+)\)/)[1], 10);
  await p.close();
  return n;
};

test('S3-F1 every field is present and the congress is prefilled', async ({ page }) => {
  await page.goto(`/congres/${SLUG.cardio}`);
  for (const l of ['Nom et prénom', 'E-mail', 'Téléphone', 'Société', 'Ville de départ', 'Date aller', 'Date retour', 'Passagers', 'Message']) await expect(page.getByLabel(l, { exact: false }).first()).toBeVisible();
  await expect(page.locator('label[for="f-company"]')).toContainText('(facultatif)');
  await expect(page.locator('#f-consent')).toBeVisible();
  await expect(page.locator('label[for="f-consent"]')).toContainText('J’accepte');
  await expect(page.locator('[data-congress]')).toContainText('Congrès européen de cardiologie');
});

test('S3-F2 S3-F3 S3-E1 valid submission in 1 click: stored, linked to the congress, reference shown, team notified', async ({ page }) => {
  await page.goto(`/congres/${SLUG.onco}`);
  await fillEnquiry(page, { out: '2027-01-27', back: '2027-01-31', name: 'Claire Dubois (exemple)' });
  await page.waitForTimeout(3100); // a human takes longer than the minimum fill time
  let clicks = 0;
  await page.getByRole('button', { name: 'Envoyer ma demande' }).click(); clicks++;
  expect(clicks).toBe(1);
  await expect(page.getByRole('heading', { name: 'Merci, votre demande est enregistrée.' })).toBeVisible();
  const ref = (await page.locator('[data-ref]').textContent()).trim();
  expect(ref).toMatch(/^DV-2026-\d{4}$/);
  expect(ref).toBe('DV-2026-0007');
  await expect(page.locator('.thanks')).toContainText('Journées d’oncologie digestive — exemple');
  // server-side: the console holds it, linked to the congress; the notification log has the e-mail
  const admin = await page.context().newPage();
  await login(admin, 'equipe');
  await admin.goto('/console/demandes?q=' + ref);
  await expect(admin.locator('tbody tr')).toHaveCount(1);
  await expect(admin.locator('tbody tr')).toContainText('Journées d’oncologie digestive — exemple');
  await admin.goto('/console/notifications');
  const mail = admin.locator('.mail').first();
  await expect(mail).toContainText(`Nouvelle demande ${ref}`);
  await expect(mail).toContainText('Claire Dubois (exemple)');
  await expect(mail).toContainText('Envoi simulé à equipe.congres@example.com');
  await admin.close();
});

test('S3-F4 reloading the confirmation page or replaying the POST creates no second enquiry', async ({ page }) => {
  const request = page.request;
  const before = await countEnquiries(page);
  const first = await postEnquiry(request, SLUG.cardio, { name: 'Rejeu (exemple)' });
  expect(first.res.status()).toBe(303);
  const loc = first.res.headers().location;
  await page.goto(loc);
  await page.reload();
  await page.reload();
  await expect(page.locator('[data-ref]')).toHaveText('DV-2026-0007');
  // same token sent again (double-click, back button + resubmit): same reference, no new row
  const replay = await postEnquiry(request, SLUG.cardio, { name: 'Rejeu (exemple)' }, { token: first.token, wait: 0 });
  expect(replay.res.status()).toBe(303);
  expect(replay.res.headers().location).toBe(loc);
  expect(await countEnquiries(page)).toBe(before + 1);
  // a forged or unsigned confirmation link reveals nothing
  const forged = await (await request.get('/demande/confirmation?ref=DV-2026-0001')).text();
  expect(forged).not.toContain('DV-2026-0001');
});

test('S3-E1 errors appear next to each field in plain French and keep what was typed', async ({ page }) => {
  await page.goto(`/congres/${SLUG.cardio}`);
  await fillEnquiry(page, { email: 'pas-un-email', pax: '0', out: '2027-08-30', back: '2027-08-20', consent: false, name: 'Jeanne Typée (exemple)' });
  await page.waitForTimeout(3100);
  await page.getByRole('button', { name: 'Envoyer ma demande' }).click();
  await expect(page.locator('#form-errors')).toContainText('champs à corriger');
  await expect(page.locator('#f-email-e')).toHaveText(/adresse e-mail n’est pas valide/);
  await expect(page.locator('#f-pax-e')).toHaveText(/entre 1 et 50/);
  await expect(page.locator('#f-back-e')).toHaveText(/date retour doit être le jour de l’aller ou après/);
  await expect(page.locator('#f-consent-e')).toHaveText(/Cochez cette case/);
  await expect(page.getByLabel('Nom et prénom')).toHaveValue('Jeanne Typée (exemple)');
  await expect(page.getByLabel('E-mail')).toHaveValue('pas-un-email');
  await expect(page.getByLabel('Message')).toHaveValue('Trois places, départ le matin.');
  // correct and send: success
  await page.getByLabel('E-mail').fill('jeanne@example.com');
  await page.getByLabel('Passagers').fill('2');
  await page.getByLabel('Date retour').fill('2027-08-31');
  await page.locator('#f-consent').check();
  await page.waitForTimeout(3100);
  await page.getByRole('button', { name: 'Envoyer ma demande' }).click();
  await expect(page.locator('[data-ref]')).toHaveText(/DV-2026-\d{4}/);
});

test('S3-H1 rejected with a message: passengers 0, 51, abc; return before outbound; past dates; bad email; missing consent', async ({ page }) => {
  const request = page.request;
  const before = await countEnquiries(page);
  const cases = [
    [{ passengers: '0' }, 'entre 1 et 50'], [{ passengers: '51' }, 'entre 1 et 50'], [{ passengers: 'abc' }, 'entre 1 et 50'], [{ passengers: '-3' }, 'entre 1 et 50'], [{ passengers: '2.5' }, 'entre 1 et 50'],
    [{ date_out: '2027-08-30', date_back: '2027-08-20' }, 'date retour doit être'], [{ date_out: '2025-01-10', date_back: '2025-01-12' }, 'ne peut pas être passée'],
    [{ date_out: 'demain' }, 'Date invalide'], [{ email: 'a@b' }, 'n’est pas valide'], [{ email: 'x@example.com\r\nBcc: victim@example.com' }, 'n’est pas valide'],
    [{ consent: undefined }, 'Cochez cette case'], [{ name: '' }, 'Indiquez votre nom'], [{ name: 'x'.repeat(121) }, '120 caractères'], [{ message: 'm'.repeat(2001) }, '2 000 caractères'],
    [{ phone: '<script>' }, 'chiffres'],
  ];
  const tokens = [];
  for (let i = 0; i < cases.length; i++) tokens.push(null);
  for (const [fields, msg] of cases) {
    const { res, text } = await postEnquiry(request, SLUG.cardio, fields, { wait: 0 });
    // no wait: the token check returns « trop rapide » before validation, so wait once per batch below
    // D4: every re-render is a 200 page whose content says what happened (here: sent too fast, nothing stored)
    expect(res.status()).toBe(200);
    expect(text).toContain('n’a pas été envoyée');
  }
  // now the same cases with a realistic fill time: every one is re-rendered (200) with its French message
  const pageHtml = await (await request.get(`/congres/${SLUG.cardio}`)).text();
  const toks = [];
  for (let i = 0; i < cases.length; i++) toks.push(/name="_token" value="([^"]+)"/.exec(await (await request.get(`/congres/${SLUG.cardio}`)).text())[1]);
  await new Promise((r) => setTimeout(r, 3100));
  for (let i = 0; i < cases.length; i++) {
    const [fields, msg] = cases[i];
    const { res, text } = await postEnquiry(request, SLUG.cardio, fields, { wait: 0, token: toks[i] });
    expect(res.status(), JSON.stringify(fields)).toBe(200);
    expect(text).toContain('rien n’a été enregistré');
    expect(text, JSON.stringify(fields)).toContain(msg);
  }
  expect(pageHtml).toContain('Envoyer ma demande');
  // oversized body
  const big = await request.post('/demande', { form: { message: 'x'.repeat(40000) }, maxRedirects: 0 });
  expect(big.status()).toBe(413);
  expect(await countEnquiries(page)).toBe(before);
});

test('S3-H2 honeypot or too-fast form is not stored; rapid repeats from one address are rate-limited', async ({ page }) => {
  const request = page.request;
  const before = await countEnquiries(page);
  const hp = await postEnquiry(request, SLUG.cardio, { zx_confirm: 'http://spam.example' });
  expect(hp.res.status()).toBe(303);
  expect(hp.res.headers().location).toBe('/demande/confirmation');
  const fast = await postEnquiry(request, SLUG.cardio, {}, { wait: 0 });
  expect(fast.res.status()).toBe(200);
  expect(fast.text).toContain('Votre demande n’a pas été envoyée : le formulaire a été validé trop vite');
  const forged = await postEnquiry(request, SLUG.cardio, {}, { wait: 0, token: `${Date.now() - 10000}.abcdefghijkl.forgedforgedforgedforged` });
  expect(forged.res.status()).toBe(403);
  const noToken = await request.post('/demande', { form: { congress: '101', name: 'x' }, maxRedirects: 0 });
  expect(noToken.status()).toBe(403);
  expect(await countEnquiries(page)).toBe(before);
  // rate limit: 10 accepted per 10 minutes per browser and connection, the 11th is refused with a visible message
  const toks = [];
  for (let i = 0; i < 11; i++) toks.push(/name="_token" value="([^"]+)"/.exec(await (await request.get(`/congres/${SLUG.cardio}`)).text())[1]);
  await new Promise((r) => setTimeout(r, 3100));
  const statuses = [];
  let last;
  for (let i = 0; i < 11; i++) { last = await postEnquiry(request, SLUG.cardio, { name: `Rafale ${i} (exemple)` }, { wait: 0, token: toks[i] }); statuses.push(last.res.status()); }
  expect(statuses).toEqual([...Array(10).fill(303), 200]);
  expect(last.text).toContain('Votre demande n’a pas été envoyée : trop de demandes depuis ce navigateur en 10 minutes');
  expect(await countEnquiries(page)).toBe(before + 10);
});

test('S3-H3 script or HTML in any field is stored and shown as text only; SQL-ish text is inert', async ({ page }) => {
  let dialogs = 0;
  page.on('dialog', () => { dialogs++; });
  const evil = '<img src=x onerror=alert(1)><script>alert(2)</script>';
  await page.goto(`/congres/${SLUG.cardio}`);
  await fillEnquiry(page, { name: `${evil} (exemple)`, company: "Robert'); DROP TABLE enquiries;--", city: '=HYPERLINK("http://evil.example")', msg: `${evil}\n<b>gras</b>` });
  await page.waitForTimeout(3100);
  await page.getByRole('button', { name: 'Envoyer ma demande' }).click();
  const ref = (await page.locator('[data-ref]').textContent()).trim();
  const admin = await page.context().newPage();
  let adminDialogs = 0; admin.on('dialog', (d) => { adminDialogs++; d.dismiss(); });
  await login(admin, 'equipe');
  await admin.goto('/console/demandes');
  await admin.getByRole('link', { name: ref }).click();
  await expect(admin.locator('.facts')).toContainText(evil);
  await expect(admin.locator('.facts')).toContainText("Robert'); DROP TABLE enquiries;--");
  expect(await admin.locator('main img').count()).toBe(0);
  expect(await admin.locator('main b', { hasText: 'gras' }).count()).toBe(0);
  await admin.goto('/console/notifications');
  await expect(admin.locator('.mail').first()).toContainText(evil);
  await admin.goto('/console');
  await expect(admin.locator('.feed')).toContainText(evil);
  expect(adminDialogs).toBe(0);
  expect(dialogs).toBe(0);
  await admin.close();
  expect(d1Count(`SELECT COUNT(*) AS n FROM enquiries WHERE sbx = '${await sbxOf(page)}'`)[0].n).toBe(1); // the new enquiry only; the 6 seeded ones stay shared
});
