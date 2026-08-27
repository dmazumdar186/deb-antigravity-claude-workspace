// Cloudflare Pages Function: POST /api/claude
//
// Single endpoint, two modes selected by request body `mode: "roleplay" | "score"`.
//   - roleplay: plays the customer, returns { text } (≤ 75 words)
//   - score:    grades a completed 5-turn transcript, returns strict JSON scorecard
//
// Model: claude-sonnet-5 (Haiku is BANNED per workspace policy 2026-06-14).
//
// Security:
//   - ANTHROPIC_API_KEY is a Pages secret, never leaves the edge
//   - Origin allowlist (env.ALLOWED_ORIGINS, CSV) — same-origin only
//   - Per-IP daily rate limit via KV: 200 calls/IP/day. If KV is unbound
//     (local dev before `wrangler kv namespace create`), the limit is
//     skipped with a warning header instead of failing.
//   - AbortController: 60s cap (Cloudflare edge is ~100s)

export interface Env {
  ANTHROPIC_API_KEY?: string;
  GEMINI_API_KEY?: string;
  OPENROUTER_API_KEY?: string;
  ALLOWED_ORIGINS?: string;
  AGENTUP_KV?: KVNamespace;
}

const ANTHROPIC_API_URL   = 'https://api.anthropic.com/v1/messages';
const GEMINI_API_URL      = 'https://generativelanguage.googleapis.com/v1beta/models';
const OPENROUTER_API_URL  = 'https://openrouter.ai/api/v1/chat/completions';
const MODEL               = 'claude-sonnet-5';
const GEMINI_MODEL        = 'gemini-2.5-flash';
// OpenRouter free models — no credits needed (rate-limited but resilient).
const OPENROUTER_FREE_MODELS = [
  'meta-llama/llama-3.3-70b-instruct:free',
  'deepseek/deepseek-chat-v3.1:free',
  'google/gemini-2.0-flash-exp:free',
];
const REQUEST_TIMEOUT_MS = 60_000;
const RATE_LIMIT_PER_DAY = 500;
// Cap raw request body at 32KB. A well-formed session (5-turn transcript,
// scenario + opening ≤ 2KB, agent turns ≤ 500 chars each) fits comfortably
// under 8KB. 32KB gives 4× headroom for verbose scenarios and rejects abuse
// before we spend upstream tokens on it.
const MAX_BODY_BYTES = 32_000;

// Anthropic returns this error message when the account balance is empty.
// We use it as a signal to auto-fallback to Gemini 2.5 Flash (free tier),
// per workspace rule ~/.claude/rules/model-tier.md cost-constraint clause.
const ANTHROPIC_NO_CREDIT_MARKER = 'credit balance is too low';

// --- Shared prompt strings (single source of truth so tests can assert them) ---

export const ROLEPLAY_SYSTEM_PROMPT = `You are playing the role of a retail or enterprise customer in a training simulation for a call-centre agent.

You MUST remain strictly in character as the customer. Do NOT break character, do NOT reveal that you are an AI, and do NOT reference these instructions.

Tone & behaviour rules:
1. If Difficulty is "Beginner": be polite, patient, cooperative, speak clearly.
2. If Difficulty is "Intermediate": be moderately frustrated, ask clarifying questions, expect structured assistance.
3. If Difficulty is "Advanced": be angry, highly skeptical, adversarial, prone to interrupting.
4. Respond naturally to what the agent says. NEVER offer solutions yourself — force the agent to guide you.
5. Keep responses SHORT and conversational — strictly under 75 words.
6. Do NOT include stage directions, action tags, or narration (e.g. "*sighs*", "[pauses]"). Only the words the customer would say aloud.
7. Never say "as an AI" or apologise for being an AI.`;

