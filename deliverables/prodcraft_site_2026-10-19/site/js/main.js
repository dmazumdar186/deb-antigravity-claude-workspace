/* ProdCraft v2 — one IIFE. Cover scrub + backdrop/video, ledger tri-fold scrub + sheet turn, deck tabs with hash routing,
   persona spotlight (?for= / #02-<persona>), counters, plate dialog, header chapter indicator, mobile bar.
   ?record=1 + window.__tick(frame) => deterministic cover frames for render_hero_video.mjs (Kling-ready slot). */
(function () {
  'use strict';
  var root = document.documentElement, $ = function (s, c) { return (c || document).querySelector(s); }, $$ = function (s, c) { return Array.prototype.slice.call((c || document).querySelectorAll(s)); };
  var mq = function (q) { return !!(window.matchMedia && window.matchMedia(q).matches); };
  var REC = /[?&]record=1/.test(location.search), reduced = !REC && mq('(prefers-reduced-motion: reduce)');
  var clamp = function (v, a, b) { return v < a ? a : v > b ? b : v; };
  var BD = function () { return window.ProdCraftBackdrop; };
  root.classList.add('has-js'); if (REC) root.classList.add('rec');
  window.addEventListener('error', function () { root.classList.remove('has-js'); });

  /* ---------- counters: exact string on the final frame ---------- */
  function fmt(n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ','); }
  function count(el) {
    var to = +el.dataset.count, pre = el.dataset.prefix || '', suf = el.dataset.suffix || '', fin = pre + fmt(to) + suf;
    if (reduced || el.dataset.done) { el.textContent = fin; return; }
    el.dataset.done = '1'; var t0 = null;
    (function step(ts) { if (!t0) t0 = ts; var k = clamp((ts - t0) / 900, 0, 1); if (k >= 1) { el.textContent = fin; return; } el.textContent = pre + fmt(Math.round(to * (1 - Math.pow(1 - k, 3)))) + suf; requestAnimationFrame(step); })(performance.now());
  }

  /* ---------- header chapter indicator ---------- */
  var hdr = $('[data-hdr]'), chNo = $('[data-chapter-no]'), chName = $('[data-chapter-name]'), rule = $('.hdr__rule');
  function setChapter(no, name) { if (chNo) chNo.textContent = no; if (chName) chName.textContent = name; if (rule) rule.style.setProperty('--prog', (parseInt(no, 10) / 8).toFixed(2)); }

  /* ---------- cover: 5 beats, 00 = p 0–.25, 04 held to track end ---------- */
  var mbar = $('[data-mbar]'), fold = $('[data-fold]'), spread = $('[data-spread]');
  var cover = $('[data-cover]'), beats = $$('[data-beat]'), railItems = $$('[data-rail-item]'), canvas = $('[data-backdrop]'), vid = $('[data-hero-video]');
  var EDGES = [0, 0.25, 0.4, 0.55, 0.7, 1.0001], lastBeat = -1, moveTimer = 0, backdropOn = false;
  function beatOf(p) { for (var i = EDGES.length - 2; i >= 0; i--) if (p >= EDGES[i]) return i; return 0; }
  function setBeat(n) {
    if (n === lastBeat) return; lastBeat = n;
    beats.forEach(function (b, k) { b.classList.toggle('is-on', k === n); if (k === n) $$('[data-count]', b).forEach(count); });
    railItems.forEach(function (r, k) { r.classList.toggle('is-on', k === n); r.classList.toggle('is-done', k < n); });
    if (cover) cover.dataset.cur = n;
  }
  function applyCover(p) {
    var n = beatOf(p); setBeat(n);
    var seg = (p - EDGES[n]) / (Math.min(1, EDGES[n + 1]) - EDGES[n]); railItems.forEach(function (r, k) { r.style.setProperty('--p', k === n ? clamp(seg, 0, 1).toFixed(3) : '0'); });
    if (backdropOn && BD()) BD().setProgress(p);
  }
  function coverScroll() {
    if (!cover) return;
    var r = cover.getBoundingClientRect(), track = cover.offsetHeight - window.innerHeight; if (track <= 0) return;
    applyCover(clamp(-r.top / track, 0, 1));
    if (hdr) { var out = parseFloat(cover.style.getPropertyValue('--out') || '0'); hdr.classList.toggle('over', r.bottom > 64 && out < 1); }
    cover.classList.add('is-moving'); clearTimeout(moveTimer); moveTimer = setTimeout(function () { cover.classList.remove('is-moving'); }, 900);
    if (r.bottom > window.innerHeight * 0.5) setChapter('00', 'Cover');
  }
  if (canvas && BD()) {
    try { BD().init(canvas, { seed: 20261019, dpr: reduced ? 1 : (window.innerWidth < 768 ? 1.25 : 1.5), reducedMotion: reduced, autoplay: !REC }); backdropOn = true; } catch (err) { backdropOn = false; }
  }
  if (cover && backdropOn && 'IntersectionObserver' in window) {
    new IntersectionObserver(function (es) { if (!BD() || cover.classList.contains('has-video')) return; if (es[0].isIntersecting) BD().resume(); else BD().pause(); }, { threshold: 0 }).observe(cover);
  }
  // footage: assets/hero.json ready:true => play hero.mp4 / hero-m.mp4; canvas is the fallback. ?canvas=1 forces the canvas (QA).
  function syncVideo() { if (!vid || !cover || !cover.classList.contains('has-video')) return; var r = cover.getBoundingClientRect(); var on = r.bottom > 0 && !document.hidden; if (on) { if (vid.paused) { var pl = vid.play(); if (pl && pl.catch) pl.catch(function () {}); } } else if (!vid.paused) vid.pause(); }
  if (vid && cover && !REC && !/[?&]canvas=1/.test(location.search) && window.fetch && /^https?:/.test(location.protocol)) {
    var con = navigator.connection, saveData = !!(con && con.saveData);
    fetch('assets/hero.json').then(function (r) { return r.ok ? r.json() : null; }).then(function (mf) {
      if (!mf || !mf.ready) return;
      if (mf.poster) vid.poster = 'assets/' + mf.poster;
      if (reduced || saveData) { cover.classList.add('has-poster'); return; }
      var f = ((window.innerWidth < 768 || mq('(orientation: portrait)')) && mf.portrait) || mf.landscape || 'hero.mp4';
      vid.addEventListener('playing', function () { cover.classList.add('has-video'); if (BD() && backdropOn) BD().pause(); }, { once: true });
      vid.addEventListener('error', function () { cover.classList.remove('has-video'); if (BD() && backdropOn) BD().resume(); }, { once: true });
      vid.innerHTML = '<source src="assets/' + f + '" type="video/mp4"><source src="assets/' + f.replace(/\.mp4$/, '.webm') + '" type="video/webm">';
      vid.load(); var pl = vid.play(); if (pl && pl.catch) pl.catch(function () {});
    }).catch(function () {});
    document.addEventListener('visibilitychange', syncVideo);
  }

  /* ---------- 01 ledger: hinge scrub + sheet turn (flat snap row on phones, portrait tablets/TV and landscape phones) ---------- */
  function flat() { return window.innerWidth < 768 || mq('(orientation: portrait)') || window.innerHeight <= 500; }
  var navEl = $('[data-deck-nav]');
  function navVar() { if (navEl) root.style.setProperty('--navh', navEl.offsetHeight + 'px'); }
  navVar(); window.addEventListener('resize', navVar);
  function foldScroll() {
    if (!fold || !spread) return;
    var r = fold.getBoundingClientRect(), track = fold.offsetHeight - window.innerHeight;
    if (mbar) mbar.classList.toggle('is-on', !!(cover && cover.classList.contains('is-out')) || r.top < 0);
    if (flat()) { var mo = clamp((window.innerHeight * 0.85 - r.top) / (window.innerHeight * 0.15), 0, 1); if (cover) { cover.style.setProperty('--out', mo.toFixed(3)); cover.classList.toggle('is-out', mo >= 1); } if (mbar) mbar.classList.toggle('is-on', mo >= 1); if (r.top < window.innerHeight * 0.5 && r.bottom > window.innerHeight * 0.5) setChapter('01', 'The ledger'); return; }
    if (track <= 0) return;
    var p = clamp(-r.top / track, 0, 1), e = p < 0.5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2;
    if (!reduced) spread.style.setProperty('--fold', e.toFixed(4));
    fold.classList.toggle('is-open', p > 0.9);
    var en = clamp(p / 0.3, 0, 1), out = clamp(en / 0.5, 0, 1);
    fold.style.setProperty('--enter', en.toFixed(3)); fold.style.setProperty('--tenter', clamp((en - 0.55) / 0.2, 0, 1).toFixed(3));
    if (cover) { cover.style.setProperty('--out', out.toFixed(3)); cover.classList.toggle('is-out', out >= 1); }
    if (r.top < window.innerHeight * 0.5 && r.bottom > window.innerHeight * 0.5) setChapter('01', 'The ledger');
  }
  if (reduced && spread) spread.style.setProperty('--fold', '1');
  var sheets = $$('[data-sheet-i]'), dots = $$('[data-turn-dot]'), sheetI = 0;
  function turn(i) {
    if (!sheets.length) return; sheetI = (i + sheets.length) % sheets.length;
    sheets.forEach(function (s, k) { s.hidden = k !== sheetI; });
    dots.forEach(function (d, k) { d.setAttribute('aria-selected', k === sheetI ? 'true' : 'false'); });
    if (spread) spread.dataset.sheet = sheetI;
  }
  function desktopFold() { return !flat(); }
  if (sheets.length) {
    if (desktopFold()) turn(0);
    var tp = $('[data-turn-prev]'), tn = $('[data-turn-next]');
    if (tp) tp.addEventListener('click', function () { turn(sheetI - 1); });
    if (tn) tn.addEventListener('click', function () { turn(sheetI + 1); });
    dots.forEach(function (d, k) { d.addEventListener('click', function () { turn(k); }); });
    if (spread) spread.addEventListener('keydown', function (e) { if (!desktopFold()) return; if (e.key === 'ArrowRight') { e.preventDefault(); turn(sheetI + 1); } else if (e.key === 'ArrowLeft') { e.preventDefault(); turn(sheetI - 1); } });
  }

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
    var p = $('#' + id); if (p) { setChapter(p.dataset.chapter, p.dataset.chapterName); $$('[data-count]', p).forEach(count); }
    if (push && location.hash !== '#' + id) history.pushState({ tab: id }, '', location.pathname + location.search + '#' + id);
    if (scroll && deck) { var top = deck.getBoundingClientRect().top + window.pageYOffset - (hdr ? hdr.offsetHeight : 64); if (window.pageYOffset > top + 40 || window.pageYOffset < top - 40) window.scrollTo({ top: top, behavior: reduced ? 'auto' : 'smooth' }); }
    if (nav) { var a = $('[data-tab="' + id + '"]', nav), ul = nav.querySelector('ul'); if (a && ul && ul.scrollWidth > ul.clientWidth + 2) ul.scrollTo({ left: a.offsetLeft - (ul.clientWidth - a.offsetWidth) / 2, behavior: reduced ? 'auto' : 'smooth' }); }
    return true;
  }
  tabs.forEach(function (t, i) {
    t.addEventListener('click', function (e) { e.preventDefault(); show(t.dataset.tab, true, true); });
    t.addEventListener('keydown', function (e) {
      var k = e.key, n = -1; if (k === 'ArrowRight') n = (i + 1) % tabs.length; else if (k === 'ArrowLeft') n = (i - 1 + tabs.length) % tabs.length; else if (k === 'Home') n = 0; else if (k === 'End') n = tabs.length - 1;
      if (n > -1) { e.preventDefault(); tabs[n].focus(); show(tabs[n].dataset.tab, true, false); }
    });
  });

  /* ---------- 02 personas: spotlight 03 + contact headline ---------- */
  var PERSONAS = {
    founder: { order: ['mobile', 'video', 'cv', 'operator', 'jev', 'outbound', 'adoption', 'lists', 'audit'], h: 'Stop reading. Scope a first build.' },
    sales: { order: ['outbound', 'lists', 'jev', 'operator', 'cv', 'video', 'adoption', 'mobile', 'audit'], h: 'Stop reading. Start the pipeline.' },
    recruiter: { order: ['lists', 'cv', 'outbound', 'audit', 'jev', 'video', 'operator', 'mobile', 'adoption'], h: 'Stop reading. Ship the site.' },
    enterprise: { order: ['adoption', 'operator', 'jev', 'audit', 'cv', 'outbound', 'mobile', 'video', 'lists'], h: 'Stop reading. Put GenAI in production.' }
  };
  var contactH = $('[data-contact-h]'), defaultH = contactH ? contactH.textContent : '', persona = '';
  function setPersona(key, push) {
    var P = PERSONAS[key]; if (!P) return false; persona = key;
    $$('[data-persona]').forEach(function (b) { var on = b.dataset.persona === key; b.setAttribute('aria-pressed', on ? 'true' : 'false'); });
    $$('[data-persona-card]').forEach(function (c) { c.classList.toggle('is-on', c.dataset.personaCard === key); });
    $$('[data-sys-id]').forEach(function (c) { var i = P.order.indexOf(c.dataset.sysId); c.style.order = i < 0 ? 99 : i; c.classList.toggle('is-pick', i > -1 && i < 3); });
    if (contactH) contactH.textContent = P.h || defaultH;
    if (push) { var q = '?for=' + key; history.pushState({ tab: 'who', persona: key }, '', location.pathname + q + '#02-' + key); }
    return true;
  }
  $$('[data-persona]').forEach(function (b) { b.addEventListener('click', function () { setPersona(b.dataset.persona, true); show('who', false, false); }); });

  function fromHash(scroll) {
    var h = location.hash.replace('#', ''), m = /^02-(\w+)$/.exec(h);
    if (!(m && PERSONAS[m[1]]) && /^\d\d-/.test(h) && ids.indexOf(h.slice(3)) > -1) h = h.slice(3);
    if (m && PERSONAS[m[1]]) { setPersona(m[1], false); show('who', false, scroll); return true; }
    if (ids.indexOf(h) > -1) { show(h, false, scroll); return true; }
    return false;
  }
  window.addEventListener('popstate', function () { var q = /[?&]for=(\w+)/.exec(location.search); if (q) setPersona(q[1], false); if (!fromHash(true)) show(ids[0], false, false); });
  window.addEventListener('hashchange', function () { fromHash(true); });
  function deckChapter() { if (!deck) return; var r = deck.getBoundingClientRect(); if (r.top < window.innerHeight * 0.5 && r.bottom > window.innerHeight * 0.3) { var p = $('#' + current); if (p) setChapter(p.dataset.chapter, p.dataset.chapterName); } }
  var qf = /[?&]for=(\w+)/.exec(location.search); if (qf) setPersona(qf[1], false);
  if (location.hash && fromHash(false)) { var jump = function () { if (!deck) return; var html = root.style.scrollBehavior; root.style.scrollBehavior = 'auto'; window.scrollTo(0, deck.getBoundingClientRect().top + window.pageYOffset - (hdr ? hdr.offsetHeight : 64)); root.style.scrollBehavior = html; onScroll(); }; if (document.readyState === 'complete') jump(); else window.addEventListener('load', function () { requestAnimationFrame(jump); }); } else show(ids[0], false, false);

  /* ---------- plate dialog ---------- */
  var PLATES = { misb: 'Private business school, Paris — prospectus concept', gtm: 'SaaS GTM recruiter, London — concept', midas: 'Franchise auto-service brand, France — concept', greenjobs: 'GreenJobs — greenjobs.ie / .co.uk' };
  var dlg = $('[data-gallery]'), galGrid = $('[data-gal-grid]'), galTitle = $('[data-gal-title]'), opener = null;
  function openPlate(key, btn) {
    if (!PLATES[key] || !dlg || !galGrid) return;
    if (galTitle) galTitle.textContent = PLATES[key]; galGrid.innerHTML = '';
    var img = document.createElement('img'); img.src = 'assets/plates/' + key + '.webp'; img.alt = PLATES[key] + ' — screenshot at 1440 px'; img.width = 1200; img.height = 750; galGrid.appendChild(img);
    opener = btn || null;
    if (typeof dlg.showModal === 'function') dlg.showModal(); else dlg.setAttribute('open', '');
  }
  function closePlate() { if (!dlg) return; if (dlg.open && typeof dlg.close === 'function') dlg.close(); else dlg.removeAttribute('open'); if (opener) opener.focus(); }
  $$('[data-plate-open]').forEach(function (b) { b.addEventListener('click', function () { openPlate(b.dataset.plateOpen, b); }); });
  var gc = $('[data-gal-close]'); if (gc) gc.addEventListener('click', closePlate);
  if (dlg) dlg.addEventListener('click', function (e) { if (e.target === dlg) closePlate(); });

  /* ---------- record mode ---------- */
  if (REC) {
    var FPS = 30, SEC = 11;
    window.__tick = function (f) { var t = f / FPS * 1000, p = clamp((f % (FPS * SEC)) / (FPS * SEC), 0, 1); if (backdropOn && BD()) { BD().setProgress(p); BD().render(t); } return p; };
    window.__tick(0);
  } else { foldScroll(); coverScroll(); }
})();
