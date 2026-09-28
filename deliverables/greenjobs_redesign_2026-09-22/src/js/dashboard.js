'use strict';
/* KPI dashboard: draws the three charts from the embedded #gj-dash payload
   with GJCharts and exports the live-now table as CSV, client-side only.
   Pure helpers are exported for node --test (dashboard.test.js). */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.GJDash = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  function csvCell(v) {
    var s = v == null ? '' : String(v);
    if (/^[=+\-@]/.test(s)) s = "'" + s; /* spreadsheet formula injection guard */
    return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  }
  function toCsv(rows) {
    return rows.map(function (r) { return r.map(csvCell).join(','); }).join('\r\n') + '\r\n';
  }
  /* Flatten the KPI payload into [metric, value, definition] rows. */
  function kpiRows(k, sym) {
    var rows = [['metric', 'value', 'how we measure it'],
      ['Live roles', k.live, 'listings with a page on the snapshot date'],
      ['New this week', k.new7, 'posted within 7 days of the snapshot'],
      ['Closing within 7 days', k.closing7, 'closing date within the next 7 days'],
      ['Salary disclosure %', k.sal_pct, k.sal_n + ' roles publish a figure'],
      ['Median disclosed salary', k.sal_median == null ? '' : sym + k.sal_median, 'median of annualised midpoints'],
      ['Top employer share %', k.top_share, k.top_employer],
      ['Agency share %', k.agency_pct, 'roles flagged agency by the build (known agency names or recruit/talent/staffing words in the employer name)'],
      ['Advertised window (median days)', k.days_to_close == null ? '' : k.days_to_close, 'closing minus posted'],
      ['Remote or hybrid %', k.remote_pct, 'workplace field is remote or hybrid']];
    (k.sectors || []).forEach(function (s) { rows.push(['Sector: ' + s.l, s.v, 'live roles']); });
    (k.regions || []).forEach(function (r) { rows.push(['Region: ' + r.l, r.v, 'live roles']); });
    (k.quality || []).forEach(function (n, i) { rows.push(['Quality score ' + i + '/4', n, 'roles']); });
    return rows;
  }
  function init() {
    var host = document.querySelector('[data-dash]'), src = document.getElementById('gj-dash');
    if (!host || !src || !window.GJCharts) return;
    var C = window.GJCharts, k = JSON.parse(src.textContent), sym = document.documentElement.lang === 'en-GB' ? '£' : '€';
    function fig(key, rows, label, unit) {
      var f = host.querySelector('[data-fig="' + key + '"]');
      if (!f) return;
      f.appendChild(C.bars(rows.map(function (r) { return { label: r.l, v: r.v }; }), { label: label, fmt: function (v) { return v + (v === 1 ? ' role' : ' roles'); } }));
      f.appendChild(C.table([unit, 'Roles'], rows.map(function (r) { return [r.l, String(r.v)]; })));
    }
    fig('sectors', k.sectors, 'Live roles by sector', 'Sector');
    fig('regions', k.regions, 'Live roles by area', 'Area');
    var q = host.querySelector('[data-fig="quality"]');
    if (q) {
      var bins = k.quality.map(function (n, i) { return { label: i + ' of 4', n: n }; });
      q.appendChild(C.columns(bins, { label: 'Listing quality score distribution' }));
      q.appendChild(C.table(['Score', 'Roles'], bins.map(function (b) { return [b.label, String(b.n)]; })));
    }
    var btn = host.querySelector('[data-csv]');
    if (btn) btn.addEventListener('click', function () {
      var blob = new Blob([toCsv(kpiRows(k, sym))], { type: 'text/csv;charset=utf-8' }), a = document.createElement('a');
      a.href = URL.createObjectURL(blob); a.download = 'greenjobs-kpis-' + k.asof + '.csv';
      document.body.appendChild(a); a.click(); a.remove(); setTimeout(function () { URL.revokeObjectURL(a.href); }, 1000);
    });
  }
  if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
  }
  return { csvCell: csvCell, toCsv: toCsv, kpiRows: kpiRows };
});
