/* main.js — header, reveals, card stack (folio), method drum, congress catalogue, listing + F03 quote,
   contact journeys (F01/F02). Hand-rolled, no libraries, every querySelector guarded. */
(function () {
  'use strict';
  if (/[?&]record=1/.test(location.search)) return;
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return [].slice.call((r || document).querySelectorAll(s)); };
  var clamp = function (v, a, b) { return Math.min(b, Math.max(a, v)); };
  var clamp01 = function (v) { return clamp(Number(v) || 0, 0, 1); };
  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var desktop = window.matchMedia('(min-width: 800px)');
  window.addEventListener('error', function () { document.documentElement.classList.remove('has-js'); });

  /* ---------- header ---------- */
  var header = $('[data-header]'), burger = $('[data-burger]'), menu = $('[data-menu]');
  var mq = window.matchMedia('(max-width: 1050px)');
  function setMenu(open) {
    if (!burger || !menu) return;
    burger.setAttribute('aria-expanded', String(open)); menu.classList.toggle('is-open', open);
    if (mq.matches) menu.inert = !open; else menu.inert = false;
    document.body.style.overflow = open ? 'hidden' : '';
    if (open) { var f = $('a', menu); if (f) f.focus(); }
  }
  if (burger && menu) {
    if (mq.matches) menu.inert = true;
    mq.addEventListener('change', function () { setMenu(false); });
    burger.addEventListener('click', function () { setMenu(burger.getAttribute('aria-expanded') !== 'true'); });
    $$('a', menu).forEach(function (a) { a.addEventListener('click', function () { if (mq.matches) setMenu(false); }); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && burger.getAttribute('aria-expanded') === 'true') { setMenu(false); burger.focus(); } });
  }
  var cBtn = $('[data-client]'), cPop = $('[data-client-pop]');
  if (cBtn && cPop) {
    cBtn.addEventListener('click', function (e) { e.stopPropagation(); var o = cPop.hidden; cPop.hidden = !o; cBtn.setAttribute('aria-expanded', String(o)); });
    document.addEventListener('click', function (e) { if (!cPop.hidden && !cPop.contains(e.target)) { cPop.hidden = true; cBtn.setAttribute('aria-expanded', 'false'); } });
  }
  var en = $('[data-en]'), toast = $('[data-toast]'), tt = 0;
  if (en && toast) en.addEventListener('click', function () { toast.textContent = 'English version: coming soon · version anglaise bientôt'; toast.hidden = false; clearTimeout(tt); tt = setTimeout(function () { toast.hidden = true; }, 2600); });

  /* ---------- reveals: always painted on phones; IO + failsafe on desktop ---------- */
  var items = $$('[data-reveal]');
  if (reduce || !desktop.matches || !('IntersectionObserver' in window)) items.forEach(function (el) { el.classList.add('is-in'); });
  else {
    var io = new IntersectionObserver(function (es) { es.forEach(function (en2) { if (en2.isIntersecting) { en2.target.classList.add('is-in'); io.unobserve(en2.target); } }); }, { threshold: 0.01, rootMargin: '0px 0px 8% 0px' });
    items.forEach(function (el) { io.observe(el); });
    setTimeout(function () { items.forEach(function (el) { el.classList.add('is-in'); }); }, 2500);
  }

  /* ---------- motion math (card stack + drum) ---------- */
  var sectionProgress = function (rect, vh) { return clamp01(-rect.top / Math.max(rect.height - vh, 1)); };
  var activeIndex = function (p, n) { return n <= 1 ? 0 : Math.min(n - 1, Math.floor(clamp01(p) * n)); };
  function folioState(p, i, n) {
    var pos = clamp01(p) * Math.max(n - 1, 0), off = i - pos, dir = i % 2 === 0 ? 1 : -1;
    var exit = clamp01((-off - 0.08) / 0.82), depth = Math.max(0, Math.min(4, off));
    return { x: exit > 0 ? dir * 36 * exit : dir * depth * 2.8, y: exit > 0 ? -76 * exit : depth * 3.2, r: exit > 0 ? dir * 3.5 * exit : dir * depth * 0.8,
      s: exit > 0 ? 1 - 0.03 * exit : Math.max(0.9, 1 - depth * 0.028), c: exit > 0 ? clamp01(1 - exit * 5) : clamp01(1 - depth * 1.6), o: exit > 0 ? Math.max(0, 1 - exit * 1.6) : Math.max(0.58, 1 - depth * 0.1), z: n - i };
  }
  function drumState(p, i, n) {
    var x = Math.min(Math.max(n - 1, 0), clamp01(p) * n), fl = Math.floor(x), fr = x - fl, k = clamp01((fr - 0.6) / 0.4);
    var pos = Math.min(n - 1, fl + k * k * (3 - 2 * k)), off = i - pos;
    return { r: clamp(off * 62, -84, 84), y: clamp(off * 94, -130, 130), s: Math.max(0.78, 1 - Math.abs(off) * 0.12), o: Math.max(0, 1 - Math.abs(off) * 1.35) };
  }
  var folio = $('[data-folio]'), cards = folio ? $$('[data-card]', folio) : [], fIdx = $('[data-folio-idx]');
  var drum = $('[data-drum]'), dSteps = drum ? $$('[data-step]', drum) : [];
  var scheduled = false;
  function update() {
    scheduled = false;
    var vh = window.innerHeight;
    if (header) {
      var range = Math.max(document.documentElement.scrollHeight - vh, 1);
      header.classList.toggle('is-scrolled', window.scrollY > 48);
      header.style.setProperty('--page-progress', String(clamp01(window.scrollY / range)));
    }
    var motion = !reduce && desktop.matches;
    if (folio && cards.length) {
      var fp = sectionProgress(folio.getBoundingClientRect(), vh);
      cards.forEach(function (c, i) {
        if (!motion) { c.removeAttribute('style'); c.inert = false; return; }
        var s = folioState(fp, i, cards.length);
        c.style.setProperty('--fx', s.x + '%'); c.style.setProperty('--fy', s.y + '%'); 
        c.style.setProperty('--fs', String(s.s)); c.style.setProperty('--fo', String(s.o)); c.style.setProperty('--fc', String(s.c)); c.style.zIndex = String(s.z); c.style.visibility = s.o < 0.02 ? 'hidden' : '';
        c.inert = Math.abs(i - fp * (cards.length - 1)) > 0.5;
      });
      if (fIdx) fIdx.textContent = '0' + (Math.round(fp * (cards.length - 1)) + 1);
    }
    if (drum && dSteps.length) {
      var dp = sectionProgress(drum.getBoundingClientRect(), vh);
      drum.style.setProperty('--approach-progress', String(dp));
      dSteps.forEach(function (li, i) {
        if (!motion) { li.removeAttribute('style'); return; }
        var s = drumState(dp, i, dSteps.length);
        li.style.setProperty('--dr', s.r + 'deg'); li.style.setProperty('--dy', s.y + '%'); li.style.setProperty('--ds', String(s.s)); li.style.setProperty('--do', String(s.o));
        li.classList.toggle('is-on', i === activeIndex(dp, dSteps.length));
      });
    }
  }
  function schedule() { if (scheduled) return; scheduled = true; requestAnimationFrame(update); }
  window.addEventListener('scroll', schedule, { passive: true });
  window.addEventListener('resize', schedule);
  update();

  /* ---------- congress catalogue (C02) ---------- */
  var MONTHS = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.'];
  var pd = function (s) { var a = s.split('-'); return { y: +a[0], m: +a[1], d: +a[2] }; };
  var fmtRange = function (a, b) { var x = pd(a), y = pd(b); return x.m === y.m ? x.d + '–' + y.d + ' ' + MONTHS[x.m - 1] + ' ' + x.y : x.d + ' ' + MONTHS[x.m - 1] + ' – ' + y.d + ' ' + MONTHS[y.m - 1] + ' ' + y.y; };
  var frDate = function (s, delta) { var x = pd(s), dt = new Date(Date.UTC(x.y, x.m - 1, x.d + delta)); return dt.toLocaleDateString('fr-FR', { timeZone: 'UTC', day: '2-digit', month: '2-digit', year: 'numeric' }); };
  var list = $('[data-rows]'), filt = $('[data-filters]'), empty = $('[data-empty]'), pager = $('[data-pager]'), countL = $('[data-count-label]');
  var rows = list ? $$('.row', list) : [], PER = 6, page = 1;
  rows.forEach(function (r) { var d = $('.row__date', r), x = pd(r.dataset.start); if (d) d.textContent = fmtRange(r.dataset.start, r.dataset.end); r.dataset.q = String(Math.floor((x.m - 1) / 3) + 1); });
  rows.sort(function (a, b) { return a.dataset.start < b.dataset.start ? -1 : a.dataset.start > b.dataset.start ? 1 : 0; });
  rows.forEach(function (r) { list.appendChild(r); });
  var norm = function (s) { s = (s || '').toLowerCase(); return s.normalize ? s.normalize('NFD').replace(/[\u0300-\u036f]/g, '') : s; };
  function fill(sel, key) { if (!sel) return; var seen = {}; rows.map(function (r) { return r.dataset[key]; }).sort(function (a, b) { return a.localeCompare(b, 'fr'); }).forEach(function (v) { if (seen[v]) return; seen[v] = 1; var o = document.createElement('option'); o.value = v; o.textContent = v; sel.appendChild(o); }); }
  function apply() {
    if (!filt) return;
    var el = filt.elements, q = norm(el.q.value.trim()), dsc = el.disc.value, ct = el.country.value, per = el.per.value;
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
    fill(filt.elements.disc, 'disc'); fill(filt.elements.country, 'country');
    filt.addEventListener('input', function () { page = 1; apply(); });
    filt.addEventListener('change', function () { page = 1; apply(); });
    filt.addEventListener('submit', function (e) { e.preventDefault(); });
    filt.addEventListener('reset', function () { setTimeout(function () { page = 1; apply(); }, 0); });
    apply();
  }

  /* ---------- forms ---------- */
  function okMsg(form, msg) { var ok = $('[data-ok]', form); if (!ok) return; ok.textContent = msg; ok.hidden = false; ok.scrollIntoView({ block: 'nearest' }); }
  function valid(form) {
    var ctrls = $$('input,select,textarea', form).filter(function (c) { return !c.closest('[hidden]'); });
    for (var i = 0; i < ctrls.length; i++) { if (!ctrls[i].checkValidity()) { ctrls[i].reportValidity(); return false; } }
    return true;
  }

  /* listing dialog + prefilled flight quote (F03) */
  var dlg = $('[data-listing]'), f03 = $('[data-form="f03"]'), opener = null, curRow = null;
  function openListing(r, btn) {
    if (!dlg || !r) return; curRow = r; opener = btn || null;
    var t = $('.row__t', r).textContent, set = function (s, v) { var el = $(s, dlg); if (el) el.textContent = v; };
    set('[data-l-title]', t); set('[data-l-dates]', fmtRange(r.dataset.start, r.dataset.end)); set('[data-l-place]', r.dataset.city + ', ' + r.dataset.country); set('[data-l-disc]', r.dataset.disc); set('[data-l-id]', r.dataset.id);
    if (f03) {
      f03.reset(); var ok = $('[data-ok]', f03); if (ok) ok.hidden = true;
      var e = f03.elements; e.event.value = t + ' (' + r.dataset.id + ')'; e.to.value = r.dataset.city + ', ' + r.dataset.country;
      e.out.value = frDate(r.dataset.start, -1); e.back.value = frDate(r.dataset.end, 1);
    }
    if (typeof dlg.showModal === 'function') dlg.showModal(); else dlg.setAttribute('open', '');
  }
  function closeListing() { if (!dlg) return; if (dlg.open && typeof dlg.close === 'function') dlg.close(); else dlg.removeAttribute('open'); if (opener) opener.focus(); }
  rows.forEach(function (r) { var b = $('[data-open]', r); if (b) b.addEventListener('click', function () { openListing(r, b); }); });
  var dc = dlg && $('[data-close]', dlg); if (dc) dc.addEventListener('click', closeListing);
  if (dlg) dlg.addEventListener('click', function (e) { if (e.target === dlg) closeListing(); });
  if (f03) f03.addEventListener('submit', function (e) {
    e.preventDefault(); if (!valid(f03)) return;
    var el = f03.elements, n = +el.pax.value;
    okMsg(f03, 'Demande enregistrée (maquette) — ' + (curRow ? curRow.dataset.id : '') + ' · départ ' + el.from.value + ' le ' + el.out.value + ' · ' + n + (n > 1 ? ' voyageurs' : ' voyageur') + ' · ' + el.cls.value + '. Rien n’a été envoyé ; en production, la demande est liée au congrès, enregistrée et notifiée à l’équipe, qui émet le devis.');
  });

  /* contact: three journeys (F01 / F02 / congrès) */
  var cf = $('[data-form="contact"]');
  if (cf) {
    var parts = $$('[data-part]', cf), recap = $('[data-recap]', cf), needSel = $('[data-need-select]', cf);
    var setJourney = function (j) {
      $$('[data-j]', cf).forEach(function (r) { r.checked = r.value === j; });
      parts.forEach(function (p) { p.hidden = p.dataset.part !== j; });
      var co = cf.elements.company; if (co) co.required = j === 'entreprise';
      var pax = cf.elements.pax; if (pax) pax.required = j === 'evenement';
      var ok = $('[data-ok]', cf); if (ok) ok.hidden = true;
      sumUp();
    };
    var sumUp = function () {
      if (!recap) return; var e = cf.elements;
      recap.textContent = 'Récapitulatif : ' + e.etype.value + ' · ' + (e.dest.value || 'destination à définir') + ' · ' + (e.when.value || 'dates souples') + ' · ' + (e.pax.value || '?') + ' participants' + (e.svc.value ? ' · ' + e.svc.value : '') + '.';
    };
    $$('[data-j]', cf).forEach(function (r) { r.addEventListener('change', function () { setJourney(r.value); }); });
    cf.addEventListener('input', sumUp);
    $$('[data-journey]').forEach(function (a) {
      a.addEventListener('click', function () {
        setJourney(a.dataset.journey); if (a.dataset.need && needSel) needSel.value = a.dataset.need;
        if (a.hasAttribute('data-search')) { var gq = $('#q'), gn = $('#g-name'); if (gn) { if (gq && gq.value.trim()) gn.value = gq.value.trim(); setTimeout(function () { gn.focus({ preventScroll: true }); }, 700); } }
      });
    });
    cf.addEventListener('submit', function (e) {
      e.preventDefault(); if (!valid(cf)) return;
      var j = ($$('[data-j]', cf).filter(function (r) { return r.checked; })[0] || {}).value;
      var lbl = { entreprise: 'Voyages d’affaires', evenement: 'MICE', congres: 'Congrès' }[j] || '';
      okMsg(cf, 'Merci, ' + cf.elements.name.value + '. Demande « ' + lbl + ' » enregistrée (maquette) : rien n’a été envoyé. En production, elle est enregistrée, routée vers l’équipe concernée et confirmée par un accusé de réception.');
    });
    setJourney('entreprise');
  }
}());