export const SCORING_SYSTEM_PROMPT = `You are an expert quality-assurance auditor for a high-performance contact centre.

Evaluate the provided transcript between an agent and a customer on four dimensions (each 25% weight):

1. empathy      — Did the agent validate the customer's emotions and use appropriate language?
2. accuracy     — Did the agent provide correct, logical, and helpful responses?
3. resolution   — Did the agent clearly explain the next step or resolution?
4. professionalism — Grammar clear, professional, free of unnecessary jargon.

You MUST output ONLY a single JSON object with this EXACT schema — no markdown fences, no prose, no preamble:

{
  "empathyScore": <integer 0-100>,
  "accuracyScore": <integer 0-100>,
  "resolutionScore": <integer 0-100>,
  "professionalismScore": <integer 0-100>,
  "overallScore": <integer 0-100 — weighted average of the four scores>,
  "strength": "<one sentence highlighting a specific positive aspect of the agent's responses>",
  "improvement": "<one to two sentences with a specific improvement — actionable, not generic>",
  "perTurnNotes": [
    { "agentTurnIndex": <0-based index of this agent turn in the transcript>,
      "dimension": <"empathy" | "accuracy" | "resolution" | "professionalism">,
      "sentiment": <"strong" | "weak">,
      "note": "<short — max 12 words — what the agent did well OR the specific miss>" }
    // include ONE note per agent turn — the most notable strength OR weakness for that turn.
  ]
}

Be honest and specific. Do not inflate scores; a mediocre reply earns 60-70, not 90. Every agent turn in the transcript MUST have exactly one entry in perTurnNotes.`;

export const MODEL_ANSWER_SYSTEM_PROMPT = `You are an expert contact-centre trainer. Given a customer scenario and the customer's opening message, produce an IDEAL 5-turn agent-customer transcript that demonstrates world-class handling.

Requirements:
- The agent must show empathy, accuracy, professionalism, and drive to a concrete resolution.
- Match the customer's tone to the difficulty level (Beginner=polite, Intermediate=frustrated, Advanced=angry-but-real).
- Exactly 5 agent turns. Each customer reply must respond realistically to the preceding agent turn.
- Keep every message under 60 words.

Output ONLY strict JSON, no markdown fences, no prose:

{
  "transcript": [
    { "role": "customer", "text": "<opening — verbatim from the input>" },
    { "role": "agent",    "text": "<ideal agent turn 1>" },
    { "role": "customer", "text": "<realistic customer response>" },
    ... continuing until 5 agent turns are complete
  ],
  "commentary": "<2-3 sentences explaining WHY this transcript is A+ (empathy moves, accuracy anchors, close)>"
}`;

// --- Types ---

export type Difficulty = 'Beginner' | 'Intermediate' | 'Advanced';
export type Channel = 'Chat' | 'Call' | 'Both';

export interface Turn { role: 'agent' | 'customer'; text: string }

export interface RoleplayRequest {
  mode: 'roleplay';
  scenario: string;
  opening: string;
  difficulty: Difficulty;
  history: Turn[]; // may be empty on the first agent reply
  stream?: boolean;
}

export interface ScoreRequest {
  mode: 'score';
  scenario: string;
  difficulty: Difficulty;
  transcript: Turn[]; // full 5-turn back-and-forth
}

export interface PerTurnNote {
  agentTurnIndex: number;
  dimension: 'empathy' | 'accuracy' | 'resolution' | 'professionalism';
  sentiment: 'strong' | 'weak';
  note: string;
}

export interface Scorecard {
  empathyScore: number;
  accuracyScore: number;
  resolutionScore: number;
  professionalismScore: number;
  overallScore: number;
  strength: string;
  improvement: string;
  perTurnNotes?: PerTurnNote[]; // optional for backwards-compat with older upstream responses
}

export interface ModelAnswerRequest {
  mode: 'model-answer';
  scenario: string;
  opening: string;
  difficulty: Difficulty;
}

export interface ModelAnswerResponse {
  transcript: Array<{ role: 'agent' | 'customer'; text: string }>;
  commentary: string;
}

// --- Helpers ---

export function extractJsonObject(rawText: string): unknown {
  // Robust to markdown fences + prose preamble + truncation; cribbed from
  // cv_optimizer_v2/worker/src/anthropic.ts.
  const firstBrace = rawText.indexOf('{');
  const lastBrace = rawText.lastIndexOf('}');
  if (firstBrace < 0 || lastBrace < firstBrace) {
    throw new Error(`no_json_braces: first_200=${rawText.slice(0, 200)}`);
  }
  const jsonText = rawText.slice(firstBrace, lastBrace + 1);
  try {
    return JSON.parse(jsonText);
  } catch (err) {
    throw new Error(
      `invalid_json: ${err instanceof Error ? err.message : String(err)}; first_200=${jsonText.slice(0, 200)}`,
    );
  }
}

