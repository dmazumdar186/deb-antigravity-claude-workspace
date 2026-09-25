'use strict';
(function () {
var G = window.GJ, C = window.GJCharts, doc = document, $ = function (s, c) { return (c || doc).querySelector(s); };
var dataEl = $('#gj-data');
if (!dataEl || !C) return;
var data = JSON.parse(dataEl.textContent), jobs = data.jobs, cur = data.currency || 'EUR';
var money = function (v) { return G.money(Math.round(v), cur); };
var tm = $('[data-treemap]');
if (tm) {
var items = data.sectors.filter(function (s) { return s.n > 0; }).map(function (s) { return { key: s.name, label: s.name, v: s.n, color: s.color, dark: s.dark }; });
var picked = '';
var svg = C.treemap(items, { label: 'Live roles by sector', height: 460, onPick: function (it) {
picked = picked === it.key ? '' : it.key;
Array.prototype.forEach.call(tm.querySelectorAll('.cell'), function (c) { c.classList.toggle('is-on', c.getAttribute('data-key') === picked); });
Array.prototype.forEach.call(doc.querySelectorAll('[data-secrow]'), function (r) {
var me = r.getAttribute('data-secrow') === picked;
r.classList.toggle('is-dim', !!picked && !me);
if (me) { r.open = true; r.scrollIntoView({ block: 'nearest', behavior: 'smooth' }); }
});
var n = $('[data-tm-note]'); if (n) n.textContent = picked ? 'Showing ' + picked + '. Press it again to clear.' : 'Tap a block to highlight that sector in the list below.';
} });
tm.appendChild(svg);
tm.parentNode.appendChild(C.table(['Sector', 'Live roles'], items.map(function (i) { return [i.label, String(i.v)]; })));
}
var ins = $('[data-insights]');
if (ins) {
var withSal = jobs.map(function (j) { var a = G.annual(j); return a ? { j: j, a: a } : null; }).filter(Boolean);
var mids = withSal.map(function (x) { return x.a.mid; });
var med = G.median(mids);
function stat(sel, v) { var e = $(sel, ins); if (e) e.textContent = v; }
stat('[data-s-n]', String(jobs.length)); stat('[data-s-disc]', Math.round(100 * withSal.length / Math.max(1, jobs.length)) + '%');
stat('[data-s-med]', med ? money(med) : 'n/a'); stat('[data-s-cnt]', String(withSal.length));
var edges = [20000, 30000, 40000, 50000, 60000, 75000, 100000];
var bins = G.histogram(mids, edges);
var f1 = $('[data-fig="hist"]', ins);
f1.appendChild(C.columns(bins, { label: 'Disclosed salaries by band' }));
f1.appendChild(C.table(['Band (' + cur + ')', 'Roles'], bins.map(function (b) { return [b.label, String(b.n)]; })));
var bySec = {};
withSal.forEach(function (x) { x.j.sectors.forEach(function (s) { (bySec[s] = bySec[s] || []).push(x.a.mid); }); });
var rows = Object.keys(bySec).filter(function (s) { return bySec[s].length >= 3; }).map(function (s) { return { label: s, v: G.median(bySec[s]), sub: bySec[s].length + ' disclosed' }; }).sort(function (a, b) { return b.v - a.v; });
var f2 = $('[data-fig="sector"]', ins);
if (rows.length) { f2.appendChild(C.bars(rows, { fmt: money, label: 'Median disclosed salary by sector', labelWidth: 200 })); f2.appendChild(C.table(['Sector', 'Median', 'Disclosed'], rows.map(function (r) { return [r.label, money(r.v), r.sub.split(' ')[0]]; }))); }
else f2.insertAdjacentHTML('beforeend', '<p class="note">Fewer than three disclosed salaries in any one sector this week, so no sector median is shown.</p>');
var disc = data.sectors.filter(function (s) { return s.n >= 3; }).map(function (s) {
var inS = jobs.filter(function (j) { return j.sectors.indexOf(s.name) >= 0; }), d = inS.filter(function (j) { return G.annual(j); }).length;
return { label: s.name, v: Math.round(100 * d / inS.length), sub: d + ' of ' + inS.length };
}).sort(function (a, b) { return b.v - a.v; });
var f3 = $('[data-fig="disc"]', ins);
f3.appendChild(C.bars(disc, { fmt: function (v) { return v + '%'; }, max: 100, label: 'Salary disclosure rate by sector', labelWidth: 200 }));
f3.appendChild(C.table(['Sector', 'Disclosed', 'Of'], disc.map(function (r) { return [r.label, r.v + '%', r.sub]; })));
var reg = data.regions.slice(0, 12).map(function (r) { return { label: r.name, v: r.n }; });
var f4 = $('[data-fig="region"]', ins);
f4.appendChild(C.bars(reg, { label: 'Live roles by region', labelWidth: 200, fmt: function (v) { return String(v); } }));
f4.appendChild(C.table([data.regionUnit || 'Region', 'Roles'], reg.map(function (r) { return [r.label, String(r.v)]; })));
var tabs = Array.prototype.slice.call(ins.querySelectorAll('[data-chart]'));
function showChart(k, focus) {
if (!tabs.some(function (t) { return t.getAttribute('data-chart') === k; })) k = 'band';
tabs.forEach(function (t) {
var on = t.getAttribute('data-chart') === k, p = doc.getElementById(t.getAttribute('aria-controls'));
t.setAttribute('aria-selected', on ? 'true' : 'false'); t.tabIndex = on ? 0 : -1;
if (p) p.hidden = !on;
if (on && focus) t.focus();
});
if (window.location.hash !== '#chart=' + k) history.replaceState(null, '', window.location.pathname + window.location.search + '#chart=' + k);
}
tabs.forEach(function (t, i) {
t.addEventListener('click', function () { showChart(t.getAttribute('data-chart')); });
t.addEventListener('keydown', function (e) {
var d = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : e.key === 'Home' ? -i : e.key === 'End' ? tabs.length - 1 - i : 0;
if (d) { e.preventDefault(); showChart(tabs[(i + d + tabs.length) % tabs.length].getAttribute('data-chart'), true); }
});
});
var fromHash = function () { var m = /chart=([a-z]+)/.exec(window.location.hash); if (m) showChart(m[1]); };
window.addEventListener('hashchange', fromHash);
fromHash();
}
})();
