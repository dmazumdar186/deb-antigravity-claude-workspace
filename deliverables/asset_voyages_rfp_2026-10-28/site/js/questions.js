/* questions.js — #q1…#q30 jumps are instant (no smooth scroll), and a deep link is re-aligned once fonts and layout have settled. */
(function () {
  var root = document.documentElement, isQ = /^#q\d{1,2}$/, ok = /^#(q\d{1,2}|s\d)$/;
  function jump(h) { var el = document.getElementById(h.slice(1)); if (!el) return; var prev = root.style.scrollBehavior; root.style.scrollBehavior = 'auto'; el.scrollIntoView({ block: 'start', behavior: 'instant' }); root.style.scrollBehavior = prev; }
  if (isQ.test(location.hash)) root.style.scrollBehavior = 'auto';
  document.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('a[href^="#q"]'); if (!a) return;
    var h = a.getAttribute('href'); if (!isQ.test(h)) return;
    e.preventDefault(); history.pushState(null, '', h); jump(h);
  });
  window.addEventListener('hashchange', function () { if (isQ.test(location.hash)) jump(location.hash); });
  window.addEventListener('load', function () {
    (document.fonts && document.fonts.ready ? document.fonts.ready : Promise.resolve()).then(function () {
      if (ok.test(location.hash)) jump(location.hash);
      root.style.scrollBehavior = '';
    });
  });
})();
