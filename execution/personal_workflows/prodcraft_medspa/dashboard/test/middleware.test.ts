import { describe, expect, it } from 'vitest';
import { onRequest, type Env } from '../functions/_middleware';

function fakeContext(request: Request, env: Env) {
  return {
    request,
    env,
    next: async () => new Response('ok', { status: 200 }),
    params: {},
    data: {},
    functionPath: '/',
    waitUntil: () => {},
    passThroughOnException: () => {},
  } as unknown as Parameters<typeof onRequest>[0];
}

function basicAuthHeader(user: string, pass: string): string {
  return `Basic ${btoa(`${user}:${pass}`)}`;
}

const ENV: Env = { DASHBOARD_USER: 'ops', DASHBOARD_PASS: 'correct-horse' };

describe('_middleware Basic Auth', () => {
  it('401s with no Authorization header', async () => {
    const req = new Request('https://dash.example.com/');
    const res = await onRequest(fakeContext(req, ENV));
    expect(res.status).toBe(401);
    expect(res.headers.get('WWW-Authenticate')).toMatch(/^Basic/);
  });

  it('401s with wrong credentials', async () => {
    const req = new Request('https://dash.example.com/', {
      headers: { Authorization: basicAuthHeader('ops', 'wrong') },
    });
    const res = await onRequest(fakeContext(req, ENV));
    expect(res.status).toBe(401);
  });

  it('401s with wrong username, correct password', async () => {
    const req = new Request('https://dash.example.com/', {
      headers: { Authorization: basicAuthHeader('intruder', 'correct-horse') },
    });
    const res = await onRequest(fakeContext(req, ENV));
    expect(res.status).toBe(401);
  });

  it('200s and forwards to next() with correct credentials', async () => {
    const req = new Request('https://dash.example.com/api/queue', {
      headers: { Authorization: basicAuthHeader('ops', 'correct-horse') },
    });
    const res = await onRequest(fakeContext(req, ENV));
    expect(res.status).toBe(200);
    expect(await res.text()).toBe('ok');
  });

  it('every response (401 and 200) carries X-Robots-Tag and Cache-Control', async () => {
    const unauth = await onRequest(fakeContext(new Request('https://dash.example.com/'), ENV));
    expect(unauth.headers.get('X-Robots-Tag')).toBe('noindex');
    expect(unauth.headers.get('Cache-Control')).toBe('no-store');

    const req = new Request('https://dash.example.com/', {
      headers: { Authorization: basicAuthHeader('ops', 'correct-horse') },
    });
    const ok = await onRequest(fakeContext(req, ENV));
    expect(ok.headers.get('X-Robots-Tag')).toBe('noindex');
    expect(ok.headers.get('Cache-Control')).toBe('no-store');
  });

  it('503s when DASHBOARD_PASS is not configured (never fails open)', async () => {
    const req = new Request('https://dash.example.com/');
    const res = await onRequest(fakeContext(req, { DASHBOARD_USER: 'ops' }));
    expect(res.status).toBe(503);
  });

  it('401s on a malformed Authorization header', async () => {
    const req = new Request('https://dash.example.com/', {
      headers: { Authorization: 'Basic not-valid-base64!!' },
    });
    const res = await onRequest(fakeContext(req, ENV));
    expect(res.status).toBe(401);
  });
});
