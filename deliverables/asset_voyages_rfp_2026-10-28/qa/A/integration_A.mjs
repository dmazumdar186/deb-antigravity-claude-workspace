// Integration A. Usage: WP_BASE=http://127.0.0.1:9403 node integration_A.mjs  (fresh Playground recommended)
import fs from 'fs';
import path from 'path';
import { launch, asRole, BASE, LOGS, sleep } from './common.mjs';

const results = [];
const NEURO = 'Congrès européen de neurologie — exemple';
const rec = (id, name, ok, info) => {
  results.push({ id, name, ok, info });
  console.log((ok ? 'PASS ' : 'FAIL ') + id + ' ' + name + ' :: ' + info);
};
async function step(id, name, fn) {
  try { const info = await fn(); rec(id, name, true, info || 'ok'); }
  catch (e) { rec(id, name, false, String(e.message).split('\n')[0]); }
}
const assert = (c, m) => { if (!c) throw new Error(m); };
const PII = /[\w.+-]+@example\.com|DV-2026-\d{4}/;
const ref = `INT-${Date.now()}`;

const browser = await launch();
const direction = await asRole(browser, 'direction');
const equipe = await asRole(browser, 'equipe');
const contrib = await asRole(browser, 'contributeur');
const anon = await browser.newContext({ baseURL: BASE, locale: 'fr-FR' });
const A = (c, p) => c.request.get(p, { maxRedirects: 0 });

const countList = async () => {
  await direction.page.goto('/wp-admin/admin.php?page=asset-demandes');
  const t = await direction.page.locator('.subsubsub li').first().innerText();
  return parseInt((t.match(/\((\d+)\)/) || [])[1], 10);
};

// --- 1. Anonymous GETs and denials
await step('INT-A-001', 'anon GET Demandes screen -> login redirect, no data', async () => {
  const r = await A(anon, '/wp-admin/admin.php?page=asset-demandes');
  assert(r.status() === 302 && /wp-login\.php/.test(r.headers().location || ''), 'status ' + r.status());
  assert(!PII.test(await r.text()), 'PII in body');
  return '302 -> wp-login';
});
await step('INT-A-002', 'anon GET 3 GM&E screens -> login redirect, no code', async () => {
  const out = [];
  for (const p of ['asset-gme', 'asset-gme-acces', 'asset-gme-journal']) {
    const r = await A(anon, '/wp-admin/admin.php?page=' + p);
    assert(r.status() === 302 && /wp-login\.php/.test(r.headers().location || ''), p + ' status ' + r.status());
    assert(!/DEMO-GME-/.test(await r.text()), p + ' leaks code');
    out.push(p + ':302');
  }
  return out.join(' ');
});
await step('INT-A-003', 'anon GET CSV export (admin-post, with and without nonce) refused, no rows', async () => {
  const out = [];
  for (const q of ['action=asset_demandes_export', 'action=asset_demandes_export&_wpnonce=abc123']) {
    const r = await A(anon, '/wp-admin/admin-post.php?' + q);
    const body = await r.text();
    assert(r.status() >= 300, 'status ' + r.status());
    assert(!PII.test(body) && !/text\/csv/.test(r.headers()['content-type'] || ''), 'CSV/PII served');
    out.push(r.status());
  }
  return 'statuses ' + out.join(',');
});
await step('INT-A-004', 'anon public catalogue GET 200 with no PII or code', async () => {
  const r = await A(anon, '/');
  const b = await r.text();
  assert(r.status() === 200, 'status ' + r.status());
  assert(!/DEMO-GME-/.test(b) && !/[\w.+-]+@example\.com/.test(b), 'leak');
  return '200';
});

// --- 2. Enquiry POST
let tokens, madridUrl;
const openForm = async (page) => {
  await page.goto('/?q=madrid');
  await page.locator('.asset-card__title a').first().click();
  await page.waitForSelector('form.asset-form', { timeout: 30000 });
  madridUrl = page.url();
  return page.evaluate(() => {
    const f = document.querySelector('form.asset-form'); const o = {};
    for (const el of f.querySelectorAll('input[type=hidden]')) o[el.name] = el.value;
    return o;
  });
};
const valid = (nom) => ({ nom, email: 'int.test@example.com', telephone: '+33 6 11 22 33 44', societe: 'Test (exemple)', ville_depart: 'Nice', date_aller: '2027-08-26', date_retour: '2027-08-31', passagers: '2', message: 'Integration ' + ref, consentement: '1' });

