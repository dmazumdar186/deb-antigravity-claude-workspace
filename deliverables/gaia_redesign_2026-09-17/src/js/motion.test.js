'use strict';
/* node --test js/motion.test.js  — pure maths, no DOM required. */

const test = require('node:test');
const assert = require('node:assert/strict');
const m = require('./motion.js');

test('clamp01 pins to the unit interval and survives rubbish input', () => {
  assert.equal(m.clamp01(-3), 0);
  assert.equal(m.clamp01(0.42), 0.42);
  assert.equal(m.clamp01(9), 1);
  assert.equal(m.clamp01(NaN), 0);
  assert.equal(m.clamp01(undefined), 0);
  assert.equal(m.clamp01('0.5'), 0.5);
});

test('sectionProgress maps a pinned rect to 0..1', () => {
  const vh = 800;
  assert.equal(m.sectionProgress({ top: 0, height: 4000 }, vh), 0);
  assert.equal(m.sectionProgress({ top: -1600, height: 4000 }, vh), 0.5);
  assert.equal(m.sectionProgress({ top: -3200, height: 4000 }, vh), 1);
  assert.equal(m.sectionProgress({ top: 500, height: 4000 }, vh), 0, 'not reached yet');
  assert.equal(m.sectionProgress({ top: -9999, height: 4000 }, vh), 1, 'scrolled past');
});

test('sectionProgress does not divide by zero on a collapsed section', () => {
  const p = m.sectionProgress({ top: -10, height: 100 }, 800);
  assert.ok(Number.isFinite(p));
  assert.ok(p >= 0 && p <= 1);
});

test('flowState walks 7 panels from first to last', () => {
  const n = 7;
  const start = m.flowState(0, n);
  assert.equal(start.index, 0);
  assert.equal(start.position, 0);
  assert.equal(start.fill.length, n);

  const end = m.flowState(1, n);
  assert.equal(end.index, n - 1);
  assert.ok(Math.abs(end.position - (n - 1)) < 1e-9);
  assert.ok(end.fill.every((f) => f === 1 || f === 0));
  assert.equal(end.fill[0], 1);
});

test('flowState crossfades copy at the midpoint of each leg', () => {
  const n = 7;
  // 0.92 of the track covers 6 legs, so one leg is 0.92/6 of progress.
  const leg = 0.92 / 6;
  assert.equal(m.flowState(leg * 0.4, n).index, 0, 'still on panel 0 before halfway');
  assert.equal(m.flowState(leg * 0.6, n).index, 1, 'flipped to panel 1 after halfway');
  assert.equal(m.flowState(leg * 1.4, n).index, 1);
  assert.equal(m.flowState(leg * 1.6, n).index, 2);
});

test('flowState position is monotonic and bounded', () => {
  let prev = -1;
  for (let i = 0; i <= 200; i += 1) {
    const s = m.flowState(i / 200, 7);
    assert.ok(s.position >= prev - 1e-9, `position went backwards at ${i}`);
    assert.ok(s.position >= 0 && s.position <= 6);
    prev = s.position;
  }
});

test('flowState holds a state for the first 15% of its leg', () => {
  const n = 7;
  const leg = 0.92 / 6;
  assert.equal(m.flowState(leg * 0.1, n).position, 0, 'hold before the leg plays');
  assert.ok(m.flowState(leg * 0.85, n).position > 0.95, 'leg complete before the next hold');
});

test('flowState copes with a single panel', () => {
  const s = m.flowState(0.5, 1);
  assert.equal(s.index, 0);
  assert.equal(s.position, 0);
  assert.deepEqual(s.fill, [1]);
});

test('stateWeight is 1 at its own state and 0 a full state away', () => {
  assert.equal(m.stateWeight(2, 2), 1);
  assert.equal(m.stateWeight(2, 4), 0);
  assert.equal(m.stateWeight(3, 1), 0);
  assert.ok(m.stateWeight(2.15, 2) === 1, 'plateau covers the 15% overlap');
  assert.ok(m.stateWeight(2.5, 2) > 0 && m.stateWeight(2.5, 2) < 1);
  assert.ok(Math.abs(m.stateWeight(2.5, 2) - m.stateWeight(2.5, 3)) < 1e-9, 'symmetric crossfade');
});

test('stateWeight never leaves the scene empty mid-transition', () => {
  for (let p = 0; p <= 6; p += 0.05) {
    let total = 0;
    for (let i = 0; i < 7; i += 1) total += m.stateWeight(p, i);
    assert.ok(total > 0.9, `scene faded out at position ${p} (total ${total})`);
  }
});

test('lerpProfile clips to the shorter profile rather than emitting NaN', () => {
  const out = m.lerpProfile([0, 0, 0, 0, 0], [1, 2], 1);
  assert.equal(out.length, 2);
  assert.deepEqual(out, [1, 2]);
  assert.ok(out.every(Number.isFinite));
  assert.deepEqual(m.lerpProfile([], [1, 2, 3], 0.5), []);
});

