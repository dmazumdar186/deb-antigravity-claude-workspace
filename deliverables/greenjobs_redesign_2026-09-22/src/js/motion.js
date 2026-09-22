'use strict';
/* Motion craft, shared by every page: header progress bar, count-ups on
   reveal, pointer spotlight on cards, magnetic primary buttons, and the
   job-title view transition (card ⇄ page). Everything here is gated by
   prefers-reduced-motion and touches only transform / opacity / CSS vars. */
(function () {
  var G = window.GJ, doc = document, reduce = window.matchMedia('(prefers-reduced-motion: reduce)'), fine = window.matchMedia('(pointer: fine)');
  var $$ = function (s, c) { return Array.prototype.slice.call((c || doc).querySelectorAll(s)); };

  /* ------------------------------------------------ header progress */
  var prog = doc.querySelector('[data-progress]');
  if (prog) {
    var pt = false;
    var paint = function () {
      pt = false;
      var h = doc.documentElement.scrollHeight - window.innerHeight;
      prog.style.transform = 'scaleX(' + (h > 0 ? Math.min(1, window.scrollY / h) : 0).toFixed(4) + ')';
    };
    window.addEventListener('scroll', function () { if (!pt) { pt = true; requestAnimationFrame(paint); } }, { passive: true });
    window.addEventListener('resize', paint);
    paint();
  }

  /* ------------------------------------------------ count-ups */
  var io = null;
  function countUp(el) {
    var to = parseFloat(el.getAttribute('data-count')), txt = el.textContent, grouped = txt.indexOf(',') >= 0;
    if (isNaN(to) || el.getAttribute('data-counted')) return;
    el.setAttribute('data-counted', '1');
    if (reduce.matches || to === 0) return;
    var t0 = performance.now(), dur = 600;
    var tick = function (now) {
      var u = Math.min(1, (now - t0) / dur), v = G.countAt(0, to, u);
      el.textContent = grouped ? v.toLocaleString('en-GB') : String(v);
      if (u < 1) requestAnimationFrame(tick); else el.textContent = txt;
    };
    requestAnimationFrame(tick);
    setTimeout(function () { el.textContent = txt; }, dur + 80); /* rAF can stall in a background tab: land on the real number regardless */
  }
  function watch(scope) {
    var els = $$('[data-count]', scope);
    if (!els.length) return;
    if (!('IntersectionObserver' in window) || reduce.matches) { els.forEach(countUp); return; }
    io = io || new IntersectionObserver(function (es) { es.forEach(function (e) { if (e.isIntersecting) { countUp(e.target); io.unobserve(e.target); } }); }, { threshold: 0.4 });
    els.forEach(function (el) { io.observe(el); });
  }
  watch(doc);

  /* ------------------------------------------------ spotlight + magnetic (pointer: fine only) */
  if (fine.matches && !reduce.matches) {
    var SPOT = '.role,.sect,.hit,.fact,.fig,.score__t';
    doc.addEventListener('pointermove', function (e) {
      var c = e.target.closest(SPOT);
      if (c) {
        var r = c.getBoundingClientRect();
        c.style.setProperty('--mx', (e.clientX - r.left).toFixed(0) + 'px'); c.style.setProperty('--my', (e.clientY - r.top).toFixed(0) + 'px');
        c.classList.add('is-lit');
      }
      var b = e.target.closest('[data-magnet],.btn--lime');
      if (b) {
        var br = b.getBoundingClientRect(), dx = (e.clientX - (br.left + br.width / 2)) * 0.16, dy = (e.clientY - (br.top + br.height / 2)) * 0.22;
        dx = Math.max(-6, Math.min(6, dx)); dy = Math.max(-4, Math.min(4, dy));
        b.style.setProperty('--mgx', dx.toFixed(1) + 'px'); b.style.setProperty('--mgy', dy.toFixed(1) + 'px'); b.classList.add('is-magnet');
      }
    }, { passive: true });
    doc.addEventListener('pointerout', function (e) {
      var c = e.target.closest('.is-lit');
      if (c && !c.contains(e.relatedTarget)) c.classList.remove('is-lit');
      var b = e.target.closest('.is-magnet');
      if (b && !b.contains(e.relatedTarget)) { b.classList.remove('is-magnet'); b.style.removeProperty('--mgx'); b.style.removeProperty('--mgy'); }
    });
  }

  /* ------------------------------------------------ view transition: job title, card ⇄ page */
  var KEY = 'gj-vt-job';
  function nameCard(id) {
    var b = id && doc.querySelector('[data-save="' + id.replace(/"/g, '') + '"]');
    var card = b && b.closest('.role,.row');
    var title = card && card.querySelector('h3');
    if (title) { $$('.vt-title').forEach(function (t) { if (t !== title) t.classList.remove('vt-title'); }); title.classList.add('vt-title'); return true; }
    return false;
  }
  doc.addEventListener('click', function (e) {
    var a = e.target.closest('.role h3 a,.row h3 a,.hit');
    if (!a || e.defaultPrevented || e.metaKey || e.ctrlKey || e.button) return;
    var card = a.closest('.role,.row,.hit'), save = card && card.querySelector('[data-save]');
    var id = save ? save.getAttribute('data-save') : a.getAttribute('data-vt');
    if (!id) return;
    try { sessionStorage.setItem(KEY, id); } catch (err) { /* private mode: the morph simply does not run */ }
    (a.closest('.hit') ? a : a.closest('h3')).classList.add('vt-title');
  });
  var pending = null;
  try { pending = sessionStorage.getItem(KEY); } catch (err) { pending = null; }
  if (pending && !doc.querySelector('.job__head')) {
    /* Back on a list: name the matching card before the incoming transition
       captures, then drop the name so later cards do not share it. */
    if (nameCard(pending)) setTimeout(function () { $$('.role .vt-title,.row .vt-title').forEach(function (t) { t.classList.remove('vt-title'); }); }, 700);
    try { sessionStorage.removeItem(KEY); } catch (err) { /* ignore */ }
  }

  window.GJMotion = { refresh: function (scope) { watch(scope || doc); } };
})();
