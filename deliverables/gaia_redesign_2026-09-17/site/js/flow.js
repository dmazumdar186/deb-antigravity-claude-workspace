'use strict';
(function initFlow() {
var root = document.querySelector('[data-flow]');
var M = window.GaiaMotion;
if (!root || !M) return;
var stage = root.querySelector('[data-flow-stage]');
var canvas = root.querySelector('[data-flow-scene]');
var qa = function (sel) { return Array.prototype.slice.call(root.querySelectorAll(sel)); };
var panels = qa('[data-flow-panel]');
var steps = qa('[data-flow-step]');
var COUNT = panels.length;
if (!stage || !canvas || COUNT < 2) return;
var reduce = window.matchMedia('(prefers-reduced-motion: reduce)');
var wide = window.matchMedia('(min-width: 800px)');
var enabled = function () { return wide.matches && !reduce.matches; };
root.style.setProperty('--flow-span', String(COUNT));
var VERTS = 32;
var PI2 = Math.PI * 2;
var profileAt = function (state, i) {
var x = i / (VERTS - 1);
var n = M.hashNoise(i, state) * 2 - 1;
if (state === 0) return 0.638 + Math.sin(x * 3.1 + 0.4) * 0.012 + n * 0.006;
if (state === 1) return 0.602 - Math.sin(x * 2.2 + 0.3) * 0.055 - Math.sin(x * 5.7 + 1.2) * 0.020 + n * 0.008;
if (state === 2) return 0.662 + Math.sin(x * 1.4 + 2.0) * 0.014 + n * 0.005;
if (state === 3) return 0.612 + Math.exp(-Math.pow((x - 0.52) * 4.2, 2)) * 0.100 + n * 0.007;
if (state === 4) return 0.572 + x * 0.088 + Math.sin(x * 4.0) * 0.012 + n * 0.006;
if (state === 5) return 0.642 - Math.sin(x * 1.8 + 1.1) * 0.030 + n * 0.006;
return 0.626 - Math.sin(x * 2.9 + 0.8) * 0.028 - Math.sin(x * 6.6) * 0.013 + n * 0.009;
};
var PROFILES = [];
(function buildProfiles() {
for (var s = 0; s < 7; s += 1) {
var p = [];
for (var i = 0; i < VERTS; i += 1) p.push(profileAt(s, i));
PROFILES.push(p);
}
}());
var SKY = [
[[11, 22, 34], [22, 40, 59]],
[[13, 26, 42], [27, 49, 71]],
[[13, 24, 38], [35, 48, 60]],
[[10, 26, 38], [18, 58, 74]],
[[8, 26, 32], [14, 50, 57]],
[[12, 22, 32], [30, 44, 58]],
[[10, 26, 30], [20, 51, 42]]
];
var ctx = canvas.getContext ? canvas.getContext('2d') : null;
if (!ctx) return;
var W = 0;
var H = 0;
var dpr = 1;
var position = 0;
var horizon = [];
var visible = false;
var rafId = 0;
var lastDraw = 0;
var rgba = function (c, a) {
return 'rgba(' + c[0] + ',' + c[1] + ',' + c[2] + ',' + a.toFixed(3) + ')';
};
var GREEN = [79, 208, 102];
var WHITE = [255, 255, 255];
var AMBER = [223, 162, 63];
var DEEP = [11, 22, 34];
var SURF = [22, 40, 59];
var yAt = function (x) {
var f = (x / W) * (VERTS - 1);
var i = Math.max(0, Math.min(VERTS - 2, Math.floor(f)));
var k = f - i;
return (horizon[i] + (horizon[i + 1] - horizon[i]) * k) * H;
};
var stroke = function (colour, alpha, width) {
ctx.strokeStyle = rgba(colour, alpha);
ctx.lineWidth = width || 1.5;
};
var resize = function () {
var r = stage.getBoundingClientRect();
W = Math.max(1, Math.round(r.width));
H = Math.max(1, Math.round(r.height));
dpr = Math.min(2, window.devicePixelRatio || 1);
canvas.width = Math.round(W * dpr);
canvas.height = Math.round(H * dpr);
canvas.style.width = W + 'px';
canvas.style.height = H + 'px';
ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
ctx.lineJoin = 'round';
ctx.lineCap = 'round';
};
function drawSky(from, to, k) {
var a = SKY[Math.min(from, 6)];
var b = SKY[Math.min(to, 6)];
var e = M.easeOutQuart(k);
var mix = function (i, j) { return Math.round(M.lerp(a[i][j], b[i][j], e)); };
var top = [mix(0, 0), mix(0, 1), mix(0, 2)];
var bot = [mix(1, 0), mix(1, 1), mix(1, 2)];
var g = ctx.createLinearGradient(0, 0, 0, H);
g.addColorStop(0, rgba(top, 1));
g.addColorStop(1, rgba(bot, 1));
ctx.fillStyle = g;
ctx.fillRect(0, 0, W, H);
}
function drawIntro(w) {
if (w <= 0.001) return;
var i;
var x;
stroke(WHITE, 0.18 * w, 1.3);
ctx.beginPath();
for (x = 0; x <= W; x += W / 48) {
ctx.lineTo(x, yAt(x) - H * 0.085 - Math.sin(x / W * 5.2 + 0.9) * H * 0.022);
}
ctx.stroke();
stroke(WHITE, 0.10 * w, 1.1);
ctx.beginPath();
for (x = 0; x <= W; x += W / 48) {
ctx.lineTo(x, yAt(x) - H * 0.155 - Math.sin(x / W * 3.4 + 2.1) * H * 0.030);
}
ctx.stroke();
stroke(WHITE, 0.13 * w, 1);
ctx.setLineDash([2, 7]);
for (i = 1; i <= 4; i += 1) {
ctx.beginPath();
for (x = 0; x <= W; x += W / 40) ctx.lineTo(x, yAt(x) - i * H * 0.042);
ctx.stroke();
}
ctx.setLineDash([]);
stroke(GREEN, 0.34 * w, 1.2);
for (i = 0; i < 25; i += 1) {
var tx = (i + 0.5) * (W / 25);
var ty = yAt(tx);
var len = i % 5 === 0 ? 11 : 5;
ctx.beginPath();
ctx.moveTo(tx, ty - len);
ctx.lineTo(tx, ty + len);
ctx.stroke();
}
var px = W * 0.66;
var py = yAt(px) - H * 0.30;
stroke(GREEN, 0.20 * w, 1);
ctx.setLineDash([5, 8]);
ctx.beginPath();
ctx.moveTo(px, py);
ctx.lineTo(W * 0.24, yAt(W * 0.24) + H * 0.06);
ctx.moveTo(px, py);
ctx.lineTo(W * 0.98, yAt(W * 0.98) + H * 0.02);
ctx.stroke();
ctx.setLineDash([]);
ctx.beginPath();
ctx.arc(px, py, 4, 0, PI2);
ctx.strokeStyle = rgba(GREEN, 0.5 * w);
ctx.stroke();
}
function drawGround() {
ctx.beginPath();
ctx.moveTo(0, yAt(0));
for (var x = W / 60; x <= W; x += W / 60) ctx.lineTo(x, yAt(x));
ctx.lineTo(W, H);
ctx.lineTo(0, H);
ctx.closePath();
var g = ctx.createLinearGradient(0, H * 0.5, 0, H);
g.addColorStop(0, 'rgba(9,19,30,1)');
g.addColorStop(1, 'rgba(5,11,19,1)');
ctx.fillStyle = g;
ctx.fill();
ctx.save();
ctx.clip();
for (var f = 1; f <= 6; f += 1) {
stroke(WHITE, 0.055, 1);
ctx.beginPath();
for (var fx = 0; fx <= W; fx += W / 30) ctx.lineTo(fx, yAt(fx) + Math.pow(f / 6, 1.9) * H * 0.46);
ctx.stroke();
}
ctx.restore();
stroke(GREEN, 0.62, 1.5);
ctx.beginPath();
ctx.moveTo(0, yAt(0));
for (var x2 = W / 60; x2 <= W; x2 += W / 60) ctx.lineTo(x2, yAt(x2));
ctx.stroke();
}
function drawFrame() {
var m = Math.min(46, W * 0.04);
var pad = Math.min(40, W * 0.032);
stroke(WHITE, 0.16, 1);
var corners = [[pad, pad, 1, 1], [W - pad, pad, -1, 1], [pad, H - pad, 1, -1], [W - pad, H - pad, -1, -1]];
for (var i = 0; i < 4; i += 1) {
var c = corners[i];
ctx.beginPath();
ctx.moveTo(c[0], c[1] + c[3] * m * 0.4);
ctx.lineTo(c[0], c[1]);
ctx.lineTo(c[0] + c[2] * m * 0.4, c[1]);
ctx.stroke();
}
var sx = W - pad - m * 2.6;
var sy = pad + 24;
stroke(GREEN, 0.34, 1.2);
ctx.beginPath();
ctx.moveTo(sx, sy);
ctx.lineTo(sx + m * 2.6, sy);
ctx.moveTo(sx, sy - 5);
ctx.lineTo(sx, sy + 5);
ctx.moveTo(sx + m * 1.3, sy - 4);
ctx.lineTo(sx + m * 1.3, sy + 4);
ctx.moveTo(sx + m * 2.6, sy - 5);
ctx.lineTo(sx + m * 2.6, sy + 5);
ctx.stroke();
}
var MASTS = [0.46, 0.565, 0.665, 0.775, 0.895];
function drawWind(w, now) {
if (w <= 0.001) return;
var e = M.easeOutQuart(w);
var spin = (now / 1000) * ((2 * PI2) / 60);
for (var i = 0; i < MASTS.length; i += 1) {
var x = MASTS[i] * W;
var base = yAt(x);
var h = (0.115 + M.hashNoise(i, 21) * 0.055) * H * e;
var hub = base - h;
stroke(WHITE, 0.5 * w, 1.5);
ctx.beginPath();
ctx.moveTo(x, base);
ctx.lineTo(x, hub);
ctx.stroke();
stroke(GREEN, 0.62 * w, 1.5);
var r = h * 0.44;
for (var b = 0; b < 3; b += 1) {
var a = spin + (b * PI2) / 3 + i * 0.7;
ctx.beginPath();
ctx.moveTo(x, hub);
ctx.lineTo(x + Math.cos(a) * r, hub + Math.sin(a) * r * 0.92);
ctx.stroke();
}
ctx.beginPath();
ctx.arc(x, hub, 2.4, 0, PI2);
ctx.fillStyle = rgba(GREEN, 0.7 * w);
ctx.fill();
}
var dx = 0.285 * W;
var dw = 0.135 * W;
var dy = yAt(dx + dw / 2);
var dh = 0.052 * H * e;
stroke(WHITE, 0.45 * w, 1.5);
ctx.beginPath();
ctx.moveTo(dx, dy);
ctx.lineTo(dx + dw * 0.14, dy - dh);
ctx.lineTo(dx + dw * 0.86, dy - dh);
ctx.lineTo(dx + dw, dy);
ctx.stroke();
stroke(GREEN, 0.22 * w, 1);
for (var k = 1; k <= 3; k += 1) {
ctx.beginPath();
ctx.moveTo(dx - 0.075 * W, dy - dh + k * (dh / 4));
ctx.lineTo(dx + dw * 0.12, dy - dh + k * (dh / 4));
ctx.stroke();
}
}
function drawSolar(w) {
if (w <= 0.001) return;
var e = M.easeOutQuart(w);
var tilt = ((8 + 18 * e) * Math.PI) / 180;
var glowY = yAt(0.72 * W) - (0.015 + 0.085 * e) * H;
var rad = ctx.createRadialGradient(0.72 * W, glowY, 0, 0.72 * W, glowY, 0.26 * H);
rad.addColorStop(0, rgba(AMBER, 0.2 * w));
rad.addColorStop(1, rgba(AMBER, 0));
ctx.fillStyle = rad;
ctx.fillRect(0.72 * W - 0.26 * H, glowY - 0.26 * H, 0.52 * H, 0.52 * H);
stroke(AMBER, 0.38 * w, 1.5);
ctx.beginPath();
ctx.arc(0.72 * W, glowY, 0.042 * H, 0, PI2);
ctx.stroke();
for (var row = 0; row < 4; row += 1) {
var depth = row / 3;
var y = yAt(0.5 * W) + (0.022 + Math.pow(depth, 1.6) * 0.20) * H;
if (y > H * 1.05) continue;
var sw = (0.055 + depth * 0.055) * W;
var sh = (0.032 + depth * 0.045) * H;
var gap = sw * 0.42;
var count = Math.ceil(W / (sw + gap)) + 1;
var shift = row % 2 ? -(sw + gap) * 0.5 : 0;
for (var c = 0; c < count; c += 1) {
var x = shift + c * (sw + gap);
var lift = Math.sin(tilt) * sh;
ctx.beginPath();
ctx.moveTo(x, y);
ctx.lineTo(x + sw * 0.78, y - lift);
ctx.lineTo(x + sw, y - lift + sh * 0.22);
ctx.lineTo(x + sw * 0.22, y + sh * 0.22);
ctx.closePath();
ctx.fillStyle = rgba(SURF, 0.82 * w);
ctx.fill();
stroke(GREEN, 0.6 * w, 1.2);
ctx.stroke();
}
}
}
function waterTop(ww) {
return H - (0.08 + 0.24 * M.easeOutQuart(ww)) * H;
}
function drawWater(ww, now) {
if (ww <= 0.001) return;
var top = waterTop(ww);
var swell = Math.sin(now / 2600) * 0.006 * H;
ctx.beginPath();
ctx.moveTo(0, top + swell);
for (var x = 0; x <= W; x += W / 60) {
ctx.lineTo(x, top + swell + Math.sin(x / (W / 5) + now / 3200) * 0.006 * H);
}
ctx.lineTo(W, H);
ctx.lineTo(0, H);
ctx.closePath();
var wg = ctx.createLinearGradient(0, top, 0, H);
wg.addColorStop(0, 'rgba(34,70,88,' + (0.92 * ww).toFixed(3) + ')');
wg.addColorStop(1, 'rgba(12,30,44,' + (0.95 * ww).toFixed(3) + ')');
ctx.fillStyle = wg;
ctx.fill();
stroke(GREEN, 0.55 * ww, 1.4);
ctx.stroke();
for (var r = 1; r <= 3; r += 1) {
stroke(GREEN, (0.32 - r * 0.07) * ww, 1);
ctx.beginPath();
for (var x2 = 0; x2 <= W; x2 += W / 70) {
var amp = 0.005 * H * r;
ctx.lineTo(x2, top + swell + r * 0.055 * H + Math.sin(x2 / (W / (3 + r)) + now / (1800 + r * 700)) * amp);
}
ctx.stroke();
}
stroke(WHITE, 0.2 * ww, 1);
ctx.setLineDash([3, 6]);
for (var c = 1; c <= 3; c += 1) {
ctx.beginPath();
for (var x3 = 0; x3 <= W; x3 += W / 40) ctx.lineTo(x3, yAt(x3) + c * 0.024 * H);
ctx.stroke();
}
ctx.setLineDash([]);
}
function drawTidal(w, ww, now) {
if (w <= 0.001) return;
var e = M.easeOutQuart(w);
var top = waterTop(Math.max(ww, w));
var gh = 0.062 * H * e;
stroke(WHITE, 0.55 * w, 1.5);
ctx.beginPath();
ctx.moveTo(0.46 * W, top - gh);
ctx.lineTo(0.78 * W, top - gh);
ctx.stroke();
for (var g = 0; g < 6; g += 1) {
var x = (0.46 + g * 0.064) * W;
var gw = 0.064 * W;
stroke(WHITE, 0.42 * w, 1.5);
ctx.beginPath();
ctx.moveTo(x, top - gh);
ctx.lineTo(x, top + 0.012 * H);
ctx.stroke();
var open = 0.4 + 0.6 * (0.5 + 0.5 * Math.sin(now / 2200 + g));
stroke(GREEN, 0.45 * w, 1.2);
ctx.beginPath();
ctx.moveTo(x + 2, top - gh * open);
ctx.lineTo(x + gw - 2, top - gh * open);
ctx.stroke();
}
for (var b = 0; b < 4; b += 1) {
var bx = (0.815 + b * 0.046) * W;
var by = yAt(bx + 0.018 * W);
var bw = 0.036 * W;
var bh = 0.042 * H * e;
stroke(GREEN, 0.6 * w, 1.4);
ctx.strokeRect(bx, by - bh, bw, bh);
stroke(WHITE, 0.45 * w, 1.4);
ctx.beginPath();
ctx.moveTo(bx + bw * 0.25, by - bh);
ctx.lineTo(bx + bw * 0.25, by - bh - 4);
ctx.moveTo(bx + bw * 0.75, by - bh);
ctx.lineTo(bx + bw * 0.75, by - bh - 4);
ctx.stroke();
}
}
function bez(t, p) {
var u = 1 - t;
return {
x: u * u * p[0] + 2 * u * t * p[2] + t * t * p[4],
y: u * u * p[1] + 2 * u * t * p[3] + t * t * p[5]
};
}
function drawTransport(w) {
if (w <= 0.001) return;
var e = M.easeOutQuart(w);
var p = [0.02 * W, H * 0.99, 0.40 * W, H * 0.80, 0.86 * W, yAt(0.86 * W) + 0.02 * H];
var len = 0;
var prev = bez(0, p);
for (var s = 1; s <= 40; s += 1) {
var pt = bez(s / 40, p);
len += Math.hypot(pt.x - prev.x, pt.y - prev.y);
prev = pt;
}
stroke(GREEN, 0.55 * w, 1.6);
ctx.setLineDash([len, len]);
ctx.lineDashOffset = len * (1 - e);
ctx.beginPath();
ctx.moveTo(p[0], p[1]);
ctx.quadraticCurveTo(p[2], p[3], p[4], p[5]);
ctx.stroke();
ctx.setLineDash([]);
ctx.lineDashOffset = 0;
var marks = [0.24, 0.52, 0.78];
for (var m = 0; m < marks.length; m += 1) {
if (e < marks[m]) continue;
var q = bez(marks[m], p);
ctx.beginPath();
ctx.arc(q.x, q.y, 3.4, 0, PI2);
ctx.fillStyle = rgba(DEEP, 0.9);
ctx.fill();
stroke(WHITE, 0.55 * w, 1.4);
ctx.stroke();
}
var bx = 0.54 * W;
var bw = 0.26 * W;
var deck = yAt(bx + bw / 2) - 0.075 * H * e;
stroke(WHITE, 0.55 * w, 1.6);
ctx.beginPath();
ctx.moveTo(bx - bw * 0.1, deck);
ctx.lineTo(bx + bw * 1.1, deck);
ctx.stroke();
var sag = deck + 0.055 * H * e;
stroke(GREEN, 0.5 * w, 1.4);
ctx.beginPath();
ctx.moveTo(bx, deck);
ctx.quadraticCurveTo(bx + bw / 2, sag, bx + bw, deck);
ctx.stroke();
stroke(WHITE, 0.32 * w, 1.2);
for (var hg = 1; hg <= 4; hg += 1) {
var t = hg / 5;
var hx = bx + bw * t;
var hy = (1 - t) * (1 - t) * deck + 2 * (1 - t) * t * sag + t * t * deck;
ctx.beginPath();
ctx.moveTo(hx, deck);
ctx.lineTo(hx, hy);
ctx.stroke();
}
stroke(WHITE, 0.45 * w, 1.6);
for (var pr = 0; pr <= 1; pr += 1) {
var px = bx + bw * pr;
ctx.beginPath();
ctx.moveTo(px, deck);
ctx.lineTo(px, yAt(px));
ctx.stroke();
}
}
function drawEcology(w, now) {
if (w <= 0.001) return;
var e = M.easeOutQuart(w);
var i;
stroke(GREEN, 0.4 * w, 1.3);
for (i = 0; i < 16; i += 1) {
var tx = (0.53 + i * 0.028) * W;
var ty = yAt(tx);
var th = (0.024 + M.hashNoise(i, 7) * 0.022) * H * e;
ctx.beginPath();
ctx.moveTo(tx, ty);
ctx.lineTo(tx, ty - th);
ctx.moveTo(tx, ty - th * 0.55);
ctx.lineTo(tx - th * 0.34, ty - th * 0.92);
ctx.moveTo(tx, ty - th * 0.55);
ctx.lineTo(tx + th * 0.34, ty - th * 0.92);
ctx.stroke();
}
stroke(WHITE, 0.12 * w, 1);
for (i = 1; i < 12; i += 1) {
ctx.beginPath();
ctx.moveTo((i / 12) * W, 0);
ctx.lineTo((i / 12) * W, H);
ctx.stroke();
}
for (i = 1; i < 9; i += 1) {
ctx.beginPath();
ctx.moveTo(0, (i / 9) * H);
ctx.lineTo(W, (i / 9) * H);
ctx.stroke();
}
stroke(WHITE, 0.55 * w, 1.5);
for (i = 0; i < 6; i += 1) {
var drift = (now / 1000) * 0.018 + i * 0.19 + M.hashNoise(i, 3) * 0.4;
var bxp = ((drift % 1.25) - 0.12) * W;
var byp = H * (0.16 + 0.10 * M.hashNoise(i, 5) + 0.012 * Math.sin(now / 900 + i));
var sz = (0.009 + M.hashNoise(i, 9) * 0.006) * H;
var flap = 0.45 + 0.3 * Math.sin(now / 320 + i * 1.7);
ctx.beginPath();
ctx.moveTo(bxp - sz, byp - sz * flap);
ctx.lineTo(bxp, byp);
ctx.lineTo(bxp + sz, byp - sz * flap);
ctx.stroke();
}
}
function draw(now) {
if (!W || !H) return;
var from = Math.min(6, Math.floor(position));
var to = Math.min(6, Math.ceil(position));
var k = position - from;
horizon = M.lerpProfile(PROFILES[from], PROFILES[to], k);
var w = [];
for (var i = 0; i < 7; i += 1) w.push(M.stateWeight(position, i));
var ww = Math.max(w[3], w[4] * 0.92);
ctx.clearRect(0, 0, W, H);
drawSky(from, to, k);
drawIntro(w[0]);
drawGround();
drawSolar(w[2]);
drawWind(w[1], now);
drawTransport(w[5]);
drawWater(ww, now);
drawTidal(w[4], ww, now);
drawEcology(w[6], now);
drawFrame();
}
var current = -1;
function show(index) {
if (index === current) return;
current = index;
for (var i = 0; i < COUNT; i += 1) {
panels[i].classList.toggle('is-on', i === index);
panels[i].setAttribute('aria-hidden', i === index ? 'false' : 'true');
if (steps[i]) {
steps[i].classList.toggle('is-on', i === index);
if (i === index) steps[i].setAttribute('aria-current', 'step');
else steps[i].removeAttribute('aria-current');
}
}
}
function frame() {
var rect = root.getBoundingClientRect();
var progress = M.sectionProgress(rect, window.innerHeight);
var s = M.flowState(progress, COUNT);
position = s.position;
show(s.index);
for (var i = 0; i < COUNT; i += 1) {
if (steps[i]) steps[i].style.setProperty('--fill', s.fill[i].toFixed(3));
}
}
var scheduled = false;
function schedule() {
if (scheduled || !enabled()) return;
scheduled = true;
requestAnimationFrame(function () { scheduled = false; frame(); });
}
function loop(now) {
rafId = 0;
if (!visible || document.hidden || !enabled()) return;
if (now - lastDraw >= 32) {
lastDraw = now;
draw(now);
}
rafId = requestAnimationFrame(loop);
}
function play() {
if (rafId || !visible || document.hidden || !enabled()) return;
rafId = requestAnimationFrame(loop);
}
function stop() {
if (rafId) cancelAnimationFrame(rafId);
rafId = 0;
}
function start() {
if (!enabled()) {
stop();
show(0);
return;
}
resize();
frame();
draw(performance.now());
play();
}
if ('IntersectionObserver' in window) {
new IntersectionObserver(function (entries) {
visible = entries[0].isIntersecting;
if (visible) play(); else stop();
}, { threshold: 0 }).observe(stage);
} else {
visible = true;
}
window.addEventListener('scroll', schedule, { passive: true });
window.addEventListener('resize', function () { start(); });
document.addEventListener('visibilitychange', function () {
if (document.hidden) stop(); else play();
});
if (wide.addEventListener) wide.addEventListener('change', start);
if (reduce.addEventListener) reduce.addEventListener('change', start);
steps.forEach(function (step, index) {
var btn = step.querySelector('button');
if (!btn) return;
btn.addEventListener('click', function () {
if (!enabled()) {
var fb = document.getElementById('flow-fb-' + index);
if (fb) fb.scrollIntoView({ block: 'start' });
return;
}
var range = root.offsetHeight - window.innerHeight;
var target = root.offsetTop + range * (index / Math.max(COUNT - 1, 1)) * 0.92 + 4;
window.scrollTo({ top: target, behavior: reduce.matches ? 'auto' : 'smooth' });
});
});
start();
(function deepLink() {
if (!enabled()) return;
var scene = /[?&]scene=(\d+)/.exec(window.location.search || '');
if (scene) {
var at = Math.min(COUNT - 1, Math.max(0, parseInt(scene[1], 10)));
window.removeEventListener('scroll', schedule);
root.classList.add('flow--static');
position = at;
show(at);
steps.forEach(function (step, i) { step.style.setProperty('--fill', i <= at ? '1' : '0'); });
draw(performance.now());
return;
}
var jump = /^#state-(\d+)$/.exec(window.location.hash || '');
if (!jump) return;
var index = Math.min(COUNT - 1, Math.max(0, parseInt(jump[1], 10)));
var range = root.offsetHeight - window.innerHeight;
var top = root.offsetTop + range * (index / Math.max(COUNT - 1, 1)) * 0.92 + 4;
window.scrollTo({ top: top, behavior: 'auto' });
frame();
draw(performance.now());
}());
}());
