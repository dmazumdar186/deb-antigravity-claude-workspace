/* hero.js — scroll-scrubbed film. Seven stills at 0,5,…,30 s with six 5 s legs between them.
   Each integer state holds for 15 % of its scroll unit; the leg plays across the middle 70 %.
   currentTime is eased toward the target so a fast flick does not stutter. The video is fetched
   as a blob because Cloudflare Pages serves no byte ranges and an unseekable source cannot scrub.
   Fallback: the same film drawn live on a canvas (js/film.js). Reduced motion: poster + static list.
   ?record=1 exposes window.__tick(frame) for research/render_film.mjs. */
(function () {
  'use strict';
  var hero = document.querySelector('[data-film]');
  if (!hero) return;
  var qs = location.search, FPS = 24;
  if (/[?&]record=1/.test(qs)) {
    document.documentElement.classList.add('rec');
    var cv = document.createElement('canvas'); cv.className = 'rec-stage'; cv.setAttribute('data-stage', ''); document.body.appendChild(cv);
    var size = function () { if (cv.width !== innerWidth || cv.height !== innerHeight) { cv.width = innerWidth; cv.height = innerHeight; } };
    window.__ready = document.fonts ? document.fonts.load('500 40px "EB Garamond"').then(function () { return document.fonts.ready; }) : Promise.resolve();
    window.__tick = function (f) { size(); if (window.AVFilm) window.AVFilm.draw(cv.getContext('2d'), cv.width, cv.height, f / FPS); return f / FPS; };
    return;
  }
  var film = hero.querySelector('[data-film-video]');
  var media = hero.querySelector('.film__media');
  var states = [].slice.call(hero.querySelectorAll('[data-film-state]'));
  var steps = [].slice.call(hero.querySelectorAll('[data-film-step]'));
  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var LEG = 5, LAST = states.length - 1, small = window.innerWidth < 800;
  var current = -1;
  function show(i) {
    if (i === current) return; current = i;
    states.forEach(function (el) { var on = +el.dataset.filmState === i; el.classList.toggle('is-on', on); if ('inert' in el) el.inert = !on; el.setAttribute('aria-hidden', on ? 'false' : 'true'); });
    steps.forEach(function (el) { el.classList.toggle('is-on', +el.dataset.filmStep === i); });
  }
  if (reduce) {
    show(0);
    var box = document.createElement('div'); box.className = 'film__static'; var ol = document.createElement('ol');
    states.slice(1).forEach(function (st) {
      var li = document.createElement('li'), e = st.querySelector('.eyebrow'), h = st.querySelector('.film__h'), p = st.querySelector('.film__p');
      var h3 = document.createElement('h3'); h3.textContent = h ? h.textContent : '';
      if (e) li.appendChild(e.cloneNode(true)); li.appendChild(h3); if (p) li.appendChild(p.cloneNode(true)); ol.appendChild(li);
    });
    box.appendChild(ol); hero.appendChild(box);
    return;
  }
  var base = 'assets/hero' + (small ? '-m' : '');
  var webm = film && film.canPlayType && film.canPlayType('video/webm; codecs="vp9"');
  var src = base + (webm ? '.webm' : '.mp4');
  if (small && film) film.poster = 'assets/hero-m.jpg';
  var target = 0, raf = 0, seeking = false, canvas = null, ctx = null, ct = 0;
  function useCanvas() {
    if (canvas || !window.AVFilm || !media) return;
    canvas = document.createElement('canvas'); canvas.className = 'film__canvas'; media.appendChild(canvas);
    if (film) film.style.visibility = 'hidden';
    var fit = function () { var r = media.getBoundingClientRect(), d = Math.min(2, window.devicePixelRatio || 1); canvas.width = Math.round(r.width * d); canvas.height = Math.round(r.height * d); paint(); };
    window.addEventListener('resize', fit); fit();
  }
  function paint() { if (!canvas) return; ctx = ctx || canvas.getContext('2d'); window.AVFilm.draw(ctx, canvas.width, canvas.height, ct); }
  function tick() {
    if (raf) return;
    raf = requestAnimationFrame(function () {
      raf = 0;
      if (canvas) { var d0 = target - ct; if (Math.abs(d0) < 1 / 48) { ct = target; paint(); return; } ct += d0 * 0.22; paint(); tick(); return; }
      if (!film || film.readyState < 1) { if (film) tick(); return; }
      var delta = target - film.currentTime;
      if (Math.abs(delta) < 1 / 48) return;
      if (!seeking) { seeking = true; film.currentTime += delta * 0.22; }
      tick();
    });
  }
  function frame() {
    var rect = hero.getBoundingClientRect(), vh = window.innerHeight;
    var p = Math.min(1, Math.max(0, -rect.top / Math.max(1, rect.height - vh)));
    var t = Math.min(LAST, (p / 0.92) * LAST), s = Math.floor(Math.min(t, LAST - 0.001)), f = t - s;
    var g = Math.min(1, Math.max(0, (f - 0.15) / 0.7));
    target = (s + g) * LEG;
    show(f < 0.5 ? s : Math.min(LAST, s + 1));
    steps.forEach(function (el, i) { el.style.setProperty('--fill', Math.min(1, Math.max(0, t * (LAST + 1) / LAST - i)).toFixed(3)); });
    hero.classList.toggle('is-moving', p > 0.01);
    tick();
  }
  if (film) {
    film.addEventListener('seeked', function () { seeking = false; });
    film.addEventListener('loadedmetadata', frame);
    film.addEventListener('error', useCanvas);
    var load = function () {
      if (!window.fetch || !window.URL) { film.src = src; film.load(); return; }
      fetch(src).then(function (r) { if (!r.ok) throw new Error(r.status); return r.blob(); })
        .then(function (b) { film.preload = 'auto'; film.src = URL.createObjectURL(b); film.load(); })
        .catch(function () { film.src = src; film.load(); });
    };
    load();
    setTimeout(function () { if (film.readyState < 1) useCanvas(); }, 9000);
  } else useCanvas();
  var scheduled = false;
  function schedule() { if (scheduled) return; scheduled = true; requestAnimationFrame(function () { scheduled = false; frame(); }); }
  window.addEventListener('scroll', schedule, { passive: true });
  window.addEventListener('resize', schedule);
  show(0); frame();
}());
