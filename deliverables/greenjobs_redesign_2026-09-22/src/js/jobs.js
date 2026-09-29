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
  var f = { q: $('#f-q'), loc: $('#f-loc'), sector: $('#f-sector'), type: $('#f-type'), sal: $('#f-sal'), wp: $('#f-wp'), level: $('#f-level'), ct: $('#f-ct'),
    smin: $('#f-smin'), smax: $('#f-smax'), only: $('#f-only'), close: $('#f-close'), emp: $('#f-emp'), sort: $('#f-sort') };
  var CUR = data.currency || 'EUR', OPTS = { cur: CUR, home: data.home || ['ie', 'cross', 'remote'] };
  var LABEL = { q: 'Search', loc: 'Where', sector: 'Sector', type: 'Type', sal: 'Salary disclosed', wp: 'Workplace', level: 'Level', ct: 'Contract', smin: 'Min salary', smax: 'Max salary',
    only: data.edition === 'uk' ? 'Hide Ireland/abroad-only roles' : 'Hide UK/abroad-only roles', close: 'Closing', emp: 'Advertised by' };
  var CHIP_KEYS = ['q', 'loc', 'sector', 'type', 'sal', 'wp', 'level', 'ct', 'smin', 'smax', 'only', 'close', 'emp'];
  function optText(sel, v) {
    var opts = sel ? Array.prototype.slice.call(sel.options) : [], hit = opts.filter(function (o) { return o.value === String(v); })[0];
    return hit ? hit.textContent : String(v);
  }
  function chipText(k) {
    if (k === 'sal' || k === 'only') return '';
    if (k === 'smin' || k === 'smax') return ': ' + G.money(parseFloat(st[k]), CUR);
    if (k === 'wp' || k === 'level' || k === 'ct' || k === 'close' || k === 'emp') return ': ' + optText(f[k], st[k]);
    return ': ' + st[k];
  }
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
  var TODAY = Date.parse(data.today || '') || Date.now();
  function isClosed(j) { var t = j.closing ? Date.parse(j.closing) : NaN; return !isNaN(t) && t + 864e5 <= TODAY; }
  var CUR_SYM = { euros: '\u20ac', sterling: '\u00a3', pounds: '\u00a3', EUR: '\u20ac', GBP: '\u00a3' };
  /* "€5.1k–6k/mo (advertised in euros, about £4.4k–5.1k/mo)" -> the salary chip plus a muted "advertised in €" chip
     (the currency glyph sits in the dot slot so every chip shares one anatomy). */
  function salChips(sal) {
    var m = /^(.*) \((?:paid|advertised) in ([^,]+), about (.+)\)$/.exec(sal || '');
    if (!m) return sal ? '<span class="tag tag--sal"><span class="tag__t">' + G.esc(sal) + '</span></span>' : '';
    var sym = CUR_SYM[m[2]] || m[2];
    return '<span class="tag tag--sal"><span class="tag__t">' + G.esc(m[1]) + '</span></span><span class="tag tag--fx" title="' + G.esc('Advertised in ' + m[2] + ', about ' + m[3]) + '"><b class="tag__cur" aria-hidden="true">' + G.esc(sym) + '</b><span class="tag__t">advertised in ' + G.esc(m[2]) + ' <s>\u2248 ' + G.esc(m[3]) + '</s></span></span>';
  }
  /* onMap: the map side list shows the location badge and one full sector chip (it may wrap), no salary or level chips. */
  function row(j, q, onMap) {
    var sal = G.salaryLabel(j, CUR), lc = G.locLabel(j.loc_class), closed = isClosed(j);
    var sec = sect0(j) ? '<span class="tag tag--sec"><i style="background:' + G.esc(j.color || '') + '"></i><span class="tag__t">' + G.esc(sect0(j)) + '</span></span>' : '';
    return '<article class="row' + (closed ? ' row--closed' : '') + '" data-id="' + G.esc(j.id) + '">' + logo(j) +
      '<div class="row__body"><h3><a href="' + G.esc(j.href) + '">' + hl(j.title, q) + '</a></h3>' +
      '<div class="row__meta"><span class="row__emp">' + G.esc(j.employer) + '</span><span><span class="row__sep" aria-hidden="true">· </span>' + G.esc(j.location) + '</span>' +
      (closed ? '<span class="tag tag--closed">Closed</span>' : '') + (onMap ? '' : salChips(sal)) + (lc ? '<span class="tag tag--loc" data-loc="' + G.esc(j.loc_class) + '">' + G.esc(lc) + '</span>' : '') + sec + (j.level && !onMap ? '<span class="tag tag--lvl" title="Career level">' + G.esc(j.level) + '</span>' : '') + '</div>' +
      (j.unverified_cur ? '<p class="role__note">Salary as listed on greenjobs.ie; the advertiser may pay in sterling.</p>' : '') + '</div>' +
      '<div class="row__r"><time datetime="' + G.esc(j.posted || '') + '">' + G.esc(G.ago(j.posted)) + '</time><span>' + G.esc(j.type || '') + '</span></div>' +
      '<button class="save" type="button" data-save="' + G.esc(j.id) + '" data-title="' + G.esc(j.title) + '" aria-pressed="false" aria-label="Save: ' + G.esc(j.title) + '"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 3h12v18l-6-4-6 4z"/></svg></button></article>';
  }
  function val(k) { return f[k] ? f[k].value : ''; }
  function readForm() {
    st = { q: f.q.value.trim(), loc: f.loc.value.trim(), sector: f.sector.value, type: f.type.value, sal: f.sal.checked ? '1' : '', sort: f.sort.value, view: view,
      wp: val('wp'), level: val('level'), ct: val('ct'), smin: val('smin').trim(), smax: val('smax').trim(), only: f.only && f.only.checked ? '1' : '', close: val('close'), emp: val('emp') };
  }
  function writeForm() {
    f.q.value = st.q || ''; f.loc.value = st.loc || ''; f.sector.value = st.sector || ''; f.type.value = st.type || '';
    f.sal.checked = !!st.sal; f.sort.value = st.sort || 'newest';
    if (f.sector.value !== (st.sector || '')) f.sector.value = '';
    f.sector.title = f.sector.value ? optText(f.sector, f.sector.value) : '';
    ['wp', 'level', 'ct', 'close', 'emp', 'smin', 'smax'].forEach(function (k) {
      if (!f[k]) return;
      f[k].value = st[k] || '';
      if (f[k].tagName === 'SELECT' && f[k].value !== (st[k] || '')) { f[k].value = ''; st[k] = ''; }
    });
    if (f.only) f.only.checked = !!st.only;
  }
  function sync() {
    var qs = G.toQuery(st);
    history.replaceState(null, '', window.location.pathname + qs + window.location.hash);
  }
  function paintChips() {
    chips.innerHTML = CHIP_KEYS.filter(function (k) { return st[k]; }).map(function (k) {
      return '<span class="chip">' + G.esc(LABEL[k]) + G.esc(chipText(k)) + '<button type="button" data-clear="' + k + '" aria-label="Remove ' + G.esc(LABEL[k]) + ' filter">×</button></span>';
    }).join('');
  }
  /* lib.orderSectors puts the active filter's sector first on the card chip (visual 23);
     lib.suggestSectors offers only sectors that still yield a role under the other facets (visual 22). */
  function sect0(j) { return (G.orderSectors ? G.orderSectors(j, st.sector) : j.sectors)[0]; }
  function empty(msg) {
    var pop = (G.suggestSectors ? G.suggestSectors(data.jobs, st) : data.sectors.slice(0, 4)).map(function (s) { return '<button class="btn btn--sm btn--ghost" type="button" data-set="sector" data-v="' + G.esc(s.name) + '">' + G.esc(s.name) + ' · ' + s.n + '</button>'; }).join('');
    return '<div class="empty"><h3>' + msg + '</h3><p>Try a broader search, another region, or one of the busiest sectors right now.</p><div class="sugg"><button class="btn btn--sm btn--lime" type="button" data-reset>Clear all filters</button>' + pop + '</div></div>';
  }
  function render() {
    var res = G.filterJobs(jobs, st, OPTS), ids = window.GJSaved.list();
    $$('[data-view]').forEach(function (b) { b.setAttribute('aria-selected', b.getAttribute('data-view') === view ? 'true' : 'false'); });
    paintChips();
    if (view === 'saved') {
      var sv = G.sortJobs(jobs.filter(function (j) { return ids.indexOf(j.id) >= 0; }), st.sort, CUR);
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
      var offHtml = Object.keys(off).length ? ' Not on the map: ' + Object.keys(off).map(function (r) { return '<a href="' + G.esc(G.toQuery(Object.assign({}, st, { loc: r, view: '' }))) + '">' + G.esc(r) + ' (' + off[r] + ')</a>'; }).join(', ') + '.' : '';
      mapList.innerHTML = '<p class="muted" style="font-size:.9rem">' + (mapPick ? '<b>' + G.esc(mapPick) + '</b> · ' + sub.length + (sub.length === 1 ? ' role' : ' roles') + ' <button class="btn btn--sm btn--ghost" type="button" data-mapclear>Show all</button>' : 'Tap a region to filter. ' + (res.length - Object.keys(off).reduce(function (a, r) { return a + off[r]; }, 0)) + ' of ' + res.length + ' roles sit in ' + Object.keys(counts).filter(function (r) { return ON_MAP[r]; }).length + ' mapped regions.' + offHtml) + '</p>' + sub.slice(0, 40).map(function (j) { return row(j, st.q, true); }).join('');
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
    if (!f[k]) return;
    var ev = k === 'q' || k === 'loc' || k === 'smin' || k === 'smax' ? 'input' : 'change', t;
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
