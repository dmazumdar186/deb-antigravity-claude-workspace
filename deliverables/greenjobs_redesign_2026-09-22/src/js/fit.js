'use strict';
/* "Your fit in ten seconds": paste a CV, a headline or three words and get
   the six live roles that overlap most (lib.js fitMatch: title-weighted
   TF-IDF with two-word phrases and sector / place boosts), the matched words
   highlighted, your position on the board's disclosed-salary strip, a small
   map of where the matches are, and one caveat. Result lives in the URL hash. */
(function () {
  var G = window.GJ, doc = document, panel = doc.querySelector('[data-fit]');
  if (!panel) return;
  var form = panel.querySelector('[data-fit-form]'), ta = form.querySelector('textarea'), out = panel.querySelector('[data-fit-out]');
  var empty = panel.querySelector('[data-fit-empty]'), share = panel.querySelector('[data-fit-share]'), mapTpl = panel.querySelector('template[data-fit-map]');
  var jobsHref = panel.getAttribute('data-jobs') || 'index.html', sym = panel.getAttribute('data-sym') || '€', ROOT = doc.body.getAttribute('data-root') || '';
  var cur = sym === '£' ? 'GBP' : 'EUR', jobs = null, idx = null, timer = 0, lastQ = '';

  function load() {
    if (jobs) return Promise.resolve(jobs);
    return window.GJData().then(function (d) { jobs = d.jobs || []; idx = G.fitIndex(jobs); return jobs; });
  }
  function esc(s) { return G.esc(s); }
  function hl(txt, stemsList) {
    var res = stemsList.map(function (s) { return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }).filter(Boolean);
    if (!res.length) return esc(txt);
    var re = new RegExp('(\\b(?:' + res.join('|') + ')[a-z]*)', 'ig');
    return String(txt == null ? '' : txt).split(re).map(function (piece, i) { return i % 2 ? '<mark>' + esc(piece) + '</mark>' : esc(piece); }).join('');
  }
  function money(n) { return G.money(n, cur); }
  function strip(pos) {
    var b = pos.board, W = 400, H = 64, lo = Math.floor(b.min / 10000) * 10000, hi = Math.ceil(b.max / 10000) * 10000 || 100000;
    function X(v) { return 10 + 380 * (v - lo) / Math.max(1, hi - lo); }
    var dots = jobs.map(G.annual).filter(Boolean).map(function (a) { return '<circle cx="' + X(a.mid).toFixed(1) + '" cy="34" r="3"/>'; }).join('');
    var mine = pos.lo != null ? '<rect class="fit__me" x="' + X(pos.lo).toFixed(1) + '" y="26" width="' + Math.max(8, X(pos.hi) - X(pos.lo)).toFixed(1) + '" height="16" rx="8"/>' : '';
    var med = '<line class="fit__med" x1="' + X(b.median).toFixed(1) + '" x2="' + X(b.median).toFixed(1) + '" y1="20" y2="48"/>';
    return '<svg class="fit__strip" viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="' + esc(pos.lo != null ? 'Roles like yours pay ' + money(pos.lo) + ' to ' + money(pos.hi) + ' against ' + b.n + ' disclosed salaries on the board' : b.n + ' disclosed salaries on the board; none of these matches publishes one') + '">' +
      '<g class="fit__dots">' + dots + '</g>' + med + mine +
      '<text x="10" y="60" class="fit__tick">' + esc(money(lo)) + '</text><text x="' + X(b.median).toFixed(1) + '" y="12" class="fit__tick" text-anchor="middle">median ' + esc(money(b.median)) + '</text><text x="390" y="60" class="fit__tick" text-anchor="end">' + esc(money(hi)) + '</text></svg>';
  }
  function miniMap(hits) {
    if (!mapTpl) return '';
    var counts = {}, max = 0;
    hits.forEach(function (h) { (h.job.regions || []).forEach(function (r) { counts[r] = (counts[r] || 0) + 1; if (counts[r] > max) max = counts[r]; }); });
    var wrap = doc.createElement('div'); wrap.className = 'fit__map'; wrap.appendChild(mapTpl.content.cloneNode(true));
    var svg = wrap.querySelector('svg'), any = false;
    if (!svg) return '';
    svg.setAttribute('aria-label', 'Where the matches are');
    [].slice.call(svg.querySelectorAll('.gmap__r')).forEach(function (g) {
      var name = g.getAttribute('data-region'), n = counts[name] || 0;
      g.setAttribute('data-n', String(n)); g.setAttribute('data-lvl', n === 0 ? '0' : n >= max * 0.6 ? '3' : n >= max * 0.25 ? '2' : '1');
      g.setAttribute('aria-label', name + ': ' + n + (n === 1 ? ' match' : ' matches'));
      var t = g.querySelector('text'); if (t) g.removeChild(t);
      if (n) { any = true; var tx = doc.createElementNS('http://www.w3.org/2000/svg', 'text'); tx.setAttribute('x', g.getAttribute('data-cx')); tx.setAttribute('y', g.getAttribute('data-cy')); tx.setAttribute('dy', '6'); tx.textContent = String(n); g.appendChild(tx); }
    });
    var places = Object.keys(counts).sort(function (a, b) { return counts[b] - counts[a]; });
    var cap = '<p class="fit__cap">' + (any ? esc(places.slice(0, 4).map(function (p) { return p + ' ' + counts[p]; }).join(' · ')) : 'The matches are nationwide or remote.') + '</p>';
    return '<div class="fit__where"><h3>Where they are</h3>' + wrap.outerHTML + cap + '</div>';
  }
  function chips(list) { return list.map(function (t) { return '<span>' + esc(t) + '</span>'; }).join(''); }
  function render(q, hits) {
    empty.hidden = true; share.hidden = false;
    if (!hits.length) {
      var secs = {}; jobs.forEach(function (j) { (j.sectors || []).forEach(function (s) { secs[s] = (secs[s] || 0) + 1; }); });
      var top = Object.keys(secs).sort(function (a, b) { return secs[b] - secs[a]; }).slice(0, 5);
      out.innerHTML = '<div class="fit__none"><h3>Nothing on the board overlaps with that yet.</h3><p>The board is small and honest: ' + jobs.length + ' live roles, matched on the words in their titles, sectors and descriptions. Try a skill, a tool, a place, or start from a sector:</p><div class="fit__try">' +
        top.map(function (s) { return '<button type="button" data-fit-eg="' + esc(s) + '">' + esc(s) + '</button>'; }).join('') + '</div></div>';
      return;
    }
    var pos = G.salaryPosition(hits, jobs), stemsAll = [];
    hits.forEach(function (h) { h.stems.forEach(function (s) { if (stemsAll.indexOf(s) < 0) stemsAll.push(s); }); });
    var pay = pos.lo != null
      ? 'Roles like yours pay <b>' + esc(money(pos.lo)) + '–' + esc(money(pos.hi)) + '</b>; ' + pos.share + '% of matches disclose (' + pos.disclosed + ' of ' + pos.n + '). That range runs from the ' + pos.plo + 'th to the ' + pos.phi + 'th percentile of the ' + pos.board.n + ' disclosed salaries on the board.'
      : 'None of these ' + pos.n + ' matches publishes a salary. The board\'s ' + pos.board.n + ' disclosed salaries, for scale:';
    var list = hits.map(function (h, i) {
      var j = h.job, sal = G.salaryLabel(j);
      return '<a class="hit reveal" style="--i:' + i + '" href="' + esc(G.jobUrl(jobsHref, j.href)) + '" data-vt="' + esc(j.id) + '"><b>' + hl(j.title, h.stems) + '</b><small>' + esc(j.employer) + ' · ' + esc(j.location) + (sal ? ' · <span class="hit__sal">' + esc(sal) + '</span>' : '') + '</small><span class="why">' + chips(h.terms) + '</span></a>';
    }).join('');
    out.innerHTML = '<p class="fit__sum">' + hits.length + ' of ' + jobs.length + ' roles overlap. Matched on ' + chips(hits[0].terms.slice(0, 4)) + '</p>' +
      '<div class="fit__hits">' + list + '</div>' +
      '<div class="fit__side"><div class="fit__pay"><h3>Where you sit on pay</h3><p>' + pay + '</p>' + strip(pos) + '</div>' + miniMap(hits) + '</div>' +
      '<p class="fit__caveat">Matched on words, not judgement: a role can rank high because a word repeats, and a great fit can hide behind an odd title. Pay figures are the ' + pos.disclosed + ' of ' + pos.n + ' matches that publish one, annualised at the midpoint. <a href="' + esc(jobsHref) + '?q=' + encodeURIComponent(hits[0].terms[0] || '') + '">Open the full search</a>.</p>';
    if (window.GJMotion) window.GJMotion.refresh(out);
  }
  function run(q, fromHash) {
    q = String(q || '').trim();
    if (!q) { out.innerHTML = ''; out.appendChild(empty); empty.hidden = false; share.hidden = true; if (!fromHash && window.location.hash.indexOf('#fit=') === 0) history.replaceState(null, '', window.location.pathname + window.location.search); lastQ = ''; return; }
    if (q === lastQ) return;
    lastQ = q;
    load().then(function () {
      render(q, G.fitMatch(q, jobs, idx, 6));
      history.replaceState(null, '', window.location.pathname + window.location.search + '#fit=' + G.encodeFit(q));
    });
  }
  form.addEventListener('submit', function (e) { e.preventDefault(); clearTimeout(timer); lastQ = ''; run(ta.value); out.setAttribute('tabindex', '-1'); out.focus({ preventScroll: true }); });
  ta.addEventListener('input', function () { clearTimeout(timer); timer = setTimeout(function () { run(ta.value); }, 180); });
  ta.addEventListener('focus', function () { load(); });
  panel.addEventListener('click', function (e) {
    var b = e.target.closest('[data-fit-eg]');
    if (b) { ta.value = b.getAttribute('data-fit-eg'); ta.focus(); lastQ = ''; run(ta.value); }
  });
  share.addEventListener('click', function () {
    var url = window.location.href;
    if (navigator.clipboard) navigator.clipboard.writeText(url).then(function () { window.GJsay('Link copied'); }, function () { window.GJsay(url); });
    else window.GJsay(url);
  });
  var fromHash = G.decodeFit(window.location.hash);
  if (fromHash) { ta.value = fromHash; run(fromHash, true); panel.scrollIntoView({ block: 'start' }); }
  window.GJFit = { run: run, ready: load };
})();