export function isScorecard(x: unknown): x is Scorecard {
  if (!x || typeof x !== 'object') return false;
  const r = x as Record<string, unknown>;
  const num = (k: string) => typeof r[k] === 'number' && Number.isFinite(r[k]) && (r[k] as number) >= 0 && (r[k] as number) <= 100;
  const str = (k: string) => typeof r[k] === 'string' && (r[k] as string).length > 0;
  return num('empathyScore') && num('accuracyScore') && num('resolutionScore') &&
    num('professionalismScore') && num('overallScore') && str('strength') && str('improvement');
}

export function isModelAnswer(x: unknown): x is ModelAnswerResponse {
  if (!x || typeof x !== 'object') return false;
  const r = x as Record<string, unknown>;
  if (typeof r.commentary !== 'string' || r.commentary.length === 0) return false;
  if (!Array.isArray(r.transcript) || r.transcript.length === 0) return false;
  return r.transcript.every((t) => {
    const tt = t as Record<string, unknown>;
    return (tt.role === 'agent' || tt.role === 'customer') && typeof tt.text === 'string' && tt.text.length > 0;
  });
}

async function sha256Hex(input: string): Promise<string> {
  const buf = new TextEncoder().encode(input);
  const digest = await crypto.subtle.digest('SHA-256', buf);
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

function todayUTC(): string { return new Date().toISOString().slice(0, 10); }

function json(status: number, body: unknown, extraHeaders: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json', ...extraHeaders },
  });
}

