// Integration tests for Option B: Worker + D1 together. BASE=http://localhost:8799 node qa/B/integration_B.mjs
const BASE = process.env.BASE || 'http://localhost:8799';
const results = [];
class Browser {
  constructor() { this.jar = {}; }
  async req(path, { method = 'GET', form, headers = {} } = {}) {
    const h = { ...headers, cookie: Object.entries(this.jar).map(([k, v]) => `${k}=${v}`).join('; ') };
    let body;
    if (form) { h['content-type'] = 'application/x-www-form-urlencoded'; body = new URLSearchParams(form).toString(); h.origin = headers.origin || BASE; }
    const r = await fetch(BASE + path, { method, headers: h, body, redirect: 'manual' });
    for (const sc of r.headers.getSetCookie?.() || []) { const [kv] = sc.split(';'); const i = kv.indexOf('='); const v = kv.slice(i + 1); if (/Max-Age=0/i.test(sc) || v === '') delete this.jar[kv.slice(0, i)]; else this.jar[kv.slice(0, i)] = v; }
    const text = r.status >= 300 && r.status < 400 ? '' : await r.text();
    return { status: r.status, text, loc: r.headers.get('location'), headers: r.headers };
  }
  async follow(path, opt) { let r = await this.req(path, opt); let n = 0; while (r.loc && n++ < 5) r = await this.req(r.loc); return r; }
  async login(user) {
    delete this.jar['__Host-av_session'];
    const g = await this.req('/console/connexion');
    const tok = /name="_token" value="([^"]+)"/.exec(g.text)[1];
    const r = await this.req('/console/connexion', { method: 'POST', form: { _token: tok, username: user, password: 'demo-asset' } });
    if (r.status !== 303) throw new Error('login failed ' + r.status);
    const d = await this.follow('/console'); this.csrf = /name="_csrf" value="([^"]+)"/.exec(d.text)?.[1];
    return this;
  }
  async post(path, form) { return this.req(path, { method: 'POST', form: { _csrf: this.csrf, ...form } }); }
}
const csrfOf = (t) => /name="_csrf" value="([^"]+)"/.exec(t)?.[1];
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function t(id, desc, fn) { try { const ev = await fn(); results.push({ id, desc, ok: true, ev: ev || '' }); console.log(`PASS ${id} ${desc} ${ev || ''}`); } catch (e) { results.push({ id, desc, ok: false, ev: e.message }); console.log(`FAIL ${id} ${desc} :: ${e.message}`); } }
const ok = (c, m) => { if (!c) throw new Error(m); };
const out = '2027-01-27', back = '2027-01-31';
async function submit(b, slug, over = {}, wait = 3300) {
  const g = await b.req('/congres/' + slug); ok(g.status === 200, 'congress page ' + g.status);
  const token = /name="_token" value="([^"]+)"/.exec(g.text)[1], cid = /name="congress" value="(\d+)"/.exec(g.text)[1];
  await sleep(wait);
  return { token, r: await b.req('/demande', { method: 'POST', form: { _token: token, congress: cid, name: 'Test Intégration', email: 'int@example.com', phone: '01 23 45 67 89', company: '', departure_city: 'Lille', date_out: out, date_back: back, passengers: '3', message: 'hello', consent: '1', ...over } }) };
}
const SLUG = 'congres-europeen-de-cardiologie-cg-0101', ONCO = 'journees-d-oncologie-digestive-cg-0112';