const pub = await anon.newPage();
const before = await countList();
await step('INT-A-005', 'enquiry POST without nonce refused and not stored', async () => {
  tokens = await openForm(pub);
  const noNonce = { ...tokens };
  const names = Object.keys(noNonce).filter((k) => /nonce/i.test(k));
  assert(names.length > 0, 'no nonce field found among ' + Object.keys(tokens));
  for (const n of names) delete noNonce[n];
  await sleep(3500);
  const r = await anon.request.post('/wp-admin/admin-post.php', { form: { ...noNonce, ...valid('Sans Nonce ' + ref) }, maxRedirects: 5 });
  const html = await r.text();
  assert(!/class="asset-ref"/.test(html) && !/asset_ok=/.test(r.url()), 'confirmation shown');
  const after = await countList();
  assert(after === before, `count ${before} -> ${after}`);
  return `status ${r.status()}, count unchanged ${before}`;
});
let newRef;
await step('INT-A-006', 'valid enquiry creates a record visible in admin', async () => {
  tokens = await openForm(pub);
  for (const [k, v] of Object.entries(valid('Alice Integration ' + ref))) await pub.fill('#asset-q-' + (k === 'consentement' ? 'x' : k), v).catch(() => {});
  await pub.check('#asset-q-consentement');
  await sleep(3500);
  await pub.click('.asset-form button[type=submit]');
  newRef = (await pub.locator('.asset-ref').innerText({ timeout: 30000 })).trim();
  assert(/^DV-2026-\d{4}$/.test(newRef), 'ref ' + newRef);
  const after = await countList();
  assert(after === before + 1, `count ${before} -> ${after}`);
  await direction.page.goto('/wp-admin/admin.php?page=asset-demandes&s=' + newRef);
  const txt = await direction.page.locator('table.wp-list-table tbody').innerText();
  assert(txt.includes(newRef) && txt.includes('Alice Integration'), 'not in admin list');
  return `ref ${newRef}, count ${before} -> ${after}`;
});

// --- 3. Status change writes history
await step('INT-A-007', 'status change writes history row (who, from -> to)', async () => {
  const p = equipe.page;
  await p.goto('/wp-admin/admin.php?page=asset-demandes&s=' + newRef);
  await p.locator('a.row-title', { hasText: newRef }).click();
  await p.waitForSelector('table.asset-history tbody tr', { timeout: 30000 });
  const rowsBefore = await p.locator('table.asset-history tbody tr').count();
  await p.selectOption('#asset-statut', 'qualifiee');
  await p.click('#submit');
  await p.waitForLoadState('load');
  const txt = await p.locator('table.asset-history').innerText();
  const rowsAfter = await p.locator('table.asset-history tbody tr').count();
  assert(rowsAfter === rowsBefore + 1, `rows ${rowsBefore} -> ${rowsAfter}`);
  assert(txt.includes('Nouvelle → Qualifiée') && txt.includes('Équipe (démo)'), 'history text missing');
  return `history rows ${rowsBefore} -> ${rowsAfter}`;
});

