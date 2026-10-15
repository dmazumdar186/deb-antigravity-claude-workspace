/* MISB concept — hand-rolled motion, zero dependencies, no globals. */
(() => {
  'use strict';
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const narrow = () => innerWidth < 800;

  /* ---------- header, menu ---------- */
  const header = $('[data-header]'), menu = $('[data-menu]'), toggle = $('[data-menu-toggle]');
  const isMenuNarrow = () => innerWidth <= 1050;
  if (header) {
    const onScroll = () => header.classList.toggle('is-scrolled', scrollY > 12);
    addEventListener('scroll', onScroll, { passive: true }); onScroll();
  }
  if (menu && toggle) {
    const setMenu = (open) => {
      menu.classList.toggle('is-open', open);
      toggle.setAttribute('aria-expanded', String(open));
      toggle.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
      menu.inert = !open && isMenuNarrow();
      if (open) { const a = menu.querySelector('a'); if (a) a.focus(); }
      else if (document.activeElement && menu.contains(document.activeElement)) toggle.focus();
    };
    toggle.addEventListener('click', () => setMenu(!menu.classList.contains('is-open')));
    menu.addEventListener('click', (e) => { if (e.target.closest('a') && menu.classList.contains('is-open')) setMenu(false); });
    addEventListener('keydown', (e) => { if (e.key === 'Escape' && menu.classList.contains('is-open')) setMenu(false); });
    addEventListener('resize', () => { menu.inert = isMenuNarrow() && !menu.classList.contains('is-open'); });
    menu.inert = isMenuNarrow();
  }

  /* ---------- leaflet: tri-fold that opens, then turns pages ---------- */
  const lf = $('[data-leaflet]');
  if (lf) {
    const pages = $$('.lf-page', lf), P = pages.length;
    const prev = $('[data-lf-prev]', lf), next = $('[data-lf-next]', lf), dots = $('[data-lf-dots]', lf), count = $('[data-lf-count]', lf), scene = $('.lf-scene', lf);
    let s = 0, opened = false, timer = null, hold = 0;
    const setZ = () => pages.forEach((p, i) => { const j = i + 1; p.style.zIndex = String(p.classList.contains('is-flipped') ? 5 + j : 5 + P - j + 1); });
    const dotBtns = [];
    if (dots) for (let i = 0; i < P; i++) {
      const b = document.createElement('button'); b.type = 'button'; b.setAttribute('aria-label', `Spread ${i + 1} of ${P}`); b.appendChild(document.createElement('i'));
      b.addEventListener('click', () => { go(i); bump(); }); dots.appendChild(b); dotBtns.push(b);
    }
    const paint = () => {
      dotBtns.forEach((b, i) => b.setAttribute('aria-current', i === s ? 'true' : 'false'));
      if (count) count.textContent = `${s + 1} / ${P}`;
      lf.dataset.spread = String(s);
    };
    const go = (n) => {
      s = ((n % P) + P) % P;
      let k = 0;
      pages.forEach((p, i) => {
        const want = i < s, has = p.classList.contains('is-flipped');
        if (want === has) return;
        p.style.transitionDelay = reduced ? '0s' : `${k * 70}ms`; k++;
        p.classList.toggle('is-flipped', want); p.classList.add('is-turning');
        setTimeout(() => { p.classList.remove('is-turning'); p.style.transitionDelay = ''; }, reduced ? 20 : 950 + k * 70);
      });
      setZ(); paint();
    };
    const openNow = () => {
      if (opened) return; opened = true;
      lf.classList.remove('is-closed', 'is-cover'); lf.classList.add('is-open');
      setZ(); paint(); start();
    };
    const openSeq = () => {
      if (opened) return;
      if (reduced || narrow()) { openNow(); return; }
      lf.classList.remove('is-closed'); lf.classList.add('is-cover');
      setTimeout(openNow, 900);
    };
    /* auto-advance */
    const tick = () => { if (Date.now() < hold || document.hidden) return; go(s + 1); };
    const start = () => { if (!timer && !reduced) timer = setInterval(tick, 4500); };
    const stop = () => { clearInterval(timer); timer = null; };
    const bump = () => { hold = Date.now() + 8000; };
    if (prev) prev.addEventListener('click', () => { openNow(); go(s - 1); bump(); });
    if (next) next.addEventListener('click', () => { openNow(); go(s + 1); bump(); });
    lf.addEventListener('mouseenter', () => { hold = Infinity; });
    lf.addEventListener('mouseleave', () => { hold = 0; });
    lf.addEventListener('focusin', () => { hold = Infinity; });
    lf.addEventListener('focusout', () => { hold = Date.now() + 2000; });
    lf.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowRight') { e.preventDefault(); openNow(); go(s + 1); bump(); }
      else if (e.key === 'ArrowLeft') { e.preventDefault(); openNow(); go(s - 1); bump(); }
    });
    /* swipe / drag */
    if (scene) {
      let x0 = null, y0 = null;
      scene.addEventListener('pointerdown', (e) => { x0 = e.clientX; y0 = e.clientY; bump(); }, { passive: true });
      const end = (e) => {
        if (x0 === null) return;
        const dx = e.clientX - x0, dy = e.clientY - y0; x0 = null;
        if (Math.abs(dx) > 36 && Math.abs(dx) > Math.abs(dy)) { openNow(); go(dx < 0 ? s + 1 : s - 1); bump(); }
      };
      scene.addEventListener('pointerup', end); scene.addEventListener('pointercancel', () => { x0 = null; });
    }
    /* scroll-driven: never stuck closed */
    const onScroll = () => { if (!opened && scrollY > 8) openNow(); };
    addEventListener('scroll', onScroll, { passive: true });
    addEventListener('visibilitychange', () => { if (document.hidden) stop(); else if (opened) start(); });
    /* initial state */
    if (reduced) { lf.classList.add('no-anim'); openNow(); }
    else { setZ(); paint(); setTimeout(openSeq, 600); }
  }

  /* ---------- program filter ---------- */
  const tabs = $$('[data-filter]'), cards = $$('[data-cat]');
  if (tabs.length && cards.length) tabs.forEach((t) => t.addEventListener('click', () => {
    const f = t.dataset.filter;
    tabs.forEach((x) => x.setAttribute('aria-pressed', String(x === t)));
    cards.forEach((c) => c.classList.toggle('is-hidden', f !== 'all' && !c.dataset.cat.split(' ').includes(f)));
  }));

  /* ---------- counters ---------- */
  const counters = $$('[data-count]');
  const runCount = (el) => {
    const end = parseInt(el.dataset.count, 10), pre = el.dataset.prefix || '', suf = el.dataset.suffix || '';
    if (reduced) { el.textContent = pre + end + suf; return; }
    const t0 = performance.now(), d = 1400;
    const step = (t) => { const p = Math.min(1, (t - t0) / d), v = Math.round(end * (1 - Math.pow(1 - p, 3))); el.textContent = pre + v + suf; if (p < 1) requestAnimationFrame(step); };
    requestAnimationFrame(step);
  };
  if (counters.length) {
    if ('IntersectionObserver' in window) {
      const io = new IntersectionObserver((es) => es.forEach((e) => { if (e.isIntersecting) { runCount(e.target); io.unobserve(e.target); } }), { threshold: .3 });
      counters.forEach((c) => io.observe(c));
      setTimeout(() => counters.forEach((c) => { if (c.textContent.trim() === '0') runCount(c); }), 3000);
    } else counters.forEach(runCount);
  }

  /* ---------- lightbox ---------- */
  const lb = $('[data-lightbox]'), shots = $$('[data-shot]');
  if (lb && shots.length && typeof lb.showModal === 'function') {
    const img = $('img', lb), cap = $('[data-lb-cap]', lb); let i = 0;
    const show = (n) => { i = ((n % shots.length) + shots.length) % shots.length; const b = shots[i]; if (img) { img.src = b.dataset.shot; img.alt = b.dataset.alt || ''; } if (cap) cap.textContent = b.dataset.cap || ''; };
    shots.forEach((b, n) => b.addEventListener('click', () => { show(n); lb.showModal(); }));
    const close = $('[data-lb-close]', lb), pv = $('[data-lb-prev]', lb), nx = $('[data-lb-next]', lb);
    if (close) close.addEventListener('click', () => lb.close());
    if (pv) pv.addEventListener('click', () => show(i - 1));
    if (nx) nx.addEventListener('click', () => show(i + 1));
    lb.addEventListener('click', (e) => { if (e.target === lb) lb.close(); });
    lb.addEventListener('keydown', (e) => { if (e.key === 'ArrowRight') show(i + 1); else if (e.key === 'ArrowLeft') show(i - 1); });
  }

  /* ---------- mobile bottom bar: only once the hero CTAs have scrolled away ---------- */
  const mbar = $('[data-mbar]'), heroCtas = $('[data-hero-ctas]');
  if (mbar && heroCtas && 'IntersectionObserver' in window) {
    new IntersectionObserver((es) => es.forEach((e) => mbar.classList.toggle('is-on', !e.isIntersecting && e.boundingClientRect.top < 0)), { threshold: 0 }).observe(heroCtas);
  } else if (mbar) mbar.classList.add('is-on');

  /* ---------- reveal ---------- */
  const reveals = $$('.reveal');
  const showAll = () => reveals.forEach((el) => el.classList.add('is-in'));
  if (reveals.length) {
    if (narrow() || reduced || !('IntersectionObserver' in window)) showAll();
    else {
      const io = new IntersectionObserver((es) => es.forEach((e) => { if (e.isIntersecting) { e.target.classList.add('is-in'); io.unobserve(e.target); } }), { threshold: .01, rootMargin: '0px 0px 8% 0px' });
      reveals.forEach((el) => io.observe(el));
      setTimeout(showAll, 2500);
    }
  }
})();