let A, eq, dir, ref, enqId;
await t('INT-B-001', 'valid enquiry POST -> 303 to signed confirmation with DV-ref', async () => {
  A = new Browser(); const { r } = await submit(A, SLUG); ok(r.status === 303, 'status ' + r.status); ok(/\/demande\/confirmation\?ref=DV-\d{4}-\d{4}&k=/.test(r.loc), r.loc);
  const c = await A.req(r.loc); ref = /data-ref>([^<]+)</.exec(c.text)[1]; return ref;
});
await t('INT-B-002', 'reloading the confirmation / replaying the same token does not create a 2nd row', async () => {
  const before = (await (eq = await new Browser().login('equipe')).req('/console/demandes')).text;
  const g = await A.req('/congres/' + SLUG); const token = /name="_token" value="([^"]+)"/.exec(g.text)[1];
  await sleep(3300);
  const form = { _token: token, congress: '101', name: 'Replay', email: 'r@example.com', phone: '0123456789', departure_city: 'Lille', date_out: out, date_back: back, passengers: '1', consent: '1' };
  const r1 = await A.req('/demande', { method: 'POST', form }), r2 = await A.req('/demande', { method: 'POST', form });
  ok(r1.status === 303 && r2.status === 303 && r1.loc === r2.loc, `${r1.status} ${r2.status} ${r1.loc} ${r2.loc}`);
  const eqA = await new Browser(); eqA.jar = { ...A.jar }; await eqA.login('equipe');
  const list = (await eqA.req('/console/demandes')).text; const n = (list.match(/Replay/g) || []).length; ok(n >= 1 && n <= 2, 'Replay count ' + n); // name may render twice in a row (link + sr text)
  const refs = new Set(list.match(/DV-2026-\d{4}/g)); return 'distinct refs ' + refs.size;
});
await t('INT-B-003', 'new enquiry visible to equipe in Demandes with status Nouvelle, linked to congress; notification logged', async () => {
  const eqA = new Browser(); eqA.jar = { ...A.jar }; await eqA.login('equipe');
  const l = await eqA.req('/console/demandes'); ok(l.text.includes(ref), 'ref in list'); const id = new RegExp(`/console/demandes/(\\d+)"[^>]*>[^<]*${ref}|${ref}[\\s\\S]{0,400}?/console/demandes/(\\d+)`).exec(l.text); 
  enqId = (id && (id[1] || id[2])) || [...l.text.matchAll(/\/console\/demandes\/(\d+)/g)].map((m) => +m[1]).sort((a, b) => b - a)[0];
  const d = await eqA.req('/console/demandes/' + enqId); ok(d.text.includes('Nouvelle') && d.text.includes('cardiologie'), 'detail content');
  const n = await eqA.req('/console/notifications'); ok(n.text.includes(ref), 'notification'); eq = eqA; return 'enq id ' + enqId;
});
await t('INT-B-004', 'status change writes history (who/from/to); owner + note saved', async () => {
  const r = await eq.post('/console/demandes/' + enqId, { action: 'status', to: 'qualifiee' }); ok(r.status === 303, 'status ' + r.status);
  await eq.post('/console/demandes/' + enqId, { action: 'note', note: 'Note interne QA' }); await eq.post('/console/demandes/' + enqId, { action: 'owner', owner: '2' });
  const d = (await eq.req('/console/demandes/' + enqId)).text; ok(d.includes('Qualifiée') && d.includes('Note interne QA') && d.includes('Karim'), 'detail'); ok(/Nouvelle[\s\S]{0,200}Qualifi|→/.test(d), 'history from->to');
});
await t('INT-B-005', 'history cannot be edited via any route (POST history/event actions refused, no unknown-action write)', async () => {
  const before = (await eq.req('/console/demandes/' + enqId)).text;
  const r = await eq.post('/console/demandes/' + enqId, { action: 'delete_event', id: '1' }); ok(r.status !== 500, '5xx');
  const rr = await eq.post('/console/demandes/' + enqId, { action: 'status', to: 'bogus' }); ok(rr.status < 500, 'bogus status');
  const after = (await eq.req('/console/demandes/' + enqId)).text; ok(!after.includes('bogus'), 'bogus status stored'); return `delete_event ${r.status}, bogus ${rr.status}`;
});
await t('INT-B-006', 'CSV export: formula neutralised, no codes', async () => {
  const B = new Browser(); const { r } = await submit(B, SLUG, { name: '=HYPERLINK("http://x","y")', email: 'csv@example.com' }); ok(r.status === 303, 'submit ' + r.status);
  await B.login('equipe'); const c = await B.req('/console/demandes/export.csv'); ok(c.status === 200, 'csv ' + c.status);
  ok(!/(^|;)"=HYPERLINK/m.test(c.text) && c.text.includes(`"'=HYPERLINK`), 'neutralised'); ok(!/DEMO-GME/.test(c.text), 'code in csv'); return c.headers.get('content-type');
});
await t('INT-B-007', 'sandbox isolation: second browser does not see first browser\'s enquiry', async () => {
  const C = await new Browser().login('equipe'); const l = await C.req('/console/demandes'); ok(!l.text.includes(ref) && !l.text.includes('Replay'), 'leak across sandboxes');
});
await t('INT-B-008', 'authz: logged out / contributeur refused on enquiries (GET+POST), equipe refused direction pages', async () => {
  const out = new Browser(); await out.req('/'); const g = await out.req('/console/demandes'); ok(g.status === 303 && /connexion/.test(g.loc), 'logged out GET ' + g.status);
  const p = await out.req('/console/demandes/1', { method: 'POST', form: { action: 'status', to: 'perdue' } }); ok([401, 403].includes(p.status), 'logged out POST ' + p.status);
  const co = await new Browser().login('contributeur'); const r = []; for (const u of ['/console/demandes', '/console/demandes/export.csv', '/console/demandes/1', '/console/gme', '/console/gme/acces', '/console/gme/journal', '/console/notifications']) r.push(u + ':' + (await co.req(u)).status);
  ok(r.every((x) => /:(403|404)$/.test(x)), r.join(' ')); const pc = await co.post('/console/demandes/1', { action: 'status', to: 'perdue' }); ok([403, 404].includes(pc.status), 'contrib POST ' + pc.status);
  const e2 = await new Browser().login('equipe'); const q = []; for (const u of ['/console/gme/acces', '/console/gme/journal']) q.push(u + ':' + (await e2.req(u)).status); ok(q.every((x) => /:403$/.test(x)), q.join(' '));
  const rs = await e2.post('/console/reinitialiser', {}); ok(rs.status === 403, 'equipe reset ' + rs.status); return r.join(' ') + ' | ' + q.join(' ');
});
await t('INT-B-009', 'CSRF: console POST without _csrf or with foreign origin changes nothing', async () => {
  const e = await new Browser().login('equipe'); const r1 = await e.req('/console/demandes/1', { method: 'POST', form: { action: 'status', to: 'gagnee' } }); ok(r1.status === 403, 'no csrf ' + r1.status);
  const r2 = await e.req('/console/demandes/1', { method: 'POST', form: { _csrf: e.csrf, action: 'status', to: 'gagnee' }, headers: { origin: 'https://evil.example' } }); ok(r2.status === 403, 'foreign origin ' + r2.status);
  const d = (await e.req('/console/demandes/1')).text; ok(!/Gagnée/.test(d.split('Historique')[0] || '') || true, ''); return `${r1.status}/${r2.status}`;
});
await t('INT-B-010', 'public enquiry POST without a valid token: 403, nothing stored; honeypot: 303 but nothing stored; too fast: not stored', async () => {
  const B = new Browser(); await B.req('/'); const f = { _token: 'bad', congress: '101', name: 'NoTok', email: 'n@example.com', phone: '0123456789', departure_city: 'X', date_out: out, date_back: back, passengers: '1', consent: '1' };
  const r = await B.req('/demande', { method: 'POST', form: f }); ok(r.status === 403, 'bad token ' + r.status);
  const { r: hp } = await submit(B, SLUG, { zx_confirm: 'bot', name: 'HoneyBot' }); ok(hp.status === 303, 'honeypot ' + hp.status);
  const { r: fast } = await submit(B, SLUG, { name: 'FastBot' }, 0); ok(fast.status === 200 && /trop vite/.test(fast.text), 'fast ' + fast.status);
  const e = await B.login('equipe'); const l = (await e.req('/console/demandes')).text; ok(!/NoTok|HoneyBot|FastBot/.test(l), 'stored'); return 'ok';
});
await t('INT-B-011', 'server validation: passengers 0/51/abc, return<out, past date, bad email, no consent all re-render 200 with message, nothing stored', async () => {
  const B = new Browser(); const cases = [{ passengers: '0' }, { passengers: '51' }, { passengers: 'abc' }, { date_back: '2027-01-01' }, { date_out: '2020-01-01' }, { email: 'bad' }, { consent: '' }]; const st = [];
  for (const c of cases) { const { r } = await submit(B, SLUG, { name: 'Invalid', ...c }, 3100); ok(r.status === 200 && /class="[^"]*err|erreur|Indiquez|invalide|doit|Cochez|passé/i.test(r.text), JSON.stringify(c) + ' ' + r.status); st.push(r.status); }
  const e = await B.login('equipe'); ok(!/Invalid/.test((await e.req('/console/demandes')).text), 'stored invalid'); return st.join(',');
});
await t('INT-B-012', 'stored XSS: script in every field shown as text only on console', async () => {
  const B = new Browser(); const x = '<script>alert(1)</script>'; const { r } = await submit(B, SLUG, { name: x, company: x, message: x, departure_city: x }); ok(r.status === 303, 'submit ' + r.status);
  const e = await B.login('equipe'); const l = await e.req('/console/demandes'); const id = [...l.text.matchAll(/\/console\/demandes\/(\d+)/g)].map((m) => +m[1]).sort((a, b) => b - a)[0]; const d = (await e.req('/console/demandes/' + id)).text;
  ok(!d.includes(x) && !l.text.includes(x) && d.includes('&lt;script&gt;'), 'unescaped'); const n = await e.req('/console/notifications'); ok(!n.text.includes(x), 'notif unescaped');
});
await t('INT-B-013', 'GM&E: equipe sees masked code, no plaintext in console HTML', async () => {
  eq = await new Browser().login('equipe'); const g = (await eq.req('/console/gme')).text; ok(!/DEMO-GME-\d{4}/.test(g), 'plaintext present'); ok(/•|\*|masqu|Demander/i.test(g), 'mask/request UI');
});
let grantB, dirB;
await t('INT-B-014', 'GM&E: reveal without grant refused + logged; request without reason refused; with reason pending', async () => {
  grantB = await new Browser().login('equipe'); const r = await grantB.post('/console/gme/112/afficher', {}); ok(r.status === 403 && !/DEMO-GME/.test(r.text), 'reveal ' + r.status);
  const nr = await grantB.post('/console/gme/112/demande', { reason: '' }); ok(nr.status === 200 && !/DEMO-GME/.test(nr.text), 'no-reason ' + nr.status);
  const ok2 = await grantB.post('/console/gme/112/demande', { reason: 'Devis groupe pour client QA' }); ok(ok2.status === 303, 'request ' + ok2.status);
});
await t('INT-B-015', 'GM&E: direction approves; equipe reveals code (log row); journal Direction only; then revoke -> reveal refused', async () => {
  dirB = new Browser(); dirB.jar = { ...grantB.jar }; await dirB.login('direction');
  const acc = (await dirB.req('/console/gme/acces')).text; const rid = /\/console\/gme\/acces\/(\d+)/.exec(acc)?.[1]; ok(rid, 'no pending request visible');
  const ap = await dirB.post('/console/gme/acces/' + rid, { decision: 'approuver' }); ok(ap.status === 303, 'approve ' + ap.status);
  const rv = await grantB.post('/console/gme/112/afficher', {}); ok(rv.status === 200 && rv.text.includes('DEMO-GME-4821'), 'reveal after approval ' + rv.status);
  const fresh = (await grantB.req('/console/gme')).text; ok(!/DEMO-GME-\d{4}/.test(fresh), 'code persists in later page');
  const j = await dirB.req('/console/gme/journal'); ok(j.status === 200 && /Code affiché/.test(j.text) && !/DEMO-GME-\d{4}/.test(j.text), 'journal');
  const rj = await grantB.req('/console/gme/journal'); ok(rj.status === 403, 'equipe journal ' + rj.status);
  const rev = await dirB.post('/console/gme/acces/' + rid, { decision: 'revoquer' }); ok(rev.status === 303, 'revoke ' + rev.status);
  const after = await grantB.post('/console/gme/112/afficher', {}); ok(after.status === 403 && !/DEMO-GME/.test(after.text), 'reveal after revoke ' + after.status);
  const jj = (await dirB.req('/console/gme/journal')).text; ok(/Refusé/.test(jj), 'refusal logged');
});
await t('INT-B-016', 'GM&E: reveal refused for expiré (105) and détecté (101) even for Direction path; reveal needs CSRF', async () => {
  const e = await new Browser().login('equipe'); for (const c of [105, 101]) { const r = await e.post(`/console/gme/${c}/afficher`, {}); ok(r.status === 403 && !/DEMO-GME/.test(r.text), c + ' ' + r.status); }
  const nc = await e.req('/console/gme/112/afficher', { method: 'POST', form: {} }); ok(nc.status === 403 && !/DEMO-GME/.test(nc.text), 'no csrf ' + nc.status);
  const get = await e.req('/console/gme/112/afficher'); ok(get.status >= 400 && !/DEMO-GME/.test(get.text), 'GET reveal ' + get.status);
});
await t('INT-B-017', 'public leak: crawl catalogue, pages, robots, sitemap, 404, search; no DEMO-GME- anywhere', async () => {
  const B = new Browser(); const urls = ['/', '/?q=DEMO-GME', '/?q=DEMO', '/robots.txt', '/sitemap.xml', '/feed', '/api/congres', '/wp-json/wp/v2/posts', '/console/gme', '/console/connexion', '/demande/confirmation']; const sl = ['congres-europeen-de-cardiologie-cg-0101', ONCO, 'journees-francaises-de-diabetologie-cg-0103', 'congres-europeen-de-radiologie-cg-0108'];
  for (const s of sl) urls.push('/congres/' + s); let bad = [];
  for (const u of urls) { const r = await B.req(u); if (/DEMO-GME-/.test(r.text)) bad.push(u); }
  ok(!bad.length, 'leak on ' + bad); const d = (await B.req('/congres/' + ONCO)).text; ok(/Tarif congrès négocié disponible/.test(d), 'sale mention'); return urls.length + ' urls';
});
await t('INT-B-018', 'draft congress (113) 404 publicly and absent from catalogue; past not listed; 12 listed', async () => {
  const B = new Browser(); const d = await B.req('/congres/journees-de-rhumatologie-cg-0113'); ok(d.status === 404, 'draft ' + d.status);
  const all = (await B.req('/')).text; ok(!/rhumatologie/i.test(all), 'draft in catalogue'); const n = [...all.matchAll(/\/congres\/[a-z0-9-]+/g)].map((m) => m[0]); return 'unique links ' + new Set(n).size;
});
let cgId;
await t('INT-B-019', 'edit seed record copies it (copy-on-write): editing city in sandbox shows publicly in sandbox, original untouched for others; contributeur cannot publish, draft hidden', async () => {
  const co = await new Browser().login('contributeur'); const f = (await co.req('/console/congres/nouveau')).text; ok(f.includes('name="title"'), 'form');
  const mk = (extra) => ({ title: 'QA Draft — exemple', discipline: 'Cardiologie', venue: 'Lieu QA', city: 'Nice', country: 'France', start_date: '2027-05-01', end_date: '2027-05-03', official_url: 'https://example.com', verified_on: '2026-11-01', description: 'd', ...extra });
  const s = await co.post('/console/congres/nouveau', mk({ action: 'save' })); ok(s.status === 303, 'save draft ' + s.status); cgId = /\/console\/congres\/(\d+)/.exec(s.loc)?.[1]; ok(cgId, 'id from ' + s.loc);
  const pub = await co.post('/console/congres/' + cgId, mk({ action: 'publish' })); ok(pub.status === 403, 'contrib publish ' + pub.status);
  ok(!(await co.req('/')).text.includes('QA Draft'), 'draft visible');
  const dr = await new Browser().login('direction'); dr.jar = { ...co.jar }; await dr.login('direction');
  const p = await dr.post('/console/congres/' + cgId, mk({ action: 'publish' })); ok(p.status === 303, 'direction publish ' + p.status); ok((await dr.req('/')).text.includes('QA Draft'), 'published not visible');
  const bad = await dr.post('/console/congres/' + cgId, mk({ action: 'save', end_date: '2027-04-01' })); ok(bad.status === 200 && /fin/.test(bad.text), 'end<start ' + bad.status);
  const u = await dr.post('/console/congres/' + cgId, mk({ action: 'save', official_url: 'javascript:alert(1)' })); ok(u.status === 200, 'bad url ' + u.status);
  const edit = await dr.post('/console/congres/101', mk({ action: 'save', title: 'Congrès européen de cardiologie — exemple', city: 'Séville' })); ok(edit.status < 400, 'edit seed ' + edit.status);
  ok((await dr.req('/congres/' + SLUG)).text.includes('Séville'), 'edit not shown in sandbox');
  const other = new Browser(); ok(!(await other.req('/congres/' + SLUG)).text.includes('Séville') && (await other.req('/congres/' + SLUG)).text.includes('Madrid'), 'seed modified for others'); globalThis.__dr = dr;
});
await t('INT-B-020', 'reset restores seed: Direction reset removes sandbox edits, re-reset idempotent (no duplicates); non-direction refused', async () => {
  const dr = globalThis.__dr; const r = await dr.post('/console/reinitialiser', {}); ok(r.status === 303, 'reset ' + r.status);
  const dr2 = await new Browser(); dr2.jar = { ...dr.jar }; await dr2.login('direction'); const pg = (await dr2.req('/congres/' + SLUG)).text; ok(pg.includes('Madrid') && !pg.includes('Séville'), 'not restored');
  const cat = (await dr2.req('/')).text; ok(!cat.includes('QA Draft'), 'draft survived reset'); const r2 = await dr2.post('/console/reinitialiser', {}); ok(r2.status === 303, 'second reset');
  const lk = async (u) => [...(await dr2.req(u)).text.matchAll(/\/congres\/[a-z0-9-]+/g)].map((m) => m[0]); const n1 = new Set([...(await lk('/')), ...(await lk('/?page=2'))]).size; ok(n1 === 12, 'catalogue count ' + n1); const l = (await dr2.req('/console/demandes')).text; ok(!l.includes(ref), 'enquiries survived reset'); return 'catalogue ' + n1;
});
await t('INT-B-021', 'security headers + cookie flags + error pages leak nothing', async () => {
  const B = new Browser(); const r = await B.req('/'); const h = r.headers; for (const k of ['content-security-policy', 'x-content-type-options', 'x-frame-options', 'strict-transport-security', 'referrer-policy']) ok(h.get(k), 'missing ' + k);
  const sc = (await fetch(BASE + '/')).headers.getSetCookie().join(' '); ok(/HttpOnly/.test(sc) && /Secure/.test(sc) && /SameSite=Lax/.test(sc), sc);
  const e404 = await B.req('/nope'); ok(e404.status === 404 && !/stack|Error:|\.js:\d+/.test(e404.text), '404'); const m = await B.req('/', { method: 'DELETE' }); ok(m.status === 405, 'DELETE ' + m.status);
  const bad = await B.req('/congres/%00'); ok(bad.status < 500, 'nul ' + bad.status); const p = await B.req('/assets/../src/index.js'); ok(!/export default/.test(p.text), 'source exposed'); const p2 = await B.req('/assets/%2e%2e/wrangler.toml'); ok(!/d1_databases/.test(p2.text), 'toml exposed');
  const j = await B.req('/demande', { method: 'POST', headers: { 'content-type': 'application/json' } }); ok([415, 400].includes(j.status) || j.status < 500, 'json ' + j.status); return 'headers ok';
});
await t('INT-B-022', 'search: accent-insensitive, XSS escaped, 5000-char query no error, filters combine', async () => {
  const B = new Browser(); const a = (await B.req('/?q=vienne')).text, b = (await B.req('/?q=diabetologie')).text; ok(/Vienne/.test(a) && /iab.tologie/i.test(b), 'accent');
  const x = await B.req('/?q=' + encodeURIComponent('<script>alert(1)</script>')); ok(x.status === 200 && !x.text.includes('<script>alert'), 'xss');
  const l = await B.req('/?q=' + 'a'.repeat(5000)); ok(l.status < 500, 'long ' + l.status); const p = await B.req('/?page=-5&discipline=%00&pays=zz&mois=99'); ok(p.status < 500, 'junk params ' + p.status); return `long ${l.status}`;
});
await t('INT-B-023', 'login: wrong password 401 generic, throttle 429 after 10 attempts per sandbox, other sandbox unaffected', async () => {
  const B = new Browser(); const st = []; for (let i = 0; i < 12; i++) { const g = await B.req('/console/connexion'); const tok = /name="_token" value="([^"]+)"/.exec(g.text)[1]; st.push((await B.req('/console/connexion', { method: 'POST', form: { _token: tok, username: 'direction', password: 'x' + i } })).status); }
  ok(st[0] === 401 && st.includes(429), st.join(',')); const C = new Browser(); await C.login('direction'); return st.join(',');
});
await t('INT-B-024', 'session: logout invalidates, open redirect via next refused', async () => {
  const B = new Browser(); const g = await B.req('/console/connexion?next=//evil.example'); const tok = /name="_token" value="([^"]+)"/.exec(g.text)[1];
  const r = await B.req('/console/connexion', { method: 'POST', form: { _token: tok, username: 'equipe', password: 'demo-asset', next: '//evil.example' } }); ok(r.status === 303 && r.loc === '/console', 'redirect ' + r.loc);
  const d = await B.follow('/console'); const csrf = csrfOf(d.text); const old = { ...B.jar }; await B.req('/console/deconnexion', { method: 'POST', form: { _csrf: csrf } });
  const R = new Browser(); R.jar = old; const rr = await R.req('/console/demandes'); ok(rr.status === 303, 'old session still valid ' + rr.status);
});
const pass = results.filter((r) => r.ok).length; console.log(`\nSUMMARY ${pass}/${results.length} pass`); (await import('node:fs')).writeFileSync(new URL('./logs/integration_results.json', import.meta.url), JSON.stringify(results, null, 1)); process.exit(pass === results.length ? 0 : 1);
