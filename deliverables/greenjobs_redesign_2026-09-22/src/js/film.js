'use strict';
/* Home film: a pinned sequence scrubbed by scroll, second on the page. One
   canvas of particles plays three states — the edition map (points sampled
   from the SVG at build time), the disclosed-salary bands, the sector ring.
   Progress → state (15% hold, 70% travel); every particle eases to a
   per-state target (easeOutQuart, staggered by index) so a wheel flick stays
   smooth. Toned for the page theme (paper by default, moss in dark) and
   re-toned live when the theme toggles. DPR-aware, paused off-screen, the
   same three states at every width, static map copy under reduced motion. */
(function () {
  var G = window.GJ, doc = document, host = doc.querySelector('[data-film]');
  if (!host) return;
  var stage = host.querySelector('[data-film-stage]'), cwrap = host.querySelector('[data-film-canvas]');
  var states = [].slice.call(host.querySelectorAll('[data-film-state]')), steps = [].slice.call(host.querySelectorAll('[data-film-step]'));
  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)'), narrow = window.matchMedia('(max-width: 899px)');
  var data = null;
  try { data = JSON.parse(doc.getElementById('gj-film').textContent); } catch (e) { data = null; }
  var cur = -1;
  function show(i) {
    if (i === cur) return;
    cur = i;
    host.setAttribute('data-fs', String(i));
    states.forEach(function (el) { el.classList.toggle('is-on', +el.getAttribute('data-film-state') === i); });
    steps.forEach(function (el) { el.classList.toggle('is-on', +el.getAttribute('data-film-step') === i); });
  }
  function staticFilm() { host.classList.add('film--static'); show(0); }
  if (reduce.matches || !data || !window.HTMLCanvasElement || !doc.createElement('canvas').getContext) { staticFilm(); return; }

  /* ---------------------------------------------------------- scroll → state */
  var SEQ = [0, 1, 2], LAST = SEQ.length - 1, scrub = { t: 0, g: 0, show: 0 };
  function span() { host.style.setProperty('--film-span', String(SEQ.length)); host.classList.toggle('film--m', narrow.matches); }
  function topFor(k) { /* scrollY at which state k is fully held */
    var rect = host.getBoundingClientRect(), vh = window.innerHeight;
    return window.scrollY + rect.top + (k * 0.92 / LAST) * (rect.height - vh) + (k === LAST ? (rect.height - vh) * 0.08 : 0);
  }
  function frame() {
    var rect = host.getBoundingClientRect(), vh = window.innerHeight;
    scrub = G.filmScrub(-rect.top / Math.max(1, rect.height - vh), LAST);
    doc.body.classList.toggle('film-pinned', rect.top <= 0 && rect.bottom > vh - 2);
    var idx = SEQ[scrub.show];
    if (idx !== cur) { show(idx); retarget(idx); }
    steps.forEach(function (el) { var k = SEQ.indexOf(+el.getAttribute('data-film-step')); el.style.setProperty('--fill', k < 0 ? '0' : scrub.fills[k].toFixed(3)); });
  }
  var scheduled = false;
  function schedule() { if (scheduled) return; scheduled = true; requestAnimationFrame(function () { scheduled = false; frame(); }); }

  /* ---------------------------------------------------------- theme tones */
  var T = {};
  function tone() {
    var dark = doc.documentElement.getAttribute('data-theme') === 'dark';
    T = dark
      ? { bg: [30, 26, 23], ink: '#f3ece1', muted: '#c9bfb2', chip: 'rgba(30,26,23,.86)', lit: '#d99a1c', dim: '#4a423b', dimA: 0.7, dot: '#7fb3d3', line: 'rgba(243,236,225,.35)', onLime: '#1e1a17' }
      : { bg: [239, 230, 214], ink: '#f6f0e6', muted: '#5a524b', chip: 'rgba(42,37,33,.9)', lit: '#a3653c', dim: '#b9ab8f', dimA: 0.85, dot: '#3f7ea6', line: 'rgba(42,37,33,.35)', onLime: '#2a2521' };
  }
  tone();
  new MutationObserver(function () { tone(); if (W) { ctx.fillStyle = 'rgb(' + T.bg.join(',') + ')'; ctx.fillRect(0, 0, W, H); } }).observe(doc.documentElement, { attributes: true, attributeFilter: ['data-theme'] });

  /* ---------------------------------------------------------- canvas + particles */
  var c = doc.createElement('canvas'); c.setAttribute('aria-hidden', 'true'); cwrap.appendChild(c);
  var ctx = c.getContext('2d', { alpha: true }), W = 0, H = 0, dpr = 1, P = [], N = 0, raf = 0, running = false, visible = true;
  var layout = null, mode = 0, LIME = '#d99a1c', PX = narrow.matches ? 2.4 : 3;
  var colors = ['#5b95b8', '#d99a1c', '#6f8f6a', '#3f7ea6', '#b7774e'];
  try { colors = JSON.parse(host.querySelector('[data-colors]') ? host.querySelector('[data-colors]').getAttribute('data-colors') : 'null') || colors; } catch (e) { /* defaults */ }
  var regionsByCount = data.regions.map(function (r, i) { return { i: i, c: r.c }; }).filter(function (r) { return r.c > 0; }).sort(function (a, b) { return b.c - a.c; });
  var litRank = {}; regionsByCount.forEach(function (r, k) { litRank[r.i] = k; });
  var np = data.pts.length / 3;

  function size() {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    W = stage.clientWidth; H = stage.clientHeight;
    c.width = Math.round(W * dpr); c.height = Math.round(H * dpr);
    c.style.width = W + 'px'; c.style.height = H + 'px';
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    N = narrow.matches ? Math.min(1200, Math.max(500, Math.round(W * H / 400))) : Math.min(3000, Math.max(1200, Math.round(W * H / 430)));
    while (P.length < N) P.push(spawn({}));
    P.length = N;
    ctx.fillStyle = 'rgb(' + T.bg.join(',') + ')'; ctx.fillRect(0, 0, W, H);
    layout = null;
    if (cur >= 0) retarget(cur, true);
  }
  function spawn(p) {
    p.x = Math.random() * W; p.y = Math.random() * H; p.c = colors[(Math.random() * colors.length) | 0];
    p.tx = p.x; p.ty = p.y; p.t0 = 0; p.a = 0; p.r = 0; p.k = 0; p.ph = Math.random() * 6.283; return p;
  }
  /* The figure area: right half on wide screens, the top half on narrow. */
  function area() {
    return narrow.matches ? { x: 20, y: 64, w: W - 40, h: H * 0.5 - 40 } : { x: W * 0.5, y: 84, w: W * 0.5 - 40, h: H - 170 };
  }
  /* ------------------------------ per-state target layouts (particle i → x, y, colour, meta) */
  function mapLayout() {
    var A = area(), vw = data.vb[0], vh = data.vb[1], sc = Math.min(A.w / vw, A.h / vh), ox = A.x + (A.w - vw * sc) / 2, oy = A.y + (A.h - vh * sc) / 2;
    return { geo: { sc: sc, ox: ox, oy: oy }, at: function (i) {
      var k = (i % np) * 3, j = Math.floor(i / np);
      return { x: ox + data.pts[k] * sc + (j ? (Math.random() - 0.5) * 3 : 0), y: oy + data.pts[k + 1] * sc + (j ? (Math.random() - 0.5) * 3 : 0), r: data.pts[k + 2] };
    } };
  }
  function bandLayout() {
    var A = area(), bands = data.bands, total = data.n_sal || 1, mx = 1;
    bands.forEach(function (b) { if (b.n > mx) mx = b.n; });
    var cw = A.w / bands.length, base = A.y + A.h - 34, quota = [], acc = 0;
    bands.forEach(function (b) { acc += Math.round(N * b.n / total); quota.push(acc); });
    return { geo: { cw: cw, base: base, A: A, mx: mx }, at: function (i) {
      var b = 0; while (b < quota.length - 1 && i >= quota[b]) b++;
      var hgt = (bands[b].n / mx) * (A.h - 70), x = A.x + b * cw + cw * 0.14 + Math.random() * cw * 0.72;
      return { x: x, y: base - Math.random() * Math.max(hgt, 2), b: b, hgt: hgt };
    } };
  }
  function ringLayout() {
    var A = area(), cx = A.x + A.w / 2, cy = A.y + A.h / 2, R = Math.min(A.w, A.h) * 0.3, secs = data.sectors, total = 0;
    secs.forEach(function (s) { total += s.c; });
    var arcs = [], a0 = -Math.PI / 2, gap = 0.035;
    secs.forEach(function (s) { var sw = (s.c / (total || 1)) * (Math.PI * 2 - gap * secs.length); arcs.push({ a0: a0, a1: a0 + sw, mid: a0 + sw / 2, s: s }); a0 += sw + gap; });
    var quota = [], acc = 0;
    secs.forEach(function (s) { acc += Math.round(N * s.c / (total || 1)); quota.push(acc); });
    return { geo: { cx: cx, cy: cy, R: R, arcs: arcs }, at: function (i) {
      var k = 0; while (k < quota.length - 1 && i >= quota[k]) k++;
      var arc = arcs[k], a = arc.a0 + Math.random() * (arc.a1 - arc.a0), r = R + (Math.random() - 0.5) * R * 0.26;
      return { x: cx + Math.cos(a) * r, y: cy + Math.sin(a) * r, a: a, r: r, k: k, c: arc.s.col };
    } };
  }
  function retarget(state, silent) {
    mode = state;
    var now = performance.now();
    layout = state === 0 ? mapLayout() : state === 1 ? bandLayout() : ringLayout();
    for (var i = 0; i < N; i++) {
      var p = P[i], t = layout.at(i);
      p.sx = p.x; p.sy = p.y; p.tx = t.x; p.ty = t.y; p.a = t.a || 0; p.r = t.r || 0; p.k = t.k || 0; p.b = t.b || 0; p.hgt = t.hgt || 0; p.rg = t.r != null && state === 0 ? t.r : p.rg;
      p.t0 = silent ? 0 : now + (i / N) * 380; p.dur = 620 + (i % 7) * 30;
      if (state === 2 && t.c) p.c = t.c;
      if (silent) { p.x = t.x; p.y = t.y; }
    }
    start();
  }
  function lerp(p, now) {
    if (!p.t0) return true;
    var u = (now - p.t0) / p.dur;
    if (u >= 1) { p.t0 = 0; p.x = p.tx; p.y = p.ty; return true; }
    if (u > 0) { var e = G.easeOutQuart(u); p.x = p.sx + (p.tx - p.sx) * e; p.y = p.sy + (p.ty - p.sy) * e; }
    return false;
  }
  function text(s, x, y, opts) {
    ctx.font = opts.font || '600 12px "Nunito", sans-serif'; ctx.fillStyle = opts.color || T.ink; ctx.textAlign = opts.align || 'center'; ctx.textBaseline = 'middle';
    ctx.globalAlpha = opts.alpha == null ? 1 : opts.alpha; ctx.fillText(s, x, y);
  }
  /* Draw a lozenge behind a label so it stays legible over the particles. */
  function chip(s, x, y, opts) {
    ctx.font = opts.font || '600 12px "Nunito", sans-serif';
    var w = ctx.measureText(s).width + 14, h = opts.h || 22, ax = opts.align === 'left' ? x : opts.align === 'right' ? x - w : x - w / 2;
    ax = Math.max(10, Math.min(W - 10 - w, ax)); /* never off-canvas */
    ctx.globalAlpha = opts.alpha == null ? 1 : opts.alpha; ctx.fillStyle = opts.bg || T.chip;
    ctx.beginPath(); ctx.roundRect ? ctx.roundRect(ax, y - h / 2, w, h, h / 2) : ctx.rect(ax, y - h / 2, w, h); ctx.fill();
    text(s, ax + w / 2, y + 0.5, { font: opts.font, color: opts.color, alpha: opts.alpha });
  }

  function frameCanvas(now) {
    if (!running) return;
    ctx.globalAlpha = 1; ctx.fillStyle = 'rgba(' + T.bg.join(',') + ',0.3)'; ctx.fillRect(0, 0, W, H);
    var i, p, lp = Math.min(1, Math.max(0, scrub.t - SEQ.indexOf(mode) + 0.5)); /* 0 → 1 while this state slides in and holds */
    if (mode === 0) {
      var lit = Math.floor(lp * 1.7 * regionsByCount.length), g = layout.geo;
      for (i = 0; i < N; i++) {
        p = P[i]; var done = lerp(p, now), rk = litRank[p.rg];
        var on = rk != null && rk < lit;
        ctx.fillStyle = on ? T.lit : T.dim; ctx.globalAlpha = on ? 0.95 : T.dimA;
        if (done) { p.x += Math.sin(now * 0.001 + p.ph) * 0.08; p.y += Math.cos(now * 0.0013 + p.ph) * 0.08; }
        ctx.fillRect(p.x - PX / 2, p.y - PX / 2, PX, PX);
      }
      for (var r = 0; r < Math.min(lit, regionsByCount.length); r++) {
        var reg = data.regions[regionsByCount[r].i], top = r < (narrow.matches ? 3 : 6);
        var lx = g.ox + reg.x * g.sc, ly = g.oy + reg.y * g.sc;
        chip(top ? reg.n + ' ' + reg.c : String(reg.c), lx, ly, { font: top ? '700 12px "Nunito", sans-serif' : '700 11px "Nunito", sans-serif', color: top ? T.onLime : T.ink, bg: top ? LIME : T.chip, h: top ? 22 : 18 });
      }
    } else if (mode === 1) {
      var gb = layout.geo;
      for (i = 0; i < N; i++) {
        p = P[i];
        if (lerp(p, now)) { p.y += 0.35 + (i % 5) * 0.08; if (p.y > gb.base) p.y = gb.base - Math.max(p.hgt, 2); }
        ctx.fillStyle = T.dot; ctx.globalAlpha = 0.8; ctx.fillRect(p.x - PX / 2, p.y - PX / 2, PX, PX);
      }
      ctx.globalAlpha = 0.5; ctx.strokeStyle = T.line; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(gb.A.x, gb.base + 4); ctx.lineTo(gb.A.x + gb.A.w, gb.base + 4); ctx.stroke();
      data.bands.forEach(function (b, k) {
        var cx = gb.A.x + k * gb.cw + gb.cw / 2, hgt = (b.n / gb.mx) * (gb.A.h - 70);
        text(b.l, cx, gb.base + 18, { color: T.muted, font: '600 11px "Nunito", sans-serif', alpha: Math.min(1, lp * 2) });
        if (b.n) chip(String(b.n), cx, gb.base - hgt - 16, { font: '700 12px "Nunito", sans-serif', color: T.onLime, bg: LIME, alpha: Math.min(1, lp * 2), h: 20 });
      });
    } else {
      var gr = layout.geo;
      for (i = 0; i < N; i++) {
        p = P[i];
        if (lerp(p, now)) { p.a += 0.0007 + (i % 3) * 0.0002; p.x = gr.cx + Math.cos(p.a) * p.r; p.y = gr.cy + Math.sin(p.a) * p.r; }
        ctx.fillStyle = p.c; ctx.globalAlpha = 0.9; ctx.fillRect(p.x - PX / 2, p.y - PX / 2, PX, PX);
      }
      gr.arcs.forEach(function (arc) {
        var lx = gr.cx + Math.cos(arc.mid) * gr.R * 1.34, ly = gr.cy + Math.sin(arc.mid) * gr.R * 1.34, left = Math.cos(arc.mid) < -0.15, right = Math.cos(arc.mid) > 0.15;
        var name = arc.s.n.length > 22 ? arc.s.n.replace(/ & .*$/, '') : arc.s.n;
        chip(name + '  ' + arc.s.c, lx, ly, { align: left ? 'right' : right ? 'left' : 'center', font: '700 11px "Nunito", sans-serif', color: T.ink, bg: T.chip, alpha: Math.min(1, lp * 2), h: 20 });
      });
      chip(data.n_jobs + ' roles', gr.cx, gr.cy, { font: '700 14px "Nunito", sans-serif', color: T.onLime, bg: LIME, alpha: Math.min(1, lp * 2), h: 26 });
    }
    ctx.globalAlpha = 1;
    raf = requestAnimationFrame(frameCanvas);
  }
  function start() { if (!running && visible && !doc.hidden) { running = true; raf = requestAnimationFrame(frameCanvas); } }
  function stop() { running = false; cancelAnimationFrame(raf); }
  new IntersectionObserver(function (es) { es.forEach(function (e) { visible = e.isIntersecting; if (visible) start(); else stop(); }); }, { threshold: 0.02 }).observe(stage);
  doc.addEventListener('visibilitychange', function () { if (doc.hidden) stop(); else start(); });
  var rt; window.addEventListener('resize', function () { clearTimeout(rt); rt = setTimeout(function () { span(); size(); cur = -1; frame(); }, 120); });
  window.addEventListener('scroll', schedule, { passive: true });
  if (reduce.addEventListener) reduce.addEventListener('change', function () { if (reduce.matches) { stop(); staticFilm(); } });

  /* Keyboard: tabbing into a state's copy scrolls the film to that state. */
  stage.addEventListener('focusin', function (e) {
    var st = e.target.closest('[data-film-state]');
    if (!st) return;
    var k = SEQ.indexOf(+st.getAttribute('data-film-state'));
    if (k >= 0 && SEQ[k] !== cur) window.scrollTo({ top: topFor(k), behavior: 'instant' });
  });

  span(); size(); show(0); retarget(0, true); frame();
  /* Capture and verification hook: ?film=N scrolls to state N once laid out. */
  var want = (window.location.search.match(/[?&]film=(\d)/) || [])[1];
  if (want != null) {
    var k0 = SEQ.indexOf(+want);
    if (k0 >= 0) setTimeout(function () { window.scrollTo({ top: topFor(k0), behavior: 'instant' }); frame(); }, 60);
  }
  window.GJFilm = { state: function () { return cur; }, seq: function () { return SEQ.slice(); }, particles: function () { return N; }, top: topFor };
})();
