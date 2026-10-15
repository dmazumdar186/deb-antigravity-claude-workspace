/* MISB v3 — one IIFE. Cover scrub + backdrop/video, fold-out scrub, deck tabs with hash routing,
   gallery dialog, testimonial stack, counters, reveals, header chapter indicator, mobile bar.
   ?record=1 + window.__tick(frame) => deterministic cover frames for research/render_hero_video.mjs (Kling-ready slot). */
(function () {
  'use strict';
  var root = document.documentElement, $ = function (s, c) { return (c || document).querySelector(s); }, $$ = function (s, c) { return Array.prototype.slice.call((c || document).querySelectorAll(s)); };
  var mq = function (q) { return !!(window.matchMedia && window.matchMedia(q).matches); };
  var REC = /[?&]record=1/.test(location.search), reduced = !REC && mq('(prefers-reduced-motion: reduce)');
  var clamp = function (v, a, b) { return v < a ? a : v > b ? b : v; };
  root.classList.add('has-js'); if (REC) root.classList.add('rec');
  window.addEventListener('error', function () { root.classList.remove('has-js'); });

  /* ---------- reveals: additive on desktop, painted on phones ---------- */
  var reveals = $$('.reveal');
  if (reveals.length && 'IntersectionObserver' in window && window.innerWidth >= 800 && !reduced) {
    var io = new IntersectionObserver(function (es) { es.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add('is-in'); io.unobserve(e.target); } }); }, { threshold: 0.01, rootMargin: '0px 0px 8% 0px' });
    reveals.forEach(function (el) { io.observe(el); });
    setTimeout(function () { reveals.forEach(function (el) { el.classList.add('is-in'); }); }, 2500);
  } else reveals.forEach(function (el) { el.classList.add('is-in'); });

  /* ---------- header: chapter indicator + over-cover tint ---------- */
  var hdr = $('[data-hdr]'), chNo = $('[data-chapter-no]'), chName = $('[data-chapter-name]'), rule = $('.hdr__rule');
  var chapters = $$('[data-chapter]').filter(function (el) { return !el.classList.contains('dp'); });
  function setChapter(no, name) { if (chNo) chNo.textContent = no; if (chName) chName.textContent = name; if (rule) rule.style.setProperty('--prog', (parseInt(no, 10) / 8).toFixed(2)); }

  /* ---------- cover ---------- */
  var mbar = $('[data-mbar]'), fold = $('[data-fold]'), spread = $('[data-spread]');
  var cover = $('[data-cover]'), pin = $('[data-cover-pin]'), beats = $$('[data-beat]'), railItems = $$('[data-rail-item]'), canvas = $('[data-backdrop]'), vid = $('[data-hero-video]');
  var coverP = 0, lastBeat = -1, moveTimer = 0, backdropOn = false;
  function setBeat(n) {
    if (n === lastBeat) return; lastBeat = n;
    beats.forEach(function (b, k) { b.classList.toggle('is-on', k === n); });
    railItems.forEach(function (r, k) { r.classList.toggle('is-on', k === n); r.classList.toggle('is-done', k < n); });
  }
  function applyCover(p) {
    coverP = p; var n = Math.min(3, Math.floor(p * 4)); setBeat(n);
    var seg = p * 4 - n; if (railItems[n]) railItems[n].style.setProperty('--p', seg.toFixed(3));
    if (cover) cover.dataset.cur = n;
    if (backdropOn && window.MISBBackdrop) window.MISBBackdrop.setProgress(p);
  }
  function coverScroll() {
    if (!cover) return;
    var r = cover.getBoundingClientRect(), track = cover.offsetHeight - window.innerHeight; if (track <= 0) return;
    applyCover(clamp(-r.top / track, 0, 1));
    if (hdr) { var out = parseFloat(cover.style.getPropertyValue('--out') || '0'); hdr.classList.toggle('over', r.bottom > 64 && out < 1); }
    cover.classList.add('is-moving'); clearTimeout(moveTimer); moveTimer = setTimeout(function () { cover.classList.remove('is-moving'); }, 900);
    if (r.bottom > window.innerHeight * 0.5) setChapter('00', 'Cover');
  }
  if (canvas && window.MISBBackdrop && !reduced) {
    try { window.MISBBackdrop.init(canvas, { seed: 20261015, dpr: window.innerWidth < 800 ? 1.25 : 1.5, reducedMotion: false, autoplay: !REC }); backdropOn = true; } catch (err) { backdropOn = false; }
  } else if (canvas && window.MISBBackdrop && reduced) {
    try { window.MISBBackdrop.init(canvas, { seed: 20261015, dpr: 1, reducedMotion: true }); backdropOn = true; } catch (err) { backdropOn = false; }
  }
  // pause the canvas when the cover is offscreen or the tab is hidden
  if (cover && backdropOn && 'IntersectionObserver' in window) {
    new IntersectionObserver(function (es) { if (!window.MISBBackdrop) return; if (es[0].isIntersecting) window.MISBBackdrop.resume(); else window.MISBBackdrop.pause(); }, { threshold: 0 }).observe(cover);
  }
  // footage: assets/hero.json ready:true => play the self-rendered journey (hero.mp4 / hero-m.mp4); canvas is the fallback.
  // Replace the mp4s with Kling / Higgsfield footage of the same length and nothing else changes. ?canvas=1 forces the canvas (QA).
  function syncVideo() { if (!vid || !cover.classList.contains('has-video')) return; var r = cover.getBoundingClientRect(); var on = r.bottom > 0 && !document.hidden; if (on) { if (vid.paused) vid.play().catch(function () {}); } else if (!vid.paused) vid.pause(); }
  if (vid && cover && !REC && !/[?&]canvas=1/.test(location.search) && window.fetch && /^https?:/.test(location.protocol)) {
    var con = navigator.connection, saveData = !!(con && con.saveData);
    fetch('assets/hero.json').then(function (r) { return r.ok ? r.json() : null; }).then(function (mf) {
      if (!mf || !mf.ready || reduced || saveData) return;
      var f = (window.innerWidth < 800 && mf.portrait) || mf.landscape || 'hero.mp4';
      if (mf.poster) vid.poster = 'assets/' + mf.poster;
      vid.addEventListener('playing', function () { cover.classList.add('has-video'); if (window.MISBBackdrop && backdropOn) window.MISBBackdrop.pause(); }, { once: true });
      vid.addEventListener('error', function () { cover.classList.remove('has-video'); if (window.MISBBackdrop && backdropOn) window.MISBBackdrop.resume(); }, { once: true });
      vid.innerHTML = '<source src="assets/' + f + '" type="video/mp4"><source src="assets/' + f.replace(/\.mp4$/, '.webm') + '" type="video/webm">';
      vid.load(); var pl = vid.play(); if (pl && pl.catch) pl.catch(function () {});
    }).catch(function () {});
    document.addEventListener('visibilitychange', syncVideo);
  }

  /* ---------- fold-out ---------- */
  function foldScroll() {
    if (!fold || !spread) return;
    var r = fold.getBoundingClientRect(), track = fold.offsetHeight - window.innerHeight;
    if (mbar) mbar.classList.toggle('is-on', r.top < window.innerHeight * 0.5);
    if (window.innerWidth < 800) { var mo = clamp((window.innerHeight * 0.85 - r.top) / (window.innerHeight * 0.15), 0, 1); if (cover) { cover.style.setProperty('--out', mo.toFixed(3)); cover.classList.toggle('is-out', mo >= 1); } return; }
    if (track <= 0) return;
    var p = clamp(-r.top / track, 0, 1), e = p < 0.5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2;
    spread.style.setProperty('--fold', e.toFixed(4)); fold.classList.toggle('is-open', p > 0.9); var en = clamp(p / 0.3, 0, 1), out = clamp(en / 0.5, 0, 1); fold.style.setProperty('--enter', en.toFixed(3)); fold.style.setProperty('--tenter', clamp((en - 0.55) / 0.45, 0, 1).toFixed(3)); if (cover) { cover.style.setProperty('--out', out.toFixed(3)); cover.classList.toggle('is-out', out >= 1); }
    if (r.top < window.innerHeight * 0.5 && r.bottom > window.innerHeight * 0.5) setChapter('01', 'Campus life');
  }
  if (reduced && spread) spread.style.setProperty('--fold', '1');

  /* ---------- scroll loop ---------- */
  var ticking = false;
  function onScroll() { if (ticking) return; ticking = true; requestAnimationFrame(function () { ticking = false; foldScroll(); coverScroll(); syncVideo(); deckChapter(); }); }
  window.addEventListener('scroll', onScroll, { passive: true }); window.addEventListener('resize', onScroll);

  /* ---------- deck: one panel area, hash-routed ---------- */
  var tabs = $$('[data-tab]'), panels = $$('.dp'), deck = $('#deck'), nav = $('[data-deck-nav]');
  var ids = tabs.map(function (t) { return t.dataset.tab; }), current = ids[0] || '';
  function show(id, push, scroll) {
    if (ids.indexOf(id) < 0) return false;
    current = id;
    panels.forEach(function (p) { var on = p.id === id; p.hidden = !on; if (on) p.removeAttribute('inert'); else p.setAttribute('inert', ''); });
    tabs.forEach(function (t) { var on = t.dataset.tab === id; t.setAttribute('aria-selected', on ? 'true' : 'false'); t.tabIndex = on ? 0 : -1; });
    var p = $('#' + id); if (p) setChapter(p.dataset.chapter, p.dataset.chapterName);
    if (push) { if (location.hash !== '#' + id) history.pushState({ tab: id }, '', '#' + id); }
    if (scroll && deck) { var top = deck.getBoundingClientRect().top + window.pageYOffset - 64; if (window.pageYOffset > top + 40 || window.pageYOffset < top - 40) window.scrollTo({ top: top, behavior: reduced ? 'auto' : 'smooth' }); }
    if (nav) { var a = $('[data-tab="' + id + '"]', nav); var ul = nav.querySelector('ul'); if (a && ul && ul.scrollWidth > ul.clientWidth + 2) ul.scrollTo({ left: a.offsetLeft - (ul.clientWidth - a.offsetWidth) / 2, behavior: reduced ? 'auto' : 'smooth' }); }
    startCounters(); return true;
  }
  tabs.forEach(function (t, i) {
    t.addEventListener('click', function (e) { e.preventDefault(); show(t.dataset.tab, true, true); });
    t.addEventListener('keydown', function (e) {
      var k = e.key, n = -1; if (k === 'ArrowRight') n = (i + 1) % tabs.length; else if (k === 'ArrowLeft') n = (i - 1 + tabs.length) % tabs.length; else if (k === 'Home') n = 0; else if (k === 'End') n = tabs.length - 1;
      if (n > -1) { e.preventDefault(); tabs[n].focus(); show(tabs[n].dataset.tab, true, false); }
    });
  });
  function fromHash(scroll) { var h = location.hash.replace('#', ''); if (ids.indexOf(h) > -1) { show(h, false, scroll); return true; } return false; }
  window.addEventListener('popstate', function () { if (!fromHash(true)) show(ids[0], false, false); });
  window.addEventListener('hashchange', function () { fromHash(true); });
  function deckChapter() { if (!deck) return; var r = deck.getBoundingClientRect(); if (r.top < window.innerHeight * 0.5 && r.bottom > window.innerHeight * 0.5) { var p = $('#' + current); if (p) setChapter(p.dataset.chapter, p.dataset.chapterName); } var why = $('#why'); if (why) { var w = why.getBoundingClientRect(); if (w.top < window.innerHeight * 0.5 && w.bottom > window.innerHeight * 0.2) setChapter('08', 'Why this concept'); } }
  if (!fromHash(true)) show(ids[0], false, false);

  /* ---------- counters (04) ---------- */
  var counted = false;
  function startCounters() {
    if (counted || current !== 'career') return; counted = true;
    $$('[data-count]').forEach(function (el) {
      var to = +el.dataset.count, pre = el.dataset.prefix || '', suf = el.dataset.suffix || '';
      if (reduced) { el.textContent = pre + to + suf; return; }
      var t0 = null; (function step(ts) { if (!t0) t0 = ts; var k = clamp((ts - t0) / 900, 0, 1); if (k >= 1) { el.textContent = pre + to + suf; return; } el.textContent = pre + Math.round(to * (1 - Math.pow(1 - k, 3))) + suf; requestAnimationFrame(step); })(performance.now());
    });
  }

  /* ---------- testimonial stack ---------- */
  var track = $('[data-stack-track]'), prev = $('[data-stack-prev]'), next = $('[data-stack-next]');
  function slide(dir) { if (!track) return; var card = track.firstElementChild; var w = card ? card.getBoundingClientRect().width + 12 : 300; track.scrollBy({ left: dir * w, behavior: reduced ? 'auto' : 'smooth' }); }
  if (prev) prev.addEventListener('click', function () { slide(-1); }); if (next) next.addEventListener('click', function () { slide(1); });

  /* ---------- gallery dialog ---------- */
  var ALBUMS = {
    palais: { t: 'Petit Palais · 16 Oct', f: ['palais-1', 'palais-15', 'palais-17', 'palais-19', 'palais-21', 'palais-23', 'palais-25', 'palais-27'] },
    memorial: { t: 'Jews Memorial · 24 Oct', f: ['memorial-1', 'memorial-2', 'memorial-5', 'memorial-9'] },
    city: { t: 'City trip · 13 Nov', f: ['city-trip-1', 'city-trip-5', 'city-trip-6', 'city-trip-8'] },
    atelier: { t: 'Atelier des Lumières', f: ['atelier-1', 'atelier-2', 'atelier-4', 'atelier-5', 'atelier-8'] },
    'class': { t: 'Class highlight', f: ['class-5', 'class-8', 'class-11', 'class-12'] }
  };
  var dlg = $('[data-gallery]'), galGrid = $('[data-gal-grid]'), galTitle = $('[data-gal-title]'), opener = null;
  function openAlbum(key, btn) {
    var a = ALBUMS[key]; if (!a || !dlg || !galGrid) return;
    galTitle.textContent = a.t; galGrid.innerHTML = '';
    a.f.forEach(function (n, i) { var img = document.createElement('img'); img.src = 'assets/img/' + n + '.webp'; img.alt = a.t + ' — photo ' + (i + 1); img.width = 1080; img.height = 1080; img.loading = 'lazy'; galGrid.appendChild(img); });
    opener = btn || null;
    if (typeof dlg.showModal === 'function') dlg.showModal(); else dlg.setAttribute('open', '');
  }
  function closeAlbum() { if (!dlg) return; if (dlg.open && typeof dlg.close === 'function') dlg.close(); else dlg.removeAttribute('open'); if (opener) opener.focus(); }
  $$('[data-album]').forEach(function (b) { b.addEventListener('click', function () { openAlbum(b.dataset.album, b); }); });
  var gc = $('[data-gal-close]'); if (gc) gc.addEventListener('click', closeAlbum);
  if (dlg) dlg.addEventListener('click', function (e) { if (e.target === dlg) closeAlbum(); });

  /* ---------- mobile bottom bar: shown once the cover CTA leaves ---------- */

  /* ---------- record mode ---------- */
  if (REC) {
    var FPS = 30, SEC = 11;
    window.__tick = function (f) { var t = f / FPS * 1000, p = clamp((f % (FPS * SEC)) / (FPS * SEC), 0, 1); if (backdropOn && window.MISBBackdrop) { window.MISBBackdrop.setProgress(p); window.MISBBackdrop.render(t); } return p; };
    window.__tick(0);
  } else { foldScroll(); coverScroll(); }
})();