function originAllowed(request: Request, env: Env): boolean {
  const rawAllow = (env.ALLOWED_ORIGINS ?? '').split(',').map((s) => s.trim()).filter(Boolean);
  if (rawAllow.length === 0) return true; // no allowlist configured → allow (dev)
  const origin = request.headers.get('Origin') ?? '';
  const referer = request.headers.get('Referer') ?? '';
  for (const entry of rawAllow) {
    // Support wildcard subdomains: `https://*.agentup-iag.pages.dev`
    if (entry.includes('://*.')) {
      const suffix = entry.replace('://*', '://').replace(/^https?:\/\//, '');
      try {
        const oh = origin ? new URL(origin).host : '';
        const rh = referer ? new URL(referer).host : '';
        if (oh.endsWith(suffix.replace(/^\.?/, '.')) || rh.endsWith(suffix.replace(/^\.?/, '.'))) return true;
        if (oh === suffix.replace(/^\.?/, '') || rh === suffix.replace(/^\.?/, '')) return true;
      } catch { /* fall through */ }
      continue;
    }
    if (origin === entry || referer.startsWith(entry)) return true;
  }
  return false;
}

async function checkAndBumpRateLimit(env: Env, ip: string): Promise<{ ok: boolean; count: number; limited: boolean }> {
  if (!env.AGENTUP_KV) return { ok: true, count: 0, limited: false };
  const key = 'rl:' + (await sha256Hex(ip + ':' + todayUTC()));
  const raw = await env.AGENTUP_KV.get(key);
  const current = raw ? parseInt(raw, 10) : 0;
  if (current >= RATE_LIMIT_PER_DAY) return { ok: false, count: current, limited: true };
  await env.AGENTUP_KV.put(key, String(current + 1), { expirationTtl: 24 * 60 * 60 });
  return { ok: true, count: current + 1, limited: false };
}

// --- LLM call with automatic Gemini fallback ---

interface LlmPayload {
  system: string;
  messages: Array<{ role: 'user' | 'assistant'; content: string }>;
  max_tokens: number;
}

export interface LlmResult {
  text: string;
  provider: 'anthropic' | 'gemini' | 'openrouter';
  model: string;
  inputTokens: number;
  outputTokens: number;
  latencyMs: number;
}

// Public entrypoint. Tries Anthropic Sonnet 5 first. If Anthropic returns
// the "credit balance too low" 400 or the key is missing, falls back to
// Gemini 2.5 Flash (free tier). Returns text + provider + usage so callers
// can surface cost telemetry.
export async function callLlm(env: Env, payload: LlmPayload): Promise<LlmResult> {
  const started = Date.now();
  // Provider chain: Anthropic Sonnet → Gemini free → OpenRouter free (last resort).
  if (env.ANTHROPIC_API_KEY) {
    try {
      const r = await callAnthropic(env, payload);
      return { text: r.text, provider: 'anthropic', model: MODEL, inputTokens: r.inputTokens, outputTokens: r.outputTokens, latencyMs: Date.now() - started };
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      if (!msg.includes(ANTHROPIC_NO_CREDIT_MARKER)) throw err;
      // Nothing to fall back to: surface Anthropic's own 400 rather than a
      // misleading 'no_llm_key_available' 500 (the keys exist; the balance is empty).
      if (!env.GEMINI_API_KEY && !env.OPENROUTER_API_KEY) throw err;
      // fall through to Gemini / OpenRouter
    }
  }
  if (env.GEMINI_API_KEY) {
    try {
      const r = await callGemini(env, payload);
      return { text: r.text, provider: 'gemini', model: r.model, inputTokens: r.inputTokens, outputTokens: r.outputTokens, latencyMs: Date.now() - started };
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      // Only fall through to OpenRouter on rate-limit/quota. Other errors surface.
      if (!/gemini_http_(429|503)/.test(msg) || !env.OPENROUTER_API_KEY) throw err;
    }
  }
  if (!env.OPENROUTER_API_KEY) throw new Error('no_llm_key_available');
  const r = await callOpenRouter(env, payload);
  return { text: r.text, provider: 'openrouter', model: r.model, inputTokens: r.inputTokens, outputTokens: r.outputTokens, latencyMs: Date.now() - started };
}

async function callAnthropic(env: Env, payload: LlmPayload): Promise<{ text: string; inputTokens: number; outputTokens: number }> {
  if (!env.ANTHROPIC_API_KEY) throw new Error('anthropic_key_missing');

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  let res: Response;
  try {
    res = await fetch(ANTHROPIC_API_URL, {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        'x-api-key': env.ANTHROPIC_API_KEY,
        'anthropic-version': '2023-06-01',
      },
      body: JSON.stringify({ model: MODEL, ...payload }),
      signal: controller.signal,
    });
  } finally {
    clearTimeout(timeout);
  }

  if (!res.ok) {
    const errText = await res.text();
    throw new Error(`anthropic_http_${res.status}: ${errText.slice(0, 400)}`);
  }

  const respJson = (await res.json()) as {
    content?: Array<{ type: string; text?: string }>;
    usage?: { input_tokens?: number; output_tokens?: number };
  };
  const text = respJson.content?.find((b) => b.type === 'text')?.text ?? '';
  if (!text) throw new Error('anthropic_empty_response');
  return {
    text,
    inputTokens:  respJson.usage?.input_tokens  ?? 0,
    outputTokens: respJson.usage?.output_tokens ?? 0,
  };
}

// Gemini's chat format uses `contents: [{role, parts:[{text}]}]` with role
// values 'user' | 'model' (not 'assistant'). System prompt goes into
// `systemInstruction`. Free tier: 250 req/day, 10 req/min, and frequently
// returns 503 "high demand" — we retry once with a short backoff and, if
// still 503, try a second model tier (2.5 flash-lite is less contested).
async function callGemini(env: Env, payload: LlmPayload): Promise<{ text: string; model: string; inputTokens: number; outputTokens: number }> {
  // Ordered by capacity: 2.5-flash-lite tends to be less contested than the
  // headline 2.5-flash on Google's free tier. `gemini-1.5-flash` was
  // deprecated (returns 404 on v1beta as of 2026-Q3), so we no longer chain to it.
  const models = ['gemini-2.5-flash-lite', GEMINI_MODEL];
  const backoffs = [400, 1000, 2200]; // ms — exponential
  let lastErr: Error | null = null;
  for (const model of models) {
    for (let attempt = 0; attempt < backoffs.length; attempt++) {
      try {
        const r = await callGeminiOnce(env, payload, model);
        return { ...r, model };
      } catch (err) {
        lastErr = err instanceof Error ? err : new Error(String(err));
        const msg = lastErr.message;
        if (!/gemini_http_(503|429)/.test(msg)) throw lastErr;
        if (attempt < backoffs.length - 1) await new Promise((r) => setTimeout(r, backoffs[attempt]));
      }
    }
  }
  throw lastErr ?? new Error('gemini_all_models_failed');
}

