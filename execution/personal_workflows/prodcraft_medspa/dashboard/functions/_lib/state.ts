// Outreach state machine — CONTRACTS.md "Outreach state machine
// (outreach/state_machine.py)". Duplicated on purpose (dashboard is
// TypeScript, the pipeline is Python) so the dashboard can validate
// transitions without a Python round trip. Keep this table byte-identical
// in shape to execution/personal_workflows/prodcraft_medspa/outreach/state_machine.py
// whenever that file exists/changes.

export const STATES = [
  'queued',
  'drafted',
  'sent',
  'replied',
  'call_booked',
  'closed_won',
  'closed_lost',
  'dnc',
] as const;

export type OutreachState = (typeof STATES)[number];

export const TOUCH_DAYS = [0, 3, 7, 12] as const;

// Explicit transition table. `dnc` is reachable from every state (`*→dnc`)
// and is handled separately in canTransition rather than listed on every
// row, but every other edge is spelled out here.
const TRANSITIONS: Record<OutreachState, OutreachState[]> = {
  queued: ['drafted'],
  drafted: ['sent'],
  sent: ['replied', 'queued', 'closed_lost'],
  replied: ['call_booked', 'closed_lost'],
  call_booked: ['closed_won', 'closed_lost'],
  closed_won: [],
  closed_lost: [],
  dnc: [],
};

export function isOutreachState(value: unknown): value is OutreachState {
  return typeof value === 'string' && (STATES as readonly string[]).includes(value);
}

/**
 * `*→dnc` is always legal (opt-out / takedown must always be reachable).
 * Every other edge must appear in TRANSITIONS.
 */
export function canTransition(from: OutreachState, to: OutreachState): boolean {
  if (to === 'dnc') return true;
  return TRANSITIONS[from]?.includes(to) ?? false;
}

export function allowedTransitions(from: OutreachState): OutreachState[] {
  const rest = TRANSITIONS[from] ?? [];
  return rest.includes('dnc') ? rest : [...rest, 'dnc'];
}

export class IllegalTransition extends Error {
  constructor(from: OutreachState, to: OutreachState) {
    super(`illegal outreach transition: ${from} -> ${to}`);
    this.name = 'IllegalTransition';
  }
}

export function assertTransition(from: OutreachState, to: OutreachState): void {
  if (!canTransition(from, to)) {
    throw new IllegalTransition(from, to);
  }
}
