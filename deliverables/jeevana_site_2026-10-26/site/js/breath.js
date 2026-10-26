(function () {
  'use strict';
  var api = {}, cv = null, ctx = null, raf = 0, paused = false, hidden = false;
  var W = 0, H = 0, dpr = 1, p = 0, seed = 1, reduced = false, pts = [], n = 0;
  var INK = '243,238,228', ACC = '196,115,26', tgt = null, lvl = 0.5, G = { cx: 0, cy: 0, r: 0, rMax: 0 };

  function mul(a) { return function () { a |= 0; a = a + 0x6D2B79F5 | 0; var t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }

  function build() {
    var r = mul(seed), area = W * H, k = Math.max(120, Math.min(220, Math.round(area / 9000)));
    pts = [];
    for (var i = 0; i < k; i++) {
      var u = r(), g = r(), rr = 0.7 + 0.65 * Math.pow(u, 0.6); // denser near ring (u~0 -> 0.7R)
      var ang = g * Math.PI * 2, sp = 0.0002 + r() * 0.0006, ph = r() * 6.283, amp = 0.02 + r() * 0.05;
      pts.push({ a: ang, r: rr, sz: 0.6 + r() * 0.8, al: 0.05 + r() * 0.17, acc: r() < 0.03, sp: sp, ph: ph, amp: amp });
    }
    n = k;
  }

  function resize() {
    if (!cv) return;
    dpr = Math.min(opts.dpr || 1.5, window.devicePixelRatio || 1);
    W = cv.clientWidth; H = cv.clientHeight;
    var b = Math.max(1, Math.round(W * dpr)), h = Math.max(1, Math.round(H * dpr));
    if (cv.width !== b) cv.width = b;
    if (cv.height !== h) cv.height = h;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    build();
  }

  var opts = {};

  function draw(t) {
    if (!ctx) return;
    if (tgt !== null) lvl += (tgt - lvl) * 0.06; else lvl = api.breath(t);
    var b = lvl, cx = W / 2, cy = H * (0.5 - 0.04 * p), R = 0.36 * Math.min(W, H);
    var rot = p * 0.6, s = 1 + 0.04 * b, hb = 1 + 0.3 * b;
    G.cx = cx; G.cy = cy; G.r = R * s; G.rMax = R * 1.04;
    ctx.clearRect(0, 0, W, H);
    ctx.lineWidth = 1;
    ctx.strokeStyle = 'rgba(' + INK + ',0.35)';
    ctx.beginPath();
    ctx.arc(cx, cy, R * s, 0, 6.2832);
    ctx.stroke();
    var i, q;
    for (i = 0; i < n; i++) {
      q = pts[i];
      var a = q.a + rot + q.sp * t * 0.06 + Math.sin(t * 0.0004 + q.ph) * q.amp;
      var rr = q.r * R * s * (1 + Math.cos(t * 0.0003 + q.ph) * q.amp * 0.5);
      var x = cx + Math.cos(a) * rr, y = cy + Math.sin(a) * rr;
      ctx.fillStyle = 'rgba(' + (q.acc ? ACC : INK) + ',' + (q.al * hb).toFixed(3) + ')';
      ctx.beginPath();
      ctx.arc(x, y, q.sz, 0, 6.2832);
      ctx.fill();
    }
  }

  function loop() {
    raf = 0;
    if (paused || hidden) return;
    draw(performance.now());
    raf = requestAnimationFrame(loop);
  }

  function start() { if (!raf && !paused && !hidden && !reduced) raf = requestAnimationFrame(loop); }

  var ro = null;

  api.init = function (canvas, o) {
    opts = o || {};
    cv = canvas; seed = (opts.seed || 1) | 0;
    reduced = !!opts.reducedMotion;
    ctx = cv.getContext ? cv.getContext('2d') : null;
    if (!ctx) return;
    p = 0;
    resize();
    if (window.ResizeObserver) { ro = new ResizeObserver(resize); ro.observe(cv); }
    else window.addEventListener('resize', resize);
    document.addEventListener('visibilitychange', onVis);
    if (reduced) { draw(1375); } // b=0.5 at t=1375
    else if (opts.autoplay !== false) start();
  };

  function onVis() {
    hidden = document.hidden;
    if (hidden) { if (raf) { cancelAnimationFrame(raf); raf = 0; } }
    else start();
  }

  api.setProgress = function (v) {
    p = Math.max(0, Math.min(1, v || 0));
    if (reduced) draw(1375);
  };
  api.render = function (t) { if (!reduced) draw(t); else draw(1375); };
  api.breath = function (t) { return (1 - Math.cos(6.283185307 * (t / 5500))) / 2; };
  api.setBreath = function (v) { tgt = (v === null || v === undefined) ? null : Math.max(0, Math.min(1, v)); if (reduced) { lvl = tgt === null ? 0.5 : tgt; draw(1375); } };
  api.level = function () { return lvl; };
  api.geom = function () { return { cx: G.cx, cy: G.cy, r: G.r, rMax: G.rMax }; };
  api.pause = function () { paused = true; if (raf) { cancelAnimationFrame(raf); raf = 0; } };
  api.resume = function () { paused = false; start(); };
  api.destroy = function () {
    api.pause(); paused = false;
    if (ro) { ro.disconnect(); ro = null; }
    window.removeEventListener('resize', resize);
    document.removeEventListener('visibilitychange', onVis);
    cv = ctx = null; pts = [];
  };

  window.JeevanaBackdrop = api;
})();
