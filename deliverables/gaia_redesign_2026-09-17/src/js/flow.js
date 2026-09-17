'use strict';
/* The hero: one drawn landscape that rearranges itself across seven states.
   Scroll drives a single number (`position`, 0..6); the horizon polyline lerps
   vertex-by-vertex between two y-profiles and each element fades in on a
   triangular window around its own state. Time-based motion (blades, ripples,
   birds) runs at ~30fps, only while on screen and the tab is visible.
   Maths lives in motion.js so it can be tested headlessly. */

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

  /* ---------------------------------------------------------- scene data */
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

  /* Sky stops per state: [top, bottom]. Navy family, shifted in hue only. */
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

  /* --------------------------------------------------------- resize */
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

  /* --------------------------------------------------------- elements */

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

  /* State 0 — the survey sheet the whole scene is drawn on. */
  function drawIntro(w) {
    if (w <= 0.001) return;
    var i;
    stroke(WHITE, 0.10 * w, 1);
    ctx.setLineDash([2, 7]);
    for (i = 1; i <= 3; i += 1) {
      ctx.beginPath();
      for (var x = 0; x <= W; x += W / 40) ctx.lineTo(x, yAt(x) - i * H * 0.052);
      ctx.stroke();
    }
    ctx.setLineDash([]);
    stroke(GREEN, 0.26 * w, 1);
    for (i = 0; i < 9; i += 1) {
      var tx = (i + 0.5) * (W / 9);
      var ty = yAt(tx);
      ctx.beginPath();
      ctx.moveTo(tx, ty - 7);
      ctx.lineTo(tx, ty + 7);
      ctx.stroke();
    }
  }

  function drawGround() {
    ctx.beginPath();
    ctx.moveTo(0, yAt(0));
    for (var x = W / 60; x <= W; x += W / 60) ctx.lineTo(x, yAt(x));
    ctx.lineTo(W, H);
    ctx.lineTo(0, H);
    ctx.closePath();
    ctx.fillStyle = rgba(DEEP, 0.94);
    ctx.fill();
    stroke(GREEN, 0.6, 1.5);
    ctx.beginPath();
    ctx.moveTo(0, yAt(0));
    for (var x2 = W / 60; x2 <= W; x2 += W / 60) ctx.lineTo(x2, yAt(x2));
    ctx.stroke();
  }

  /* State 1 — onshore wind and hydropower. */
  var MASTS = [0.40, 0.515, 0.625, 0.745, 0.875];
  function drawWind(w, now) {
    if (w <= 0.001) return;
    var e = M.easeOutQuart(w);
    var spin = (now / 1000) * ((2 * PI2) / 60);
    for (var i = 0; i < MASTS.length; i += 1) {
      var x = MASTS[i] * W;
      var base = yAt(x);
      var h = (0.115 + M.hashNoise(i, 21) * 0.055) * H * e;
      var hub = base - h;
      stroke(WHITE, 0.34 * w, 1.5);
      ctx.beginPath();
      ctx.moveTo(x, base);
      ctx.lineTo(x, hub);
      ctx.stroke();
      stroke(GREEN, 0.5 * w, 1.5);
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
    /* hydropower: a dam wall on the left with a still reservoir behind it */
    var dx = 0.13 * W;
    var dw = 0.15 * W;
    var dy = yAt(dx + dw / 2);
    var dh = 0.052 * H * e;
    stroke(WHITE, 0.3 * w, 1.5);
    ctx.beginPath();
    ctx.moveTo(dx, dy);
    ctx.lineTo(dx + dw * 0.14, dy - dh);
    ctx.lineTo(dx + dw * 0.86, dy - dh);
    ctx.lineTo(dx + dw, dy);
    ctx.stroke();
    stroke(GREEN, 0.22 * w, 1);
    for (var k = 1; k <= 3; k += 1) {
      ctx.beginPath();
      ctx.moveTo(dx - 0.09 * W, dy - dh + k * (dh / 4));
      ctx.lineTo(dx + dw * 0.12, dy - dh + k * (dh / 4));
      ctx.stroke();
    }
  }

  /* State 2 — solar. Rows of slabs whose tilt opens from 8deg to 26deg. */
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
      var y = yAt(0.5 * W) + (0.035 + depth * depth * 0.30) * H;
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
        ctx.fillStyle = rgba(SURF, 0.6 * w);
        ctx.fill();
        stroke(GREEN, 0.42 * w, 1.2);
        ctx.stroke();
      }
    }
  }

  /* States 3 and 4 share one rising water plane. */
  function waterTop(ww) {
    return H - (0.06 + 0.24 * M.easeOutQuart(ww)) * H;
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
    ctx.fillStyle = rgba(SURF, 0.62 * ww);
    ctx.fill();
    stroke(GREEN, 0.34 * ww, 1.2);
    ctx.stroke();
    for (var r = 1; r <= 3; r += 1) {
      stroke(GREEN, (0.2 - r * 0.04) * ww, 1);
      ctx.beginPath();
      for (var x2 = 0; x2 <= W; x2 += W / 70) {
        var amp = 0.005 * H * r;
        ctx.lineTo(x2, top + swell + r * 0.055 * H + Math.sin(x2 / (W / (3 + r)) + now / (1800 + r * 700)) * amp);
      }
      ctx.stroke();
    }
    /* flood-plain contours hugging the horizon */
    stroke(WHITE, 0.13 * ww, 1);
    ctx.setLineDash([3, 6]);
    for (var c = 1; c <= 3; c += 1) {
      ctx.beginPath();
      for (var x3 = 0; x3 <= W; x3 += W / 40) ctx.lineTo(x3, yAt(x3) + c * 0.024 * H);
      ctx.stroke();
    }
    ctx.setLineDash([]);
  }

  /* State 4 — barrage gates on the water, storage blocks on the shore. */
  function drawTidal(w, ww, now) {
    if (w <= 0.001) return;
    var e = M.easeOutQuart(w);
    var top = waterTop(Math.max(ww, w));
    var gh = 0.062 * H * e;
    stroke(WHITE, 0.4 * w, 1.5);
    ctx.beginPath();
    ctx.moveTo(0.30 * W, top - gh);
    ctx.lineTo(0.94 * W, top - gh);
    ctx.stroke();
    for (var g = 0; g < 6; g += 1) {
      var x = (0.30 + g * 0.128) * W;
      var gw = 0.085 * W;
      stroke(WHITE, 0.3 * w, 1.5);
      ctx.beginPath();
      ctx.moveTo(x, top - gh);
      ctx.lineTo(x, top + 0.012 * H);
      ctx.stroke();
      var open = 0.4 + 0.6 * (0.5 + 0.5 * Math.sin(now / 2200 + g));
      stroke(GREEN, 0.3 * w, 1.2);
      ctx.beginPath();
      ctx.moveTo(x + 2, top - gh * open);
      ctx.lineTo(x + gw - 2, top - gh * open);
      ctx.stroke();
    }
    for (var b = 0; b < 4; b += 1) {
      var bx = (0.05 + b * 0.055) * W;
      var by = yAt(bx + 0.02 * W);
      var bw = 0.042 * W;
      var bh = 0.042 * H * e;
      stroke(GREEN, 0.45 * w, 1.4);
      ctx.strokeRect(bx, by - bh, bw, bh);
      stroke(WHITE, 0.3 * w, 1.4);
      ctx.beginPath();
      ctx.moveTo(bx + bw * 0.25, by - bh);
      ctx.lineTo(bx + bw * 0.25, by - bh - 4);
      ctx.moveTo(bx + bw * 0.75, by - bh);
      ctx.lineTo(bx + bw * 0.75, by - bh - 4);
      ctx.stroke();
    }
  }

  /* State 5 — a greenway drawing itself in, and a bridge on the horizon. */
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
    /* bridge span */
    var bx = 0.50 * W;
    var bw = 0.24 * W;
    var deck = yAt(bx + bw / 2) - 0.055 * H * e;
    stroke(WHITE, 0.42 * w, 1.5);
    ctx.beginPath();
    ctx.moveTo(bx, deck);
    ctx.lineTo(bx + bw, deck);
    ctx.stroke();
    for (var pr = 0; pr <= 2; pr += 1) {
      var px = bx + (bw / 2) * pr;
      ctx.beginPath();
      ctx.moveTo(px, deck);
      ctx.lineTo(px, yAt(px));
      ctx.stroke();
    }
    stroke(GREEN, 0.3 * w, 1.2);
    ctx.beginPath();
    ctx.moveTo(bx, deck);
    ctx.quadraticCurveTo(bx + bw / 2, deck - 0.035 * H * e, bx + bw, deck);
    ctx.stroke();
  }

  /* State 6 — survey grid, tree line, birds. */
  function drawEcology(w, now) {
    if (w <= 0.001) return;
    var e = M.easeOutQuart(w);
    var i;
    stroke(GREEN, 0.4 * w, 1.3);
    for (i = 0; i < 16; i += 1) {
      var tx = (0.06 + i * 0.024) * W;
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

  /* --------------------------------------------------------- compositor */
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
    drawSolar(w[2]);
    drawIntro(w[0]);
    drawGround();
    drawWind(w[1], now);
    drawEcology(w[6], now);
    drawTransport(w[5]);
    drawWater(ww, now);
    drawTidal(w[4], ww, now);
  }

  /* --------------------------------------------------------- scroll */
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

  /* 30fps cap, only while the stage is on screen and the tab is visible. */
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

  /* Rail steps are real buttons: click or keyboard jumps to that state. */
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
}());
