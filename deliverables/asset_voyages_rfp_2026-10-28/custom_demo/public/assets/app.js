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
  // After a failed submission, move focus to the summary so screen readers hear it.
  var errs = document.getElementById('form-errors');
  if (errs) errs.focus();
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
