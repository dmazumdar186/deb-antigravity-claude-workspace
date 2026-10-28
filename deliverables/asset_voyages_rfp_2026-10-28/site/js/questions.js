/* questions.js — re-align a #q1…#q30 link once fonts and layout have settled (the first jump can land under the header). */
(function () {
  function fix() { var h = location.hash; if (!/^#(q\d{1,2}|s\d)$/.test(h)) return; var el = document.getElementById(h.slice(1)); if (el) el.scrollIntoView({ block: 'start' }); }
  window.addEventListener('load', function () { (document.fonts && document.fonts.ready ? document.fonts.ready : Promise.resolve()).then(fix); });
})();
