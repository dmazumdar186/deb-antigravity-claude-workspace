// In-browser telemetry store used by the Dev HUD and the cost tile on the
// dashboard. Kept small and pure — no side-effects outside a bounded array
// in memory + a persisted rolling window in localStorage.
//
// Pricing (EUR, per million tokens — 2026 workspace convention).
// Anthropic Sonnet 4.6 : $3 in / $15 out → €2.76 in / €13.80 out at 0.92
// Gemini 2.5 flash-lite: free tier (€0)
// Numbers are illustrative — real invoice takes precedence. Change here in one place.

const USD_TO_EUR = 0.92;

export const PRICING_EUR_PER_MTOK: Record<string, { in: number; out: number }> = {
  'claude-sonnet-5':      { in: 2 * USD_TO_EUR, out: 10 * USD_TO_EUR },
  'claude-sonnet-4-6':    { in: 3 * USD_TO_EUR, out: 15 * USD_TO_EUR },
  'gemini-2.5-flash':     { in: 0, out: 0 },
  'gemini-2.5-flash-lite': { in: 0, out: 0 },
  'gemini-1.5-flash':     { in: 0, out: 0 },
};

export type Provider = 'anthropic' | 'gemini' | 'unknown';

export interface CallEvent {
  ts: number;               // Date.now()
  mode: 'roleplay' | 'score' | 'model-answer';
  provider: Provider;
  latencyMs: number;
  inputTokens: number;
  outputTokens: number;
  costEur: number;
  pageUrl?: string;
  ok: boolean;
  errorCode?: string;
}

const STORAGE_KEY = 'agentup:telemetry:v1';
const MAX_EVENTS  = 200; // rolling window

type Listener = (events: CallEvent[]) => void;
const listeners = new Set<Listener>();

let inMem: CallEvent[] = [];
let loaded = false;

function load(): CallEvent[] {
  if (loaded) return inMem;
  loaded = true;
  if (typeof localStorage === 'undefined') return inMem;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) inMem = JSON.parse(raw) as CallEvent[];
  } catch { inMem = []; }
  return inMem;
}

function persist(): void {
  if (typeof localStorage === 'undefined') return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(inMem.slice(-MAX_EVENTS)));
  } catch { /* quota */ }
}

export function recordCall(ev: Omit<CallEvent, 'ts'> & { ts?: number }): CallEvent {
  const full: CallEvent = { ts: Date.now(), ...ev };
  load();
  inMem = [...inMem, full].slice(-MAX_EVENTS);
  persist();
  for (const l of listeners) l(inMem);
  return full;
}

export function getAllEvents(): CallEvent[] { return load().slice(); }

export function subscribe(fn: Listener): () => void {
  listeners.add(fn);
  return () => { listeners.delete(fn); };
}

export function clearTelemetry(): void {
  inMem = [];
  persist();
  for (const l of listeners) l(inMem);
}

// --- Cost math ---

export function estimateCostEur(provider: Provider, model: string | undefined, inputTokens: number, outputTokens: number): number {
  const p = model && PRICING_EUR_PER_MTOK[model];
  if (!p) return 0;
  return (inputTokens / 1_000_000) * p.in + (outputTokens / 1_000_000) * p.out;
}

// --- Rollups for the dashboard tile ---

export interface CostRollup {
  totalCalls: number;
  totalCostEur: number;
  totalTokensIn: number;
  totalTokensOut: number;
  byProvider: Record<Provider, { calls: number; costEur: number; tokensIn: number; tokensOut: number }>;
  perSessionEur: number;      // avg € / session (heuristic: 4 calls/session)
  perMonthEur: number;        // projected — 30 sessions per agent per month
  p50LatencyMs: number;
  p95LatencyMs: number;
}

export function rollup(events?: CallEvent[]): CostRollup {
  const evs = events ?? getAllEvents();
  const byProvider: CostRollup['byProvider'] = {
    anthropic: { calls: 0, costEur: 0, tokensIn: 0, tokensOut: 0 },
    gemini:    { calls: 0, costEur: 0, tokensIn: 0, tokensOut: 0 },
    unknown:   { calls: 0, costEur: 0, tokensIn: 0, tokensOut: 0 },
  };
  let totalCostEur = 0, totalTokensIn = 0, totalTokensOut = 0;
  const latencies: number[] = [];
  for (const e of evs) {
    const bp = byProvider[e.provider] ?? byProvider.unknown;
    bp.calls++;
    bp.costEur     += e.costEur;
    bp.tokensIn    += e.inputTokens;
    bp.tokensOut   += e.outputTokens;
    totalCostEur   += e.costEur;
    totalTokensIn  += e.inputTokens;
    totalTokensOut += e.outputTokens;
    if (e.ok && e.latencyMs > 0) latencies.push(e.latencyMs);
  }
  latencies.sort((a, b) => a - b);
  const pct = (p: number): number => latencies.length === 0 ? 0 : latencies[Math.min(latencies.length - 1, Math.floor(latencies.length * p))];
  const p50 = pct(0.5);
  const p95 = pct(0.95);
  const totalCalls = evs.length;
  // Session = 4 calls (3 roleplay + 1 score, per case × 3 cases ≈ 15 calls, but
  // amortising for realistic ~7 min sessions we use 15 as a conservative mean).
  const CALLS_PER_SESSION = 15;
  const perSessionEur = totalCalls > 0 ? (totalCostEur / totalCalls) * CALLS_PER_SESSION : 0;
  const perMonthEur   = perSessionEur * 30;
  return {
    totalCalls, totalCostEur, totalTokensIn, totalTokensOut, byProvider,
    perSessionEur, perMonthEur, p50LatencyMs: p50, p95LatencyMs: p95,
  };
}
