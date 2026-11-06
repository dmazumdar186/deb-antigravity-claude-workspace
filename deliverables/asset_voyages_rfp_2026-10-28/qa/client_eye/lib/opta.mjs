// Option A (WordPress plugin) on a local Playground CLI built from the current wp_demo/ code, plus one hosted boot
// of each Playground link on the hub (A2, and C10 task 1 on the real admin link).
import { newCtx, snap, flushErrors, probeButtons, finding, log, RUN, settle, SHOTS } from './core.mjs';
import { Agent, stepResult } from './agent.mjs';
import { WIDTHS6 } from './hub.mjs';
import { readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';

export const A = process.env.A_BASE || 'http://127.0.0.1:9431';
const OPT = 'A';
const PASSWORD = 'demo-asset';
const S = (page, state, extra = {}) => snap(page, { option: OPT, surface: page.url().includes('/wp-admin') || page.url().includes('wp-login') ? 'A-admin' : 'A-public', state, demo: true, b4: true, wait: 800, ...extra });
const E = (page, state) => flushErrors(page, { option: OPT, state });

async function login(page, user, ag) {
  await page.context().clearCookies();
  await page.goto(A + '/wp-login.php');
  const why = ag ? (await ag.fill('Identifiant ou adresse e-mail', user)) || (await ag.fill('Mot de passe', PASSWORD, { exact: true })) || (await ag.click('Se connecter')) : null;
  if (!ag) { await page.fill('#user_login', user); await page.fill('#user_pass', PASSWORD); await page.click('#wp-submit'); }
  await page.waitForLoadState('load');
  page.__meta.role = user;
  if (why) return why;
  if (page.url().includes('wp-login.php')) return 'still on the login page';
  return null;
}
// « Sign out »: WordPress keeps « Se déconnecter » in the account menu that opens on hover or focus.
async function logout(page, ag) {
  const acct = page.locator('#wp-admin-bar-my-account').first();
  if (await acct.count()) { await acct.hover(); await page.waitForTimeout(300); }
  const w = ag ? await ag.click('Se déconnecter') : null;
  if (!ag) await page.locator('#wp-admin-bar-logout a').click();
  await page.waitForLoadState('load');
  page.__meta.role = 'visiteur';
  return w;
}
async function crawlMenu(page, tag, { b6 = false } = {}) {
  const hrefs = await page.$$eval('#adminmenu a[href]', (as) => [...new Set(as.map((a) => a.href))]);
  for (const h of hrefs) {
    if (/customize\.php|site-editor|themes\.php|plugins\.php|update-core|tools\.php$|options-|export|import/.test(h)) continue;
    try { await page.goto(h, { timeout: 60000 }); } catch (e) { log('A nav failed', h, e.message.split('\n')[0]); continue; }
    await S(page, `${tag} ${h.replace(A, '')}`);
    E(page, `${tag} ${h}`);
  }
  return hrefs;
}

// ---------------------------------------------------------------- public crawl, all widths, both locales
export async function crawlAPublic(browser) {
  for (const locale of ['fr-FR', 'en-GB']) {
    for (const w of locale === 'fr-FR' ? WIDTHS6 : [1440, 390]) {
      const full = w === 1440 || w === 390;
      const { ctx, page } = await newCtx(browser, { width: w, locale, option: OPT });
      page.setDefaultTimeout(60000);
      const visit = async (path, state, extra = {}) => {
        page.__meta.expectErrorDoc = !!extra.error;
        const r = await page.goto(A + path, { timeout: 90000 });
        await S(page, state + (locale === 'en-GB' ? ' (en-GB)' : ''), { rules: full ? undefined : ['B4', 'C6', 'C4'], shot: full });
        E(page, state); page.__meta.expectErrorDoc = false;
        return r ? r.status() : 0;
      };
      await visit('/', 'catalogue');
      await visit('/congres/journees-mediterraneennes-doncologie-exemple/', 'congress');
      if (full) {
        if (locale === 'fr-FR') {
          await probeButtons(page, { option: OPT, state: 'congress' });
          await visit('/?s_congres=cardiologie&q=cardiologie', 'search many');
          await visit('/?q=zzqqxx', 'search zero');
          await visit('/?discipline=cardiologie', 'filter discipline');
          await visit('/?pg=2', 'page 2');
        }
        const st = await visit('/cette-page-n-existe-pas/', 'error 404 public', { error: true });
        if (st !== 404) finding({ check: 'C1', option: OPT, page: A + '/cette-page-n-existe-pas/', width: w, text: `status ${st}`, note: 'bad URL should answer a styled 404' });
        await visit('/wp-login.php', 'login page');
        if (locale === 'en-GB') {
          await page.goto(A + '/congres/journees-mediterraneennes-doncologie-exemple/');
          const msgs = await page.$$eval('form input[required], form textarea[required]', (els) => els.filter((e) => e.offsetParent && !e.form.noValidate).map((e) => ({ name: e.name, msg: e.validationMessage })).filter((x) => x.msg));
          for (const m of msgs.slice(0, 3)) finding({ check: 'B1', option: OPT, page: page.url(), width: w, locale, text: m.msg, element: `input[name=${m.name}] (native validation bubble)`, note: 'an English-language browser shows English validation text on the French form (form has no novalidate)' });
        }
      }
      await ctx.close();
    }
  }
}

// ---------------------------------------------------------------- C10 replay + role crawls, 1440
export async function replayA(browser, hub) {
  const rows = [];
  const res = { rows, evidence: {} };
  const { ctx, page } = await newCtx(browser, { width: 1440, option: OPT });
  page.setDefaultTimeout(60000);
  const ag = new Agent(page, OPT);
  const T = hub.tasks;
  const hubStep = (ti, n) => (T[ti] && T[ti].opts.A && T[ti].opts.A.steps[n - 1]) || { text: '(missing on hub)', links: [] };
  const step = async (task, n, text, fn) => {
    ag.clicks = 0; let why = null; let extra = '';
    try { const r = await fn(); if (typeof r === 'string') why = r; else if (r) { why = r.why || null; extra = r.extra || ''; } } catch (e) { why = 'exception: ' + e.message.split('\n')[0]; }
    const s = await S(page, `C10 ${task}.${n}`, { allowCode: /reveal/.test(extra) });
    E(page, `C10 ${task}.${n}`);
    stepResult(rows, { option: OPT, task, n, text, ok: !why, why, clicks: ag.clicks, page: page.url(), role: page.__meta.role, shot: s && s.shot, extra });
    return !why;
  };
  const stamp = Date.now().toString(36).slice(-4);
  const title = `Congrès de relecture ${stamp} — exemple`;
  // Task 1. Local stand-in for « Open the admin. You are already signed in. »: the admin blueprint signs in as
  // direction; the hosted boot below checks the literal claim on the real link.
  let s = hubStep(0, 1);
  await step('T1', 1, s.text, async () => { const w = await login(page, 'direction', ag); return w ? w : { extra: 'local: signed in as direction through wp-login (hosted link checked separately)' }; });
  s = hubStep(0, 2);
  await step('T1', 2, s.text, async () => {
    const labels = [...s.text.matchAll(/«\s*([^»]+?)\s*»/g)].map((m) => m[1]);
    for (const l of labels) { const w = await ag.click(l, { within: '#adminmenu' }); if (w) return w; }
    return labels.length === 2 ? null : 'expected two quoted labels';
  });
  s = hubStep(0, 3);
  await step('T1', 3, s.text, async () => {
    await page.getByLabel(/titre/i).first().fill(title);
    for (const [l, v] of [['Date de début', '2027-07-05'], ['Date de fin', '2027-07-07'], ['Ville', 'Nice']]) { const w = await ag.fill(l, v, { exact: true }); if (w) return w; }
    // literal: only the fields the hub names (name, dates, city, discipline); a further required field is a finding
    const d = page.getByLabel(/^Discipline/).filter({ visible: true }).first();
    if (!(await d.count())) return 'no « Discipline » field';
    await d.fill('Cardiologie');
    let w = await ag.click('Publier'); if (w) return w;
    await page.waitForTimeout(1500);
    if (!(await ag.sees(/publié|Publié/))) return 'no publish confirmation';
    const q = (s.text.match(/«\s*([^»]+?)\s*»/) || [])[1];
    w = await ag.click(q, { within: '#adminmenu' }); if (w) return w;
    if (!(await ag.sees(title.replace(/ — exemple$/, '')))) return 'the new congress is not in « Tous les congrès »';
    return null;
  });
  res.evidence['1'] = rows.slice(-3).every((r) => r.ok);
  await crawlMenu(page, 'direction');
  // contributeur tip: their congress waits for review
  await login(page, 'contributeur');
  await crawlMenu(page, 'contributeur');
  await page.goto(A + '/wp-admin/post-new.php?post_type=asset_congres').catch(() => {});
  await S(page, 'contributeur new congress');
  const tip = await page.getByRole('button', { name: /Soumettre/ }).count();
  stepResult(rows, { option: OPT, task: 'T1', n: 'tip', text: (T[0] && T[0].opts.A.notes.join(' ')) || '', ok: tip > 0, why: tip ? '' : 'contributeur sees no « Soumettre … » button', clicks: 0, page: page.url(), role: 'contributeur' });

  // Task 2
  s = hubStep(1, 1);
  await step('T2', 1, s.text, async () => {
    await page.context().clearCookies(); page.__meta.role = 'visiteur';
    await page.goto(A + '/');
    return (await page.getByRole('heading', { name: /Catalogue des congrès/ }).count()) ? { extra: 'local: visitor site root' } : ag.click('Catalogue des congrès');
  });
  s = hubStep(1, 2);
  await step('T2', 2, s.text, async () => {
    const box = page.getByRole('searchbox').or(page.getByRole('textbox', { name: /Recherche/ })).filter({ visible: true }).first();
    if (!(await box.count())) return 'no visible search box';
    await box.fill('cardiologie');
    const w = await ag.click('Rechercher'); if (w) return w;
    const miss = []; for (const l of ['Discipline', 'Pays', 'Mois']) { if (await page.getByLabel(l, { exact: true }).filter({ visible: true }).count()) continue; if (l === 'Discipline' && await page.getByRole('link', { name: 'Cardiologie', exact: true }).filter({ visible: true }).count()) continue; miss.push(l); }
    if (miss.length) return `filters not visible by label: ${miss.join(', ')}`;
    return (await ag.sees(/cardiologie/i)) ? null : 'no result';
  });
  s = hubStep(1, 3);
  await step('T2', 3, s.text, async () => {
    const first = page.locator('main a[href*="/congres/"]').filter({ visible: true }).first();
    const w = await ag.click(((await first.innerText()).split('\n').find((x) => /[a-z]{4}/i.test(x)) || '').trim(), { exact: false }); if (w) return w;
    const t = await page.locator('main').innerText();
    const miss = ['Dates', 'Ville', 'Lieu', 'Discipline'].filter((x) => !new RegExp(x).test(t));
    return miss.length ? `details page lacks: ${miss.join(', ')}` : null;
  });
  res.evidence['2'] = rows.slice(-3).every((r) => r.ok);

  // Task 3
  let ref = '';
  s = hubStep(2, 1);
  await step('T3', 1, s.text, async () => {
    const q = (s.text.match(/«\s*([^»]+?)\s*»/) || [])[1];
    return (await ag.sees(q)) ? null : `« ${q} » not on the details page`;
  });
  s = hubStep(2, 2);
  await step('T3', 2, s.text, async () => {
    for (const [l, v] of [['Nom et prénom', 'Claire Dubois (exemple)'], ['E-mail', 'claire.dubois@example.com'], ['Téléphone', '01 99 00 12 34'], ['Ville de départ', 'Bordeaux'], ['Date aller', '2027-01-27'], ['Date retour', '2027-01-31'], ['Nombre de passagers', '3']]) { const w = await ag.fill(l, v); if (w) return w; }
    await page.getByLabel(/J’accepte/).check();
    return null;
  });
  s = hubStep(2, 3);
  await step('T3', 3, s.text, async () => {
    await page.waitForTimeout(3300);
    const w = await ag.click('Envoyer ma demande'); if (w) return w;
    ref = ((await page.locator('body').innerText()).match(/DV-2026-\d{4}/) || [])[0] || '';
    return ref ? null : 'no reference number on screen';
  });
  res.evidence['3'] = rows.slice(-3).every((r) => r.ok);

  // Task 4
  s = hubStep(3, 1);
  await step('T4', 1, s.text, async () => {
    const labels = [...s.text.matchAll(/«\s*([^»]+?)\s*»/g)].map((m) => m[1]);
    let w = await ag.click(labels[0] || 'Espace équipe'); if (w) return w;
    w = (await ag.fill('Identifiant ou adresse e-mail', 'equipe')) || (await ag.fill('Mot de passe', PASSWORD, { exact: true })) || (await ag.click('Se connecter')); if (w) return w;
    page.__meta.role = 'equipe';
    w = await ag.click(labels[1] || 'Demandes', { within: '#adminmenu' }); if (w) return w;
    const first = await page.locator('table tbody tr').first().innerText().catch(() => '');
    return first.includes(ref) ? null : `top row is not ${ref}: « ${first.slice(0, 80)} »`;
  });
  s = hubStep(3, 2);
  await step('T4', 2, s.text, async () => {
    let w = await ag.click(ref, { exact: false }); if (w) { const l = page.locator('table tbody tr').first().getByRole('link').first(); await l.click(); ag.clicks++; await page.waitForLoadState(); }
    const sel = page.getByLabel('Statut', { exact: true });
    if (!(await sel.count())) return 'no « Statut » field';
    await sel.selectOption({ label: 'Qualifiée' }); ag.clicks++;
    w = await ag.click('Enregistrer'); if (w) return w;
    const t = await page.locator('body').innerText();
    if (!/Nouvelle\s*→\s*Qualifiée|Nouvelle.*Qualifiée/s.test(t)) return 'history does not show Nouvelle → Qualifiée';
    const paris = new Intl.DateTimeFormat('fr-FR', { timeZone: 'Europe/Paris', hour: '2-digit', minute: '2-digit' }).format(new Date());
    const times = [...t.matchAll(/\b(\d{2}:\d{2})\b/g)].map((m) => m[1]);
    const near = (a, b) => Math.abs((+a.slice(0, 2) * 60 + +a.slice(3)) - (+b.slice(0, 2) * 60 + +b.slice(3))) <= 3;
    if (!times.some((x) => near(x, paris))) finding({ check: 'B2', option: OPT, page: page.url(), role: 'equipe', width: 1440, text: `times shown: ${[...new Set(times)].join(', ')}; Paris now ${paris}`, note: 'the change just made is not shown in Paris time' });
    return null;
  });
  s = hubStep(3, 3);
  await step('T4', 3, s.text, async () => {
    let w = await ag.click('Demandes', { within: '#adminmenu' }); if (w) return w;
    const dl = page.waitForEvent('download', { timeout: 15000 }).catch(() => null);
    w = await ag.click('Exporter en CSV'); if (w) return 'hub says « Export the list as a spreadsheet file (CSV) »: ' + w;
    const d = await dl; if (!d) return 'no CSV download';
    const p = join(SHOTS, '..', 'a-demandes.csv'); await d.saveAs(p);
    const csv = readFileSync(p, 'utf8'); if (!csv.includes(ref)) return `CSV lacks ${ref}`;
    const q = [...s.text.matchAll(/«\s*([^»]+?)\s*»/g)].map((m) => m[1]).pop();
    w = await ag.click(q, { within: '#adminmenu' }); if (w) return w;
    return (await ag.sees(ref)) ? null : `« ${q} » does not list ${ref}`;
  });
  res.evidence['4'] = rows.slice(-3).every((r) => r.ok);
  await crawlMenu(page, 'equipe');
  for (const p of ['/wp-admin/index.php']) { await page.goto(A + p); await probeButtons(page, { option: OPT, state: 'equipe dashboard' }); }

  // Task 5
  s = hubStep(4, 1);
  await step('T5', 1, s.text, async () => {
    const q = (s.text.match(/«\s*([^»]+?)\s*»/) || [])[1];
    let w = await ag.click(q, { within: '#adminmenu' }); if (w) return w;
    if (/DEMO-GME-[A-Z0-9]{4}/.test(await page.content())) return 'codes are not hidden';
    const reason = page.getByLabel(/Raison de la demande/).filter({ visible: true }).first();
    if (!(await reason.count())) return 'no reason field';
    await reason.fill('Devis pour un groupe, trois places.');
    w = await ag.click('Demander l’accès'); if (w) return w;
    return null;
  });
  s = hubStep(4, 2);
  await step('T5', 2, s.text, async () => {
    let w = await logout(page, ag); if (w) return w;
    w = (await ag.fill('Identifiant ou adresse e-mail', 'direction')) || (await ag.fill('Mot de passe', PASSWORD, { exact: true })) || (await ag.click('Se connecter')); if (w) return w;
    page.__meta.role = 'direction';
    w = await ag.click('Approuver (24 h)'); if (w) return w;
    return (await ag.sees(/approuv|accord/i)) ? null : 'no approval confirmation';
  });
  await crawlMenu(page, 'direction (after approval)');
  s = hubStep(4, 3);
  await step('T5', 3, s.text, async () => {
    let w = await logout(page, ag); if (w) return w;
    w = (await ag.fill('Identifiant ou adresse e-mail', 'equipe')) || (await ag.fill('Mot de passe', PASSWORD, { exact: true })) || (await ag.click('Se connecter')); if (w) return w;
    page.__meta.role = 'equipe';
    w = await ag.click('Accès GM&E', { within: '#adminmenu' }); if (w) return w;
    let why = null;
    if (!/DEMO-GME-[A-Z0-9]{4}/.test(await page.locator('#wpbody').innerText())) {
      w = await ag.click('Révéler le code'); if (w) return 'code not shown and ' + w;
      why = 'hub says « the code is shown » after signing in; the reader must still click « Révéler le code »';
    }
    if (!/DEMO-GME-[A-Z0-9]{4}/.test(await page.locator('#wpbody').innerText())) return 'code still not shown';
    const menu = await page.$$eval('#adminmenu a', (as) => as.map((a) => a.innerText.trim()).join(' | '));
    if (!/Journal GM&E/.test(menu) && !/consultation|affichage enregistré|journal/i.test(await page.locator('#wpbody').innerText())) why = (why ? why + '; ' : '') + 'equipe sees no access record (« Journal GM&E » is Direction-only)';
    return { why, extra: 'reveal' };
  });
  res.evidence['5'] = rows.slice(-3).every((r) => r.ok);
  // Editing all pages (D1 row « Works in the demo » for A)
  await login(page, 'direction');
  const pages = await page.goto(A + '/wp-admin/edit.php?post_type=page').then((r) => r.status()).catch(() => 0);
  const pageText = await page.locator('#wpbody').innerText().catch(() => '');
  await S(page, 'direction pages list');
  res.pagesEditor = { status: pages, ok: pages === 200 && !/Désolé|pas autorisé|not allowed/i.test(pageText) };

  // C7 + C1: expired session and bad admin URL
  await page.goto(A + '/wp-admin/admin.php?page=asset-demandes');
  await ctx.clearCookies();
  await page.reload(); await page.waitForLoadState();
  const r7 = await S(page, 'C7 expired session (admin reload)');
  const t7 = await page.locator('body').innerText();
  if (!/Session expirée|session a expiré|expiré/i.test(t7)) finding({ check: 'C7', option: OPT, page: page.url(), role: 'equipe', width: 1440, text: t7.split('\n').filter(Boolean).slice(0, 3).join(' | ').slice(0, 200), note: 'after the session ends the reader lands on the login page with no « Session expirée » message', shot: r7 && r7.shot });
  await login(page, 'equipe');
  page.__meta.expectErrorDoc = true;
  await page.goto(A + '/wp-admin/admin.php?page=page-inexistante');
  await S(page, 'error bad admin URL');
  await page.goto(A + '/wp-admin/admin.php?page=asset-gme-journal');
  await S(page, 'error equipe opens Journal GM&E');
  page.__meta.expectErrorDoc = false;
  E(page, 'errors');
  await ctx.close();
  return res;
}

// ---------------------------------------------------------------- admin at 390 and six widths
export async function phoneA(browser) {
  const { ctx, page } = await newCtx(browser, { width: 390, option: OPT });
  page.setDefaultTimeout(60000);
  for (const who of ['contributeur', 'equipe', 'direction']) {
    await login(page, who);
    await crawlMenu(page, `${who} 390`);
    E(page, who);
  }
  // six widths, direction
  for (const w of WIDTHS6) {
    await page.setViewportSize({ width: w, height: w < 500 ? 844 : 900 });
    for (const p of ['/wp-admin/index.php', '/wp-admin/admin.php?page=asset-demandes', '/wp-admin/admin.php?page=asset-gme', '/wp-admin/edit.php?post_type=asset_congres']) { await page.goto(A + p); await snap(page, { option: OPT, surface: 'A-admin', state: `6w direction ${p}`, b4: true, rules: ['B4', 'C6', 'C4'], shot: false }); }
  }
  await ctx.close();
}

// ---------------------------------------------------------------- hosted boots (A2 + C10 task 1 literal)
export async function hostedA(browser, hub) {
  const out = { boots: [] };
  const links = [...new Map(hub.buttons.filter((b) => /playground/.test(b.href)).map((b) => [b.href, b])).values()];
  for (const l of links) {
    const kind = /blueprint-admin/.test(l.href) ? 'admin' : 'visitor';
    const { ctx, page } = await newCtx(browser, { width: 1440, option: 'A-hosted' });
    page.setDefaultTimeout(120000);
    const t0 = Date.now();
    const samples = [];
    page.goto(l.href).catch(() => {});
    let ready = 0; let frame = null;
    const want = kind === 'admin' ? /Tableau de bord|Demandes/ : /Catalogue des congrès/;
    for (let i = 0; i < 240 && !ready; i++) {
      await page.waitForTimeout(500);
      const sec = (Date.now() - t0) / 1000;
      if ([1, 3, 6, 10, 15, 20, 30].some((x) => Math.abs(sec - x) < 0.3)) {
        const p = join(SHOTS, `hosted-${kind}-${Math.round(sec)}s.png`);
        await page.screenshot({ path: p }).catch(() => {});
        const visible = await page.evaluate(() => (document.body ? document.body.innerText.trim().length : 0) + document.querySelectorAll('progress,[role=progressbar],svg,img,canvas').length).catch(() => 0);
        samples.push({ sec: Math.round(sec), shot: 'out/shots/' + p.split('/').pop(), bytes: statSync(p, { throwIfNoEntry: false })?.size || 0, visible });
      }
      for (const f of page.frames()) {
        try { const t = await f.evaluate(() => document.body ? document.body.innerText : ''); if (want.test(t)) { ready = (Date.now() - t0) / 1000; frame = f; break; } } catch {}
      }
    }
    out.boots.push({ kind, href: l.href, readySec: ready, samples, near: l.near });
    log(`A2 hosted ${kind}: ready after ${ready || 'TIMEOUT'} s`);
    const claim = (hub.passA.match(/about (\d+) to (\d+) seconds|(\d+)\s*[–-]\s*(\d+)\s*s/) || []);
    const hi = +(claim[2] || claim[4] || 0);
    if (!ready) finding({ check: 'A2', option: 'A-hosted', page: l.href, width: 1440, text: 'not ready after 120 s', note: `${kind} link never showed its first screen` });
    else if (hi && ready > hi) finding({ check: 'A2', option: 'A-hosted', page: l.href, width: 1440, text: `first screen after ${ready.toFixed(1)} s`, note: `hub promises « ${claim[0]} »` });
    const blank = samples.filter((x) => x.visible === 0 && x.sec >= 1 && (!ready || x.sec < ready));
    if (blank.length) finding({ check: 'A2', option: 'A-hosted', page: l.href, width: 1440, text: `blank at ${blank.map((b) => b.sec + ' s').join(', ')}`, note: 'no boot screen (no text, no progress) while loading', shot: blank[0].shot });
    if (frame) {
      await page.waitForTimeout(1500);
      const r = await snap(page, { option: 'A-hosted', surface: kind === 'admin' ? 'A-admin' : 'A-public', state: `hosted ${kind} first screen`, demo: true, b4: true, frame });
      flushErrors(page, { option: 'A-hosted', state: `hosted ${kind}` });
      if (kind === 'admin') {
        // C10 task 1, literally on the hub's admin link
        const rows = out.c10 = [];
        const T = hub.tasks[0].opts.A.steps;
        const signed = await frame.locator('#wpadminbar').count();
        const who = await frame.locator('#wp-admin-bar-my-account').innerText().catch(() => '');
        stepResult(rows, { option: 'A-hosted', task: 'T1', n: 1, text: T[0].text, ok: !!signed, why: signed ? '' : 'not signed in on arrival', clicks: 0, page: frame.url(), role: who.trim(), shot: r && r.shot, extra: `signed in as « ${who.trim()} »` });
        const ag = new Agent(frame, 'A-hosted');
        let why = null;
        for (const q of [...T[1].text.matchAll(/«\s*([^»]+?)\s*»/g)].map((m) => m[1])) { why = await ag.click(q, { within: '#adminmenu' }); if (why) break; }
        const r2 = await snap(page, { option: 'A-hosted', surface: 'A-admin', state: 'hosted admin after task 1 step 2', demo: true, frame });
        stepResult(rows, { option: 'A-hosted', task: 'T1', n: 2, text: T[1].text, ok: !why, why, clicks: ag.clicks, page: frame.url(), role: who.trim(), shot: r2 && r2.shot });
        // the hub says « The admin link signs you in automatically as administrator »: check the role shown
        RUN.notes.push(`hosted admin signed in as: ${who.trim()}`);
        out.adminWho = who.trim();
      }
    }
    await ctx.close();
  }
  return out;
}
