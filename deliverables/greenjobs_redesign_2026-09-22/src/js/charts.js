'use strict';
/* In-house SVG charts: sparkline, horizontal bars, columns (histogram) and
   a squarified treemap. One system: thin marks, recessive axes, text in
   text tokens, tooltip + keyboard focus on every mark, table under each. */
(function () {
  var G = window.GJ, NS = 'http://www.w3.org/2000/svg';
  function el(tag, attrs, text) {
    var e = document.createElementNS(NS, tag);
    Object.keys(attrs || {}).forEach(function (k) { e.setAttribute(k, attrs[k]); });
    if (text != null) e.textContent = text;
    return e;
  }
  function tipOn(node, html) {
    node.addEventListener('mousemove', function (e) { window.GJTip.show(e.clientX, e.clientY, html); });
    node.addEventListener('mouseleave', window.GJTip.hide);
    node.addEventListener('focus', function () { var r = node.getBoundingClientRect(); window.GJTip.show(r.left + r.width / 2, r.top, html); });
    node.addEventListener('blur', window.GJTip.hide);
  }
  function sparkline(vals, w, h) {
    w = w || 120; h = h || 34;
    var max = Math.max.apply(null, vals) || 1, n = vals.length, pad = 3;
    var pts = vals.map(function (v, i) { return [(pad + i * (w - 2 * pad) / Math.max(1, n - 1)).toFixed(1), (h - pad - (v / max) * (h - 2 * pad)).toFixed(1)]; });
    var line = 'M' + pts.map(function (p) { return p.join(','); }).join(' L');
    var last = pts[pts.length - 1];
    return '<svg class="spark" viewBox="0 0 ' + w + ' ' + h + '" aria-hidden="true" focusable="false"><path class="fill" d="' + line + ' L' + last[0] + ',' + h + ' L' + pts[0][0] + ',' + h + 'Z"/><path d="' + line + '"/><circle cx="' + last[0] + '" cy="' + last[1] + '" r="3"/></svg>';
  }
  /* rows: [{label, v, sub, cls}] ; opts: {fmt, max, unit} */
  /* Horizontal bars as HTML rows: the label sits above the bar in real text,
     so it wraps instead of truncating and never scales with the SVG width. */
  function bars(rows, opts) {
    opts = opts || {};
    var max = opts.max || Math.max.apply(null, rows.map(function (r) { return r.v; })) || 1;
    var list = document.createElement('div'); list.className = 'hbars'; list.setAttribute('role', 'list'); list.setAttribute('aria-label', opts.label || 'Bar chart');
    rows.forEach(function (r) {
      var val = opts.fmt ? opts.fmt(r.v) : String(r.v), d = document.createElement('div');
      d.className = 'hbar' + (r.cls ? ' ' + r.cls : ''); d.setAttribute('role', 'listitem'); d.setAttribute('tabindex', '0');
      d.setAttribute('aria-label', r.label + ': ' + val + (r.sub ? ', ' + r.sub : ''));
      d.innerHTML = '<span class="hbar__l">' + G.esc(r.label) + '</span><i class="hbar__b" style="--w:' + Math.max(1, 100 * r.v / max).toFixed(1) + '%"></i><b class="hbar__v num">' + G.esc(val) + '</b>';
      tipOn(d, '<b>' + G.esc(r.label) + '</b><span>' + G.esc(val) + (r.sub ? ' · ' + G.esc(r.sub) : '') + '</span>');
      list.appendChild(d);
    });
    return list;
  }
  function columns(bins, opts) {
    opts = opts || {};
    var W = 600, H = 220, pb = 34, pl = 30, n = bins.length, cw = (W - pl) / n, max = Math.max.apply(null, bins.map(function (b) { return b.n; })) || 1;
    var svg = el('svg', { viewBox: '0 0 ' + W + ' ' + H, role: 'list', 'aria-label': opts.label || 'Histogram' });
    var grid = el('g', { class: 'grid' });
    [0.5, 1].forEach(function (f) { var y = H - pb - f * (H - pb - 20); grid.appendChild(el('line', { x1: pl, x2: W, y1: y, y2: y })); grid.appendChild(el('text', { x: pl - 6, y: y + 4, 'text-anchor': 'end', class: 'lbl lbl--m' }, String(Math.round(max * f)))); });
    svg.appendChild(grid);
    bins.forEach(function (b, i) {
      var h = (b.n / max) * (H - pb - 20), x = pl + i * cw + 4, y = H - pb - h;
      var g = el('g', { role: 'listitem', tabindex: '0', 'aria-label': b.label + ': ' + b.n + (b.n === 1 ? ' role' : ' roles') });
      g.appendChild(el('rect', { x: x, y: y, width: cw - 8, height: Math.max(h, b.n ? 3 : 0), rx: 4, class: 'bar' }));
      if (b.n) g.appendChild(el('text', { x: x + (cw - 8) / 2, y: y - 6, 'text-anchor': 'middle', class: 'lbl' }, String(b.n)));
      g.appendChild(el('text', { x: x + (cw - 8) / 2, y: H - 12, 'text-anchor': 'middle', class: 'lbl lbl--m' }, b.label));
      tipOn(g, '<b>' + G.esc(b.label) + '</b><span>' + b.n + (b.n === 1 ? ' role' : ' roles') + '</span>');
      svg.appendChild(g);
    });
    return svg;
  }
  function treemap(items, opts) {
    opts = opts || {};
    var W = 800, H = opts.height || 460, rects = G.treemap(items, W, H);
    var svg = el('svg', { viewBox: '0 0 ' + W + ' ' + H, class: 'treemap', role: 'list', 'aria-label': opts.label || 'Treemap' });
    rects.forEach(function (r) {
      var it = r.item, g = el('g', { class: 'cell', role: 'listitem', tabindex: '0', 'data-key': it.key, 'aria-label': it.label + ': ' + it.v + (it.v === 1 ? ' role' : ' roles') });
      g.appendChild(el('rect', { x: r.x, y: r.y, width: r.w, height: r.h, fill: it.color }));
      if (r.w >= 90 && r.h > 40) {
        var dark = it.dark;
        var t = el('text', { x: r.x + 10, y: r.y + 22, fill: dark ? '#eef2ea' : '#0c1a12' });
        var words = it.label.split(' '), line = '', lines = [];
        words.forEach(function (w) { if ((line + ' ' + w).length * 7.8 > r.w - 16 && line) { lines.push(line); line = w; } else line = line ? line + ' ' + w : w; });
        lines.push(line);
        lines.slice(0, Math.max(1, Math.floor((r.h - 34) / 17))).forEach(function (l, i) { t.appendChild(el('tspan', { x: r.x + 10, dy: i ? 16 : 0 }, l)); });
        g.appendChild(t);
        g.appendChild(el('text', { x: r.x + 10, y: r.y + r.h - 10, class: 't2', fill: dark ? '#eef2ea' : '#0c1a12' }, it.v + (it.v === 1 ? ' role' : ' roles')));
      }
      tipOn(g, '<b>' + G.esc(it.label) + '</b><span>' + it.v + (it.v === 1 ? ' role' : ' roles') + '</span>');
      var act = function (e) { e.preventDefault(); if (opts.onPick) opts.onPick(it); };
      g.addEventListener('click', act);
      g.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') act(e); });
      svg.appendChild(g);
    });
    return svg;
  }
  function table(head, rows) {
    var t = document.createElement('table'); t.className = 'vtable';
    t.innerHTML = '<thead><tr>' + head.map(function (h, i) { return '<th' + (i ? ' class="n"' : '') + '>' + G.esc(h) + '</th>'; }).join('') + '</tr></thead><tbody>' +
      rows.map(function (r) { return '<tr>' + r.map(function (c, i) { return '<td' + (i ? ' class="n"' : '') + '>' + G.esc(c) + '</td>'; }).join('') + '</tr>'; }).join('') + '</tbody>';
    var d = document.createElement('details'); d.className = 'tbl';
    d.innerHTML = '<summary>Show as table</summary>'; d.appendChild(t);
    return d;
  }
  window.GJCharts = { sparkline: sparkline, bars: bars, columns: columns, treemap: treemap, table: table };
})();
