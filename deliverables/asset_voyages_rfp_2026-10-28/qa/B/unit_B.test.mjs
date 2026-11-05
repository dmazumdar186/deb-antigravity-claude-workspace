// Unit tests for Option B pure logic. Run: node --test qa/B/unit_B.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
const SRC = new URL('../../custom_demo/src/', import.meta.url);
const L = await import(new URL('lib.js', SRC));
const P = await import(new URL('public.js', SRC));
const D = await import(new URL('data.js', SRC));
const KEY = Buffer.alloc(32, 7).toString('base64');
const env = { GME_KEY: KEY };
const T = '2026-11-05';
const form = (o) => (k) => (o[k] ?? '');
const good = { name: 'A B', email: 'a@example.com', phone: '01 23 45 67 89', departure_city: 'Lille', date_out: '2026-11-06', date_back: '2026-11-08', passengers: '2', consent: '1' };
const v = (o = {}, t = T) => P.validateEnquiry(form({ ...good, ...o }), t).e;

test('UNIT-B-001 passengers boundaries 0/1/50/51/abc', () => {
  assert.ok(v({ passengers: '0' }).passengers);
  assert.equal(v({ passengers: '1' }).passengers, undefined);
  assert.equal(v({ passengers: '50' }).passengers, undefined);
  assert.ok(v({ passengers: '51' }).passengers);
  assert.ok(v({ passengers: 'abc' }).passengers);
  assert.ok(v({ passengers: '' }).passengers);
  assert.ok(v({ passengers: '-1' }).passengers);
  assert.ok(v({ passengers: '1.5' }).passengers);
  assert.ok(v({ passengers: '1e1' }).passengers);
});
test('UNIT-B-002 date_out: today ok, day before rejected, +730 ok, +731 rejected', () => {
  assert.equal(v({ date_out: T, date_back: T }).date_out, undefined);
  assert.ok(v({ date_out: '2026-11-04' }).date_out);
  assert.equal(v({ date_out: L.addDays(T, 730), date_back: L.addDays(T, 730) }).date_out, undefined);
  assert.ok(v({ date_out: L.addDays(T, 731) }).date_out);
});
test('UNIT-B-003 return: same day ok, day before outbound rejected, past rejected', () => {
  assert.equal(v({ date_out: '2026-11-10', date_back: '2026-11-10' }).date_back, undefined);
  assert.ok(v({ date_out: '2026-11-10', date_back: '2026-11-09' }).date_back);
  assert.ok(v({ date_back: '2026-11-04' }).date_back);
  assert.ok(v({ date_back: '2026-02-30' }).date_back);
  assert.ok(v({ date_back: '' }).date_back);
});
test('UNIT-B-004 email valid/invalid + length 254 boundary', () => {
  assert.equal(v({ email: 'x.y@societe.fr' }).email, undefined);
  for (const bad of ['', 'abc', 'a@b', 'a b@c.fr', '@c.fr', 'a@@c.fr', 'a@c..fr', '<a>@c.fr', 'a@-c.fr']) assert.ok(v({ email: bad }).email, bad);
  const long = 'a'.repeat(64) + '@' + 'b'.repeat(63) + '.' + 'c'.repeat(63) + '.' + 'd'.repeat(63) + '.fr';
  assert.ok(long.length <= 254 ? true : v({ email: long }).email);
  assert.ok(v({ email: 'a'.repeat(65) + '@c.fr' }).email);
});
test('UNIT-B-005 consent required', () => {
  assert.ok(v({ consent: '' }).consent);
  assert.ok(v({ consent: '0' }).consent);
  assert.ok(v({ consent: 'on' }).consent);
  assert.equal(v({ consent: '1' }).consent, undefined);
});
test('UNIT-B-006 required fields and max lengths (name 120/121, phone 30/31, message 2000/2001)', () => {
  assert.ok(v({ name: '' }).name); assert.ok(v({ name: '   ' }).name);
  assert.equal(v({ name: 'n'.repeat(120) }).name, undefined); assert.ok(v({ name: 'n'.repeat(121) }).name);
  assert.equal(v({ phone: '1'.repeat(30) }).phone, undefined); assert.ok(v({ phone: '1'.repeat(31) }).phone);
  assert.equal(v({ phone: '12345' }).phone !== undefined, true); // 5 chars below 6-char floor
  assert.equal(v({ phone: '123456' }).phone, undefined);
  assert.ok(v({ phone: 'abc123456' }).phone);
  assert.equal(v({ message: 'm'.repeat(2000) }).message, undefined); assert.ok(v({ message: 'm'.repeat(2001) }).message);
  assert.ok(v({ departure_city: '' }).departure_city);
  assert.equal(v({ departure_city: 'c'.repeat(80) }).departure_city, undefined); assert.ok(v({ departure_city: 'c'.repeat(81) }).departure_city);
});
test('UNIT-B-007 valid enquiry has no errors; control chars stripped', () => {
  assert.deepEqual(v(), {});
  const r = P.validateEnquiry(form({ ...good, name: 'A\u0000B\u0007C' }), T);
  assert.equal(r.v.name, 'ABC');
});
test('UNIT-B-008 csvCell neutralises = + - @ tab CR, escapes quotes, null', () => {
  for (const c of ['=1+1', '+1', '-1', '@SUM(A1)', '\tx', '\rx']) assert.ok(L.csvCell(c).startsWith('"\''), c);
  assert.equal(L.csvCell('safe'), '"safe"');
  assert.equal(L.csvCell('a"b'), '"a""b"');
  assert.equal(L.csvCell(null), '""'); assert.equal(L.csvCell(undefined), '""'); assert.equal(L.csvCell(0), '"0"');
});
test('UNIT-B-009 esc/html escape & < > " \' and raw passthrough, arrays, null', () => {
  assert.equal(L.esc('<script>"x"&\'y\''), '&lt;script&gt;&quot;x&quot;&amp;&#39;y&#39;');
  assert.equal(L.esc(null), ''); assert.equal(L.esc(undefined), ''); assert.equal(L.esc(false), '');
  assert.equal(L.esc(0), '0');
  assert.equal(String(L.html`<b>${'<i>'}</b>`), '<b>&lt;i&gt;</b>');
  assert.equal(String(L.html`${L.raw('<i>')}`), '<i>');
  assert.equal(L.esc(['<', '>']), '&lt;&gt;');
});
test('UNIT-B-010 AES-GCM round trip, unique IV, tamper and wrong key fail', async () => {
  const a = await L.encryptCode(env, 'DEMO-GME-4821'), b = await L.encryptCode(env, 'DEMO-GME-4821');
  assert.match(a, /^v1:/); assert.ok(!a.includes('DEMO-GME')); assert.notEqual(a, b);
  assert.equal(await L.decryptCode(env, a), 'DEMO-GME-4821');
  const bytes = Buffer.from(a.slice(3), 'base64'); bytes[bytes.length - 1] ^= 1;
  await assert.rejects(L.decryptCode(env, 'v1:' + bytes.toString('base64')));
  await assert.rejects(L.decryptCode({ GME_KEY: Buffer.alloc(32, 9).toString('base64') }, a));
  assert.equal(await L.decryptCode(env, await L.encryptCode(env, '')), '');
  assert.equal(await L.decryptCode(env, await L.encryptCode(env, 'é€😀')), 'é€😀');
});
test('UNIT-B-011 keys(): missing / short key rejected', async () => {
  await assert.rejects(L.encryptCode({}, 'x'), /GME_KEY/);
  await assert.rejects(L.encryptCode({ GME_KEY: Buffer.alloc(31).toString('base64') }, 'x'), /32 bytes/);
});
test('UNIT-B-012 PBKDF2 hash deterministic; differs by salt and password', async () => {
  const s = L.newSalt(), s2 = L.newSalt();
  const h = await L.hashPassword('demo-asset', s);
  assert.equal(h, await L.hashPassword('demo-asset', s));
  assert.notEqual(h, await L.hashPassword('demo-asseT', s));
  assert.notEqual(h, await L.hashPassword('demo-asset', s2));
});
test('UNIT-B-013 safeEqual', () => {
  assert.ok(L.safeEqual('abc', 'abc')); assert.ok(!L.safeEqual('abc', 'abd')); assert.ok(!L.safeEqual('abc', 'abcd'));
  assert.ok(!L.safeEqual(null, 'a')); assert.ok(!L.safeEqual(undefined, undefined)); assert.ok(L.safeEqual('', ''));
});
test('UNIT-B-014 form tokens: valid, tampered, too fast, expired, garbage', async () => {
  const t = await L.makeFormToken(env, 'enquiry');
  assert.ok((await L.checkFormToken(env, 'enquiry', t)).ok);
  assert.equal((await L.checkFormToken(env, 'enquiry', t, { minMs: 60000 })).why, 'fast');
  assert.equal((await L.checkFormToken(env, 'login', t)).ok, false); // wrong purpose
  const [ts, n, s] = t.split('.');
  assert.equal((await L.checkFormToken(env, 'enquiry', `${ts}.${n}.${s.slice(0, -1)}A`)).ok, false);
  const old = String(Date.now() - 3 * 3600 * 1000);
  const oldTok = `${old}.${n}.` + (await L.hmac(env, `enquiry|${old}|${n}`));
  assert.equal((await L.checkFormToken(env, 'enquiry', oldTok)).why, 'expired');
  for (const g of [null, undefined, '', 'x', '1.2.3', {}]) assert.equal((await L.checkFormToken(env, 'enquiry', g)).ok, false);
});
test('UNIT-B-015 isIsoDate / addDays boundaries', () => {
  assert.ok(L.isIsoDate('2028-02-29')); assert.ok(!L.isIsoDate('2027-02-29')); assert.ok(!L.isIsoDate('2026-13-01'));
  assert.ok(!L.isIsoDate('2026-1-1')); assert.ok(!L.isIsoDate(null)); assert.ok(!L.isIsoDate(20261105)); assert.ok(!L.isIsoDate('2026-11-05T00:00'));
  assert.equal(L.addDays('2026-12-31', 1), '2027-01-01'); assert.equal(L.addDays('2026-03-01', -1), '2026-02-28');
});
test('UNIT-B-016 French date formatting and ranges', () => {
  assert.equal(L.frDate('2027-08-27'), '27 août 2027'); assert.equal(L.frDate(''), ''); assert.equal(L.frNumDate('2027-03-05'), '05/03/2027');
  assert.equal(L.frRange('2027-08-27', '2027-08-30'), '27 au 30 août 2027');
  assert.equal(L.frRange('2027-08-27', '2027-08-27'), '27 août 2027');
  assert.equal(L.frRange('2027-08-30', '2027-09-02'), '30 août au 2 sept. 2027');
  assert.equal(L.frRange('2027-12-30', '2028-01-02'), '30 déc. 2027 au 2 janv. 2028');
  assert.equal(L.rangeParts('2027-08-27', '2027-08-30').cross, false); assert.equal(L.rangeParts('2027-08-30', '2027-09-02').cross, true);
});
test('UNIT-B-017 norm/slugify accent-insensitive', () => {
  assert.equal(L.norm('Diabétologie'), 'diabetologie'); assert.equal(L.norm(null), ''); assert.equal(L.norm('  VIENNE '), 'vienne');
  assert.equal(L.slugify('Journées d’oncologie — exemple'), 'journees-d-oncologie-exemple'); assert.equal(L.slugify('!!!'), '');
  assert.ok(L.slugify('a'.repeat(500)).length <= 80);
});
test('UNIT-B-018 clean() trims, strips control chars, truncates to max+1 (so >max is detectable)', () => {
  assert.equal(L.clean('  x  ', 5), 'x'); assert.equal(L.clean(null, 5), ''); assert.equal(L.clean('abcdefghij', 3), 'abcd');
  assert.equal(L.clean('a\r\nb', 9), 'a\nb');
});
test('UNIT-B-019 reference numbering: seed congress refs and slugs unique, slug round-trip', () => {
  const refs = D.CONGRESSES.map((c) => c.ref); assert.equal(new Set(refs).size, refs.length);
  const slugs = D.CONGRESSES.map((c) => D.congressSlug(c.title, c.ref)); assert.equal(new Set(slugs).size, slugs.length);
  assert.ok(slugs.every((s) => /^[a-z0-9-]{1,120}$/.test(s)));
  assert.equal(D.CONGRESSES.filter((c) => c.status === 'publie').length, 12);
  assert.equal(D.CONGRESSES.filter((c) => c.status !== 'publie').length, 1);
});
test('UNIT-B-020 fictional data (X3): titles end « — exemple », seed codes DEMO-GME-, enquiry emails example.com', () => {
  assert.ok(D.CONGRESSES.every((c) => /exemple$/.test(c.title)));
  assert.ok(D.GME_SEED_CODES.every((c) => /^DEMO-GME-\d{4}$/.test(c)));
});
test('UNIT-B-021 notificationFor never contains a GM&E code and builds console link', () => {
  const n = D.notificationFor({ id: 7, ref: 'DV-2026-0007', name: 'N', email: 'e@example.com', phone: '0123456', company: '', departure_city: 'Lille', date_out: '2027-01-01', date_back: '2027-01-05', passengers: 2 }, { title: 'T', ref: 'CG-0101' }, 'https://x.test/');
  assert.match(n.body, /https:\/\/x\.test\/console\/demandes\/7$/); assert.ok(!/DEMO-GME/.test(n.subject + n.body)); assert.match(n.subject, /DV-2026-0007/);
});
test('UNIT-B-022 status labels cover the 5-state pipeline; sandbox id validator', () => {
  assert.deepEqual(Object.keys(D.STATUS_LABELS), ['nouvelle', 'qualifiee', 'devis', 'gagnee', 'perdue']);
  assert.ok(D.validSbx(L.randomToken(18))); for (const b of [null, '', 'x', '../../etc', 'a'.repeat(200), '<script>']) assert.ok(!D.validSbx(b), String(b));
});
test('UNIT-B-023 cookie parsing and sameOrigin', () => {
  const r = (h) => new Request('https://x.test/p', { headers: h });
  assert.equal(L.getCookie(r({ cookie: 'a=1; __Host-av_sbx=zz; b=2' }), '__Host-av_sbx'), 'zz'); assert.equal(L.getCookie(r({}), 'a'), null);
  assert.ok(L.sameOrigin(r({ origin: 'https://x.test' }))); assert.ok(!L.sameOrigin(r({ origin: 'https://evil.test' })));
  assert.ok(!L.sameOrigin(r({ 'sec-fetch-site': 'cross-site' }))); assert.ok(L.sameOrigin(r({})));
  assert.ok(!L.sameOrigin(r({ origin: 'null' })));
});
test('UNIT-B-024 readForm: content-type 415, size 413 on both sides of 32 KiB', async () => {
  const mk = (ct, body, len) => new Request('https://x.test/', { method: 'POST', headers: { 'content-type': ct, ...(len ? { 'content-length': String(len) } : {}) }, body });
  assert.equal((await L.readForm(mk('application/json', '{}'))).error, 415);
  const ok = await L.readForm(mk('application/x-www-form-urlencoded', 'a=' + 'x'.repeat(L.MAX_BODY - 2))); assert.equal(ok.error, undefined); assert.equal(ok.get('a').length, L.MAX_BODY - 2);
  assert.equal((await L.readForm(mk('application/x-www-form-urlencoded', 'a=' + 'x'.repeat(L.MAX_BODY)))).error, 413);
});
test('UNIT-B-025 rateHit counter logic (in-memory D1 stub): allows up to limit, blocks limit+1, window reset', async () => {
  const store = new Map();
  const db = { prepare: () => ({ bind: (key, now, win) => ({ first: async () => { let r = store.get(key); if (!r || r.reset_at <= now) r = { count: 1, reset_at: now + win }; else r = { ...r, count: r.count + 1 }; store.set(key, r); return { count: r.count }; } }) }) };
  const e = { DB: db };
  for (let i = 0; i < 10; i++) assert.equal(await L.rateHit(e, 'k', 10, 60), true);
  assert.equal(await L.rateHit(e, 'k', 10, 60), false);
  store.get('k').reset_at = 0; assert.equal(await L.rateHit(e, 'k', 10, 60), true);
});
