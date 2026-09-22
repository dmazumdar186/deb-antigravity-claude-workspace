'use strict';
(function () {
var host = document.querySelector('[data-wind]');
if (!host || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
var colors = ['#b4e33d', '#5aa9e6', '#f2b544', '#d9774f', '#2fbf9f'];
try { colors = JSON.parse(host.getAttribute('data-colors')) || colors; } catch (e) {  }
var c = document.createElement('canvas'); c.setAttribute('aria-hidden', 'true');
host.appendChild(c);
var ctx = c.getContext('2d', { alpha: true }), W = 0, H = 0, dpr = 1, P = [], N = 0, t = 0, raf = 0, running = false;
var px = -1e4, py = -1e4, pv = 0;
function size() {
dpr = Math.min(window.devicePixelRatio || 1, 2);
W = host.clientWidth; H = host.clientHeight;
c.width = Math.round(W * dpr); c.height = Math.round(H * dpr);
c.style.width = W + 'px'; c.style.height = H + 'px';
ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
N = Math.round(Math.min(900, Math.max(220, W * H / 3200)));
P.length = 0;
for (var i = 0; i < N; i++) P.push(spawn({}, true));
ctx.fillStyle = 'rgba(12,26,18,1)'; ctx.fillRect(0, 0, W, H);
}
function spawn(p, anywhere) {
p.x = Math.random() * W; p.y = anywhere ? Math.random() * H : (Math.random() < 0.5 ? -4 : Math.random() * H);
p.px = p.x; p.py = p.y; p.life = 80 + Math.random() * 220; p.c = colors[(Math.random() * colors.length) | 0];
p.s = 0.6 + Math.random() * 1.2; return p;
}
function field(x, y, tt) {
var a = Math.sin(x * 0.0021 + tt * 0.00035) + Math.cos(y * 0.0017 - tt * 0.0002) * 0.9
+ Math.sin((x + y) * 0.0009 + tt * 0.0005) * 0.7;
return a * 1.15 + 0.35;
}
function frame(now) {
if (!running) return;
t = now;
ctx.fillStyle = 'rgba(12,26,18,0.06)'; ctx.fillRect(0, 0, W, H);
ctx.lineWidth = 1.5; ctx.lineCap = 'round';
for (var i = 0; i < N; i++) {
var p = P[i], ang = field(p.x, p.y, t);
var dx = p.x - px, dy = p.y - py, d2 = dx * dx + dy * dy;
var vx = Math.cos(ang) * p.s, vy = Math.sin(ang) * p.s;
if (d2 < 40000) { var f = (1 - d2 / 40000) * (0.9 + pv); var d = Math.sqrt(d2) + 0.01; vx += dx / d * f * 2.2; vy += dy / d * f * 2.2; }
p.px = p.x; p.py = p.y; p.x += vx; p.y += vy; p.life--;
ctx.strokeStyle = p.c; ctx.globalAlpha = 0.75;
ctx.beginPath(); ctx.moveTo(p.px, p.py); ctx.lineTo(p.x, p.y); ctx.stroke();
if (p.life <= 0 || p.x < -6 || p.x > W + 6 || p.y < -6 || p.y > H + 6) spawn(p, false);
}
ctx.globalAlpha = 1; pv *= 0.94;
raf = requestAnimationFrame(frame);
}
function start() { if (!running) { running = true; raf = requestAnimationFrame(frame); } }
function stop() { running = false; cancelAnimationFrame(raf); }
function point(x, y) { var r = host.getBoundingClientRect(); px = x - r.left; py = y - r.top; pv = Math.min(1.5, pv + 0.25); }
host.addEventListener('pointermove', function (e) { point(e.clientX, e.clientY); }, { passive: true });
host.addEventListener('pointerleave', function () { px = py = -1e4; });
host.addEventListener('touchmove', function (e) { if (e.touches[0]) point(e.touches[0].clientX, e.touches[0].clientY); }, { passive: true });
var rt; window.addEventListener('resize', function () { clearTimeout(rt); rt = setTimeout(size, 120); });
new IntersectionObserver(function (es) { es.forEach(function (e) { if (e.isIntersecting) start(); else stop(); }); }, { threshold: 0.02 }).observe(host);
document.addEventListener('visibilitychange', function () { if (document.hidden) stop(); else start(); });
size(); start();
})();
