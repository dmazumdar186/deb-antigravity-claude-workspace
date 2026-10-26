/* Jeevana — one IIFE. Cover "Twelve breaths, drawn then real": 13 scrubbed states (S0 draws itself at load,
   S1–S8 the drawing moves, S9–S11 the drawing takes colour, S12 hold). Drum, deck, i18n, forms, dialog, events.
   One `state` variable drives figure, rail and copy. Figures, pencil layers and contours come from
   assets/fig/manifest.json + contours.json: dropping pencil files in and re-running the ingest needs no HTML edit. */
(function () {
  'use strict';
  /* ---------- named constants (fix brief D17) ---------- */
  var STATES = 13, LAST = 12;                 // S0..S12; S12 holds position 12
  var END_P = 0.92;                           // p at which S12 is reached; held to p = 1
  var HOLD_IN = 0.15, LEG_W = 0.7, CROSS_AT = 0.5; // Evolution scrub: 15 / 70 / 15, swap at 50 % of the leg
  var REVEAL_FROM = 8, REVEAL_TO = 11;        // photograph wipes in across S9–S11
  var CTA_FROM = 9, BEAT2_FROM = 4;           // CTAs from S9, Sūtra 2.46 from S4
  var S0_LINE_MS = 2200, S0_TONE_MS = 1200, S0_LIT_MS = 100; // contour reveal, tone fade, rail 01
  var AUTO_LEG_MS = 2600, AUTO_TO = 3;        // autoplay S1→S3 at breathing pace, then hold
  var COVER_END = 0.8, COVER_OUT = 0.5, MBAR_AT = 0.5; // hint off at p > .8; cover hidden once the drum top < 50 % vh
  var FOLD_OPEN = 0.9, REVEAL_FAILSAFE_MS = 2500, DIALOG_DECK_MS = 1200, DIALOG_TIME_MS = 35000;
  var DESK = { ground: 0.86, height: 0.72, maxW: 0.56 }, PHONE = { ground: 0.78, height: 0.60, min: 0.58, maxW: 0.92 };
  var KEYS = ['sn-01', 'sn-02', 'sn-03', 'sn-04', 'sn-05', 'sn-06', 'photo-05', 'sn-05', 'alt-09', 'sn-03', 'sn-02', 'sn-12'];
  var FIG = 'assets/fig/', FILM_LEG_S = 5;

  var d = document, w = window, root = d.documentElement;
  function $(s, c) { return (c || d).querySelector(s); }
  function $$(s, c) { return Array.prototype.slice.call((c || d).querySelectorAll(s)); }
  function clamp(v, a, b) { return v < a ? a : v > b ? b : v; }
  function mq(q) { return !!(w.matchMedia && w.matchMedia(q).matches); }
  function store(k, v) { try { if (v === undefined) return w.localStorage.getItem(k); w.localStorage.setItem(k, v); } catch (e) { return null; } return null; }
  function getJSON(u) { return fetch(u, { credentials: 'same-origin' }).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; }); }
  function pad(n) { return (n < 10 ? '0' : '') + n; }
  root.classList.add('has-js');
  w.addEventListener('error', function () { root.classList.remove('has-js'); });
  var STATIC = /[?&]static=1/.test(location.search) || mq('(prefers-reduced-motion: reduce)');
  if (STATIC) root.classList.add('is-static');

  /* ---------- events (first-party counts, no PII) ---------- */
  var sent = {};
  function ev(name, once) {
    if (once && sent[name]) return; sent[name] = 1;
    try { var b = new Blob([JSON.stringify({ name: name })], { type: 'application/json' }); if (navigator.sendBeacon) navigator.sendBeacon('/api/event', b); } catch (e) { /* counts are best effort */ }
  }
  d.addEventListener('click', function (e) { var a = e.target && e.target.closest ? e.target.closest('[data-ev]') : null; if (a) ev(a.getAttribute('data-ev')); });

  /* ---------- i18n ---------- */
  var DICT = w.JV_I18N || { en: {}, fr: {} };
  var lang = store('jv-lang') || ((navigator.language || 'en').toLowerCase().indexOf('fr') === 0 ? 'fr' : 'en');
  if (!DICT[lang]) lang = 'en';
  function tr(k) { var t = DICT[lang] || {}; return t[k] !== undefined ? t[k] : (DICT.en[k] !== undefined ? DICT.en[k] : ''); }
  function applyLang(l, save) {
    if (!DICT[l]) return;
    lang = l; root.lang = l;
    if (save) { store('jv-lang', l); if (l === 'fr') ev('lang_fr', true); }
    $$('[data-i18n]').forEach(function (el) { var v = tr(el.getAttribute('data-i18n')); if (v) el.textContent = v; });
    $$('[data-i18n-ph]').forEach(function (el) { el.setAttribute('placeholder', tr(el.getAttribute('data-i18n-ph'))); });
    $$('[data-i18n-aria]').forEach(function (el) { el.setAttribute('aria-label', tr(el.getAttribute('data-i18n-aria'))); });
    $$('[data-i18n-alt]').forEach(function (el) { el.setAttribute('alt', tr(el.getAttribute('data-i18n-alt'))); });
    $$('[data-lang]').forEach(function (b) { b.setAttribute('aria-pressed', String(b.getAttribute('data-lang') === l)); });
    var t = tr(d.body.classList.contains('nf') ? 'nf.h' : 'title'); if (t && !d.body.classList.contains('legal-page')) d.title = d.body.classList.contains('nf') ? t + ' — Jeevana' : t;
    $$('.f__err').forEach(function (el) { el.textContent = tr(el.getAttribute('data-key')); });
    rail(curState, true);
    chapter(true);
  }
  $$('[data-lang]').forEach(function (b) { b.addEventListener('click', function () { applyLang(b.getAttribute('data-lang'), true); }); });

  /* ---------- elements ---------- */
  var hdr = $('[data-hdr]'), cover = $('[data-cover]'), stage = $('[data-stage]'), fold = $('[data-fold]'), spread = $('[data-spread]');
  var slots = $$('[data-fig]'), figs = $('[data-figs]'), sun = $('.cover__sun'), film = $('[data-film]');
  var beats = $$('[data-beat]'), steps = $$('[data-rail-item]'), railEl = $('[data-rail]'), railm = $('[data-railm]');
  var copy = $('[data-copy]'), deck = $('#deck'), mbar = $('[data-mbar]');
  var chNo = $('[data-chapter-no]'), chName = $('[data-chapter-name]');
  function phone() { return w.innerWidth < 800 || w.innerHeight >= w.innerWidth; }
  function mobile() { return w.innerWidth < 800; }

  /* ---------- manifest ---------- */
  var MAN = { fig: {} }, CONT = {};
  function rec(key) { return MAN.fig && MAN.fig[key]; }
  function srcset(list) { return (list || []).map(function (x) { return FIG + x[0] + ' ' + x[1] + 'w'; }).join(', '); }

  /* ---------- figure geometry: feet on the ground line, height share of the stage ---------- */
  function layout(key) {
    var r = rec(key); if (!r || !stage) return null;
    var W = stage.clientWidth, H = stage.clientHeight, ph = phone(), L = ph ? PHONE : DESK;
    var gy = L.ground * H, target = L.height * H;
    if (ph && copy) { // keep the copy block clear of the figure: shrink toward the floor (≥ .58) only if needed
      var bt = $('.beats', copy), cb = bt ? bt.getBoundingClientRect().bottom - stage.getBoundingClientRect().top : 0;
      target = clamp(Math.min(target, gy - cb - 10), L.min * H, L.height * H);
    }
    var a = r.w / r.h, h = target, wd = h * a, maxW = L.maxW * W;
    if (wd > maxW) { wd = maxW; h = wd / a; }
    var top = gy - r.ground * h, left = W / 2 - wd / 2;
    return { x: left, y: top, w: wd, h: h, g: r.ground, gy: gy };
  }
  function place(slot, key) {
    var g = layout(key); if (!g) return;
    slot.style.setProperty('--x', g.x.toFixed(1) + 'px'); slot.style.setProperty('--y', g.y.toFixed(1) + 'px');
    slot.style.setProperty('--w', g.w.toFixed(1) + 'px'); slot.style.setProperty('--h', g.h.toFixed(1) + 'px');
    slot.style.setProperty('--g', String(g.g));
    var sizes = Math.ceil(g.w * Math.max(1, 1.5 / (w.devicePixelRatio || 1))) + 'px'; // ≥ 1.5× the rendered size
    $$('img', slot).forEach(function (im) { if (im.getAttribute('sizes') !== sizes) im.setAttribute('sizes', sizes); });
    slot._g = g;
    if (slot.classList.contains('is-on')) {
      if (sun) { sun.style.setProperty('--sx', (g.x + g.w / 2).toFixed(0) + 'px'); sun.style.setProperty('--sy', (g.y + g.h * 0.3).toFixed(0) + 'px'); sun.style.setProperty('--sr', (Math.max(g.h, g.w) * 0.9).toFixed(0) + 'px'); }
      if (railm) railm.style.setProperty('--ground', String(phone() ? PHONE.ground : DESK.ground));
      if (film) { film.style.setProperty('--x', ((stage.clientWidth - g.h * 0.75) / 2).toFixed(0) + 'px'); film.style.setProperty('--y', (g.gy - g.h).toFixed(0) + 'px'); film.style.setProperty('--w', (g.h * 0.75).toFixed(0) + 'px'); film.style.setProperty('--h', g.h.toFixed(0) + 'px'); }
    }
  }
  function fill(slot, key) {
    var r = rec(key); if (!r) return;
    slot.setAttribute('data-key', key);
    var ph = $('[data-fig-photo]', slot), dr = $('[data-fig-draw]', slot), ln = $('[data-fig-line] path', slot), sv = $('[data-fig-line]', slot);
    var pencil = r.pencil && r.pencil.length;
    slot.classList.toggle('is-pencil', !!pencil);
    place(slot, key);
    if (ph) { ph.setAttribute('srcset', srcset(r.srcset)); ph.setAttribute('src', FIG + r.srcset[r.srcset.length - 1][0]); ph.width = r.w; ph.height = r.h; }
    if (dr) { var list = pencil ? r.pencil : r.srcset; dr.setAttribute('srcset', srcset(list)); dr.setAttribute('src', FIG + list[list.length - 1][0]); }
    var c = CONT[key];
    if (sv && ln && c && c.d) { sv.setAttribute('viewBox', '0 0 ' + c.vb[0] + ' ' + c.vb[1]); ln.setAttribute('d', c.d); }
  }
  function prefetch(key) { var r = rec(key), s = slots[0]; if (!r || !s) return; var im = new Image(); im.sizes = $('img', s).getAttribute('sizes') || '50vw'; im.srcset = srcset(r.srcset); if (r.pencil && r.pencil.length) { var p2 = new Image(); p2.sizes = im.sizes; p2.srcset = srcset(r.pencil); } }

  /* ---------- the one state ---------- */
  var curState = -1, curKey = '', front = 0, autoS = 0, contT = 0;
  function posOf(s) { return Math.min(s, 11) + 1; }
  function setFigure(key) {
    if (!slots.length || key === curKey || !rec(key)) return;
    curKey = key;
    var next = slots[1 - front], prev = slots[front];
    fill(next, key);
    next.classList.remove('is-leaving'); prev.classList.add('is-leaving');
    var go = function () { if (curKey !== key) return; next.classList.add('is-on'); prev.classList.remove('is-on'); front = 1 - front; place(next, key); };
    var im = $('[data-fig-photo]', next);
    if (im && !im.complete) { var done = false, once = function () { if (!done) { done = true; go(); } }; im.addEventListener('load', once, { once: true }); im.addEventListener('error', once, { once: true }); setTimeout(once, 900); } else go();
  }
  function rail(s, force) {
    if (s < 0) return;
    var n = posOf(s);
    if (railEl && (force || railEl.getAttribute('data-pos') !== String(n))) {
      railEl.setAttribute('data-pos', String(n));
      var no = $('[data-rail-no]', railEl); if (no) no.textContent = pad(n);
      $$('[data-rail-key]', railEl).forEach(function (el) { var k = 'sn.' + n + '.' + el.getAttribute('data-rail-key'); el.setAttribute('data-i18n', k); el.textContent = tr(k); });
    }
    if (railm) {
      railm.setAttribute('data-pos', String(n));
      var set = function (sel, k) { var el = $(sel, railm); if (el) el.textContent = k ? tr(k) : ''; };
      var mn = $('[data-railm-no]', railm); if (mn) mn.textContent = pad(n);
      set('[data-railm-iast]', 'sn.' + n + '.iast'); set('[data-railm-breath]', 'sn.' + n + '.breath');
      set('[data-railm-mantra]', 'sn.' + n + '.mantra'); set('[data-railm-tr]', 'sn.' + n + '.tr');
    }
  }
  function setState(s, t) {
    s = clamp(s | 0, 0, LAST);
    var tt = t === undefined ? s : t;
    if (cover) {
      cover.setAttribute('data-state', String(s));
      cover.classList.toggle('is-ctas', s >= CTA_FROM);
      var reveal = clamp((tt - REVEAL_FROM) / (REVEAL_TO - REVEAL_FROM), 0, 1);
      if (s <= REVEAL_FROM) reveal = 0; if (s >= REVEAL_TO) reveal = 1;
      if (stage) stage.style.setProperty('--reveal', reveal.toFixed(3));
    }
    beats.forEach(function (el) { var b = +el.getAttribute('data-beat'); el.classList.toggle('is-on', (s >= BEAT2_FROM ? 1 : 0) === b); });
    steps.forEach(function (li, i) { li.style.setProperty('--fill', clamp(tt - i, 0, 1).toFixed(3)); li.classList.toggle('is-on', i === posOf(s) - 1 && lit); });
    if (s !== curState) {
      curState = s; rail(s);
      setFigure(KEYS[posOf(s) - 1]);
      prefetch(KEYS[Math.min(11, posOf(s))]); prefetch(KEYS[Math.min(11, posOf(s) + 1)]);
      if (s === LAST) ev('cover_complete', true);
    }
  }

  /* ---------- S0: the drawing draws itself, then autoplay S1→S3 ---------- */
  var lit = false, introDone = false, autoOn = !STATIC, timers = [];
  function later(fn, ms) { timers.push(setTimeout(fn, ms)); }
  function finishIntro() {
    if (introDone) return; introDone = true;
    if (stage) { stage.style.setProperty('--draw', '0'); stage.style.setProperty('--tone', '1'); }
    lit = true; if (cover) { cover.classList.remove('is-drawing'); cover.setAttribute('data-intro', 'done'); }
    setState(Math.max(curState, 0), Math.max(curState, 0));
  }
  function stopAuto() { if (!autoOn) return; autoOn = false; timers.forEach(clearTimeout); timers = []; finishIntro(); if (cover) cover.setAttribute('data-autoplay', 'off'); }
  function intro() {
    if (!cover || !stage) return;
    if (STATIC) { lit = true; introDone = true; cover.setAttribute('data-intro', 'done'); setState(11, 11); return; }
    cover.setAttribute('data-intro', 'drawing'); cover.setAttribute('data-autoplay', 'on');
    stage.style.setProperty('--draw', '1'); stage.style.setProperty('--tone', '0');
    setState(0, 0);
    void stage.offsetWidth;
    cover.classList.add('is-drawing');
    w.requestAnimationFrame(function () { w.requestAnimationFrame(function () { stage.style.setProperty('--draw', '0'); }); });
    later(function () { stage.style.setProperty('--tone', '1'); }, S0_LINE_MS);
    later(function () { finishIntro(); }, S0_LINE_MS + S0_TONE_MS + S0_LIT_MS);
    for (var i = 1; i <= AUTO_TO; i++) (function (k) {
      later(function () { if (!autoOn) return; autoS = k; setState(k, k); if (k === AUTO_TO) cover.setAttribute('data-autoplay', 'held'); }, S0_LINE_MS + S0_TONE_MS + S0_LIT_MS + k * AUTO_LEG_MS);
    })(i);
  }

  /* ---------- scrub engine ---------- */
  function overlap() { return fold ? Math.max(0, -parseFloat(getComputedStyle(fold).marginTop) || 0) : 0; }
  function coverP() {
    if (!cover) return 0;
    var r = cover.getBoundingClientRect(), span = cover.offsetHeight - w.innerHeight - overlap();
    return span > 0 ? clamp(-r.top / span, 0, 1) : 1;
  }
  var p = 0, onCover = true, filmOn = false, filmTarget = 0, seeking = false;
  function coverScroll() {
    if (!cover || STATIC) return;
    p = coverP();
    var t = clamp(p / END_P, 0, 1) * LAST, s = Math.floor(Math.min(t, LAST - 0.001)), f = t - s;
    var g = clamp((f - HOLD_IN) / LEG_W, 0, 1), eased = s + g, shown = f < CROSS_AT ? s : Math.min(LAST, s + 1);
    if (t >= LAST) { shown = LAST; eased = LAST; }
    if (w.scrollY > 4 || !autoOn) {
      if (autoS && shown < autoS) { shown = autoS; eased = Math.max(eased, autoS); } else autoS = 0; // scroll takes over from the current state
      setState(shown, eased);
    }
    filmTarget = eased * FILM_LEG_S;
    cover.classList.toggle('is-end', p > COVER_END);
    var fr = fold ? fold.getBoundingClientRect().top : 1e9, ih = w.innerHeight;
    cover.classList.toggle('is-out', fr < ih * COVER_OUT);
    onCover = fr > ih * COVER_OUT;
    if (mbar) mbar.classList.toggle('is-on', fold ? fold.getBoundingClientRect().bottom < ih * MBAR_AT : false);
  }
  function easeQ(x) { return x < 0.5 ? 2 * x * x : 1 - Math.pow(-2 * x + 2, 2) / 2; }
  function foldScroll() {
    if (!fold || !spread) return;
    var r = fold.getBoundingClientRect(), ih = w.innerHeight;
    var span = fold.offsetHeight - ih, pf = span > 0 ? clamp(-r.top / span, 0, 1) : 1;
    var enter = clamp((ih - r.top) / ih, 0, 1);
    var still = STATIC || mobile() || getComputedStyle($('.fold__pin', fold)).position !== 'sticky';
    if (still) pf = 1;
    fold.style.setProperty('--tenter', (still ? 1 : clamp((enter - 0.55) / 0.45, 0, 1)).toFixed(3));
    $$('.plate', spread).forEach(function (pl, i) {
      var rise = still ? 1 : clamp((Math.max(enter - 0.5, 0) * 2 * 0.5 + pf) - i * 0.08, 0, 1);
      rise = still ? 1 : easeQ(clamp(rise, 0, 1));
      pl.style.setProperty('--rise', rise.toFixed(3));
      pl.style.setProperty('--cap', (rise >= 0.3 ? 1 : rise / 0.3).toFixed(3));
    });
    fold.classList.toggle('is-open', pf > FOLD_OPEN);
  }

  /* ---------- Kling film branch (dormant until assets/film/hero.json ready:true) ---------- */
  function filmTick() {
    if (!filmOn || !film || seeking || !film.duration) return;
    var target = Math.min(film.duration - 0.05, filmTarget), delta = target - film.currentTime;
    if (Math.abs(delta) < 1 / 48) return;
    seeking = true; film.currentTime += delta * 0.22;
  }
  if (film && !STATIC) {
    film.addEventListener('seeked', function () { seeking = false; });
    getJSON('assets/film/hero.json').then(function (mf) {
      if (!mf || mf.ready !== true) return;
      var src = 'assets/film/' + (mobile() ? (mf.portrait || mf.landscape) : mf.landscape);
      fetch(src).then(function (r) { return r.blob(); }).then(function (b) { film.src = URL.createObjectURL(b); film.load(); })
        .catch(function () { film.src = src; })
        .then(function () { film.hidden = false; filmOn = true; if (cover) cover.classList.add('has-film'); });
    });
  }

  /* ---------- deck ---------- */
  var tabs = $$('[data-tab]'), panels = $$('.dp'), active = panels[0] ? panels[0].id : '', deckActive = false;
  function countUp(panel) {
    $$('[data-count]', panel).forEach(function (el) {
      var to = parseInt(el.getAttribute('data-count'), 10) || 0;
      if (STATIC) { el.textContent = String(to); return; }
      var t0 = 0;
      function step(tm) { if (!t0) t0 = tm; var x = clamp((tm - t0) / 900, 0, 1), e = 1 - Math.pow(1 - x, 3); el.textContent = String(x >= 1 ? to : Math.round(to * e)); if (x < 1) w.requestAnimationFrame(step); }
      w.requestAnimationFrame(step);
    });
  }
  function show(id, push, focusTab) {
    var pn = $('#' + id); if (!pn || !pn.classList.contains('dp')) return false;
    panels.forEach(function (x) { var on = x === pn; x.hidden = !on && !STATIC; if (on || STATIC) x.removeAttribute('inert'); else x.setAttribute('inert', ''); });
    tabs.forEach(function (t) { var on = t.getAttribute('data-tab') === id; t.setAttribute('aria-selected', String(on)); t.tabIndex = on ? 0 : -1; if (on) { if (focusTab) t.focus(); centreTab(t); } });
    var changed = active !== id; active = id;
    if (push && location.hash !== '#' + id) history.pushState(null, '', '#' + id);
    if (changed) countUp(pn);
    chapter(true); newsArm();
    return true;
  }
  function centreTab(t) { var ul = t.parentNode && t.parentNode.parentNode; if (!ul || !ul.scrollTo) return; ul.scrollTo({ left: t.parentNode.offsetLeft - (ul.clientWidth - t.parentNode.offsetWidth) / 2, behavior: 'auto' }); }
  function fromHash(scroll) {
    var id = (location.hash || '').slice(1), el = id && $('#' + id);
    if (!el || !el.classList.contains('dp')) return;
    show(id, false);
    if (scroll && deck) deck.scrollIntoView({ behavior: STATIC ? 'auto' : 'smooth' });
  }
  tabs.forEach(function (t, k) {
    t.addEventListener('click', function () { show(t.getAttribute('data-tab'), true); });
    t.addEventListener('keydown', function (e) {
      var j = -1;
      if (e.key === 'ArrowRight') j = (k + 1) % tabs.length; else if (e.key === 'ArrowLeft') j = (k - 1 + tabs.length) % tabs.length; else if (e.key === 'Home') j = 0; else if (e.key === 'End') j = tabs.length - 1;
      if (j > -1) { e.preventDefault(); show(tabs[j].getAttribute('data-tab'), true, true); }
    });
  });
  w.addEventListener('popstate', function () { fromHash(false); });
  w.addEventListener('hashchange', function () { fromHash(true); });
  d.addEventListener('click', function (e) {
    var a = e.target && e.target.closest ? e.target.closest('a[href^="#"]') : null; if (!a) return;
    var id = a.getAttribute('href').slice(1), t = id && $('#' + id);
    if (t && t.classList.contains('dp')) { e.preventDefault(); show(id, true); if (deck) deck.scrollIntoView({ behavior: STATIC ? 'auto' : 'smooth' }); }
  });

  /* ---------- header: brand only over the cover; chapter from the drum on ---------- */
  var lastCh = '';
  function chapter(force) {
    if (!hdr) return;
    var no = '', key = '', h = w.innerHeight;
    if (deck && deck.getBoundingClientRect().top < h * 0.5) { var pn = $('#' + active); if (pn) { no = pn.getAttribute('data-chapter'); key = pn.getAttribute('data-name'); } if (!deckActive) ev('deck_open', true); deckActive = true; }
    else if (fold && fold.getBoundingClientRect().top < h * 0.5) { no = '01'; key = 'ch.fold'; }
    hdr.classList.toggle('is-cover', !no);
    var sig = no + key + lang;
    if (sig === lastCh && !force) return; lastCh = sig;
    if (no && chNo) chNo.textContent = no;
    if (key && chName) { chName.setAttribute('data-i18n', key); chName.textContent = tr(key); }
  }

  /* ---------- scroll loop ---------- */
  var ticking = false;
  function frame() { ticking = false; coverScroll(); foldScroll(); chapter(false); newsCheck(); filmTick(); }
  function onScroll() { if (w.scrollY > 4) stopAuto(); if (!ticking) { ticking = true; w.requestAnimationFrame(frame); } }
  w.addEventListener('scroll', onScroll, { passive: true });
  w.addEventListener('resize', function () { slots.forEach(function (s) { var k = s.getAttribute('data-key'); if (k) place(s, k); }); onScroll(); });
  if (film) film.addEventListener('seeked', filmTick);

  /* ---------- dialogs ---------- */
  function modal(dlg, opener) { if (!dlg || dlg.open) return; dlg._ret = opener || d.activeElement; if (dlg.showModal) dlg.showModal(); else dlg.setAttribute('open', ''); }
  function trap(dlg) {
    if (!dlg) return;
    dlg.addEventListener('keydown', function (e) {
      if (e.key !== 'Tab') return;
      var f = $$('a[href],button,input:not([tabindex="-1"]),select,textarea', dlg).filter(function (x) { return !x.disabled && x.offsetParent !== null; });
      if (!f.length) return;
      var first = f[0], last = f[f.length - 1];
      if (e.shiftKey && d.activeElement === first) { e.preventDefault(); last.focus(); } else if (!e.shiftKey && d.activeElement === last) { e.preventDefault(); first.focus(); }
    });
    dlg.addEventListener('close', function () { var r = dlg._ret; if (r && r.focus) { try { r.focus({ preventScroll: true }); } catch (e) { r.focus(); } } });
    dlg.addEventListener('click', function (e) { if (e.target === dlg) dlg.close(); });
  }

  /* ---------- forms: inline errors, mocked-safe posting, fallbacks ---------- */
  var EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  function post(url, data) {
    return fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) })
      .then(function (r) { return r.json().catch(function () { return {}; }).then(function (j) { return { ok: r.ok && j && j.ok !== false, status: r.status }; }); })
      .catch(function () { return { ok: false, status: 0 }; });
  }
  function fieldErr(el, key) {
    var host = el.closest('.f, .check') || el.parentNode, msg = $('.f__err', host);
    if (!key) { el.removeAttribute('aria-invalid'); if (msg) msg.parentNode.removeChild(msg); return; }
    el.setAttribute('aria-invalid', 'true');
    if (!msg) { msg = d.createElement('span'); msg.className = 'f__err'; msg.id = 'e-' + Math.random().toString(36).slice(2, 8); host.appendChild(msg); }
    msg.setAttribute('data-key', key); msg.textContent = tr(key); el.setAttribute('aria-describedby', msg.id);
  }
  function wireForm(form, url, extra, done, okEl) {
    if (!form) return;
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var ok = okEl || $('[data-ok]', form), err = $('[data-err],[data-reg-err]', form);
      var fd = {}; $$('input,select,textarea', form).forEach(function (el) { if (el.name) fd[el.name] = el.type === 'checkbox' ? el.checked : el.value.trim(); });
      var bad = null;
      $$('[required]', form).forEach(function (el) {
        var v = el.type === 'checkbox' ? el.checked : el.value.trim();
        var k = !v ? (el.type === 'checkbox' ? 'err.consent' : 'err.req') : (el.type === 'email' && !EMAIL.test(v) ? 'err.email' : '');
        fieldErr(el, k); if (k && !bad) bad = el;
      });
      if (bad) { bad.focus(); return; }
      fd.lang = lang; fd.source_url = location.pathname; if (extra) extra(fd);
      var btn = $('button[type="submit"]', form); if (btn) btn.disabled = true;
      post(url, fd).then(function (res) {
        if (btn) btn.disabled = res.ok;
        if (ok) ok.hidden = !res.ok; if (err) err.hidden = res.ok;
        var fb = $('[data-fallback]', form); if (fb) fb.hidden = res.ok || !(res.status === 429 || res.status >= 500 || res.status === 0);
        if (!res.ok) { var m = $('[data-reg-mail]', form); if (m) m.setAttribute('href', 'mailto:jeevanagogula.gj22@gmail.com?subject=' + encodeURIComponent(tr('reg.subject')) + '&body=' + encodeURIComponent(tr('mail.body') + '\n' + ['name', 'email', 'phone', 'class', 'level', 'message'].filter(function (k) { return fd[k]; }).map(function (k) { return k + ': ' + fd[k]; }).join('\n'))); }
        if (res.ok) { form.reset(); if (done) done(); }
      });
    });
  }
  var regForm = $('[data-reg]'), regOk = $('[data-reg-ok]');
  if (regForm) regForm.addEventListener('focusin', function () { ev('register_start', true); });
  wireForm(regForm, '/api/register', null, function () {
    ev('register_done'); regForm.hidden = true;
    if (regOk) { regOk.scrollIntoView({ block: 'center', behavior: 'auto' }); try { regOk.focus({ preventScroll: true }); } catch (e) { regOk.focus(); } }
  }, regOk);
  wireForm($('[data-news-inline]'), '/api/subscribe', function (fd) { fd.source = 'footer'; }, function () { ev('newsletter_done'); });
  var news = $('[data-news]'); trap(news);
  wireForm(news && $('form', news), '/api/subscribe', function (fd) { fd.source = 'dialog'; }, function () { ev('newsletter_done'); setTimeout(function () { if (news.open) news.close(); }, 1600); });
  var newsNo = $('[data-news-close]'); if (newsNo && news) newsNo.addEventListener('click', function () { news.close(); });

  /* ---------- newsletter pop-up: once per visitor; 35 s or deck active; never on the cover, never inside a form ---------- */
  var NEWS_KEY = 'jv-news-seen', newsDue = false, newsDone = !news || !!store(NEWS_KEY), deckTimer = 0;
  if (!newsDone) setTimeout(function () { newsDue = true; newsCheck(); }, DIALOG_TIME_MS);
  function inForm() { var a = d.activeElement; return !!(a && a.closest && a.closest('form') && !(news && news.contains(a))); }
  function newsArm() { newsCheck(); }
  d.addEventListener('focusout', function () { setTimeout(newsCheck, 0); });
  function newsCheck() {
    if (newsDone) return;
    if (deckActive && !deckTimer) deckTimer = setTimeout(function () { newsDue = true; newsCheck(); }, DIALOG_DECK_MS);
    if (!newsDue || onCover || inForm() || (active === 'register' && deckActive)) return;
    newsDone = true; store(NEWS_KEY, String(Date.now()));
    ev('newsletter_open'); modal(news);
  }

  /* ---------- contact slots (contact.json): never render a dead link ---------- */
  getJSON('/js/contact.json').then(function (c) {
    c = c || {};
    var map = { tel: c.tel, whatsapp: c.whatsapp, facebook: c.facebook };
    $$('[data-wire]').forEach(function (a) {
      var v = map[a.getAttribute('data-wire')], li = a.closest('[data-wire-item]');
      if (v && /^(tel:\+\d{6,}|https:\/\/)/.test(v)) { a.setAttribute('href', v); a.hidden = false; if (li) li.hidden = false; }
      else { a.removeAttribute('href'); a.hidden = true; if (li) li.hidden = true; }
    });
    if (c.phone) $$('[data-wire-label="phone"]').forEach(function (s) { s.textContent = c.phone; });
  });

  /* ---------- timetable (schedule.json) ---------- */
  if ($('[data-tt]')) getJSON('js/schedule.json').then(function (rows) {
    rows = Array.isArray(rows) ? rows : [];
    var empty = $('[data-tt-empty]'), sel = $('[data-class-select]');
    rows.forEach(function (r) {
      var ul = $('[data-day="' + (r.day | 0) + '"]'); if (!ul || !r.time || !r.title) return;
      var li = d.createElement('li'); li.textContent = r.time + ' · ' + r.title; ul.appendChild(li);
      if (sel) { var o = d.createElement('option'); o.value = String(r.id || (r.day + '-' + r.time)); o.textContent = r.title + ' — ' + r.time; sel.appendChild(o); }
    });
    if (empty) empty.hidden = rows.length > 0;
    var tt = $('[data-tt]'); if (tt) tt.hidden = rows.length === 0;
  });

  /* ---------- boot ---------- */
  applyLang(lang, false);
  if (STATIC) panels.forEach(function (x) { x.hidden = false; x.removeAttribute('inert'); });
  if (cover) {
    Promise.all([getJSON(FIG + 'manifest.json'), getJSON(FIG + 'contours.json')]).then(function (a) {
      if (a[0] && a[0].fig) MAN = a[0];
      CONT = a[1] || {};
      if (w.scrollY > 4) { autoOn = false; finishIntro(); coverScroll(); }
      else intro();
      onScroll();
    });
  }
  fromHash(false);
  frame();
  setTimeout(function () { $$('.reveal').forEach(function (e) { e.classList.add('is-in'); }); }, REVEAL_FAILSAFE_MS);
  void STATES; void contT;
})();
