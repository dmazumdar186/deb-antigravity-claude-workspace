/* Jeevana v3 — one IIFE. The cover film is scrubbed by one variable, `pos` (state units 0..11): film time, rail and copy
   all derive from it. Before any scroll the film plays itself through the first two legs, then holds; the first scroll
   takes over from the held time (pos stays at the held state until scroll catches up, then tracks p). */
(function () {
  'use strict';
  var doc = document, root = doc.documentElement, W = window;
  // ---- named constants ----
  var STATES = 12;              // keyframes / positions
  var LAST = STATES - 1;        // S11, held to p = 1
  var UNITS = 12;               // p * UNITS = pos; pos clamps at LAST, so the 13th unit is the hold
  var HOLD_IN = 0.15, LEG_SPAN = 0.70; // 15 / 70 / 15 hold-leg-hold window per unit
  var TEXT_SWITCH = 0.5;        // copy/rail crossfade at 50 % of a leg
  var LERP = 0.22;              // currentTime easing per frame
  var SEEK_EPS = 1 / 48;        // ~1 frame tolerance
  var AUTOPLAY_LEGS = 2;        // the film plays itself through the first two legs
  var AUTOPLAY_DELAY = 400;     // ms after canplay before autoplay starts
  var BREATH_MS = 5500;         // shared breath clock (js/breath.js uses the same period)
  var COVER_DONE = 0.98;        // p at which cover_complete fires and the mobile bar shows
  var DIALOG_DELAY = 1200;      // ms after chapter 01 is reached
  var PHONE_MAX = 799;          // px; phones get the 9:16 film and the 10 x 100svh track
  var COPY_STATES = [0, 4, 11]; // copy state shown from this pos index onwards
  var LS_LANG = 'jv-lang', LS_NEWS = 'jv-news-seen';

  root.classList.add('has-js');
  var $ = function (s, c) { return (c || doc).querySelector(s); };
  var $$ = function (s, c) { return Array.prototype.slice.call((c || doc).querySelectorAll(s)); };
  var clamp = function (v, a, b) { return Math.min(b, Math.max(a, v)); };
  var store = { get: function (k) { try { return W.localStorage.getItem(k); } catch (e) { return null; } }, set: function (k, v) { try { W.localStorage.setItem(k, v); } catch (e) { /* private mode */ } } };
  var params = new URLSearchParams(W.location.search);
  var reduce = W.matchMedia && W.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var saveData = !!(navigator.connection && navigator.connection.saveData);
  var staticMode = reduce || saveData || params.get('static') === '1';
  W.addEventListener('error', function () { root.classList.remove('has-js'); root.classList.add('is-static'); var f = $('[data-film]'); if (f) f.classList.remove('is-live'); });

  // ---- events (counts only) ----
  var sent = {};
  function ev(name, once) {
    if (once && sent[name]) return; sent[name] = 1;
    try { var b = new Blob([JSON.stringify({ name: name })], { type: 'application/json' }); if (navigator.sendBeacon) navigator.sendBeacon('/api/event', b); } catch (e) { /* ignore */ }
  }
  $$('[data-ev]').forEach(function (a) { a.addEventListener('click', function () { ev(a.getAttribute('data-ev')); }); });

  // ---- i18n ----
  var I = W.JV_I18N || { en: {}, fr: {} };
  var lang = store.get(LS_LANG) === 'fr' ? 'fr' : 'en';
  function tr(k) { return (I[lang] && I[lang][k]) || (I.en && I.en[k]) || ''; }
  function applyLang(l, user) {
    lang = l === 'fr' ? 'fr' : 'en'; root.lang = lang; store.set(LS_LANG, lang);
    $$('[data-i18n]').forEach(function (el) { var v = tr(el.getAttribute('data-i18n')); if (v) el.textContent = v; });
    $$('[data-i18n-aria]').forEach(function (el) { var v = tr(el.getAttribute('data-i18n-aria')); if (v) el.setAttribute('aria-label', v); });
    $$('[data-i18n-alt]').forEach(function (el) { var v = tr(el.getAttribute('data-i18n-alt')); if (v) el.setAttribute('alt', v); });
    $$('[data-lang]').forEach(function (b) { b.setAttribute('aria-pressed', String(b.getAttribute('data-lang') === lang)); });
    if (tr('title') && $('[data-cover]')) doc.title = tr('title');
    if (user && lang === 'fr') ev('lang_fr', true);
    railText(); if (cover) measureCopy();
  }
  $$('[data-lang]').forEach(function (b) { b.addEventListener('click', function () { applyLang(b.getAttribute('data-lang'), true); }); });

  // ---- cover ----
  var cover = $('[data-cover]'), stage = $('[data-stage]'), film = $('[data-film]'), video = $('[data-film-video]');
  var copyStates = $$('[data-copy-state]'), items = $$('.rail__item'), hdr = $('[data-hdr]'), mbar = $('[data-mbar]');
  var railCount = $('[data-rail-count]'), railName = $('[data-rail-name]'), railBreath = $('[data-rail-breath]'), breathLive = $('[data-breath-live]');
  var K = [], meta = null, pos = 0, shown = -1, target = 0, seeking = false, autoplaying = false, held = -1, scrolled = false;
  var engine = { p: 0, pos: 0, state: 0, copy: 0, target: 0, ready: false, mode: 'idle', K: K };
  W.__jv = engine; // read-only probe for research/functional.mjs (no behaviour depends on it)

  function keyframes(m) { // 12 keyframe times; a short stand-in film (fewer keyframes) is scaled to 12 evenly
    var ks = (m && m.keyframes_s) || [], sec = (m && m.seconds) || 0, out = [];
    if (ks.length >= STATES) return ks.slice(0, STATES);
    for (var i = 0; i < STATES; i++) out.push(sec * i / LAST);
    return out;
  }
  function posToTime(x) { // x: 0..LAST continuous; within unit s: hold 15 %, leg 70 %, hold 15 %
    if (!K.length) return 0; x = clamp(x, 0, LAST); var s = Math.min(Math.floor(x), LAST - 1), f = x - s;
    var g = clamp((f - HOLD_IN) / LEG_SPAN, 0, 1); return K[s] + g * (K[s + 1] - K[s]);
  }
  function timeToPos(t) {
    if (!K.length) return 0; for (var s = 0; s < LAST; s++) { if (t <= K[s + 1]) { var d = K[s + 1] - K[s]; var g = d > 0 ? clamp((t - K[s]) / d, 0, 1) : 1; return s + (g >= 1 ? 1 : HOLD_IN + g * LEG_SPAN); } }
    return LAST;
  }
  function autoplayEnd() { // end of leg 2 on the 12-keyframe film; on a one-leg stand-in, the stand-in's own two-leg span
    if (!meta) return 0; var ks = meta.keyframes_s || [];
    if (ks.length >= STATES) return ks[AUTOPLAY_LEGS];
    return Math.min(meta.seconds, AUTOPLAY_LEGS * (meta.leg_seconds || meta.seconds));
  }
  function progress() { if (!cover) return 0; var r = cover.getBoundingClientRect(), vh = W.innerHeight; return clamp(-r.top / Math.max(1, r.height - vh), 0, 1); }
  function stateOf(x) { var s = Math.floor(x), f = x - s; return clamp(f >= TEXT_SWITCH ? s + 1 : s, 0, LAST); }
  function copyOf(st) { var c = COPY_STATES[0]; COPY_STATES.forEach(function (v) { if (st >= v) c = v; }); return c; }
  function railText() {
    if (shown < 0) return; var it = items[shown]; if (!it) return;
    if (railCount) railCount.textContent = ('0' + (shown + 1)).slice(-2) + ' / 12';
    var iast = $('.rail__iast', it), br = $('.rail__breath', it);
    if (railName && iast) railName.textContent = iast.textContent;
    if (railBreath && br) railBreath.textContent = br.textContent;
  }
  function show(st, x) {
    items.forEach(function (el, i) {
      el.classList.toggle('is-on', i === st); el.classList.toggle('is-done', i < Math.floor(x));
      var bar = $('.rail__bar', el); if (bar) bar.style.setProperty('--fill', i === Math.floor(x) ? clamp(x - i, 0, 1).toFixed(3) : '0');
    });
    if (st === shown) return; shown = st; railText();
    var c = copyOf(st); engine.copy = c;
    copyStates.forEach(function (el) { el.classList.toggle('is-on', Number(el.getAttribute('data-copy-state')) === c); });
  }
  function setPos(x) { pos = clamp(x, 0, LAST); engine.pos = pos; var st = stateOf(pos); engine.state = st; show(st, pos); }
  function measureCopy() { // phones: the film starts below the tallest copy state (CSS reads --copy-h)
    if (!stage) return; var h = 0; copyStates.forEach(function (el) { h = Math.max(h, el.offsetHeight); });
    var c = $('[data-copy]'); var top = c ? c.offsetTop : 0; stage.style.setProperty('--copy-h', Math.ceil(h + top) + 'px');
  }

  var raf = 0;
  function seekTick() {
    if (raf) return;
    raf = W.requestAnimationFrame(function () {
      raf = 0; if (!video || video.readyState < 2 || autoplaying) return;
      var d = target - video.currentTime; if (Math.abs(d) < SEEK_EPS) return;
      if (!seeking) { seeking = true; video.currentTime = Math.abs(d) < 0.05 ? target : video.currentTime + d * LERP; }
      seekTick();
    });
  }
  function frame() {
    var p = progress(); engine.p = p;
    if (cover) cover.classList.toggle('is-moved', p > 0.002);
    if (hdr) hdr.classList.toggle('is-solid', !cover || cover.getBoundingClientRect().bottom < W.innerHeight * 0.5);
    if (mbar) mbar.classList.toggle('is-shown', p >= COVER_DONE || (cover && cover.getBoundingClientRect().bottom < W.innerHeight));
    if (p >= COVER_DONE) ev('cover_complete', true);
    if (W.JeevanaBackdrop && !staticMode) W.JeevanaBackdrop.setProgress(p);
    if (!engine.ready || staticMode) return;
    if (p > 0 && autoplaying) stopAutoplay();
    if (p > 0) scrolled = true;
    if (!scrolled) return; // untouched: autoplay / hold drives pos
    var x = Math.min(LAST, p * UNITS);
    if (held >= 0) { if (x >= held) held = -1; else x = held; } // hold until scroll catches up with the autoplayed state
    setPos(x); target = held >= 0 ? posToTime(held) : posToTime(x); engine.target = target; engine.mode = held >= 0 ? 'hold' : 'scroll'; seekTick();
  }
  var sched = false;
  function schedule() { if (sched) return; sched = true; W.requestAnimationFrame(function () { sched = false; frame(); }); }

  function stopAutoplay() {
    autoplaying = false; if (video && !video.paused) video.pause();
    held = video ? timeToPos(video.currentTime) : -1; target = video ? video.currentTime : 0;
  }
  function startAutoplay() {
    if (!video || scrolled || progress() > 0) return;
    var end = autoplayEnd(); autoplaying = true; engine.mode = 'autoplay';
    var step = function () {
      if (!autoplaying) return;
      var t = video.currentTime; setPos(timeToPos(t));
      if (t >= end - 0.02 || video.ended) { video.pause(); autoplaying = false; held = timeToPos(Math.min(t, end)); setPos(held); target = video.currentTime; engine.mode = 'held'; return; }
      W.requestAnimationFrame(step);
    };
    video.playbackRate = 1; var pr = video.play(); if (pr && pr.catch) pr.catch(function () { autoplaying = false; });
    W.requestAnimationFrame(step);
  }
  function loadFilm() {
    if (!video || !film) return;
    var url = video.getAttribute('data-src');
    fetch(url, { cache: 'no-cache' }).then(function (r) { if (!r.ok) throw new Error('hero.json ' + r.status); return r.json(); }).then(function (m) {
      if (!m || !m.ready) return; meta = m; K = keyframes(m); engine.K = K; engine.meta = m;
      var phone = W.innerWidth <= PHONE_MAX, file = phone ? m.portrait : m.landscape, v = m.v && m.v[phone ? 'portrait' : 'landscape'];
      var src = '/assets/film/' + file + (v ? '?v=' + v : ''); engine.src = src;
      return fetch(src).then(function (r) { if (!r.ok) throw new Error('film ' + r.status); return r.blob(); })
        .then(function (b) { video.src = URL.createObjectURL(b); }, function () { video.src = src; })
        .then(function () {
          video.addEventListener('seeked', function () { seeking = false; });
          video.addEventListener('loadeddata', function () {
            film.classList.add('is-live'); engine.ready = true;
            if (progress() > 0) { scrolled = true; frame(); } else { setPos(0); W.setTimeout(startAutoplay, AUTOPLAY_DELAY); }
          }, { once: true });
          video.load();
        });
    }).catch(function () { /* poster stays */ });
  }

  // ---- breath clock (shared with js/breath.js) ----
  function breathAt(t) { return W.JeevanaBackdrop && W.JeevanaBackdrop.breath ? W.JeevanaBackdrop.breath(t) : (1 - Math.cos(2 * Math.PI * t / BREATH_MS)) / 2; }
  var lastLabel = '', breathOn = false;
  function breathLoop(t) {
    breathOn = true;
    var b = breathAt(t); root.style.setProperty('--b', b.toFixed(3));
    var inh = (t % BREATH_MS) < BREATH_MS / 2, lbl = tr(inh ? 'breath.in' : 'breath.ex');
    if (breathLive && lbl !== lastLabel) { breathLive.textContent = lbl; breathLive.setAttribute('data-phase', inh ? 'in' : 'ex'); lastLabel = lbl; }
    if (!doc.hidden) W.requestAnimationFrame(breathLoop); else breathOn = false;
  }

  // ---- chapters (desktop crossfade; phones are stacked and always painted) ----
  var chapters = $$('[data-chapter]'), reached1 = false;
  function chapterTick() {
    var mid = W.innerHeight * 0.5, on = -1;
    chapters.forEach(function (c, i) { var r = c.getBoundingClientRect(); if (r.top <= mid && r.bottom > mid) on = i; });
    chapters.forEach(function (c, i) { c.classList.toggle('is-on', i === on || staticMode); });
    if (on >= 0 && !reached1) { reached1 = true; armDialog(); }
  }

  // ---- newsletter dialog ----
  var dlg = $('[data-news]'), dlgTimer = 0, lastFocus = null;
  function inForm() { var a = doc.activeElement; return !!(a && a.closest && a.closest('form') && !(dlg && dlg.contains(a))); }
  function armDialog() {
    if (!dlg || store.get(LS_NEWS) || dlg.open) return;
    W.clearTimeout(dlgTimer);
    dlgTimer = W.setTimeout(function () { if (inForm()) return; openDialog(); }, DIALOG_DELAY);
  }
  doc.addEventListener('focusout', function () { W.setTimeout(function () { if (reached1 && !inForm() && !sent.newsletter_open) armDialog(); }, 0); });
  doc.addEventListener('focusin', function () { if (inForm()) W.clearTimeout(dlgTimer); });
  function openDialog(manual) {
    if (!dlg || dlg.open || typeof dlg.showModal !== 'function') return;
    lastFocus = doc.activeElement; store.set(LS_NEWS, '1'); dlg.showModal(); ev('newsletter_open', !manual);
    var f = $('input[name="email"]', dlg); if (f) f.focus();
  }
  function closeDialog() { if (dlg && dlg.open) dlg.close(); }
  if (dlg) {
    dlg.addEventListener('close', function () { if (lastFocus && lastFocus.focus) lastFocus.focus(); });
    $$('[data-news-close]', dlg).forEach(function (b) { b.addEventListener('click', closeDialog); });
    dlg.addEventListener('keydown', function (e) {
      if (e.key !== 'Tab') return; var f = $$('input:not([tabindex="-1"]),button,a[href],select,textarea', dlg).filter(function (x) { return x.offsetParent !== null; });
      if (!f.length) return; var a = f[0], z = f[f.length - 1];
      if (e.shiftKey && doc.activeElement === a) { e.preventDefault(); z.focus(); } else if (!e.shiftKey && doc.activeElement === z) { e.preventDefault(); a.focus(); }
    });
  }
  $$('[data-news-open]').forEach(function (b) { b.addEventListener('click', function () { openDialog(true); }); });

  // ---- forms ----
  var EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/, PHONE = /^[+()\d\s.-]{6,24}$/;
  function setErr(form, name, key) {
    var e = $('[data-err="' + name + '"]', form), i = $('[name="' + name + '"]', form);
    if (e) e.textContent = key ? tr(key) : ''; if (i) { if (key) i.setAttribute('aria-invalid', 'true'); else i.removeAttribute('aria-invalid'); }
    return !key;
  }
  function wire(form, url, kind) {
    if (!form) return; var started = false;
    form.addEventListener('input', function () { if (!started && kind === 'reg') { started = true; ev('register_start', true); } });
    form.addEventListener('submit', function (e) {
      e.preventDefault(); var fd = new FormData(form), d = {}; fd.forEach(function (v, k) { d[k] = String(v).trim(); });
      var ok = true;
      if (kind === 'reg') ok = setErr(form, 'name', d.name ? '' : 'err.req') && ok;
      ok = setErr(form, 'email', !d.email ? 'err.req' : (EMAIL.test(d.email) ? '' : 'err.email')) && ok;
      ok = setErr(form, 'phone', d.phone && !PHONE.test(d.phone) ? 'err.phone' : '') && ok;
      ok = setErr(form, 'consent', $('[name="consent"]', form).checked ? '' : 'err.consent') && ok;
      if (!ok) { var bad = $('[aria-invalid="true"]', form); if (bad) bad.focus(); return; }
      d.consent = true; d.lang = lang; d.source_url = W.location.href.slice(0, 300); if (kind === 'news') d.source = 'dialog';
      var btn = $('button[type="submit"]', form); if (btn) btn.disabled = true;
      fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(d) })
        .then(function (r) { return r.json().catch(function () { return {}; }).then(function (j) { if (!r.ok || !j.ok) throw r.status; }); })
        .then(function () {
          var okEl = form.parentNode.querySelector('[data-ok]'); form.hidden = true; if (okEl) { okEl.hidden = false; var fx = okEl.matches('[tabindex]') ? okEl : $('[tabindex]', okEl); if (fx) fx.focus(); }
          ev(kind === 'reg' ? 'register_done' : 'newsletter_done');
        })
        .catch(function () {
          var fail = $('[data-fail]', form); if (fail) fail.hidden = false; if (btn) btn.disabled = false;
          var m = $('[data-mailto]', form);
          if (m) { var body = tr('mail.body') + '\n\n' + ['name', 'email', 'phone', 'class', 'level', 'message'].map(function (k) { return k + ': ' + (d[k] || '-'); }).join('\n');
            m.href = 'mailto:Jeevana.yogawellness@gmail.com?subject=' + encodeURIComponent(tr('reg.subject')) + '&body=' + encodeURIComponent(body); }
        });
    });
  }
  wire($('[data-reg]'), '/api/register', 'reg'); wire($('[data-sub]'), '/api/subscribe', 'news');
  $$('a[href="#register"]').forEach(function (a) { a.addEventListener('click', function () { W.setTimeout(function () { var n = $('[data-reg] [name="name"]'); if (n && W.innerWidth > PHONE_MAX) n.focus({ preventScroll: true }); }, 700); }); });

  // ---- timetable + contact slots ----
  var ttRows = $('[data-tt-rows]'), ttEmpty = $('[data-tt-empty]');
  if (ttRows) fetch('/js/schedule.json').then(function (r) { return r.ok ? r.json() : []; }).then(function (rows) {
    if (!Array.isArray(rows) || !rows.length) return; ttRows.textContent = '';
    rows.forEach(function (r) { var li = doc.createElement('li'); [tr('day.' + r.day), r.time, r.title].forEach(function (v) { var s = doc.createElement('span'); s.textContent = v || ''; li.appendChild(s); }); ttRows.appendChild(li); });
    ttRows.hidden = false; if (ttEmpty) ttEmpty.hidden = true;
  }).catch(function () { /* keeps the empty line */ });
  var fb = $('[data-fb]');
  if (fb) fetch('/js/contact.json').then(function (r) { return r.ok ? r.json() : {}; }).then(function (c) { if (c && c.facebook) { $('[data-fb-link]', fb).href = c.facebook; fb.hidden = false; } }).catch(function () { /* hidden */ });

  // ---- boot ----
  applyLang(lang, false);
  if (cover) {
    if (staticMode) { root.classList.add('is-static'); setPos(0); copyStates.forEach(function (el) { el.classList.remove('is-on'); }); }
    else {
      setPos(0); loadFilm();
      var cv = $('[data-breath]');
      if (cv && W.JeevanaBackdrop) W.JeevanaBackdrop.init(cv, { seed: 12, dpr: 1.5, reducedMotion: false, autoplay: true });
    }
    measureCopy();
    if (doc.fonts && doc.fonts.ready) doc.fonts.ready.then(measureCopy);
    W.addEventListener('resize', function () { measureCopy(); schedule(); });
    W.addEventListener('scroll', function () { schedule(); chapterTick(); }, { passive: true });
    frame(); chapterTick();
  }
  if (!staticMode) W.requestAnimationFrame(breathLoop);
  else { root.style.setProperty('--b', '0.5'); if (breathLive) breathLive.textContent = tr('breath.in'); }
  doc.addEventListener('visibilitychange', function () { if (!doc.hidden && !staticMode && !breathOn) W.requestAnimationFrame(breathLoop); });
}());
