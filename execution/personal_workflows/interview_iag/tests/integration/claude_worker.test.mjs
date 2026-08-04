// Integration test: exercises the Cloudflare Pages Function `functions/api/claude.ts`
// end-to-end against the Anthropic API through a fetch-mock, without needing a
// live wrangler dev server. This isolates our routing / validation / prompt
// assembly logic from Claude's real responses.
//
// We do this by dynamically importing the function module and stubbing
// globalThis.fetch to intercept the outbound call to api.anthropic.com.

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { onRequestPost, onRequestGet } from '../../functions/api/claude.ts';

const realFetch = globalThis.fetch;

function makeRequest(body, headers = {}) {
  return new Request('https://agentup-iag.pages.dev/api/claude', {
    method: 'POST',
    headers: { 'content-type': 'application/json', 'Origin': 'https://agentup-iag.pages.dev', ...headers },
    body: JSON.stringify(body),
  });
}

function baseEnv(overrides = {}) {
  return {
    ANTHROPIC_API_KEY: 'sk-ant-test-fake',
    ALLOWED_ORIGINS: 'https://agentup-iag.pages.dev,http://localhost:4321',
    AGENTUP_KV: undefined, // unbound → rate limit skipped in tests
    ...overrides,
  };
}

function mockAnthropicOnce(responseText, status = 200) {
  const spy = vi.fn(async (url, init) => {
    if (typeof url === 'string' && url.includes('api.anthropic.com')) {
      return new Response(
        JSON.stringify({ content: [{ type: 'text', text: responseText }] }),
        { status, headers: { 'content-type': 'application/json' } },
      );
    }
    return realFetch(url, init);
  });
  globalThis.fetch = spy;
  return spy;
}

// Anthropic returns 400 with the specific "credit balance is too low" message
// when the account is empty. This is the trigger for Gemini fallback.
function mockAnthropicNoCredit() {
  const errBody = JSON.stringify({
    type: 'error',
    error: { type: 'invalid_request_error', message: 'Your credit balance is too low to access the Anthropic API.' },
  });
  globalThis.fetch = vi.fn(async (url) => {
    if (typeof url === 'string' && url.includes('api.anthropic.com')) {
      return new Response(errBody, { status: 400, headers: { 'content-type': 'application/json' } });
    }
    if (typeof url === 'string' && url.includes('generativelanguage.googleapis.com')) {
      return new Response(JSON.stringify({
        candidates: [{ content: { parts: [{ text: 'gemini_fallback_response' }] } }],
      }), { status: 200, headers: { 'content-type': 'application/json' } });
    }
    throw new Error('unmocked url: ' + url);
  });
}

function mockGeminiOnly(text) {
  globalThis.fetch = vi.fn(async (url) => {
    if (typeof url === 'string' && url.includes('generativelanguage.googleapis.com')) {
      return new Response(JSON.stringify({
        candidates: [{ content: { parts: [{ text }] } }],
      }), { status: 200, headers: { 'content-type': 'application/json' } });
    }
    throw new Error('unexpected fetch: ' + url);
  });
}

beforeEach(() => { globalThis.fetch = realFetch; });
afterEach(() => { globalThis.fetch = realFetch; vi.restoreAllMocks(); });

describe('GET /api/claude (health)', () => {
  it('returns model and key_present status', async () => {
    const res = await onRequestGet({ request: new Request('https://agentup-iag.pages.dev/api/claude'), env: baseEnv() });
    const body = await res.json();
    expect(res.status).toBe(200);
    expect(body.ok).toBe(true);
    expect(body.primary_model).toBe('claude-sonnet-4-6');
    expect(body.fallback_model).toMatch(/^gemini/);
    expect(body.key_present).toBe(true);
  });
});

describe('POST /api/claude — roleplay mode', () => {
  it('returns customer text on happy path', async () => {
    mockAnthropicOnce("I've been on hold twice already — I want this refunded today.");
    const res = await onRequestPost({
      request: makeRequest({
        mode: 'roleplay',
        scenario: 'Duplicate charge on the bill.',
        opening: 'Hi, I was charged twice.',
        difficulty: 'Intermediate',
        history: [{ role: 'agent', text: 'I understand — let me pull up your account.' }],
      }),
      env: baseEnv(),
    });
    const body = await res.json();
    expect(res.status).toBe(200);
    expect(typeof body.text).toBe('string');
    expect(body.text.length).toBeGreaterThan(0);
  });

  it('rejects roleplay when history ends with a customer turn', async () => {
    const res = await onRequestPost({
      request: makeRequest({
        mode: 'roleplay',
        scenario: 'x', opening: 'x', difficulty: 'Beginner',
        history: [{ role: 'customer', text: 'still waiting' }],
      }),
      env: baseEnv(),
    });
    expect(res.status).toBe(502); // wrapped as upstream_failure
  });

  it('rejects roleplay missing fields', async () => {
    const res = await onRequestPost({
      request: makeRequest({ mode: 'roleplay', scenario: 'x' }),
      env: baseEnv(),
    });
    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error).toBe('roleplay_missing_fields');
  });
});

