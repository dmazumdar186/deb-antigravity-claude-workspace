// Developer overlay panel — Ctrl+` (or Cmd+`) to toggle.
//
// Purpose: expose the "under the hood" mechanics that make AgentUp work,
// in the spirit of "if you built it, you should be able to inspect it."
// This is a demoable artefact: opens in <1s, shows real numbers, no fake data.

import { useEffect, useState } from 'react';
import { getAllEvents, subscribe, rollup, clearTelemetry } from '../lib/telemetry';
import type { CallEvent } from '../lib/telemetry';

const HOTKEY_HINT = 'Ctrl+`';

export default function DevHUD() {
  const [open, setOpen] = useState(false);
  const [events, setEvents] = useState<CallEvent[]>([]);
  const [tab, setTab] = useState<'events' | 'rollup' | 'prompts'>('events');

  useEffect(() => {
    setEvents(getAllEvents());
    const unsub = subscribe(setEvents);
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === '`') {
        e.preventDefault();
        setOpen((v) => !v);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => { unsub(); window.removeEventListener('keydown', onKey); };
  }, []);

  return (
    <>
      {/* Tiny corner tab so the interviewer knows the panel exists. */}
      <button
        type="button"
        aria-label={`Open developer HUD (${HOTKEY_HINT})`}
        onClick={() => setOpen((v) => !v)}
        className="fixed bottom-3 right-3 z-40 rounded-md border border-ink-700/60 bg-ink-900/85 px-2.5 py-1 text-[10px] font-mono font-semibold text-emerald-400 shadow-lg backdrop-blur-sm hover:bg-ink-900 transition"
        data-testid="hud-toggle"
      >
        {open ? '▼' : '▲'} DEV · {HOTKEY_HINT}
      </button>

      {open && (
        <aside
          role="complementary"
          aria-label="Developer HUD"
          data-testid="hud-panel"
          className="fixed bottom-14 right-3 z-40 w-[min(95vw,560px)] max-h-[70vh] overflow-hidden rounded-xl border border-ink-700/70 bg-ink-950/95 text-ink-100 shadow-2xl backdrop-blur-md flex flex-col font-mono text-xs animate-slide-up"
        >
          <header className="flex items-center justify-between border-b border-ink-700/60 px-3 py-2">
            <div className="flex items-center gap-2">
              <span className="inline-flex h-2 w-2 rounded-full bg-emerald-400 animate-pulse-soft" />
              <strong className="text-emerald-400">AgentUp DEV HUD</strong>
              <span className="text-ink-500">· live</span>
            </div>
            <div className="flex items-center gap-1">
              <button onClick={() => { clearTelemetry(); }} className="rounded px-2 py-0.5 text-[10px] text-ink-400 hover:bg-ink-800 hover:text-white transition">clear</button>
              <button onClick={() => setOpen(false)} className="rounded px-2 py-0.5 text-[10px] text-ink-400 hover:bg-ink-800 hover:text-white transition" aria-label="Close">✕</button>
            </div>
          </header>

          <nav className="flex border-b border-ink-700/60 text-[11px]">
            {(['events', 'rollup', 'prompts'] as const).map((k) => (
              <button
                key={k}
                onClick={() => setTab(k)}
                className={`flex-1 px-3 py-1.5 uppercase tracking-wider transition ${tab === k ? 'bg-ink-800 text-emerald-400 font-semibold' : 'text-ink-400 hover:text-white'}`}
              >{k}</button>
            ))}
          </nav>

          <div className="flex-1 overflow-y-auto p-3">
            {tab === 'events'  && <EventsTab events={events} />}
            {tab === 'rollup'  && <RollupTab />}
            {tab === 'prompts' && <PromptsTab />}
          </div>
        </aside>
      )}
    </>
  );
}

function EventsTab({ events }: { events: CallEvent[] }) {
  const recent = events.slice(-15).reverse();
  if (recent.length === 0) return <div className="text-ink-500">No API calls yet. Complete a training turn to populate.</div>;
  return (
    <div className="space-y-1.5">
      {recent.map((e, i) => (
        <div key={i} className="rounded px-2 py-1.5 hover:bg-ink-900/50 transition">
          <div className="flex items-baseline gap-2">
            <span aria-hidden="true" className={`inline-block h-1.5 w-1.5 rounded-full ${e.ok ? 'bg-emerald-400' : 'bg-rose-400'}`} />
            <span className={e.ok ? 'text-ink-100 font-semibold uppercase' : 'text-rose-300 font-semibold uppercase'}>{e.mode}</span>
            <span className="text-ink-400">{e.provider}</span>
            <span className="ml-auto text-ink-500 tabular-nums">{e.latencyMs}ms</span>
          </div>
          <div className="pl-3.5 text-[10px] text-ink-500 tabular-nums">
            in {e.inputTokens.toLocaleString()}tok · out {e.outputTokens.toLocaleString()}tok · €{e.costEur.toFixed(6)}
            {e.errorCode && <span className="text-rose-300 ml-2">error: {e.errorCode}</span>}
          </div>
        </div>
      ))}
    </div>
  );
}

