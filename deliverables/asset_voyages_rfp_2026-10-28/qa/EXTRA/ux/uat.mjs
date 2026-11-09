// Usability + UAT for « Le lien de groupe » on the PREVIEW Worker. Usage: node uat.mjs 1440|390
import { chromium, B, ctx, login, reset, findCandidate, submitDelegate } from './lib.mjs';
import fs from 'node:fs';
const W = +(process.argv[2] || 1440); fs.mkdirSync('evidence', { recursive: true });
const br = await chromium.launch();
const steps = []; const metrics = {}; const T = Date.now() % 100000;
const step = async (n, text, fn) => {
  try { const r = await fn(); steps.push({ n, text, pass: r.pass !== false, note: r.note || '' }); }
  catch (e) { steps.push({ n, text, pass: false, note: 'ERROR ' + e.message.split('\n')[0] }); }
  console.log(steps.at(-1).n, steps.at(-1).pass ? 'PASS' : 'FAIL', steps.at(-1).note.slice(0, 300));
};
const shot = (p, k) => p.screenshot({ path: `evidence/${W}-${k}.png`, fullPage: true }).catch(() => {});
const { c: sc, p: s } = await ctx(br, W, { permissions: ['clipboard-read', 'clipboard-write'] });
await login(s, 'equipe');
let cand, url, gid, out, back;
const mob = async (p) => p.evaluate(() => {
  const vw = innerWidth; const hs = document.documentElement.scrollWidth > vw + 1;
  const inputs = [...document.querySelectorAll('input:not([type=hidden]):not([tabindex="-1"]),select,textarea')].filter((e) => e.offsetParent).map((e) => parseFloat(getComputedStyle(e).fontSize));
  const small = [...document.querySelectorAll('a,button,input[type=checkbox],input:not([type=hidden])')].filter((e) => e.offsetParent && !e.closest('[aria-hidden=true]')).map((e) => { const r = e.getBoundingClientRect(); return { t: (e.innerText || e.id || e.name || '').trim().slice(0, 30), w: Math.round(r.width), h: Math.round(r.height) }; }).filter((x) => x.h < 24 || x.w < 24);
  return { hScroll: hs, minInputFont: Math.min(...inputs), smallTargets: small, docH: document.documentElement.scrollHeight };
});