describe('POST /api/claude — score mode', () => {
  it('returns a validated scorecard on happy path', async () => {
    const fakeScorecard = {
      empathyScore: 78, accuracyScore: 82, resolutionScore: 74, professionalismScore: 88,
      overallScore: 80, strength: 'Clear ownership of the issue.', improvement: 'Confirm the ETA in writing next time.',
    };
    mockAnthropicOnce(JSON.stringify(fakeScorecard));
    const res = await onRequestPost({
      request: makeRequest({
        mode: 'score',
        scenario: 'Duplicate charge.',
        difficulty: 'Intermediate',
        transcript: [
          { role: 'agent', text: 'I hear you — let me check.' },
          { role: 'customer', text: 'OK, I want a refund today.' },
        ],
      }),
      env: baseEnv(),
    });
    const body = await res.json();
    expect(res.status).toBe(200);
    expect(body).toMatchObject(fakeScorecard);
    expect(body._provider).toBe('anthropic');
    expect(body._usage).toBeDefined();
    expect(body._usage.provider).toBe('anthropic');
    expect(body._usage.model).toBe('claude-sonnet-4-6');
    expect(typeof body._usage.latencyMs).toBe('number');
  });

  it('502s when upstream returns malformed JSON', async () => {
    mockAnthropicOnce('this is not JSON at all');
    const res = await onRequestPost({
      request: makeRequest({
        mode: 'score', scenario: 'x', difficulty: 'Beginner',
        transcript: [{ role: 'agent', text: 'hi' }],
      }),
      env: baseEnv(),
    });
    expect(res.status).toBe(502);
  });

  it('502s when upstream returns wrong shape', async () => {
    mockAnthropicOnce(JSON.stringify({ empathyScore: 80 })); // missing fields
    const res = await onRequestPost({
      request: makeRequest({
        mode: 'score', scenario: 'x', difficulty: 'Beginner',
        transcript: [{ role: 'agent', text: 'hi' }],
      }),
      env: baseEnv(),
    });
    expect(res.status).toBe(502);
    const body = await res.json();
    expect(body.error).toBe('scorecard_shape_mismatch');
  });
});

describe('POST /api/claude — model-answer mode', () => {
  const validAnswer = {
    transcript: [
      { role: 'customer', text: 'Hi, I was charged twice.' },
      { role: 'agent',    text: 'I understand — let me check your account right away.' },
      { role: 'customer', text: 'Thank you.' },
      { role: 'agent',    text: 'I can see the duplicate; refunding it now with a confirmation email.' },
      { role: 'customer', text: 'Great.' },
      { role: 'agent',    text: 'Anything else I can help with today?' },
      { role: 'customer', text: 'No, thanks!' },
      { role: 'agent',    text: 'Wonderful — you should see the refund in 3-5 business days.' },
      { role: 'customer', text: 'Perfect.' },
      { role: 'agent',    text: 'Thank you for reaching out — have a great day.' },
    ],
    commentary: 'The agent led with empathy, gave a concrete resolution, and closed warmly.',
  };

  it('returns validated model answer on happy path', async () => {
    mockAnthropicOnce(JSON.stringify(validAnswer));
    const res = await onRequestPost({
      request: makeRequest({
        mode: 'model-answer',
        scenario: 'Duplicate charge on bill.',
        opening: 'Hi, I was charged twice.',
        difficulty: 'Beginner',
      }),
      env: baseEnv(),
    });
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.transcript).toHaveLength(10);
    expect(body.commentary).toContain('empathy');
    expect(body._provider).toBe('anthropic');
  });

  it('rejects model-answer with missing fields', async () => {
    const res = await onRequestPost({
      request: makeRequest({ mode: 'model-answer', scenario: 'x' }),
      env: baseEnv(),
    });
    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error).toBe('model_answer_missing_fields');
  });

  it('502s when upstream returns malformed model-answer JSON', async () => {
    mockAnthropicOnce('not json at all');
    const res = await onRequestPost({
      request: makeRequest({
        mode: 'model-answer', scenario: 'x', opening: 'y', difficulty: 'Beginner',
      }),
      env: baseEnv(),
    });
    expect(res.status).toBe(502);
    const body = await res.json();
    expect(body.error).toMatch(/model_answer|upstream/);
  });

  it('502s when transcript has wrong shape', async () => {
    mockAnthropicOnce(JSON.stringify({ transcript: [{ role: 'wrong', text: 'x' }], commentary: 'x' }));
    const res = await onRequestPost({
      request: makeRequest({
        mode: 'model-answer', scenario: 'x', opening: 'y', difficulty: 'Beginner',
      }),
      env: baseEnv(),
    });
    expect(res.status).toBe(502);
  });
});

