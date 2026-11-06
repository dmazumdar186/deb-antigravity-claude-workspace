// Option B (custom platform) and its extra « Le lien de groupe », on the deployed Worker.
// Budget: at most 6 writing contexts and 10 logins; only this run's own sandboxes are reset and then checked in D1.
import { newCtx, snap, flushErrors, probeButtons, finding, log, RUN, settle, SHOTS } from './core.mjs';
import { Agent, stepResult } from './agent.mjs';
import { WIDTHS6 } from './hub.mjs';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

export const B = process.env.B_BASE || 'https://asset-voyages-demo.debanjan186.workers.dev';
const OPT = 'B';
const MAX_LOGINS = 10;
const PASSWORD = 'demo-asset';

async function sbxOf(ctx) { const c = (await ctx.cookies()).find((x) => x.name === '__Host-av_sbx'); return c ? c.value : ''; }
function writer(ctx, label) { RUN.writingContexts.add(label); if (RUN.writingContexts.size > 6) throw new Error('writing-context budget exceeded'); }

async function login(page, user, ag) {
  if (RUN.logins >= MAX_LOGINS) throw new Error('login budget exhausted');
  if (!page.url().includes('/console/connexion')) {
    if (page.url().includes('/console')) {
      const out = page.getByRole('button', { name: 'Se déconnecter' }).first();
      if (await out.count()) { await out.click(); await page.waitForURL(/connexion/); }
    }
    if (!page.url().includes('/console/connexion')) await page.goto(B + '/console/connexion');
  }
  const e1 = await (ag ? ag.fill('Identifiant', user) : page.getByLabel('Identifiant').fill(user));
  const e2 = await (ag ? ag.fill('Mot de passe', PASSWORD) : page.getByLabel('Mot de passe').fill(PASSWORD));
  if (ag) { const e3 = await ag.click('Se connecter'); if (e1 || e2 || e3) return e1 || e2 || e3; } else await page.getByRole('button', { name: 'Se connecter' }).click();
  RUN.logins++;
  await page.waitForLoadState('load');
  page.__meta.role = user;
  if (page.url().includes('/connexion')) return 'still on the login page after « Se connecter »';
  return null;
}
async function logout(page, ag) {
  const why = ag ? await ag.click('Se déconnecter') : (await page.getByRole('button', { name: 'Se déconnecter' }).first().click(), null);
  await page.waitForLoadState('load');
  page.__meta.role = 'visiteur';
  return why;
}
const S = (page, state, extra = {}) => snap(page, { option: OPT, surface: page.url().includes('/console') ? 'B-console' : page.url().includes('/g/') ? 'B-group' : 'B-public', state, demo: true, b4: true, ...extra });
const E = (page, state) => flushErrors(page, { option: OPT, state });

// Read every console page linked from the visible side navigation (the role's whole menu).
async function crawlNav(page, tag) {
  const hrefs = await page.$$eval('nav.side a[href]', (as) => as.filter((a) => a.offsetParent).map((a) => a.getAttribute('href')));
  for (const h of [...new Set(hrefs)]) {
    if (!h.startsWith('/console')) continue;
    await page.goto(B + h);
    await S(page, `${tag} ${h}`);
    await probeButtons(page, { option: OPT, state: `${tag} ${h}` });
    E(page, `${tag} ${h}`);
  }
}

