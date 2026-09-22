'use strict';
/* Jobs board: instant client-side filtering with all state in the URL, list /
   map / saved views, mobile filter sheet and the command palette (Ctrl/⌘+K).
   The "Your fit" panel below the list lives in fit.js. */
(function () {
  var G = window.GJ, doc = document, $ = function (s, c) { return (c || doc).querySelector(s); };
  var $$ = function (s, c) { return Array.prototype.slice.call((c || doc).querySelectorAll(s)); };
  var board = $('[data-board]');
  if (!board) return;
  var data = JSON.parse($('#gj-data').textContent), jobs = data.jobs, ROOT = doc.body.getAttribute('data-root') || '';
  var st = G.parseState(window.location.search), view = st.view || 'list';
  var list = $('[data-list]'), count = $('[data-count]'), chips = $('[data-chips]'), rail = $('[data-rail]'), railHome = rail.parentNode;
  var mapWrap = $('[data-jobs-map]'), mapList = $('[data-map-list]'), mapSvg = mapWrap ? $('svg', mapWrap) : null;
  var f = { q: $('#f-q'), loc: $('#f-loc'), sector: $('#f-sector'), type: $('#f-type'), sal: $('#f-sal'), sort: $('#f-sort') };
  var LABEL = { q: 'Search', loc: 'Where', sector: 'Sector', type: 'Type', sal: 'Salary disclosed' };
  var mapPick = '';
  var ON_MAP = {};
  (data.regions || []).forEach(function (r) { ON_MAP[r.name] = true; });

  function logo(j) {
    return j.logo ? '<img class="role__logo" src="' + ROOT + 'assets/logos/' + G.esc(j.logo) + '" alt="" width="' + (j.lw || 200) + '" height="' + (j.lh || 80) + '" loading="lazy">'
      : '<div class="role__logo role__logo--t" aria-hidden="true">' + G.esc((j.employer || '?').charAt(0)) + '</div>';
  }
  /* Highlight on the plain string, escape each piece afterwards, so a match
     can never land inside an HTML entity (e.g. "amp" in "&amp;"). */
  function hl(text, q) {
    var words = G.tokens(q || '').map(function (w) { return w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }).filter(Boolean);
    if (!words.length) return G.esc(text);
    return String(text == null ? '' : text).split(new RegExp('(' + words.join('|') + ')', 'ig')).map(function (piece, i) {
      return i % 2 ? '<mark>' + G.esc(piece) + '</mark>' : G.esc(piece);
    }).join('');
  }
  function row(j, q) {
    var sal = G.salaryLabel(j);
    return '<article class="row" data-id="' + G.esc(j.id) + '">' + logo(j) +
      '<div class="row__body"><h3><a href="' + G.esc(j.href) + '">' + hl(j.title, q) + '</a></h3>' +
      '<div class="row__meta"><span>' + G.esc(j.employer) + '</span><span aria-hidden="true">·</span><span>' + G.esc(j.location) + '</span>' +
      (sal ? '<span class="tag tag--sal">' + G.esc(sal) + '</span>' : '') + (j.sectors[0] ? '<span class="tag"><i style="background:' + G.esc(j.color || '') + '"></i>' + G.esc(j.sectors[0]) + '</span>' : '') + '</div></div>' +
      '<div class="row__r"><time datetime="' + G.esc(j.posted || '') + '">' + G.esc(G.ago(j.posted)) + '</time><span>' + G.esc(j.type || '') + '</span></div>' +
      '<button class="save" type="button" data-save="' + G.esc(j.id) + '" data-title="' + G.esc(j.title) + '" aria-pressed="false" aria-label="Save: ' + G.esc(j.title) + '"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 3h12v18l-6-4-6 4z"/></svg></button></article>';
  }
  function readForm() {
    st = { q: f.q.value.trim(), loc: f.loc.value.trim(), sector: f.sector.value, type: f.type.value, sal: f.sal.checked ? '1' : '', sort: f.sort.value, view: view };
  }
  function writeForm() {
    f.q.value = st.q || ''; f.loc.value = st.loc || ''; f.sector.value = st.sector || ''; f.type.value = st.type || '';
    f.sal.checked = !!st.sal; f.sort.value = st.sort || 'newest';
    if (f.sector.value !== (st.sector || '')) f.sector.value = '';
  }
  function sync() {
    var qs = G.toQuery(st);
    history.replaceState(null, '', window.location.pathname + qs + window.location.hash);
  }
  function paintChips() {
    chips.innerHTML = ['q', 'loc', 'sector', 'type', 'sal'].filter(function (k) { return st[k]; }).map(function (k) {
      return '<span class="chip">' + G.esc(LABEL[k]) + (k === 'sal' ? '' : ': ' + G.esc(st[k])) + '<button type="button" data-clear="' + k + '" aria-label="Remove ' + G.esc(LABEL[k]) + ' filter">×</button></span>';
    }).join('');
  }
  function empty(msg) {
    var pop = data.sectors.slice(0, 4).map(function (s) { return '<button class="btn btn--sm btn--ghost" type="button" data-set="sector" data-v="' + G.esc(s.name) + '">' + G.esc(s.name) + ' · ' + s.n + '</button>'; }).join('');
    return '<div class="empty"><h3>' + msg + '</h3><p>Try a broader search, another region, or one of the busiest sectors right now.</p><div class="sugg"><button class="btn btn--sm btn--lime" type="button" data-reset>Clear all filters</button>' + pop + '</div></div>';
  }
  function render() {
    var res = G.filterJobs(jobs, st), ids = window.GJSaved.list();
    $$('[data-view]').forEach(function (b) { b.setAttribute('aria-selected', b.getAttribute('data-view') === view ? 'true' : 'false'); });
    paintChips();
    if (view === 'saved') {
      var sv = G.sortJobs(jobs.filter(function (j) { return ids.indexOf(j.id) >= 0; }), st.sort);
      list.innerHTML = sv.length ? sv.map(function (j) { return row(j, ''); }).join('') : '<div class="empty"><h3>Nothing saved yet</h3><p>Tap the bookmark on any role and it will wait for you here, on this device.</p></div>';
      count.innerHTML = '<b>' + sv.length + '</b> saved <small>on this device</small>';
      list.hidden = false; if (mapWrap) mapWrap.hidden = true;
    } else if (view === 'map' && mapSvg) {
      var counts = {};
      res.forEach(function (j) { (j.regions || []).forEach(function (r) { counts[r] = (counts[r] || 0) + 1; }); });
      window.GJMap(mapSvg, counts, function (name) { mapPick = mapPick === name ? '' : name; render(); });
      $$('.gmap__r', mapSvg).forEach(function (g) { g.classList.toggle('is-on', g.getAttribute('data-region') === mapPick); });
      var sub = mapPick ? res.filter(function (j) { return (j.regions || []).indexOf(mapPick) >= 0; }) : res;
      var off = {};
      res.forEach(function (j) { if (!(j.regions || []).some(function (r) { return ON_MAP[r]; })) (j.regions || []).forEach(function (r) { off[r] = (off[r] || 0) + 1; }); });
      var offHtml = Object.keys(off).length ? ' Not on the map: ' + Object.keys(off).map(function (r) { return '<a href="' + G.esc(G.toQuery({ loc: r, q: st.q, sector: st.sector, type: st.type, sal: st.sal, sort: st.sort })) + '">' + G.esc(r) + ' (' + off[r] + ')</a>'; }).join(', ') + '.' : '';
      mapList.innerHTML = '<p class="muted" style="font-size:.9rem">' + (mapPick ? '<b>' + G.esc(mapPick) + '</b> · ' + sub.length + (sub.length === 1 ? ' role' : ' roles') + ' <button class="btn btn--sm btn--ghost" type="button" data-mapclear>Show all</button>' : 'Tap a region to filter. ' + (res.length - Object.keys(off).reduce(function (a, r) { return a + off[r]; }, 0)) + ' of ' + res.length + ' roles sit in ' + Object.keys(counts).filter(function (r) { return ON_MAP[r]; }).length + ' mapped regions.' + offHtml) + '</p>' + sub.slice(0, 40).map(function (j) { return row(j, st.q); }).join('');
      count.innerHTML = '<b>' + res.length + '</b> ' + (res.length === 1 ? 'role' : 'roles') + ' <small>on the map</small>';
      list.hidden = true; mapWrap.hidden = false;
    } else {
      list.innerHTML = res.length ? res.map(function (j) { return row(j, st.q); }).join('') : empty('No roles match');
      count.innerHTML = '<b>' + res.length + '</b> ' + (res.length === 1 ? 'role' : 'roles') + (res.length !== jobs.length ? ' <small>of ' + jobs.length + '</small>' : ' <small>live</small>');
      list.hidden = false; if (mapWrap) mapWrap.hidden = true;
    }
    window.GJSaved.paint(board);
    sync();
  }
  function set(k, v) { st[k] = v; writeForm(); render(); }
  Object.keys(f).forEach(function (k) {
    var ev = k === 'q' || k === 'loc' ? 'input' : 'change', t;
    f[k].addEventListener(ev, function () { clearTimeout(t); t = setTimeout(function () { readForm(); render(); }, ev === 'input' ? 120 : 0); });
  });
  $('[data-filters]').addEventListener('submit', function (e) { e.preventDefault(); readForm(); render(); });
  board.addEventListener('click', function (e) {
    var b = e.target.closest('[data-clear],[data-reset],[data-set],[data-view],[data-mapclear]');
    if (!b) return;
    if (b.hasAttribute('data-clear')) set(b.getAttribute('data-clear'), '');
    else if (b.hasAttribute('data-reset')) { st = { sort: st.sort, view: view }; writeForm(); render(); }
    else if (b.hasAttribute('data-set')) set(b.getAttribute('data-set'), b.getAttribute('data-v'));
    else if (b.hasAttribute('data-mapclear')) { mapPick = ''; render(); }
    else { view = b.getAttribute('data-view'); st.view = view; render(); }
  });
  $$('[data-reset]', rail).forEach(function (b) { b.addEventListener('click', function () { st = { sort: st.sort, view: view }; writeForm(); render(); }); });
  doc.addEventListener('gj:saved', function () { if (view === 'saved') render(); else window.GJSaved.paint(board); });

  /* ---- mobile filter sheet: the one rail node moves into the dialog and back */
  var sheet = $('[data-sheet]'), sheetSlot = $('[data-sheet-slot]');
  $$('[data-sheet-open]').forEach(function (b) { b.addEventListener('click', function () { sheetSlot.appendChild(rail); rail.classList.add('rail--sheet'); sheet.showModal(); }); });
  function closeSheet() { railHome.appendChild(rail); rail.classList.remove('rail--sheet'); }
  if (sheet) {
    sheet.addEventListener('close', closeSheet);
    sheet.addEventListener('click', function (e) { if (e.target === sheet) sheet.close(); });
    $$('[data-sheet-close]', sheet).forEach(function (b) { b.addEventListener('click', function () { sheet.close(); }); });
    window.matchMedia('(min-width:1024px)').addEventListener('change', function (m) { if (m.matches && sheet.open) sheet.close(); });
  }

  /* ---- command palette */
  var pal = $('[data-palette]'), pin = $('input', pal), plist = $('[role="listbox"]', pal), pitems = [], psel = 0;
  var pages = [];
  try { pages = JSON.parse(pal.getAttribute('data-pages') || '[]'); } catch (e) { pages = []; }
  function pquery(q) {
    var w = G.norm(q), out = [];
    if (!w) { out = pages.map(function (p) { return { k: 'page', t: p.t, href: p.h }; }).concat(data.sectors.slice(0, 5).map(function (s) { return { k: 'sector', t: s.name, sub: s.n + ' roles', sector: s.name }; })); }
    else {
      pages.forEach(function (p) { if (G.norm(p.t).indexOf(w) >= 0) out.push({ k: 'page', t: p.t, href: p.h }); });
      data.sectors.forEach(function (s) { if (G.norm(s.name).indexOf(w) >= 0) out.push({ k: 'sector', t: s.name, sub: s.n + ' roles', sector: s.name }); });
      jobs.forEach(function (j) { if (out.length < 14 && G.haystack(j).indexOf(w) >= 0) out.push({ k: 'role', t: j.title, sub: j.employer + ' · ' + j.location, href: j.href }); });
    }
    return out.slice(0, 14);
  }
  function ppaint() {
    plist.innerHTML = pitems.length ? pitems.map(function (it, i) {
      return '<div role="option" id="po-' + i + '" aria-selected="' + (i === psel) + '" data-i="' + i + '"><span class="k">' + it.k + '</span><span>' + G.esc(it.t) + '</span>' + (it.sub ? '<small>' + G.esc(it.sub) + '</small>' : '') + '</div>';
    }).join('') : '<div role="option" aria-selected="false"><span class="k">—</span>No matches</div>';
    pin.setAttribute('aria-activedescendant', 'po-' + psel);
  }
  function pgo(it) {
    if (!it) return;
    pal.close();
    if (it.href) window.location.href = it.href; else if (it.sector) { view = 'list'; set('sector', it.sector); }
  }
  function popen() { pin.value = ''; pitems = pquery(''); psel = 0; ppaint(); pal.showModal(); pin.focus(); }
  $$('[data-palette-open]').forEach(function (b) { b.addEventListener('click', popen); });
  doc.addEventListener('keydown', function (e) {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); if (pal.open) pal.close(); else popen(); }
  });
  pin.addEventListener('input', function () { pitems = pquery(pin.value); psel = 0; ppaint(); });
  pin.addEventListener('keydown', function (e) {
    if (!pitems.length) { if (e.key === 'Enter') e.preventDefault(); return; }
    if (e.key === 'ArrowDown') { psel = Math.min(pitems.length - 1, psel + 1); ppaint(); e.preventDefault(); }
    else if (e.key === 'ArrowUp') { psel = Math.max(0, psel - 1); ppaint(); e.preventDefault(); }
    else if (e.key === 'Enter') { e.preventDefault(); pgo(pitems[psel]); }
  });
  plist.addEventListener('click', function (e) { var o = e.target.closest('[data-i]'); if (o) pgo(pitems[+o.getAttribute('data-i')]); });
  pal.addEventListener('click', function (e) { if (e.target === pal) pal.close(); });

  /* ---- Ask GreenJobs: local smart match */
  writeForm();
  render();
})();
