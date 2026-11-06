/* demo.js — the demos hub (/demo/). No libraries. The page is complete without it:
   this file only sets the demo links, the A/B switch on phones, the section highlight,
   the one reveal (GM&E access path) and the recordings. */
(() => {
  'use strict';

  // ---- The four demo addresses: change them here (and the matching href fallbacks in demo/index.html). ----
  const WP_VISITOR_URL = 'https://playground.wordpress.net/?mode=seamless&login=no&blueprint-url=https://asset-voyages-redesign.pages.dev/demo-wordpress/blueprint-visitor.json';
  const WP_ADMIN_URL = 'https://playground.wordpress.net/?mode=seamless&blueprint-url=https://asset-voyages-redesign.pages.dev/demo-wordpress/blueprint-admin.json';
  const CUSTOM_URL = 'https://asset-voyages-demo.debanjan186.workers.dev/';
  const CUSTOM_CONSOLE_URL = CUSTOM_URL + 'console';
  const DEMO = { WP_VISITOR_URL, WP_ADMIN_URL, CUSTOM_URL, CUSTOM_CONSOLE_URL };

  const root = document.documentElement;
  root.classList.add('js');
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  document.querySelectorAll('a[data-demo]').forEach((a) => {
    const url = DEMO[a.dataset.demo];
    if (url) a.href = url;
  });
  // deeper Option B pages (e.g. one enquiry in the console) follow CUSTOM_URL too
  document.querySelectorAll('a[data-demo-b]').forEach((a) => {
    const path = a.dataset.demoB;
    if (/^[a-z0-9/_-]+$/i.test(path)) a.href = CUSTOM_URL + path;
  });

  // ---- A/B switch (only shown on narrow screens by CSS) ----
  const sw = document.querySelector('[data-switch]');
  const tasks = document.querySelector('[data-tasks]');
  if (sw && tasks) {
    sw.hidden = false;
    const btns = [...sw.querySelectorAll('button[data-show]')];
    const set = (v) => {
      tasks.dataset.view = v;
      btns.forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.show === v)));
    };
    btns.forEach((b) => b.addEventListener('click', () => set(b.dataset.show)));
  }

  // ---- section highlight in the sticky strip ----
  const links = [...document.querySelectorAll('[data-mini] a[href^="#"]')];
  const byId = new Map(links.map((a) => [a.getAttribute('href').slice(1), a]));
  const sections = [...byId.keys()].map((id) => document.getElementById(id)).filter(Boolean);
  if ('IntersectionObserver' in window && sections.length) {
    let current = null;
    const strip = document.querySelector('.mini__in');
    const mark = (a) => {
      if (a === current) return;
      if (current) current.removeAttribute('aria-current');
      current = a;
      if (a) a.setAttribute('aria-current', 'true');
      if (strip && strip.scrollWidth > strip.clientWidth) {
        // keep the marked link in view; with nothing marked (top of page) the strip starts at its first link
        const x = a ? a.offsetLeft - strip.offsetLeft - (strip.clientWidth - a.offsetWidth) / 2 : 0;
        strip.scrollTo({ left: Math.max(0, x), behavior: reduce || !a ? 'auto' : 'smooth' });
      }
    };
    const update = () => {
      const atEnd = window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 4;
      const line = Math.min(160, window.innerHeight * 0.3);
      const passed = sections.filter((s) => !s.hidden && s.getBoundingClientRect().top <= line);
      const shown = sections.filter((s) => !s.hidden);
      const top = atEnd ? shown[shown.length - 1] : passed[passed.length - 1];
      mark(top ? byId.get(top.id) : null);
    };
    const io = new IntersectionObserver((entries) => {
      update();
    }, { rootMargin: '-72px 0px -55% 0px' });
    let tick = 0;
    window.addEventListener('scroll', () => { if (!tick) tick = requestAnimationFrame(() => { tick = 0; update(); }); }, { passive: true });
    sections.forEach((s) => io.observe(s));
    if (strip) {
      // edge fade: tells a phone reader more sections sit off-screen
      const edges = () => {
        const max = strip.scrollWidth - strip.clientWidth;
        const l = strip.scrollLeft > 4, r = max - strip.scrollLeft > 4;
        if (l && r) strip.dataset.more = 'both'; else if (r) strip.dataset.more = 'right'; else if (l) strip.dataset.more = 'left'; else delete strip.dataset.more;
      };
      strip.scrollLeft = 0;
      strip.addEventListener('scroll', edges, { passive: true });
      window.addEventListener('resize', edges);
      edges();
    }
  }

  // ---- the one reveal: the GM&E access path draws itself once ----
  const flow = document.querySelector('[data-flow]');
  if (flow && !reduce && 'IntersectionObserver' in window) {
    const r = flow.getBoundingClientRect();
    if (r.top > window.innerHeight) {
      flow.setAttribute('data-armed', '');
      const fio = new IntersectionObserver((entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          requestAnimationFrame(() => flow.classList.add('is-in'));
          fio.disconnect();
        }
      }, { threshold: 0.25 });
      fio.observe(flow);
      // never leave it half-drawn (print, odd viewers)
      window.addEventListener('beforeprint', () => flow.classList.add('is-in'));
    }
  }

  // ---- recordings: the markup is rendered from media/manifest.json (a link to each announced file,
  // no fallback text); this upgrades each link to a player and drops anything the manifest no longer announces ----
  const recs = [...document.querySelectorAll('[data-rec]')];
  const fail = (fig, msg) => {
    const v = fig.querySelector('video');
    if (v) v.remove();
    const empty = fig.querySelector('[data-rec-empty]');
    if (empty) empty.hidden = false;
    const m = fig.querySelector('[data-rec-msg]');
    if (m && msg) m.textContent = msg;
  };
  const mount = (fig) => {
    const name = fig.dataset.rec;
    const frame = fig.querySelector('[data-rec-frame]');
    const empty = fig.querySelector('[data-rec-empty]');
    const v = document.createElement('video');
    v.controls = true;
    v.preload = 'metadata';
    v.playsInline = true;
    v.poster = 'media/' + name + '.jpg';
    v.setAttribute('aria-label', fig.querySelector('figcaption')?.textContent || 'Recording');
    const s = document.createElement('source');
    s.src = 'media/' + name + '.mp4';
    s.type = 'video/mp4';
    s.addEventListener('error', () => fail(fig, 'This recording could not be loaded just now.'));
    v.addEventListener('error', () => fail(fig, 'This recording could not be loaded just now.'));
    v.appendChild(s);
    if (empty) empty.hidden = true;
    const file = fig.querySelector('[data-rec-file]');
    if (file) file.remove();
    frame.prepend(v);
  };
  if (recs.length && window.fetch) {
    fetch('media/manifest.json', { cache: 'no-store' })
      .then((r) => (r.ok ? r.json() : {}))
      .then((m) => {
        const ready = recs.filter((fig) => m && m[fig.dataset.rec] === true);
        recs.filter((fig) => !ready.includes(fig)).forEach((fig) => fig.remove());
        const sec = document.querySelector('[data-recs]'), nav = document.querySelector('[data-rec-nav]');
        if (sec) sec.hidden = !ready.length;
        if (nav) nav.hidden = !ready.length;
        if (!ready.length) return;
        ready.forEach((fig) => { fig.hidden = false; mount(fig); });
        if (ready.length === 1 && sec) sec.classList.add('recs--one');
      })
      .catch(() => {});
  }
})();
