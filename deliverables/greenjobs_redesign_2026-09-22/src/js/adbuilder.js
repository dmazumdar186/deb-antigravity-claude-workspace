'use strict';
/* Employers: the live ad builder. Every keystroke re-renders the exact job
   card (board) and the top of the job page beside the form; a logo previews
   through FileReader and never leaves the device; the reach line is read
   from this week's data. Under 900px the preview sits under the form with a
   sticky Preview toggle. Submitting shows the honest demo note (main.js). */
(function () {
  var G = window.GJ, doc = document, root = doc.querySelector('[data-adb]');
  if (!root) return;
  var reach = {};
  try { reach = JSON.parse(root.getAttribute('data-reach') || '{}'); } catch (e) { reach = {}; }
  var sym = root.getAttribute('data-sym') || '€', cur = sym === '£' ? 'GBP' : 'EUR', unit = root.getAttribute('data-unit') || 'county';
  var form = root.querySelector('form'), card = root.querySelector('[data-adb-card]'), hero = root.querySelector('[data-adb-hero]'), reachEl = root.querySelector('[data-adb-reach]');
  var toggle = root.querySelector('[data-adb-toggle]'), preview = root.querySelector('[data-adb-preview]');
  var F = {}; ['title', 'org', 'loc', 'sector', 'type', 'smin', 'smax', 'b1', 'b2', 'b3'].forEach(function (k) { F[k] = doc.getElementById('p-' + k); });
  var logoIn = doc.getElementById('p-logo'), logoData = '';
  var IE = (doc.body.getAttribute('data-edition') || 'ie') === 'ie';
  var today = new Date().toISOString().slice(0, 10);

  function num(el) { var v = parseInt(el.value, 10); return isNaN(v) || v <= 0 ? null : v; }
  function job() {
    var lo = num(F.smin), hi = num(F.smax);
    if (lo != null && hi != null && hi < lo) { var t = lo; lo = hi; hi = t; }
    var sec = F.sector.value, r = reach[sec] || {};
    return {
      id: 'preview', title: F.title.value.trim(), employer: F.org.value.trim(), location: F.loc.value.trim(), type: F.type.value,
      sal_min: lo, sal_max: hi, cur: cur, period: 'year', sal_text: '', sectors: [sec], color: r.col || '#d99a1c', posted: today,
      bullets: [F.b1.value.trim(), F.b2.value.trim(), F.b3.value.trim()].filter(Boolean)
    };
  }
  function logo(j, cls) {
    if (logoData) return '<img class="' + cls + '" src="' + logoData + '" alt="" width="200" height="80">';
    return '<div class="' + cls + ' role__logo--t" aria-hidden="true">' + G.esc((j.employer || 'Y').charAt(0).toUpperCase()) + '</div>';
  }
  function ph(v, fallback) { return v ? G.esc(v) : '<span class="adb__ph">' + fallback + '</span>'; }
  function render() {
    var j = job(), sal = G.salaryLabel(j), blank = !j.title && !j.employer;
    root.classList.toggle('is-blank', blank);
    var chips = (sal ? '<span class="tag tag--sal">' + G.esc(sal) + '</span>' : '') + (j.type ? '<span class="tag tag--type">' + G.esc(j.type) + '</span>' : '');
    card.innerHTML = '<article class="role"><div class="role__top">' + logo(j, 'role__logo') + '<span class="save" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M6 3h12v18l-6-4-6 4z"/></svg></span></div>' +
      '<h3>' + ph(j.title, 'Your job title') + '</h3><p class="role__emp"><span>' + ph(j.employer, 'Your organisation') + '</span><span>' + ph(j.location, 'Location') + '</span></p>' +
      '<div class="role__meta">' + chips + '<time datetime="' + today + '">Today</time></div></article>';
    var meta = [j.location, j.type].filter(Boolean).map(function (x) { return '<span class="tag">' + G.esc(x) + '</span>'; }).join('') + (sal ? '<span class="tag tag--sal">' + G.esc(sal) + '</span>' : '');
    hero.innerHTML = '<nav class="crumbs" aria-hidden="true"><span>Home</span><span>/</span><span>Jobs</span><span>/</span><span>' + G.esc(j.sectors[0]) + '</span></nav>' +
      '<p class="adb__h1">' + ph(j.title, 'Your job title') + '</p><div class="job__emp">' + logo(j, 'job__logo') + '<span>' + ph(j.employer, 'Your organisation') + '</span></div>' +
      '<div class="job__meta">' + meta + '</div>' +
      (j.bullets.length ? '<ul class="adb__bul">' + j.bullets.map(function (b) { return '<li>' + G.esc(b) + '</li>'; }).join('') + '</ul>' : '<p class="adb__ph adb__bulph">Three things a candidate should know appear here.</p>') +
      '<span class="btn btn--lime adb__apply" aria-hidden="true">Apply<span class="arw">→</span></span>';
    var r = reach[j.sectors[0]];
    if (r) {
      var line = 'Roles in ' + j.sectors[0] + ' this week: ' + r.n + '; ' + (r.disc ? 'median disclosed: ' + r.med + ' (' + r.disc + ' of ' + r.n + ' publish one).' : 'none of them publishes a salary, so yours would be the first.');
      if (r.disc && sal) line += ' Listing a range puts this ad in the "salary disclosed" filter that candidates use.';
      else if (!sal) line += ' Add a range to appear in the salary-disclosed filter.';
      reachEl.textContent = line;
    } else reachEl.textContent = '';
  }
  form.addEventListener('input', render);
  form.addEventListener('change', render);
  if (logoIn && window.FileReader) {
    logoIn.addEventListener('change', function () {
      var f = logoIn.files && logoIn.files[0];
      if (!f || !/^image\//.test(f.type) || f.size > 2 * 1024 * 1024) { logoData = ''; render(); if (f) window.GJsay('Use an image under 2 MB'); return; }
      var rd = new FileReader();
      rd.onload = function () { logoData = String(rd.result || ''); render(); };
      rd.readAsDataURL(f);
    });
  }
  var fill = root.querySelector('[data-adb-fill]');
  function example() {
    var first = Object.keys(reach)[0] || '';
    F.title.value = 'Senior Hydrogeologist'; F.org.value = 'Your Company Ltd'; F.loc.value = IE ? 'Galway' : 'Leeds';
    var opt = [].slice.call(F.sector.options).filter(function (o) { return /water/i.test(o.value); })[0];
    F.sector.value = opt ? opt.value : first; F.type.value = 'Permanent'; F.smin.value = '55000'; F.smax.value = '65000';
    F.b1.value = 'Lead groundwater and flood-risk assessments for infrastructure clients';
    F.b2.value = 'A team of eight, hybrid, two days a week on site';
    F.b3.value = 'Chartership supported and paid for';
    render();
  }
  if (fill) fill.addEventListener('click', function () { example(); F.title.focus(); });
  if (toggle && preview) {
    toggle.addEventListener('click', function () {
      var open = root.classList.toggle('is-open');
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false'); toggle.textContent = open ? 'Back to the form' : 'Preview';
      (open ? preview : form).scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  }
  render();
  if (/[?&]ad=demo/.test(window.location.search)) { example(); root.scrollIntoView({ block: 'start' }); }
  window.GJAd = { job: job, example: example };
})();