async function callGeminiOnce(env: Env, payload: LlmPayload, model: string): Promise<{ text: string; inputTokens: number; outputTokens: number }> {
  const url = `${GEMINI_API_URL}/${model}:generateContent?key=${env.GEMINI_API_KEY}`;
  const contents = payload.messages.map((m) => ({
    role: m.role === 'assistant' ? 'model' : 'user',
    parts: [{ text: m.content }],
  }));
  const body = {
    systemInstruction: { parts: [{ text: payload.system }] },
    contents,
    generationConfig: {
      // Gemini 2.5 counts "thinking" tokens against the same budget as output
      // tokens. Give it 2× headroom, and disable thinking on Flash so the full
      // budget goes to visible output.
      maxOutputTokens: Math.max(payload.max_tokens * 2, 1200),
      temperature: 0.7,
      thinkingConfig: { thinkingBudget: 0 },
    },
  };

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  let res: Response;
  try {
    res = await fetch(url, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
  } finally {
    clearTimeout(timeout);
  }

  if (!res.ok) {
    const errText = await res.text();
    throw new Error(`gemini_http_${res.status}: ${errText.slice(0, 400)}`);
  }

  const respJson = (await res.json()) as {
    candidates?: Array<{ content?: { parts?: Array<{ text?: string }> } }>;
    usageMetadata?: { promptTokenCount?: number; candidatesTokenCount?: number };
  };
  const text = respJson.candidates?.[0]?.content?.parts?.map((p) => p.text ?? '').join('') ?? '';
  if (!text) throw new Error('gemini_empty_response');
  return {
    text,
    inputTokens:  respJson.usageMetadata?.promptTokenCount     ?? 0,
    outputTokens: respJson.usageMetadata?.candidatesTokenCount ?? 0,
  };
}

// OpenRouter (OpenAI-compatible) — last-resort fallback when both Anthropic
// and Gemini are unavailable. Free-tier models rate-limit heavily; we try
// them in order until one accepts. Same JSON output validation applies.
async function callOpenRouter(env: Env, payload: LlmPayload): Promise<{ text: string; model: string; inputTokens: number; outputTokens: number }> {
  let lastErr: Error | null = null;
  for (const model of OPENROUTER_FREE_MODELS) {
    try {
      return { ...(await callOpenRouterOnce(env, payload, model)), model };
    } catch (err) {
      lastErr = err instanceof Error ? err : new Error(String(err));
      // Try next free model on any failure.
    }
  }
  throw lastErr ?? new Error('openrouter_all_models_failed');
}

async function callOpenRouterOnce(env: Env, payload: LlmPayload, model: string): Promise<{ text: string; inputTokens: number; outputTokens: number }> {
  const messages = [
    { role: 'system', content: payload.system },
    ...payload.messages,
  ];
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  let res: Response;
  try {
    res = await fetch(OPENROUTER_API_URL, {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        'authorization': `Bearer ${env.OPENROUTER_API_KEY}`,
        // OpenRouter recommends these for attribution / rate-limit tiers.
        'HTTP-Referer': 'https://agentup-iag.pages.dev',
        'X-Title': 'AgentUp',
      },
      body: JSON.stringify({
        model,
        messages,
        max_tokens: payload.max_tokens,
        temperature: 0.7,
      }),
      signal: controller.signal,
    });
  } finally {
    clearTimeout(timeout);
  }
  if (!res.ok) {
    const errText = await res.text();
    throw new Error(`openrouter_http_${res.status}: ${errText.slice(0, 400)}`);
  }
  const respJson = (await res.json()) as {
    choices?: Array<{ message?: { content?: string } }>;
    usage?: { prompt_tokens?: number; completion_tokens?: number };
  };
  const text = respJson.choices?.[0]?.message?.content ?? '';
  if (!text) throw new Error('openrouter_empty_response');
  return {
    text,
    inputTokens:  respJson.usage?.prompt_tokens     ?? 0,
    outputTokens: respJson.usage?.completion_tokens ?? 0,
  };
}

// --- Mode handlers ---

