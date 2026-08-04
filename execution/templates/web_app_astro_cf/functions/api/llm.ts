// POST /api/llm  — example LLM call scaffold.
//
// Provider preference (per ~/.claude/rules/model-tier.md):
//   1. Gemini 2.5 Flash (free tier, 250 RPD, 10 RPM)   — default
//   2. Anthropic (Sonnet 4.6 minimum, if paid budget)  — fallback
//   3. GLM 5.2 — FORBIDDEN for any PII/customer/CV/lead content.
//
// Cost is logged in EUR via telemetry.ts (see MODEL_PRICING_USD).
//
// This is a REFERENCE. Delete if the project does not call an LLM.

import { logEvent, estimateCostEUR } from '../../src/lib/telemetry';

interface Env {
  APP_KV?: KVNamespace;
  GEMINI_API_KEY?: string;
  ANTHROPIC_API_KEY?: string;
}

interface Body {
  prompt: string;
  max_tokens?: number;
}

async function callGemini(apiKey: string, prompt: string, maxTokens: number) {
  const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=${apiKey}`;
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      contents: [{ parts: [{ text: prompt }] }],
      generationConfig: { maxOutputTokens: maxTokens, temperature: 0.7 },
    }),
  });
  if (!res.ok) throw new Error(`Gemini ${res.status}: ${await res.text()}`);
  const data = await res.json() as {
    candidates?: Array<{ content?: { parts?: Array<{ text?: string }> } }>;
    usageMetadata?: { promptTokenCount?: number; candidatesTokenCount?: number };
  };
  const text = data.candidates?.[0]?.content?.parts?.[0]?.text ?? '';
  return {
    text,
    model: 'gemini-2.5-flash',
    usage: {
      input_tokens: data.usageMetadata?.promptTokenCount ?? 0,
      output_tokens: data.usageMetadata?.candidatesTokenCount ?? 0,
    },
  };
}

async function callAnthropic(apiKey: string, prompt: string, maxTokens: number) {
  const res = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-api-key': apiKey,
      'anthropic-version': '2023-06-01',
    },
    body: JSON.stringify({
      model: 'claude-sonnet-4-6',
      max_tokens: maxTokens,
      messages: [{ role: 'user', content: prompt }],
    }),
  });
  if (!res.ok) throw new Error(`Anthropic ${res.status}: ${await res.text()}`);
  const data = await res.json() as {
    content?: Array<{ text?: string }>;
    usage?: { input_tokens?: number; output_tokens?: number; cache_read_input_tokens?: number };
  };
  return {
    text: data.content?.map(c => c.text ?? '').join('') ?? '',
    model: 'claude-sonnet-4-6',
    usage: {
      input_tokens: data.usage?.input_tokens ?? 0,
      cache_read_tokens: data.usage?.cache_read_input_tokens ?? 0,
      output_tokens: data.usage?.output_tokens ?? 0,
    },
  };
}

export const onRequest: PagesFunction<Env> = async ({ request, env }) => {
  if (request.method !== 'POST') return new Response('Method not allowed', { status: 405 });

  let body: Body;
  try { body = await request.json() as Body; }
  catch { return new Response('Invalid JSON', { status: 400 }); }

  if (!body.prompt || typeof body.prompt !== 'string') {
    return new Response('prompt required', { status: 400 });
  }
  const maxTokens = Math.min(body.max_tokens ?? 512, 2048);

  try {
    let out;
    if (env.GEMINI_API_KEY) {
      out = await callGemini(env.GEMINI_API_KEY, body.prompt, maxTokens);
    } else if (env.ANTHROPIC_API_KEY) {
      out = await callAnthropic(env.ANTHROPIC_API_KEY, body.prompt, maxTokens);
    } else {
      return new Response('No LLM provider configured (set GEMINI_API_KEY or ANTHROPIC_API_KEY).', { status: 503 });
    }
    const cost_eur = estimateCostEUR(out.model, out.usage);
    await logEvent(env.APP_KV, 'llm.call', { model: out.model, cost_eur, usage: out.usage });
    return new Response(JSON.stringify({ text: out.text, model: out.model, cost_eur }), {
      headers: { 'Content-Type': 'application/json' },
    });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return new Response(`LLM error: ${msg}`, { status: 502 });
  }
};