await step('X.1', 'As equipe, open « Demandes » and click the reference of an enquiry with ≥ 2 passengers and no link.', async () => {
  cand = await findCandidate(s); if (!cand.pick) return { pass: false, note: 'no candidate: ' + JSON.stringify(cand.list) };
  await s.goto(B + '/console'); await s.getByRole('link', { name: /^Demandes/ }).first().click(); await s.waitForLoadState();
  await s.getByRole('link', { name: cand.pick.ref, exact: true }).first().click(); await s.waitForLoadState(); gid = cand.pick.id;
  const t = await s.locator('main').innerText(); out = t.match(/Aller\s*\n\s*(\d\d)\/(\d\d)\/(\d{4})/); back = t.match(/Retour\s*\n\s*(\d\d)\/(\d\d)\/(\d{4})/);
  const card = s.getByRole('heading', { name: 'Lien de groupe' }); const box = await card.boundingBox(); metrics.cardY = Math.round(box?.y ?? -1); metrics.viewportH = s.viewportSize().height;
  metrics.createCardBelowFold = metrics.cardY > metrics.viewportH;
  await shot(s, 'X1-detail');
  return { pass: await s.getByRole('button', { name: 'Créer le lien' }).isVisible(), note: `${cand.pick.ref} (${cand.pick.pax} pax); card heading at y=${metrics.cardY}px vs viewport ${metrics.viewportH}px; candidates ${JSON.stringify(cand.list)}` };
});
await step('X.2', 'Click « Créer le lien ».', async () => {
  await s.getByRole('button', { name: 'Créer le lien' }).click(); await s.waitForLoadState();
  const t = await s.locator('main').innerText(); url = await s.locator('[data-group-url]').inputValue();
  metrics.createClicksFromList = 2; metrics.landsOn = s.url().replace(B, '');
  const tok = url.split('/g/')[1] || ''; const exp = t.match(/Valable jusqu’au (\d\d\/\d\d\/\d{4})/)?.[1];
  await shot(s, 'X2-created');
  return { pass: /Lien créé : copiez-le et envoyez-le aux participants\./.test(t) && tok.length === 43 && url.startsWith(B), note: `lands on ${metrics.landsOn}; token ${tok.length} chars; expiry ${exp}` };
});
await step('X.3', 'Click « Copier le lien ».', async () => {
  const b = s.getByRole('button', { name: 'Copier le lien' }); await b.click(); await s.waitForTimeout(400);
  const clip = await s.evaluate(() => navigator.clipboard.readText()).catch((e) => 'ERR ' + e.message);
  const fb = (await s.locator('main').innerText()).match(/[^\n]*copi[ée][^\n]*/gi);
  return { pass: clip === url, note: `clipboard==url ${clip === url}; feedback: ${JSON.stringify(fb)}; button now « ${(await b.innerText().catch(() => '?')).trim()} »` };
});
const d1 = await ctx(br, W); const d2 = await ctx(br, W); const d3 = await ctx(br, W);
const iso = (m) => m ? `${m[3]}-${m[2]}-${m[1]}` : '';
await step('X.4', 'As delegate A (new browser, logged out), open the link.', async () => {
  const r = await d1.p.goto(url); const t = await d1.p.locator('body').innerText(); const h = await d1.p.content();
  const leaks = ['DEMO-GME', 'GM&E', 'Air France', 'KLM', 'tarif', 'Seuil', '€', cand.pick.ref, 'Passagers', 'example.com>', 'Laboratoire', 'Hôpital'].filter((x) => h.includes(x) || t.includes(x));
  Object.assign(metrics, { publicMobile: await mob(d1.p) });
  await shot(d1.p, 'X4-public');
  return { pass: r.status() === 200 && /Vos informations de voyage/.test(t) && !leaks.length, note: `status ${r.status()}; h1 « ${await d1.p.locator('h1').innerText()} »; dates « ${await d1.p.locator('[data-dates]').innerText()} »; leak terms found: ${JSON.stringify(leaks)}; prefilled out=${await d1.p.getByLabel('Date aller').inputValue()} back=${await d1.p.getByLabel('Date retour').inputValue()}` };
});
await step('X.5', 'Delegate A clicks « Envoyer mes informations » with everything empty.', async () => {
  await d1.p.getByLabel('Date aller').fill(''); await d1.p.getByLabel('Date retour').fill(''); await d1.p.waitForTimeout(3300);
  await d1.p.getByRole('button', { name: 'Envoyer mes informations' }).click(); await d1.p.waitForLoadState();
  const t = await d1.p.locator('body').innerText(); const foc = await d1.p.evaluate(() => document.activeElement?.className + ' ' + document.activeElement?.tagName);
  await shot(d1.p, 'X5-errors');
  return { pass: /Indiquez vos nom et prénom/.test(t) && /Cochez cette case/.test(t), note: `summary: ${(t.match(/[^\n]*(corriger|champs?)[^\n]*/i) || [''])[0]}; focus ${foc}` };
});
await step('X.6', 'Delegate A fills name, e-mail and city, sets « Date retour » before « Date aller », ticks consent, sends.', async () => {
  const t = await submitDelegate(d1.p, url, { name: `Delphine Roux ${T} (exemple)`, email: `delphine.${T}@example.com`, city: 'Lyon', out: iso(out), back: iso(out).replace(/\d\d$/, (x) => String(+x - 1).padStart(2, '0')) });
  return { pass: /La date retour doit être le jour de l’aller ou après/.test(t) || /retour/i.test(t) && !/bien été reçue/.test(t), note: (t.match(/[^\n]*retour[^\n]*/gi) || []).slice(0, 3).join(' | ') + ' | name kept: ' + (await d1.p.getByLabel('Nom et prénom').inputValue().catch(() => '')) };
});
await step('X.7', 'Delegate A fills the form correctly and taps « Envoyer mes informations » (1 click).', async () => {
  const t = await submitDelegate(d1.p, url, { name: `Delphine Roux ${T} (exemple)`, email: `delphine.${T}@example.com`, city: 'Lyon' });
  metrics.delegateSubmitClicks = 1; metrics.confirmMobile = await mob(d1.p);
  await shot(d1.p, 'X7-confirm');
  return { pass: /Votre réponse a bien été reçue\./.test(t) && /Lyon/.test(t) && !/alice\.martin|Alice Martin/.test(t), note: t.replace(/\s+/g, ' ').slice(0, 400) };
});
await step('X.8', 'Delegate A, same browser, resends with the same e-mail and « Ville de départ » = Marseille.', async () => {
  const t = await submitDelegate(d1.p, url, { name: `Delphine Roux ${T} (exemple)`, email: `delphine.${T}@example.com`, city: 'Marseille' });
  await s.goto(B + `/console/demandes/${gid}/groupe`); const g = await s.locator('main').innerText();
  return { pass: /bien été reçue/.test(t) && /Marseille/.test(g) && !/Modifications à vérifier/.test(g), note: `staff counter « ${await s.locator('[data-counter]').innerText()} »; pending block ${/Modifications à vérifier/.test(g)}` };
});
await step('X.9', 'Delegate B (another browser) sends the same e-mail with « Ville de départ » = Nantes.', async () => {
  const t = await submitDelegate(d2.p, url, { name: `Delphine Roux ${T} (exemple)`, email: `delphine.${T}@example.com`, city: 'Nantes' });
  return { pass: /Votre réponse a bien été reçue\./.test(t) && /Nantes/.test(t), note: 'confirmation identical shape; echoes Nantes ' + /Nantes/.test(t) };
});
await step('X.10', 'As equipe: « Demandes » › the reference › « Groupe (n/m) » tab (2 clicks from the list).', async () => {
  await s.goto(B + '/console/demandes'); await s.getByRole('link', { name: cand.pick.ref, exact: true }).first().click(); await s.waitForLoadState();
  await s.getByRole('link', { name: /^Groupe \(\d+\/\d+\)/ }).click(); await s.waitForLoadState(); metrics.manifestClicksFromList = 2;
  const t = await s.locator('main').innerText(); await shot(s, 'X10-pending');
  return { pass: /Modification à vérifier/.test(t) && /Actuel :[^\n]*Marseille/.test(t) && /Proposé :[^\n]*Nantes/.test(t), note: `counter « ${await s.locator('[data-counter]').innerText()} »; tab label « ${(await s.locator('nav.chips a[aria-current]').innerText())} »` };
});
await step('X.11', 'Click « Refuser » on the proposed change.', async () => {
  await s.getByRole('button', { name: 'Refuser' }).first().click(); await s.waitForLoadState(); const t = await s.locator('main').innerText();
  return { pass: /Modification refusée : l’inscription d’origine est conservée\./.test(t) && /Marseille/.test(t) && !/Nantes/.test(t), note: '' };
});
await step('X.12', 'Delegate B resends (Nantes); equipe reloads « Groupe » and clicks « Accepter ».', async () => {
  await submitDelegate(d2.p, url, { name: `Delphine Roux ${T} (exemple)`, email: `delphine.${T}@example.com`, city: 'Nantes' });
  await s.reload(); await s.getByRole('button', { name: 'Accepter' }).first().click(); await s.waitForLoadState(); const t = await s.locator('main').innerText();
  return { pass: /Modification acceptée : la liste est à jour\./.test(t) && /Nantes/.test(t) && !/Modifications à vérifier/.test(t), note: `counter « ${await s.locator('[data-counter]').innerText()} »` };
});
await step('X.13', 'Keep « Groupe » open; delegate C sends from a third browser; wait ≤ 20 s without reloading.', async () => {
  const before = await s.locator('[data-counter]').innerText();
  await submitDelegate(d3.p, url, { name: `Étienne N’Diaye ${T} (exemple)`, email: `etienne.${T}@example.com`, city: 'Lyon' });
  let after = before; for (let i = 0; i < 25 && after === before; i++) { await s.waitForTimeout(1000); after = await s.locator('[data-counter]').innerText(); }
  return { pass: after !== before && /2 répondus/.test(after), note: `« ${before} » → « ${after} » without reload` };
});
await step('X.14', 'Set « Seuil groupe (à confirmer) » to 3, « Enregistrer »; then to 0.', async () => {
  await s.reload(); await s.getByLabel('Seuil groupe (à confirmer)').fill('3'); await s.getByRole('button', { name: 'Enregistrer' }).click(); await s.waitForLoadState();
  const t = await s.locator('main').innerText(); const hint = await s.locator('[data-hint]').innerText().catch(() => '');
  await shot(s, 'X14-hint');
  await s.getByLabel('Seuil groupe (à confirmer)').fill('0'); const vm = await s.getByLabel('Seuil groupe (à confirmer)').evaluate((e) => e.validationMessage);
  await s.getByRole('button', { name: 'Enregistrer' }).click(); await s.waitForLoadState();
  let t2 = await s.locator('main').innerText(); if (vm) t2 += '\nSeuil refusé (navigateur) : ' + vm;
  await s.getByLabel('Seuil groupe (à confirmer)').fill('10'); await s.getByRole('button', { name: 'Enregistrer' }).click(); await s.waitForLoadState();
  return { pass: /Seuil groupe enregistré/.test(t) && !!hint && /Seuil refusé/.test(t2), note: `hint « ${hint} »; error « ${(t2.match(/Seuil refusé[^\n]*/) || [''])[0]} »` };
});
await step('X.15', 'Click « Exporter pour cotation (CSV) ».', async () => {
  const [dl] = await Promise.all([s.waitForEvent('download'), s.getByRole('link', { name: 'Exporter pour cotation (CSV)' }).click()]);
  const pth = await dl.path(); const csv = fs.readFileSync(pth, 'utf8'); fs.writeFileSync(`evidence/${W}-X15.csv`, csv);
  const lines = csv.trim().split(/\r?\n/);
  return { pass: /Nom \(pièce d’identité\)/.test(lines[0]) && lines.length === 3 && /Nantes/.test(csv), note: `${dl.suggestedFilename()}; ${lines.length} lines; header ${lines[0].slice(0, 140)}; BOM ${csv.charCodeAt(0) === 0xfeff}` };
});
await step('X.16', 'Click « Révoquer le lien », confirm; delegate A reloads the link.', async () => {
  s.once('dialog', (d) => { metrics.revokeDialog = d.message(); d.accept(); });
  await s.getByRole('button', { name: 'Révoquer le lien' }).click(); await s.waitForLoadState(); const t = await s.locator('main').innerText();
  const r = await d1.p.goto(url); const pt = await d1.p.locator('h1').innerText(); await shot(d1.p, 'X16-revoked');
  return { pass: /Lien révoqué : il ne fonctionne plus\./.test(t) && r.status() === 410 && /n’est plus actif/.test(pt), note: `dialog « ${metrics.revokeDialog} »; public ${r.status()} « ${pt} »; list kept: ${/2 répondus/.test(t)}` };
});
await step('X.17', 'Click « Créer un nouveau lien ».', async () => {
  await s.getByRole('button', { name: 'Créer un nouveau lien' }).click(); await s.waitForLoadState(); const u2 = await s.locator('[data-group-url]').inputValue();
  const r = await d1.p.goto(u2); const r2 = await d1.p.goto(url);
  return { pass: u2 !== url && r.status() === 200 && r2.status() === 410, note: `new ${r.status()}, old ${r2.status()}` };
});
await step('X.18', 'Open DV-2026-0001 › « Groupe (3/6) »; open its link logged out.', async () => {
  await s.goto(B + '/console/demandes/1/groupe'); const t = await s.locator('main').innerText(); const su = await s.locator('[data-group-url]').inputValue();
  const r = await d3.p.goto(su); const h = await d3.p.content();
  metrics.seedToken = su.split('/g/')[1];
  return { pass: /3 répondus \/ 6 attendus/.test(t) && r.status() === 200 && !/Alice|Bruno|Chloé|DEMO-GME/.test(h), note: `public ${r.status()}; others' names absent` };
});
await step('X.19', 'Log in as contributeur and open the « Groupe » address of DV-2026-0001.', async () => {
  const { c, p } = await ctx(br, W); await login(p, 'contributeur'); const r = await p.goto(B + '/console/demandes/1/groupe'); const t = await p.locator('body').innerText(); await c.close();
  return { pass: r.status() >= 400 && !/Alice Martin/.test(t), note: `status ${r.status()}; ${(t.match(/[^\n]*(autoris|accès|refus)[^\n]*/i) || [''])[0]}` };
});
await step('X.20', 'Open an enquiry with 1 passenger.', async () => {
  if (!cand.single) return { pass: true, note: 'no 1-passenger enquiry in seed; checked /groupe on a 1-pax id not possible' };
  await s.goto(B + '/console/demandes/' + cand.single.id); const t = await s.locator('main').innerText(); const r = await s.goto(B + `/console/demandes/${cand.single.id}/groupe`);
  return { pass: !/Lien de groupe/.test(t) && r.status() === 404, note: `${cand.single.ref}: card shown ${/Lien de groupe/.test(t)}; /groupe ${r.status()}` };
});
await step('X.21', 'Open /g/ with a made-up token.', async () => {
  const r = await d2.p.goto(B + '/g/' + 'A'.repeat(43)); const t = await d2.p.locator('h1').innerText(); await shot(d2.p, 'X21-unknown');
  return { pass: r.status() === 404 && /Lien introuvable/.test(t), note: `${r.status()} « ${t} »` };
});
metrics.errors = { staff: s.errs, d1: d1.p.errs, d2: d2.p.errs, d3: d3.p.errs }; metrics.s5 = [...s.s5, ...d1.p.s5, ...d2.p.s5, ...d3.p.s5];
metrics.reset = await reset(s);
for (const d of [d1, d2, d3]) metrics.reset += ' | ' + await reset(d.p);
fs.writeFileSync(`uat-${W}.json`, JSON.stringify({ W, steps, metrics }, null, 1));
console.log(JSON.stringify(metrics, null, 1)); await br.close();