describe('POST /api/claude — errors and edge cases', () => {
  it('rejects payload exceeding MAX_BODY_BYTES with typed 413', async () => {
    // Build a body >32KB and set Content-Length so the cap fires pre-parse.
    const huge = 'x'.repeat(40_000);
    const body = JSON.stringify({
      mode: 'score', scenario: huge, difficulty: 'Beginner',
      transcript: [{ role: 'agent', text: 'hi' }],
    });
    const req = new Request('https://agentup-iag.pages.dev/api/claude', {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        'content-length': String(body.length),
        'Origin': 'https://agentup-iag.pages.dev',
      },
      body,
    });
    const res = await onRequestPost({ request: req, env: baseEnv() });
    expect(res.status).toBe(413);
    const respBody = await res.json();
    expect(respBody.error).toBe('payload_too_large');
    expect(respBody.max_bytes).toBe(32000);
  });

  it('rejects invalid JSON body', async () => {
    const req = new Request('https://agentup-iag.pages.dev/api/claude', {
      method: 'POST',
      headers: { 'content-type': 'application/json', 'Origin': 'https://agentup-iag.pages.dev' },
      body: 'not-json',
    });
    const res = await onRequestPost({ request: req, env: baseEnv() });
    expect(res.status).toBe(400);
  });

  it('rejects unknown mode', async () => {
    const res = await onRequestPost({
      request: makeRequest({ mode: 'destroy_the_world' }),
      env: baseEnv(),
    });
    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error).toBe('invalid_mode');
  });

  it('rejects disallowed origin', async () => {
    const res = await onRequestPost({
      request: makeRequest({ mode: 'roleplay' }, { 'Origin': 'https://attacker.example' }),
      env: baseEnv(),
    });
    expect(res.status).toBe(403);
  });

  it('accepts wildcard subdomain of allowlisted host', async () => {
    mockAnthropicOnce("Sure — let's fix this.");
    const res = await onRequestPost({
      request: makeRequest(
        { mode: 'roleplay', scenario: 'x', opening: 'x', difficulty: 'Beginner', history: [{ role: 'agent', text: 'hi' }] },
        { 'Origin': 'https://abc123.agentup-iag.pages.dev' },
      ),
      env: baseEnv({ ALLOWED_ORIGINS: 'https://agentup-iag.pages.dev,https://*.agentup-iag.pages.dev' }),
    });
    expect(res.status).toBe(200);
  });

  it('rejects a hostile lookalike that only looks like a subdomain', async () => {
    const res = await onRequestPost({
      request: makeRequest(
        { mode: 'roleplay', scenario: 'x', opening: 'x', difficulty: 'Beginner', history: [{ role: 'agent', text: 'hi' }] },
        { 'Origin': 'https://agentup-iag.pages.dev.attacker.example' },
      ),
      env: baseEnv({ ALLOWED_ORIGINS: 'https://agentup-iag.pages.dev,https://*.agentup-iag.pages.dev' }),
    });
    expect(res.status).toBe(403);
  });

  it('500s when both ANTHROPIC_API_KEY and GEMINI_API_KEY missing', async () => {
    mockAnthropicOnce('unused'); // shouldn't be called
    const res = await onRequestPost({
      request: makeRequest({
        mode: 'roleplay', scenario: 'x', opening: 'x', difficulty: 'Beginner',
        history: [{ role: 'agent', text: 'hi' }],
      }),
      env: baseEnv({ ANTHROPIC_API_KEY: undefined, GEMINI_API_KEY: undefined }),
    });
    expect(res.status).toBe(500);
  });

  it('propagates upstream 429 as 429', async () => {
    mockAnthropicOnce('rate limited', 429);
    const res = await onRequestPost({
      request: makeRequest({
        mode: 'roleplay', scenario: 'x', opening: 'x', difficulty: 'Beginner',
        history: [{ role: 'agent', text: 'hi' }],
      }),
      env: baseEnv(),
    });
    expect(res.status).toBe(429);
  });
});

