/* ASSET Voyages concept — one IIFE. Cover scrub + backdrop/video, fold-out scrub, deck tabs with hash routing,
   MICE progressive brief, congress catalogue (search, filters, date sort, pager, no-results, listing dialog,
   prefilled flight-quote form), counters, reveals, header chapter indicator, mobile bar.
   Front-end only: no form is sent anywhere. ?record=1 + window.__tick(frame) => deterministic cover frames. */
(function () {
  'use strict';
  var root = document.documentElement, $ = function (s, c) { return (c || document).querySelector(s); }, $$ = function (s, c) { return Array.prototype.slice.call((c || document).querySelectorAll(s)); };
  var mq = function (q) { return !!(window.matchMedia && window.matchMedia(q).matches); };
  var REC = /[?&]record=1/.test(location.search), reduced = !REC && mq('(prefers-reduced-motion: reduce)');
  var clamp = function (v, a, b) { return v < a ? a : v > b ? b : v; };
  var BD = window.AssetBackdrop;
  root.classList.add('has-js'); if (REC) root.classList.add('rec');
  window.addEventListener('error', function () { root.classList.remove('has-js'); });

  /* ---------- reveals: additive on desktop, painted on phones ---------- */
  var reveals = $$('.reveal');
  if (reveals.length && 'IntersectionObserver' in window && window.innerWidth >= 800 && !reduced) {
    var io = new IntersectionObserver(function (es) { es.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add('is-in'); io.unobserve(e.target); } }); }, { threshold: 0.01, rootMargin: '0px 0px 8% 0px' });
    reveals.forEach(function (el) { io.observe(el); });
    setTimeout(function () { reveals.forEach(function (el) { el.classList.add('is-in'); }); }, 2500);
  } else reveals.forEach(function (el) { el.classList.add('is-in'); });

  /* ---------- header chapter indicator ---------- */
  var hdr = $('[data-hdr]'), chNo = $('[data-chapter-no]'), chName = $('[data-chapter-name]'), rule = $('.hdr__rule');
  function setChapter(no, name) { if (chNo) chNo.textContent = no; if (chName) chName.textContent = name; if (rule) rule.style.setProperty('--prog', (parseInt(no, 10) / 6).toFixed(2)); }

  /* ---------- cover ---------- */
  var mbar = $('[data-mbar]'), fold = $('[data-fold]'), spread = $('[data-spread]');
  var cover = $('[data-cover]'), beats = $$('[data-beat]'), railItems = $$('[data-rail-item]'), plates = $$('[data-plate]'), canvas = $('[data-backdrop]'), vid = $('[data-hero-video]');
  var lastBeat = -1, moveTimer = 0, backdropOn = false;
  function setBeat(n) {
    if (n === lastBeat) return; lastBeat = n;
    beats.forEach(function (b, k) { b.classList.toggle('is-on', k === n); });
    railItems.forEach(function (r, k) { r.classList.toggle('is-on', k === n); r.classList.toggle('is-done', k < n); });
    plates.forEach(function (pl) { pl.classList.toggle('is-on', +pl.dataset.plate === n); });
  }
  function applyCover(p) {
    var n = Math.min(3, Math.floor(p * 4)); setBeat(n);
    var seg = p * 4 - n; railItems.forEach(function (r, k) { r.style.setProperty('--p', k === n ? seg.toFixed(3) : '0'); });
    if (cover) cover.dataset.cur = n;
    if (backdropOn && BD) BD.setProgress(p);
  }
  function coverScroll() {
    if (!cover) return;
    var r = cover.getBoundingClientRect(), track = cover.offsetHeight - window.innerHeight; if (track <= 0) return;
    applyCover(clamp(-r.top / track, 0, 1));
    if (hdr) { var out = parseFloat(cover.style.getPropertyValue('--out') || '0'); hdr.classList.toggle('over', r.bottom > 64 && out < 1); }
    cover.classList.add('is-moving'); clearTimeout(moveTimer); moveTimer = setTimeout(function () { cover.classList.remove('is-moving'); }, 900);
    if (r.bottom > window.innerHeight * 0.5 && !cover.classList.contains('is-out')) setChapter('00', 'Couverture');
  }
  if (canvas && BD) {
    try { BD.init(canvas, { seed: 20261028, dpr: window.innerWidth < 800 ? 1.25 : 1.5, reducedMotion: reduced, autoplay: !REC }); backdropOn = true; } catch (err) { backdropOn = false; }
  }
  if (cover && backdropOn && !reduced && 'IntersectionObserver' in window) {
    new IntersectionObserver(function (es) { if (es[0].isIntersecting) BD.resume(); else BD.pause(); }, { threshold: 0 }).observe(cover);
  }
  function syncVideo() { if (!vid || !cover || !cover.classList.contains('has-video')) return; var r = cover.getBoundingClientRect(); var on = r.bottom > 0 && !document.hidden; if (on) { if (vid.paused) vid.play().catch(function () {}); } else if (!vid.paused) vid.pause(); }
  if (vid && cover && !REC && !/[?&]canvas=1/.test(location.search) && window.fetch && /^https?:/.test(location.protocol)) {
    var con = navigator.connection, saveData = !!(con && con.saveData);
    fetch('assets/hero.json').then(function (r) { return r.ok ? r.json() : null; }).then(function (mf) {
      if (!mf || !mf.ready || reduced || saveData) return;
      var f = (window.innerWidth < 800 && mf.portrait) || mf.landscape || 'hero.mp4';
      if (mf.poster) vid.poster = 'assets/' + mf.poster;
      vid.addEventListener('playing', function () { cover.classList.add('has-video'); if (backdropOn) BD.pause(); }, { once: true });
      vid.addEventListener('error', function () { cover.classList.remove('has-video'); if (backdropOn) BD.resume(); }, { once: true });
      var s1 = document.createElement('source'); s1.src = 'assets/' + f; s1.type = 'video/mp4';
      var s2 = document.createElement('source'); s2.src = 'assets/' + f.replace(/\.mp4$/, '.webm'); s2.type = 'video/webm';
      vid.appendChild(s1); vid.appendChild(s2); vid.load(); var pl = vid.play(); if (pl && pl.catch) pl.catch(function () {});
    }).catch(function () {});
    document.addEventListener('visibilitychange', syncVideo);
  }

  /* ---------- fold-out ---------- */
  function foldScroll() {
    if (!fold || !spread) return;
    var r = fold.getBoundingClientRect(), track = fold.offsetHeight - window.innerHeight;
    if (mbar) mbar.classList.toggle('is-on', r.top < window.innerHeight * 0.5);
    if (r.top < window.innerHeight * 0.5 && r.bottom > window.innerHeight * 0.5) setChapter('00', 'Sommaire');
    if (window.innerWidth < 800) { var mo = clamp((window.innerHeight * 0.85 - r.top) / (window.innerHeight * 0.15), 0, 1); if (cover) { cover.style.setProperty('--out', mo.toFixed(3)); cover.classList.toggle('is-out', mo >= 1); } return; }
    if (track <= 0) return;
    var p = clamp(-r.top / track, 0, 1), e = p < 0.5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2;
    spread.style.setProperty('--fold', reduced ? '1' : e.toFixed(4)); fold.classList.toggle('is-open', p > 0.9);
    var en = clamp(p / 0.3, 0, 1), out = clamp(en / 0.5, 0, 1);
    fold.style.setProperty('--enter', en.toFixed(3)); fold.style.setProperty('--tenter', clamp((en - 0.55) / 0.45, 0, 1).toFixed(3));
    if (cover) { cover.style.setProperty('--out', out.toFixed(3)); cover.classList.toggle('is-out', out >= 1); }
  }
  if (reduced && spread) spread.style.setProperty('--fold', '1');

  /* ---------- scroll loop ---------- */
  var ticking = false;
  function onScroll() { if (ticking) return; ticking = true; requestAnimationFrame(function () { ticking = false; foldScroll(); coverScroll(); syncVideo(); deckChapter(); }); }
  window.addEventListener('scroll', onScroll, { passive: true }); window.addEventListener('resize', onScroll);

  /* ---------- deck: one panel area, hash-routed ---------- */
  var tabs = $$('[data-tab]'), panels = $$('.dp'), deck = $('#deck'), nav = $('[data-deck-nav]');
  var ids = tabs.map(function (t) { return t.dataset.tab; }), current = ids[0] || '';
  function deckTop() { return deck ? deck.getBoundingClientRect().top + window.pageYOffset - 64 : 0; }
  function show(id, push, scroll) {
    if (ids.indexOf(id) < 0) return false;
    current = id;
    panels.forEach(function (p) { var on = p.id === id; p.hidden = !on; if (on) p.removeAttribute('inert'); else p.setAttribute('inert', ''); });
    tabs.forEach(function (t) { var on = t.dataset.tab === id; t.setAttribute('aria-selected', on ? 'true' : 'false'); t.tabIndex = on ? 0 : -1; });
    var p = $('#' + id); if (p) setChapter(p.dataset.chapter, p.dataset.chapterName);
    if (push && location.hash !== '#' + id) history.pushState({ tab: id }, '', '#' + id);
    if (scroll && deck) { var top = deckTop(); if (Math.abs(window.pageYOffset - top) > 40) window.scrollTo({ top: top, behavior: reduced ? 'auto' : 'smooth' }); }
    if (nav) { var a = $('[data-tab="' + id + '"]', nav), ul = nav.querySelector('ul'); if (a && ul && ul.scrollWidth > ul.clientWidth + 2) ul.scrollTo({ left: a.offsetLeft - (ul.clientWidth - a.offsetWidth) / 2, behavior: reduced ? 'auto' : 'smooth' }); }
    startCounters(); return true;
  }
  tabs.forEach(function (t, i) {
    t.addEventListener('click', function (e) { e.preventDefault(); show(t.dataset.tab, true, true); });
    t.addEventListener('keydown', function (e) {
      var k = e.key, n = -1; if (k === 'ArrowRight') n = (i + 1) % tabs.length; else if (k === 'ArrowLeft') n = (i - 1 + tabs.length) % tabs.length; else if (k === 'Home') n = 0; else if (k === 'End') n = tabs.length - 1;
      if (n > -1) { e.preventDefault(); tabs[n].focus(); show(tabs[n].dataset.tab, true, false); }
    });
  });
  function fromHash(scroll) {
    var h = location.hash.replace('#', '');
    if (h === 'espace-client') { show('voyages', false, false); var ec = $('#espace-client'); if (ec && scroll) ec.scrollIntoView({ block: 'center' }); return true; }
    if (ids.indexOf(h) > -1) { show(h, false, scroll); return true; } return false;
  }
  window.addEventListener('popstate', function () { if (!fromHash(true)) show(ids[0], false, false); });
  window.addEventListener('hashchange', function () { fromHash(true); });
  function deckChapter() {
    if (!deck) return; var r = deck.getBoundingClientRect();
    if (r.top < window.innerHeight * 0.5 && r.bottom > window.innerHeight * 0.5) { var p = $('#' + current); if (p) setChapter(p.dataset.chapter, p.dataset.chapterName); }
    var why = $('#why'); if (why) { var w = why.getBoundingClientRect(); if (w.top < window.innerHeight * 0.5 && w.bottom > window.innerHeight * 0.2) setChapter('06', 'Pourquoi ce concept'); }
  }
  if (!fromHash(true)) show(ids[0], false, false);

  // jump links anywhere on the page: data-go="<tab>", optional data-need (prefills F01) / data-focus
  var needSel = $('[data-need-select]');
  $$('[data-go]').forEach(function (a) {
    a.addEventListener('click', function (e) {
      e.preventDefault(); var id = a.dataset.go;
      if (a.getAttribute('href') === '#espace-client') { show('voyages', true, false); var ec = $('#espace-client'); if (ec) ec.scrollIntoView({ block: 'center', behavior: reduced ? 'auto' : 'smooth' }); return; }
      show(id, true, true);
      if (a.dataset.need && needSel) { needSel.value = a.dataset.need; }
    });
  });
  $$('[data-focus]').forEach(function (a) { a.addEventListener('click', function (e) { var el = document.getElementById(a.dataset.focus); if (el) { e.preventDefault(); el.focus(); } }); });
  var cBtn = $('[data-client]'), cNote = $('#client-note');
  if (cBtn && cNote) cBtn.addEventListener('click', function () { var open = cNote.hidden; cNote.hidden = !open; cBtn.setAttribute('aria-expanded', open ? 'true' : 'false'); });

  /* ---------- counters (04 L'agence) ---------- */
  var counted = false;
  function startCounters() {
    if (counted || current !== 'agence') return; counted = true;
    $$('[data-count]').forEach(function (el) {
      var to = +el.dataset.count, pre = el.dataset.prefix || '', suf = el.dataset.suffix || '';
      if (reduced) { el.textContent = pre + to + suf; return; }
      var t0 = null; (function step(ts) { if (!t0) t0 = ts; var k = clamp((ts - t0) / 900, 0, 1); if (k >= 1) { el.textContent = pre + to + suf; return; } el.textContent = pre + Math.round(to * (1 - Math.pow(1 - k, 3))) + suf; requestAnimationFrame(step); })(performance.now());
    });
  }

  /* ---------- simple forms: validate, then confirm (no network) ---------- */
  function okMsg(form, text) { var ok = $('[data-ok]', form); if (!ok) return; if (text) ok.textContent = text; ok.hidden = false; ok.focus && ok.setAttribute('tabindex', '-1'); ok.focus(); }
  var f01 = $('[data-form="f01"]');
  if (f01) f01.addEventListener('submit', function (e) { e.preventDefault(); if (!f01.checkValidity()) { f01.reportValidity(); return; } okMsg(f01); });

  /* ---------- MICE progressive brief ---------- */
  var brief = $('[data-brief]');
  if (brief) {
    var steps = $$('[data-step]', brief), dots = $$('[data-step-dot]', brief), si = 0;
    var bPrev = $('[data-prev]', brief), bNext = $('[data-next]', brief), bSend = $('[data-send]', brief), sum = $('[data-summary]', brief);
    var val = function (n) { var el = brief.elements[n]; if (!el) return ''; if (el.length !== undefined && !el.tagName) { var out = []; Array.prototype.forEach.call(el, function (x) { if (x.checked) out.push(x.value); }); return out.join(', '); } return el.value; };
    var setStep = function (n) {
      si = n; steps.forEach(function (s, k) { s.hidden = k !== n; }); dots.forEach(function (d, k) { d.classList.toggle('is-on', k === n); d.classList.toggle('is-done', k < n); });
      if (bPrev) bPrev.hidden = n === 0; if (bNext) bNext.hidden = n === steps.length - 1; if (bSend) bSend.hidden = n !== steps.length - 1;
      if (n === steps.length - 1 && sum) {
        var rows = [['Événement', val('type')], ['Participants', val('pax')], ['Destination', val('dest') || 'À définir'], ['Période', val('when') + (brief.elements.flex && brief.elements.flex.checked ? ' · dates flexibles' : '')], ['Services', val('svc') || '—'], ['Budget indicatif', val('budget') || 'Non communiqué']];
        sum.textContent = ''; rows.forEach(function (r) { var dt = document.createElement('dt'), dd = document.createElement('dd'); dt.textContent = r[0]; dd.textContent = r[1]; sum.appendChild(dt); sum.appendChild(dd); });
      }
    };
    var stepValid = function () { var bad = $$('input,select,textarea', steps[si]).filter(function (x) { return !x.checkValidity(); }); if (bad.length) { bad[0].reportValidity(); return false; } return true; };
    if (bNext) bNext.addEventListener('click', function () { if (stepValid()) setStep(Math.min(si + 1, steps.length - 1)); });
    if (bPrev) bPrev.addEventListener('click', function () { setStep(Math.max(si - 1, 0)); });
    brief.addEventListener('submit', function (e) { e.preventDefault(); if (!stepValid()) return; okMsg(brief); });
    setStep(0);
  }

  /* ---------- congress catalogue ---------- */
  var MONTHS = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.'];
  var pd = function (s) { var a = s.split('-'); return { y: +a[0], m: +a[1], d: +a[2] }; };
  var fmtRange = function (a, b) { var x = pd(a), y = pd(b); return x.m === y.m ? x.d + '–' + y.d + ' ' + MONTHS[x.m - 1] + ' ' + x.y : x.d + ' ' + MONTHS[x.m - 1] + ' – ' + y.d + ' ' + MONTHS[y.m - 1] + ' ' + y.y; };
  var iso = function (s, delta) { var x = pd(s), dt = new Date(Date.UTC(x.y, x.m - 1, x.d + delta)); return dt.toISOString().slice(0, 10); };
  var list = $('[data-rows]'), filt = $('[data-filters]'), empty = $('[data-empty]'), pager = $('[data-pager]'), countL = $('[data-count-label]');
  var rows = list ? $$('.row', list) : [], PER = 6, page = 1;
  rows.forEach(function (r) { var d = $('.row__date', r); var x = pd(r.dataset.start); if (d) { d.textContent = fmtRange(r.dataset.start, r.dataset.end); } r.dataset.q = Math.floor((x.m - 1) / 3) + 1; });
  rows.sort(function (a, b) { return a.dataset.start < b.dataset.start ? -1 : a.dataset.start > b.dataset.start ? 1 : 0; });
  rows.forEach(function (r) { list.appendChild(r); });
  var norm = function (s) { return (s || '').toLowerCase().normalize ? (s || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '') : (s || '').toLowerCase(); };
  function fillSelect(sel, key) { if (!sel) return; var seen = {}; rows.map(function (r) { return r.dataset[key]; }).sort(function (a, b) { return a.localeCompare(b, 'fr'); }).forEach(function (v) { if (seen[v]) return; seen[v] = 1; var o = document.createElement('option'); o.value = v; o.textContent = v; sel.appendChild(o); }); }
  if (filt) { fillSelect(filt.elements.disc, 'disc'); fillSelect(filt.elements.country, 'country'); }
  function apply() {
    if (!filt) return;
    var q = norm(filt.elements.q.value.trim()), dsc = filt.elements.disc.value, ct = filt.elements.country.value, per = filt.elements.per.value;
    var hits = rows.filter(function (r) {
      var text = norm($('.row__t', r).textContent + ' ' + r.dataset.city + ' ' + r.dataset.country + ' ' + r.dataset.disc);
      return (!q || text.indexOf(q) > -1) && (!dsc || r.dataset.disc === dsc) && (!ct || r.dataset.country === ct) && (!per || r.dataset.q === per);
    });
    var pages = Math.max(1, Math.ceil(hits.length / PER)); page = clamp(page, 1, pages);
    rows.forEach(function (r) { r.hidden = true; });
    hits.slice((page - 1) * PER, page * PER).forEach(function (r) { r.hidden = false; });
    if (empty) empty.hidden = hits.length > 0;
    if (countL) countL.textContent = hits.length + ' congrès' + (pages > 1 ? ' · page ' + page + '/' + pages : '');
    if (pager) {
      pager.textContent = '';
      if (pages > 1) {
        var mk = function (label, to, aria, cur) { var b = document.createElement('button'); b.type = 'button'; b.textContent = label; b.setAttribute('aria-label', aria); if (cur) b.setAttribute('aria-current', 'true'); if (to < 1 || to > pages) b.disabled = true; b.addEventListener('click', function () { page = to; apply(); }); pager.appendChild(b); };
        mk('‹', page - 1, 'Page précédente'); for (var i = 1; i <= pages; i++) mk(String(i), i, 'Page ' + i, i === page); mk('›', page + 1, 'Page suivante');
      }
    }
  }
  if (filt) {
    filt.addEventListener('input', function () { page = 1; apply(); });
    filt.addEventListener('change', function () { page = 1; apply(); });
    filt.addEventListener('submit', function (e) { e.preventDefault(); });
    filt.addEventListener('reset', function () { setTimeout(function () { page = 1; apply(); }, 0); });
    apply();
  }

  /* ---------- listing dialog + prefilled flight quote (F03) ---------- */
  var dlg = $('[data-listing]'), f03 = $('[data-form="f03"]'), opener = null, curRow = null;
  function openListing(r, btn) {
    if (!dlg || !r) return; curRow = r; opener = btn || null;
    var t = $('.row__t', r).textContent, set = function (s, v) { var el = $(s, dlg); if (el) el.textContent = v; };
    set('[data-l-title]', t); set('[data-l-dates]', fmtRange(r.dataset.start, r.dataset.end)); set('[data-l-place]', r.dataset.city + ', ' + r.dataset.country); set('[data-l-disc]', r.dataset.disc); set('[data-l-id]', r.dataset.id);
    if (f03) {
      f03.reset(); var ok = $('[data-ok]', f03); if (ok) ok.hidden = true;
      f03.elements.event.value = t + ' (' + r.dataset.id + ')'; f03.elements.to.value = r.dataset.city + ', ' + r.dataset.country;
      f03.elements.out.value = iso(r.dataset.start, -1); f03.elements.back.value = iso(r.dataset.end, 1);
    }
    if (typeof dlg.showModal === 'function') dlg.showModal(); else dlg.setAttribute('open', '');
  }
  function closeListing() { if (!dlg) return; if (dlg.open && typeof dlg.close === 'function') dlg.close(); else dlg.removeAttribute('open'); if (opener) opener.focus(); }
  rows.forEach(function (r) { var b = $('[data-open]', r); if (b) b.addEventListener('click', function () { openListing(r, b); }); });
  var dc = dlg && $('[data-close]', dlg); if (dc) dc.addEventListener('click', closeListing);
  if (dlg) dlg.addEventListener('click', function (e) { if (e.target === dlg) closeListing(); });
  if (f03) f03.addEventListener('submit', function (e) {
    e.preventDefault(); if (!f03.checkValidity()) { f03.reportValidity(); return; }
    var el = f03.elements, n = +el.pax.value;
    okMsg(f03, 'Demande enregistrée (maquette) — ' + (curRow ? curRow.dataset.id : '') + ' · départ ' + el.from.value + ' · ' + n + (n > 1 ? ' voyageurs' : ' voyageur') + ' · ' + el.cls.value + '. Rien n\'a été envoyé ; en production, la demande est liée au congrès, enregistrée et notifiée à l\'équipe, qui émet le devis.');
  });

  /* ---------- record mode ---------- */
  if (REC) {
    var FPS = 30, SEC = 11;
    window.__tick = function (f) { var t = f / FPS * 1000, p = clamp((f % (FPS * SEC)) / (FPS * SEC), 0, 1); if (backdropOn) { BD.setProgress(p); BD.render(t); } return p; };
    window.__tick(0);
  } else { foldScroll(); coverScroll(); }
})();