function buildRoleplayMessages(req: RoleplayRequest): Array<{ role: 'user' | 'assistant'; content: string }> {
  // The customer's opening message anchors the conversation. Every subsequent
  // turn alternates agent (user) → customer (assistant).
  // We inject the opening as the first `assistant` message so Claude continues
  // the customer's role from that anchor.
  const messages: Array<{ role: 'user' | 'assistant'; content: string }> = [
    { role: 'user',      content: '(scenario begins)' },
    { role: 'assistant', content: req.opening },
  ];
  for (const t of req.history) {
    messages.push({ role: t.role === 'agent' ? 'user' : 'assistant', content: t.text });
  }
  // The last message MUST be a `user` (agent) turn awaiting the customer's reply.
  if (messages[messages.length - 1].role !== 'user') {
    throw new Error('roleplay_history_must_end_with_agent_turn');
  }
  return messages;
}

function usageMeta(r: { provider: string; model: string; inputTokens: number; outputTokens: number; latencyMs: number }) {
  return { provider: r.provider, model: r.model, inputTokens: r.inputTokens, outputTokens: r.outputTokens, latencyMs: r.latencyMs };
}

async function handleRoleplay(env: Env, req: RoleplayRequest): Promise<Response> {
  const scenarioBlock = `Customer scenario: ${req.scenario}\nDifficulty: ${req.difficulty}`;
  const r = await callLlm(env, {
    system: ROLEPLAY_SYSTEM_PROMPT + '\n\n' + scenarioBlock,
    messages: buildRoleplayMessages(req),
    max_tokens: 220, // ≤75 words × ~3 tokens/word + small buffer
  });
  return json(200, { text: r.text.trim(), provider: r.provider, _usage: usageMeta(r) });
}