// --- 4. GM&E lifecycle
const row = (page) => page.locator('table.asset-gme-table tbody tr', { hasText: NEURO });
let revealForm = null;
await step('INT-A-008', 'GM&E: equipe requests, direction approves, equipe reveals code', async () => {
  const p = equipe.page;
  await p.goto('/wp-admin/admin.php?page=asset-gme');
  assert(!/DEMO-GME-/.test(await p.content()), 'code visible before reveal');
  await row(p).locator('textarea').fill('Integration test: devis groupe (fictif).');
  await row(p).locator('button', { hasText: 'Demander' }).click();
  await p.locator('.notice-success').waitFor();
  const d = direction.page;
  await d.goto('/wp-admin/');
  await d.locator('#asset_cd_gme .asset-widget-req', { hasText: NEURO }).locator('button', { hasText: 'Approuver' }).click();
  await d.locator('.notice-success').waitFor();
  await p.goto('/wp-admin/admin.php?page=asset-gme');
  const form = row(p).locator('form', { has: p.locator('button', { hasText: 'Révéler' }) });
  revealForm = new URLSearchParams({
    asset_gme_action: 'reveal',
    congres_id: await form.locator('input[name=congres_id]').inputValue(),
    asset_nonce: await form.locator('input[name=asset_nonce]').inputValue(),
    _wp_http_referer: '/wp-admin/admin.php?page=asset-gme',
  }).toString();
  await row(p).locator('button', { hasText: 'Révéler' }).click();
  const code = await row(p).locator('code.asset-revealed').innerText();
  assert(/^DEMO-GME-[A-Z0-9]{4}$/.test(code), 'code ' + code);
  return 'reveal shown for single congress';
});
await step('INT-A-009', 'GM&E: after revoke, reveal replay refused, no code, UI hides button', async () => {
  const d = direction.page;
  await d.goto('/wp-admin/admin.php?page=asset-gme-acces');
  await d.locator('table.asset-access-history tr', { hasText: NEURO }).first().locator('button', { hasText: 'Révoquer' }).click();
  await d.locator('.notice-success').waitFor();
  const r = await equipe.page.request.post('/wp-admin/admin.php?page=asset-gme', { data: revealForm, headers: { 'content-type': 'application/x-www-form-urlencoded' } });
  const html = await r.text();
  assert(/aucune autorisation active/.test(html), 'no refusal message');
  assert(!/DEMO-GME-/.test(html), 'code leaked after revoke');
  await equipe.page.goto('/wp-admin/admin.php?page=asset-gme');
  assert((await row(equipe.page).locator('button', { hasText: 'Révéler' }).count()) === 0, 'reveal button still offered');
  await d.goto('/wp-admin/admin.php?page=asset-gme-journal');
  assert((await d.locator('tr[data-action="reveal_refused"]').count()) >= 1, 'refusal not logged');
  return 'refused + logged';
});

// --- 5. Capability matrix (status codes, no redirect following)
const ROLES = { anon: anon, contributeur: contrib.ctx, equipe: equipe.ctx, direction: direction.ctx };
const SCREENS = {
  demandes: '/wp-admin/admin.php?page=asset-demandes',
  gme_codes: '/wp-admin/admin.php?page=asset-gme',
  gme_acces: '/wp-admin/admin.php?page=asset-gme-acces',
  gme_journal: '/wp-admin/admin.php?page=asset-gme-journal',
  new_congres: '/wp-admin/post-new.php?post_type=asset_congres',
};
const EXPECT = { // 302 = login redirect, 403 = forbidden, 200 = allowed
  demandes: { anon: 302, contributeur: 403, equipe: 200, direction: 200 },
  gme_codes: { anon: 302, contributeur: 403, equipe: 200, direction: 200 },
  gme_acces: { anon: 302, contributeur: 403, equipe: 403, direction: 200 },
  gme_journal: { anon: 302, contributeur: 403, equipe: 403, direction: 200 },
  new_congres: { anon: 302, contributeur: 200, equipe: 200, direction: 200 },
};
let n = 10;
for (const [screen, url] of Object.entries(SCREENS)) {
  await step('INT-A-0' + n++, `matrix ${screen}: ` + Object.entries(EXPECT[screen]).map(([r, s]) => `${r}=${s}`).join(' '), async () => {
    const got = {};
    for (const [role, ctx] of Object.entries(ROLES)) {
      const r = await A(ctx, url);
      got[role] = r.status();
      const body = await r.text();
      if (got[role] !== 200) assert(!/DEMO-GME-|[\w.+-]+@example\.com/.test(body), `${role} denial body leaks`);
    }
    const bad = Object.keys(got).filter((r) => got[r] !== EXPECT[screen][r]);
    assert(!bad.length, 'mismatch ' + bad.map((r) => `${r}:${got[r]}(want ${EXPECT[screen][r]})`).join(' '));
    return JSON.stringify(got);
  });
}

await browser.close();
const fails = results.filter((r) => !r.ok);
const summary = `TOTAL ${results.length} PASS ${results.length - fails.length} FAIL ${fails.length}`;
console.log(summary);
fs.writeFileSync(path.join(LOGS, 'integration.log'), results.map((r) => `${r.ok ? 'PASS' : 'FAIL'} ${r.id} ${r.name} :: ${r.info}`).join('\n') + '\n' + summary + '\n');
process.exit(fails.length ? 1 : 0);
