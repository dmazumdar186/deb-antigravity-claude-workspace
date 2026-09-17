'use strict';
/* Pure scroll/motion maths. No DOM, no side effects — so it can be unit tested
   with `node --test js/motion.test.js`. Everything that touches the page lives
   in main.js / flow.js and imports these numbers. */

(function exposeMotion(root) {
  var clamp = function (lo, hi, v) { return Math.min(hi, Math.max(lo, v)); };
  var clamp01 = function (value) {
    var n = Number(value);
    return n > 0 ? (n < 1 ? n : 1) : 0;
  };

  /* How far a pinned section has been scrolled through: 0 when its top meets
     the viewport top, 1 when its bottom does. */
  var sectionProgress = function (rect, viewportHeight) {
    var range = Math.max(rect.height - viewportHeight, 1);
    return clamp01(-rect.top / range);
  };

  var lerp = function (a, b, k) { return a + (b - a) * k; };
  var easeOutQuart = function (k) {
    var t = clamp01(k);
    return 1 - Math.pow(1 - t, 4);
  };

  /* Scroll progress -> flow stage. `count` panels, the last 8% of the track is
     a hold so the closing panel is readable before the section unpins.
     - position: continuous 0..count-1, what the canvas interpolates on
     - index:    which copy panel is showing (crossfades at the leg midpoint)
     - fill[i]:  0..1 rail bar fill for step i                             */
  var flowState = function (progress, count) {
    var last = Math.max(count - 1, 0);
    var t = Math.min(last, (clamp01(progress) / 0.92) * last);
    // The epsilon keeps `from` one below `last` when t lands exactly on the
    // final state, so `to` stays in range and the closing leg still eases in
    // rather than snapping (floor(6) would give from === to === 6, leg 0).
    var from = Math.floor(Math.min(t, Math.max(last - 0.001, 0)));
    var frac = t - from;
    var leg = clamp01((frac - 0.15) / 0.7);
    var to = Math.min(last, from + 1);
    var fill = [];
    for (var i = 0; i < count; i += 1) fill.push(last === 0 ? 1 : clamp01(t - i));
    return {
      t: t,
      from: from,
      to: to,
      leg: leg,
      position: from + leg,
      index: frac < 0.5 ? from : to,
      fill: fill
    };
  };

  /* Triangular presence window with a 15% plateau either side of the centre,
     so scene elements cross-dissolve instead of hard-cutting. */
  var stateWeight = function (position, index) {
    var d = Math.abs(Number(position) - index);
    if (d >= 1) return 0;
    return clamp01((1 - d) / 0.85);
  };

  /* Vertex-wise interpolation of two horizon profiles (equal length). */
  var lerpProfile = function (a, b, k) {
    var n = Math.min(a.length, b.length);
    var out = new Array(n);
    var e = easeOutQuart(k);
    for (var i = 0; i < n; i += 1) out[i] = a[i] + (b[i] - a[i]) * e;
    return out;
  };

  var activeStepIndex = function (progress, count) {
    if (count <= 1) return 0;
    return Math.min(count - 1, Math.floor(clamp01(progress) * count));
  };

  /* Pinned step sequence. One step is readable at a time: each holds while it
     is within 0.38 of its own position, then cross-fades with the next one over
     a window in which the two opacities always sum to 1. Text does not survive
     being stacked at partial opacity, so this is a hold-and-swap rather than a
     pile of peeking cards. */
  var stackCardState = function (progress, index, count) {
    var position = clamp01(progress) * Math.max(count - 1, 0);
    var offset = index - position;
    var distance = Math.abs(offset);
    return {
      yPercent: offset * 22,
      rotationDeg: 0,
      scale: 1 - Math.min(distance, 1) * 0.03,
      opacity: clamp01((0.62 - distance) / 0.24),
      isFront: Math.min(Math.max(count - 1, 0), Math.round(position)) === index,
      zIndex: 10 - Math.round(Math.min(distance, 9))
    };
  };

  /* Deterministic value noise so the horizon is identical on every load and
     on every device — no Math.random in the scene. */
  var hashNoise = function (i, seed) {
    var x = Math.sin((i + 1) * 127.1 + (seed || 0) * 311.7) * 43758.5453;
    return x - Math.floor(x);
  };

  var api = {
    activeStepIndex: activeStepIndex,
    clamp: clamp,
    clamp01: clamp01,
    easeOutQuart: easeOutQuart,
    flowState: flowState,
    hashNoise: hashNoise,
    lerp: lerp,
    lerpProfile: lerpProfile,
    sectionProgress: sectionProgress,
    stackCardState: stackCardState,
    stateWeight: stateWeight
  };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (root) root.GaiaMotion = api;
}(typeof window !== 'undefined' ? window : globalThis));