test('lerpProfile interpolates vertex-wise with an ease-out', () => {
  const a = [0, 0, 0];
  const b = [1, 2, 4];
  assert.deepEqual(m.lerpProfile(a, b, 0), [0, 0, 0]);
  assert.deepEqual(m.lerpProfile(a, b, 1), [1, 2, 4]);
  const mid = m.lerpProfile(a, b, 0.5);
  assert.equal(mid.length, 3);
  assert.ok(mid[0] > 0.5, 'ease-out quart is ahead of linear at the midpoint');
  assert.ok(mid[2] < 4);
});

test('easeOutQuart is monotonic, clamped and starts fast', () => {
  assert.equal(m.easeOutQuart(0), 0);
  assert.equal(m.easeOutQuart(1), 1);
  assert.equal(m.easeOutQuart(-1), 0);
  assert.equal(m.easeOutQuart(2), 1);
  assert.ok(m.easeOutQuart(0.25) > 0.25);
  let prev = -1;
  for (let i = 0; i <= 50; i += 1) {
    const v = m.easeOutQuart(i / 50);
    assert.ok(v >= prev, 'not monotonic');
    prev = v;
  }
});

test('stackCardState: first step is front and fully readable at rest', () => {
  const rest = m.stackCardState(0, 0, 5);
  assert.equal(rest.isFront, true);
  assert.equal(rest.opacity, 1);
  assert.equal(rest.yPercent, 0);
  assert.equal(rest.zIndex, 10);

  const gone = m.stackCardState(1, 0, 5);
  assert.equal(gone.opacity, 0, 'fully faded once the sequence has advanced');
  assert.ok(gone.yPercent < -22, 'lifted out of frame');
  assert.equal(m.stackCardState(0, 1, 5).opacity, 0, 'the next step waits off-stage');
  assert.ok(gone.scale < 1);
});

test('stackCardState: exactly one card is front at any progress', () => {
  for (let i = 0; i <= 100; i += 1) {
    const p = i / 100;
    const fronts = [0, 1, 2, 3, 4].filter((idx) => m.stackCardState(p, idx, 5).isFront);
    assert.equal(fronts.length, 1, `progress ${p} had ${fronts.length} front cards`);
  }
});

test('stackCardState: never more than two steps are drawn at once', () => {
  for (let i = 0; i <= 200; i += 1) {
    const p = i / 200;
    const drawn = [0, 1, 2, 3, 4].filter((idx) => m.stackCardState(p, idx, 5).opacity > 0.01);
    assert.ok(drawn.length <= 2, `progress ${p} drew ${drawn.length} steps at once`);
  }
});

test('stackCardState: some step is always legible', () => {
  for (let i = 0; i <= 200; i += 1) {
    const p = i / 200;
    const total = [0, 1, 2, 3, 4].reduce((sum, idx) => sum + m.stackCardState(p, idx, 5).opacity, 0);
    assert.ok(total > 0.95, `progress ${p} left the stage nearly blank (${total.toFixed(2)})`);
  }
});

test('stackCardState: the step on top is the nearest one', () => {
  const p = 0.4;
  const states = [0, 1, 2, 3, 4].map((idx) => m.stackCardState(p, idx, 5));
  const brightest = states.indexOf(states.reduce((a, b) => (b.opacity > a.opacity ? b : a)));
  const highest = states.indexOf(states.reduce((a, b) => (b.zIndex > a.zIndex ? b : a)));
  assert.equal(brightest, highest);
});

test('stackCardState opacity never goes negative', () => {
  for (let i = 0; i <= 100; i += 1) {
    for (let idx = 0; idx < 5; idx += 1) {
      const s = m.stackCardState(i / 100, idx, 5);
      assert.ok(s.opacity >= 0 && s.opacity <= 1);
      assert.ok(Number.isFinite(s.yPercent) && Number.isFinite(s.scale));
      assert.ok(Number.isFinite(s.zIndex));
    }
  }
});

test('activeStepIndex stays inside the list', () => {
  assert.equal(m.activeStepIndex(0, 5), 0);
  assert.equal(m.activeStepIndex(0.5, 5), 2);
  assert.equal(m.activeStepIndex(1, 5), 4);
  assert.equal(m.activeStepIndex(1, 1), 0);
  assert.equal(m.activeStepIndex(2, 5), 4);
});

test('hashNoise is deterministic and in 0..1', () => {
  // Pinned literal: the horizon and the scatter must be byte-identical on every
  // device and every reload, so a change to this function is a visible change.
  assert.equal(m.hashNoise(7, 3).toFixed(12), '0.418177968844');
  assert.equal(m.hashNoise(7, 3), m.hashNoise(7, 3));
  assert.notEqual(m.hashNoise(7, 3), m.hashNoise(8, 3));
  for (let i = 0; i < 64; i += 1) {
    const v = m.hashNoise(i, 11);
    assert.ok(v >= 0 && v < 1, `noise out of range at ${i}: ${v}`);
  }
});

test('lerp is plain linear interpolation', () => {
  assert.equal(m.lerp(10, 20, 0), 10);
  assert.equal(m.lerp(10, 20, 1), 20);
  assert.equal(m.lerp(10, 20, 0.5), 15);
});
