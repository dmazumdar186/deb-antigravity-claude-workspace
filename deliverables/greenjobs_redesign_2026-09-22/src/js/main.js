'use strict';
/* Shared page behaviour: theme, header, menu, reveals, marquee, saved jobs,
   edition switch, home search type-ahead, demo forms, share, toast, data
   loading. Every block bails out quietly when its markup is absent. */
(function () {
  var G = window.GJ, doc = document, root = doc.documentElement, body = doc.body;
  var ED = body.getAttribute('data-edition') || 'ie';
  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)');
  var $ = function (s, c) { return (c || doc).querySelector(s); };
  var $$ = function (s, c) { return Array.prototype.slice.call((c || doc).querySelectorAll(s)); };
  function store(k, v) {
    try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (e) { return null; }
  }

  /* ------------------------------------------------ toast */
  var toast = doc.createElement('div');
  toast.className = 'toast'; toast.setAttribute('role', 'status'); toast.setAttribute('aria-live', 'polite');
  body.appendChild(toast);
  var toastT;
  function say(msg) {
    toast.textContent = msg; toast.classList.add('is-on');
    clearTimeout(toastT); toastT = setTimeout(function () { toast.classList.remove('is-on'); }, 2200);
  }

  /* ------------------------------------------------ theme */
  $$('[data-theme-toggle]').forEach(function (b) {
    b.addEventListener('click', function () {
      var next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
      root.setAttribute('data-theme', next); store('gj-theme', next);
      b.setAttribute('aria-label', next === 'dark' ? 'Switch to light theme' : 'Switch to dark theme');
    });
  });

  /* ------------------------------------------------ header + menu */
  var hdr = $('[data-header]');
  if (hdr) {
    var onScroll = function () { hdr.classList.toggle('is-stuck', window.scrollY > 8); };
    onScroll(); window.addEventListener('scroll', onScroll, { passive: true });
  }
  var menu = $('[data-menu]');
  $$('[data-menu-open]').forEach(function (b) { b.addEventListener('click', function () { if (menu) menu.showModal(); }); });
  $$('[data-menu-close]').forEach(function (b) { b.addEventListener('click', function () { if (menu) menu.close(); }); });
  if (menu) menu.addEventListener('click', function (e) { if (e.target === menu) menu.close(); });

  /* ------------------------------------------------ edition switch memory */
  /* The switch carries the current page, query and hash to the other edition when that
     edition has the same page (the server-rendered href is the ground truth for "exists":
     it points at the same file when it does, at that edition's list or home when it does not). */
  var here = (window.location.pathname.split('/' + ED + '/')[1] || '').replace(/\/$/, '/index.html') || 'index.html';
  $$('[data-edswitch]').forEach(function (a) {
    var to = a.getAttribute('data-edswitch');
    a.addEventListener('click', function () { store('gj-edition', to); });
    if (to === ED) return;
    var target = (a.getAttribute('href') || '').split(/[?#]/)[0], rel = (target.split('/' + to + '/')[1] || '');
    if (rel && rel === here && (window.location.search || window.location.hash)) a.setAttribute('href', target + window.location.search + window.location.hash);
  });
  store('gj-edition', ED);

  /* ------------------------------------------------ reveals */
  var revs = $$('.reveal');
  if (revs.length && 'IntersectionObserver' in window && !reduce.matches) {
    var io = new IntersectionObserver(function (es) {
      es.forEach(function (e) { if (e.isIntersecting) { e.target.classList.remove('pre'); io.unobserve(e.target); } });
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0.05 });
    /* Only elements below the first viewport are ever hidden, so nothing in
       view depends on the observer firing (headless renderers, print). */
    revs.forEach(function (el, i) {
      el.style.setProperty('--i', String(i % 8));
      if (el.getBoundingClientRect().top > window.innerHeight) { el.classList.add('pre'); io.observe(el); }
    });
    setTimeout(function () { revs.forEach(function (el) { el.classList.remove('pre'); }); }, 4000);
  }

  /* ------------------------------------------------ marquee */
  $$('[data-marq]').forEach(function (m) {
    var b = $('[data-marq-pause]', m.parentNode);
    if (!b) return;
    b.addEventListener('click', function () {
      var on = m.classList.toggle('is-paused');
      b.setAttribute('aria-pressed', on ? 'true' : 'false'); b.textContent = on ? 'Play' : 'Pause';
    });
  });

  /* ------------------------------------------------ saved jobs */
  var SKEY = 'gj-saved-' + ED;
  function saved() { try { var v = JSON.parse(store(SKEY) || '[]'); return Array.isArray(v) ? v : []; } catch (e) { return []; } }
  function paintSaves(scope) {
    var ids = saved();
    $$('[data-save]', scope).forEach(function (b) {
      var on = ids.indexOf(b.getAttribute('data-save')) >= 0;
      b.setAttribute('aria-pressed', on ? 'true' : 'false');
      b.setAttribute('aria-label', (on ? 'Saved: ' : 'Save: ') + b.getAttribute('data-title'));
    });
    $$('[data-saved-count]').forEach(function (el) { el.textContent = String(ids.length); });
  }
  doc.addEventListener('click', function (e) {
    var b = e.target.closest('[data-save]');
    if (!b) return;
    e.preventDefault();
    var id = b.getAttribute('data-save'), ids = saved(), i = ids.indexOf(id);
    if (i >= 0) ids.splice(i, 1); else ids.push(id);
    store(SKEY, JSON.stringify(ids));
    paintSaves();
    say(i >= 0 ? 'Removed from saved roles' : 'Saved — find it under Saved on the jobs page');
    if (i < 0) track('save_role', { job_id: id, src_page: window.location.pathname });
    doc.dispatchEvent(new CustomEvent('gj:saved', { detail: ids }));
  });
  paintSaves();
  window.GJSaved = { list: saved, paint: paintSaves };

  /* ------------------------------------------------ data loading (embedded or fetched) */
  var dataP = null;
  window.GJData = function () {
    if (dataP) return dataP;
    var inline = $('#gj-data');
    if (inline) { try { dataP = Promise.resolve(JSON.parse(inline.textContent)); return dataP; } catch (e) { /* fall through to fetch */ } }
    var url = body.getAttribute('data-data');
    dataP = url ? fetch(url).then(function (r) { if (!r.ok) throw new Error('data ' + r.status); return r.json(); }) : Promise.resolve({ jobs: [] });
    return dataP;
  };

  /* ------------------------------------------------ home search with type-ahead */
  var sform = $('[data-search]');
  if (sform) {
    var qIn = $('input[name="q"]', sform), locIn = $('input[name="loc"]', sform), ta = $('[data-ta]', sform);
    var jobs = null, sel = -1, items = [];
    function close() { ta.hidden = true; ta.innerHTML = ''; items = []; sel = -1; qIn.setAttribute('aria-expanded', 'false'); }
    function paint() {
      if (!items.length) return close();
      ta.innerHTML = items.map(function (it, i) {
        return '<button type="button" role="option" id="ta-' + i + '" aria-selected="' + (i === sel) + '" data-i="' + i + '"><span class="ta__k">' + it.kind + '</span><b>' + G.esc(it.text) + '</b><small>' + G.esc(it.sub) + '</small></button>';
      }).join('');
      ta.hidden = false; qIn.setAttribute('aria-expanded', 'true');
      qIn.setAttribute('aria-activedescendant', sel >= 0 ? 'ta-' + sel : '');
    }
    function pick(it) {
      if (it.kind === 'place') { locIn.value = it.text; qIn.value = ''; }
      else qIn.value = it.text;
      close(); sform.requestSubmit ? sform.requestSubmit() : sform.submit();
    }
    function update() {
      if (!jobs || doc.activeElement !== qIn) return; /* data may arrive after blur: never paint then */
      items = G.suggest(jobs, qIn.value.trim(), 7); sel = -1; paint();
    }
    qIn.addEventListener('focus', function () { window.GJData().then(function (d) { jobs = d.jobs; update(); }); });
    qIn.addEventListener('input', update);
    qIn.addEventListener('keydown', function (e) {
      if (ta.hidden) return;
      if (!items.length) return;
      if (e.key === 'ArrowDown') { sel = (sel + 1) % items.length; paint(); e.preventDefault(); }
      else if (e.key === 'ArrowUp') { sel = (sel - 1 + items.length) % items.length; paint(); e.preventDefault(); }
      else if (e.key === 'Enter' && sel >= 0) { e.preventDefault(); pick(items[sel]); }
      else if (e.key === 'Escape') close();
    });
    ta.addEventListener('click', function (e) { var b = e.target.closest('[data-i]'); if (b) pick(items[+b.getAttribute('data-i')]); });
    doc.addEventListener('click', function (e) { if (!sform.contains(e.target)) close(); });
    sform.addEventListener('submit', function (e) {
      e.preventDefault();
      var st = { q: qIn.value.trim(), loc: locIn.value.trim() };
      window.location.href = sform.getAttribute('action') + G.toQuery(st);
    });
  }

  /* ------------------------------------------------ consent-gated event layer
     track(name, props) is a no-op unless the visitor switched Analytics on in
     the cookie settings AND a provider registered itself as window.GJAnalytics
     (a function taking (name, props)). No provider ships with the demo, so
     nothing is ever sent; the data-ev attributes below name the events the
     dashboard's "Event spec for launch" lists. */
  function consentOn() {
    try { var c = JSON.parse(localStorage.getItem('gj-consent') || 'null'); return !!(c && c.analytics); } catch (e) { return false; }
  }
  function track(name, props) {
    if (!name || !consentOn() || typeof window.GJAnalytics !== 'function') return false;
    try { window.GJAnalytics(name, props || {}); } catch (e) { /* a provider fault never breaks the page */ }
    return true;
  }
  function evProps(el) {
    var p = { src_page: window.location.pathname }, a = el.attributes, i;
    for (i = 0; i < a.length; i++) if (a[i].name.indexOf('data-ev-') === 0) p[a[i].name.slice(8).replace(/-/g, '_')] = a[i].value;
    if (p.job) { p.job_id = p.job; delete p.job; }
    return p;
  }
  doc.addEventListener('click', function (e) {
    var el = e.target.closest('a[data-ev], button[data-ev]:not([type="submit"])');
    if (el) track(el.getAttribute('data-ev'), evProps(el));
  });
  doc.addEventListener('submit', function (e) {
    var f = e.target, el = f.getAttribute && f.getAttribute('data-ev') ? f : (f.querySelector ? f.querySelector('[type="submit"][data-ev]') : null);
    if (el) track(el.getAttribute('data-ev'), evProps(el));
  });
  window.GJTrack = track;
  if (body.getAttribute('data-page') === 'job') { var jv = $('[data-ev="apply_click"][data-ev-job]'); track('job_view', { job_id: jv ? jv.getAttribute('data-ev-job') : '', src_page: window.location.pathname }); }

  /* ------------------------------------------------ closed roles (job page) */
  var aside = $('.job__aside[data-closing]');
  if (aside) {
    var closing = aside.getAttribute('data-closing'), closeMs = closing ? Date.parse(closing) : NaN;
    if (!isNaN(closeMs) && closeMs + 864e5 <= Date.now()) {
      $$('a[data-apply]').forEach(function (a) {
        var s = doc.createElement('span'); s.className = 'job__closed'; s.setAttribute('role', 'status'); s.textContent = 'This role has closed';
        a.parentNode.replaceChild(s, a);
      });
    }
  }

  /* ------------------------------------------------ demo forms (never a fake success) */
  $$('[data-demo-form]').forEach(function (f) {
    f.addEventListener('submit', function (e) {
      e.preventDefault();
      var n = $('[data-demo-note]', f), pre = $('[data-demo-pre]', f);
      if (pre) pre.hidden = true;
      if (n) { n.hidden = false; n.focus(); }
    });
  });

  /* ------------------------------------------------ rail scroll cue, blank logo tiles (dates are rendered server-side by build_site.date_long) */
  $$('[data-rail-home]').forEach(function (a) {
    var r = $('.rail', a); if (!r) return;
    var end = function () { a.classList.toggle('is-over', r.scrollHeight > r.clientHeight + 12); a.classList.toggle('is-end', r.scrollHeight - r.scrollTop - r.clientHeight < 12); };
    r.addEventListener('scroll', end, { passive: true }); window.addEventListener('resize', end); end();
  });
  $$('[data-marq]').forEach(function (m) { m.classList.add('is-js'); });
  $$('.emp img').forEach(function (img) {
    var blank = function () { if (!img.naturalWidth || img.naturalWidth < 8 || img.naturalHeight < 8) img.parentNode.classList.add('is-blank'); else img.setAttribute('data-loaded', ''); };
    img.addEventListener('error', function () { img.parentNode.classList.add('is-blank'); });
    if (img.complete) blank(); else img.addEventListener('load', blank);
  });

  /* ------------------------------------------------ share */
  $$('[data-share]').forEach(function (b) {
    b.addEventListener('click', function () {
      var data = { title: doc.title, url: window.location.href };
      if (navigator.share) navigator.share(data).catch(function () { /* user dismissed the sheet: nothing to report */ });
      else if (navigator.clipboard) navigator.clipboard.writeText(data.url).then(function () { say('Link copied'); }, function () { say('Copy failed — use the address bar'); });
      else say(data.url);
    });
  });

  /* ------------------------------------------------ region map (shared by home + jobs) */
  var tip = doc.createElement('div'); tip.className = 'tip'; tip.setAttribute('role', 'tooltip'); body.appendChild(tip);
  window.GJTip = {
    show: function (x, y, html) { tip.innerHTML = html; tip.style.left = x + 'px'; tip.style.top = y + 'px'; tip.classList.add('is-on'); },
    hide: function () { tip.classList.remove('is-on'); }
  };
  /* Listeners bind once per region (data-bound); counts, onPick and labelFn
     live on the svg and are refreshed on every call so re-renders never stack
     handlers. The count <text> is updated (or removed) on every call too. */
  window.GJMap = function (svg, counts, onPick, labelFn) {
    if (!svg) return;
    var S = svg._gj || (svg._gj = {});
    S.counts = counts || {}; S.onPick = onPick; S.labelFn = labelFn;
    var max = 0;
    Object.keys(S.counts).forEach(function (k) { if (S.counts[k] > max) max = S.counts[k]; });
    $$('.gmap__r', svg).forEach(function (g) {
      var name = g.getAttribute('data-region'), n = S.counts[name] || 0;
      g.setAttribute('data-n', String(n));
      g.setAttribute('data-lvl', n === 0 ? '0' : n >= max * 0.6 ? '3' : n >= max * 0.25 ? '2' : '1');
      g.setAttribute('aria-label', name + ': ' + n + (n === 1 ? ' role' : ' roles'));
      /* Zero-count regions keep a muted "0" and the is-zero fill rather than reading as holes (visual 12). */
      g.classList.toggle('is-zero', n === 0);
      var text = g.querySelector('text');
      if (!text && g.getAttribute('data-cx')) {
        text = doc.createElementNS('http://www.w3.org/2000/svg', 'text');
        text.setAttribute('x', g.getAttribute('data-cx')); text.setAttribute('y', g.getAttribute('data-cy')); text.setAttribute('dy', '4');
        g.appendChild(text);
      }
      if (text) { text.textContent = String(n); text.classList.toggle('is-zero', n === 0); }
      if (g.getAttribute('data-bound')) return;
      g.setAttribute('data-bound', '1');
      g.setAttribute('role', 'button'); g.setAttribute('tabindex', '0');
      var html = function () { var c = S.counts[name] || 0; return '<b>' + G.esc(name) + '</b><span>' + (S.labelFn ? S.labelFn(c) : c + (c === 1 ? ' live role' : ' live roles')) + '</span>'; };
      g.addEventListener('mousemove', function (e) { window.GJTip.show(e.clientX, e.clientY, html()); });
      g.addEventListener('mouseleave', window.GJTip.hide);
      g.addEventListener('focus', function () { var r = g.getBoundingClientRect(); window.GJTip.show(r.left + r.width / 2, r.top + r.height / 2, html()); });
      g.addEventListener('blur', window.GJTip.hide);
      var act = function (e) { e.preventDefault(); if (S.onPick) S.onPick(name, S.counts[name] || 0); };
      g.addEventListener('click', act);
      g.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') act(e); });
    });
  };
  var homeMap = $('[data-home-map]');
  if (homeMap) {
    var counts = {};
    try { counts = JSON.parse(homeMap.getAttribute('data-counts') || '{}'); } catch (e) { counts = {}; }
    var jobsHref = homeMap.getAttribute('data-jobs');
    window.GJMap($('svg', homeMap), counts, function (name) { window.location.href = jobsHref + G.toQuery({ loc: name }); });
  }
  /* Server-rendered rows (home, sector pages): split "€… (advertised in euros, about £…)" into a salary chip plus a muted "advertised in €" chip, as jobs.js does for the board. */
  var FX_SYM = { euros: '\u20ac', sterling: '\u00a3', pounds: '\u00a3' };
  $$('.row .tag--sal, .role .tag--sal').forEach(function (chip) {
    var m = /^(.*) \((?:paid|advertised) in ([^,]+), about (.+)\)$/.exec(chip.textContent.trim());
    if (!m) return;
    chip.innerHTML = '<span class="tag__t">' + G.esc(m[1]) + '</span>';
    var fx = doc.createElement('span'); fx.className = 'tag tag--fx'; fx.title = 'Advertised in ' + m[2] + ', about ' + m[3];
    fx.innerHTML = '<b class="tag__cur" aria-hidden="true">' + G.esc(FX_SYM[m[2]] || m[2]) + '</b><span class="tag__t">advertised in ' + G.esc(m[2]) + ' <s>\u2248 ' + G.esc(m[3]) + '</s></span>';
    chip.insertAdjacentElement('afterend', fx);
  });
  /* Footer social buttons: the build emits a placeholder circle; draw the real mark for the host. */
  var SOCIAL = [
    [/facebook\.com/i, 'Facebook', 'M13.5 22v-8h2.7l.4-3.2h-3.1V8.8c0-.9.3-1.6 1.6-1.6h1.7V4.4c-.3 0-1.3-.1-2.5-.1-2.5 0-4.1 1.5-4.1 4.2v2.3H7.4V14h2.8v8z'],
    [/(twitter|x)\.com/i, 'X (Twitter)', 'M17.5 3h3l-6.8 7.8L21.8 21h-6.2l-4.9-6.4L5.1 21h-3l7.3-8.3L1.8 3h6.4l4.4 5.8L17.5 3zm-1.1 16.2h1.7L7 4.7H5.2l11.2 14.5z'],
    [/linkedin\.com/i, 'LinkedIn', 'M6.5 8.5H3V21h3.5V8.5zM4.75 3a2 2 0 100 4 2 2 0 000-4zM21 13.3c0-3.4-1.8-5.1-4.3-5.1-2 0-2.9 1.1-3.4 1.9V8.5H9.9V21h3.4v-6.9c0-1.8.6-2.9 2.1-2.9 1.4 0 2.1.9 2.1 2.9V21H21v-7.7z'],
    [/instagram\.com/i, 'Instagram', 'M12 7.3a4.7 4.7 0 100 9.4 4.7 4.7 0 000-9.4zm0 7.7a3 3 0 110-6 3 3 0 010 6zm6-7.9a1.1 1.1 0 11-2.2 0 1.1 1.1 0 012.2 0zM12 3c-2.4 0-2.7 0-3.7.1C5 3.2 3.2 5 3.1 8.3 3 9.3 3 9.6 3 12s0 2.7.1 3.7c.1 3.3 1.9 5.1 5.2 5.2 1 .1 1.3.1 3.7.1s2.7 0 3.7-.1c3.3-.1 5.1-1.9 5.2-5.2.1-1 .1-1.3.1-3.7s0-2.7-.1-3.7C20.8 5 19 3.2 15.7 3.1 14.7 3 14.4 3 12 3zm0 1.6c2.4 0 2.6 0 3.6.1 2.4.1 3.6 1.3 3.7 3.7.1 1 .1 1.2.1 3.6s0 2.6-.1 3.6c-.1 2.4-1.3 3.6-3.7 3.7-1 .1-1.2.1-3.6.1s-2.6 0-3.6-.1c-2.4-.1-3.6-1.3-3.7-3.7-.1-1-.1-1.2-.1-3.6s0-2.6.1-3.6c.1-2.4 1.3-3.6 3.7-3.7 1-.1 1.2-.1 3.6-.1z']
  ];
  $$('.ftr__social a').forEach(function (a) {
    var hit = null; SOCIAL.forEach(function (s) { if (!hit && s[0].test(a.href)) hit = s; });
    if (!hit) { a.remove(); return; }
    a.setAttribute('aria-label', 'GreenJobs on ' + hit[1]);
    a.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="' + hit[2] + '"/></svg>';
  });
  $$('.ftr__social').forEach(function (w) { if (!w.children.length) w.remove(); });
  /* Irish landline in the footer: dial-able from abroad (the scraped number is the domestic form). */
  $$('.ftr a[href^="tel:0"]').forEach(function (a) {
    var li = a.closest('li'); if (li && /ireland/i.test(li.textContent)) a.setAttribute('href', a.getAttribute('href').replace(/^tel:0/, 'tel:+353'));
  });
  window.GJsay = say;
})();
