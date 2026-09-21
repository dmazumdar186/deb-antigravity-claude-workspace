import { describe, it, expect } from 'vitest';
import {
  clamp01,
  sectionProgress,
  activeStepIndex,
  folioCardState,
  FOLIO_TAB_Y_PERCENT,
  FOLIO_VISIBLE_DEPTH,
  drumStepState,
  heroFrame,
} from './motion';

describe('clamp01', () => {
  it('clamps to [0,1] and coerces NaN to 0', () => {
    expect(clamp01(-5)).toBe(0);
    expect(clamp01(5)).toBe(1);
    expect(clamp01(0.5)).toBe(0.5);
    expect(clamp01(Number.NaN)).toBe(0);
  });
});

describe('sectionProgress', () => {
  it('is 0 at the top and 1 at the bottom of the scrollable range', () => {
    const rect = { top: 0, height: 3000 };
    expect(sectionProgress(rect, 1000)).toBe(0);
    expect(sectionProgress({ ...rect, top: -2000 }, 1000)).toBe(1);
    expect(sectionProgress({ ...rect, top: -1000 }, 1000)).toBeCloseTo(0.5);
  });

  it('never divides by zero for a section shorter than the viewport', () => {
    expect(() => sectionProgress({ top: 0, height: 10 }, 1000)).not.toThrow();
  });
});

describe('activeStepIndex', () => {
  it('returns 0 for a single step regardless of progress', () => {
    expect(activeStepIndex(0.9, 1)).toBe(0);
  });

  it('advances through steps across progress', () => {
    expect(activeStepIndex(0, 4)).toBe(0);
    expect(activeStepIndex(0.99, 4)).toBe(3);
    expect(activeStepIndex(0.5, 4)).toBe(2);
  });
});

describe('folioCardState', () => {
  it('keeps the first card near-rest at progress 0', () => {
    const state = folioCardState(0, 0, 5);
    expect(state.opacity).toBeGreaterThan(0.5);
    expect(state.zIndex).toBe(5);
  });

  it('exits an earlier card (fades and moves away) once progress passes it', () => {
    const early = folioCardState(0.9, 0, 5);
    expect(early.opacity).toBeLessThan(0.2);
  });

  it('produces different transforms for different indices at the same progress', () => {
    const a = folioCardState(0.4, 0, 5);
    const b = folioCardState(0.4, 3, 5);
    expect(a.yPercent).not.toBe(b.yPercent);
  });

  it('lifts each back card by one tab strip per depth so its headline clears the front card', () => {
    const count = 6;
    const front = folioCardState(0, 0, count);
    expect(front.yPercent).toBe(0);
    expect(front.scale).toBe(1);
    for (let depth = 1; depth <= FOLIO_VISIBLE_DEPTH; depth++) {
      const back = folioCardState(0, depth, count);
      expect(back.yPercent).toBe(-FOLIO_TAB_Y_PERCENT * depth);
      expect(back.zIndex).toBeLessThan(front.zIndex);
    }
    // Deeper cards park at the last visible layer (hidden behind it by z-order),
    // never running further off the top of the stage.
    const deep = folioCardState(0, count - 1, count);
    expect(deep.yPercent).toBe(-FOLIO_TAB_Y_PERCENT * FOLIO_VISIBLE_DEPTH);
    expect(deep.opacity).toBe(0);
    expect(folioCardState(0, FOLIO_VISIBLE_DEPTH, count).opacity).toBeGreaterThan(0.5);
  });
});

describe('drumStepState', () => {
  it('marks exactly one step active per progress value', () => {
    const count = 4;
    for (const progress of [0, 0.2, 0.4, 0.6, 0.8, 0.99]) {
      const activeCount = Array.from({ length: count }, (_, i) => drumStepState(progress, i, count)).filter(
        (s) => s.isActive
      ).length;
      expect(activeCount).toBe(1);
    }
  });

  it('fades and tilts steps away from the active one', () => {
    const active = drumStepState(0, 0, 4);
    const distant = drumStepState(0, 3, 4);
    expect(active.opacity).toBeGreaterThan(distant.opacity);
    expect(Math.abs(active.rotationX)).toBeLessThan(Math.abs(distant.rotationX));
  });
});

describe('heroFrame', () => {
  it('starts at state 0 with an empty rail and ends at the last state fully filled', () => {
    const first = heroFrame(0, 4);
    expect(first.stateIndex).toBe(0);
    expect(first.fill.every((f) => f === 0)).toBe(true);

    const last = heroFrame(1, 4);
    expect(last.stateIndex).toBe(3);
    expect(last.fill[0]).toBe(1);
    expect(last.fill[2]).toBe(1);
  });

  it('fill is monotonically non-decreasing per step as progress increases', () => {
    const p1 = heroFrame(0.3, 4);
    const p2 = heroFrame(0.7, 4);
    p1.fill.forEach((f, i) => expect(p2.fill[i]).toBeGreaterThanOrEqual(f));
  });

  it('handles a single-state hero without dividing by zero', () => {
    expect(() => heroFrame(0.5, 1)).not.toThrow();
    expect(heroFrame(0.5, 1).stateIndex).toBe(0);
  });
});
