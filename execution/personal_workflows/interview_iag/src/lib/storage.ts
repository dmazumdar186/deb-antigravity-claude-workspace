// localStorage read/write for AgentUp. Single key, JSON blob.
// Defensive: private-mode / quota-exceeded / stale-schema → returns a fresh state.

import type { AppState, Case, Session } from './types';
import DEFAULT_CASES from '../data/default-cases.json';

const STORAGE_KEY = 'agentup:v1';

function emptyState(): AppState {
  return {
    cases: (DEFAULT_CASES as Case[]).slice(),
    sessions: [],
    streak: { count: 0, lastDate: null },
  };
}

export function loadState(): AppState {
  if (typeof localStorage === 'undefined') return emptyState();
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return emptyState();
    const parsed = JSON.parse(raw) as Partial<AppState>;
    // Merge defaults so a user who nuked their custom cases still has the built-ins.
    const defaults = DEFAULT_CASES as Case[];
    const existingIds = new Set((parsed.cases ?? []).map((c) => c.id));
    const mergedCases = [
      ...(parsed.cases ?? []),
      ...defaults.filter((d) => !existingIds.has(d.id)),
    ];
    return {
      cases: mergedCases,
      sessions: Array.isArray(parsed.sessions) ? parsed.sessions as Session[] : [],
      streak: parsed.streak ?? { count: 0, lastDate: null },
    };
  } catch {
    return emptyState();
  }
}

export function saveState(state: AppState): void {
  if (typeof localStorage === 'undefined') return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // Quota exceeded / private mode — silently degrade.
  }
}

export function resetState(): void {
  if (typeof localStorage === 'undefined') return;
  try { localStorage.removeItem(STORAGE_KEY); } catch { /* ignore */ }
}
