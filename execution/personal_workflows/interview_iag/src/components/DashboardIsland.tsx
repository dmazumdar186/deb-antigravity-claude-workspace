import { useEffect, useState } from 'react';
import {
  LineChart, Line, ResponsiveContainer, XAxis, YAxis, Tooltip, CartesianGrid,
  BarChart, Bar, Cell,
} from 'recharts';
import { loadState } from '../lib/storage';
import { daily30, groupByKey, summaryStats, todayUTC } from '../lib/session';
import { rollup as costRollup } from '../lib/telemetry';
import type { AppState, CompletedCase } from '../lib/types';

export default function DashboardIsland() {
  const [state, setState] = useState<AppState | null>(null);
  useEffect(() => { setState(loadState()); }, []);
  if (!state) return <div className="card p-8 text-ink-500">Loading…</div>;

  const stats = summaryStats(state);
  const timeline = daily30(state.sessions, todayUTC());
  const byTopic   = groupByKey(state.sessions, (c) => c.topic);
  const byChannel = groupByKey(state.sessions, (c) => c.channel);

  const empty = state.sessions.length === 0;

  if (empty) {
    return (
      <div className="card p-10 text-center animate-fade-in" data-testid="dashboard-empty">
        <div className="mx-auto h-16 w-16 rounded-full bg-ink-100 dark:bg-ink-800 flex items-center justify-center text-3xl">📊</div>
        <h2 className="mt-4 font-display text-xl font-semibold">No sessions yet</h2>
        <p className="mt-2 text-sm text-ink-500 max-w-md mx-auto">
          Complete your first daily training session and your streak, score trend, and
          skill breakdown will appear here.
        </p>
        <a href="/" className="mt-6 inline-flex btn-primary">Start today’s session →</a>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in" data-testid="dashboard-loaded">
      {/* KPI row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Current streak"   value={String(stats.streak)}          hint={stats.streak === 1 ? 'day' : 'days'} accent="emerald" icon="🔥" />
        <StatCard label="Sessions this wk" value={String(stats.sessionsThisWeek)} hint={`of ${stats.totalSessions} total`} accent="indigo" icon="📚" />
        <StatCard label="Top skill"        value={stats.topSkill?.label ?? '—'}    hint={stats.topSkill ? `${stats.topSkill.score}/100` : ''} accent="emerald" icon="✨" />
        <StatCard label="Focus on"         value={stats.weakSkill?.label ?? '—'}   hint={stats.weakSkill ? `${stats.weakSkill.score}/100` : ''} accent="amber" icon="🎯" />
      </div>

      {/* Timeline */}
      <div className="card p-5">
        <div className="flex items-baseline justify-between mb-3">
          <h3 className="font-display text-lg font-semibold">Score over time</h3>
          <span className="text-xs text-ink-500">Last 30 days · daily average</span>
        </div>
        <div style={{ width: '100%', height: 220 }}>
          <ResponsiveContainer>
            <LineChart data={timeline} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="currentColor" className="text-ink-200 dark:text-ink-800" />
              <XAxis dataKey="date" tickFormatter={(d) => d.slice(5)} tick={{ fontSize: 11 }} stroke="currentColor" className="text-ink-500" />
              <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} stroke="currentColor" className="text-ink-500" />
              <Tooltip contentStyle={{ background: '#0A0B10', border: '1px solid #3A3D48', borderRadius: 8, fontSize: 12, color: '#fff' }} formatter={(v: number) => v === 0 ? '—' : `${v}/100`} labelFormatter={(l) => `Day ${l}`} />
              <Line type="monotone" dataKey="score" stroke="#10B981" strokeWidth={2.5} dot={{ r: 3, strokeWidth: 0, fill: '#10B981' }} isAnimationActive={true} animationDuration={600} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Bar charts side-by-side */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <BreakdownCard title="By topic"   data={byTopic}   />
        <BreakdownCard title="By channel" data={byChannel} />
      </div>

      {/* Cost + telemetry surface */}
      <CostTile />

      {/* Recent sessions */}
      <div className="card overflow-hidden">
        <h3 className="font-display text-lg font-semibold px-5 pt-4">Recent sessions</h3>
        <div className="overflow-x-auto mt-2">
          <table className="w-full text-left text-sm">
            <thead className="bg-ink-100 dark:bg-ink-900 text-ink-600 dark:text-ink-300 text-xs uppercase tracking-wide">
              <tr>
                <th className="px-5 py-3">Date</th>
                <th className="px-5 py-3">Cases</th>
                <th className="px-5 py-3">Average</th>
                <th className="px-5 py-3">Detail</th>
              </tr>
            </thead>
            <tbody data-testid="sessions-list">
              {state.sessions.slice(0, 10).map((s) => (
                <tr key={s.id} className="border-t border-ink-200/60 dark:border-ink-700/60">
                  <td className="px-5 py-3 tabular-nums">{s.date}</td>
                  <td className="px-5 py-3 text-ink-600 dark:text-ink-300">{s.cases.length}</td>
                  <td className="px-5 py-3">
                    <ScorePill score={s.averageScore} />
                  </td>
                  <td className="px-5 py-3 text-ink-500 text-xs max-w-xl truncate">
                    {s.cases.map((c: CompletedCase) => c.caseTitle).join(' · ')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function StatCard(props: { label: string; value: string; hint?: string; accent: 'emerald' | 'indigo' | 'amber' | 'rose'; icon: string }) {
  const accentMap = {
    emerald: 'text-emerald-600 dark:text-emerald-400',
    indigo:  'text-indigo-600  dark:text-indigo-400',
    amber:   'text-amber-600   dark:text-amber-400',
    rose:    'text-rose-600    dark:text-rose-400',
  } as const;
  return (
    <div className="card p-4">
      <div className="flex items-center justify-between">
        <div className="text-xs font-semibold uppercase tracking-wider text-ink-500">{props.label}</div>
        <span aria-hidden="true" className="text-lg opacity-80">{props.icon}</span>
      </div>
      <div className={`mt-2 font-display text-2xl font-semibold ${accentMap[props.accent]}`}>{props.value}</div>
      {props.hint && <div className="text-xs text-ink-500 mt-0.5">{props.hint}</div>}
    </div>
  );
}

function BreakdownCard(props: { title: string; data: { key: string; score: number; count: number }[] }) {
  return (
    <div className="card p-5">
      <h3 className="font-display text-lg font-semibold mb-3">{props.title}</h3>
      {props.data.length === 0 ? (
        <div className="text-sm text-ink-500 py-8 text-center">No data yet.</div>
      ) : (
        <div style={{ width: '100%', height: 200 }}>
          <ResponsiveContainer>
            <BarChart data={props.data} layout="vertical" margin={{ top: 4, right: 12, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="currentColor" className="text-ink-200 dark:text-ink-800" />
              <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11 }} stroke="currentColor" className="text-ink-500" />
              <YAxis type="category" dataKey="key" width={110} tick={{ fontSize: 11 }} stroke="currentColor" className="text-ink-500" />
              <Tooltip contentStyle={{ background: '#0A0B10', border: '1px solid #3A3D48', borderRadius: 8, fontSize: 12, color: '#fff' }} formatter={(v: number) => `${v}/100`} />
              <Bar dataKey="score" radius={[0, 6, 6, 0]}>
                {props.data.map((d, i) => (
                  <Cell key={i} fill={d.score >= 80 ? '#10B981' : d.score >= 60 ? '#F59E0B' : '#F43F5E'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}

function CostTile() {
  const r = costRollup();
  if (r.totalCalls === 0) return null;
  const anthropicShare = r.totalCalls === 0 ? 0 : Math.round((r.byProvider.anthropic.calls / r.totalCalls) * 100);
  return (
    <div className="card p-5" data-testid="cost-tile">
      <div className="flex items-baseline justify-between mb-3">
        <h3 className="font-display text-lg font-semibold">Cost & telemetry</h3>
        <span className="text-xs text-ink-500">Live — from your session data</span>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MiniStat label="Total spend"        value={`€${r.totalCostEur.toFixed(4)}`}  hint={`${r.totalCalls} calls`} />
        <MiniStat label="Per session (est.)" value={`€${r.perSessionEur.toFixed(4)}`} hint="15 calls / session avg" />
        <MiniStat label="Per agent / month"  value={`€${r.perMonthEur.toFixed(2)}`}   hint="30 sessions / month" />
        <MiniStat label="p95 latency"        value={`${r.p95LatencyMs}ms`}                 hint={`p50 ${r.p50LatencyMs}ms`} />
      </div>
      <div className="mt-4">
        <div className="flex items-baseline justify-between text-xs text-ink-500">
          <span>Provider mix</span>
          <span className="tabular-nums">{anthropicShare}% Anthropic · {100 - anthropicShare}% Gemini</span>
        </div>
        <div className="mt-1.5 flex h-2 overflow-hidden rounded-full bg-ink-200 dark:bg-ink-800">
          <div className="h-full bg-indigo-500 transition-all" style={{ width: `${anthropicShare}%` }} title="Anthropic Sonnet 4.6" />
          <div className="h-full bg-emerald-500 transition-all" style={{ width: `${100 - anthropicShare}%` }} title="Gemini fallback" />
        </div>
        <div className="mt-2 text-[11px] text-ink-500 tabular-nums">
          Tokens: in {r.totalTokensIn.toLocaleString()} · out {r.totalTokensOut.toLocaleString()}
        </div>
      </div>
    </div>
  );
}

function MiniStat(props: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-lg border border-ink-200/70 dark:border-ink-700/70 bg-white/60 dark:bg-ink-900/40 p-3">
      <div className="text-[10px] font-semibold uppercase tracking-wider text-ink-500">{props.label}</div>
      <div className="mt-1 font-display text-2xl font-semibold tabular-nums">{props.value}</div>
      {props.hint && <div className="text-[11px] text-ink-500 mt-0.5">{props.hint}</div>}
    </div>
  );
}

function ScorePill({ score }: { score: number }) {
  const tone = score >= 80 ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300' :
               score >= 60 ? 'bg-amber-500/15   text-amber-700   dark:text-amber-300' :
                             'bg-rose-500/15    text-rose-700    dark:text-rose-300';
  return <span className={`inline-flex items-center rounded-md px-2 py-0.5 text-sm font-semibold tabular-nums ${tone}`}>{score}</span>;
}