describe('POST /api/claude — Gemini fallback', () => {
  it('falls back to Gemini when Anthropic returns credit-too-low 400', async () => {
    mockAnthropicNoCredit();
    const res = await onRequestPost({
      request: makeRequest({
        mode: 'roleplay', scenario: 'x', opening: 'x', difficulty: 'Beginner',
        history: [{ role: 'agent', text: 'hi' }],
      }),
      env: baseEnv({ GEMINI_API_KEY: 'gk-fake' }),
    });
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.provider).toBe('gemini');
    expect(body.text).toBe('gemini_fallback_response');
  });

  it('uses Gemini directly when Anthropic key is absent', async () => {
    mockGeminiOnly('direct gemini reply');
    const res = await onRequestPost({
      request: makeRequest({
        mode: 'roleplay', scenario: 'x', opening: 'x', difficulty: 'Beginner',
        history: [{ role: 'agent', text: 'hi' }],
      }),
      env: baseEnv({ ANTHROPIC_API_KEY: undefined, GEMINI_API_KEY: 'gk-fake' }),
    });
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.provider).toBe('gemini');
  });

  it('propagates the credit-too-low error when no Gemini key is available', async () => {
    mockAnthropicNoCredit();
    const res = await onRequestPost({
      request: makeRequest({
        mode: 'roleplay', scenario: 'x', opening: 'x', difficulty: 'Beginner',
        history: [{ role: 'agent', text: 'hi' }],
      }),
      env: baseEnv({ GEMINI_API_KEY: undefined }),
    });
    expect(res.status).toBe(400);
  });

  it('does NOT fall back on non-credit Anthropic errors', async () => {
    // Simulate 500 from Anthropic; fallback should not fire, error surfaces as-is.
    globalThis.fetch = vi.fn(async (url) => {
      if (typeof url === 'string' && url.includes('api.anthropic.com')) {
        return new Response('{"error":{"message":"internal server error"}}', { status: 500 });
      }
      throw new Error('gemini should not be called: ' + url);
    });
    const res = await onRequestPost({
      request: makeRequest({
        mode: 'roleplay', scenario: 'x', opening: 'x', difficulty: 'Beginner',
        history: [{ role: 'agent', text: 'hi' }],
      }),
      env: baseEnv({ GEMINI_API_KEY: 'gk-fake' }),
    });
    expect(res.status).toBe(502); // anthropic_http_500 → default 502
  });
});

describe('POST /api/claude — KV rate limiter', () => {
  // Minimal in-memory KV mock. Only get/put with expirationTtl are used.
  function makeKV() {
    const store = new Map();
    return {
      get: async (k) => store.has(k) ? store.get(k).value : null,
      put: async (k, v, _opts) => { store.set(k, { value: v }); },
      delete: async (k) => { store.delete(k); },
    };
  }

  it('bumps counter and allows within limit', async () => {
    mockAnthropicOnce('sure');
    const env = baseEnv({ AGENTUP_KV: makeKV() });
    for (let i = 0; i < 3; i++) {
      const res = await onRequestPost({
        request: makeRequest({
          mode: 'roleplay', scenario: 'x', opening: 'x', difficulty: 'Beginner',
          history: [{ role: 'agent', text: 'hi' }],
        }),
        env,
      });
      expect(res.status).toBe(200);
    }
  });

  it('rejects with 429 once RATE_LIMIT_PER_DAY exceeded', async () => {
    mockAnthropicOnce('sure');
    const kv = makeKV();
    // Pre-populate the counter to the limit.
    const encoder = new TextEncoder();
    const ipDay = '0.0.0.0:' + new Date().toISOString().slice(0, 10);
    const digest = await crypto.subtle.digest('SHA-256', encoder.encode(ipDay));
    const hex = Array.from(new Uint8Array(digest)).map((b) => b.toString(16).padStart(2, '0')).join('');
    await kv.put('rl:' + hex, '500');

    const res = await onRequestPost({
      request: makeRequest({
        mode: 'roleplay', scenario: 'x', opening: 'x', difficulty: 'Beginner',
        history: [{ role: 'agent', text: 'hi' }],
      }),
      env: baseEnv({ AGENTUP_KV: kv }),
    });
    expect(res.status).toBe(429);
  });
});
