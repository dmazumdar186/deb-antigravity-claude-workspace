(function(){ 'use strict';

  var INK = '#0A1F30', ORANGE = '#EF760D', CYAN = '#0DAFDB', PAPER = '#F2EEE5', NAVY = '#0D3048';
  var CACHE = {};

  /* ---------- small helpers ---------- */
  function clamp01(v){ return v < 0 ? 0 : (v > 1 ? 1 : v); }
  function lerp(a, b, p){ return a + (b - a) * p; }
  function ease(p){ p = clamp01(p); return p < 0.5 ? 4*p*p*p : 1 - Math.pow(-2*p + 2, 3) / 2; }
  function seg(t, a, b){ return ease((t - a) / (b - a)); }
  function segL(t, a, b){ return clamp01((t - a) / (b - a)); }
  function pw(t, pts){
    if (t <= pts[0][0]) return pts[0][1];
    for (var i = 0; i < pts.length - 1; i++){
      var a = pts[i], b = pts[i + 1];
      if (t <= b[0]) return lerp(a[1], b[1], (t - a[0]) / (b[0] - a[0]));
    }
    return pts[pts.length - 1][1];
  }
  function mulberry32(seed){
    return function(){
      seed |= 0; seed = seed + 0x6D2B79F5 | 0;
      var z = Math.imul(seed ^ seed >>> 15, 1 | seed);
      z = z + Math.imul(z ^ z >>> 7, 61 | z) ^ z;
      return ((z ^ z >>> 14) >>> 0) / 4294967296;
    };
  }
  function rr(ctx, x, y, w, h, r){
    r = Math.min(r, w / 2, h / 2);
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  }
  function quadPt(a, c, b, s){
    var m = 1 - s;
    return { x: m*m*a.x + 2*m*s*c.x + s*s*b.x, y: m*m*a.y + 2*m*s*c.y + s*s*b.y };
  }
  function quadTan(a, c, b, s){
    return { x: 2*(1 - s)*(c.x - a.x) + 2*s*(b.x - c.x), y: 2*(1 - s)*(c.y - a.y) + 2*s*(b.y - c.y) };
  }

  /* ---------- text / card helpers (caller restores) ---------- */
  function mono(ctx, size, txt, x, y, color, align, alpha){
    ctx.save();
    ctx.globalAlpha *= (alpha === undefined ? 1 : alpha);
    ctx.fillStyle = color;
    ctx.font = '600 ' + size.toFixed(2) + 'px ui-monospace, Menlo, monospace';
    ctx.textAlign = align || 'left';
    ctx.textBaseline = 'middle';
    ctx.fillText(txt, x, y);
    ctx.restore();
  }
  function serif(ctx, size, txt, x, y, color, align, alpha){
    ctx.save();
    ctx.globalAlpha *= (alpha === undefined ? 1 : alpha);
    ctx.fillStyle = color;
    ctx.font = '500 ' + size.toFixed(2) + 'px "EB Garamond", Georgia, serif';
    ctx.textAlign = align || 'left';
    ctx.textBaseline = 'middle';
    ctx.fillText(txt, x, y);
    ctx.restore();
  }
  function card(ctx, u, k, x, y, w, h, rot){
    ctx.save();
    ctx.translate(x, y);
    ctx.rotate(rot);
    ctx.fillStyle = 'rgba(10,31,48,0.10)';
    ctx.fillRect(-w/2 + 0.6*u, -h/2 + 0.8*u, w, h);
    ctx.fillStyle = '#FFFFFF';
    ctx.fillRect(-w/2, -h/2, w, h);
    ctx.strokeStyle = INK;
    ctx.globalAlpha *= 0.35;
    ctx.lineWidth = Math.max(1, k);
    ctx.strokeRect(-w/2, -h/2, w, h);
    ctx.globalAlpha /= 0.35;
  }
  function tickStroke(ctx, u, k, x, y, s, p, color){
    if (p <= 0) return;
    var pts = [[x, y], [x + 0.32*s, y + 0.30*s], [x + s, y - 0.42*s]];
    var segs = [[0, 1, 0.45], [1, 2, 1]];
    ctx.save();
    ctx.strokeStyle = color; ctx.lineWidth = Math.max(1.4, 1.8 * k);
    ctx.lineCap = 'round'; ctx.lineJoin = 'round';
    ctx.beginPath();
    var started = false, budget = p * 1.45;
    for (var i = 0; i < segs.length; i++){
      var sg = segs[i], a = pts[sg[0]], b = pts[sg[1]], len = sg[2];
      var f = clamp01(budget / len);
      if (f <= 0) break;
      if (!started){ ctx.moveTo(a[0], a[1]); started = true; }
      ctx.lineTo(lerp(a[0], b[0], f), lerp(a[1], b[1], f));
      budget -= len * f;
    }
    ctx.stroke();
    ctx.restore();
  }

  /* ---------- seeded geometry, cached by W,H ---------- */
  function geo(W, H){
    var key = W + 'x' + H;
    if (CACHE[key]) return CACHE[key];
    var landscape = (W / H) >= 1.2, S, u, k = W / 1920;
    if (landscape) S = { x: 0.40 * W, y: 0.08 * H, w: 0.57 * W, h: 0.84 * H };
    else          S = { x: 0.05 * W, y: 0.06 * H, w: 0.90 * W, h: 0.54 * H };
    u = Math.min(S.w, S.h) / 100;
    S.cx = S.x + S.w / 2; S.cy = S.y + S.h / 2;

    var rnd = mulberry32(20240517);
    var g = { S: S, u: u, k: k };

    // abstract coastline (~40 pts), sweeping lower band of S
    var coast = [], i, n = 40;
    for (i = 0; i < n; i++){
      var fx = i / (n - 1);
      var base = 0.72 + 0.12 * fx + 0.06 * Math.sin(fx * 5.1);
      coast.push({ x: S.x + (0.02 + 0.96 * fx) * S.w, y: S.y + (base + rnd() * 0.05) * S.h });
    }
    g.coast = coast;

    // cities + arcs
    g.paris = { x: S.x + 0.24 * S.w, y: S.y + 0.60 * S.h };
    g.dest  = { x: S.x + 0.72 * S.w, y: S.y + 0.30 * S.h };
    g.ctrl  = { x: (g.paris.x + g.dest.x) / 2 + 0.02 * S.w, y: Math.min(g.paris.y, g.dest.y) - 0.24 * S.h };
    g.altc1 = { x: g.paris.x + 0.12 * S.w, y: g.paris.y + 0.06 * S.h };
    g.altc2 = { x: g.paris.x + 0.42 * S.w, y: g.dest.y + 0.30 * S.h };

    // barcode bars (widths)
    g.bars = [];
    for (i = 0; i < 26; i++) g.bars.push(rnd() < 0.5 ? 0.32 : 0.85);

    // report chart heights
    g.chart = [];
    for (i = 0; i < 6; i++) g.chart.push(0.30 + rnd() * 0.65);

    // grain dots (static, deterministic)
    g.grain = [];
    var gd = Math.round(W * H / 4200);
    for (i = 0; i < gd; i++) g.grain.push([rnd() * W, rnd() * H]);

    // split-flap scramble chars per tile
    var cs = 'ABCDEFGHIJKLMNOPQRSTUVWXYZÀÉÈÇ0123456789';
    g.scr = [];
    for (i = 0; i < 32; i++) g.scr.push(cs.charAt(Math.floor(rnd() * cs.length)));

    // receipt seeds: [x0, x1, rot]
    g.receipts = [];
    for (i = 0; i < 5; i++) g.receipts.push([(rnd() - 0.5) * 26, (rnd() - 0.5) * 16, (rnd() - 0.5) * 0.6]);

    CACHE[key] = g;
    return g;
  }

  /* ---------- document painters (draw centred at origin, inside card) ---------- */
  function docPass(ctx, u, k, g){
    var w = 40 * u, h = 14 * u;
    card(ctx, u, k, 0, 0, w, h, 0);
    mono(ctx, 1.5 * u, 'PARIS → CONGRÈS', -w/2 + 1.8 * u, 0, INK, 'left', 1);
    ctx.strokeStyle = INK; ctx.globalAlpha *= 0.5; ctx.lineWidth = Math.max(1, k);
    ctx.setLineDash([0.5 * u, 0.7 * u]);
    ctx.beginPath(); ctx.moveTo(w * 0.10, -h/2 + 1.6 * u); ctx.lineTo(w * 0.10, h/2 - 1.6 * u); ctx.stroke();
    ctx.setLineDash([]);
    ctx.globalAlpha /= 0.5;
    var bx = w * 0.10 + 1.4 * u, x = bx, i;
    for (i = 0; i < g.bars.length; i++){
      var bw = g.bars[i] * u;
      ctx.fillStyle = INK; ctx.fillRect(x, -2.6 * u, bw, 5.2 * u);
      x += bw + 0.34 * u;
    }
    ctx.restore();
  }
  function docTrain(ctx, u, k, g){
    var w = 26 * u, h = 12 * u;
    card(ctx, u, k, 0, 0, w, h, 0);
    mono(ctx, 1.7 * u, 'TRAIN', 0, -1.6 * u, INK, 'center', 1);
    ctx.strokeStyle = INK; ctx.globalAlpha *= 0.3; ctx.lineWidth = Math.max(1, k);
    for (var i = 0; i < 2; i++){
      ctx.beginPath();
      ctx.moveTo(-w/2 + 2 * u, -0.2 * u + i * 1.8 * u);
      ctx.lineTo(w/2 - 2 * u, -0.2 * u + i * 1.8 * u);
      ctx.stroke();
    }
    ctx.restore();
  }
  function docHotel(ctx, u, k, g){
    var w = 26 * u, h = 14 * u;
    card(ctx, u, k, 0, 0, w, h, 0);
    mono(ctx, 1.7 * u, 'HÔTEL', 0, -2.2 * u, INK, 'center', 1);
    ctx.strokeStyle = INK; ctx.globalAlpha *= 0.3; ctx.lineWidth = Math.max(1, k);
    for (var i = 0; i < 3; i++){
      ctx.beginPath();
      ctx.moveTo(-w/2 + 2.4 * u, 0 + i * 2 * u);
      ctx.lineTo(w/2 - 2.4 * u, 0 + i * 2 * u);
      ctx.stroke();
    }
    ctx.restore();
  }
  function docBadge(ctx, u, k, g){
    var w = 16 * u, h = 22 * u;
    card(ctx, u, k, 0, 0, w, h, 0);
    ctx.strokeStyle = INK; ctx.globalAlpha *= 0.6; ctx.lineWidth = Math.max(1, k);
    ctx.beginPath(); ctx.arc(0, -h/2 + 2.4 * u, 0.9 * u, 0, Math.PI * 2); ctx.stroke();
    ctx.globalAlpha /= 0.6;
    ctx.fillStyle = ORANGE; ctx.fillRect(-w/2, -h/2 + 4.2 * u, w, 3.4 * u);
    mono(ctx, 1.5 * u, 'BADGE', 0, -h/2 + 5.9 * u, '#FFFFFF', 'center', 1);
    ctx.strokeStyle = INK; ctx.globalAlpha *= 0.3;
    for (var i = 0; i < 3; i++){
      ctx.beginPath();
      ctx.moveTo(-w/2 + 2.2 * u, 2.5 * u + i * 2 * u);
      ctx.lineTo(w/2 - 2.2 * u, 2.5 * u + i * 2 * u);
      ctx.stroke();
    }
    ctx.restore();
  }
  function docProg(ctx, u, k, g){
    var w = 16 * u, h = 11 * u;
    card(ctx, u, k, 0, 0, w, h, 0);
    serif(ctx, 2.1 * u, 'Programme', 0, -2.6 * u, INK, 'center', 1);
    ctx.strokeStyle = INK; ctx.globalAlpha *= 0.3; ctx.lineWidth = Math.max(1, k);
    for (var i = 0; i < 3; i++){
      ctx.beginPath();
      ctx.moveTo(-w/2 + 2 * u, 0.4 * u + i * 1.8 * u);
      ctx.lineTo(w/2 - 2 * u, 0.4 * u + i * 1.8 * u);
      ctx.stroke();
    }
    ctx.restore();
  }

  var DOCS = [
    { w: 40, h: 14, fr: -8 * Math.PI / 180, fx: -8,  fy: -8, sd: 0.00, paint: docPass },
    { w: 26, h: 12, fr:  6 * Math.PI / 180, fx: 11,  fy: -9, sd: 0.14, paint: docTrain },
    { w: 26, h: 14, fr: -4 * Math.PI / 180, fx: -13, fy:  5, sd: 0.28, paint: docHotel },
    { w: 16, h: 22, fr: 10 * Math.PI / 180, fx: 12,  fy:  5, sd: 0.42, paint: docBadge }
  ];

  /* ---------- map ---------- */
  function drawCoast(ctx, g, alpha){
    var S = g.S;
    ctx.save();
    ctx.globalAlpha *= alpha;
    // water hint below the coast
    ctx.fillStyle = CYAN; ctx.globalAlpha *= 0.09;
    ctx.beginPath();
    ctx.moveTo(g.coast[0].x, g.coast[0].y);
    for (var i = 1; i < g.coast.length; i++) ctx.lineTo(g.coast[i].x, g.coast[i].y);
    ctx.lineTo(S.x + S.w, S.y + S.h);
    ctx.lineTo(S.x, S.y + S.h);
    ctx.closePath(); ctx.fill();
    ctx.globalAlpha /= 0.09;
    // coastline, smoothed through midpoints
    ctx.strokeStyle = INK; ctx.lineWidth = Math.max(1.2, 1.5 * g.k);
    ctx.globalAlpha *= alpha * 0.9;
    ctx.beginPath();
    ctx.moveTo(g.coast[0].x, g.coast[0].y);
    for (var j = 1; j < g.coast.length - 1; j++){
      var a = g.coast[j], b = g.coast[j + 1];
      ctx.quadraticCurveTo(a.x, a.y, (a.x + b.x) / 2, (a.y + b.y) / 2);
    }
    ctx.lineTo(g.coast[g.coast.length - 1].x, g.coast[g.coast.length - 1].y);
    ctx.stroke();
    ctx.restore();
  }
  function arcPoly(ctx, a, c, b, p, back){
    var N = 48, i, s;
    ctx.beginPath();
    for (i = 0; i <= N; i++){
      var f = i / N;
      s = back ? 1 - p * f : p * f;
      var pt = quadPt(a, c, b, s);
      if (i === 0) ctx.moveTo(pt.x, pt.y); else ctx.lineTo(pt.x, pt.y);
    }
  }
  function drawMap(ctx, g, t){
    var u = g.u, S = g.S;
    drawCoast(ctx, g, 1);
    // faint alternative arcs, fading out early in leg 10->15
    var altA = 0.25 * (1 - seg(t, 10.8, 13.2));
    if (altA > 0.005){
      ctx.save();
      ctx.strokeStyle = INK; ctx.globalAlpha *= altA / 0.25 * 0.25;
      ctx.lineWidth = Math.max(1, 1.5 * g.k); ctx.setLineDash([1.4 * u, 1.4 * u]);
      arcPoly(ctx, g.paris, g.altc1, g.dest, 1, false); ctx.stroke();
      arcPoly(ctx, g.paris, g.altc2, g.dest, 1, false); ctx.stroke();
      ctx.setLineDash([]);
      ctx.restore();
    }
    // main orange route
    var fwdA = 1 - seg(t, 27.9, 28.5);
    var p = seg(t, 10.6, 14.4);
    if (p > 0 && fwdA > 0.005){
      ctx.save();
      ctx.strokeStyle = ORANGE; ctx.globalAlpha *= fwdA;
      ctx.lineWidth = Math.max(1.6, 2.2 * g.k);
      ctx.setLineDash([2 * u, 1.2 * u]);
      arcPoly(ctx, g.paris, g.ctrl, g.dest, p, false);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.restore();
    }
    // reversed route for the finale
    if (t > 28.4){
      var pr = seg(t, 28.6, 29.5);
      ctx.save();
      ctx.strokeStyle = ORANGE;
      ctx.lineWidth = Math.max(1.6, 2.2 * g.k);
      ctx.setLineDash([2 * u, 1.2 * u]);
      arcPoly(ctx, g.paris, g.ctrl, g.dest, pr, true);
      ctx.stroke();
      ctx.setLineDash([]);
      if (pr > 0.92){
        var aa = seg(t, 29.35, 29.7);
        var dv = quadTan(g.paris, g.ctrl, g.dest, 0);
        var ang = Math.atan2(dv.y, dv.x);
        ctx.translate(g.paris.x, g.paris.y); ctx.rotate(ang);
        ctx.globalAlpha *= aa;
        ctx.fillStyle = ORANGE;
        ctx.beginPath();
        ctx.moveTo(1.8 * u, 0); ctx.lineTo(-1.1 * u, 1.1 * u); ctx.lineTo(-1.1 * u, -1.1 * u);
        ctx.closePath(); ctx.fill();
      }
      ctx.restore();
    }
    // city dots + labels
    ctx.save();
    ctx.fillStyle = INK; ctx.strokeStyle = INK;
    ctx.lineWidth = Math.max(1.2, 1.5 * g.k);
    ctx.beginPath(); ctx.arc(g.paris.x, g.paris.y, 1.1 * u, 0, Math.PI * 2); ctx.fill();
    ctx.beginPath(); ctx.arc(g.paris.x, g.paris.y, 1.9 * u, 0, Math.PI * 2); ctx.stroke();
    ctx.beginPath(); ctx.arc(g.dest.x, g.dest.y, 1.1 * u, 0, Math.PI * 2); ctx.fill();
    ctx.beginPath(); ctx.arc(g.dest.x, g.dest.y, 1.9 * u, 0, Math.PI * 2); ctx.stroke();
    mono(ctx, 1.8 * u, 'PARIS', g.paris.x - 2.6 * u, g.paris.y + 2.9 * u, INK, 'right', 1);
    mono(ctx, 1.8 * u, 'VILLE DU CONGRÈS', g.dest.x + 2.6 * u, g.dest.y - 2.6 * u, INK, 'left', 1);
    ctx.restore();
  }

  /* ---------- brief sheet (K0 / K5) ---------- */
  function drawSheet(ctx, g, t){
    var S = g.S, u = g.u, k = g.k;
    var fade = 1 - seg(t, 8.4, 9.4);
    if (fade <= 0.005) return;
    var p = seg(t, 5.6, 9.4);
    var cx = lerp(S.cx, S.x + 0.18 * S.w, p);
    var cy = lerp(S.cy, S.y + 0.80 * S.h, p);
    var sc = lerp(1, 0.42, p);
    var sh = 0.70 * S.h, sw = sh / 1.414;

    ctx.save();
    ctx.globalAlpha *= fade;
    ctx.translate(cx, cy); ctx.scale(sc, sc); ctx.rotate(-2 * Math.PI / 180);
    ctx.translate(-sw / 2, -sh / 2);

    card(ctx, u, k, sw / 2, sh / 2, sw, sh, 0); // sheet body (rot applied outside)
    ctx.translate(sw / 2, sh / 2); ctx.translate(-sw / 2, -sh / 2);

    serif(ctx, 3 * u, 'Votre demande', 0.08 * sw, 0.11 * sh, INK, 'left', 1);

    // three ruled lines under the title
    ctx.strokeStyle = INK; ctx.globalAlpha *= 0.3; ctx.lineWidth = Math.max(1, k);
    for (var i = 0; i < 3; i++){
      ctx.beginPath();
      ctx.moveTo(0.08 * sw, (0.20 + i * 0.045) * sh);
      ctx.lineTo(0.92 * sw, (0.20 + i * 0.045) * sh);
      ctx.stroke();
    }
    ctx.globalAlpha /= 0.3;

    // K0 checkbox rows
    var cbA = 1 - seg(t, 3.0, 3.5);
    if (cbA > 0.005){
      var labels = ['VOYAGE D\u2019AFFAIRES', 'SÉMINAIRE · GROUPE', 'CONGRÈS INTERNATIONAL'];
      var tickP = [seg(t, 1.0, 1.6), seg(t, 1.7, 2.3), seg(t, 2.4, 3.0)];
      ctx.save();
      ctx.globalAlpha *= cbA;
      for (var c = 0; c < 3; c++){
        var by = (0.44 + c * 0.15) * sh, bx = 0.08 * sw, bs = 0.05 * sh;
        ctx.strokeStyle = INK; ctx.lineWidth = Math.max(1.2, 1.5 * k);
        ctx.strokeRect(bx, by - bs / 2, bs, bs);
        tickStroke(ctx, u, k, bx + 0.12 * bs, by, 0.78 * bs, tickP[c], INK);
        mono(ctx, 1.6 * u, labels[c], bx + bs + 0.6 * u, by, INK, 'left', 1);
      }
      ctx.restore();
    }

    // K5 policy block: four ruled rows sliding in from the right edge of the sheet
    var pl = ['TRANSPORT', 'HÉBERGEMENT', 'ASSURANCE', 'VALIDATION'];
    for (var r = 0; r < 4; r++){
      var rp = seg(t, 3.1 + r * 0.28, 3.9 + r * 0.28);
      if (rp <= 0) continue;
      var ry = (0.42 + r * 0.12) * sh;
      var ox = (1 - rp) * (0.86 * sw);
      ctx.save();
      ctx.translate(ox, 0);
      mono(ctx, 1.6 * u, pl[r], 0.08 * sw, ry, INK, 'left', 1);
      ctx.strokeStyle = INK; ctx.globalAlpha *= 0.3; ctx.lineWidth = Math.max(1, k);
      ctx.beginPath();
      ctx.moveTo(0.08 * sw + 0.34 * sw, ry);
      ctx.lineTo(0.84 * sw, ry);
      ctx.stroke();
      ctx.globalAlpha /= 0.3;
      tickStroke(ctx, u, k, 0.86 * sw, ry + 0.4 * u, 1.3 * u, seg(t, 3.9 + r * 0.28, 4.3 + r * 0.28), INK);
      ctx.restore();
    }

    // round orange stamp, pressed
    var sp = seg(t, 4.55, 4.95);
    if (sp > 0){
      ctx.save();
      ctx.translate(0.72 * sw, 0.86 * sh);
      ctx.rotate(12 * Math.PI / 180);
      var ss = lerp(1.6, 1, sp);
      ctx.scale(ss, ss);
      ctx.globalAlpha *= sp * 0.92;
      ctx.strokeStyle = ORANGE; ctx.lineWidth = Math.max(1.6, 2.2 * k);
      ctx.beginPath(); ctx.arc(0, 0, 0.075 * sh, 0, Math.PI * 2); ctx.stroke();
      ctx.lineWidth = Math.max(1, 1.4 * k);
      ctx.beginPath(); ctx.arc(0, 0, 0.058 * sh, 0, Math.PI * 2); ctx.stroke();
      mono(ctx, 1.35 * u, 'POLITIQUE', 0, 0, ORANGE, 'center', 1);
      ctx.restore();
    }
    ctx.restore(); // sheet card
    ctx.restore();
  }

  /* ---------- documents & wallet ---------- */
  function wallet(ctx, g, cx, cy, sc, flap, alpha){
    var u = g.u;
    if (alpha <= 0.005) return;
    ctx.save();
    ctx.globalAlpha *= alpha;
    ctx.translate(cx, cy); ctx.scale(sc, sc);
    var w = 40 * u, h = 26 * u;
    ctx.fillStyle = NAVY;
    rr(ctx, -w/2, -h/2, w, h, 2.5 * u); ctx.fill();
    ctx.save();
    ctx.translate(0, -h/2);
    ctx.scale(1, Math.max(0.03, flap));
    ctx.fillStyle = '#16405F';
    rr(ctx, -w/2, 0, w, h/2, 2.5 * u); ctx.fill();
    if (flap > 0.55){
      mono(ctx, 1.5 * u, 'A S S E T   V O Y A G E S', 0, h/4, '#FFFFFF', 'center', 0.92);
    }
    ctx.restore();
    ctx.restore();
  }

  function drawDocs(ctx, g, t){
    var S = g.S, u = g.u;
    if (t < 13.3 || t > 29.4) return;
    ctx.save();
    ctx.beginPath(); ctx.rect(S.x, S.y, S.w, S.h); ctx.clip();

    // wallet journey
    var wcx = null, wcy = null, wsc = 0.95, wflap = 0, wa = 0;
    if (t < 19.3){
      wa = seg(t, 16.8, 17.3);
      wcx = S.cx; wcy = S.cy + 2 * u;
      wflap = seg(t, 18.5, 19.3);
    } else if (t < 23.8){
      var m1 = seg(t, 19.3, 19.9);
      wcx = lerp(S.cx, g.paris.x, m1); wcy = lerp(S.cy + 2 * u, g.paris.y, m1);
      wsc = lerp(0.95, 0.5, m1); wa = 1; wflap = 1;
    } else if (t < 25.6){
      var m2 = seg(t, 23.8, 24.8);
      wcx = lerp(g.paris.x, g.dest.x, m2); wcy = lerp(g.paris.y, g.dest.y, m2);
      wsc = 0.5; wa = 1; wflap = 1;
    } else {
      var HC = { x: S.x + 0.48 * S.w, y: S.y + 0.44 * S.h };
      var m3 = seg(t, 25.6, 26.4);
      wcx = lerp(g.dest.x, HC.x, m3); wcy = lerp(g.dest.y, HC.y, m3);
      wsc = lerp(0.5, 0.9, m3);
      wa = 1 - seg(t, 28.4, 29.2);
      wflap = 1 - seg(t, 26.3, 27.0);
    }
    if (wa > 0.005) wallet(ctx, g, wcx, wcy, wsc, wflap, wa);

    // documents
    for (var i = 0; i < DOCS.length; i++){
      var d = DOCS[i];
      var x, y, rot, alpha = 1;
      if (t < 14.4){
        var pp = seg(t, 13.4 + i * 0.15, 14.1 + i * 0.15);
        if (pp <= 0) continue;
        x = S.cx + (i - 1.5) * 7 * u;
        y = lerp(S.y + S.h + 9 * u, S.y + S.h - 1.5 * u, pp);
        rot = 0; alpha = pp;
      } else if (t < 15.6){
        var pf = seg(t, 14.4, 14.95);
        x = lerp(S.cx + (i - 1.5) * 7 * u, S.cx + d.fx * u, pf);
        y = lerp(S.y + S.h - 1.5 * u, S.cy + d.fy * u, pf);
        rot = d.fr * pf;
      } else if (t < 25.5){
        var ps = seg(t, 15.7 + d.sd, 17.1 + d.sd);
        x = lerp(S.cx + d.fx * u, S.cx, ps);
        y = lerp(S.cy + d.fy * u, S.cy + 2 * u, ps);
        rot = d.fr * (1 - ps);
        alpha = 1 - seg(t, 16.6 + d.sd, 17.15 + d.sd);
        if (alpha <= 0.005) continue;
      } else {
        var p2 = seg(t, 26.6 + d.sd * 0.5, 27.3 + d.sd * 0.5);
        if (p2 <= 0) continue;
        var HC2 = { x: S.x + 0.48 * S.w, y: S.y + 0.44 * S.h };
        var tx = HC2.x + d.fx * 0.75 * u, ty = HC2.y + 12 * u + d.fy * 0.35 * u;
        x = lerp(HC2.x, tx, p2); y = lerp(HC2.y, ty, p2);
        rot = d.fr * p2;
        alpha = p2 * (1 - seg(t, 28.4, 29.2));
        if (alpha <= 0.005) continue;
      }
      ctx.save();
      ctx.globalAlpha *= alpha;
      ctx.translate(x, y); ctx.rotate(rot);
      ctx.scale(0.85, 0.85);
      d.paint(ctx, u, g.k, g); // painter saves/restores its own card
      ctx.restore();
    }

    // "Programme" sheet appears in front of the hall
    var pg = seg(t, 26.9, 27.6);
    if (pg > 0){
      var HCP = { x: S.x + 0.48 * S.w, y: S.y + 0.44 * S.h };
      ctx.save();
      ctx.globalAlpha *= pg * (1 - seg(t, 28.4, 29.2));
      ctx.translate(lerp(HCP.x, HCP.x + 13 * u, pg), lerp(HCP.y, HCP.y + 19 * u, pg));
      ctx.rotate(4 * Math.PI / 180 * pg);
      ctx.scale(0.85, 0.85);
      docProg(ctx, u, g.k, g);
      ctx.restore();
    }
    ctx.restore();
  }

  /* ---------- plane ---------- */
  function drawPlane(ctx, g, t){
    if (t < 19.9 || t > 25.0) return;
    var u = g.u;
    var p = segL(t, 19.9, 24.4); // linear: the plane only
    var a = clamp01(1 - seg(t, 24.4, 24.9));
    var pt = quadPt(g.paris, g.ctrl, g.dest, p);
    var dv = quadTan(g.paris, g.ctrl, g.dest, p);
    var ang = Math.atan2(dv.y, dv.x);
    ctx.save();
    ctx.globalAlpha *= a;
    ctx.translate(pt.x, pt.y); ctx.rotate(ang);
    ctx.fillStyle = INK;
    ctx.beginPath();
    ctx.moveTo(2.6 * u, 0); ctx.lineTo(-1.4 * u, 0.55 * u); ctx.lineTo(-2.3 * u, 0.3 * u);
    ctx.lineTo(-2.3 * u, -0.3 * u); ctx.lineTo(-1.4 * u, -0.55 * u); ctx.closePath(); ctx.fill();
    ctx.beginPath();
    ctx.moveTo(0.5 * u, 0.12 * u); ctx.lineTo(-1.2 * u, 2.3 * u); ctx.lineTo(-0.3 * u, 2.3 * u);
    ctx.lineTo(1.1 * u, 0.12 * u); ctx.closePath(); ctx.fill();
    ctx.beginPath();
    ctx.moveTo(0.5 * u, -0.12 * u); ctx.lineTo(-1.2 * u, -2.3 * u); ctx.lineTo(-0.3 * u, -2.3 * u);
    ctx.lineTo(1.1 * u, -0.12 * u); ctx.closePath(); ctx.fill();
    ctx.beginPath();
    ctx.moveTo(-1.6 * u, 0.1 * u); ctx.lineTo(-2.4 * u, 1.1 * u); ctx.lineTo(-1.9 * u, 1.1 * u);
    ctx.lineTo(-1.1 * u, 0.1 * u); ctx.closePath(); ctx.fill();
    ctx.beginPath();
    ctx.moveTo(-1.6 * u, -0.1 * u); ctx.lineTo(-2.4 * u, -1.1 * u); ctx.lineTo(-1.9 * u, -1.1 * u);
    ctx.lineTo(-1.1 * u, -0.1 * u); ctx.closePath(); ctx.fill();
    ctx.restore();
  }

  /* ---------- split-flap departure board ---------- */
  function drawBoard(ctx, g, t){
    if (t < 18.5 || t > 25.5) return;
    var S = g.S, u = g.u, k = g.k;
    var a = seg(t, 18.5, 19.1) * (1 - seg(t, 24.6, 25.3));
    if (a <= 0.005) return;
    ctx.save();
    ctx.globalAlpha *= a;
    var txt = 'DÉPART  PARIS → CONGRÈS';
    var n = txt.length;
    var tw = Math.min(S.w * 0.92, 74 * u);
    var ts = tw / (n * 0.72);
    var tx = tw / n;
    var th = ts * 1.85;
    var by = S.y + 2 * u + th / 2;
    var tt = 'DÉPART  PARIS → CONGRÈS';
    for (var i = 0; i < n; i++){
      var cxp = S.x + (S.w - tw) / 2 + (i + 0.5) * tx;
      var flip = seg(t, 20.2 + i * 0.11, 20.7 + i * 0.11);
      var sy = 1 - Math.sin(flip * Math.PI);
      var ch;
      if (flip <= 0) ch = g.scr[i % g.scr.length];
      else if (flip >= 1) ch = tt[i];
      else ch = g.scr[(i * 7 + 13) % g.scr.length];
      ctx.save();
      ctx.translate(cxp, by);
      ctx.fillStyle = '#0A1F30';
      ctx.fillRect(-tx / 2 + 0.08 * u, -th / 2, tx - 0.16 * u, th);
      ctx.scale(1, Math.max(0.06, sy));
      mono(ctx, ts, ch, 0, 0, '#FFFFFF', 'center', 1);
      ctx.restore();
    }
    ctx.restore();
  }

  /* ---------- congress hall ---------- */
  function drawHall(ctx, g, t){
    if (t < 24.9 || t > 29.6) return;
    var S = g.S, u = g.u, k = g.k;
    var a = seg(t, 25.7, 26.4) * (1 - seg(t, 28.4, 29.2));
    if (a <= 0.005) return;
    var hc = { x: S.x + 0.48 * S.w, y: S.y + 0.44 * S.h };
    ctx.save();
    ctx.globalAlpha *= a;
    // hall floor plan
    ctx.strokeStyle = INK; ctx.lineWidth = Math.max(1.2, 1.6 * k);
    ctx.globalAlpha *= 0.5; ctx.globalAlpha /= 0.5;
    ctx.save();
    ctx.globalAlpha *= 0.35;
    rr(ctx, hc.x - 30 * u, hc.y - 22 * u, 60 * u, 44 * u, 1.5 * u);
    ctx.stroke();
    ctx.restore();
    // stage bar
    var sp = seg(t, 26.0, 26.5);
    if (sp > 0){
      ctx.fillStyle = INK;
      ctx.fillRect(hc.x + lerp(-14 * u, -26 * u, sp), hc.y - 19 * u, lerp(28 * u, 52 * u, sp), 2.2 * u);
    }
    // 6 rows of seats
    for (var r = 0; r < 6; r++){
      var rp = seg(t, 26.2 + r * 0.12, 26.7 + r * 0.12);
      if (rp <= 0) continue;
      var ry = hc.y - 13 * u + r * 3.2 * u;
      var cnt = 10;
      for (var c = 0; c < cnt; c++){
        var sx = hc.x - 22.5 * u + c * 5 * u;
        var x0 = lerp(sx, Math.max(sx, lerp(hc.x, sx, rp)), 1);
        var fx = hc.x + (sx - hc.x) * rp;
        ctx.fillStyle = INK;
        ctx.globalAlpha *= 0.55; ctx.globalAlpha /= 0.55;
        ctx.save();
        ctx.globalAlpha *= 0.6 * rp;
        ctx.fillRect(fx - 1.1 * u, ry, 2.2 * u, 1.6 * u);
        ctx.restore();
      }
    }
    // two vertical banners
    var bp = seg(t, 26.6, 27.1);
    if (bp > 0){
      ctx.save();
      ctx.globalAlpha *= bp;
      ctx.fillStyle = ORANGE;
      var bh = lerp(4 * u, 26 * u, bp);
      ctx.fillRect(hc.x - 28 * u, hc.y - 21 * u, 1.8 * u, bh * 0.55);
      ctx.fillRect(hc.x + 26.2 * u, hc.y - 21 * u, 1.8 * u, bh * 0.55);
      ctx.restore();
    }
    ctx.restore();
    // pulsing assistance ring (pure function of t)
    var pa = seg(t, 26.8, 27.4) * (1 - seg(t, 28.4, 29.2));
    if (pa > 0.005){
      var ax = hc.x + 30 * u, ay = hc.y + 24 * u;
      var ph = (Math.sin(t * 2.4) + 1) / 2;
      ctx.save();
      ctx.globalAlpha *= pa;
      ctx.strokeStyle = INK;
      ctx.lineWidth = Math.max(1.2, 1.5 * k);
      ctx.beginPath(); ctx.arc(ax, ay, 1.4 * u, 0, Math.PI * 2); ctx.stroke();
      ctx.strokeStyle = ORANGE;
      ctx.globalAlpha *= pa * (1 - ph) * 0.9;
      ctx.lineWidth = Math.max(1, 1.4 * k);
      ctx.beginPath(); ctx.arc(ax, ay, 1.4 * u + ph * 2.6 * u, 0, Math.PI * 2); ctx.stroke();
      ctx.restore();
      mono(ctx, 1.3 * u, 'ASSISTANCE 24H/24 · 7J/7', ax + 3 * u, ay, INK, 'left', pa);
    }
  }

  /* ---------- drifting receipts ---------- */
  function drawReceipts(ctx, g, t){
    if (t < 26.4 || t > 29.4) return;
    var S = g.S, u = g.u, k = g.k;
    ctx.save();
    ctx.beginPath(); ctx.rect(S.x, S.y, S.w, S.h); ctx.clip();
    var rx = S.x + 0.30 * S.w, ry = S.y + 0.72 * S.h;
    for (var i = 0; i < 5; i++){
      var p = seg(t, 26.5 + i * 0.3, 27.6 + i * 0.3);
      if (p <= 0) continue;
      var seed = g.receipts[i];
      var x = lerp(rx + seed[0] * u, rx + seed[0] * 0.4 * u, p);
      var y = lerp(S.y - 5 * u, ry + seed[1] * 0.3 * u, p);
      var a = p * (1 - seg(t, 27.9 + i * 0.1, 28.5 + i * 0.1));
      if (a <= 0.005) continue;
      ctx.save();
      ctx.globalAlpha *= a;
      ctx.translate(x, y);
      ctx.rotate(seed[2] * p);
      ctx.fillStyle = '#FFFFFF';
      ctx.fillRect(-2.4 * u, -1.6 * u, 4.8 * u, 3.2 * u);
      ctx.strokeStyle = INK; ctx.globalAlpha *= 0.35; ctx.lineWidth = Math.max(1, k);
      ctx.strokeRect(-2.4 * u, -1.6 * u, 4.8 * u, 3.2 * u);
      ctx.globalAlpha /= 0.35;
      ctx.globalAlpha *= 0.4; ctx.globalAlpha /= 0.4;
      ctx.save();
      ctx.globalAlpha *= 0.4;
      ctx.beginPath();
      ctx.moveTo(-1.7 * u, -0.5 * u);
      ctx.lineTo(1.7 * u, -0.5 * u);
      ctx.moveTo(-1.7 * u, 0.4 * u);
      ctx.lineTo(1.7 * u, 0.4 * u);
      ctx.strokeStyle = INK; ctx.lineWidth = Math.max(1, k);
      ctx.stroke();
      ctx.restore();
      ctx.restore();
    }
    ctx.restore();
  }

  /* ---------- report sheet (K30) ---------- */
  function drawReport(ctx, g, t){
    if (t < 28.4) return;
    var S = g.S, u = g.u, k = g.k;
    var a = seg(t, 28.5, 29.2);
    if (a <= 0.005) return;
    var rise = seg(t, 28.7, 29.4);
    var sw = 46 * u, sh = 58 * u;
    var cx = lerp(S.x + 0.62 * S.w, S.x + 0.56 * S.w, rise);
    var cy = lerp(S.y + S.h + sh, S.y + 0.50 * S.h, rise);

    ctx.save();
    ctx.globalAlpha *= a;
    ctx.translate(cx, cy); ctx.rotate(1.5 * Math.PI / 180); ctx.translate(-sw / 2, -sh / 2);
    card(ctx, u, k, sw / 2, sh / 2, sw, sh, 0);
    ctx.translate(sw / 2, sh / 2); ctx.translate(-sw / 2, -sh / 2);

    serif(ctx, 3 * u, 'Reporting', 0.09 * sw, 0.09 * sh, INK, 'left', 1);

    // bar chart, 6 seeded bars
    ctx.strokeStyle = INK; ctx.globalAlpha *= 0.35; ctx.lineWidth = Math.max(1, k);
    ctx.beginPath(); ctx.moveTo(0.09 * sw, 0.20 * sh); ctx.lineTo(0.91 * sw, 0.20 * sh); ctx.stroke();
    ctx.globalAlpha /= 0.35;
    for (var i = 0; i < 6; i++){
      var bp = seg(t, 28.8 + i * 0.1, 29.3 + i * 0.1);
      if (bp <= 0) continue;
      var bh = g.chart[i] * 0.30 * sh * bp;
      var bx = 0.13 * sw + i * 0.13 * sw;
      ctx.fillStyle = INK;
      ctx.fillRect(bx, 0.20 * sh - bh, 0.07 * sw, bh);
    }

    // two rows with ticks
    var rows = ['NOTES DE FRAIS', 'FACTURES DÉMATÉRIALISÉES'];
    for (var r = 0; r < 2; r++){
      var by = (0.60 + r * 0.13) * sh;
      mono(ctx, 1.5 * u, rows[r], 0.09 * sw, by, INK, 'left', 1);
      tickStroke(ctx, u, k, 0.86 * sw, by - 0.3 * u, 1.4 * u, seg(t, 29.0 + r * 0.25, 29.4 + r * 0.25), INK);
    }
    ctx.restore(); // card
    ctx.restore();
  }

  /* ---------- ambient paper ---------- */
  function drawAmbient(ctx, g){
    var S = g.S, u = g.u;
    // faint ruled grid inside S
    ctx.save();
    ctx.beginPath(); ctx.rect(S.x, S.y, S.w, S.h); ctx.clip();
    ctx.strokeStyle = INK; ctx.globalAlpha *= 0.05;
    ctx.lineWidth = 1;
    ctx.beginPath();
    var gx = S.x;
    while (gx <= S.x + S.w + 0.1){ ctx.moveTo(gx, S.y); ctx.lineTo(gx, S.y + S.h); gx += 4 * u; }
    var gy = S.y;
    while (gy <= S.y + S.h + 0.1){ ctx.moveTo(S.x, gy); ctx.lineTo(S.x + S.w, gy); gy += 4 * u; }
    ctx.stroke();
    ctx.restore();
  }

  /* ---------- timeline at bottom of S ---------- */
  function drawTimeline(ctx, g, t){
    var S = g.S, u = g.u, k = g.k;
    var y = S.y + S.h - 0.15 * u;
    var h = 0.3 * u;
    ctx.save();
    ctx.fillStyle = INK; ctx.globalAlpha *= 0.2;
    ctx.fillRect(S.x, y - h / 2, S.w, h);
    ctx.globalAlpha /= 0.2;
    ctx.fillStyle = ORANGE;
    ctx.fillRect(S.x, y - h / 2, S.w * clamp01(t / 30), h);
    for (var i = 0; i <= 6; i++){
      var tx = S.x + (i / 6) * S.w;
      ctx.fillStyle = INK; ctx.globalAlpha *= 0.35; ctx.globalAlpha /= 0.35;
      ctx.save();
      ctx.globalAlpha *= 0.35;
      ctx.fillRect(tx - 0.15 * u, y - h, 0.3 * u, h * 2);
      ctx.restore();
    }
    ctx.restore();
  }

  /* ---------- grain ---------- */
  function drawGrain(ctx, g){
    ctx.save();
    ctx.fillStyle = INK;
    ctx.globalAlpha *= 0.04;
    var gr = g.grain;
    for (var i = 0; i < gr.length; i++){
      ctx.fillRect(gr[i][0], gr[i][1], 1.1 * g.k, 1.1 * g.k);
    }
    ctx.restore();
  }

  /* ---------- main draw ---------- */
  function draw(ctx, W, H, t){
    var g = geo(W, H);
    var S = g.S, u = g.u;

    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.fillStyle = PAPER;
    ctx.fillRect(0, 0, W, H);
    ctx.lineCap = 'butt'; ctx.lineJoin = 'miter';

    drawAmbient(ctx, g);

    // scene content
    if (t < 10.2) drawSheet(ctx, g, t);
    if (t >= 9.2 && t < 21.6) drawMap(ctx, g, Math.min(t, 15.5));
    if (t >= 27.4){
      // map again for finale (route fading handled inside)
      drawMap(ctx, g, t);
    }
    if (t >= 10.6){
      // print documents into view first, then docs/wallet system handles rest
      drawDocs(ctx, g, t);
    }
    drawPlane(ctx, g, t);
    drawBoard(ctx, g, t);
    drawHall(ctx, g, t);
    drawReceipts(ctx, g, t);
    drawReport(ctx, g, t);

    drawTimeline(ctx, g, t);
    drawGrain(ctx, g);
  }

  window.AVFilm = { draw: draw, DURATION: 30 };
})();