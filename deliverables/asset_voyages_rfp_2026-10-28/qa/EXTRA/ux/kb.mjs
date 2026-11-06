// Keyboard-only: delegate form, staff create/copy, accept/refuse. Usage: node kb.mjs 1440|390
import { chromium, B, ctx, login, reset, submitDelegate } from './lib.mjs';
import fs from 'node:fs';
const W = +(process.argv[2] || 1440); const br = await chromium.launch(); const out = []; const noFocus = new Map();
const info = () => { const e = document.activeElement; if (!e || e === document.body) return null; const cs = getComputedStyle(e); const r = e.getBoundingClientRect();
  const name = (e.labels && e.labels[0] ? e.labels[0].innerText : '') || e.getAttribute('aria-label') || e.innerText || e.value || '';
  const vis = (cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) > 0) || (cs.boxShadow && cs.boxShadow !== 'none');
  return { tag: e.tagName, id: e.id, name: name.replace(/\s+/g, ' ').trim().slice(0, 120), vis, inView: r.bottom > 0 && r.top < innerHeight && r.width > 0 }; };
async function tabTo(p, re, max = 120) { for (let i = 0; i < max; i++) { await p.keyboard.press('Tab'); let f; try { f = await p.evaluate(info); } catch { await p.waitForLoadState('load'); f = await p.evaluate(info); } if (!f) continue;
  if (!f.vis || !f.inView) noFocus.set(p.url().replace(B, '').replace(/\/g\/[\w-]+/, '/g/T').replace(/\d+/g, 'N') + ' :: ' + f.tag + ' ' + f.name, (f.vis ? '' : 'NO-RING ') + (f.inView ? '' : 'OFFSCREEN')); if (re.test(f.name)) return i + 1; } throw new Error('not reached by Tab: ' + re + ' on ' + p.url()); }
async function act(p, re, key = 'Enter') { const n = await tabTo(p, re); await p.keyboard.press(key); await p.waitForTimeout(700); await p.waitForLoadState('load'); return n; }
async function type(p, re, txt) { const n = await tabTo(p, re); await p.keyboard.type(txt); return n; }
const T = Date.now() % 100000;
const { c: sc, p: s } = await ctx(br, W, { permissions: ['clipboard-read', 'clipboard-write'] });
let url = '', id = 3;
const res = async (k, fn) => { try { out.push({ k, W, pass: true, note: await fn() }); } catch (e) { out.push({ k, W, pass: false, note: e.message.split('\n')[0] }); } console.log(JSON.stringify(out.at(-1))); };
await res('staff-create-copy', async () => {
  await s.goto(B + '/console/connexion'); await type(s, /Identifiant/, 'equipe'); await type(s, /Mot de passe/, 'demo-asset'); await act(s, /Se connecter/);
  const a = await act(s, /^Demandes/); const b = await act(s, /^DV-2026-0003$/); const c = await act(s, /^Créer le lien$/);
  url = await s.locator('[data-group-url]').inputValue(); if (!url) throw new Error('no link');
  const d = await act(s, /^Copier le lien$/); const clip = await s.evaluate(() => navigator.clipboard.readText()).catch(() => '');
  return `tabs Demandes ${a}, ref ${b}, Créer ${c}, Copier ${d}; clipboard ok ${clip === url}; focus after create: ${JSON.stringify(await s.evaluate(info))}`;
});
const { c: dc, p: d } = await ctx(br, W);
await res('delegate-form', async () => {
  await d.goto(url); const t0 = Date.now(); const first = await (async () => { await d.keyboard.press('Tab'); return d.evaluate(info); })();
  await d.keyboard.press('Enter'); const afterSkip = await d.evaluate(() => document.activeElement?.tagName + '#' + document.activeElement?.id);
  const n1 = await type(d, /^Nom et prénom/, `Inès Kaci ${T} (exemple)`); await type(d, /^E-mail/, `ines.${T}@example.com`); await type(d, /^Ville de départ/, 'Bordeaux');
  await tabTo(d, /J’accepte/); await d.keyboard.press('Space'); await d.waitForTimeout(Math.max(0, 3300 - (Date.now() - t0)));
  const n2 = await act(d, /Envoyer mes informations/); const t = await d.locator('body').innerText(); const f = await d.evaluate(info);
  if (!/bien été reçue/.test(t)) throw new Error('not sent: ' + t.slice(0, 200));
  return `first Tab « ${first?.name} » vis ${first?.vis}; skip → ${afterSkip}; tabs to name ${n1}, to send ${n2}; focus after send: ${f?.tag} « ${f?.name} »`;
});
await res('delegate-errors-kb', async () => {
  const { c, p } = await ctx(br, W); await p.goto(url); await p.waitForTimeout(3300); await act(p, /Envoyer mes informations/);
  const f = await p.evaluate(() => ({ tag: document.activeElement?.tagName, cls: document.activeElement?.className, txt: document.activeElement?.innerText?.slice(0, 80) }));
  const links = await p.locator('.alert a[href^="#"]').count(); let jump = '';
  if (links) { await p.keyboard.press('Tab'); await p.keyboard.press('Enter'); await p.waitForTimeout(200); jump = await p.evaluate(() => document.activeElement?.id); }
  await c.close(); return `focus on submit-error: ${JSON.stringify(f)}; summary links ${links}; first link → #${jump}`;
});
await res('staff-refuse', async () => {
  const { c, p } = await ctx(br, W); await submitDelegate(p, url, { name: `Inès Kaci ${T} (exemple)`, email: `ines.${T}@example.com`, city: 'Pau' }); await c.close();
  await s.goto(B + '/console/demandes/3/groupe'); const n = await act(s, /^Refuser$/); const t = await s.locator('main').innerText();
  if (!/Modification refusée/.test(t)) throw new Error('refuse failed'); const f = await s.evaluate(info);
  return `tabs to Refuser ${n}; message focused: ${f?.name?.slice(0, 60)}`;
});
await res('staff-accept', async () => {
  const { c, p } = await ctx(br, W); await submitDelegate(p, url, { name: `Inès Kaci ${T} (exemple)`, email: `ines.${T}@example.com`, city: 'Pau' }); await c.close();
  await s.goto(B + '/console/demandes/3/groupe'); const n = await act(s, /^Accepter$/); const t = await s.locator('main').innerText();
  if (!/Modification acceptée/.test(t) || !/Pau/.test(t)) throw new Error('accept failed');
  const n2 = await tabTo(s, /Exporter pour cotation/); return `tabs to Accepter ${n}; then to CSV ${n2}`;
});
const nf = [...noFocus].map(([k, v]) => k + ' -> ' + v);
const rs = [await reset(s), await reset(d)];
fs.writeFileSync(`kb-${W}.json`, JSON.stringify({ out, noFocus: nf, rs, errs: [...s.errs, ...d.errs] }, null, 1));
console.log('focus issues', nf.length, nf.slice(0, 30).join('\n')); console.log(rs);
await br.close();
