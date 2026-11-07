import { test } from 'node:test';
import assert from 'node:assert/strict';
import { AUD, NOW, TEAM, baseEnv, makeWorld, adminRequest, signToken, testKeys, workerModule } from './helpers.mjs';

const A = await workerModule('auth.js');
const keys = await testKeys();
const env = baseEnv();

function deps(nowMs = NOW.getTime()) {
  return { getKey: A.createJwksCache(() => async () => keys.jwks), nowMs };
}

const verify = (token, e = env, d = deps()) => A.verifyAccessJwt(token, e, d);

test('valid RS256 token verifies and returns the lower-cased email', async () => {
  const r = await verify(await signToken({ email: 'Keith@GreenJobs.ie' }));
  assert.equal(r.ok, true);
  assert.equal(r.email, 'keith@greenjobs.ie');
});

test('aud may be a string', async () => {
  assert.equal((await verify(await signToken({ aud: AUD }))).ok, true);
});

const cases = [
  ['expired', async () => signToken({ exp: Math.floor(NOW.getTime() / 1000) - 3600 }), 'expired'],
  ['missing exp', async () => signToken({ exp: undefined }), 'expired'],
  ['not yet valid (nbf)', async () => signToken({ nbf: Math.floor(NOW.getTime() / 1000) + 3600 }), 'nbf'],
  ['wrong aud', async () => signToken({ aud: ['someone-else'] }), 'aud'],
  ['wrong iss', async () => signToken({ iss: 'https://evil.cloudflareaccess.com' }), 'iss'],
  ['tampered payload', async () => signToken({}, { tamper: true }), 'signature'],
  ['signed by another key', async () => signToken({}, { wrongKey: true }), 'signature'],
  ['alg none', async () => signToken({}, { alg: 'none' }), 'alg'],
  ['alg HS256', async () => signToken({}, { alg: 'HS256' }), 'alg'],
  ['unknown kid', async () => signToken({}, { kid: 'nope' }), 'unknown_kid'],
  ['missing token', async () => '', 'missing'],
  ['garbage', async () => 'a.b', 'malformed'],
  ['bad base64', async () => '!!.??.##', 'malformed'],
  ['no email claim', async () => signToken({ email: undefined }), 'no_email'],
];
for (const [name, make, reason] of cases) {
  test(`rejects: ${name}`, async () => {
    const r = await verify(await make());
    assert.equal(r.ok, false);
    assert.equal(r.reason, reason);
  });
}

test('fails closed when ACCESS_AUD or ACCESS_TEAM_DOMAIN is not configured', async () => {
  const t = await signToken();
  assert.equal((await verify(t, baseEnv({ ACCESS_AUD: '' }))).reason, 'not_configured');
  assert.equal((await verify(t, baseEnv({ ACCESS_TEAM_DOMAIN: '' }))).reason, 'not_configured');
  assert.equal((await verify(t, baseEnv({ ACCESS_TEAM_DOMAIN: 'bad host/../x' }))).reason, 'not_configured');
});

test('team domain may be given with https:// and a trailing slash', async () => {
  assert.equal((await verify(await signToken(), baseEnv({ ACCESS_TEAM_DOMAIN: `https://${TEAM}/` }))).ok, true);
});

test('JWKS is fetched from the team certs host and cached', async () => {
  const hosts = [];
  const getKey = A.createJwksCache((host) => async () => {
    hosts.push(host);
    return keys.jwks;
  });
  const t = await signToken();
  await A.verifyAccessJwt(t, env, { getKey, nowMs: NOW.getTime() });
  await A.verifyAccessJwt(t, env, { getKey, nowMs: NOW.getTime() + 1000 });
  assert.deepEqual(hosts, [TEAM]);
});

test('JWKS outage is a 503, not a pass', async () => {
  const getKey = A.createJwksCache(() => async () => {
    throw new Error('down');
  });
  const r = await A.authenticateStaff(new Request('https://greenjobs.ie/admin/', { headers: { 'Cf-Access-Jwt-Assertion': await signToken() } }), env, { getKey, nowMs: NOW.getTime() });
  assert.deepEqual([r.ok, r.status], [false, 503]);
});

test('end to end: missing header 401, valid but not on allow-list 403, staff 200', async () => {
  const w = await makeWorld();
  assert.equal((await w.fetch(await adminRequest('GET', '/api/admin/jobs', { token: null }))).status, 401);
  assert.equal((await w.fetch(await adminRequest('GET', '/api/admin/jobs', { claims: { email: 'intern@example.com' } }))).status, 403);
  assert.equal((await w.fetch(await adminRequest('GET', '/api/admin/jobs', { signOpts: { alg: 'none' } }))).status, 401);
  assert.equal((await w.fetch(await adminRequest('GET', '/api/admin/jobs'))).status, 200);
  assert.equal((await w.fetch(await adminRequest('GET', '/api/admin/jobs', { claims: { email: 'STAFF@greenjobs.ie' } }))).status, 200);
});

test('empty STAFF_EMAILS lets nobody in', async () => {
  const w = await makeWorld({ STAFF_EMAILS: '' });
  assert.equal((await w.fetch(await adminRequest('GET', '/api/admin/jobs'))).status, 403);
});