function RollupTab() {
  const r = rollup();
  const Row = ({ k, v }: { k: string; v: string }) => (
    <div className="flex justify-between border-b border-ink-800/60 py-1">
      <span className="text-ink-400">{k}</span>
      <span className="text-emerald-400 tabular-nums">{v}</span>
    </div>
  );
  return (
    <div className="space-y-3">
      <section>
        <h4 className="mb-1 text-[10px] uppercase tracking-wider text-ink-500">Aggregate</h4>
        <Row k="calls (session)"   v={String(r.totalCalls)} />
        <Row k="total cost"         v={`€${r.totalCostEur.toFixed(5)}`} />
        <Row k="tokens in / out"    v={`${r.totalTokensIn.toLocaleString()} / ${r.totalTokensOut.toLocaleString()}`} />
        <Row k="p50 latency"        v={`${r.p50LatencyMs}ms`} />
        <Row k="p95 latency"        v={`${r.p95LatencyMs}ms`} />
      </section>
      <section>
        <h4 className="mb-1 text-[10px] uppercase tracking-wider text-ink-500">By provider</h4>
        <Row k="anthropic — calls" v={String(r.byProvider.anthropic.calls)} />
        <Row k="anthropic — cost"  v={`€${r.byProvider.anthropic.costEur.toFixed(5)}`} />
        <Row k="gemini — calls"    v={String(r.byProvider.gemini.calls)} />
        <Row k="gemini — cost"     v={`€${r.byProvider.gemini.costEur.toFixed(5)}`} />
      </section>
      <section>
        <h4 className="mb-1 text-[10px] uppercase tracking-wider text-ink-500">Projected</h4>
        <Row k="€ per session (est.)"          v={`€${r.perSessionEur.toFixed(4)}`} />
        <Row k="€ per agent / month (30/mo)"   v={`€${r.perMonthEur.toFixed(2)}`} />
      </section>
    </div>
  );
}

function PromptsTab() {
  return (
    <div className="space-y-3">
      <section>
        <h4 className="mb-1 text-[10px] uppercase tracking-wider text-ink-500">Active provider chain</h4>
        <ol className="list-decimal list-inside space-y-0.5 text-ink-300">
          <li>Anthropic Claude Sonnet 4.6 (primary)</li>
          <li className="text-ink-500">Gemini 2.5 Flash-Lite (fallback #1)</li>
          <li className="text-ink-500">Gemini 2.5 Flash (fallback #2)</li>
          <li className="text-ink-500">Gemini 1.5 Flash (fallback #3)</li>
        </ol>
        <p className="mt-1 text-[10px] text-ink-500">Fallback triggers: Anthropic <code>credit balance too low</code> (400) → Gemini chain; Gemini 503/429 → next model.</p>
      </section>
      <section>
        <h4 className="mb-1 text-[10px] uppercase tracking-wider text-ink-500">Roleplay system prompt (summary)</h4>
        <pre className="whitespace-pre-wrap rounded bg-ink-900/70 p-2 text-[10px] leading-relaxed text-ink-300">
{`Play a customer in a training simulation.
Stay strictly in character. Never reveal you're an AI.
Tone by difficulty:
  Beginner     → polite, patient, cooperative
  Intermediate → moderately frustrated, seeks structure
  Advanced     → angry, skeptical, adversarial
Never offer solutions yourself.
Responses < 75 words. No stage directions.`}
        </pre>
      </section>
      <section>
        <h4 className="mb-1 text-[10px] uppercase tracking-wider text-ink-500">Scoring system prompt (summary)</h4>
        <pre className="whitespace-pre-wrap rounded bg-ink-900/70 p-2 text-[10px] leading-relaxed text-ink-300">
{`Grade the transcript on 4 dimensions (25% each):
  empathyScore, accuracyScore, resolutionScore, professionalismScore.
Output ONLY strict JSON — no markdown fences, no prose.
Include overallScore (weighted avg), strength, improvement.
Do not inflate scores; a mediocre reply earns 60-70.`}
        </pre>
      </section>
      <section>
        <h4 className="mb-1 text-[10px] uppercase tracking-wider text-ink-500">Client-side safety</h4>
        <ul className="list-disc list-inside space-y-0.5 text-ink-300">
          <li>PII redaction (Aadhaar / PAN / mobile / UPI / card / email)</li>
          <li>Payload cap: 32KB (server rejects with 413)</li>
          <li>Origin allowlist: <code>*.agentup-iag.pages.dev</code> + localhost</li>
          <li>Per-IP rate limit: 200 calls / day (KV)</li>
        </ul>
      </section>
    </div>
  );
}
