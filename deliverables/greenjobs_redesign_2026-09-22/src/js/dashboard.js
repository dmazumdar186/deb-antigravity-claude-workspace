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
      ['Advertised window, days', k.days_to_close == null ? '' : k.days_to_close, 'closing minus posted'],
      ['Remote or hybrid %', k.remote_pct, 'workplace field is remote or hybrid']];
    (k.sectors || []).forEach(function (s) { rows.push(['Sector: ' + s.l, s.v, 'live roles']); });
    (k.regions || []).forEach(function (r) { rows.push(['Region: ' + r.l, r.v, 'live roles']); });
    (k.quality || []).forEach(function (n, i) { rows.push(['Quality score ' + i + '/4', n, 'roles']); });
    return rows;
  }
  /* The eight "Live now" tile values in render_dashboard()'s order and format. */
  var TILE_KEYS = ['live', 'new7', 'closing7', 'sal_pct', 'days_to_close', 'remote_pct', 'top_share', 'agency_pct'];
  function tileTexts(k) {
    return TILE_KEYS.map(function (key) {
      var v = k[key];
      if (v == null) return 'n/a';
      return /_pct$|^top_share$/.test(key) ? v + '%' : String(v);
    });
  }
  /* "Measures to come" slots fed by /api/stats `measures` (applications, alert sign-ups, advertiser
     enquiries); null = not collected yet, shown as the page's dash ("collected from launch"). */
  function measureText(v) {
    return v == null ? '—' : String(v);
  }
  /* Live figures: GET /api/stats from the platform Worker replaces the build-time payload so the
     dashboard never goes stale; any failure (no Worker on this host, offline) keeps the embedded one. */
  function fetchStats(ed, timeoutMs) {
    if (typeof fetch !== 'function' || (ed !== 'ie' && ed !== 'uk')) return Promise.resolve(null);
    var timer = new Promise(function (res) { setTimeout(function () { res(null); }, timeoutMs); });
    var req = fetch('/api/stats?site=' + ed, { credentials: 'omit' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (s) { return s && s.site === ed && s.kpis ? s : null; })
      .catch(function () { return null; });
    return Promise.race([req, timer]);
  }
  function init() {
    var host = document.querySelector('[data-dash]'), src = document.getElementById('gj-dash');
    if (!host || !src || !window.GJCharts) return;
    var ed = document.body.getAttribute('data-edition');
    // /api/stats only where the platform Worker serves this host (build_site --live-api); else the embedded figures.
    if (document.body.getAttribute('data-live-api') !== '1') { draw(host, src, null); return; }
    fetchStats(ed, 4000).then(function (s) { draw(host, src, s); });
  }
  function draw(host, src, s) {
    var C = window.GJCharts, k = s ? s.kpis : JSON.parse(src.textContent), sym = document.documentElement.lang === 'en-GB' ? '£' : '€';
    if (s) {
      var vals = tileTexts(k);
      Array.prototype.forEach.call(host.querySelectorAll('.kpis:not([data-wired]) .kpi__v'), function (el, i) { if (i < vals.length) el.textContent = vals[i]; });
      var t = host.querySelector('.dash__bar time');
      if (t) {
        t.setAttribute('datetime', k.asof);
        t.textContent = new Date(k.asof + 'T00:00:00Z').toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' });
      }
      Array.prototype.forEach.call(host.querySelectorAll('[data-measure]'), function (el) {
        var key = el.getAttribute('data-measure'), v = el.querySelector('.kpi__v');
        if (v && s.measures && Object.prototype.hasOwnProperty.call(s.measures, key)) v.textContent = measureText(s.measures[key]);
      });
    }
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
  return { csvCell: csvCell, toCsv: toCsv, kpiRows: kpiRows, tileTexts: tileTexts, measureText: measureText, fetchStats: fetchStats, TILE_KEYS: TILE_KEYS };
});
