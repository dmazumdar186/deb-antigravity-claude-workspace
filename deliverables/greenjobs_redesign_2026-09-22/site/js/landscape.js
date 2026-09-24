'use strict';
(function () {
var host = document.querySelector('[data-landscape]');
if (!host) return;
var reduce = window.matchMedia('(prefers-reduced-motion: reduce)'), fine = window.matchMedia('(pointer: fine)');
var c = document.createElement('canvas'); c.className = 'hero__canvas'; c.setAttribute('aria-hidden', 'true');
var ctx = c.getContext ? c.getContext('2d', { alpha: false }) : null;
if (!ctx) return;
host.insertBefore(c, host.firstChild); host.classList.add('has-canvas');
var sky = host.getAttribute('data-sky') || 'ie';
var W = 0, H = 0, dpr = 1, PAD = 90, L = {}, raf = 0, running = false, visible = true, t0 = 0, last = 0;
var px = 0, py = 0, tx = 0, ty = 0, scroll = 0, video = host.querySelector('video');
var TURB = [[0.16, 62, 0.9], [0.24, 78, 1.15], [0.33, 56, 0.75], [0.71, 70, 1.0], [0.8, 52, 0.85]];
var birds = { t: -1, x: 0, y: 0 }, T = {};
function tone() {
var dark = document.documentElement.getAttribute('data-theme') === 'dark';
T = dark ? {
sky: ['#1e1a17', '#2b2420', '#3a2f27'], sun: ['#d99a1c', '#c65d3b'], glow: 'rgba(217,154,28,.16)', cloud: 'rgba(243,236,225,.08)',
far: '#332f2a', mid: '#3d4436', near: '#4a5642', nearest: '#56654d', haze: 'rgba(30,26,23,.3)', river: '#4a6f8c', glint: 'rgba(243,236,225,.35)',
tower: '#c9bfb2', blade: '#f3ece1', panel: '#3f7ea6', frame: '#1e1a17', tree: '#2e3d2c', bird: 'rgba(243,236,225,.6)'
} : {
sky: ['#f6f0e6', sky === 'uk' ? '#f1ebdd' : '#fbeed6', sky === 'uk' ? '#e9e2d0' : '#f7e3c0'], sun: ['#d99a1c', '#c65d3b'], glow: 'rgba(217,154,28,.22)', cloud: 'rgba(255,253,249,.85)',
far: '#e2d5ba', mid: '#c6cfae', near: '#a6ba94', nearest: '#87a07a', haze: 'rgba(246,240,230,.3)', river: '#8fb4cc', glint: 'rgba(255,253,249,.95)',
tower: '#fffdf9', blade: '#fffdf9', panel: '#3f7ea6', frame: '#2a2521', tree: '#4f6d4a', bird: 'rgba(42,37,33,.55)'
};
}
function ridge(x, seed, amp, base) {
return base + Math.sin(x * 0.0021 + seed) * amp + Math.sin(x * 0.0057 + seed * 1.7) * amp * 0.35 + Math.cos(x * 0.011 + seed * 2.3) * amp * 0.12;
}
function layer(draw) {
var o = document.createElement('canvas'); o.width = Math.round((W + PAD * 2) * dpr); o.height = Math.round(H * dpr);
var g = o.getContext('2d'); g.setTransform(dpr, 0, 0, dpr, 0, 0); g.translate(PAD, 0); draw(g); return o;
}
function hill(g, seed, amp, base, fill, haze) {
g.beginPath(); g.moveTo(-PAD, H + 4);
for (var x = -PAD; x <= W + PAD; x += 6) g.lineTo(x, ridge(x, seed, amp, base));
g.lineTo(W + PAD, H + 4); g.closePath(); g.fillStyle = fill; g.fill();
if (haze) { g.fillStyle = haze; g.fill(); }
}
function build() {
var farB = H * 0.56, midB = H * 0.66, nearB = H * 0.76, nstB = H * 0.86;
L.far = layer(function (g) { hill(g, 1.3, H * 0.05, farB, T.far, T.haze); });
L.mid = layer(function (g) {
hill(g, 4.1, H * 0.045, midB, T.mid, null);
TURB.forEach(function (t) {
var x = t[0] * W, y = ridge(x, 4.1, H * 0.045, midB), h = t[1] * (H / 720);
g.strokeStyle = T.tower; g.lineWidth = 3; g.lineCap = 'round'; g.beginPath(); g.moveTo(x, y + 2); g.lineTo(x, y - h); g.stroke();
g.strokeStyle = T.frame; g.globalAlpha = 0.28; g.lineWidth = 1; g.beginPath(); g.moveTo(x - 1.5, y + 2); g.lineTo(x - 1.5, y - h); g.stroke(); g.globalAlpha = 1;
});
g.strokeStyle = T.river; g.lineCap = 'round';
var rx = W * 0.58, ry = midB + 8;
for (var k = 0; k < 6; k++) {
g.lineWidth = 6 + k * 6; g.globalAlpha = 0.9;
g.beginPath(); g.moveTo(rx, ry);
g.bezierCurveTo(W * 0.5, H * 0.72, W * 0.36, H * 0.78, W * 0.3, H * 0.84);
g.bezierCurveTo(W * 0.25, H * 0.9, W * 0.2, H * 0.96, W * 0.16, H + 10);
g.stroke(); rx += 0.5; ry += 4;
}
g.globalAlpha = 1;
});
L.near = layer(function (g) {
hill(g, 7.7, H * 0.04, nearB, T.near, null);
var rows = 4, cols = 9, x0 = W * 0.6, dx = Math.max(14, W * 0.028), ph = 7, pw = dx * 0.82;
for (var r = 0; r < rows; r++) for (var i = 0; i < cols; i++) {
var x = x0 + i * dx + r * 6, y = ridge(x, 7.7, H * 0.04, nearB) + 10 + r * 11;
g.fillStyle = T.frame; g.fillRect(x - 1, y - ph - 1, pw + 2, ph + 2);
g.fillStyle = T.panel; g.fillRect(x, y - ph, pw, ph);
g.fillStyle = 'rgba(255,255,255,.22)'; g.fillRect(x, y - ph, pw, 2);
}
});
L.nearest = layer(function (g) {
hill(g, 2.6, H * 0.035, nstB, T.nearest, null);
for (var x = -PAD + 12; x < W + PAD; x += 22 + (Math.abs(x * 7) % 17)) {
var y = ridge(x, 2.6, H * 0.035, nstB), r = 5 + (Math.abs(x * 13) % 7);
g.fillStyle = T.tree; g.beginPath(); g.arc(x, y - r * 0.6, r, 0, 6.283); g.fill();
g.fillStyle = 'rgba(255,253,249,.12)'; g.beginPath(); g.arc(x - r * 0.3, y - r * 0.9, r * 0.5, 0, 6.283); g.fill();
}
});
L.grad = ctx.createLinearGradient(0, 0, 0, H * 0.7);
L.grad.addColorStop(0, T.sky[0]); L.grad.addColorStop(0.55, T.sky[1]); L.grad.addColorStop(1, T.sky[2]);
}
function size() {
dpr = Math.min(window.devicePixelRatio || 1, 2);
W = host.clientWidth; H = host.clientHeight;
c.width = Math.round(W * dpr); c.height = Math.round(H * dpr);
c.style.width = W + 'px'; c.style.height = H + 'px';
ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
build();
}
function lerpColor(a, b, u) {
var A = parseInt(a.slice(1), 16), B = parseInt(b.slice(1), 16), r = (A >> 16) + (((B >> 16) - (A >> 16)) * u), g = ((A >> 8) & 255) + ((((B >> 8) & 255) - ((A >> 8) & 255)) * u), bl = (A & 255) + (((B & 255) - (A & 255)) * u);
return 'rgb(' + (r | 0) + ',' + (g | 0) + ',' + (bl | 0) + ')';
}
function cloud(x, y, s, a) {
ctx.globalAlpha = a; ctx.fillStyle = T.cloud;
[[0, 0, 26], [22, -8, 20], [44, 0, 24], [18, 8, 18], [62, 6, 16]].forEach(function (b) { ctx.beginPath(); ctx.ellipse(x + b[0] * s, y + b[1] * s, b[2] * s, b[2] * s * 0.62, 0, 0, 6.283); ctx.fill(); });
ctx.globalAlpha = 1;
}
function draw(now) {
var t = (now - t0) / 1000, u = Math.min(1, scroll / Math.max(1, H)), sunT = Math.min(1, u * 1.6);
tx += (px - tx) * 0.06; ty += (py - ty) * 0.06;
ctx.fillStyle = L.grad; ctx.fillRect(0, 0, W, H);
var sx = W * 0.8 + tx * 2, sy = H * 0.17 + scroll * 0.06 + ty * 2, sr = Math.max(24, Math.min(64, W * 0.036));
var glow = ctx.createRadialGradient(sx, sy, sr * 0.6, sx, sy, sr * 4.2);
glow.addColorStop(0, T.glow); glow.addColorStop(1, 'rgba(217,154,28,0)');
ctx.fillStyle = glow; ctx.fillRect(0, 0, W, H);
ctx.fillStyle = lerpColor(T.sun[0], T.sun[1], sunT); ctx.beginPath(); ctx.arc(sx, sy, sr, 0, 6.283); ctx.fill();
cloud(((W + 300) - ((t * 6 + 120) % (W + 300))) + tx * 3, H * 0.12 + ty * 2, 1.1, 0.9);
cloud(((W + 300) - ((t * 4 + 620) % (W + 300))) + tx * 2, H * 0.24 + ty * 1.5, 0.8, 0.75);
cloud(((W + 300) - ((t * 8 + 380) % (W + 300))) + tx * 4, H * 0.06 + ty * 2, 0.7, 0.6);
ctx.drawImage(L.far, -PAD + tx * 4, scroll * 0.12 + ty * 2, W + PAD * 2, H);
ctx.drawImage(L.mid, -PAD + tx * 8, scroll * 0.22 + ty * 4, W + PAD * 2, H);
var midB = H * 0.66, oy = scroll * 0.22 + ty * 4, ox = tx * 8;
ctx.strokeStyle = T.blade; ctx.lineCap = 'round'; ctx.lineWidth = 2.4;
TURB.forEach(function (tb, i) {
var x = tb[0] * W + ox, y = ridge(tb[0] * W, 4.1, H * 0.045, midB) - tb[1] * (H / 720) + oy, len = tb[1] * (H / 720) * 0.62, a = t * tb[2] + i;
for (var k = 0; k < 3; k++) { var ang = a + k * 2.0944; ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + Math.cos(ang) * len, y + Math.sin(ang) * len); ctx.stroke(); }
ctx.fillStyle = T.tower; ctx.beginPath(); ctx.arc(x, y, 3, 0, 6.283); ctx.fill();
});
ctx.save(); ctx.translate(ox, oy); ctx.strokeStyle = T.glint; ctx.lineWidth = 2; ctx.setLineDash([10, 70]); ctx.lineDashOffset = -t * 18; ctx.globalAlpha = 0.7;
ctx.beginPath(); ctx.moveTo(W * 0.58, midB + 14); ctx.bezierCurveTo(W * 0.5, H * 0.72, W * 0.36, H * 0.78, W * 0.3, H * 0.84); ctx.bezierCurveTo(W * 0.25, H * 0.9, W * 0.2, H * 0.96, W * 0.16, H + 10); ctx.stroke(); ctx.restore();
ctx.drawImage(L.near, -PAD + tx * 12, scroll * 0.34 + ty * 6, W + PAD * 2, H);
ctx.drawImage(L.nearest, -PAD + tx * 16, scroll * 0.46 + ty * 8, W + PAD * 2, H);
if (birds.t < 0 && Math.floor(t) % 18 === 4) { birds.t = t; birds.y = H * (0.1 + Math.random() * 0.2); }
if (birds.t >= 0) {
var bu = (t - birds.t) / 14, bx = -40 + bu * (W + 80), flap = Math.sin(t * 6) * 3;
ctx.strokeStyle = T.bird; ctx.lineWidth = 1.6;
[[0, 0], [18, 7]].forEach(function (o) { var x = bx + o[0], y = birds.y + o[1] + Math.sin(bu * 6 + o[0]) * 6; ctx.beginPath(); ctx.moveTo(x - 7, y + flap); ctx.quadraticCurveTo(x, y - 2, x, y + 1); ctx.quadraticCurveTo(x, y - 2, x + 7, y + flap); ctx.stroke(); });
if (bu >= 1) birds.t = -1;
}
}
var cost = 0, frames = 0;
function frame(now) {
if (!running) return;
if (now - last >= 16) { last = now; var a = performance.now(); draw(now); cost += performance.now() - a; frames++; }
raf = requestAnimationFrame(frame);
}
function start() { if (!running && visible && !document.hidden && !reduce.matches && !host.classList.contains('is-playing')) { running = true; t0 = t0 || performance.now(); raf = requestAnimationFrame(frame); } }
function stop() { running = false; cancelAnimationFrame(raf); }
function still() { stop(); draw(performance.now()); }
host.parentNode.addEventListener('pointermove', function (e) { if (!fine.matches) return; var r = host.getBoundingClientRect(); px = (e.clientX - r.left) / r.width - 0.5; py = (e.clientY - r.top) / r.height - 0.5; }, { passive: true });
host.parentNode.addEventListener('pointerleave', function () { px = py = 0; });
window.addEventListener('scroll', function () { scroll = Math.max(0, Math.min(H, window.scrollY)); if (reduce.matches) still(); }, { passive: true });
var rt; window.addEventListener('resize', function () { clearTimeout(rt); rt = setTimeout(function () { size(); if (reduce.matches) still(); }, 120); });
new IntersectionObserver(function (es) { es.forEach(function (e) { visible = e.isIntersecting; if (visible) { start(); if (video && host.classList.contains('is-playing')) video.play().catch(function () {}); } else { stop(); if (video) video.pause(); } }); }, { threshold: 0.02 }).observe(host);
document.addEventListener('visibilitychange', function () { if (document.hidden) stop(); else start(); });
if (reduce.addEventListener) reduce.addEventListener('change', function () { if (reduce.matches) { still(); if (video) video.pause(); } else start(); });
new MutationObserver(function () { tone(); build(); if (reduce.matches) still(); }).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
if (video) {
var conn = navigator.connection, save = !!(conn && conn.saveData);
if (save || reduce.matches) { video.removeAttribute('autoplay'); video.preload = 'none'; [].slice.call(video.querySelectorAll('source')).forEach(function (s) { s.remove(); }); video.load(); host.classList.add('is-playing'); stop(); }
else {
var takeOver = function () { host.classList.add('is-playing'); stop(); };
if (video.readyState >= 2) takeOver(); else video.addEventListener('loadeddata', takeOver, { once: true });
video.play().catch(function () {  });
}
}
tone(); size();
if (reduce.matches) still(); else start();
window.GJLandscape = { running: function () { return running; }, canvas: c, ms: function () { return frames ? cost / frames : 0; } };
})();
