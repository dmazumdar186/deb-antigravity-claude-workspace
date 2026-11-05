// Smoke test for Option B. BASE=https://... node qa/B/smoke_B.mjs  (target < 2 min)
import { writeFileSync } from 'node:fs';
const BASE = process.env.BASE || 'https://asset-voyages-demo.debanjan186.workers.dev';
const t0 = Date.now(); const res = []; const jar = {};
async function req(path, { method = 'GET', form } = {}) {
  const h = { cookie: Object.entries(jar).map(([k, v]) => `${k}=${v}`).join('; ') }; let body;
  if (form) { h['content-type'] = 'application/x-www-form-urlencoded'; h.origin = BASE; body = new URLSearchParams(form).toString(); }
  const r = await fetch(BASE + path, { method, headers: h, body, redirect: 'manual', signal: AbortSignal.timeout(20000) });
  for (const sc of r.headers.getSetCookie()) { const [kv] = sc.split(';'); const i = kv.indexOf('='); const v = kv.slice(i + 1); if (/Max-Age=0/i.test(sc) || !v) delete jar[kv.slice(0, i)]; else jar[kv.slice(0, i)] = v; }
  return { status: r.status, text: r.status >= 300 && r.status < 400 ? '' : await r.text(), loc: r.headers.get('location') };
}
const chk = async (name, fn) => { try { const e = await fn(); res.push({ name, ok: true }); console.log('PASS', name, e || ''); } catch (e) { res.push({ name, ok: false, err: e.message }); console.log('FAIL', name, e.message); } };
const ok = (c, m) => { if (!c) throw new Error(m); };
await chk('catalogue 200 with 12 congresses', async () => { const r = await req('/'); ok(r.status === 200, r.status); const n = new Set([...r.text.matchAll(/\/congres\/[a-z0-9-]+/g)].map((m) => m[0])).size; ok(n === 12, 'n=' + n); return n; });
await chk('congress page 200', async () => { const r = await req('/congres/congres-europeen-de-cardiologie-cg-0101'); ok(r.status === 200 && /name="_token"/.test(r.text), r.status); });
await chk('console login page 200', async () => { const r = await req('/console/connexion'); ok(r.status === 200, r.status); });
await chk('static asset + robots 200', async () => { const r = await req('/robots.txt'); ok(r.status === 200, r.status); });
let csrf;
for (const u of ['contributeur', 'equipe', 'direction']) await chk(`login ${u}`, async () => {
  for (const k of Object.keys(jar)) if (k.includes('session')) delete jar[k];
  const g = await req('/console/connexion'); const tok = /name="_token" value="([^"]+)"/.exec(g.text)[1];
  const r = await req('/console/connexion', { method: 'POST', form: { _token: tok, username: u, password: 'demo-asset' } }); ok(r.status === 303, 'login ' + r.status);
  const d = await req('/console'); ok(d.status === 200, 'dash ' + d.status); csrf = /name="_csrf" value="([^"]+)"/.exec(d.text)?.[1];
});
await chk('enquiry submitted and appears in Demandes (as equipe)', async () => {
  const g = await req('/congres/congres-europeen-de-cardiologie-cg-0101'); const token = /name="_token" value="([^"]+)"/.exec(g.text)[1]; await new Promise((r) => setTimeout(r, 3300));
  const r = await req('/demande', { method: 'POST', form: { _token: token, congress: '101', name: 'Smoke Test', email: 'smoke@example.com', phone: '0123456789', departure_city: 'Lille', date_out: '2027-08-26', date_back: '2027-08-31', passengers: '2', consent: '1' } });
  ok(r.status === 303, 'post ' + r.status); const ref = /ref=(DV-\d{4}-\d{4})/.exec(r.loc)[1];
  for (const k of Object.keys(jar)) if (k.includes('session')) delete jar[k];
  const lg = await req('/console/connexion'); const tok = /name="_token" value="([^"]+)"/.exec(lg.text)[1]; await req('/console/connexion', { method: 'POST', form: { _token: tok, username: 'equipe', password: 'demo-asset' } });
  const l = await req('/console/demandes'); ok(l.text.includes(ref), 'ref missing'); return ref;
});
const secs = (Date.now() - t0) / 1000; console.log(`SMOKE ${res.filter((r) => r.ok).length}/${res.length} in ${secs.toFixed(1)}s`);
writeFileSync(new URL('./logs/smoke_result.json', import.meta.url), JSON.stringify({ base: BASE, secs, res }, null, 1)); process.exit(res.every((r) => r.ok) && secs < 120 ? 0 : 1);
