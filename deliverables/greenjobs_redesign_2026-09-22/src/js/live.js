'use strict';
/* Live figures. The build prints every job-derived number (live roles, disclosed salaries, disclosure
   rate, median, sector tile counts) as of the build; once jobs come from the platform Worker those go
   stale, so this script asks GET /api/stats?site=<edition> (same rules as build_site.py, cached <= 5 min
   at the edge) and replaces each [data-live] / [data-live-sector] value in place. The build-time
   numbers stay as the no-JS and offline fallback: any failure leaves them untouched (advice, not
   delivery: it degrades silently). Pure helpers are exported for node --test (live.test.js). */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.GJLive = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  /* {key: text} for every [data-live] key the templates use. */
  function liveValues(s) {
    if (!s || !s.salary) return null;
    return { n_jobs: String(s.salary.n_jobs), n_disc: String(s.salary.n_disc), disc_pct: String(s.salary.disc_pct), median: String(s.salary.median) };
  }
  /* Sector tile caption, as build_site.sector_tiles() writes it. */
  function sectorCaption(sec) {
    return (sec.n === 1 ? 'role' : 'roles') + ' · ' + sec.stat;
  }
  function apply(doc, s) {
    var v = liveValues(s);
    if (!v) return 0;
    var n = 0;
    Array.prototype.forEach.call(doc.querySelectorAll('[data-live]'), function (el) {
      var key = el.getAttribute('data-live');
      if (!Object.prototype.hasOwnProperty.call(v, key)) return;
      el.textContent = v[key];
      if (el.hasAttribute('data-count')) el.setAttribute('data-count', v[key]);
      n++;
    });
    var byName = {};
    (s.sectors || []).forEach(function (x) { byName[x.name] = x; });
    Array.prototype.forEach.call(doc.querySelectorAll('[data-live-sector]'), function (el) {
      var sec = byName[el.getAttribute('data-live-sector')], p = el.querySelector('.n'), small = p && p.querySelector('small');
      if (!sec || !p || !small) return;
      if (p.firstChild && p.firstChild.nodeType === 3) p.firstChild.nodeValue = String(sec.n);
      small.textContent = sectorCaption(sec);
      n++;
    });
    return n;
  }
  function init() {
    var ed = document.body && document.body.getAttribute('data-edition');
    // Only where the platform Worker answers /api/* on this host (build_site --live-api): a static host
    // (the demo, staging Pages) would log a 404 on every page.
    if (document.body.getAttribute('data-live-api') !== '1') return;
    if ((ed !== 'ie' && ed !== 'uk') || typeof fetch !== 'function') return;
    fetch('/api/stats?site=' + ed, { credentials: 'omit' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (s) { if (s && s.site === ed) apply(document, s); })
      .catch(function () { /* offline or no Worker on this host (the static demo): keep the build-time figures */ });
  }
  if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
  }
  return { liveValues: liveValues, sectorCaption: sectorCaption, apply: apply };
});
