// Fix round 5 (UX re-check P3 defects, B_ux.md EYE-B-202 to 205): one test per item (FIX5-n).
import { test, expect, login, newPage, assertClean, ROOT } from './helpers.mjs';

// Every text segment of el renders on a single line (a segment = text between allowed break points).
const oneLine = (loc) => loc.evaluate((el) => {
  const range = document.createRange();
  const bad = [];
  const walk = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
  for (let n = walk.nextNode(); n; n = walk.nextNode()) {
    if (!n.textContent.trim()) continue;
    range.selectNodeContents(n);
    const tops = new Set([...range.getClientRects()].map((r) => Math.round(r.top)));
    if (tops.size > 1) bad.push(n.textContent);
  }
  return bad;
});

test('FIX5-1 (EYE-B-202) DV references never split on a phone: notification titles and GM&E request reasons', async ({ browser }) => {
  const P = await newPage(browser, { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  const page = P.page;
  await login(page, 'direction');
  await page.goto('/console/notifications');
  const refs = page.locator('.mail h2 .nw');
  expect(await refs.count()).toBeGreaterThanOrEqual(6);
  for (let i = 0; i < await refs.count(); i++) {
    await expect(refs.nth(i)).toHaveText(/^DV-2026-\d{4}$/);
    expect(await oneLine(refs.nth(i))).toEqual([]);
  }
  await page.goto('/console/gme/acces');
  const inReason = page.locator('.req q .nw');
  await expect(inReason.first()).toHaveText('DV-2026-0002');
  expect(await oneLine(inReason.first())).toEqual([]);
  assertClean(P.problems); await P.ctx.close();
});

test('FIX5-2 (EYE-B-203) CG references stay on one line in the desktop congress list', async ({ page }) => {
  await login(page, 'equipe');
  await page.goto('/console/congres');
  const cells = page.locator('tbody td[data-label="Réf."]');
  expect(await cells.count()).toBe(13);
  for (let i = 0; i < 13; i++) {
    expect(await cells.nth(i).evaluate((td) => getComputedStyle(td).whiteSpace)).toBe('nowrap');
    expect(await oneLine(cells.nth(i))).toEqual([]);
  }
});

test('FIX5-3 (EYE-B-204) e-mails in the desktop enquiries table never break mid-word: only before « @ » or a dot', async ({ page }) => {
  await login(page, 'equipe');
  await page.goto('/console/demandes');
  const emails = page.locator('tbody td[data-label="Contact"] .quiet', { hasText: '@' });
  expect(await emails.count()).toBeGreaterThanOrEqual(2);
  for (let i = 0; i < await emails.count(); i++) {
    const el = emails.nth(i);
    expect(await el.innerHTML()).toMatch(/<wbr>@/);
    expect(await el.evaluate((e) => getComputedStyle(e).overflowWrap)).toBe('normal');
    expect(await oneLine(el), await el.textContent()).toEqual([]); // each piece between break points is whole
  }
});

test('FIX5-4 (EYE-B-205) « Vérifié le » defaults to the Paris date, also just after midnight Paris time', async ({ page }) => {
  // unit: at 23:05 UTC on 5 Nov (00:05 in Paris on 6 Nov) the staff's day is 6 Nov
  const lib = await import(`${ROOT}/src/lib.js`);
  const RealDate = Date;
  globalThis.Date = class extends RealDate { constructor(...a) { super(...(a.length ? a : ['2026-11-05T23:05:00Z'])); } static now() { return new RealDate('2026-11-05T23:05:00Z').getTime(); } };
  try {
    expect(lib.parisToday()).toBe('2026-11-06');
    expect(lib.today()).toBe('2026-11-06'); // CE-B2-002: « today » is the Paris date everywhere
  } finally { globalThis.Date = RealDate; }
  // integration: the form's default equals today's Paris date
  const paris = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Paris', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
  await login(page, 'contributeur');
  await page.goto('/console/congres/nouveau');
  await expect(page.getByLabel('Vérifié le')).toHaveValue(paris);
});
