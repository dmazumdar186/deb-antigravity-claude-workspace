'use strict';
/* Progressive enhancement over the server-rendered roles list: every row is
   already in the HTML, this only hides the ones that do not match. Without
   JS the full list is still there and the filter bar is hidden by CSS. */

(function initJobs() {
  var list = document.querySelector('[data-joblist]');
  if (!list) return;
  var rows = Array.prototype.slice.call(list.querySelectorAll('[data-job]'));
  var q = document.getElementById('f-q');
  var loc = document.getElementById('f-location');
  var sec = document.getElementById('f-sector');
  var typ = document.getElementById('f-type');
  var count = document.querySelector('[data-count]');
  var empty = document.querySelector('[data-empty]');
  var clear = document.querySelector('[data-clear]');
  var total = rows.length;

  var norm = function (s) { return (s || '').toString().toLowerCase().trim(); };

  function fromQuery() {
    var params = new URLSearchParams(window.location.search);
    var set = function (el, key) {
      if (!el) return;
      var v = params.get(key);
      if (!v) return;
      var want = norm(v);
      if (el.tagName === 'SELECT') {
        for (var i = 0; i < el.options.length; i += 1) {
          if (norm(el.options[i].value) === want) { el.selectedIndex = i; return; }
        }
      } else {
        el.value = v;
      }
    };
    set(q, 'q');
    set(loc, 'location');
    set(sec, 'sector');
    set(typ, 'type');
  }

  function toQuery() {
    var params = new URLSearchParams();
    if (q && q.value.trim()) params.set('q', q.value.trim());
    if (loc && loc.value) params.set('location', loc.value);
    if (sec && sec.value) params.set('sector', sec.value);
    if (typ && typ.value) params.set('type', typ.value);
    var s = params.toString();
    if (window.history && window.history.replaceState) {
      window.history.replaceState(null, '', s ? '?' + s : window.location.pathname);
    }
  }

  function apply() {
    var text = norm(q && q.value);
    var wl = norm(loc && loc.value);
    var ws = norm(sec && sec.value);
    var wt = norm(typ && typ.value);
    var shown = 0;
    for (var i = 0; i < rows.length; i += 1) {
      var row = rows[i];
      var d = row.dataset;
      var ok = (!wl || norm(d.location) === wl)
        && (!ws || norm(d.sector) === ws)
        && (!wt || norm(d.type) === wt)
        && (!text || norm(d.search).indexOf(text) !== -1);
      row.hidden = !ok;
      if (ok) shown += 1;
    }
    if (count) {
      count.innerHTML = shown === total
        ? 'Showing all <b>' + total + '</b> live roles.'
        : 'Showing <b>' + shown + '</b> of ' + total + ' live roles.';
    }
    if (empty) empty.classList.toggle('is-on', shown === 0);
    toQuery();
  }

  [q, loc, sec, typ].forEach(function (el) {
    if (!el) return;
    el.addEventListener('input', apply);
    el.addEventListener('change', apply);
  });
  if (clear) {
    clear.addEventListener('click', function () {
      if (q) q.value = '';
      [loc, sec, typ].forEach(function (el) { if (el) el.selectedIndex = 0; });
      apply();
      if (q) q.focus();
    });
  }

  fromQuery();
  apply();
}());
