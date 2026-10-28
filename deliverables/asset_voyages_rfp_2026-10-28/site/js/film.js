/* film.js: « Du brief au retour », a 30 s vector film drawn as a pure function of time.
   First draft by z-ai/glm-5.3 (research/glm_log.md), reviewed and re-choreographed by hand.
   Seven keyframes at 0,5,…,30 s: Brief, Politique voyage, Itinéraire, Réservation, Départ, Sur place, Retour.
   API: window.AVFilm.draw(ctx, W, H, t), DURATION = 30. Public facts only; no figures, no names. */
(function () {
  'use strict';
  var INK = '#0A1F30', NAVY = '#0D3048', OR = '#EF760D', PAPER = '#F2EEE5', WHITE = '#FFFFFF';
  var SERIF = '"EB Garamond", Georgia, serif', MONO = 'ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace';
  var cache = {};

  function cl(x, a, b) { return x < a ? a : x > b ? b : x; }
  function ease(x) { x = cl(x, 0, 1); return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; }
  function back(x) { x = cl(x, 0, 1); var c = 1.6; return 1 + (c + 1) * Math.pow(x - 1, 3) + c * Math.pow(x - 1, 2); }
  function seg(t, a, b) { return ease((t - a) / (b - a)); }
  function lin(t, a, b) { return cl((t - a) / (b - a), 0, 1); }
  function mix(a, b, k) { return a + (b - a) * k; }
  function rng(seed) { return function () { seed |= 0; seed = seed + 0x6D2B79F5 | 0; var r = Math.imul(seed ^ seed >>> 15, 1 | seed); r = r + Math.imul(r ^ r >>> 7, 61 | r) ^ r; return ((r ^ r >>> 14) >>> 0) / 4294967296; }; }

  /* ---------- geometry, computed once per size ---------- */
  function geo(W, H) {
    var key = W + 'x' + H; if (cache[key]) return cache[key];
    var land = W / H >= 1.2, S;
    if (land) S = { x: W * 0.43, y: H * 0.11, w: W * 0.54, h: H * 0.8 };
    else S = { x: W * 0.04, y: H * 0.035, w: W * 0.92, h: H * 0.74 };
    var u = Math.min(S.w, S.h) / 94;
    var g = { land: land, S: S, u: u, cx: S.x + S.w / 2, cy: S.y + S.h / 2, hw: S.w / u / 2, lw: 1 / u };
    g.MW = Math.min(g.hw - 2, 64); g.MH = 42;
    var r = rng(1789);
    /* paper grain */
    var gc = document.createElement('canvas'); gc.width = 256; gc.height = 256; var gx = gc.getContext('2d');
    for (var i = 0; i < 2600; i++) { gx.fillStyle = r() < 0.5 ? 'rgba(10,31,48,.05)' : 'rgba(255,255,255,.35)'; gx.fillRect(r() * 256, r() * 256, 1, 1); }
    g.grain = gc;
    /* land masses: noisy blobs in map units */
    var blobs = [[-30, 14, 22, 15], [-6, 30, 16, 9], [26, -14, 24, 17], [4, -30, 14, 8], [-44, -24, 10, 9], [46, 22, 12, 10]];
    g.isles = blobs.map(function (b, k) {
      var pts = [], n = 48, ph = [r() * 6, r() * 6, r() * 6];
      for (var j = 0; j < n; j++) {
        var a = j / n * Math.PI * 2, d = 1 + 0.12 * Math.sin(a * 3 + ph[0]) + 0.07 * Math.sin(a * 7 + ph[1]) + 0.04 * Math.sin(a * 13 + ph[2]);
        pts.push([b[0] + Math.cos(a) * b[2] * d, b[1] + Math.sin(a) * b[3] * d]);
      }
      return pts;
    });
    g.bars = [0.42, 0.66, 0.5, 0.82, 0.58, 0.74];
    g.tiles = []; for (i = 0; i < 40; i++) g.tiles.push('ABCDEFGHLMNOPRSTUV'.charAt(Math.floor(r() * 18)));
    g.code = []; for (i = 0; i < 26; i++) g.code.push(0.25 + r() * 0.75);
    cache[key] = g; return g;
  }

  /* ---------- drawing helpers (stage units) ---------- */
  function rr(c, x, y, w, h, rad) { c.beginPath(); c.moveTo(x + rad, y); c.arcTo(x + w, y, x + w, y + h, rad); c.arcTo(x + w, y + h, x, y + h, rad); c.arcTo(x, y + h, x, y, rad); c.arcTo(x, y, x + w, y, rad); c.closePath(); }
  function txt(c, s, x, y, size, font, color, align, alpha) { c.save(); c.globalAlpha *= alpha == null ? 1 : alpha; c.fillStyle = color || INK; c.font = (font === 'serif' ? '500 ' + size + 'px ' + SERIF : '600 ' + size + 'px ' + MONO); c.textAlign = align || 'left'; c.textBaseline = 'alphabetic'; c.fillText(s, x, y); c.restore(); }
  function line(c, g, x1, y1, x2, y2, px, color, alpha, dash) { c.save(); c.globalAlpha *= alpha == null ? 1 : alpha; c.strokeStyle = color || INK; c.lineWidth = (px || 1.4) * g.lw; if (dash) c.setLineDash(dash); c.beginPath(); c.moveTo(x1, y1); c.lineTo(x2, y2); c.stroke(); c.restore(); }
  /* a paper card centred at (x,y): shadow, white face, hairline, then contents in local coordinates */
  function card(c, g, x, y, w, h, rot, sc, alpha, fill, body) {
    if (alpha <= 0.003 || sc <= 0.003) return;
    c.save(); c.translate(x, y); c.rotate(rot * Math.PI / 180); c.scale(sc, sc); c.globalAlpha *= alpha;
    c.fillStyle = 'rgba(10,31,48,.10)'; rr(c, -w / 2 + 0.7, -h / 2 + 0.9, w, h, 0.6); c.fill();
    c.fillStyle = fill || WHITE; rr(c, -w / 2, -h / 2, w, h, 0.6); c.fill();
    c.strokeStyle = 'rgba(10,31,48,.32)'; c.lineWidth = g.lw; c.stroke();
    if (body) { c.translate(-w / 2, -h / 2); body(c); }
    c.restore();
  }
  function tick(c, g, x, y, s, k, color) { /* hand-drawn tick, k = 0..1 drawn */
    if (k <= 0) return; c.save(); c.strokeStyle = color || INK; c.lineWidth = 2 * g.lw; c.lineCap = 'round'; c.lineJoin = 'round';
    var p = [[x, y], [x + s * 0.38, y + s * 0.4], [x + s, y - s * 0.55]], L1 = 0.42; c.beginPath(); c.moveTo(p[0][0], p[0][1]);
    if (k < L1) c.lineTo(mix(p[0][0], p[1][0], k / L1), mix(p[0][1], p[1][1], k / L1));
    else { c.lineTo(p[1][0], p[1][1]); var q = (k - L1) / (1 - L1); c.lineTo(mix(p[1][0], p[2][0], q), mix(p[1][1], p[2][1], q)); }
    c.stroke(); c.restore();
  }
  function scribble(c, g, x, y, w, k, seed) { /* handwriting suggestion */
    if (k <= 0) return; c.save(); c.strokeStyle = NAVY; c.lineWidth = 1.5 * g.lw; c.lineCap = 'round'; c.beginPath();
    var n = Math.max(2, Math.floor(40 * k)); for (var i = 0; i <= n; i++) { var f = i / 40, xx = x + f * w, yy = y - 0.6 - 0.55 * Math.sin(f * 37 + seed) * Math.abs(Math.sin(f * 9 + seed)); if (i) c.lineTo(xx, yy); else c.moveTo(xx, yy); }
    c.stroke(); c.restore();
  }
  function stamp(c, g, x, y, r, label, k, rot) {
    if (k <= 0) return; var s = mix(1.6, 1, back(k)); c.save(); c.translate(x, y); c.rotate(rot * Math.PI / 180); c.scale(s, s); c.globalAlpha *= cl(k * 3, 0, 1) * 0.92;
    c.strokeStyle = OR; c.lineWidth = 2.2 * g.lw; c.beginPath(); c.arc(0, 0, r, 0, 7); c.stroke(); c.lineWidth = g.lw; c.beginPath(); c.arc(0, 0, r * 0.8, 0, 7); c.stroke();
    c.fillStyle = OR; c.font = '700 ' + (r * 0.3) + 'px ' + MONO; c.textAlign = 'center'; c.fillText(label[0], 0, -r * 0.05); c.font = '600 ' + (r * 0.2) + 'px ' + MONO; c.fillText(label[1], 0, r * 0.32);
    c.restore();
  }

  /* ---------- the map ---------- */
  var PARIS = [-26, 12], DEST = [28, -14], CTRL = [2, -40];
  function qpt(a, b, k, s) { var m = 1 - s; return [m * m * a[0] + 2 * m * s * k[0] + s * s * b[0], m * m * a[1] + 2 * m * s * k[1] + s * s * b[1]]; }
  function arc(c, g, a, b, k, from, to, px, color, alpha, dash) {
    if (to <= from) return; c.save(); c.globalAlpha *= alpha; c.strokeStyle = color; c.lineWidth = px * g.lw; c.lineCap = 'round'; if (dash) c.setLineDash(dash);
    c.beginPath(); for (var i = 0; i <= 60; i++) { var p = qpt(a, b, k, mix(from, to, i / 60)); if (i) c.lineTo(p[0], p[1]); else c.moveTo(p[0], p[1]); } c.stroke(); c.restore();
  }
  function pin(c, g, p, label, alpha, right, pulse, t) {
    if (alpha <= 0) return; c.save(); c.globalAlpha *= alpha;
    if (pulse) { for (var i = 0; i < 2; i++) { var q = (pulse + i * 0.5) % 1; c.strokeStyle = OR; c.globalAlpha = alpha * (1 - q) * 0.7; c.lineWidth = 1.4 * g.lw; c.beginPath(); c.arc(p[0], p[1], 1.6 + q * 6, 0, 7); c.stroke(); } c.globalAlpha = alpha; }
    c.fillStyle = WHITE; c.strokeStyle = INK; c.lineWidth = 1.6 * g.lw; c.beginPath(); c.arc(p[0], p[1], 1.5, 0, 7); c.fill(); c.stroke();
    c.fillStyle = INK; c.beginPath(); c.arc(p[0], p[1], 0.6, 0, 7); c.fill();
    if (right === 'below' && t < 23.5) txt(c, label, p[0], p[1] + 5, 2.3, 'mono', INK, 'center');
    else txt(c, label, p[0] + (right ? 2.8 : -2.8), p[1] + 0.9, 2.3, 'mono', INK, right ? 'left' : 'right');
    c.restore();
  }
  function drawMap(c, g, t, alpha, zoom, zc) {
    if (alpha <= 0.003) return;
    var MW = g.MW, MH = g.MH;
    c.save(); c.globalAlpha *= alpha;
    c.beginPath(); c.rect(-MW, -MH, MW * 2, MH * 2); c.clip();
    if (zoom !== 1) { c.translate(zc[0], zc[1]); c.scale(zoom, zoom); c.translate(-zc[0], -zc[1]); }
    var unfold = seg(t, 5.6, 7.4); /* the chart unfolds from the centre crease */
    c.save(); c.beginPath(); c.rect(-MW * unfold, -MH, MW * 2 * unfold, MH * 2); c.clip();
    c.fillStyle = 'rgba(10,31,48,.08)'; rr(c, -MW + 0.8, -MH + 1, MW * 2, MH * 2, 0.8); c.fill();
    c.fillStyle = '#E3EEF0'; rr(c, -MW, -MH, MW * 2, MH * 2, 0.8); c.fill();
    c.strokeStyle = 'rgba(10,31,48,.35)'; c.lineWidth = g.lw; c.stroke();
    /* graticule */
    c.strokeStyle = 'rgba(13,48,72,.12)'; c.lineWidth = g.lw;
    for (var gx = -MW + 8; gx < MW; gx += 12) { c.beginPath(); c.moveTo(gx, -MH); c.quadraticCurveTo(gx + (gx / MW) * 4, 0, gx, MH); c.stroke(); }
    for (var gy = -MH + 10; gy < MH; gy += 12) { c.beginPath(); c.moveTo(-MW, gy); c.lineTo(MW, gy); c.stroke(); }
    /* land */
    g.isles.forEach(function (pts) {
      c.beginPath(); pts.forEach(function (p, i) { var x = cl(p[0], -MW + 1, MW - 1), y = cl(p[1], -MH + 1, MH - 1); if (i) c.lineTo(x, y); else c.moveTo(x, y); }); c.closePath();
      c.fillStyle = '#F7F3EA'; c.fill(); c.strokeStyle = 'rgba(10,31,48,.45)'; c.lineWidth = 1.1 * g.lw; c.stroke();
    });
    /* fold creases + compass */
    line(c, g, 0, -MH, 0, MH, 1, INK, 0.12); line(c, g, -MW, 0, MW, 0, 1, INK, 0.08);
    c.save(); c.translate(MW - 7, MH - 8); c.strokeStyle = INK; c.lineWidth = g.lw; c.globalAlpha *= 0.55; c.beginPath(); c.arc(0, 0, 3.4, 0, 7); c.stroke();
    c.fillStyle = INK; c.beginPath(); c.moveTo(0, -4.6); c.lineTo(0.9, 0); c.lineTo(-0.9, 0); c.closePath(); c.fill(); txt(c, 'N', 0, -5.4, 1.8, 'mono', INK, 'center'); c.restore();
    c.restore();
    /* routes */
    var A = alpha;
    arc(c, g, PARIS, DEST, [-2, -6], 0, seg(t, 7.2, 8.6), 1.2, INK, 0.22, [0.8, 1.2]);
    arc(c, g, PARIS, DEST, [10, -58], 0, seg(t, 7.4, 8.8), 1.2, INK, 0.22, [0.8, 1.2]);
    var main = seg(t, 7.6, 9.6);
    if (t < 25.5) arc(c, g, PARIS, DEST, CTRL, 0, main, 1.8, OR, 1, [1.6, 1.1]);
    /* flight trail */
    var fl = lin(t, 20.4, 23.6);
    if (fl > 0) arc(c, g, PARIS, DEST, CTRL, 0, ease(fl), 2.4, OR, 1);
    pin(c, g, PARIS, 'PARIS', seg(t, 6.6, 7.4), false);
    pin(c, g, DEST, 'VILLE DU CONGRÈS', seg(t, 7.0, 7.8), 'below', t > 23.4 && t < 25.5 ? (t - 23.4) * 0.9 : 0, t);
    if (fl > 0 && fl < 0.93) plane(c, g, Math.min(1, ease(fl) + 0.07));
    c.restore();
  }
  function plane(c, g, s) {
    var p = qpt(PARIS, DEST, CTRL, s), q = qpt(PARIS, DEST, CTRL, Math.min(1, s + 0.01)), a = Math.atan2(q[1] - p[1], q[0] - p[0]);
    c.save(); c.translate(p[0], p[1]); c.rotate(a); c.scale(1.25, 1.25); c.fillStyle = INK;
    c.beginPath(); c.moveTo(3.4, 0); c.quadraticCurveTo(2.6, -0.55, 0, -0.5); c.lineTo(-2.8, -0.45); c.lineTo(-3.4, -1.6); c.lineTo(-3.9, -1.6); c.lineTo(-3.5, 0);
    c.lineTo(-3.9, 1.6); c.lineTo(-3.4, 1.6); c.lineTo(-2.8, 0.45); c.lineTo(0, 0.5); c.quadraticCurveTo(2.6, 0.55, 3.4, 0); c.fill();
    c.beginPath(); c.moveTo(0.8, -0.4); c.lineTo(-1.2, -3.8); c.lineTo(-2, -3.8); c.lineTo(-1, -0.4); c.closePath(); c.fill();
    c.beginPath(); c.moveTo(0.8, 0.4); c.lineTo(-1.2, 3.8); c.lineTo(-2, 3.8); c.lineTo(-1, 0.4); c.closePath(); c.fill();
    c.restore();
  }

  /* ---------- documents ---------- */
  function brief(c, g, t) {
    return function (c) {
      txt(c, 'ASSET VOYAGES · BRIEF', 4, 6, 1.7, 'mono', OR);
      txt(c, 'Votre demande', 4, 14, 5.4, 'serif');
      line(c, g, 4, 17, 46, 17, 1, INK, 0.5);
      var rows = ['DÉPART', 'DESTINATION', 'DATES', 'VOYAGEURS'];
      rows.forEach(function (lb, i) { var y = 24 + i * 7; txt(c, lb, 4, y - 1.6, 1.6, 'mono', INK, 'left', 0.55); line(c, g, 17, y, 46, y, 1, INK, 0.25); scribble(c, g, 18, y, [14, 22, 17, 6][i], lin(t, 0.7 + i * 0.5, 1.2 + i * 0.5), i * 3.1); });
      var opts = ['Voyage d’affaires', 'Séminaire · groupe', 'Congrès international'];
      opts.forEach(function (lb, i) { var y = 56 + i * 5.2; c.strokeStyle = INK; c.lineWidth = 1.2 * g.lw; c.strokeRect(4, y - 2.6, 2.8, 2.8); txt(c, lb, 9, y - 0.2, 2.4, 'serif'); });
      tick(c, g, 4.5, 64.6, 2.4, lin(t, 3.0, 3.5), OR);
    };
  }
  function policy(c, g, t) {
    return function (c) {
      txt(c, 'RÈGLES DE L’ENTREPRISE', 4, 6, 1.7, 'mono', OR);
      txt(c, 'Politique voyage', 4, 13.5, 4.6, 'serif');
      line(c, g, 4, 16.5, 40, 16.5, 1, INK, 0.5);
      ['Transport', 'Hébergement', 'Assurance', 'Validation'].forEach(function (lb, i) {
        var y = 24 + i * 6.4; txt(c, lb, 4, y, 2.7, 'serif'); line(c, g, 4, y + 1.8, 40, y + 1.8, 1, INK, 0.18); tick(c, g, 35.5, y - 1, 2.4, lin(t, 3.3 + i * 0.22, 3.6 + i * 0.22), INK);
      });
    };
  }
  function boarding(c, g) {
    return function (c) {
      c.fillStyle = NAVY; c.fillRect(0, 0, 3, 17);
      txt(c, 'CARTE D’EMBARQUEMENT', 5.5, 4.6, 1.5, 'mono', OR);
      txt(c, 'Paris → Congrès', 5.5, 10.5, 4, 'serif');
      txt(c, 'VOL · SIÈGE · PORTE', 5.5, 14.2, 1.3, 'mono', INK, 'left', 0.5);
      line(c, g, 33, 1.2, 33, 15.8, 1, INK, 0.45, [0.6, 0.6]);
      for (var i = 0; i < 20; i++) { c.fillStyle = INK; c.fillRect(35 + i * 0.38, 4 + (1 - g.code[i]) * 4, i % 3 ? 0.18 : 0.3, 9 * g.code[i]); }
    };
  }
  function train(c, g) {
    return function (c) {
      txt(c, 'TRAIN', 3, 4.6, 1.6, 'mono', OR); txt(c, 'Aller · retour', 3, 10, 3.4, 'serif');
      line(c, g, 3, 12.2, 27, 12.2, 1, INK, 0.25); line(c, g, 3, 14.6, 20, 14.6, 1, INK, 0.25);
    };
  }
  function hotel(c, g) {
    return function (c) {
      txt(c, 'HÔTEL', 3, 4.6, 1.6, 'mono', OR); txt(c, 'Bon d’échange', 3, 10.4, 3.4, 'serif');
      for (var i = 0; i < 3; i++) line(c, g, 3, 13.4 + i * 1.8, 27 - i * 5, 13.4 + i * 1.8, 1, INK, 0.22);
    };
  }
  function badge(c, g) {
    return function (c) {
      c.fillStyle = OR; c.fillRect(0, 0, 18, 6.5); c.fillStyle = PAPER; rr(c, 7, 1.6, 4, 1.4, 0.7); c.fill();
      txt(c, 'BADGE', 9, 11.5, 1.6, 'mono', INK, 'center', 0.6); txt(c, 'Participant', 9, 17, 3.2, 'serif', INK, 'center');
      line(c, g, 3.5, 20.5, 14.5, 20.5, 1, INK, 0.25); line(c, g, 5, 22.8, 13, 22.8, 1, INK, 0.25);
    };
  }
  function programme(c, g) {
    return function (c) {
      txt(c, 'SÉMINAIRE', 3, 4.8, 1.5, 'mono', OR); txt(c, 'Programme', 3, 10.5, 3.6, 'serif');
      for (var i = 0; i < 6; i++) { txt(c, ['09:00', '10:30', '12:30', '14:00', '16:30', '19:30'][i], 3, 15.5 + i * 2.6, 1.3, 'mono', INK, 'left', 0.55); line(c, g, 9, 15.2 + i * 2.6, 19 - (i % 3) * 2, 15.2 + i * 2.6, 1, INK, 0.25); }
    };
  }
  /* the travel wallet; open: 0 closed .. 1 flap fully up */
  function wallet(c, g, x, y, sc, alpha, open, inner, frontA) {
    if (frontA == null) frontA = 1;
    if (alpha <= 0.003) return; var w = 40, h = 26;
    c.save(); c.translate(x, y); c.scale(sc, sc); c.globalAlpha *= alpha;
    c.fillStyle = 'rgba(10,31,48,.16)'; rr(c, -w / 2 + 0.9, -h / 2 + 1.2, w, h, 1.4); c.fill();
    c.fillStyle = '#0A2638'; rr(c, -w / 2, -h / 2, w, h, 1.4); c.fill();
    var f0 = Math.cos(open * Math.PI);
    if (f0 < 0) drawFlap(f0);
    if (inner) inner(c, sc);
    c.save(); c.globalAlpha *= frontA;
    c.fillStyle = NAVY; rr(c, -w / 2, -h / 2 + h * 0.34, w, h * 0.66, 1.4); c.fill();
    c.strokeStyle = 'rgba(255,255,255,.18)'; c.lineWidth = g.lw; c.setLineDash([0.6, 0.6]); rr(c, -w / 2 + 1.2, -h / 2 + h * 0.34 + 1.2, w - 2.4, h * 0.66 - 2.4, 1); c.stroke(); c.setLineDash([]);
    txt(c, 'ASSET VOYAGES', 0, h * 0.2, 2.2, 'mono', '#FFFFFF', 'center', 0.85);
    txt(c, 'POCHETTE DE VOYAGE', 0, h * 0.2 + 3.4, 1.3, 'mono', OR, 'center', 0.95);
    c.restore();
    /* flap hinged on the top edge */
    var f = f0; /* 1 closed (down), -1 open (up) */
    function drawFlap(f) { c.save(); c.translate(0, -h / 2); c.scale(1, f);
      c.fillStyle = f > 0 ? '#11405F' : '#0A2638'; c.beginPath(); c.moveTo(-w / 2, 0); c.lineTo(w / 2, 0); c.lineTo(w / 2, h * 0.3); c.quadraticCurveTo(0, h * 0.5, -w / 2, h * 0.3); c.closePath(); c.fill();
      c.restore(); }
    if (f >= 0) drawFlap(f);
    if (f > 0) { c.fillStyle = OR; c.beginPath(); c.arc(0, -h / 2 + h * 0.42 * f, 1, 0, 7); c.fill(); }
    c.restore();
  }

  /* ---------- the hall ---------- */
  function hall(c, g, t, alpha) {
    if (alpha <= 0.003) return;
    var x = -17, y = -6, w = 68, h = 58, s = mix(0.94, 1, seg(t, 23.6, 24.6));
    card(c, g, x, y, w, h, 0, s, alpha, WHITE, function (c) {
      txt(c, 'SALLE PLÉNIÈRE · PLAN', 4, 5, 1.6, 'mono', OR);
      var st = seg(t, 23.7, 24.1); c.fillStyle = NAVY; c.fillRect(w / 2 - 22 * st, 8, 44 * st, 4.4); if (st > 0.9) txt(c, 'SCÈNE', w / 2, 11.1, 1.6, 'mono', '#FFFFFF', 'center');
      var bn = seg(t, 24.0, 24.4); c.fillStyle = OR; c.fillRect(5, 8, 2.2, 9 * bn); c.fillRect(w - 7.2, 8, 2.2, 9 * bn);
      for (var r = 0; r < 6; r++) {
        var k = seg(t, 23.9 + r * 0.1, 24.3 + r * 0.1); if (k <= 0) continue;
        for (var i = 0; i < 16; i++) { if (i === 8) continue; var sx = w / 2 - 25.95 + i * 3.1, sy = 19 + r * 4.8 + (1 - k) * 3; c.globalAlpha = alpha * k; c.fillStyle = r < 2 ? NAVY : 'rgba(13,48,72,.55)'; rr(c, sx, sy, 2.3, 2, 0.4); c.fill(); }
      }
      c.globalAlpha = alpha;
      line(c, g, 4, h - 6, w - 4, h - 6, 1, INK, 0.2); txt(c, 'ACCUEIL', w / 2, h - 2.4, 1.5, 'mono', INK, 'center', 0.55);
      c.strokeStyle = 'rgba(10,31,48,.4)'; c.lineWidth = g.lw; c.strokeRect(3, 3 + 4, w - 6, h - 14);
    });
  }
  function assist(c, g, t, x, y, alpha) {
    if (alpha <= 0) return; c.save(); c.globalAlpha *= alpha;
    for (var i = 0; i < 3; i++) { var q = (t * 0.6 + i / 3) % 1; c.strokeStyle = OR; c.globalAlpha = alpha * (1 - q) * 0.8; c.lineWidth = 1.4 * g.lw; c.beginPath(); c.arc(x, y, 2 + q * 7, 0, 7); c.stroke(); }
    c.globalAlpha = alpha; c.fillStyle = OR; c.beginPath(); c.arc(x, y, 1.6, 0, 7); c.fill();
    txt(c, 'ASSISTANCE', x, y + 12, 1.8, 'mono', INK, 'center'); txt(c, '24H/24 · 7J/7', x, y + 14.6, 1.8, 'mono', OR, 'center');
    c.restore();
  }

  /* ---------- report ---------- */
  function report(c, g, t) {
    return function (c) {
      txt(c, 'BILAN DU DÉPLACEMENT', 4, 6, 1.7, 'mono', OR);
      txt(c, 'Reporting', 4, 14, 5.4, 'serif'); line(c, g, 4, 17, 52, 17, 1, INK, 0.5);
      /* return route inset */
      c.save(); c.fillStyle = '#E3EEF0'; rr(c, 4, 20, 48, 12, 0.6); c.fill(); c.restore();
      var a = [46, 28], b = [10, 28], k = [28, 16], s = seg(t, 26.6, 27.8);
      arc(c, g, a, b, k, 0, s, 1.6, OR, 1);
      c.fillStyle = INK; c.beginPath(); c.arc(a[0], a[1], 0.8, 0, 7); c.fill(); c.beginPath(); c.arc(b[0], b[1], 0.8, 0, 7); c.fill();
      if (s > 0.98) { c.fillStyle = OR; c.beginPath(); c.moveTo(b[0] - 0.6, b[1] - 0.2); c.lineTo(b[0] + 2.4, b[1] - 2.2); c.lineTo(b[0] + 2.6, b[1] + 0.6); c.closePath(); c.fill(); }
      txt(c, 'RETOUR · PARIS', 6, 30.6, 1.4, 'mono', INK, 'left', 0.6);
      /* bars */
      line(c, g, 4, 52, 52, 52, 1, INK, 0.4);
      g.bars.forEach(function (v, i) { var k2 = seg(t, 27.0 + i * 0.16, 27.8 + i * 0.16); c.fillStyle = i === 3 ? OR : NAVY; c.fillRect(7 + i * 7.6, 52 - 15 * v * k2, 4.4, 15 * v * k2); });
      ['Notes de frais', 'Factures dématérialisées', 'Statistiques'].forEach(function (lb, i) { var y = 59 + i * 5; txt(c, lb, 4, y, 2.6, 'serif'); line(c, g, 4, y + 1.6, 52, y + 1.6, 1, INK, 0.15); tick(c, g, 47.5, y - 1, 2.4, lin(t, 28.2 + i * 0.3, 28.6 + i * 0.3), OR); });
    };
  }

  /* ---------- the film ---------- */
  function draw(ctx, W, H, t) {
    t = cl(t, 0, 30); var g = geo(W, H);
    ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalAlpha = 1;
    ctx.fillStyle = PAPER; ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = ctx.createPattern(g.grain, 'repeat'); ctx.fillRect(0, 0, W, H);
    /* crop marks around the stage, as on a print proof */
    var S = g.S, m = 14 * (W / 1920); ctx.strokeStyle = 'rgba(10,31,48,.28)'; ctx.lineWidth = Math.max(1, W / 1920);
    [[S.x, S.y, -1, -1], [S.x + S.w, S.y, 1, -1], [S.x, S.y + S.h, -1, 1], [S.x + S.w, S.y + S.h, 1, 1]].forEach(function (k) { ctx.beginPath(); ctx.moveTo(k[0] + k[2] * 6, k[1]); ctx.lineTo(k[0] + k[2] * (6 + m), k[1]); ctx.moveTo(k[0], k[1] + k[3] * 6); ctx.lineTo(k[0], k[1] + k[3] * (6 + m)); ctx.stroke(); });
    var c = ctx; c.save(); c.translate(g.cx, g.cy); c.scale(g.u, g.u);

    /* map (from 5.6 s), zooms into the destination at arrival, then gives way */
    var mapA = 1 - seg(t, 10.4, 11.6) * 0.72 + seg(t, 16.8, 18.2) * 0.72;
    mapA *= 1 - seg(t, 23.9, 24.7);
    var zoom = 1 + seg(t, 23.5, 24.7) * 1.6;
    if (t > 5.5 && t < 24.8) drawMap(c, g, t, mapA, zoom, DEST);

    /* 0–10 s: the brief and the policy, then they dock at Paris */
    var dock = seg(t, 5.6, 7.6), out = seg(t, 9.6, 10.8);
    if (t < 11) {
      var bx = mix(-4, PARIS[0] - 9, dock), by = mix(0, PARIS[1] + 10, dock), bs = mix(1, 0.24, dock);
      var pIn = seg(t, 1.8, 3.0);
      card(c, g, bx, by, 50, 72, mix(-2, -6, dock), bs, 1 - out, WHITE, brief(c, g, t));
      card(c, g, mix(mix(60, 16, pIn), PARIS[0] - 5, dock), mix(mix(6, 4, pIn), PARIS[1] + 12, dock), 44, 50, mix(3, 4, dock), mix(1, 0.24, dock), pIn * (1 - out), WHITE, policy(c, g, t));
      if (dock < 1) stamp(c, g, mix(28, PARIS[0] + 1, dock), mix(20, PARIS[1] + 16, dock), 7 * mix(1, 0.24, dock), ['POLITIQUE', 'APPLIQUÉE'], seg(t, 4.0, 4.5) * (1 - out), -12);
    }

    /* 10–16 s: bookings print out of the brief and slide INTO a large open pochette (the pack) */
    var docs = [
      { w: 44, h: 17, x: -14, y: -24, r: -6, f: boarding(c, g) },
      { w: 30, h: 17, x: 18, y: -30, r: 6, f: train(c, g) },
      { w: 30, h: 19, x: -24, y: -6, r: -4, f: hotel(c, g) },
      { w: 18, h: 26, x: 24, y: -8, r: 8, f: badge(c, g) }
    ];
    var wIn = seg(t, 11.4, 12.4), flap = seg(t, 15.9, 16.8), wGo = seg(t, 17.0, 18.4);
    var START = [PARIS[0] + 9, PARIS[1] + 7];
    var fly = lin(t, 20.4, 23.6), fe = ease(fly), onRoute = qpt(PARIS, DEST, CTRL, fe);
    var front = seg(t, 23.7, 24.5);                     /* arrival: the pochette comes to the front of the hall */
    var WX = mix(0, START[0], wGo), WY = mix(18, START[1], wGo), WS = mix(1.3, 0.5, wGo), WR = 0;
    if (t > 20.4) { var lift = seg(t, 20.4, 21.2); WX = onRoute[0] + mix(9, 0, lift); WY = onRoute[1] + mix(7, -3, lift); var q2 = qpt(PARIS, DEST, CTRL, Math.min(1, fe + 0.01)); WR = Math.atan2(q2[1] - onRoute[1], q2[0] - onRoute[0]) * 0.25; }
    function docsIn(c) {
      docs.forEach(function (d, i) {
        var e = seg(t, 10.5 + i * 0.45, 12.0 + i * 0.45); if (e <= 0) return;
        var pk = seg(t, 13.2 + i * 0.3, 14.6 + i * 0.3);
        var x = mix(mix(PARIS[0] - 6, d.x, e), (i - 1.5) * 6, pk), y = mix(mix(PARIS[1] + 10, d.y, e), 10 + i * 0.8, pk);
        var sc = mix(mix(0.2, 1, e), 0.8, pk), r = mix(d.r * e, (i - 1.5) * 2.5, pk);
        card(c, g, x, y, d.w, d.h, r, sc, 1, i === 1 ? '#FBF8F1' : WHITE, d.f);
      });
    }
    if (t >= 10.4 && t < 11.4) docsIn(c);
    var walletA = wIn * (1 - seg(t, 25.6, 26.4));
    if (t >= 11.4 && t < 23.7) {
      var inner = flap < 1 ? function (c, sc) { c.save(); c.rotate(-WR); c.scale(1 / sc, 1 / sc); c.translate(-WX, -WY); docsIn(c); c.restore(); } : null;
      c.save(); c.translate(WX, WY); c.rotate(WR);
      wallet(c, g, 0, 0, WS, walletA, 1 - flap, inner, 1);
      c.restore();
    }

    /* 17.8–24 s: the departure board */
    var bA = seg(t, 17.8, 18.5) * (1 - seg(t, 23.4, 24.2));
    if (bA > 0) board(c, g, t, bA);

    /* 23.6–26 s: on site — the hall assembles, the same pochette comes forward and the documents come OUT */
    var hallA = seg(t, 23.6, 24.4) * (1 - seg(t, 25.6, 26.6));
    var hallX = -seg(t, 25.6, 26.6) * 30;
    if (t >= 23.6 && t < 26.8) {
      c.save(); c.translate(hallX, 0); if (!g.land) { c.translate(-2, 2); c.scale(0.84, 0.84); }
      c.save(); c.globalAlpha *= 1 - seg(t, 25.6, 26.6);
      hall(c, g, t, hallA);
      var un = seg(t, 24.2, 24.6), out = seg(t, 24.4, 25.0);
      var HX = mix(DEST[0], 32, front), HY = mix(DEST[1] - 3, 24, front), HS = mix(0.5, 0.85, front);
      var outDocs = [
        { w: 22, h: 30, x: 22, y: 2, r: -10, s: 0.7, f: programme(c, g) },
        { w: 18, h: 26, x: 36, y: -4, r: 8, s: 0.8, f: badge(c, g) },
        { w: 44, h: 17, x: 44, y: 8, r: 12, s: 0.55, f: boarding(c, g) }
      ];
      wallet(c, g, HX, HY, HS, 1, un, out > 0 ? function (c, sc) {
        c.save(); c.scale(1 / sc, 1 / sc); c.translate(-HX, -HY);
        outDocs.forEach(function (d, i) { var k = seg(t, 24.4 + i * 0.12, 24.9 + i * 0.12); card(c, g, mix(HX + (i - 1) * 4, d.x, k), mix(HY + 4, d.y, k), d.w, d.h, mix(0, d.r, k), mix(0.6, d.s, k), 1, WHITE, d.f); });
        c.restore();
      } : null, 1);
      c.restore(); c.restore();
      assist(c, g, t, Math.min(g.hw - 9, 48), -34, hallA * seg(t, 24.4, 24.9));
    }

    /* 25.6–30 s: receipts fall into the report */
    var rIn = seg(t, 25.8, 27.0);
    if (rIn > 0) {
      for (var i = 0; i < 5; i++) {
        var k = lin(t, 26.0 + i * 0.35, 27.4 + i * 0.35); if (k <= 0 || k >= 1) continue;
        var e2 = ease(k); card(c, g, mix(-30 + i * 14, 0, e2), mix(-48, 8, e2), 8, 10, mix(-20 + i * 9, 0, e2), mix(1, 0.4, e2), 1 - lin(k, 0.85, 1), WHITE, function (c) { line(c, g, 1.5, 3, 6.5, 3, 1, INK, 0.3); line(c, g, 1.5, 5, 5, 5, 1, INK, 0.3); line(c, g, 1.5, 7.5, 6.5, 7.5, 1, OR, 0.6); });
      }
      card(c, g, mix(40, 0, rIn), 0, 56, 72, mix(4, -1.5, rIn), 1, rIn, WHITE, report(c, g, t));
    }
    c.restore();
  }

  function board(c, g, t, alpha) {
    var s = 'DÉPART  PARIS → CONGRÈS', n = s.length, tw = 3.5, gap = 0.32, W = n * (tw + gap), x0 = -W / 2, y0 = -g.MH - 2 + mix(-4, 0, alpha), th = 5;
    c.save(); c.globalAlpha *= alpha;
    c.fillStyle = 'rgba(10,31,48,.18)'; rr(c, x0 - 1.4, y0 - 1.0, W + 2.8, th + 2.6, 0.8); c.fill();
    c.fillStyle = '#071521'; rr(c, x0 - 1.6, y0 - 1.3, W + 2.8, th + 2.6, 0.8); c.fill();
    for (var i = 0; i < n; i++) {
      var ft = 18.1 + i * 0.04, k = lin(t, ft, ft + 0.26), ch = k < 0.5 ? g.tiles[i] : s.charAt(i), sy = Math.abs(Math.cos(k * Math.PI));
      if (k >= 1) sy = 1; var x = x0 + i * (tw + gap);
      c.fillStyle = '#16293A'; rr(c, x, y0, tw, th, 0.3); c.fill();
      c.save(); c.translate(x + tw / 2, y0 + th / 2); c.scale(1, Math.max(0.05, sy));
      if (ch !== ' ') { c.fillStyle = (i >= 8 ? '#FFFFFF' : OR); c.font = '700 3.4px ' + MONO; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText(ch, 0, 0.2); }
      c.restore();
      c.fillStyle = 'rgba(0,0,0,.5)'; c.fillRect(x, y0 + th / 2 - 0.06, tw, 0.12);
    }
    c.restore();
  }

  window.AVFilm = { draw: draw, DURATION: 30 };
}());