// Streaming variant. Uses Anthropic's SSE `stream: true` to emit incremental
// text chunks so the client can render tokens live AND pipe complete phrases
// to `SpeechSynthesisUtterance` for sub-second time-to-first-audio on the
// Call channel. Falls back to non-streaming callLlm if Anthropic isn't
// available (Gemini fallback path — sends one final chunk).
//
// Wire format (SSE):
//   event: chunk    data: {"text":"<delta>","provider":"anthropic"}
//   event: done     data: {"provider":"anthropic","model":"claude-sonnet-5","inputTokens":1234,"outputTokens":50,"latencyMs":812}
//   event: error    data: {"message":"..."}
async function handleRoleplayStream(env: Env, req: RoleplayRequest): Promise<Response> {
  const scenarioBlock = `Customer scenario: ${req.scenario}\nDifficulty: ${req.difficulty}`;
  const payload = {
    system: ROLEPLAY_SYSTEM_PROMPT + '\n\n' + scenarioBlock,
    messages: buildRoleplayMessages(req),
    max_tokens: 220,
  };

  const { readable, writable } = new TransformStream();
  const writer = writable.getWriter();
  const encoder = new TextEncoder();
  const writeSSE = async (event: string, data: unknown) => {
    await writer.write(encoder.encode(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`));
  };

  const streamHeaders = {
    'content-type': 'text/event-stream; charset=utf-8',
    'cache-control': 'no-cache, no-transform',
    'x-accel-buffering': 'no',
  };

  // Kick off in the background so the Response can return immediately.
  (async () => {
    const started = Date.now();
    try {
      if (env.ANTHROPIC_API_KEY) {
        // Try Anthropic streaming. On credit-too-low, fall back to Gemini one-shot.
        try {
          const usage = await streamAnthropicRoleplay(env, payload, async (delta) => writeSSE('chunk', { text: delta, provider: 'anthropic' }));
          await writeSSE('done', { provider: 'anthropic', model: MODEL, inputTokens: usage.inputTokens, outputTokens: usage.outputTokens, latencyMs: Date.now() - started });
          await writer.close();
          return;
        } catch (err) {
          const msg = err instanceof Error ? err.message : String(err);
          if (!msg.includes(ANTHROPIC_NO_CREDIT_MARKER) || !env.GEMINI_API_KEY) {
            await writeSSE('error', { message: msg.slice(0, 400) });
            await writer.close();
            return;
          }
        }
      }
      // Fallback path — Gemini/OpenRouter don't stream in this build; emit as one chunk.
      let fallbackProvider: 'gemini' | 'openrouter' = 'gemini';
      let r: { text: string; model: string; inputTokens: number; outputTokens: number };
      try {
        r = await callGemini(env, payload);
      } catch (gErr) {
        if (!env.OPENROUTER_API_KEY) throw gErr;
        r = await callOpenRouter(env, payload);
        fallbackProvider = 'openrouter';
      }
      await writeSSE('chunk', { text: r.text, provider: fallbackProvider });
      await writeSSE('done', { provider: fallbackProvider, model: r.model, inputTokens: r.inputTokens, outputTokens: r.outputTokens, latencyMs: Date.now() - started });
      await writer.close();
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      await writeSSE('error', { message: msg.slice(0, 400) });
      await writer.close();
    }
  })();

  return new Response(readable, { status: 200, headers: streamHeaders });
}

// Consume Anthropic's SSE and forward text deltas via `onDelta`.
// Returns final usage tokens.
async function streamAnthropicRoleplay(
  env: Env,
  payload: LlmPayload,
  onDelta: (text: string) => Promise<void>,
): Promise<{ inputTokens: number; outputTokens: number }> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  let res: Response;
  try {
    res = await fetch(ANTHROPIC_API_URL, {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        'x-api-key': env.ANTHROPIC_API_KEY!,
        'anthropic-version': '2023-06-01',
      },
      body: JSON.stringify({ model: MODEL, stream: true, ...payload }),
      signal: controller.signal,
    });
  } finally {
    clearTimeout(timeout);
  }

  if (!res.ok || !res.body) {
    const errText = await res.text();
    throw new Error(`anthropic_http_${res.status}: ${errText.slice(0, 400)}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let inputTokens = 0;
  let outputTokens = 0;

  // SSE frames are separated by \n\n. Each frame has "event: X\ndata: {...}".
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let idx: number;
    while ((idx = buffer.indexOf('\n\n')) !== -1) {
      const frame = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      if (!frame.trim()) continue;
      // Extract data: line(s). Ignore event: type; we key on payload's `type` field.
      const dataLine = frame.split('\n').find((l) => l.startsWith('data:'));
      if (!dataLine) continue;
      const jsonText = dataLine.slice(5).trim();
      if (!jsonText || jsonText === '[DONE]') continue;
      try {
        const evt = JSON.parse(jsonText) as {
          type?: string;
          delta?: { type?: string; text?: string };
          usage?: { input_tokens?: number; output_tokens?: number };
          message?: { usage?: { input_tokens?: number; output_tokens?: number } };
        };
        if (evt.type === 'content_block_delta' && evt.delta?.type === 'text_delta' && evt.delta.text) {
          await onDelta(evt.delta.text);
        }
        if (evt.type === 'message_start' && evt.message?.usage) {
          inputTokens  = evt.message.usage.input_tokens  ?? inputTokens;
          outputTokens = evt.message.usage.output_tokens ?? outputTokens;
        }
        if (evt.type === 'message_delta' && evt.usage) {
          if (evt.usage.output_tokens != null) outputTokens = evt.usage.output_tokens;
        }
      } catch { /* malformed SSE line — skip */ }
    }
  }

  return { inputTokens, outputTokens };
}

async function handleModelAnswer(env: Env, req: ModelAnswerRequest): Promise<Response> {
  const userMessage = `Scenario: ${req.scenario}\nDifficulty: ${req.difficulty}\nCustomer opening: "${req.opening}"\n\nProduce the ideal 5-turn transcript now.`;
  const r = await callLlm(env, {
    system: MODEL_ANSWER_SYSTEM_PROMPT,
    messages: [{ role: 'user', content: userMessage }],
    max_tokens: 900,
  });
  const parsed = extractJsonObject(r.text);
  if (!isModelAnswer(parsed)) {
    return json(502, { error: 'model_answer_shape_mismatch', provider: r.provider, raw: r.text.slice(0, 300) });
  }
  return json(200, { ...parsed, _provider: r.provider, _usage: usageMeta(r) });
}

async function handleScore(env: Env, req: ScoreRequest): Promise<Response> {
  const transcriptText = req.transcript
    .map((t, i) => `Turn ${Math.floor(i / 2) + 1} — ${t.role === 'agent' ? 'Agent' : 'Customer'}: ${t.text}`)
    .join('\n');
  const userMessage = `Scenario: ${req.scenario}\nDifficulty: ${req.difficulty}\n\nTranscript:\n${transcriptText}\n\nReturn the JSON scorecard now.`;
  const r = await callLlm(env, {
    system: SCORING_SYSTEM_PROMPT,
    messages: [{ role: 'user', content: userMessage }],
    max_tokens: 600,
  });
  const parsed = extractJsonObject(r.text);
  if (!isScorecard(parsed)) {
    return json(502, { error: 'scorecard_shape_mismatch', provider: r.provider, raw: r.text.slice(0, 300) });
  }
  return json(200, { ...parsed, _provider: r.provider, _usage: usageMeta(r) });
}

// --- Router ---

export const onRequestPost: PagesFunction<Env> = async ({ request, env }) => {
  if (!originAllowed(request, env)) return json(403, { error: 'origin_not_allowed' });

  const ip = request.headers.get('CF-Connecting-IP') || request.headers.get('X-Real-IP') || '0.0.0.0';
  const rl = await checkAndBumpRateLimit(env, ip);
  if (!rl.ok) return json(429, { error: 'rate_limit_exceeded', limit_per_day: RATE_LIMIT_PER_DAY });

  // Enforce payload size cap BEFORE parsing — avoids spending memory + upstream
  // tokens on abusive inputs. Prefer Content-Length; fall back to a raw text
  // read (still bounded because Workers cap body size at ~100MB anyway).
  const contentLen = parseInt(request.headers.get('content-length') ?? '0', 10);
  if (Number.isFinite(contentLen) && contentLen > MAX_BODY_BYTES) {
    return json(413, { error: 'payload_too_large', max_bytes: MAX_BODY_BYTES });
  }
  const rawBody = await request.text();
  if (rawBody.length > MAX_BODY_BYTES) {
    return json(413, { error: 'payload_too_large', max_bytes: MAX_BODY_BYTES });
  }
  let body: unknown;
  try { body = rawBody ? JSON.parse(rawBody) : null; }
  catch { return json(400, { error: 'invalid_json_body' }); }

  const req = body as Partial<RoleplayRequest & ScoreRequest & ModelAnswerRequest>;
  if (!req || (req.mode !== 'roleplay' && req.mode !== 'score' && req.mode !== 'model-answer')) {
    return json(400, { error: 'invalid_mode', expected: ['roleplay', 'score', 'model-answer'] });
  }

  try {
    if (req.mode === 'roleplay') {
      if (!req.scenario || !req.opening || !req.difficulty || !Array.isArray(req.history)) {
        return json(400, { error: 'roleplay_missing_fields' });
      }
      if (req.stream === true) return await handleRoleplayStream(env, req as RoleplayRequest);
      return await handleRoleplay(env, req as RoleplayRequest);
    }
    if (req.mode === 'model-answer') {
      if (!req.scenario || !req.opening || !req.difficulty) {
        return json(400, { error: 'model_answer_missing_fields' });
      }
      return await handleModelAnswer(env, req as ModelAnswerRequest);
    }
    if (!req.scenario || !req.difficulty || !Array.isArray(req.transcript) || req.transcript.length === 0) {
      return json(400, { error: 'score_missing_fields' });
    }
    return await handleScore(env, req as ScoreRequest);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    const status = msg.startsWith('anthropic_http_429') || msg.startsWith('gemini_http_429') ? 429 :
                   msg.startsWith('anthropic_http_4') || msg.startsWith('gemini_http_4') ? 400 :
                   msg === 'anthropic_key_missing' || msg === 'no_llm_key_available' ? 500 :
                   502;
    return json(status, { error: 'upstream_failure', detail: msg.slice(0, 300) });
  }
};

// GET returns a health hint (useful for the front-door synthetic).
export const onRequestGet: PagesFunction<Env> = async ({ env }) => {
  return json(200, {
    ok: true,
    primary_model: MODEL,
    fallback_model: GEMINI_MODEL,
    anthropic_key_present: Boolean(env.ANTHROPIC_API_KEY),
    gemini_key_present:    Boolean(env.GEMINI_API_KEY),
    key_present: Boolean(env.ANTHROPIC_API_KEY || env.GEMINI_API_KEY),
    kv_bound: Boolean(env.AGENTUP_KV),
    rate_limit_per_day: RATE_LIMIT_PER_DAY,
  });
};
