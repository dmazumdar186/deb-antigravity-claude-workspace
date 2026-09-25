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
  $$('[data-edswitch]').forEach(function (a) {
    a.addEventListener('click', function () { store('gj-edition', a.getAttribute('data-edswitch')); });
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

  /* ------------------------------------------------ demo forms (never a fake success) */
  $$('[data-demo-form]').forEach(function (f) {
    f.addEventListener('submit', function (e) {
      e.preventDefault();
      var n = $('[data-demo-note]', f);
      if (n) { n.hidden = false; n.focus(); }
    });
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
      var text = g.querySelector('text');
      if (n > 0) {
        if (!text) {
          text = doc.createElementNS('http://www.w3.org/2000/svg', 'text');
          text.setAttribute('x', g.getAttribute('data-cx')); text.setAttribute('y', g.getAttribute('data-cy')); text.setAttribute('dy', '4');
          g.appendChild(text);
        }
        text.textContent = String(n);
      } else if (text) g.removeChild(text);
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
  window.GJsay = say;
})();

// Employer "reveal" cards: preview on hover at desktop (a closed <details> hides its body at the UA level, so CSS alone cannot).
(function(){
  if(!matchMedia('(hover:hover)').matches)return;
  document.querySelectorAll('details.reveal').forEach(function(d){
    var byHover=false;
    d.addEventListener('mouseenter',function(){if(!d.open){d.open=true;byHover=true;}});
    d.addEventListener('mouseleave',function(){if(byHover){d.open=false;byHover=false;}});
    d.addEventListener('toggle',function(){if(!d.open)byHover=false;});
    d.querySelector('summary').addEventListener('click',function(){if(byHover){byHover=false;}});
  });
})();

// Employers footage band: poster only under reduced motion / Save-Data; paused off-screen.
(function(){
  var v=document.querySelector('[data-empband] video'); if(!v)return;
  var save=navigator.connection&&navigator.connection.saveData;
  if(save||matchMedia('(prefers-reduced-motion: reduce)').matches){v.removeAttribute('autoplay');v.pause();v.preload='none';return;}
  if('IntersectionObserver' in window)new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting)v.play().catch(function(){});else v.pause();});},{threshold:.1}).observe(v);
})();
