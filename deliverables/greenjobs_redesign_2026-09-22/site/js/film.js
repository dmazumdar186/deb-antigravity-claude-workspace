'use strict';
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
function seq() { return narrow.matches ? [0, 1, 4] : [0, 1, 2, 3, 4]; }
function staticFilm() { host.classList.add('film--static'); show(0); }
if (reduce.matches || !data || !window.HTMLCanvasElement || !doc.createElement('canvas').getContext) { staticFilm(); return; }
var SEQ = seq(), LAST = SEQ.length - 1, scrub = { t: 0, g: 0, show: 0 };
function span() { host.style.setProperty('--film-span', String(SEQ.length)); host.classList.toggle('film--m', narrow.matches); }
function topFor(k) {
var rect = host.getBoundingClientRect(), vh = window.innerHeight;
return window.scrollY + rect.top + (k * 0.92 / LAST) * (rect.height - vh) + (k === LAST ? (rect.height - vh) * 0.08 : 0);
}
function frame() {
var rect = host.getBoundingClientRect(), vh = window.innerHeight;
scrub = G.filmScrub(-rect.top / Math.max(1, rect.height - vh), LAST);
doc.body.classList.toggle('film-pinned', rect.bottom > vh - 2);
var idx = SEQ[scrub.show];
if (idx !== cur) { show(idx); retarget(idx); }
steps.forEach(function (el) { var k = SEQ.indexOf(+el.getAttribute('data-film-step')); el.style.setProperty('--fill', k < 0 ? '0' : scrub.fills[k].toFixed(3)); });
}
var scheduled = false;
function schedule() { if (scheduled) return; scheduled = true; requestAnimationFrame(function () { scheduled = false; frame(); }); }
var c = doc.createElement('canvas'); c.setAttribute('aria-hidden', 'true'); cwrap.appendChild(c);
var ctx = c.getContext('2d', { alpha: true }), W = 0, H = 0, dpr = 1, P = [], N = 0, raf = 0, running = false, visible = true;
var px = -1e4, py = -1e4, pv = 0, layout = null, mode = 0;
var BG = [12, 26, 18], LIME = '#b4e33d', DIM = '#2f5a3f', INK = '#eef2ea', MUTED = '#aebfb2';
var colors = ['#b4e33d', '#5aa9e6', '#f2b544', '#d9774f', '#2fbf9f'];
try { colors = JSON.parse(host.querySelector('[data-colors]') ? host.querySelector('[data-colors]').getAttribute('data-colors') : 'null') || colors; } catch (e) {  }
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
while (P.length < N) P.push(spawn({}, true));
P.length = N;
ctx.fillStyle = 'rgb(' + BG.join(',') + ')'; ctx.fillRect(0, 0, W, H);
layout = null;
if (cur >= 0) retarget(cur, true);
}
function spawn(p, anywhere) {
p.x = Math.random() * W; p.y = anywhere ? Math.random() * H : (Math.random() < 0.5 ? -4 : Math.random() * H);
p.px = p.x; p.py = p.y; p.life = 80 + Math.random() * 220; p.c = colors[(Math.random() * colors.length) | 0];
p.s = 0.6 + Math.random() * 1.2; p.tx = p.x; p.ty = p.y; p.t0 = 0; p.a = 0; p.r = 0; p.k = 0; p.ph = Math.random() * 6.283; return p;
}
function field(x, y, tt) {
var a = Math.sin(x * 0.0021 + tt * 0.00035) + Math.cos(y * 0.0017 - tt * 0.0002) * 0.9 + Math.sin((x + y) * 0.0009 + tt * 0.0005) * 0.7;
return a * 1.15 + 0.35;
}
function area() {
return narrow.matches ? { x: 20, y: 64, w: W - 40, h: H * 0.5 - 40 } : { x: W * 0.5, y: 84, w: W * 0.5 - 40, h: H - 170 };
}
function mapLayout() {
var A = area(), vw = data.vb[0], vh = data.vb[1], sc = Math.min(A.w / vw, A.h / vh), ox = A.x + (A.w - vw * sc) / 2, oy = A.y + (A.h - vh * sc) / 2;
var geo = { sc: sc, ox: ox, oy: oy };
return { geo: geo, at: function (i) {
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
function calmLayout() {
return { geo: {}, at: function () { return { x: Math.random() * W, y: Math.random() * H }; } };
}
function retarget(state, silent) {
mode = state;
var now = performance.now();
layout = state === 1 ? mapLayout() : state === 2 ? bandLayout() : state === 3 ? ringLayout() : calmLayout();
for (var i = 0; i < N; i++) {
var p = P[i];
if (state === 0) { p.t0 = 0; p.life = 40 + Math.random() * 200; continue; }
var t = layout.at(i);
p.sx = p.x; p.sy = p.y; p.tx = t.x; p.ty = t.y; p.a = t.a || 0; p.r = t.r || 0; p.k = t.k || 0; p.b = t.b || 0; p.hgt = t.hgt || 0; p.rg = t.r != null && state === 1 ? t.r : p.rg;
p.t0 = silent ? 0 : now + (i / N) * 380; p.dur = 620 + (i % 7) * 30;
if (state === 3 && t.c) p.c = t.c;
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
ctx.font = opts.font || '600 12px "Public Sans", sans-serif'; ctx.fillStyle = opts.color || INK; ctx.textAlign = opts.align || 'center'; ctx.textBaseline = 'middle';
ctx.globalAlpha = opts.alpha == null ? 1 : opts.alpha; ctx.fillText(s, x, y);
}
function chip(s, x, y, opts) {
ctx.font = opts.font || '600 12px "Public Sans", sans-serif';
var w = ctx.measureText(s).width + 14, h = opts.h || 22, ax = opts.align === 'left' ? x : opts.align === 'right' ? x - w : x - w / 2;
ax = Math.max(10, Math.min(W - 10 - w, ax));
ctx.globalAlpha = opts.alpha == null ? 1 : opts.alpha; ctx.fillStyle = opts.bg || 'rgba(12,26,18,.82)';
ctx.beginPath(); ctx.roundRect ? ctx.roundRect(ax, y - h / 2, w, h, h / 2) : ctx.rect(ax, y - h / 2, w, h); ctx.fill();
text(s, ax + w / 2, y + 0.5, { font: opts.font, color: opts.color, alpha: opts.alpha });
}
function frameCanvas(now) {
if (!running) return;
var fade = mode === 0 ? 0.07 : mode === 4 ? 0.12 : 0.26;
ctx.globalAlpha = 1; ctx.fillStyle = 'rgba(' + BG.join(',') + ',' + fade + ')'; ctx.fillRect(0, 0, W, H);
var i, p, lp = Math.min(1, Math.max(0, scrub.t - SEQ.indexOf(mode) + 0.5));
if (mode === 0 || mode === 4) {
ctx.lineWidth = mode === 0 ? 1.5 : 1; ctx.lineCap = 'round';
for (i = 0; i < N; i++) {
p = P[i];
var settled = lerp(p, now);
if (settled) {
var ang = field(p.x, p.y, now), sp = mode === 0 ? p.s : p.s * 0.22;
var dx = p.x - px, dy = p.y - py, d2 = dx * dx + dy * dy, vx = Math.cos(ang) * sp, vy = Math.sin(ang) * sp;
if (d2 < 40000) { var f = (1 - d2 / 40000) * (0.9 + pv), d = Math.sqrt(d2) + 0.01; vx += dx / d * f * 2.2; vy += dy / d * f * 2.2; }
p.px = p.x; p.py = p.y; p.x += vx; p.y += vy; p.life--;
if (p.life <= 0 || p.x < -6 || p.x > W + 6 || p.y < -6 || p.y > H + 6) { spawn(p, mode === 4); p.px = p.x; p.py = p.y; }
} else { p.px = p.x; p.py = p.y; }
ctx.strokeStyle = p.c; ctx.globalAlpha = mode === 0 ? 0.75 : 0.28;
ctx.beginPath(); ctx.moveTo(p.px, p.py); ctx.lineTo(p.x, p.y); ctx.stroke();
}
pv *= 0.94;
} else if (mode === 1) {
var lit = Math.floor(lp * 1.7 * regionsByCount.length), g = layout.geo;
for (i = 0; i < N; i++) {
p = P[i]; var done = lerp(p, now), rk = litRank[p.rg];
var on = rk != null && rk < lit;
ctx.fillStyle = on ? LIME : DIM; ctx.globalAlpha = on ? 0.9 : 0.55;
if (done) { p.x += Math.sin(now * 0.001 + p.ph) * 0.08; p.y += Math.cos(now * 0.0013 + p.ph) * 0.08; }
ctx.fillRect(p.x - 1, p.y - 1, 2.2, 2.2);
}
for (var r = 0; r < Math.min(lit, regionsByCount.length); r++) {
var reg = data.regions[regionsByCount[r].i], top = r < (narrow.matches ? 3 : 6);
var lx = g.ox + reg.x * g.sc, ly = g.oy + reg.y * g.sc;
chip(top ? reg.n + ' ' + reg.c : String(reg.c), lx, ly, { font: top ? '700 12px "Archivo", sans-serif' : '700 11px "Archivo", sans-serif', color: top ? '#0c1a12' : INK, bg: top ? LIME : 'rgba(12,26,18,.78)', h: top ? 22 : 18 });
}
} else if (mode === 2) {
var gb = layout.geo;
for (i = 0; i < N; i++) {
p = P[i];
if (lerp(p, now)) { p.y += 0.35 + (i % 5) * 0.08; if (p.y > gb.base) p.y = gb.base - Math.max(p.hgt, 2); }
ctx.fillStyle = LIME; ctx.globalAlpha = 0.7; ctx.fillRect(p.x - 1, p.y - 1, 2.2, 2.2);
}
ctx.globalAlpha = 0.5; ctx.strokeStyle = 'rgba(238,242,234,.35)'; ctx.lineWidth = 1;
ctx.beginPath(); ctx.moveTo(gb.A.x, gb.base + 4); ctx.lineTo(gb.A.x + gb.A.w, gb.base + 4); ctx.stroke();
data.bands.forEach(function (b, k) {
var cx = gb.A.x + k * gb.cw + gb.cw / 2, hgt = (b.n / gb.mx) * (gb.A.h - 70);
text(b.l, cx, gb.base + 18, { color: MUTED, font: '600 11px "Public Sans", sans-serif', alpha: Math.min(1, lp * 2) });
if (b.n) chip(String(b.n), cx, gb.base - hgt - 16, { font: '700 12px "Archivo", sans-serif', color: '#0c1a12', bg: LIME, alpha: Math.min(1, lp * 2), h: 20 });
});
} else if (mode === 3) {
var gr = layout.geo;
for (i = 0; i < N; i++) {
p = P[i];
if (lerp(p, now)) { p.a += 0.0007 + (i % 3) * 0.0002; p.x = gr.cx + Math.cos(p.a) * p.r; p.y = gr.cy + Math.sin(p.a) * p.r; }
ctx.fillStyle = p.c; ctx.globalAlpha = 0.85; ctx.fillRect(p.x - 1, p.y - 1, 2.2, 2.2);
}
gr.arcs.forEach(function (arc) {
var lx = gr.cx + Math.cos(arc.mid) * gr.R * 1.34, ly = gr.cy + Math.sin(arc.mid) * gr.R * 1.34, left = Math.cos(arc.mid) < -0.15, right = Math.cos(arc.mid) > 0.15;
var name = arc.s.n.length > 22 ? arc.s.n.replace(/ & .*$/, '') : arc.s.n;
chip(name + '  ' + arc.s.c, lx, ly, { align: left ? 'right' : right ? 'left' : 'center', font: '700 11px "Archivo", sans-serif', color: INK, bg: 'rgba(12,26,18,.78)', alpha: Math.min(1, lp * 2), h: 20 });
});
chip(data.n_jobs + ' roles', gr.cx, gr.cy, { font: '700 14px "Archivo", sans-serif', color: '#0c1a12', bg: LIME, alpha: Math.min(1, lp * 2), h: 26 });
}
ctx.globalAlpha = 1;
raf = requestAnimationFrame(frameCanvas);
}
function start() { if (!running && visible && !doc.hidden) { running = true; raf = requestAnimationFrame(frameCanvas); } }
function stop() { running = false; cancelAnimationFrame(raf); }
function point(x, y) { var r = stage.getBoundingClientRect(); px = x - r.left; py = y - r.top; pv = Math.min(1.5, pv + 0.25); }
stage.addEventListener('pointermove', function (e) { point(e.clientX, e.clientY); }, { passive: true });
stage.addEventListener('pointerleave', function () { px = py = -1e4; });
new IntersectionObserver(function (es) { es.forEach(function (e) { visible = e.isIntersecting; if (visible) start(); else stop(); }); }, { threshold: 0.02 }).observe(stage);
doc.addEventListener('visibilitychange', function () { if (doc.hidden) stop(); else start(); });
var rt; window.addEventListener('resize', function () { clearTimeout(rt); rt = setTimeout(function () { SEQ = seq(); LAST = SEQ.length - 1; span(); size(); cur = -1; frame(); }, 120); });
window.addEventListener('scroll', schedule, { passive: true });
if (reduce.addEventListener) reduce.addEventListener('change', function () { if (reduce.matches) { stop(); staticFilm(); } });
stage.addEventListener('focusin', function (e) {
var st = e.target.closest('[data-film-state]');
if (!st) return;
var k = SEQ.indexOf(+st.getAttribute('data-film-state'));
if (k >= 0 && SEQ[k] !== cur) window.scrollTo({ top: topFor(k), behavior: 'instant' });
});
var skip = host.querySelector('[data-film-skip]');
if (skip) skip.addEventListener('click', function (e) { e.preventDefault(); window.scrollTo({ top: topFor(LAST), behavior: 'instant' }); frame(); var q = doc.getElementById('s-q'); if (q) q.focus({ preventScroll: true }); });
span(); size(); show(0); retarget(0); frame();
var want = (window.location.search.match(/[?&]film=(\d)/) || [])[1];
if (want != null) {
var k0 = SEQ.indexOf(+want);
if (k0 >= 0) setTimeout(function () { window.scrollTo({ top: topFor(k0), behavior: 'instant' }); frame(); }, 60);
}
window.GJFilm = { state: function () { return cur; }, seq: function () { return SEQ.slice(); }, particles: function () { return N; } };
})();
