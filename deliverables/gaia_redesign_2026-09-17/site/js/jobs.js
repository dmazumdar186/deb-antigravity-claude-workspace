'use strict';
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
var clears = Array.prototype.slice.call(document.querySelectorAll('[data-clear]'));
var total = rows.length;
var urlTimer = 0;
var norm = function (s) { return (s || '').toString().toLowerCase().trim(); };
var sectorsOf = function (row) { return norm(row.dataset.sector).split('|'); };
function fromQuery() {
var params = new URLSearchParams(window.location.search);
var spill = [];
var setSelect = function (el, key) {
if (!el) return;
var v = params.get(key);
if (!v) return;
var want = norm(v);
for (var i = 0; i < el.options.length; i += 1) {
if (norm(el.options[i].value) === want) { el.selectedIndex = i; return; }
}
spill.push(v);
};
setSelect(loc, 'location');
setSelect(sec, 'sector');
setSelect(typ, 'type');
if (q) {
var text = params.get('q') || '';
q.value = [text].concat(spill).filter(Boolean).join(' ').trim();
}
}
function syncUrl() {
window.clearTimeout(urlTimer);
urlTimer = window.setTimeout(function () {
if (!window.history || !window.history.replaceState) return;
var params = new URLSearchParams();
if (q && q.value.trim()) params.set('q', q.value.trim());
if (loc && loc.value) params.set('location', loc.value);
if (sec && sec.value) params.set('sector', sec.value);
if (typ && typ.value) params.set('type', typ.value);
var s = params.toString();
var hash = window.location.hash || '';
try {
window.history.replaceState(null, '', (s ? '?' + s : window.location.pathname) + hash);
} catch (err) {
if (window.console) window.console.warn('Could not update the address bar:', err);
}
}, 250);
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
&& (!ws || sectorsOf(row).indexOf(ws) !== -1)
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
syncUrl();
}
if (q) q.addEventListener('input', apply);
[loc, sec, typ].forEach(function (el) {
if (el) el.addEventListener('change', apply);
});
clears.forEach(function (btn) {
btn.addEventListener('click', function () {
if (q) q.value = '';
[loc, sec, typ].forEach(function (el) { if (el) el.selectedIndex = 0; });
apply();
if (q) q.focus();
});
});
fromQuery();
apply();
}());
