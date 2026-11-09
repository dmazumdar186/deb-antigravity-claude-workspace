// Eye-review screenshots + axe scans, fresh contexts, fr-FR / Europe/Paris. Run: LANG=fr_FR.UTF-8 node eye_axe.mjs 1440|390
import { chromium, AxeBuilder, B, ctx, login, reset, findCandidate, submitDelegate } from './lib.mjs';
import fs from 'node:fs';
const W = +(process.argv[2] || 1440); fs.mkdirSync('eye', { recursive: true });
const br = await chromium.launch({ env: { ...process.env, LANG: 'fr_FR.UTF-8' } });
const axe = []; const shots = []; const text = {};
const FORBID = /DEMO-GME|GM&E|GMÉ|Air France|KLM|\btarif|\bfare|€|seuil|Seuil|code promo|Passagers|DV-2026|Laboratoire|camille\.laurent|alice\.martin|bruno\.leroy|chloe\.petit/;
async function cap(p, name, { scan = true, pub = false } = {}) {
  await p.waitForTimeout(250);
  await p.screenshot({ path: `eye/${W}-${name}.png`, fullPage: true }); shots.push(name);
  if (pub) { const h = await p.content(); const t = await p.locator('body').innerText(); const m = (h.match(FORBID) || t.match(FORBID)); text[name] = { forbidden: m ? m[0] : null, lang: await p.evaluate(() => document.documentElement.lang), title: await p.title() }; }
  if (!scan) return;
  const r = await new AxeBuilder({ page: p }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice']).analyze();
  for (const v of r.violations) axe.push({ W, screen: name, id: v.id, impact: v.impact, n: v.nodes.length, help: v.help, targets: v.nodes.slice(0, 3).map((x) => x.target.join(' ')), sum: v.nodes[0]?.failureSummary?.slice(0, 200) });
  axe.push({ W, screen: name, ok: true, violations: r.violations.length, passes: r.passes.length, incomplete: r.incomplete.map((i) => i.id) });
}
const { c: sc, p: s } = await ctx(br, W); await login(s, 'equipe');
const cand = await findCandidate(s); const id = cand.pick.id;
await s.goto(B + '/console/demandes/' + id); await cap(s, 'staff-detail-nolink');
await s.getByRole('button', { name: 'Créer le lien' }).click(); await s.waitForLoadState(); await cap(s, 'staff-groupe-created-empty');
const url = await s.locator('[data-group-url]').inputValue();
await s.goto(B + '/console/demandes/' + id); await cap(s, 'staff-detail-withlink');
const T = Date.now() % 100000;
const d1 = await ctx(br, W); const d2 = await ctx(br, W);
await d1.p.goto(url); await cap(d1.p, 'public-form', { pub: true });
await d1.p.getByLabel('Date aller').fill(''); await d1.p.waitForTimeout(3300); await d1.p.getByRole('button', { name: 'Envoyer mes informations' }).click(); await d1.p.waitForLoadState(); await cap(d1.p, 'public-form-errors', { pub: true });
await submitDelegate(d1.p, url, { name: `Gaëlle Fontaine-Lemaire ${T} (exemple)`, email: `gaelle.${T}@example.com`, city: 'Saint-Étienne' }); await cap(d1.p, 'public-confirmation', { pub: true });
await submitDelegate(d2.p, url, { name: `Hugo Bernard ${T} (exemple)`, email: `hugo.${T}@example.com`, city: 'Toulouse' });
await submitDelegate(d2.p, url, { name: `Gaëlle Fontaine ${T} (exemple)`, email: `gaelle.${T}@example.com`, city: 'Clermont-Ferrand' });
await cap(d2.p, 'public-confirmation-pending', { pub: true });
await s.goto(B + `/console/demandes/${id}/groupe`); await cap(s, 'staff-groupe-pending');
await s.getByLabel('Seuil groupe (à confirmer)').fill('3'); await s.getByRole('button', { name: 'Enregistrer' }).click(); await s.waitForLoadState(); await cap(s, 'staff-groupe-hint');
await s.goto(B + '/console/demandes/1/groupe'); await cap(s, 'staff-groupe-seed');
const seed = await s.locator('[data-group-url]').inputValue();
const d3 = await ctx(br, W); await d3.p.goto(seed); await cap(d3.p, 'public-seed-form', { pub: true });
await d3.p.goto(B + '/g/' + 'Z'.repeat(43)); await cap(d3.p, 'public-unknown', { pub: true });
s.once('dialog', (d) => d.accept()); await s.goto(B + `/console/demandes/${id}/groupe`); await s.getByRole('button', { name: 'Révoquer le lien' }).click(); await s.waitForLoadState(); await cap(s, 'staff-groupe-revoked');
await d1.p.goto(url); await cap(d1.p, 'public-revoked', { pub: true });
const errs = { s: s.errs, d1: d1.p.errs, d2: d2.p.errs, d3: d3.p.errs }; const s5 = [...s.s5, ...d1.p.s5, ...d2.p.s5, ...d3.p.s5];
const rs = [await reset(s), await reset(d1.p), await reset(d2.p), await reset(d3.p)];
fs.writeFileSync(`axe-${W}.json`, JSON.stringify({ axe, shots, text, errs, s5, rs }, null, 1));
const v = axe.filter((x) => !x.ok);
console.log('screens', axe.filter((x) => x.ok).length, 'violations', v.length, 'serious/critical', v.filter((x) => /serious|critical/.test(x.impact)).length);
for (const x of v) console.log(x.impact, x.id, x.screen, x.n, x.targets[0], x.sum);
console.log(JSON.stringify(text, null, 1)); console.log(JSON.stringify({ errs, s5, rs }));
await br.close();
