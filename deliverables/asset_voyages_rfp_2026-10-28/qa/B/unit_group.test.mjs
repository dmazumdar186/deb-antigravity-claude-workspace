// Unit tests for « Le lien de groupe » (Option B extra). Run: node --test qa/B/unit_group.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
const SRC = new URL('../../custom_demo/src/', import.meta.url);
const G = await import(new URL('group.js', SRC));
const L = await import(new URL('lib.js', SRC));
const env = { GME_KEY: Buffer.alloc(32, 9).toString('base64') };
const env2 = { GME_KEY: Buffer.alloc(32, 8).toString('base64') };
const T = '2026-11-06';
const CG = { start_date: '2027-01-28', end_date: '2027-01-30' };
const good = { name: 'Alice Martin', email: 'alice@example.com', departure_city: 'Lille', date_out: '2027-01-27', date_back: '2027-01-31', consent: '1' };
const v = (o = {}, c = CG, t = T) => G.validateDelegate((k) => ({ ...good, ...o })[k] ?? '', c, t).e;

test('UNIT-G-001 token: 128-bit random salt, 256-bit token, deterministic per key, distinct per salt and per key', async () => {
  const s1 = G.newSalt(); const s2 = G.newSalt();
  assert.equal(Buffer.from(s1, 'base64url').length, 16);
  assert.notEqual(s1, s2);
  const t1 = await G.tokenFor(env, s1);
  assert.match(t1, G.TOKEN_RE);
  assert.equal(await G.tokenFor(env, s1), t1);
  assert.notEqual(await G.tokenFor(env, s2), t1);
  L.keys; // keys are cached per GME_KEY: a second key gives other tokens
  assert.notEqual(await G.tokenFor(env2, s1), await G.tokenFor(env, s1));
});
test('UNIT-G-002 the stored lookup MAC is not the token and is not a valid token for itself', async () => {
  const tok = await G.tokenFor(env, 'seed');
  const mac = await G.lookupMac(env, tok);
  assert.notEqual(mac, tok);
  assert.notEqual(await G.lookupMac(env, mac), mac);
  assert.ok(L.MAC_PURPOSES.includes('group-v1'));
  // group-v1 is its own HKDF key: the same text under form-v1 gives another MAC
  assert.notEqual(await L.hmac(env, 'form-v1', 'id|' + tok), mac);
});
test('UNIT-G-003 link state: none, active, expired at the second, revoked wins', () => {
  assert.equal(G.linkState(null), 'none');
  assert.equal(G.linkState({ expires_at: '2026-12-06T23:59:59Z' }, '2026-11-06T10:00:00Z'), 'active');
  assert.equal(G.linkState({ expires_at: '2026-12-06T23:59:59Z' }, '2026-12-06T23:59:59Z'), 'expired');
  assert.equal(G.linkState({ expires_at: '2026-12-06T23:59:59Z', revoked_at: '2026-11-06T11:00:00Z' }, '2026-11-06T12:00:00Z'), 'revoked');
  assert.equal(G.linkExpiry('2026-11-06'), '2026-12-06T23:59:59Z');
});
test('UNIT-G-004 delegate form: valid case passes, every field required, consent required', () => {
  assert.deepEqual(v(), {});
  for (const k of ['name', 'email', 'departure_city', 'date_out', 'date_back']) assert.ok(v({ [k]: '' })[k], k);
  assert.ok(v({ consent: '' }).consent);
  assert.ok(v({ consent: 'on' }).consent);
});
test('UNIT-G-005 lengths: 120/121 name, 80/81 city, oversized e-mail', () => {
  assert.equal(v({ name: 'x'.repeat(120) }).name, undefined);
  assert.ok(v({ name: 'x'.repeat(121) }).name);
  assert.equal(v({ departure_city: 'x'.repeat(80) }).departure_city, undefined);
  assert.ok(v({ departure_city: 'x'.repeat(81) }).departure_city);
  assert.ok(v({ email: 'a'.repeat(250) + '@example.com' }).email);
  assert.ok(v({ email: 'a@b' }).email);
  assert.ok(v({ email: 'x@example.com\r\nBcc: y@example.com' }).email);
});
test('UNIT-G-006 dates: reversed refused, same day ok, past refused, window 30 days around the congress', () => {
  assert.ok(v({ date_out: '2027-01-31', date_back: '2027-01-27' }).date_back);
  assert.deepEqual(v({ date_out: '2027-01-29', date_back: '2027-01-29' }), {});
  assert.ok(v({ date_out: '2026-11-05' }).date_out);
  assert.equal(v({ date_out: '2026-12-29', date_back: '2027-01-31' }).date_out, undefined); // start - 30
  assert.ok(v({ date_out: '2026-12-28' }).date_out); // start - 31
  assert.equal(v({ date_back: '2027-03-01' }).date_back, undefined); // end + 30
  assert.ok(v({ date_back: '2027-03-02' }).date_back); // end + 31
  assert.ok(v({ date_out: '2027-02-30' }).date_out);
  assert.ok(v({ date_out: 'demain' }).date_out);
});
test('UNIT-G-007 threshold setting: 2..99 integers only, default 10', () => {
  assert.equal(G.DEFAULT_SEUIL, 10);
  for (const ok of ['2', '10', '99', ' 12 ']) assert.equal(G.parseSeuil(ok), +ok.trim(), ok);
  for (const bad of ['1', '100', '0', '-3', '2.5', 'dix', '', null, '1e1']) assert.equal(G.parseSeuil(bad), null, String(bad));
});
test('UNIT-G-008 internal hint: « proche » within max(2, 20 %) of the threshold, « atteint » at it; no airline named', () => {
  assert.equal(G.seuilHint(7, 10), null);
  assert.equal(G.seuilHint(8, 10).kind, 'proche');
  assert.equal(G.seuilHint(9, 10).kind, 'proche');
  assert.equal(G.seuilHint(10, 10).kind, 'atteint');
  assert.equal(G.seuilHint(12, 10).kind, 'atteint');
  assert.equal(G.seuilHint(15, 20), null);
  assert.equal(G.seuilHint(16, 20).kind, 'proche');
  assert.equal(G.seuilHint(1, 4), null);
  assert.equal(G.seuilHint(2, 4).kind, 'proche');
  assert.equal(G.seuilHint(3, 5).kind, 'proche');
  assert.equal(G.seuilHint(4, 4).kind, 'atteint');
  for (const h of [G.seuilHint(8, 10), G.seuilHint(10, 10)]) {
    assert.match(h.text, /à confirmer/);
    assert.doesNotMatch(h.text, /air|klm|compagnie|GM&E|tarif/i);
  }
});
test('UNIT-G-014 (USAB-X-005) once everyone expected has answered: « Tous les participants ont répondu », never « Relancez »', () => {
  const near = G.seuilHint(2, 3, 2);
  assert.equal(near.kind, 'proche');
  assert.match(near.text, /Tous les participants ont répondu\./);
  assert.doesNotMatch(near.text, /Relancez/);
  assert.match(G.seuilHint(2, 3, 6).text, /Relancez/);
  assert.equal(G.seuilHint(3, 10, 3).kind, 'tous');
  assert.equal(G.seuilHint(3, 10, 3).text, 'Tous les participants ont répondu.');
  assert.equal(G.seuilHint(3, 10, 6), null);
  assert.match(G.seuilHint(10, 10, 10).text, /^Seuil groupe atteint.*Tous les participants ont répondu\.$/);
});
test('UNIT-G-015 (EYE-X-001) display titles may break inside a word only for a run of more than 24 characters without spaces', async () => {
  const V = await import(new URL('views.js', SRC));
  assert.equal(V.displayWrap('Journées françaises de diabétologie — exemple'), '');
  assert.equal(V.displayWrap('Congrès https://www.tres-long-congres-example.org'), ' display--wrap');
});
test('UNIT-G-009 counter text and plurals: « 7 répondus / 10 attendus », « 1 répondu / 2 attendus »', () => {
  assert.equal(G.counterText(7, 10), '7 répondus / 10 attendus');
  assert.equal(G.counterText(1, 2), '1 répondu / 2 attendus');
  assert.equal(G.counterText(0, 6), '0 répondu / 6 attendus');
});
test('UNIT-G-010 e-mail key and delegate cap (bounded: 10 floor, 100 ceiling)', () => {
  assert.equal(G.emailNorm('  Alice.Martin@Example.COM '), 'alice.martin@example.com');
  assert.equal(G.delegateCap(2), 10);
  assert.equal(G.delegateCap(6), 12);
  assert.equal(G.delegateCap(50), 100);
  assert.equal(G.delegateCap(80), 100);
});
test('UNIT-G-011 CSV cells reuse the formula-injection escaping', () => {
  assert.equal(L.csvCell('=HYPERLINK("http://evil.example")'), `"'=HYPERLINK(""http://evil.example"")"`);
  assert.equal(L.csvCell('+33 1'), `"'+33 1"`);
  assert.equal(L.csvCell('@SUM(A1)'), `"'@SUM(A1)"`);
  assert.equal(L.csvCell('Lille'), '"Lille"');
});
test('UNIT-G-013 delegate cookie (delegate-v1): own key, owner hash per browser id, forged or malformed cookies refused', async () => {
  assert.ok(L.MAC_PURPOSES.includes('delegate-v1'));
  const rid = 'r'.repeat(22);
  const h = await G.ownerHash(env, rid);
  assert.equal(await G.ownerHash(env, rid), h);
  assert.notEqual(await G.ownerHash(env, 's'.repeat(22)), h);
  assert.notEqual(await L.hmac(env, 'group-v1', 'owner|' + rid), h);
  const sig = await L.hmac(env, 'delegate-v1', 'cookie|' + rid);
  const req = (v) => new Request('https://x.example/g/t', { headers: { cookie: `__Host-av_dlg=${v}` } });
  assert.equal(await G.delegateCookieId(env, req(`${rid}.${sig}`)), rid);
  assert.equal(await G.delegateCookieId(env2, req(`${rid}.${sig}`)), null); // another key
  assert.equal(await G.delegateCookieId(env, req(`${'s'.repeat(22)}.${sig}`)), null);
  for (const bad of ['', 'x', `${rid}.${sig}.extra`, `${rid}`, `${rid}.${h}`]) assert.equal(await G.delegateCookieId(env, req(bad)), null, bad);
});
test('UNIT-G-012 token format: only 43 base64url characters', () => {
  for (const bad of ['', 'x'.repeat(42), 'x'.repeat(44), '../../etc/passwd', 'a'.repeat(42) + '=', 'a'.repeat(42) + '/']) assert.equal(G.TOKEN_RE.test(bad), false, bad);
  assert.equal(G.TOKEN_RE.test('A'.repeat(43)), true);
});
