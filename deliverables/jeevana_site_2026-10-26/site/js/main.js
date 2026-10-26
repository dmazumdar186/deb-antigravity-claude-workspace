/* Jeevana — one IIFE. Cover: 12-frame autoplay, then scroll scrub. Fold: card drum. Deck, i18n, forms, dialogs.
   ?record=1 exposes window.__tick(frame) for scripts/render_hero_video.mjs (backdrop stage only). */
(function () {
  'use strict';
  var d = document, w = window, root = d.documentElement;
  function $(s, c) { return (c || d).querySelector(s); }
  function $$(s, c) { return Array.prototype.slice.call((c || d).querySelectorAll(s)); }
  function clamp(v, a, b) { return v < a ? a : v > b ? b : v; }
  function mq(q) { return !!(w.matchMedia && w.matchMedia(q).matches); }
  function store(k, v) { try { if (v === undefined) return w.localStorage.getItem(k); w.localStorage.setItem(k, v); } catch (e) { return null; } return null; }
  function getJSON(u) { return fetch(u, { credentials: 'same-origin' }).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; }); }
  root.classList.add('has-js');
  w.addEventListener('error', function () { root.classList.remove('has-js'); });
  var REC = /[?&]record=1/.test(location.search);
  var reduced = !REC && mq('(prefers-reduced-motion: reduce)');
  var saveData = !!(navigator.connection && navigator.connection.saveData);
  if (REC) root.classList.add('is-rec');
  var N = 12;

  /* ---------- i18n ---------- */
  var DICT = w.JV_I18N || { en: {}, fr: {} };
  var lang = store('jv-lang') || ((navigator.language || 'en').toLowerCase().indexOf('fr') === 0 ? 'fr' : 'en');
  if (!DICT[lang]) lang = 'en';
  function tr(k) { var t = DICT[lang] || {}; return t[k] !== undefined ? t[k] : (DICT.en[k] !== undefined ? DICT.en[k] : ''); }
  function applyLang(l, save) {
    if (!DICT[l]) return;
    lang = l; root.lang = l;
    if (save) store('jv-lang', l);
    $$('[data-i18n]').forEach(function (el) { var v = tr(el.getAttribute('data-i18n')); if (v) el.textContent = v; });
    $$('[data-i18n-ph]').forEach(function (el) { el.setAttribute('placeholder', tr(el.getAttribute('data-i18n-ph'))); });
    $$('[data-i18n-aria]').forEach(function (el) { el.setAttribute('aria-label', tr(el.getAttribute('data-i18n-aria'))); });
    $$('[data-i18n-alt]').forEach(function (el) { el.setAttribute('alt', tr(el.getAttribute('data-i18n-alt'))); });
    $$('[data-lang]').forEach(function (b) { b.setAttribute('aria-pressed', String(b.getAttribute('data-lang') === l)); });
    var t = tr('title'); if (t) d.title = t;
    var mail = $('[data-reg-mail]'); if (mail) mail.setAttribute('href', 'mailto:jeevanagogula.gj22@gmail.com?subject=' + encodeURIComponent(tr('reg.subject')));
    chapter(true);
  }
  $$('[data-lang]').forEach(function (b) { b.addEventListener('click', function () { applyLang(b.getAttribute('data-lang'), true); }); });

  /* ---------- elements ---------- */
  var hdr = $('[data-hdr]'), cover = $('[data-cover]'), fold = $('[data-fold]'), spread = $('[data-spread]');
  var frameEl = $('[data-frame]'), imgs = $$('[data-img]'), echo = $('[data-echo]'), rail = $('[data-rail]');
  var beats = $$('[data-beat]'), ticks = $$('[data-rail-item]'), railNo = $('[data-rail-no]');
  var deck = $('#deck'), mbar = $('[data-mbar]'), body = $('.cover__body');
  var chNo = $('[data-chapter-no]'), chName = $('[data-chapter-name]');
  var mobile = function () { return w.innerWidth < 800; };

  /* ---------- manifest + frames ---------- */
  var MAN = { frames: {}, photos: [] }, BASE = 'assets/img/';
  function frameRec(i) { // i: 0..11 -> nearest real frame at or before i (never a drawn figure)
    for (var k = i; k >= 0; k--) { var r = MAN.frames['sn-' + (k < 9 ? '0' : '') + (k + 1)]; if (r) return { rec: r, own: k === i }; }
    return null;
  }
  function srcFor(rec) { return BASE + (w.innerWidth < 700 && rec.mfile ? rec.mfile : rec.file); }
  function fit(im, rec) { // per-frame crop: body >= ~60 % of the plate height, anchored to the mat
    if (!im || !rec || !frameEl) return;
    var W = frameEl.clientWidth, H = frameEl.clientHeight; if (!W || !H) return;
    var portrait = mq('(orientation: portrait)'), iw = rec.w, ih = rec.h, s0 = Math.max(W / iw, H / ih);
    var bx = rec.box || [0, 0.2, 1, 0.8], bh = Math.max(0.05, bx[3] - bx[1]) * ih * s0;
    var z = clamp((portrait ? 0.5 : 0.6) * H / bh, 1, 1.5); if (rec.zoom) z = Math.max(z, rec.zoom);
    var S = s0 * z, RW = iw * S, RH = ih * S, cx = (parseFloat(rec.focus) || 50) / 100;
    if (portrait && H < 760) z = Math.min(z, 1.3);
    var y = clamp((portrait ? 0.62 : 0.94) * H - bx[3] * RH, H - RH, 0), x = clamp(W / 2 - cx * RW, W - RW, 0);
    im.style.setProperty('--iw', Math.round(RW) + 'px'); im.style.setProperty('--ih', Math.round(RH) + 'px');
    im.style.setProperty('--ix', Math.round(x) + 'px'); im.style.setProperty('--iy', Math.round(y) + 'px');
    im.style.setProperty('--ox', Math.round((cx * RW / RW) * 100) + '%'); im.style.setProperty('--oy', Math.round(((bx[1] + bx[3]) / 2) * 100) + '%');
    im._rec = rec;
  }
  var cur = -1, curSrc = imgs[0] ? imgs[0].getAttribute('src') : '', front = 0;
  function setFrame(i, force) {
    i = clamp(i | 0, 0, N - 1);
    if (i === cur && !force) return;
    cur = i;
    if (cover) cover.setAttribute('data-frame-index', String(i));
    var fr = frameRec(i);
    if (frameEl && imgs.length === 2 && fr) {
      var src = srcFor(fr.rec);
      frameEl.classList.toggle('is-hold', !fr.own || (autoDone && i === N - 1));
      if (fr.rec.focus) frameEl.style.setProperty('--focus', fr.rec.focus);
      if (src === curSrc && imgs[front] && imgs[front]._rec !== fr.rec) fit(imgs[front], fr.rec);
      if (src !== curSrc) {
        var next = imgs[1 - front], prev = imgs[front];
        curSrc = src;
        var show = function () { if (curSrc !== src) return; next.classList.add('is-on'); prev.classList.remove('is-on'); front = 1 - front; };
        next.setAttribute('alt', tr('alt.sn'));
        next.removeAttribute('srcset'); next.removeAttribute('sizes');
        fit(next, fr.rec);
        next.onload = show; next.src = src;
        if (next.complete && next.naturalWidth) show();
        if (echo) echo.src = BASE + (fr.rec.mfile || fr.rec.file);
      }
    }
    var n = i + 1;
    if (railNo) railNo.textContent = (n < 10 ? '0' : '') + n;
    if (rail) {
      $$('[data-rail-key]', rail).forEach(function (el) { var key = 'sn.' + n + '.' + el.getAttribute('data-rail-key'); el.setAttribute('data-i18n', key); el.textContent = tr(key); });
    }
    ticks.forEach(function (t, k) { t.classList.toggle('is-on', k === i); t.classList.toggle('is-done', k < i); if (k !== i) t.style.setProperty('--p', '0'); });
  }

  /* ---------- autoplay (before any scroll) ---------- */
  var autoplay = !reduced && !REC, autoDone = false, autoTimer = 0, autoI = 0;
  function stopAuto() { if (!autoplay) return; autoplay = false; clearInterval(autoTimer); if (cover) cover.setAttribute('data-autoplay', 'off'); }
  function startAuto() {
    if (!autoplay || !cover) return;
    cover.setAttribute('data-autoplay', 'on');
    autoTimer = setInterval(function () {
      if (!autoplay) return;
      autoI += 1;
      if (autoI >= N - 1) { autoI = N - 1; autoDone = true; clearInterval(autoTimer); cover.setAttribute('data-autoplay', 'held'); }
      setFrame(autoI);
      var t = ticks[autoI]; if (t) t.style.setProperty('--p', '1');
    }, 900);
  }

  /* ---------- scrub engine ---------- */
  function prog(el) { if (!el) return 0; var r = el.getBoundingClientRect(), span = el.offsetHeight - w.innerHeight; return span > 0 ? clamp(-r.top / span, 0, 1) : (r.top <= 0 ? 1 : 0); }
  var coverP = 0, enter = 0, onCover = true, beat0 = true;
  function coverScroll() {
    if (!cover) return;
    coverP = prog(cover);
    var b = Math.min(beats.length - 1, Math.floor(clamp(coverP / 0.6, 0, 0.9999) * beats.length));
    cover.classList.toggle('is-b0', b === 0);
    cover.classList.toggle('is-ctas', b === beats.length - 1);
    cover.classList.toggle('is-end', coverP > 0.8);
    beat0 = b === 0;
    beats.forEach(function (el, k) { el.classList.toggle('is-on', k === b); });
    if (!autoplay || w.scrollY > 4) {
      var f = Math.min(N - 1, Math.floor(coverP * N));
      setFrame(f);
      var t = ticks[f]; if (t) t.style.setProperty('--p', (coverP * N - f).toFixed(3));
    }
    var cb = cover.getBoundingClientRect().bottom, ih = w.innerHeight;
    cover.style.setProperty('--body', clamp((cb / ih - 0.75) / 0.25, 0, 1).toFixed(3));
    onCover = cb > ih * 0.5;
  }
  function easeQ(x) { return x < 0.5 ? 2 * x * x : 1 - Math.pow(-2 * x + 2, 2) / 2; }
  function foldScroll() {
    if (!fold || !cover) return;
    var r = fold.getBoundingClientRect(), ih = w.innerHeight;
    enter = clamp((ih - r.top) / ih, 0, 1);
    fold.style.setProperty('--enter', enter.toFixed(3));
    var pf = mobile() ? 1 : prog(fold);
    if (reduced) pf = 1;
    if (spread) {
      spread.style.setProperty('--fold', (mobile() || reduced ? 1 : easeQ(pf)).toFixed(4));
      $$('.plate', spread).forEach(function (pl, i) { pl.style.setProperty('--rise', (mobile() ? 1 : clamp((pf - i * 0.12) / 0.6, 0, 1)).toFixed(3)); });
    }
    fold.classList.toggle('is-open', pf > 0.9);
    cover.classList.toggle('is-out', r.top < ih * 0.2);
    if (mbar) mbar.classList.toggle('is-on', r.top < ih * 0.5);
  }
  function placeDrum() { // offset of each plate's centre from the spread centre, for the drum phase
    if (!spread) return;
    var sr = spread.getBoundingClientRect(), c = sr.left + sr.width / 2;
    $$('.plate', spread).forEach(function (pl) {
      void c; void pl;
    });
  }

  /* ---------- video / backdrop ---------- */
  var BD = w.JeevanaBackdrop, canvas = $('[data-backdrop]'), vid = $('[data-hero-video]'), bdOn = false;
  if (BD && canvas) { try { BD.init(canvas, { seed: 7, dpr: 1.5, reducedMotion: reduced || REC, autoplay: !REC }); bdOn = true; } catch (e) { bdOn = false; } }
  function syncVideo() {
    if (!cover) return;
    var vis = cover.getBoundingClientRect().bottom > 0 && !d.hidden && !cover.classList.contains('is-out');
    if (bdOn) { try { BD.setProgress(coverP); if (cover.classList.contains('has-video') || !vis) BD.pause(); else BD.resume(); } catch (e) { bdOn = false; } }
    if (vid && cover.classList.contains('has-video')) { if (vis) { if (vid.paused) { var pr = vid.play(); if (pr && pr.catch) pr.catch(function () {}); } } else if (!vid.paused) vid.pause(); }
  }
  if (vid && !REC && !reduced && !saveData && !/[?&]canvas=1/.test(location.search)) {
    getJSON('assets/hero.json').then(function (mf) {
      if (!mf || !mf.ready) return;
      var name = mobile() ? mf.portrait : mf.landscape;
      vid.addEventListener('playing', function () { cover.classList.add('has-video'); syncVideo(); }, { once: true });
      vid.addEventListener('error', function () { cover.classList.remove('has-video'); syncVideo(); }, { once: true });
      if (mf.poster) vid.setAttribute('poster', 'assets/' + mf.poster);
      vid.src = 'assets/' + name;
      var pr = vid.play(); if (pr && pr.catch) pr.catch(function () {});
    });
  }

  /* ---------- deck ---------- */
  var tabs = $$('[data-tab]'), panels = $$('.dp'), active = panels[0] ? panels[0].id : '';
  var deckActive = false;
  function countUp(panel) {
    $$('[data-count]', panel).forEach(function (el) {
      var to = parseInt(el.getAttribute('data-count'), 10) || 0, pre = el.getAttribute('data-prefix') || '', suf = el.getAttribute('data-suffix') || '';
      if (reduced) { el.textContent = pre + to + suf; return; }
      var t0 = 0;
      function step(t) { if (!t0) t0 = t; var x = clamp((t - t0) / 900, 0, 1), e = 1 - Math.pow(1 - x, 3); el.textContent = pre + (x >= 1 ? to : Math.round(to * e)) + suf; if (x < 1) w.requestAnimationFrame(step); }
      w.requestAnimationFrame(step);
    });
  }
  function show(id, push, focusTab) {
    var p = $('#' + id); if (!p || !p.classList.contains('dp')) return false;
    panels.forEach(function (x) { var on = x === p; x.hidden = !on; if (on) x.removeAttribute('inert'); else x.setAttribute('inert', ''); });
    tabs.forEach(function (t) { var on = t.getAttribute('data-tab') === id; t.setAttribute('aria-selected', String(on)); t.tabIndex = on ? 0 : -1; if (on) { if (focusTab) t.focus(); centreTab(t); } });
    var changed = active !== id; active = id;
    if (push && location.hash !== '#' + id) history.pushState(null, '', '#' + id);
    if (changed) countUp(p);
    chapter(true);
    return true;
  }
  function centreTab(t) { var ul = t.parentNode && t.parentNode.parentNode; if (!ul || !ul.scrollTo) return; ul.scrollTo({ left: t.parentNode.offsetLeft - (ul.clientWidth - t.parentNode.offsetWidth) / 2, behavior: 'auto' }); }
  function fromHash(scroll) {
    var id = (location.hash || '').slice(1);
    if (!id || !$('#' + id) || !$('#' + id).classList.contains('dp')) return;
    show(id, false);
    if (scroll && deck) { deck.scrollIntoView({ behavior: reduced ? 'auto' : 'smooth' }); }
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
    if (t && t.classList.contains('dp')) { e.preventDefault(); show(id, true); if (deck) deck.scrollIntoView({ behavior: reduced ? 'auto' : 'smooth' }); }
  });

  /* ---------- header chapter ---------- */
  var lastCh = '';
  function chapter(force) {
    var no = '00', key = 'ch.cover', h = w.innerHeight;
    if (deck && deck.getBoundingClientRect().top < h * 0.5) { var p = $('#' + active); if (p) { no = p.getAttribute('data-chapter'); key = p.getAttribute('data-name'); } deckActive = true; }
    else if (fold && fold.getBoundingClientRect().top < h * 0.5) { no = '01'; key = 'ch.fold'; }
    if (hdr) { hdr.classList.toggle('is-cover', no === '00'); hdr.classList.toggle('is-b0', no === '00' && beat0); }
    var sig = no + key + lang;
    if (sig === lastCh && !force) return; lastCh = sig;
    if (chNo) chNo.textContent = no;
    if (chName) { chName.setAttribute('data-i18n', key); chName.textContent = tr(key); }
  }

  /* ---------- scroll loop ---------- */
  var ticking = false;
  function frame() { ticking = false; coverScroll(); foldScroll(); syncVideo(); chapter(false); newsCheck(); }
  function onScroll() { if (w.scrollY > 4) stopAuto(); if (!ticking) { ticking = true; w.requestAnimationFrame(frame); } }
  w.addEventListener('scroll', onScroll, { passive: true });
  w.addEventListener('resize', function () { imgs.forEach(function (im) { if (im._rec) fit(im, im._rec); }); onScroll(); });
  d.addEventListener('visibilitychange', syncVideo);

  /* ---------- gallery ---------- */
  var gal = $('[data-gallery]'), galGrid = $('[data-gal-grid]');
  function galPhotos() {
    var seen = {}, out = [];
    (MAN.photos || []).forEach(function (p) { if (/^photo-0[24]$/.test(p.name)) { seen[p.src] = 1; out.push(p); } });
    Object.keys(MAN.frames || {}).sort().forEach(function (k) { var f = MAN.frames[k]; if (!seen[f.src]) { seen[f.src] = 1; out.push(f); } });
    return out;
  }
  function buildGallery() {
    if (!galGrid) return;
    while (galGrid.firstChild) galGrid.removeChild(galGrid.firstChild);
    galPhotos().forEach(function (p) { var im = d.createElement('img'); im.src = BASE + (p.mfile || p.file); im.width = p.w; im.height = p.h; im.alt = tr('alt.gal'); im.loading = 'lazy'; im.decoding = 'async'; im.setAttribute('data-i18n-alt', 'alt.gal'); galGrid.appendChild(im); });
  }
  function modal(dlg, opener) {
    if (!dlg || dlg.open) return;
    dlg._ret = opener || d.activeElement;
    if (dlg.showModal) dlg.showModal(); else dlg.setAttribute('open', '');
  }
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
  trap(gal);
  $$('[data-album]').forEach(function (b) { b.addEventListener('click', function () { buildGallery(); modal(gal, b); }); });
  var galClose = $('[data-gal-close]'); if (galClose && gal) galClose.addEventListener('click', function () { gal.close(); });

  /* ---------- forms ---------- */
  var EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  function post(url, data) {
    return fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) })
      .then(function (r) { return r.json().catch(function () { return {}; }).then(function (j) { return r.ok && j && j.ok !== false; }); })
      .catch(function () { return false; });
  }
  function wireForm(form, url, extra, done, okEl) {
    if (!form) return;
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var ok = okEl || $('[data-ok]', form), err = $('[data-err],[data-reg-err]', form);
      var fd = {}; $$('input,select,textarea', form).forEach(function (el) { if (el.name) fd[el.name] = el.type === 'checkbox' ? el.checked : el.value.trim(); });
      var bad = null;
      $$('[required]', form).forEach(function (el) { var v = el.type === 'checkbox' ? el.checked : el.value.trim(); if (!v || (el.type === 'email' && !EMAIL.test(v))) { if (!bad) bad = el; el.setAttribute('aria-invalid', 'true'); } else el.removeAttribute('aria-invalid'); });
      if (bad) { bad.focus(); return; }
      fd.lang = lang; fd.source_url = location.pathname; if (extra) extra(fd);
      var btn = $('button[type="submit"]', form); if (btn) btn.disabled = true;
      post(url, fd).then(function (good) {
        if (btn) btn.disabled = good;
        if (ok) ok.hidden = !good; if (err) err.hidden = good;
        if (good) { form.reset(); if (done) done(); }
      });
    });
  }
  var regForm = $('[data-reg]'), regOk = $('[data-reg-ok]');
  wireForm(regForm, '/api/register', null, function () {
    regForm.hidden = true;
    if (regOk) { regOk.scrollIntoView({ block: 'center', behavior: 'auto' }); try { regOk.focus({ preventScroll: true }); } catch (e) {} }
  }, regOk);
  wireForm($('[data-news-inline]'), '/api/subscribe', function (fd) { fd.source = 'footer'; });
  var news = $('[data-news]'); trap(news);
  wireForm(news && $('form', news), '/api/subscribe', function (fd) { fd.source = 'dialog'; }, function () { setTimeout(function () { if (news.open) news.close(); }, 1600); });
  var newsNo = $('[data-news-close]'); if (newsNo && news) newsNo.addEventListener('click', function () { news.close(); });

  /* ---------- newsletter pop-up: once per visitor, 35 s or deck active, never on the cover ---------- */
  var NEWS_KEY = 'jv-news-seen', newsDue = false, newsDone = !news || !!store(NEWS_KEY) || REC;
  if (!newsDone) setTimeout(function () { newsDue = true; newsCheck(); }, 35000);
  var deckTimer = 0;
  function newsCheck() {
    if (newsDone) return;
    if (deckActive && !deckTimer) deckTimer = setTimeout(function () { newsDue = true; newsCheck(); }, 1200);
    if (!newsDue || onCover || (gal && gal.open)) return;
    newsDone = true; store(NEWS_KEY, String(Date.now()));
    modal(news);
  }

  /* ---------- contact slots (contact.json): never render a dead link ---------- */
  getJSON('js/contact.json').then(function (c) {
    c = c || {};
    var map = { tel: c.tel, whatsapp: c.whatsapp, facebook: c.facebook };
    $$('[data-wire]').forEach(function (a) {
      var v = map[a.getAttribute('data-wire')];
      var li = a.closest('[data-wire-item]');
      if (v && /^(tel:\+\d{6,}|https:\/\/)/.test(v)) { a.setAttribute('href', v); a.hidden = false; if (li) li.hidden = false; }
      else { a.removeAttribute('href'); a.hidden = true; if (li) li.hidden = true; }
    });
    if (c.phone) $$('[data-wire-label="phone"]').forEach(function (s) { s.textContent = c.phone; });
  });

  /* ---------- timetable (schedule.json) ---------- */
  getJSON('js/schedule.json').then(function (rows) {
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

  /* ---------- record mode (hero footage) ---------- */
  if (REC) {
    var FPS = 30, SEC = 11;
    w.__tick = function (f) { var t = f / FPS * 1000, p = clamp((f % (FPS * SEC)) / (FPS * SEC), 0, 1); if (bdOn) { BD.setProgress(p); BD.render(t); } return p; };
    w.__tick(0);
  }

  /* ---------- boot ---------- */
  applyLang(lang, false);
  getJSON(BASE + 'manifest.json').then(function (m) {
    if (m && m.frames) MAN = m;
    var r1 = MAN.frames['sn-01']; if (r1 && frameEl) { frameEl.style.setProperty('--ar', r1.w + ' / ' + r1.h); }
    $$('[data-photo]').forEach(function (im) { var n = im.getAttribute('data-photo'); (MAN.photos || []).forEach(function (p) { if (p.name === n && p.focus) im.style.setProperty('object-position', p.focus); }); });
    // warm the cache for the next frames
    Object.keys(MAN.frames).forEach(function (k) { var im = new Image(); im.decoding = 'async'; im.src = srcFor(MAN.frames[k]); });
    setFrame(cur < 0 ? 0 : cur, true);
    if (w.scrollY <= 4) startAuto();
  });
  placeDrum();
  fromHash(false);
  frame();
  setTimeout(function () { $$('.reveal').forEach(function (e) { e.classList.add('is-in'); }); }, 2500);
})();