// ---------------------------------------------------------------- read-only visitor crawl
export async function crawlBPublic(browser) {
  const out = { seedGroupUrl: '' };
  for (const locale of ['fr-FR', 'en-GB']) {
    for (const w of locale === 'fr-FR' ? WIDTHS6 : [1440, 390]) {
      const full = (w === 1440 || w === 390);
      const { ctx, page } = await newCtx(browser, { width: w, locale, option: OPT });
      const visit = async (path, state, extra = {}) => {
        page.__meta.expectErrorDoc = !!extra.error;
        const r = await page.goto(B + path);
        const st = r ? r.status() : 0;
        const res = await S(page, `${state}${locale === 'en-GB' ? ' (en-GB)' : ''}`, { rules: full ? undefined : ['B4', 'C6', 'C4'], shot: full || ['catalogue', 'congress'].includes(state) });
        E(page, state);
        page.__meta.expectErrorDoc = false;
        return { st, res };
      };
      await visit('/', 'catalogue');
      if (full && locale === 'fr-FR') {
        await probeButtons(page, { option: OPT, state: 'catalogue' });
        await visit('/?q=cardiologie', 'search many');
        await visit('/?q=chicago', 'search one');
        await visit('/?q=zzqqxx', 'search zero');
        await visit('/?discipline=Cardiologie', 'filter discipline');
        await visit('/?pays=France&mois=2027-03', 'filter pays+mois');
      }
      await visit('/congres/journees-d-oncologie-digestive-cg-0112', 'congress');
      if (full) {
        // C1: error pages reached only on purpose
        const e404 = await visit('/cette-page-n-existe-pas', 'error 404 public', { error: true });
        if (e404.st !== 404) finding({ check: 'C1', option: OPT, page: B + '/cette-page-n-existe-pas', width: w, text: `status ${e404.st}`, note: 'bad URL should answer a styled 404' });
        await visit('/congres/congres-inexistant-cg-9999', 'error 404 congress', { error: true });
        await visit('/g/lien-invalide', 'error group link unknown', { error: true });
        await visit('/console/connexion', 'login page');
        const c404 = await visit('/console/nexiste-pas', 'console bad URL (logged out)', { error: true });
        if (locale === 'en-GB') {
          // B1 en-GB: native validation bubbles come from the browser language when the form has no novalidate
          await page.goto(B + '/congres/journees-d-oncologie-digestive-cg-0112');
          const msgs = await page.$$eval('form input[required], form textarea[required]', (els) => els.filter((e) => e.offsetParent && !e.form.noValidate).map((e) => ({ name: e.name, msg: e.validationMessage })).filter((x) => x.msg));
          for (const m of msgs.slice(0, 3)) finding({ check: 'B1', option: OPT, page: page.url(), width: w, locale, text: m.msg, element: `input[name=${m.name}] (native validation bubble)`, note: 'an English-language browser shows English validation text on the French form (form has no novalidate)' });
        }
      }
      await ctx.close();
    }
  }
  return out;
}

