// Pure functions: seeded RNG, daily case selection, streak logic, aggregation.
// No DOM, no localStorage — 100% unit-testable.

import type { AppState, Case, CompletedCase, Session, Scorecard, Turn } from './types';

// --- Seeded RNG (mulberry32) so today's 3 cases are stable across page reloads ---

export function hashString(s: string): number {
  let h = 2166136261 >>> 0;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619) >>> 0;
  }
  return h >>> 0;
}

export function mulberry32(seed: number): () => number {
  let t = seed >>> 0;
  return function () {
    t = (t + 0x6D2B79F5) >>> 0;
    let x = t;
    x = Math.imul(x ^ (x >>> 15), x | 1);
    x ^= x + Math.imul(x ^ (x >>> 7), x | 61);
    return ((x ^ (x >>> 14)) >>> 0) / 4294967296;
  };
}

export function pickDailyCases(cases: Case[], dateISO: string, n = 3): Case[] {
  if (cases.length === 0) return [];
  const seed = hashString('agentup:' + dateISO);
  const rand = mulberry32(seed);
  const pool = cases.slice();
  const picked: Case[] = [];
  const target = Math.min(n, pool.length);
  while (picked.length < target && pool.length > 0) {
    const i = Math.floor(rand() * pool.length);
    picked.push(pool[i]);
    pool.splice(i, 1);
  }
  return picked;
}

// --- Streak logic ---

export function todayUTC(): string {
  return new Date().toISOString().slice(0, 10);
}

export function daysBetween(a: string, b: string): number {
  const da = Date.UTC(+a.slice(0, 4), +a.slice(5, 7) - 1, +a.slice(8, 10));
  const db = Date.UTC(+b.slice(0, 4), +b.slice(5, 7) - 1, +b.slice(8, 10));
  return Math.round((db - da) / 86_400_000);
}

export function updateStreak(prev: { count: number; lastDate: string | null }, today: string): { count: number; lastDate: string } {
  if (!prev.lastDate) return { count: 1, lastDate: today };
  const gap = daysBetween(prev.lastDate, today);
  if (gap === 0) return { count: prev.count || 1, lastDate: today };
  if (gap === 1) return { count: prev.count + 1, lastDate: today };
  return { count: 1, lastDate: today }; // gap > 1 → break
}

// --- Score aggregation ---

export function averageOfScores(scores: number[]): number {
  if (scores.length === 0) return 0;
  const sum = scores.reduce((a, b) => a + b, 0);
  return Math.round(sum / scores.length);
}

export function sessionAverage(cs: CompletedCase[]): number {
  return averageOfScores(cs.map((c) => c.scorecard.overallScore));
}

// --- Dashboard aggregation ---

export interface DailyPoint { date: string; score: number; sessions: number }
export interface GroupPoint { key: string; score: number; count: number }

export function daily30(sessions: Session[], todayISO: string): DailyPoint[] {
  const points: DailyPoint[] = [];
  const map = new Map<string, number[]>();
  for (const s of sessions) {
    const arr = map.get(s.date) ?? [];
    arr.push(s.averageScore);
    map.set(s.date, arr);
  }
  const today = Date.UTC(+todayISO.slice(0, 4), +todayISO.slice(5, 7) - 1, +todayISO.slice(8, 10));
  for (let i = 29; i >= 0; i--) {
    const d = new Date(today - i * 86_400_000);
    const iso = d.toISOString().slice(0, 10);
    const arr = map.get(iso) ?? [];
    points.push({
      date: iso,
      score: arr.length ? averageOfScores(arr) : 0,
      sessions: arr.length,
    });
  }
  return points;
}

export function groupByKey(sessions: Session[], keyFn: (c: CompletedCase) => string): GroupPoint[] {
  const map = new Map<string, number[]>();
  for (const s of sessions) {
    for (const c of s.cases) {
      const k = keyFn(c);
      const arr = map.get(k) ?? [];
      arr.push(c.scorecard.overallScore);
      map.set(k, arr);
    }
  }
  return Array.from(map.entries())
    .map(([key, scores]) => ({ key, score: averageOfScores(scores), count: scores.length }))
    .sort((a, b) => b.score - a.score);
}

export function summaryStats(state: AppState) {
  const total = state.sessions.length;
  const today = todayUTC();
  const weekStart = new Date();
  weekStart.setUTCDate(weekStart.getUTCDate() - 6);
  const weekStartISO = weekStart.toISOString().slice(0, 10);
  const thisWeek = state.sessions.filter((s) => s.date >= weekStartISO).length;

  // Skill breakdown across last 30 days (by dimension).
  const dims: Array<keyof Scorecard> = ['empathyScore', 'accuracyScore', 'resolutionScore', 'professionalismScore'];
  const per: Record<string, number[]> = { empathyScore: [], accuracyScore: [], resolutionScore: [], professionalismScore: [] };
  for (const s of state.sessions) for (const c of s.cases) for (const d of dims) per[d].push(c.scorecard[d] as number);
  const avgs: Record<string, number> = {};
  for (const d of dims) avgs[d] = averageOfScores(per[d]);

  const skillLabel: Record<string, string> = {
    empathyScore: 'Empathy & Tone',
    accuracyScore: 'Accuracy',
    resolutionScore: 'Resolution',
    professionalismScore: 'Professionalism',
  };
  let topKey = '', worstKey = '';
  let topScore = -1, worstScore = 101;
  for (const d of dims) {
    if (per[d].length === 0) continue;
    if (avgs[d] > topScore)   { topScore = avgs[d]; topKey = d; }
    if (avgs[d] < worstScore) { worstScore = avgs[d]; worstKey = d; }
  }

  return {
    streak: state.streak.count,
    sessionsThisWeek: thisWeek,
    totalSessions: total,
    topSkill:    topKey ? { label: skillLabel[topKey], score: topScore } : null,
    weakSkill:   worstKey && worstKey !== topKey ? { label: skillLabel[worstKey], score: worstScore } : null,
  };
}

export function newSessionFromCompletedCases(cs: CompletedCase[], dateISO: string): Session {
  return {
    id: 'sess-' + dateISO + '-' + Math.random().toString(36).slice(2, 8),
    date: dateISO,
    cases: cs,
    averageScore: sessionAverage(cs),
  };
}

export const _testonly = { mulberry32, hashString };
