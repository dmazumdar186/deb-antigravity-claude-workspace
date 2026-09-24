'use strict';
/* Cookie settings banner + weekly-email subscribe dialog. Both are native
   <dialog> / fixed elements, so nothing in the page moves. State lives in
   localStorage: gj-consent (essential|analytics|marketing flags) and
   gj-subscribe (ISO date of the last dismissal). The subscribe dialog opens
   once per device, 20 s after load or on exit intent (desktop), never on the
   jobs / job pages while the visitor is typing, never within 7 days of a
   dismissal. Submitting shows the honest demo note; nothing is sent. */
(function () {
  var doc = document, body = doc.body;
  function store(k, v) { try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (e) { return null; } }
  var $ = function (s, c) { return (c || doc).querySelector(s); };
  var force = (window.location.search.match(/[?&]popup=(cookie|subscribe|settings)/) || [])[1]; /* capture and verification hook */

  /* ------------------------------------------------ cookie banner + settings */
  var bar = $('[data-cookie]'), dlg = $('[data-cookie-dialog]');
  if (bar && dlg) {
    var consent = null;
    try { consent = JSON.parse(store('gj-consent') || 'null'); } catch (e) { consent = null; }
    var opener = null;
    function save(obj) { store('gj-consent', JSON.stringify(obj)); bar.classList.remove('is-on'); bar.setAttribute('aria-hidden', 'true'); }
    function openSettings(from) {
      opener = from || doc.activeElement;
      var cur = consent || { essential: true, analytics: false, marketing: false };
      $('#ck-analytics', dlg).checked = !!cur.analytics; $('#ck-marketing', dlg).checked = !!cur.marketing;
      dlg.showModal();
    }
    dlg.addEventListener('close', function () { if (opener && opener.focus && doc.contains(opener)) opener.focus(); });
    dlg.addEventListener('click', function (e) { if (e.target === dlg) dlg.close(); });
    $('[data-cookie-accept]', bar).addEventListener('click', function () { consent = { essential: true, analytics: false, marketing: false, at: new Date().toISOString() }; save(consent); });
    $('[data-cookie-settings]', bar).addEventListener('click', function (e) { openSettings(e.currentTarget); });
    $('form', dlg).addEventListener('submit', function (e) {
      e.preventDefault();
      consent = { essential: true, analytics: $('#ck-analytics', dlg).checked, marketing: $('#ck-marketing', dlg).checked, at: new Date().toISOString() };
      save(consent); dlg.close();
    });
    $('[data-cookie-close]', dlg).addEventListener('click', function () { dlg.close(); });
    if (!consent || force === 'cookie' || force === 'settings') {
      bar.removeAttribute('aria-hidden');
      setTimeout(function () { bar.classList.add('is-on'); }, force ? 0 : 600);
      if (force === 'settings') setTimeout(function () { openSettings($('[data-cookie-settings]', bar)); }, 80);
    }
    window.GJCookie = { get: function () { return consent; }, open: openSettings };
  }

  /* ------------------------------------------------ subscribe dialog */
  var sub = $('[data-subscribe]');
  if (sub) {
    var shown = false, page = body.getAttribute('data-page') || '', typing = false, lastKey = 0;
    var onBoard = /^(jobs|job)$/.test(page);
    function recent() {
      var at = store('gj-subscribe');
      if (!at) return false;
      var d = new Date(at).getTime();
      return !isNaN(d) && Date.now() - d < 7 * 864e5;
    }
    function open() {
      if (shown) return;
      if (!force && (recent() || (onBoard && (typing || Date.now() - lastKey < 4000)))) return;
      if (doc.querySelector('dialog[open]')) return; /* never stack on the menu, palette or cookie settings */
      shown = true; sub.showModal();
      var em = $('input[type="email"]', sub); if (em) em.focus();
    }
    function dismiss() { store('gj-subscribe', new Date().toISOString()); }
    sub.addEventListener('close', dismiss);
    sub.addEventListener('click', function (e) { if (e.target === sub) sub.close(); });
    $('[data-subscribe-close]', sub).addEventListener('click', function () { sub.close(); });
    $('form', sub).addEventListener('submit', function (e) { e.preventDefault(); var n = $('[data-demo-note]', sub); if (n) { n.hidden = false; n.focus(); } });
    doc.addEventListener('keydown', function (e) { var t = e.target; if (t && /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)) { typing = true; lastKey = Date.now(); } });
    doc.addEventListener('focusout', function (e) { var t = e.target; if (t && /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)) typing = false; });
    if (force === 'subscribe') setTimeout(open, 120);
    else if (!recent()) {
      var timer = setTimeout(open, 20000);
      if (window.matchMedia('(pointer: fine)').matches) doc.addEventListener('mouseout', function (e) { if (!e.relatedTarget && e.clientY <= 0) { clearTimeout(timer); open(); } });
    }
    window.GJSubscribe = { open: open, shown: function () { return shown; } };
  }
})();
