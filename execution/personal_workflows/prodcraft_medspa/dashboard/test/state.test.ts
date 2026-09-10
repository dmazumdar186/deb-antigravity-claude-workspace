import { describe, expect, it } from 'vitest';
import { allowedTransitions, canTransition, IllegalTransition, assertTransition, STATES, type OutreachState } from '../functions/_lib/state';

const LEGAL: [OutreachState, OutreachState][] = [
  ['queued', 'drafted'],
  ['drafted', 'sent'],
  ['sent', 'replied'],
  ['sent', 'queued'],
  ['sent', 'closed_lost'],
  ['replied', 'call_booked'],
  ['replied', 'closed_lost'],
  ['call_booked', 'closed_won'],
  ['call_booked', 'closed_lost'],
];

describe('state machine', () => {
  it('accepts every legal transition from CONTRACTS.md', () => {
    for (const [from, to] of LEGAL) {
      expect(canTransition(from, to), `${from}->${to}`).toBe(true);
    }
  });

  it('*→dnc is always legal, from every state including terminal ones', () => {
    for (const state of STATES) {
      expect(canTransition(state, 'dnc'), `${state}->dnc`).toBe(true);
    }
  });

  it('rejects illegal transitions', () => {
    const illegal: [OutreachState, OutreachState][] = [
      ['queued', 'sent'],
      ['queued', 'replied'],
      ['drafted', 'queued'],
      ['drafted', 'replied'],
      ['sent', 'call_booked'],
      ['sent', 'drafted'],
      ['replied', 'sent'],
      ['call_booked', 'replied'],
      ['closed_won', 'sent'],
      ['closed_lost', 'queued'],
    ];
    for (const [from, to] of illegal) {
      expect(canTransition(from, to), `${from}->${to}`).toBe(false);
    }
  });

  it('closed_won and closed_lost only accept dnc (terminal states)', () => {
    for (const state of ['closed_won', 'closed_lost'] as OutreachState[]) {
      for (const to of STATES) {
        if (to === 'dnc') continue;
        expect(canTransition(state, to), `${state}->${to}`).toBe(false);
      }
    }
  });

  it('every non-terminal state has at least one outgoing edge besides dnc', () => {
    for (const state of ['queued', 'drafted', 'sent', 'replied', 'call_booked'] as OutreachState[]) {
      const targets = allowedTransitions(state).filter((t) => t !== 'dnc');
      expect(targets.length, state).toBeGreaterThan(0);
    }
  });

  it('every state is reachable from queued (the entry state) via legal edges', () => {
    const reached = new Set<OutreachState>(['queued']);
    let changed = true;
    while (changed) {
      changed = false;
      for (const from of [...reached]) {
        for (const to of STATES) {
          if (!reached.has(to) && canTransition(from, to)) {
            reached.add(to);
            changed = true;
          }
        }
      }
    }
    for (const state of STATES) {
      expect(reached.has(state), state).toBe(true);
    }
  });

  it('assertTransition throws IllegalTransition on a bad edge and is silent on a good one', () => {
    expect(() => assertTransition('queued', 'drafted')).not.toThrow();
    expect(() => assertTransition('queued', 'sent')).toThrow(IllegalTransition);
  });
});
