// Thin fetch wrapper around the Pages Function. Same-origin. Handles typed errors.
// Also records telemetry (latency, tokens, cost, provider) into the in-browser
// telemetry store used by the Dev HUD and the dashboard cost tile.

import type { Difficulty, Turn, Scorecard, ModelAnswer } from './types';
import { redactDeep } from './pii';
import { recordCall, estimateCostEur } from './telemetry';

const API_PATH = '/api/claude';

// Playwright + integration tests can set window.__AGENTUP_MOCK to hijack
// responses without a network call. Undefined in production.
declare global {
  interface Window {
    __AGENTUP_MOCK?: (body: unknown) => Promise<unknown>;
    __AGENTUP_PII_REDACTED_TOTAL?: number;
  }
}

interface UsageMeta {
  provider: 'anthropic' | 'gemini';
  model: string;
  inputTokens: number;
  outputTokens: number;
  latencyMs: number;
}

export class ApiError extends Error {
  status: number;
  code?: string;
  constructor(status: number, message: string, code?: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

async function post<T>(mode: 'roleplay' | 'score' | 'model-answer', body: Record<string, unknown>): Promise<T> {
  // Client-side PII redaction — walk every string field in the payload and
  // mask Aadhaar / PAN / mobile / UPI / cards / email BEFORE it leaves the
  // browser. Increments a global counter the UI can surface as a badge.
  const { value: safeBody, total: redactedCount } = redactDeep(body);
  if (typeof window !== 'undefined' && redactedCount > 0) {
    window.__AGENTUP_PII_REDACTED_TOTAL = (window.__AGENTUP_PII_REDACTED_TOTAL ?? 0) + redactedCount;
  }

  const mock = typeof window !== 'undefined' ? window.__AGENTUP_MOCK : undefined;
  const started = (typeof performance !== 'undefined' ? performance.now() : Date.now());

  if (mock) {
    const out = await mock(safeBody);
    // Mocks don't emit telemetry (they aren't real network calls).
    return out as T;
  }

  let parsed: unknown = null;
  let ok = false;
  let status = 0;
  let errorCode: string | undefined;
  try {
    const res = await fetch(API_PATH, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(safeBody),
    });
    status = res.status;
    const text = await res.text();
    try { parsed = text ? JSON.parse(text) : null; }
    catch { throw new ApiError(res.status, `non-JSON response: ${text.slice(0, 200)}`); }
    ok = res.ok;
    if (!ok) {
      const err = (parsed ?? {}) as { error?: string; detail?: string };
      errorCode = err.error;
      throw new ApiError(res.status, err.detail ?? err.error ?? `HTTP ${res.status}`, err.error);
    }
    return parsed as T;
  } finally {
    const latencyMs = Math.round((typeof performance !== 'undefined' ? performance.now() : Date.now()) - started);
    const usage: UsageMeta | undefined = (parsed && typeof parsed === 'object' && '_usage' in (parsed as object))
      ? (parsed as { _usage: UsageMeta })._usage
      : undefined;
    recordCall({
      mode,
      provider: usage?.provider ?? 'unknown',
      latencyMs,
      inputTokens:  usage?.inputTokens  ?? 0,
      outputTokens: usage?.outputTokens ?? 0,
      costEur: usage ? estimateCostEur(usage.provider, usage.model, usage.inputTokens, usage.outputTokens) : 0,
      ok,
      errorCode: ok ? undefined : (errorCode ?? `http_${status}`),
    });
  }
}

export function callRoleplay(input: {
  scenario: string; opening: string; difficulty: Difficulty; history: Turn[];
}): Promise<{ text: string }> {
  return post<{ text: string }>('roleplay', { mode: 'roleplay', ...input });
}

/**
 * Streaming variant of callRoleplay. Opens an SSE stream from the Pages
 * Function, invokes `onChunk(text)` for every incremental text delta, and
 * resolves with the final full text + provider once the `done` event
 * arrives. Records telemetry from the `done` event's usage metadata.
 *
 * Falls back to non-streaming callRoleplay if the runtime doesn't have
 * ReadableStream support (very old browsers, or the __AGENTUP_MOCK path
 * in tests).
 */
export async function callRoleplayStream(
  input: { scenario: string; opening: string; difficulty: Difficulty; history: Turn[] },
  onChunk: (delta: string) => void,
): Promise<{ text: string; provider: 'anthropic' | 'gemini' }> {
  // Test / no-stream fallback.
  const mock = typeof window !== 'undefined' ? window.__AGENTUP_MOCK : undefined;
  if (mock) {
    const r = await callRoleplay(input);
    onChunk(r.text);
    return { text: r.text, provider: 'anthropic' };
  }

  const { value: safeInput, total: redactedCount } = redactDeep(input);
  if (typeof window !== 'undefined' && redactedCount > 0) {
    window.__AGENTUP_PII_REDACTED_TOTAL = (window.__AGENTUP_PII_REDACTED_TOTAL ?? 0) + redactedCount;
  }
  const body = { mode: 'roleplay', stream: true, ...safeInput };

  const started = (typeof performance !== 'undefined' ? performance.now() : Date.now());
  let ok = false;
  let errorCode: string | undefined;
  let provider: 'anthropic' | 'gemini' = 'anthropic';
  let model = '';
  let inputTokens = 0;
  let outputTokens = 0;
  let fullText = '';

  try {
    const res = await fetch(API_PATH, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok || !res.body) {
      const err = await res.text().catch(() => '');
      errorCode = `http_${res.status}`;
      throw new ApiError(res.status, err.slice(0, 200) || `HTTP ${res.status}`);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = '';
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      let idx: number;
      while ((idx = buf.indexOf('\n\n')) !== -1) {
        const frame = buf.slice(0, idx);
        buf = buf.slice(idx + 2);
        if (!frame.trim()) continue;
        const evLine   = frame.split('\n').find((l) => l.startsWith('event:'))?.slice(6).trim() ?? '';
        const dataLine = frame.split('\n').find((l) => l.startsWith('data:'))?.slice(5).trim()  ?? '';
        if (!dataLine) continue;
        try {
          const data = JSON.parse(dataLine);
          if (evLine === 'chunk' && typeof data.text === 'string') {
            fullText += data.text;
            if (data.provider) provider = data.provider;
            onChunk(data.text);
          } else if (evLine === 'done') {
            provider     = data.provider ?? provider;
            model        = data.model    ?? '';
            inputTokens  = data.inputTokens  ?? 0;
            outputTokens = data.outputTokens ?? 0;
          } else if (evLine === 'error') {
            errorCode = 'stream_error';
            throw new ApiError(502, data.message ?? 'stream error');
          }
        } catch (parseErr) {
          if (parseErr instanceof ApiError) throw parseErr;
          // else: malformed SSE frame — skip
        }
      }
    }
    ok = true;
    return { text: fullText.trim(), provider };
  } finally {
    const latencyMs = Math.round((typeof performance !== 'undefined' ? performance.now() : Date.now()) - started);
    recordCall({
      mode: 'roleplay',
      provider,
      latencyMs,
      inputTokens,
      outputTokens,
      costEur: estimateCostEur(provider, model, inputTokens, outputTokens),
      ok,
      errorCode,
    });
  }
}

export function callScore(input: {
  scenario: string; difficulty: Difficulty; transcript: Turn[];
}): Promise<Scorecard> {
  return post<Scorecard>('score', { mode: 'score', ...input });
}

export function callModelAnswer(input: {
  scenario: string; opening: string; difficulty: Difficulty;
}): Promise<ModelAnswer> {
  return post<ModelAnswer>('model-answer', { mode: 'model-answer', ...input });
}
