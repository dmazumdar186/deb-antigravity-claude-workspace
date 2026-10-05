/* Midas concept — hand-rolled motion, zero dependencies, no globals. */
(() => {
  'use strict';
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ---------- header, menu ---------- */
  const header = $('[data-header]'), menu = $('[data-menu]'), toggle = $('[data-menu-toggle]');
  const isNarrow = () => innerWidth <= 1050;
  if (header) {
    const onScroll = () => header.classList.toggle('is-scrolled', scrollY > 12);
    addEventListener('scroll', onScroll, { passive: true }); onScroll();
  }
  if (menu && toggle) {
    const setMenu = (open) => {
      menu.classList.toggle('is-open', open);
      toggle.setAttribute('aria-expanded', String(open));
      toggle.setAttribute('aria-label', open ? 'Fermer le menu' : 'Ouvrir le menu');
      menu.inert = !open && isNarrow();
      if (open) { const a = menu.querySelector('a'); if (a) a.focus(); } else if (document.activeElement && menu.contains(document.activeElement)) toggle.focus();
    };
    toggle.addEventListener('click', () => setMenu(!menu.classList.contains('is-open')));
    menu.addEventListener('click', (e) => { if (e.target.closest('a') && menu.classList.contains('is-open')) setMenu(false); });
    addEventListener('keydown', (e) => { if (e.key === 'Escape' && menu.classList.contains('is-open')) setMenu(false); });
    addEventListener('resize', () => { menu.inert = isNarrow() && !menu.classList.contains('is-open'); });
    menu.inert = isNarrow();
  }

  /* ---------- scroll progress rail ---------- */
  const rail = $('[data-rail]');
  if (rail) {
    const upd = () => { const h = document.documentElement.scrollHeight - innerHeight; rail.style.setProperty('--p', h > 0 ? clamp(scrollY / h) : 0); };
    addEventListener('scroll', upd, { passive: true }); addEventListener('resize', upd); upd();
  }

  /* ---------- rotating word ---------- */
  const rot = $('[data-rotator]');
  if (rot && !reduced) {
    const words = $$('span', rot); let i = 0;
    setInterval(() => { words[i].classList.remove('is-on'); i = (i + 1) % words.length; words[i].classList.add('is-on'); }, 2200);
  }

  /* ---------- hero dashboard cluster ---------- */
  const cluster = $('[data-cluster]');
  if (cluster) {
    const lamps = $$('[data-lamp]', cluster), needle = $('[data-needle]', cluster);
    const setStage = (k) => { // k in 0..12 : 0-6 lights up, 7-12 diagnosed
      lamps.forEach((g, n) => {
        const l = g.querySelector('.lamp'), ok = g.querySelector('.lamp-ok');
        const lit = k > n && k <= 6 + n, done = k > 6 + n;
        l.classList.toggle('is-lit', lit); l.classList.toggle('is-ok', done); ok.classList.toggle('is-on', done);
      });
      if (needle) needle.style.transform = `rotate(${-70 + clamp(k / 12) * 140}deg)`;
    };
    if (reduced) setStage(12);
    else {
      let k = 0, timer = null;
      const tick = () => { k = k >= 12 ? 0 : k + 1; setStage(k); };
      const start = () => { if (!timer) timer = setInterval(tick, 700); };
      const stop = () => { clearInterval(timer); timer = null; };
      const vis = new IntersectionObserver((es) => es.forEach((e) => e.isIntersecting ? start() : stop()), { threshold: .2 });
      vis.observe(cluster);
      addEventListener('visibilitychange', () => document.hidden ? stop() : start());
    }
  }

  /* ---------- booking widget ---------- */
  const widget = $('[data-widget]');
  if (widget) {
    const plate = $('[data-plate]', widget), service = $('[data-service]', widget), city = $('[data-city]', widget);
    const hint = $('[data-hint]', widget), slotsBox = $('[data-slots]', widget), list = $('[data-slot-list]', widget);
    const modal = $('[data-modal]'), summary = $('[data-modal-summary]');
    const PLATE = /^[A-Z]{2}-\d{3}-[A-Z]{2}$/;
    const mask = (raw) => {
      const s = raw.toUpperCase().replace(/[^A-Z0-9]/g, '');
      const a = s.slice(0, 2).replace(/[^A-Z]/g, ''), b = s.slice(2, 5).replace(/\D/g, ''), c = s.slice(5, 7).replace(/[^A-Z]/g, '');
      let out = a; if (a.length === 2) out += '-' + b; if (b.length === 3) out += '-' + c; return out;
    };
    let chosen = null;
    const fmt = (d) => {
      const now = new Date(), tomorrow = new Date(now); tomorrow.setDate(now.getDate() + 1);
      const day = d.toDateString() === now.toDateString() ? 'Aujourd’hui' : d.toDateString() === tomorrow.toDateString() ? 'Demain' : d.toLocaleDateString('fr-FR', { weekday: 'long' });
      return `${day} ${String(d.getHours()).padStart(2, '0')}h${String(d.getMinutes()).padStart(2, '0')}`;
    };
    const genSlots = () => {
      // three créneaux inside the next 24 h, within 08:00-18:30, on the half hour
      const out = [], limit = Date.now() + 24 * 3600000;
      const t = new Date(Date.now() + 90 * 60000); t.setMinutes(Math.ceil(t.getMinutes() / 30) * 30, 0, 0);
      for (let guard = 0; out.length < 3 && guard < 40 && t.getTime() <= limit; guard++) {
        const h = t.getHours() + t.getMinutes() / 60;
        if (h < 8) t.setHours(8, 30, 0, 0);
        else if (h > 18.5) { t.setDate(t.getDate() + 1); t.setHours(8, 30, 0, 0); }
        else { out.push(new Date(t)); t.setMinutes(t.getMinutes() + 150); }
      }
      if (!out.length) { const d = new Date(limit); d.setHours(8, 30, 0, 0); out.push(d); }
      return out;
    };
    const renderSlots = () => {
      if (!list) return; list.innerHTML = ''; chosen = null;
      genSlots().forEach((d, i) => {
        const li = document.createElement('li'), b = document.createElement('button');
        b.type = 'button'; b.className = 'slot'; b.textContent = fmt(d); b.setAttribute('aria-pressed', 'false'); b.dataset.iso = d.toISOString();
        b.addEventListener('click', () => { $$('.slot', list).forEach((x) => x.setAttribute('aria-pressed', 'false')); b.setAttribute('aria-pressed', 'true'); chosen = b.textContent; });
        li.appendChild(b); list.appendChild(li);
      });
      if (slotsBox) slotsBox.hidden = false;
    };
    const ready = () => plate && PLATE.test(plate.value) && service && service.value && city && city.value.trim().length >= 2;
    const check = () => { if (ready() && slotsBox && slotsBox.hidden) renderSlots(); };
    if (plate) plate.addEventListener('input', () => {
      plate.value = mask(plate.value);
      const ok = PLATE.test(plate.value);
      if (hint) { hint.textContent = ok ? 'Plaque reconnue.' : 'Format français : AA-123-AA.'; hint.classList.toggle('is-error', !ok && plate.value.length === 9); }
      check();
    });
    if (service) service.addEventListener('change', check);
    if (city) city.addEventListener('input', check);
    widget.addEventListener('submit', (e) => {
      e.preventDefault();
      if (!ready()) {
        if (hint) { hint.textContent = 'Renseignez la plaque (AA-123-AA), la prestation et la ville.'; hint.classList.add('is-error'); }
        const first = [plate, service, city].find((el) => el && !el.value); if (first) first.focus();
        return;
      }
      if (slotsBox && slotsBox.hidden) renderSlots();
      if (!chosen) { if (hint) { hint.textContent = 'Choisissez un créneau.'; hint.classList.add('is-error'); } const s = $('.slot', list); if (s) s.focus(); return; }
      if (summary) summary.textContent = `${service.value} · ${plate.value} · ${city.value.trim()} · ${chosen}.`;
      if (modal && typeof modal.showModal === 'function') modal.showModal(); else if (modal) modal.setAttribute('open', '');
    });
    if (modal) modal.addEventListener('click', (e) => { if (e.target === modal) modal.close(); });
    // pre-select a prestation from rows / CTAs
    document.addEventListener('click', (e) => {
      const a = e.target.closest('[data-pick]'); if (!a || !service) return;
      const txt = document.createElement('textarea'); txt.innerHTML = a.dataset.pick;
      const want = txt.value;
      const opt = Array.from(service.options).find((o) => o.text === want);
      if (opt) { service.value = opt.text; service.dispatchEvent(new Event('change')); }
    });
  }

  /* ---------- offer countdown ---------- */
  const cd = $('[data-countdown]');
  if (cd) {
    const END = Date.parse('2026-10-10T23:59:59+02:00');
    const upd = () => {
      const ms = END - Date.now();
      if (ms <= 0) { cd.textContent = 'Offre terminée — prochaine offre bientôt'; return; }
      const j = Math.floor(ms / 86400000), h = Math.floor(ms % 86400000 / 3600000), m = Math.floor(ms % 3600000 / 60000);
      cd.textContent = `Il reste ${j} j ${h} h ${m} min`;
    };
    upd(); setInterval(upd, 30000);
  }

  /* ---------- ticker: duplicate list for seamless loop ---------- */
  const ticker = $('[data-ticker]');
  if (ticker && !reduced) { const ul = ticker.querySelector('ul'); if (ul) { const c = ul.cloneNode(true); c.setAttribute('aria-hidden', 'true'); ticker.appendChild(c); } }

  /* ---------- prestations filter ---------- */
  const filters = $('[data-filters]'), rows = $$('[data-rows] .row');
  if (filters && rows.length) filters.addEventListener('click', (e) => {
    const b = e.target.closest('[data-filter]'); if (!b) return;
    $$('[data-filter]', filters).forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
    const f = b.dataset.filter;
    rows.forEach((r) => r.classList.toggle('is-hidden', f !== 'tout' && r.dataset.cat !== f));
  });

  /* ---------- reveals + counters + checklist + battery + windshield + map ---------- */
  const easeOut = (x) => 1 - Math.pow(1 - x, 3);
  const count = (el) => {
    const to = +el.dataset.count, from = +(el.dataset.from || 0), t0 = performance.now(), D = 1400;
    if (reduced) { el.textContent = to; return; }
    const step = (t) => { const p = clamp((t - t0) / D); el.textContent = Math.round(from + (to - from) * easeOut(p)); if (p < 1) requestAnimationFrame(step); };
    requestAnimationFrame(step);
  };
  const reveals = $$('.reveal');
  if ('IntersectionObserver' in window && reveals.length) {
    const io = new IntersectionObserver((es) => es.forEach((e) => {
      if (!e.isIntersecting) return;
      const el = e.target; el.classList.add('is-in'); io.unobserve(el);
      $$('[data-count]', el).forEach(count);
      if (el.matches('[data-checklist]')) $$('li', el).forEach((li, i) => setTimeout(() => li.classList.add('is-done'), reduced ? 0 : 300 + i * 350));
      const bat = $('[data-battery]', el); if (bat) { bat.style.setProperty('--lvl', '.82'); const pct = $('[data-battery-pct]', bat); if (pct) { pct.dataset.count = '82'; count(pct); setTimeout(() => { pct.textContent = '82 %'; }, reduced ? 0 : 1500); } }
      if (el.matches('[data-windshield]')) setTimeout(() => el.classList.add('is-clean'), reduced ? 0 : 900);
      if (el.matches('[data-map]')) $$('circle', el).forEach((c, i) => setTimeout(() => c.classList.add('is-on'), reduced ? 0 : i * 28));
    }), { threshold: .18, rootMargin: '0px 0px -6% 0px' });
    reveals.forEach((el) => io.observe(el));
  } else reveals.forEach((el) => el.classList.add('is-in'));

  /* ---------- hero scrub: fade the cluster slightly as you leave the hero ---------- */
  const hero = $('.hero');
  if (hero && cluster && !reduced) {
    const scrub = () => { const p = clamp(scrollY / Math.max(1, hero.offsetHeight * .8)); cluster.style.opacity = String(1 - p * .7); cluster.style.transform = `translateY(${p * 40}px) scale(${1 - p * .06})`; };
    addEventListener('scroll', scrub, { passive: true }); scrub();
  }
})();
