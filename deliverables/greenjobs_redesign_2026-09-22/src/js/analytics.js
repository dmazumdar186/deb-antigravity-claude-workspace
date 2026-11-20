/* GA4 loader. Present only in production builds (see analytics.json). Reads
   <meta name="gj-ga4" content="G-XXXX" data-hosts="a,b">. Consent Mode v2: all
   storage denied by default; gtag.js is not even requested until the visitor
   has accepted analytics (gj-consent.analytics === true) on a production host.
   Events carry only allow-listed non-personal keys. */
(function () {
  'use strict';
  var m = document.querySelector('meta[name="gj-ga4"]');
  if (!m) return;
  var id = m.getAttribute('content') || '', hosts = (m.getAttribute('data-hosts') || '').split(',');
  if (!/^G-[A-Z0-9]+$/.test(id) || hosts.indexOf(location.hostname) < 0) return;
  var ALLOW = { job_id: 1, sector: 1, region: 1, src_page: 1, apply_mode: 1 };
  window.dataLayer = window.dataLayer || [];
  function gtag() { window.dataLayer.push(arguments); }
  gtag('consent', 'default', { ad_storage: 'denied', ad_user_data: 'denied', ad_personalization: 'denied', analytics_storage: 'denied', wait_for_update: 500 });
  var loaded = false;
  function granted() { try { var c = JSON.parse(localStorage.getItem('gj-consent') || 'null'); return !!(c && c.analytics === true); } catch (e) { return false; } }
  function load() {
    if (loaded || !granted()) return;
    loaded = true;
    gtag('consent', 'update', { analytics_storage: 'granted' });
    gtag('js', new Date());
    gtag('config', id, { allow_google_signals: false, allow_ad_personalization_signals: false });
    var s = document.createElement('script'); s.async = true; s.src = 'https://www.googletagmanager.com/gtag/js?id=' + encodeURIComponent(id);
    document.head.appendChild(s);
  }
  window.GJAnalytics = function (name, props) {
    if (!granted()) return;
    var p = {}, k; props = props || {};
    for (k in props) if (ALLOW[k] === 1 && typeof props[k] === 'string') p[k] = props[k].slice(0, 100);
    load();
    gtag('event', name, p);
  };
  window.addEventListener('gj-consent', function () { if (granted()) load(); else if (loaded) gtag('consent', 'update', { analytics_storage: 'denied' }); });
  load();
})();