// ---------------------------------------------------------------- C10 replay + journeys, 1440 (writing context 1)
export async function replayB(browser, hub) {
  const rows = [];
  const res = { rows, evidence: {}, sbx: [], groupUrl: '' };
  const { ctx, page } = await newCtx(browser, { width: 1440, option: OPT, label: 'B-1440' });
  writer(ctx, 'B-1440 replay');
  const ag = new Agent(page, OPT);
  const T = hub.tasks;
  const step = async (task, n, text, fn) => {
    ag.clicks = 0;
    let why = null; let extra = '';
    try { const r = await fn(); if (typeof r === 'string') why = r; else if (r && r.why) { why = r.why; extra = r.extra || ''; } else if (r && r.extra) extra = r.extra; } catch (e) { why = 'exception: ' + e.message.split('\n')[0]; }
    const s = await S(page, `C10 ${task}.${n}`, { allowCode: /reveal/.test(extra) });
    E(page, `C10 ${task}.${n}`);
    stepResult(rows, { option: OPT, task, n, text, ok: !why, why, clicks: ag.clicks, page: page.url(), role: page.__meta.role, shot: s && s.shot, extra });
    return !why;
  };
  const hubStep = (ti, n) => (T[ti] && T[ti].opts.B && T[ti].opts.B.steps[n - 1]) || { text: '(missing on hub)', links: [] };
  const stamp = Date.now().toString(36).slice(-4);
  const title = `Congrès de relecture ${stamp} — exemple`;

  // Task 1
  let s = hubStep(0, 1);
  await step('T1', 1, s.text, async () => {
    if (!/sign in as contributeur/i.test(s.text)) return 'step text changed: re-map the replay';
    const href = (s.links.find((l) => /console/.test(l.href)) || {}).href;
    if (!href) return 'no « Open the team console » link in the step';
    await page.goto(href);
    return login(page, 'contributeur', ag);
  });
  await crawlNav(page, 'contributeur');
  s = hubStep(0, 2);
  await step('T1', 2, s.text, async () => {
    if (!/list of congresses and add a new one/i.test(s.text)) return 'step text changed: re-map the replay';
    let w = await ag.click('Congrès', { within: 'nav.side' }); if (w) return w;
    // « add a new one »: the agent looks for an add label on that list
    const add = ['Nouveau congrès', 'Ajouter un congrès', 'Ajouter', 'Créer un congrès'];
    let ok = false; for (const l of add) { if (!(await ag.click(l))) { ok = true; break; } }
    if (!ok) return 'no visible « add » label on the congress list';
    for (const [l, v] of [['Titre', title], ['Lieu', 'Salle de relecture — exemple'], ['Ville', 'Nice'], ['Date de début', '2027-07-05'], ['Date de fin', '2027-07-07'], ['Site officiel', 'https://www.example.org/relecture'], ['Vérifié le', '2026-11-01']]) { w = await ag.fill(l, v); if (w) return w; }
    await page.getByRole('combobox', { name: 'Discipline', exact: true }).selectOption('Cardiologie');
    await page.getByRole('combobox', { name: 'Pays', exact: true }).selectOption('France');
    return null;
  });
  s = hubStep(0, 3);
  await step('T1', 3, s.text, async () => {
    if (!/Send it for review.*Sign in as direction/i.test(s.text)) return 'step text changed: re-map the replay';
    let w = null; for (const l of ['Soumettre à relecture', 'Envoyer pour relecture']) { w = await ag.click(l); if (!w) break; }
    if (w) return 'no « review » button: ' + w;
    if (!(await ag.sees(/relecture/i))) return 'no confirmation after sending for review';
    await S(page, 'B congress submitted for review');
    w = await logout(page, ag); if (w) return w;
    w = await login(page, 'direction', ag); if (w) return w;
    w = await ag.click('Congrès', { within: 'nav.side' }); if (w) return w;
    w = await ag.click(title.replace(/ — exemple$/, ''), { exact: false }); if (w) w = await ag.click(title, { exact: false }); if (w) return 'the submitted congress is not visible in the list: ' + w;
    w = await ag.click('Publier'); if (w) return w;
    if (!(await ag.sees(/Publié/))) return 'no « Publié » confirmation';
    return null;
  });
  res.evidence['1'] = rows.slice(-3).every((r) => r.ok);
  await crawlNav(page, 'direction');
  for (const p of ['/console/congres/112', '/console/congres/108', '/console/listes', '/console/demandes/3']) { await page.goto(B + p); await S(page, `direction ${p}`); E(page, p); }

  // Task 2
  s = hubStep(1, 1);
  await step('T2', 1, s.text, async () => {
    const href = (s.links.find((l) => /workers\.dev/.test(l.href)) || {}).href;
    if (!href) return 'no « Open the visitor site » link';
    await page.goto(href);
    // « go to the congress catalogue »: either the landing page is it, or a visible label leads to it
    if (await page.getByRole('heading', { name: /catalogue/i }).count()) return null;
    return ag.click('Catalogue des congrès');
  });
  s = hubStep(1, 2);
  await step('T2', 2, s.text, async () => {
    const box = page.getByRole('searchbox').or(page.getByLabel(/Rechercher|Recherche|Mot-clé/i)).filter({ visible: true }).first();
    if (!(await box.count())) return 'no visible search box';
    await box.fill('cardiologie'); ag.note('type « cardiologie »');
    let w = await ag.click('Rechercher'); if (w) { await box.press('Enter'); ag.clicks++; }
    const missing = [];
    for (const l of ['Discipline', 'Pays', 'Mois']) if (!(await page.getByLabel(l, { exact: true }).filter({ visible: true }).count())) missing.push(l);
    if (missing.length) return `filters not visible by label: ${missing.join(', ')} (hub says discipline, country, month)`;
    if (!(await ag.sees(/cardiologie/i))) return 'no result for « cardiologie »';
    return null;
  });
  s = hubStep(1, 3);
  await step('T2', 3, s.text, async () => {
    const first = page.locator('main a[href*="/congres/"]').filter({ visible: true }).first();
    const label = (await first.innerText()).trim();
    const w = await ag.click(label, { exact: false }); if (w) return w;
    const t = await page.locator('main').innerText();
    const miss = ['Dates', 'Ville', 'Lieu', 'Discipline'].filter((x) => !new RegExp(x, 'i').test(t));
    return miss.length ? `details page lacks: ${miss.join(', ')}` : null;
  });
  res.evidence['2'] = rows.slice(-3).every((r) => r.ok);

  // Task 3 (enquiry on a congress page)
  let ref = '';
  s = hubStep(2, 1);
  await step('T3', 1, s.text, async () => {
    await page.goto(B + '/congres/journees-d-oncologie-digestive-cg-0112');
    if (await page.getByLabel('Nom et prénom').filter({ visible: true }).count()) return { extra: 'form already open on the page (0 clicks)' };
    for (const l of ['Demander un devis vol', 'Demander un devis', 'Demande de devis']) if (!(await ag.click(l, { exact: false }))) return null;
    return 'no visible enquiry form or label to open it';
  });
  s = hubStep(2, 2);
  await step('T3', 2, s.text, async () => {
    for (const [l, v] of [['Nom et prénom', 'Claire Dubois (exemple)'], ['E-mail', 'claire.dubois@example.com'], ['Téléphone', '01 99 00 12 34'], ['Ville de départ', 'Bordeaux'], ['Date aller', '2027-01-27'], ['Date retour', '2027-01-31'], ['Passagers', '3']]) { const w = await ag.fill(l, v); if (w) return w; }
    await page.locator('#f-consent').check();
    return null;
  });
  s = hubStep(2, 3);
  await step('T3', 3, s.text, async () => {
    await page.waitForTimeout(3200);
    const w = await ag.click('Envoyer la demande'); if (w) return w;
    const t = await page.locator('body').innerText();
    ref = (t.match(/DV-2026-\d{4}/) || [])[0] || '';
    return ref ? null : 'no reference number on screen';
  });
  res.evidence['3'] = rows.slice(-3).every((r) => r.ok);

  // Task 4
  s = hubStep(3, 1);
  await step('T4', 1, s.text, async () => {
    const href = (s.links.find((l) => /console/.test(l.href)) || {}).href;
    await page.goto(href || B + '/console');
    const w = await login(page, 'equipe', ag); if (w) return w;
    return ag.click('Demandes', { within: 'nav.side', exact: false });
  });
  await crawlNav(page, 'equipe');
  s = hubStep(3, 2);
  await step('T4', 2, s.text, async () => {
    await page.goto(B + '/console/demandes'); ag.note('back on « Demandes »');
    let w = await ag.click(ref, { exact: false }); if (w) { const row = page.locator('tr', { hasText: ref }).getByRole('link').first(); if (await row.count()) { await row.click(); ag.clicks++; await page.waitForLoadState(); } else return `enquiry ${ref} not visible in the list`; }
    w = await ag.click('Qualifiée'); if (w) return w;
    const t = await page.locator('body').innerText();
    if (!/Statut mis à jour/.test(t)) return 'no confirmation of the status change';
    if (!/Historique/i.test(t)) return 'no history visible';
    // B2: the time in the history line must be Paris time, not UTC
    const paris = new Intl.DateTimeFormat('fr-FR', { timeZone: 'Europe/Paris', hour: '2-digit', minute: '2-digit' }).format(new Date());
    const utc = new Date().toISOString().slice(11, 16);
    const times = [...t.matchAll(/\b(\d{2}:\d{2})\b/g)].map((m) => m[1]);
    const near = (a, b) => Math.abs((+a.slice(0, 2) * 60 + +a.slice(3)) - (+b.slice(0, 2) * 60 + +b.slice(3))) <= 3;
    if (!times.some((x) => near(x, paris))) finding({ check: 'B2', option: OPT, page: page.url(), role: 'equipe', width: 1440, text: `times shown: ${[...new Set(times)].join(', ')}; Paris now ${paris}, UTC now ${utc}`, note: 'the status change just made is not shown in Paris time' });
    return null;
  });
  s = hubStep(3, 3);
  await step('T4', 3, s.text, async () => {
    let w = await ag.click('Demandes', { within: 'nav.side', exact: false }); if (w) return w;
    const dl = page.waitForEvent('download', { timeout: 10000 }).catch(() => null);
    w = await ag.click('Exporter (tableur CSV)', { exact: false }); if (w) return w;
    const d = await dl; if (!d) return 'the CSV did not download';
    const p = join(SHOTS, '..', `b-demandes.csv`); await d.saveAs(p);
    const csv = readFileSync(p, 'utf8');
    if (!csv.startsWith('﻿') || !csv.includes(';')) return 'CSV without BOM or « ; » separators';
    if (!csv.includes(ref)) return `CSV lacks ${ref}`;
    w = await ag.click('Notifications', { within: 'nav.side', exact: false }); if (w) return w;
    if (!(await ag.sees(ref))) return `notification log does not list ${ref}`;
    return { extra: `CSV ${d.suggestedFilename()}` };
  });
  res.evidence['4'] = rows.slice(-3).every((r) => r.ok);

  // Task 5
  s = hubStep(4, 1);
  await step('T5', 1, s.text, async () => {
    const quoted = (s.text.match(/«\s*([^»]+?)\s*»/) || [])[1] || '';
    let w = await ag.click(quoted);
    let why = null;
    if (w) { why = `hub label « ${quoted} »: ${w}`; ag.note('fallback: agent reads the menu'); const w2 = await ag.click('Codes', { within: 'nav.side' }); if (w2) return why + '; ' + w2; }
    const html = await page.content();
    if (/DEMO-GME-\d{4}/.test(html)) return 'codes are not hidden';
    const card = page.locator('.gme').filter({ has: page.getByRole('button', { name: 'Demander l’accès' }) }).first();
    if (!(await card.count())) return (why ? why + '; ' : '') + 'no « Demander l’accès » on any code';
    await card.getByLabel(/Motif/).fill('Devis pour un groupe, trois places.');
    await card.getByRole('button', { name: 'Demander l’accès' }).click(); ag.clicks++;
    await page.waitForLoadState();
    return why;
  });
  s = hubStep(4, 2);
  await step('T5', 2, s.text, async () => {
    let w = await logout(page, ag); if (w) return w;
    w = await login(page, 'direction', ag); if (w) return w;
    // approve from where Direction lands; otherwise from the menu
    let b = page.getByRole('button', { name: /Approuver/ }).filter({ visible: true }).first();
    if (!(await b.count())) { w = await ag.click('Demandes d’accès', { exact: false }); if (w) return 'no approve button on the dashboard and ' + w; b = page.getByRole('button', { name: /Approuver/ }).filter({ visible: true }).first(); }
    if (!(await b.count())) return 'no « Approuver » button';
    await b.click(); ag.clicks++; await page.waitForLoadState();
    return (await ag.sees(/Accès accordé/)) ? null : 'no « Accès accordé » confirmation';
  });
  s = hubStep(4, 3);
  await step('T5', 3, s.text, async () => {
    let w = await logout(page, ag); if (w) return w;
    w = await login(page, 'equipe', ag); if (w) return w;
    w = await ag.click('Codes', { within: 'nav.side' }); if (w) return w;
    let why = null;
    if (!/DEMO-GME-\d{4}/.test(await page.locator('main').innerText())) {
      const b = page.getByRole('button', { name: 'Afficher le code' }).filter({ visible: true }).first();
      if (!(await b.count())) return 'code not shown and no « Afficher le code »';
      await b.click(); ag.clicks++; await page.waitForLoadState();
      why = 'hub says « the code is shown » after signing in; the reader must still click « Afficher le code »';
    }
    if (!/DEMO-GME-\d{4}/.test(await page.locator('main').innerText())) return 'code still not shown';
    await S(page, 'B equipe reveal', { allowCode: true });
    // « the access record lists it »: what can equipe see?
    const t = await page.locator('main').innerText();
    const navs = await page.$$eval('nav.side a', (as) => as.map((a) => a.innerText.trim()));
    if (!/Journal/.test(navs.join(' ')) && !/affich[ée] (le|par)|consultation enregistrée|enregistr/i.test(t)) why = (why ? why + '; ' : '') + 'equipe sees no access record (the « Journal » is Direction-only)';
    return why ? { why, extra: 'reveal' } : { extra: 'reveal' };
  });
  res.evidence['5'] = rows.slice(-3).every((r) => r.ok);

  // Extra: « Le lien de groupe »
  const G = hub.group;
  const gs = (n) => (G && G.steps[n - 1]) || { text: '(missing on hub)', links: [] };
  let linkUrl = '';
  let tab2;
  s = gs(1);
  await step('G', 1, s.text, async () => {
    const href = (s.links.find((l) => /demandes\/1/.test(l.href)) || {}).href;
    if (!href) return 'no « Open enquiry DV-2026-0001 » link';
    await page.goto(href);
    if (page.url().includes('connexion')) { const w = await login(page, 'equipe', ag); if (w) return w; }
    return (await ag.sees('DV-2026-0001')) ? null : 'enquiry DV-2026-0001 not shown after sign-in';
  });
  s = gs(2);
  await step('G', 2, s.text, async () => {
    let w = await ag.click('Groupe'); let why = null;
    if (w) { why = `« Groupe »: ${w}`; w = await ag.click('Groupe', { exact: false }); if (w) return why; why = null; }
    const rowsN = await page.locator('main table tbody tr, main .delegates li, main [data-delegate]').filter({ visible: true }).count();
    if (rowsN !== 3) return `${rowsN} travellers listed, hub says three`;
    return why;
  });
  s = gs(3);
  await step('G', 3, s.text, async () => {
    const sec = page.locator('#lien-groupe, section:has(h2:text("Lien de groupe"))').first();
    if (!(await sec.count()) || !(await sec.isVisible())) return '« Lien de groupe » is not on the « Groupe » tab';
    const txt = await sec.innerText();
    const val = await sec.locator('input').first().inputValue().catch(() => '');
    linkUrl = ((val || txt).match(/https?:\/\/\S+\/g\/[A-Za-z0-9_-]{20,}/) || [])[0] || '';
    if (!linkUrl) return 'no link visible under « Lien de groupe »';
    const copy = sec.getByRole('button', { name: 'Copier le lien' });
    if (await copy.count() && await copy.isVisible()) { await copy.click(); ag.clicks++; }
    tab2 = await ctx.newPage(); tab2.__meta = { ...page.__meta, role: 'voyageur', errors: [] };
    await tab2.goto(linkUrl);
    const t = await tab2.locator('body').innerText();
    if (/DEMO-GME|tarif|Camille|Hugo/i.test(t)) return 'traveller page shows codes, fares or other travellers';
    return null;
  });
  res.groupUrl = linkUrl;
  if (tab2) { await snap(tab2, { option: OPT, surface: 'B-group', state: 'group traveller page', demo: true, b4: true }); flushErrors(tab2, { option: OPT, state: 'group traveller' }); }
  s = gs(4);
  await step('G', 4, s.text, async () => {
    if (!tab2) return 'no traveller tab';
    const min = await tab2.getByLabel('Date aller').getAttribute('min').catch(() => null);
    const out = min && min > '2027-01-27' ? min : '2027-01-27';
    for (const [l, v] of [['Nom et prénom', 'Sophie Durand (exemple)'], ['E-mail', `sophie.durand.${stamp}@example.com`], ['Ville de départ', 'Rennes'], ['Date aller', out], ['Date retour', '2027-01-30']]) await tab2.getByLabel(l).fill(v);
    await tab2.getByLabel(/J’accepte/).check();
    await tab2.waitForTimeout(3300);
    await tab2.getByRole('button', { name: 'Envoyer mes informations' }).click(); await tab2.waitForLoadState();
    await snap(tab2, { option: OPT, surface: 'B-group', state: 'group traveller thanks', demo: true, b4: true });
    flushErrors(tab2, { option: OPT, state: 'group thanks' });
    if (!/bien été reçue/.test(await tab2.locator('body').innerText())) return 'no « Votre réponse a bien été reçue »';
    await page.reload(); await page.waitForLoadState();
    return (await ag.sees('Sophie Durand')) ? null : 'the answer is not in the « Groupe » list';
  });
  res.evidence.G = rows.slice(-4).every((r) => r.ok);
  // revoked link, reached on purpose
  try {
    const rv = page.getByRole('button', { name: 'Révoquer le lien' });
    if (await rv.count()) {
      await rv.click(); await page.waitForLoadState();
      await S(page, 'group link revoked (console)');
      tab2.__meta.expectErrorDoc = true;
      const r = await tab2.goto(linkUrl);
      await snap(tab2, { option: OPT, surface: 'B-group', state: 'error revoked group link', demo: true, b4: true });
      if (r && r.status() < 400) finding({ check: 'C1', option: OPT, page: linkUrl, role: 'voyageur', width: 1440, text: `status ${r.status()}`, note: 'a revoked link should answer 410' });
      flushErrors(tab2, { option: OPT, state: 'revoked' });
    } else finding({ check: 'C1', option: OPT, page: page.url(), role: 'equipe', width: 1440, text: 'no « Révoquer le lien »', note: 'could not reach the revoked-link page' });
  } catch (e) { log('revoke failed', e.message); }

  // Six widths on the console as equipe (B4, C6)
  for (const w of WIDTHS6) {
    await page.setViewportSize({ width: w, height: w < 500 ? 844 : 900 });
    for (const p of ['/console', '/console/demandes', '/console/demandes/1', '/console/demandes/1/groupe', '/console/gme']) { await page.goto(B + p); await snap(page, { option: OPT, surface: 'B-console', state: `6w equipe ${p}`, b4: true, rules: ['B4', 'C6', 'C4'], shot: false }); }
    if (tab2) { await tab2.setViewportSize({ width: w, height: 844 }); await tab2.goto(B + '/g/lien-invalide'); }
  }
  await page.setViewportSize({ width: 1440, height: 900 });
  E(page, 'six widths');

  // Reset this sandbox through the real Direction button (custom_demo/tests/helpers.mjs resetSandbox)
  res.sbx.push(await sbxOf(ctx));
  await login(page, 'direction');
  const rb = page.getByRole('button', { name: 'Réinitialiser la démo' });
  if (await rb.count()) { await rb.click(); await page.waitForLoadState(); res.reset1 = /réinitialisée/.test(await page.locator('body').innerText()); }
  E(page, 'reset');
  await ctx.close();
  return res;
}

