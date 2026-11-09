// Progressive enhancement only: every page works without this file.
(function () {
  'use strict';
  // Filters apply as soon as a list is changed.
  document.querySelectorAll('select[data-autosubmit]').forEach(function (s) {
    s.addEventListener('change', function () { if (s.form) s.form.requestSubmit ? s.form.requestSubmit() : s.form.submit(); });
  });
  // Destructive actions ask once.
  document.querySelectorAll('form[data-confirm]').forEach(function (f) {
    f.addEventListener('submit', function (e) { if (!window.confirm(f.getAttribute('data-confirm'))) e.preventDefault(); });
  });
  // Return date never before the outbound date.
  var out = document.getElementById('f-out'), back = document.getElementById('f-back');
  if (out && back) {
    out.addEventListener('change', function () {
      if (out.value) { back.min = out.value; if (back.value && back.value < out.value) back.value = out.value; }
    });
  }
  // Delegate form (« Lien de groupe »): same rule for its dates.
  var gout = document.getElementById('g-out'), gback = document.getElementById('g-back');
  if (gout && gback) {
    gout.addEventListener('change', function () {
      if (gout.value) { gback.min = gout.value; if (gback.value && gback.value < gout.value) gback.value = gout.value; }
    });
  }
  // « Copier le lien »: shown only when the clipboard is available; without it the field stays selectable.
  document.querySelectorAll('button[data-copy]').forEach(function (b) {
    var src = document.getElementById(b.getAttribute('data-copy'));
    if (!src || !navigator.clipboard || !window.isSecureContext) return;
    b.hidden = false;
    b.addEventListener('click', function () {
      navigator.clipboard.writeText(src.value).then(function () { b.textContent = 'Lien copié'; }, function () { src.select(); });
    });
  });
  // Live manifest: while the « Groupe » tab is visible, reload the list every 15 s (same page, server-rendered).
  var live = document.querySelector('[data-live]');
  if (live && window.fetch && window.DOMParser) {
    setInterval(function () {
      if (document.visibilityState !== 'visible') return;
      fetch(location.pathname, { credentials: 'same-origin', headers: { accept: 'text/html' } }).then(function (r) { return r.ok ? r.text() : null; }).then(function (t) {
        if (!t) return;
        var next = new DOMParser().parseFromString(t, 'text/html').querySelector('[data-live]');
        var cur = document.querySelector('[data-live]');
        if (next && cur && !cur.contains(document.activeElement)) cur.replaceWith(document.importNode(next, true));
      }).catch(function () {});
    }, 15000);
  }
  // After a failed submission, move focus to the summary so screen readers hear it.
  // After a redirect or a validation error, move focus to the message (or the page heading) so it is announced.
  var focusTarget = document.querySelector('[data-focus]');
  if (focusTarget) focusTarget.focus({ preventScroll: false });
  // Prevent double submission.
  document.querySelectorAll('form[method="post"]').forEach(function (f) {
    f.addEventListener('submit', function (e) {
      if (e.defaultPrevented) return;
      if (f.dataset.sent) { e.preventDefault(); return; }
      f.dataset.sent = '1';
      setTimeout(function () { delete f.dataset.sent; }, 4000);
    });
  });
})();
