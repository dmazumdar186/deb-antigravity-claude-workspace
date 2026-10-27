(() => {
  'use strict';
  const root = document.documentElement;
  const $ = (s, c = document) => c.querySelector(s);
  const $$ = (s, c = document) => Array.from(c.querySelectorAll(s));
  const i18n = window.JeevanaI18n;
  const t = key => i18n ? i18n.t(key) : key;
  const motion = matchMedia('(prefers-reduced-motion: reduce)');
  const desktop = matchMedia('(min-width: 761px)');
  root.classList.add('has-js');
  $$('[data-year]').forEach(el => { el.textContent = new Date().getFullYear(); });

  const reveals = $$('[data-reveal]');
  if ('IntersectionObserver' in window && !motion.matches) {
    const revealObserver = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          revealObserver.unobserve(entry.target);
        }
      });
    }, { threshold: 0.06, rootMargin: '0px 0px -4% 0px' });
    reveals.forEach(el => revealObserver.observe(el));
  } else reveals.forEach(el => el.classList.add('is-visible'));

  const headings = $$('.section-heading');
  const ringRatios = new WeakMap();
  if ('IntersectionObserver' in window) {
    const ringObserver = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        const ratio = Math.max(ringRatios.get(entry.target) || 0, entry.intersectionRatio);
        ringRatios.set(entry.target, ratio);
        const ring = $('[data-scroll-ring]', entry.target);
        if (ring) ring.setAttribute('stroke-dashoffset', motion.matches ? '0' : String(100 * (1 - ratio)));
      });
    }, { threshold: Array.from({ length: 21 }, (_, n) => n / 20) });
    headings.forEach(el => ringObserver.observe(el));
  } else $$('[data-scroll-ring]').forEach(el => el.setAttribute('stroke-dashoffset', '0'));

  const header = $('[data-header]');
  const pageProgress = $('[data-page-progress]');
  const photos = $$('[data-parallax]');
  let pageFrame = 0;
  function paintPage() {
    pageFrame = 0;
    const y = window.scrollY;
    header.classList.toggle('is-scrolled', y > 80);
    const span = root.scrollHeight - window.innerHeight;
    pageProgress.style.transform = 'scaleX(' + (span > 0 ? Math.min(1, y / span) : 0) + ')';
    photos.forEach(el => {
      if (motion.matches || !desktop.matches) { el.style.transform = ''; return; }
      const rect = el.getBoundingClientRect();
      if (rect.bottom < -30 || rect.top > innerHeight + 30) return;
      const p = Math.max(-1, Math.min(1, (rect.top + rect.height / 2 - innerHeight / 2) / innerHeight));
      el.style.transform = 'translate3d(0,' + (p * 12 * Number(el.dataset.parallax)).toFixed(2) + 'px,0)';
    });
  }
  const queuePage = () => { if (!pageFrame) pageFrame = requestAnimationFrame(paintPage); };
  addEventListener('scroll', queuePage, { passive: true });
  addEventListener('resize', queuePage, { passive: true });
  paintPage();

  function eventCount(name) {
    const body = JSON.stringify({ name });
    let sent = false;
    try { sent = !!navigator.sendBeacon && navigator.sendBeacon('/api/event', new Blob([body], { type: 'application/json' })); } catch (_) {}
    if (!sent) fetch('/api/event', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body, keepalive: true }).catch(() => {});
  }
  document.addEventListener('click', event => {
    const el = event.target.closest('[data-event]');
    if (el) eventCount(el.dataset.event);
    const format = event.target.closest('[data-format]');
    if (format) {
      const select = $('#reg-class');
      select.value = format.dataset.format;
      select.dispatchEvent(new Event('change', { bubbles: true }));
    }
  });

  const track = $('#breath-strip');
  const cards = $$('[data-step]', track);
  const arcs = $$('[data-arc]');
  const previous = $('[data-prev]');
  const next = $('[data-next]');
  const play = $('[data-play]');
  const playLabel = $('[data-play-label]');
  const live = $('[data-sequence-status]');
  let active = 0;
  let requested = false;
  let hovered = false;
  let focused = false;
  let visible = false;
  let timer = 0;
  let stripFrame = 0;
  let scrollEnd = 0;
  let pointer = null;
  function announce() {
    const title = $('h3', cards[active]).textContent;
    live.textContent = t('breathCount').replace('{n}', active + 1) + ': ' + title + '. ' + t('s' + (active + 1) + 'Breath') + '.';
  }
  function setActive(index) {
    active = index;
    cards.forEach((card, n) => {
      card.classList.toggle('is-active', n === index);
      if (n === index) card.setAttribute('aria-current', 'step');
      else card.removeAttribute('aria-current');
    });
    arcs.forEach((arc, n) => arc.classList.toggle('is-current', n === index));
    root.dataset.position = String(index + 1);
    $('[data-position-fill]').setAttribute('stroke-dashoffset', String(11 - index));
    $('[data-position-text]').textContent = String(index + 1).padStart(2, '0');
    previous.disabled = index === 0;
    next.disabled = index === cards.length - 1;
    announce();
  }
  function readCentre() {
    stripFrame = 0;
    const centre = track.scrollLeft + track.clientWidth / 2;
    let nearest = 0;
    let distance = Infinity;
    cards.forEach((card, n) => {
      const d = Math.abs(card.offsetLeft + card.offsetWidth / 2 - centre);
      if (d < distance) { distance = d; nearest = n; }
    });
    if (nearest !== active) setActive(nearest);
  }
  function go(index, instant = false) {
    const n = Math.max(0, Math.min(cards.length - 1, index));
    const card = cards[n];
    track.scrollTo({ left: card.offsetLeft - (track.clientWidth - card.offsetWidth) / 2, behavior: instant || motion.matches ? 'instant' : 'smooth' });
    if (instant || motion.matches) setActive(n);
  }
  function schedule() {
    clearTimeout(timer);
    if (!requested || motion.matches || hovered || focused || !visible || document.hidden || pointer) return;
    timer = setTimeout(() => { go((active + 1) % cards.length); schedule(); }, 4000);
  }
  function updatePlay() {
    play.disabled = motion.matches;
    play.setAttribute('aria-pressed', String(requested));
    playLabel.textContent = t(motion.matches ? 'motionOff' : requested ? 'pauseSequence' : 'playSequence');
    $('.play-symbol', play).textContent = requested ? 'Ⅱ' : '▷';
    live.setAttribute('aria-live', requested ? 'off' : 'polite');
    schedule();
  }
  function stopAuto() { requested = false; updatePlay(); }
  previous.addEventListener('click', () => { stopAuto(); go(active - 1); });
  next.addEventListener('click', () => { stopAuto(); go(active + 1); });
  play.addEventListener('click', () => { requested = !requested; updatePlay(); });
  track.addEventListener('keydown', event => {
    let n;
    if (event.key === 'ArrowRight') n = active + 1;
    else if (event.key === 'ArrowLeft') n = active - 1;
    else if (event.key === 'Home') n = 0;
    else if (event.key === 'End') n = cards.length - 1;
    else return;
    event.preventDefault(); stopAuto(); go(n);
  });
  track.addEventListener('scroll', () => {
    if (!stripFrame) stripFrame = requestAnimationFrame(readCentre);
    clearTimeout(scrollEnd);
    scrollEnd = setTimeout(schedule, 160);
  }, { passive: true });
  track.addEventListener('pointerenter', event => { if (event.pointerType === 'mouse') { hovered = true; schedule(); } });
  track.addEventListener('pointerleave', () => { hovered = false; schedule(); });
  track.addEventListener('focusin', () => { focused = true; schedule(); });
  track.addEventListener('focusout', event => { if (!track.contains(event.relatedTarget)) { focused = false; schedule(); } });
  track.addEventListener('pointerdown', event => {
    if (event.pointerType !== 'mouse' || event.button !== 0) { stopAuto(); return; }
    pointer = { id: event.pointerId, x: event.clientX, left: track.scrollLeft, dragging: false };
    stopAuto();
  });
  track.addEventListener('pointermove', event => {
    if (!pointer || event.pointerId !== pointer.id) return;
    const delta = event.clientX - pointer.x;
    if (!pointer.dragging && Math.abs(delta) > 6) {
      pointer.dragging = true; track.classList.add('is-dragging'); track.setPointerCapture(event.pointerId);
    }
    if (pointer.dragging) { event.preventDefault(); track.scrollLeft = pointer.left - delta; }
  });
  function endDrag(event) {
    if (!pointer || (event.pointerId !== undefined && pointer.id !== event.pointerId)) return;
    const id = pointer.id;
    const dragged = pointer.dragging;
    pointer = null;
    track.classList.remove('is-dragging');
    if (track.hasPointerCapture(id)) track.releasePointerCapture(id);
    if (dragged) { readCentre(); go(active); }
    schedule();
  }
  addEventListener('pointerup', endDrag);
  track.addEventListener('pointercancel', endDrag);
  track.addEventListener('lostpointercapture', endDrag);
  if ('IntersectionObserver' in window) {
    new IntersectionObserver(entries => { visible = entries[0].isIntersecting; schedule(); }, { threshold: 0.15 }).observe(track);
  } else visible = true;
  document.addEventListener('visibilitychange', schedule);
  let resizeTimer;
  addEventListener('resize', () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(() => go(active, true), 120); });
  setActive(0); updatePlay();

  const errors = { bad_name: 'errorName', bad_email: 'errorEmail', bad_phone: 'errorPhone', consent_required: 'errorConsent', rate_limited: 'errorRate' };
  const forms = $$('[data-form]');
  forms.forEach(form => {
    const fields = $('[data-fields]', form);
    const button = $('[data-submit]', form);
    const label = $('[data-submit-label]', form);
    const status = $('[data-form-status]', form);
    button.disabled = false;
    form.addEventListener('submit', async event => {
      event.preventDefault();
      if (form.dataset.pending === 'true' || !form.reportValidity()) return;
      const data = Object.fromEntries(new FormData(form).entries());
      data.consent = form.elements.namedItem('consent').checked;
      data.lang = root.lang === 'fr' ? 'fr' : 'en';
      data.source_url = location.href.slice(0, 300);
      if (form.dataset.form === 'subscribe') data.source = 'footer';
      status.textContent = ''; delete status.dataset.i18n;
      form.dataset.pending = 'true'; form.setAttribute('aria-busy', 'true');
      fields.disabled = true;
      label.removeAttribute('data-i18n'); label.textContent = t('sending');
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 15000);
      try {
        const response = await fetch(form.action, { method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'application/json' }, body: JSON.stringify(data), signal: controller.signal, credentials: 'same-origin' });
        const result = await response.json().catch(() => ({}));
        if (!response.ok || result.ok !== true) {
          const key = response.status === 429 ? 'errorRate' : errors[result.error] || 'errorServer';
          status.dataset.i18n = key; status.textContent = t(key); return;
        }
        fields.hidden = true;
        const success = $('[data-success]', form);
        success.hidden = false; success.focus({ preventScroll: true });
      } catch (_) {
        status.dataset.i18n = 'errorNetwork'; status.textContent = t('errorNetwork');
      } finally {
        clearTimeout(timeout); fields.disabled = false; delete form.dataset.pending;
        form.removeAttribute('aria-busy');
        const key = form.dataset.form === 'register' ? 'sendRegistration' : 'subscribe';
        label.dataset.i18n = key; label.textContent = t(key);
      }
    });
  });
  document.addEventListener('jeevana:language', () => {
    updatePlay(); announce();
    forms.forEach(form => { if (form.dataset.pending === 'true') $('[data-submit-label]', form).textContent = t('sending'); });
    queuePage();
  });
  function motionChanged() {
    if (motion.matches) {
      requested = false;
      reveals.forEach(el => el.classList.add('is-visible'));
      $$('[data-scroll-ring]').forEach(el => el.setAttribute('stroke-dashoffset', '0'));
    }
    updatePlay(); queuePage();
  }
  motion.addEventListener('change', motionChanged);
  desktop.addEventListener('change', queuePage);
})();