// ---------------------------------------------------------------- phone journeys, 390 (writing context 2)
export async function phoneB(browser) {
  const out = { sbx: [] };
  const { ctx, page } = await newCtx(browser, { width: 390, option: OPT, label: 'B-390' });
  writer(ctx, 'B-390 phone');
  // visitor: errors first, then a valid enquiry
  await page.goto(B + '/congres/congres-europeen-de-radiologie-cg-0108');
  await page.getByLabel('E-mail').fill('pas-un-email');
  await page.getByLabel('Passagers').fill('0');
  await page.waitForTimeout(3200);
  await page.getByRole('button', { name: 'Envoyer la demande' }).click(); await page.waitForLoadState();
  await S(page, 'enquiry errors (390)');
  for (const [l, v] of [['Nom et prénom', 'Marc Petit (exemple)'], ['E-mail', 'marc.petit@example.com'], ['Téléphone', '01 99 00 56 78'], ['Ville de départ', 'Nantes'], ['Date aller', '2027-02-23'], ['Date retour', '2027-02-28'], ['Passagers', '1']]) await page.getByLabel(l).fill(v);
  await page.locator('#f-consent').check();
  await page.waitForTimeout(3200);
  await page.getByRole('button', { name: 'Envoyer la demande' }).click(); await page.waitForLoadState();
  await S(page, 'enquiry confirmation (390)');
  E(page, 'visitor 390');
  // contributeur
  await page.goto(B + '/console/connexion');
  await login(page, 'contributeur');
  await S(page, 'contributeur dashboard (390)');
  await crawlNav(page, 'contributeur 390');
  await page.goto(B + '/console/congres/nouveau'); await S(page, 'contributeur new congress (390)');
  await page.goto(B + '/console/congres/113'); await S(page, 'contributeur draft congress (390)');
  // equipe
  await login(page, 'equipe');
  await crawlNav(page, 'equipe 390');
  for (const p of ['/console/demandes/1', '/console/demandes/1/groupe', '/console/demandes/6']) { await page.goto(B + p); await S(page, `equipe ${p} (390)`); await probeButtons(page, { option: OPT, state: `equipe ${p}` }); E(page, p); }
  // C7: expired session. The cookie lasts 8 h (Max-Age), after which the browser drops it: simulate by removing it.
  await page.goto(B + '/console/demandes/6');
  const keep = (await ctx.cookies()).filter((c) => c.name !== '__Host-av_session');
  const sessName = (await ctx.cookies()).map((c) => c.name).find((n) => /session/.test(n)) || '';
  await ctx.clearCookies(); await ctx.addCookies(keep);
  // stale tab: the note form is still on screen
  const note = page.getByLabel('Visible uniquement par l’équipe');
  if (await note.count()) {
    await note.fill('Note écrite avant l’expiration.');
    page.__meta.expectErrorDoc = true;
    await page.getByRole('button', { name: 'Ajouter la note' }).click(); await page.waitForLoadState();
    const r = await S(page, 'C7 expired session: stale form submitted');
    const t = await page.locator('body').innerText();
    if (!/Session expirée|session a expiré|expiré/i.test(t)) finding({ check: 'C7', option: OPT, page: page.url(), role: 'equipe', width: 390, text: t.split('\n').filter(Boolean).slice(0, 4).join(' | ').slice(0, 200), note: 'after the session ends, a form sent from an open tab shows no « Session expirée » message', shot: r && r.shot });
    page.__meta.expectErrorDoc = false;
  }
  await page.goto(B + '/console/demandes');
  const r2 = await S(page, 'C7 expired session: next navigation');
  const t2 = await page.locator('body').innerText();
  if (!/Session expirée|session a expiré/i.test(t2)) finding({ check: 'C7', option: OPT, page: page.url(), role: 'equipe', width: 390, text: t2.split('\n').filter(Boolean).slice(0, 3).join(' | ').slice(0, 200), note: `session cookie ${sessName} gone: the reader is sent to the login page with no « Session expirée » message`, shot: r2 && r2.shot });
  if (!/Se connecter/.test(t2)) finding({ check: 'C7', option: OPT, page: page.url(), role: 'equipe', width: 390, text: 'no login link', note: 'expired session page has no way to sign in again' });
  E(page, 'expired');
  // direction
  await login(page, 'direction');
  await crawlNav(page, 'direction 390');
  for (const p of ['/console/congres/112', '/console/listes']) { await page.goto(B + p); await S(page, `direction ${p} (390)`); }
  out.sbx.push(await sbxOf(ctx));
  await page.goto(B + '/console');
  const rb = page.getByRole('button', { name: 'Réinitialiser la démo' });
  if (await rb.count()) { await rb.click(); await page.waitForLoadState(); out.reset = /réinitialisée/.test(await page.locator('body').innerText()); }
  E(page, 'reset 390');
  await ctx.close();
  return out;
}

// Traveller on a phone (writes into the replay sandbox through the link; gets no sandbox of its own)
export async function travellerPhone(browser, url) {
  if (!url) return;
  const { ctx, page } = await newCtx(browser, { width: 390, option: OPT });
  await page.goto(url);
  await snap(page, { option: OPT, surface: 'B-group', state: 'group traveller page (390, revoked by now)', demo: true, b4: true });
  flushErrors(page, { option: OPT, state: 'traveller 390' });
  for (const w of WIDTHS6) { await page.setViewportSize({ width: w, height: 844 }); await page.goto(url); await snap(page, { option: OPT, surface: 'B-group', state: `6w traveller`, b4: true, rules: ['B4', 'C6'], shot: false }); }
  RUN.notes.push(`traveller phone sandbox cookie: ${await sbxOf(ctx) || '(none)'}`);
  await ctx.close();
}
