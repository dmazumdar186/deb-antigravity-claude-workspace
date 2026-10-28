(function () {
"use strict";
var S = null;
function mul(s) { return function () { s |= 0; s = s + 0x6D2B79F5 | 0; var t = Math.imul(s ^ s >>> 15, 1 | s); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
function cl(v, a, b) { return v < a ? a : v > b ? b : v; }
function ez(v) { return v <= 0 ? 0 : v >= 1 ? 1 : v * v * (3 - 2 * v); }
function lp(a, b, t) { return a + (b - a) * t; }
var FG = "#F5F1EA", AC = "#EF760D";

function build() {
  var cv = S.cv, w = cv.clientWidth || 300, h = cv.clientHeight || 300, m = Math.min(w, h);
  S.W = w; S.H = h;
  cv.width = Math.round(w * S.dpr); cv.height = Math.round(h * S.dpr);
  S.ctx.setTransform(S.dpr, 0, 0, S.dpr, 0, 0);
  var n = cl(Math.round(w * h / 9000), 90, 260), r = mul((S.seed + 1) | 0), i, t, d;
  var P = S.parts = [];
  for (i = 0; i < n; i++) {
    var ax, ay, bx, by;
    if (r() < 0.68) { // map figure: loose blob
      ax = 0.42 + (r() + r() + r() - 1.5) * 0.17; ay = 0.50 + (r() + r() + r() - 1.5) * 0.20;
    } else { // tight cluster marking the subject
      ax = 0.55 + (r() - 0.5) * 0.055; ay = 0.44 + (r() - 0.5) * 0.055;
    }
    if (r() < 0.58) { // dotted globe rim
      t = r() * 6.2832; d = 0.30 * (0.82 + 0.18 * r());
      bx = 0.5 + Math.cos(t) * d * (m / w); by = 0.5 + Math.sin(t) * d * (m / h);
    } else if (r() < 0.5) { // congress cities: inner constellation
      bx = 0.5 + (r() - 0.5) * 0.30 * (m / w); by = 0.5 + (r() - 0.5) * 0.30 * (m / h);
    } else {
      t = r() * 6.2832; d = 0.10 + r() * 0.14;
      bx = 0.5 + Math.cos(t) * d * (m / w); by = 0.5 + Math.sin(t) * d * (m / h);
    }
    P.push({ ax: ax, ay: ay, bx: bx, by: by, ph: r() * 6.2832, sp: 0.5 + r(), ln: (r() - 0.5) * 0.10, st: r() * 0.25, al: 0.45 + r() * 0.45, sz: 0.7 + r() * 0.9, ci: i % 9 === 0 });
  }
  S.pairs = []; S.links = []; S.cities = [];
  var j, dx, dy, dd, px, py, q;
  for (i = 0; i < n; i++) for (j = i + 1; j < n; j++) {
    dx = (P[i].ax - P[j].ax) * w; dy = (P[i].ay - P[j].ay) * h;
    if (dx * dx + dy * dy < 1600) S.pairs.push([i, j]);
  }
  for (i = 0; i < n; i++) if (P[i].ci) S.cities.push(i);
  for (i = 0; i < S.cities.length; i++) {
    q = [];
    for (j = 0; j < S.cities.length; j++) if (i !== j) {
      dx = (P[S.cities[i]].bx - P[S.cities[j]].bx) * w; dy = (P[S.cities[i]].by - P[S.cities[j]].by) * h;
      dd = dx * dx + dy * dy; if (dd < m * m * 0.09) q.push([j, dd]);
    }
    q.sort(function (a, b) { return a[1] - b[1]; });
    for (j = 0; j < 2 && j < q.length; j++) S.links.push([S.cities[i], S.cities[q[j][0]]]);
  }
}

function draw(t, p) {
  var c = S.ctx; if (!c) return;
  var w = S.W, h = S.H, m = Math.min(w, h), P = S.parts, n = P.length, i, o, e, x, y;
  c.clearRect(0, 0, w, h);
  var wA = 1 - ez(cl((p - 0.24) / 0.14, 0, 1)); // stage-1 weight
  var wB = ez(cl((p - 0.66) / 0.14, 0, 1));     // stage-3 weight
  var wJ = Math.sin(Math.PI * cl((p - 0.30) / 0.40, 0, 1)); // journey weight
  var dx = 0.62, dy = 0.55, dl = Math.sqrt(dx * dx + dy * dy); dx /= dl; dy /= dl;
  var px = -dy, py = dx;
  var pos = [];
  for (i = 0; i < n; i++) {
    o = P[i];
    e = ez(cl((p - 0.30 - o.st * 0.25) / 0.35, 0, 1));
    x = lp(o.ax, o.bx, e) * w + px * o.ln * m * Math.sin(Math.PI * e);
    y = lp(o.ay, o.by, e) * h + py * o.ln * m * Math.sin(Math.PI * e);
    x += Math.sin(t * 0.0003 * o.sp + o.ph) * 2.2; // ambient drift
    y += Math.cos(t * 0.00026 * o.sp + o.ph * 1.7) * 2.2;
    pos.push([x, y]);
  }
  c.lineWidth = 0.6;
  if (wA > 0.02) {
    c.strokeStyle = FG; c.globalAlpha = 0.10 * wA; c.beginPath();
    for (i = 0; i < S.pairs.length; i++) {
      o = S.pairs[i]; c.moveTo(pos[o[0]][0], pos[o[0]][1]); c.lineTo(pos[o[1]][0], pos[o[1]][1]);
    }
    c.stroke();
  }
  if (wB > 0.02) {
    c.strokeStyle = FG; c.globalAlpha = 0.12 * wB; c.beginPath();
    for (i = 0; i < S.links.length; i++) {
      o = S.links[i]; c.moveTo(pos[o[0]][0], pos[o[0]][1]); c.lineTo(pos[o[1]][0], pos[o[1]][1]);
    }
    c.stroke();
  }
  c.globalAlpha = 1;
  for (i = 0; i < n; i++) {
    o = P[i];
    c.fillStyle = (i % 43 === 3) ? AC : FG;
    c.globalAlpha = o.al * (o.ci ? 0.9 + 0.1 * wB : 1);
    c.fillRect(pos[i][0] - o.sz / 2, pos[i][1] - o.sz / 2, o.sz, o.sz);
  }
  if (wJ > 0.01) { // brand initial dissolving into dots
    var r = mul((S.seed + 7) | 0), k, a = 0.08 * wJ;
    c.fillStyle = FG; c.font = "italic 14px Georgia, 'Times New Roman', serif"; c.textBaseline = "middle";
    for (k = 0; k < 3; k++) {
      x = (0.30 + k * 0.20) * w; y = (0.40 + 0.14 * k) * h;
      c.globalAlpha = a; c.fillText("A", x, y);
      for (i = 0; i < 7; i++) { c.globalAlpha = a * r(); c.fillRect(x + (r() - 0.5) * 26, y + (r() - 0.5) * 26, 1, 1); }
    }
  }
  var rp = cl((p - 0.74) / 0.18, 0, 1); // single pulse ring on the second cluster
  if (rp > 0 && rp < 1) {
    c.strokeStyle = AC; c.globalAlpha = (1 - rp) * 0.35; c.lineWidth = 1;
    c.beginPath(); c.arc(0.5 * w, 0.5 * h, lp(0.06, 0.34, ez(rp)) * m, 0, 6.2832); c.stroke();
  }
  c.globalAlpha = 1;
}

function frame(now) { S.raf = requestAnimationFrame(frame); draw(now, S.p); }
function start() {
  if (S.rm) { draw(0, S.p); return; }
  if (!S.raf && S.play && !document.hidden) S.raf = requestAnimationFrame(frame);
}
function stop() { if (S.raf) { cancelAnimationFrame(S.raf); S.raf = 0; } }
function onVis() { if (document.hidden) stop(); else start(); }

window.AssetBackdrop = {
  init: function (cv, o) {
    o = o || {};
    this.destroy();
    var c = cv.getContext ? cv.getContext("2d") : null; if (!c) return;
    S = { cv: cv, ctx: c, dpr: Math.min(o.dpr || 1.5, window.devicePixelRatio || 1), rm: !!o.reducedMotion, play: o.autoplay !== false, p: 0, seed: (o.seed || 1) | 0, raf: 0 };
    build();
    if (window.ResizeObserver) { S.ro = new ResizeObserver(build); S.ro.observe(cv); }
    else window.addEventListener("resize", build);
    document.addEventListener("visibilitychange", onVis);
    start();
  },
  setProgress: function (p) { if (!S) return; S.p = cl(+p || 0, 0, 1); if (S.rm) draw(0, S.p); },
  render: function (tMs) { if (S) draw(+tMs || 0, S.p); },
  pause: function () { if (!S) return; S.play = false; stop(); },
  resume: function () { if (!S) return; S.play = true; start(); },
  destroy: function () {
    if (!S) return;
    stop();
    if (S.ro) S.ro.disconnect(); else window.removeEventListener("resize", build);
    document.removeEventListener("visibilitychange", onVis);
    S = null;
  }
};
})();
