/* h2 Recruit concept — hand-rolled motion, zero dependencies. */
(() => {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const mobile = () => innerWidth < 800;

  /* ---------- header, menu, progress ---------- */
  const header = $('[data-header]'), menu = $('[data-menu]'), toggle = $('[data-menu-toggle]');
  const setMenu = (open) => { menu.classList.toggle('is-open', open); toggle.setAttribute('aria-expanded', String(open)); menu.inert = !open && innerWidth <= 1050; if (open) menu.querySelector('a').focus(); else toggle.focus(); };
  toggle.addEventListener('click', () => setMenu(!menu.classList.contains('is-open')));
  menu.addEventListener('click', (e) => { if (e.target.tagName === 'A' && menu.classList.contains('is-open')) setMenu(false); });
  addEventListener('keydown', (e) => { if (e.key === 'Escape' && menu.classList.contains('is-open')) setMenu(false); });
  addEventListener('resize', () => { menu.inert = innerWidth <= 1050 && !menu.classList.contains('is-open'); });
  menu.inert = innerWidth <= 1050;

  /* ---------- hero: scroll-scrubbed pipeline (canvas, or drop-in video) ---------- */
  const hero = $('[data-film-hero]'), states = $$('[data-film-state]'), steps = $$('[data-film-step]');
  const LAST = states.length - 1, video = $('[data-film-video]'), canvas = $('[data-film-canvas]');
  let curState = 0;
  const show = (i) => { if (i === curState) return; curState = i; states.forEach((el, k) => el.classList.toggle('is-on', k === i)); steps.forEach((el, k) => el.classList.toggle('is-active', k === i)); };
  steps[0].classList.add('is-active');

  // Optional Kling/Higgsfield footage: drop assets/hero.mp4 (+hero-m.mp4) and it scrubs instead of the canvas.
  let useVideo = false, seeking = false, targetT = 0;
  const LEG = 5;
  if (!reduced) fetch('assets/hero.mp4', { method: 'HEAD' }).then((r) => {
    if (!r.ok || !/video/.test(r.headers.get('content-type') || '')) return;
    fetch(mobile() ? 'assets/hero-m.mp4' : 'assets/hero.mp4').then((r) => r.ok ? r.blob() : Promise.reject()).then((b) => { video.src = URL.createObjectURL(b); video.load(); video.hidden = false; canvas.hidden = true; useVideo = true; }).catch(() => {});
  }).catch(() => {});
  video.addEventListener('seeked', () => { seeking = false; });

  // Canvas pipeline: 360 sellers converge through six stages into one placed hire.
  const ctx = canvas.getContext('2d');
  const N = 360, P = [];
  let W = 0, H = 0, dpr = 1, px = 0.5, py = 0.5, t = 0, stageT = 0;
  const rnd = (seed) => { let s = seed; return () => (s = (s * 16807) % 2147483647) / 2147483647; };
  const r = rnd(42);
  for (let i = 0; i < N; i++) P.push({ x: r(), y: r(), j: r(), k: r(), v: .4 + r() * .6, keep: i < 5, star: i === 0 });
  const layout = (p, s, i) => { // returns [x,y,alpha,size] in 0..1 space for stage s
    const ring = (rad, ph) => [0.5 + Math.cos(ph) * rad, 0.5 + Math.sin(ph) * rad * 1.3];
    switch (s) {
      case 0: return [p.x, p.y, .55, 1];
      case 1: { const col = i % 24, row = Math.floor(i / 24); return [0.04 + col * 0.04, 0.12 + row * 0.055 + Math.sin(p.j * 9 + t * .6) * .01, .9, 1.3]; }
      case 2: { const rad = .2 + p.j * .36; const ph = p.k * Math.PI * 2 + t * .05 * p.v; const [x, y] = ring(rad, ph); return [x, y, .45, 1]; }
      case 3: { if (p.keep) { const [x, y] = ring(.16, i * 1.2566 + t * .12); return [x, y, 1, 3.2]; } const rad = .48 + p.j * .3; const [x, y] = ring(rad, p.k * 6.283); return [x, y, .12, .8]; }
      case 4: { if (p.keep) return [0.5 + (i - 2) * .11, 0.52, 1, 3.4]; return [p.x, 1.1 + p.j * .3, 0, .5]; }
      default: { if (p.star) return [0.5, 0.5, 1, 6]; if (p.keep) return [0.5 + Math.cos(i) * .3, 1.2, 0, 1]; return [p.x, 1.2, 0, .5]; }
    }
  };
  const resize = () => { dpr = Math.min(devicePixelRatio || 1, 2); W = canvas.clientWidth; H = canvas.clientHeight; canvas.width = W * dpr; canvas.height = H * dpr; ctx.setTransform(dpr, 0, 0, dpr, 0, 0); };
  resize(); addEventListener('resize', resize);
  addEventListener('pointermove', (e) => { px = e.clientX / innerWidth; py = e.clientY / innerHeight; }, { passive: true });
  const ease = (x) => x < .5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2;
  const draw = () => {
    t += 1 / 60; ctx.clearRect(0, 0, W, H);
    const s = Math.floor(clamp(stageT, 0, LAST - .001)), f = ease(clamp(stageT - s));
    const ox = (px - .5) * -30, oy = (py - .5) * -20;
    const pts = [];
    for (let i = 0; i < N; i++) {
      const p = P[i], a = layout(p, s, i), b = layout(p, Math.min(LAST, s + 1), i);
      const x = (a[0] + (b[0] - a[0]) * f) * W + ox, y = (a[1] + (b[1] - a[1]) * f) * H + oy;
      const al = a[2] + (b[2] - a[2]) * f, sz = a[3] + (b[3] - a[3]) * f;
      if (al < .02) continue; pts.push([x, y, al, sz, p]);
    }
    if (s <= 2) { ctx.lineWidth = .6; const lim = s === 0 ? 70 : 46; for (let i = 0; i < pts.length; i += 2) for (let j = i + 2; j < pts.length; j += 3) { const dx = pts[i][0] - pts[j][0], dy = pts[i][1] - pts[j][1]; const d = dx * dx + dy * dy; if (d < lim * lim) { ctx.strokeStyle = `rgba(214,255,75,${(1 - d / (lim * lim)) * .22 * pts[i][2]})`; ctx.beginPath(); ctx.moveTo(pts[i][0], pts[i][1]); ctx.lineTo(pts[j][0], pts[j][1]); ctx.stroke(); } } }
    if (s === 3 || (s === 4 && f < .5)) { ctx.strokeStyle = 'rgba(214,255,75,.35)'; ctx.lineWidth = 1; const kk = pts.filter((q) => q[4].keep); for (let i = 0; i < kk.length; i++) for (let j = i + 1; j < kk.length; j++) { ctx.beginPath(); ctx.moveTo(kk[i][0], kk[i][1]); ctx.lineTo(kk[j][0], kk[j][1]); ctx.stroke(); } }
    for (const [x, y, al, sz, p] of pts) {
      const rr = (p.keep ? 2.2 : 1.4) * sz;
      if (p.star && s >= 4) { const g = ctx.createRadialGradient(x, y, 0, x, y, 120 + Math.sin(t * 2) * 12); g.addColorStop(0, 'rgba(214,255,75,.35)'); g.addColorStop(1, 'rgba(214,255,75,0)'); ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, 130, 0, 6.283); ctx.fill(); ctx.strokeStyle = 'rgba(214,255,75,.5)'; ctx.lineWidth = 1.5; for (let q = 1; q <= 3; q++) { const rad = 40 * q + ((t * 40) % 40); ctx.globalAlpha = 1 - rad / 160; ctx.beginPath(); ctx.arc(x, y, rad, 0, 6.283); ctx.stroke(); } ctx.globalAlpha = 1; }
      ctx.fillStyle = p.keep ? `rgba(214,255,75,${al})` : `rgba(239,234,224,${al})`;
      ctx.beginPath(); ctx.arc(x, y, rr, 0, 6.283); ctx.fill();
    }
    requestAnimationFrame(draw);
  };
  if (!reduced) requestAnimationFrame(draw); else { stageT = 0; draw(); }

  const frame = () => {
    const rect = hero.getBoundingClientRect(), vh = innerHeight;
    const p = clamp(-rect.top / (rect.height - vh));
    const tt = Math.min(LAST, (p / .92) * LAST), s = Math.floor(Math.min(tt, LAST - .001)), f = tt - s;
    const g = clamp((f - .15) / .7);
    stageT = s + g; targetT = (s + g) * LEG;
    show(f < .5 ? s : Math.min(LAST, s + 1));
    steps.forEach((el, i) => el.style.setProperty('--fill', clamp(tt - i)));
    if (useVideo && video.readyState >= 2) { const d = targetT - video.currentTime; if (Math.abs(d) >= 1 / 48 && !seeking) { seeking = true; video.currentTime += d * .22; } }
    header.classList.toggle('is-scrolled', scrollY > 48);
    header.style.setProperty('--page-progress', clamp(scrollY / (document.documentElement.scrollHeight - vh)));
    folioFrame(); drumFrame();
  };

  /* ---------- roles: pinned card stack ---------- */
  const folio = $('[data-folio]'), cards = $$('[data-card]');
  const folioFrame = () => {
    if (mobile() || reduced) return;
    const rect = folio.getBoundingClientRect(), p = clamp(-rect.top / (rect.height - innerHeight));
    const idx = p * (cards.length - 1);
    cards.forEach((c, k) => { const d = k - idx; c.style.setProperty('--d', Math.max(d, -1.2)); c.style.setProperty('--a', Math.abs(Math.min(d, 0))); c.style.setProperty('--o', d < -.9 ? 0 : 1); c.style.zIndex = String(100 - Math.round(Math.abs(d) * 10)); });
  };

  /* ---------- approach: rotating drum ---------- */
  const approach = $('[data-approach]'), stepsEls = $$('[data-step]');
  const drumFrame = () => {
    if (mobile() || reduced) return;
    const rect = approach.getBoundingClientRect(), p = clamp(-rect.top / (rect.height - innerHeight));
    const idx = Math.min(stepsEls.length - 1, Math.floor(p * stepsEls.length));
    stepsEls.forEach((el, k) => { const d = k - idx; el.style.setProperty('--r', d * -28); el.style.setProperty('--o', d === 0 ? 1 : 0); });
  };

  let ticking = false;
  const onScroll = () => { if (ticking) return; ticking = true; requestAnimationFrame(() => { frame(); ticking = false; }); };
  addEventListener('scroll', onScroll, { passive: true }); addEventListener('resize', onScroll); frame();

  /* ---------- reveals, count-ups, bars ---------- */
  const io = new IntersectionObserver((es) => es.forEach((e) => { if (!e.isIntersecting) return; e.target.classList.add('is-in'); io.unobserve(e.target); $$('[data-count]', e.target).forEach(countUp); }), { threshold: .2 });
  $$('[data-reveal]').forEach((el) => io.observe(el));
  function countUp(el) { const to = Number(el.dataset.count), t0 = performance.now(), d = 1400; if (reduced) { el.textContent = to; return; } const step = (now) => { const k = clamp((now - t0) / d); el.textContent = Math.round(to * (1 - Math.pow(1 - k, 3))); if (k < 1) requestAnimationFrame(step); }; requestAnimationFrame(step); }
  const bars = $('.report__bars'); bars.classList.add('is-hidden'); new IntersectionObserver((es, o) => { if (es[0].isIntersecting) { bars.classList.remove('is-hidden'); o.disconnect(); } }, { threshold: .3 }).observe(bars);
  $$('[data-demo-form]').forEach((f) => f.addEventListener('submit', (e) => { e.preventDefault(); f.querySelector('.form__ok').hidden = false; f.querySelector('button').disabled = true; }));

  /* ---------- outreach feed replay ---------- */
  const feed = $('[data-feed]'), list = $('[data-feed-list]'), clock = $('[data-feed-clock]'), stat = $('[data-feed-stat]');
  const names = ['Priya S.', 'Tom W.', 'Amara O.', 'Jake M.', 'Sofia R.', 'Dan K.', 'Leah B.', 'Marcus T.', 'Chloe H.', 'Ravi P.', 'Emma L.', 'Ben C.', 'Nina F.', 'Oscar G.', 'Zara A.', 'Liam D.'];
  const roles = ['Founding AE · London', 'Enterprise AE · NYC', 'SDR · London', 'Strategic AM · NYC', 'Partner AM · London', 'Commercial AE · Paris'];
  const replies = ['"Interesting timing, I\'m open to a chat Thursday."', '"Not for me but my old colleague would be perfect, intro?"', '"What\'s the OTE split? Happy to talk."', '"Yes, send me the deck."', '"Can we do a call before Friday?"', '"Been waiting for something like this. Call me."'];
  let sent = 0, opened = 0, replied = 0, minute = 0, fr = rnd(7);
  const addRow = (kind, name, role, extra) => {
    const li = document.createElement('li'); if (kind === 'reply') li.className = 'is-reply';
    const h = 22 + Math.floor(minute / 60), m = minute % 60; const tm = `${String(h % 24).padStart(2, '0')}:${String(m).padStart(2, '0')}`; clock.textContent = tm;
    li.innerHTML = `<time>${tm}</time><span>${kind === 'sent' ? `Message 1 sent to <b>${name}</b> · ${role}` : kind === 'open' ? `<b>${name}</b> opened · ${role}` : `<b>${name}</b> replied: ${extra}`}</span><em>${kind}</em>`;
    list.appendChild(li); while (list.children.length > 9) list.firstChild.remove();
    stat.textContent = `${sent} sent · ${opened} opened · ${replied} replied`;
  };
  let feedOn = false;
  const tick = () => { if (!feedOn) return; minute += 3 + Math.floor(fr() * 9); const x = fr(); const name = names[Math.floor(fr() * names.length)], role = roles[Math.floor(fr() * roles.length)]; if (x < .55) { sent++; addRow('sent', name, role); } else if (x < .8) { opened++; addRow('open', name, role); } else { replied++; addRow('reply', name, role, replies[Math.floor(fr() * replies.length)]); } setTimeout(tick, reduced ? 2400 : 900 + fr() * 1100); };
  new IntersectionObserver((es) => { const on = es[0].isIntersecting; if (on && !feedOn) { feedOn = true; tick(); } if (!on) feedOn = false; }, { threshold: .25 }).observe(feed);

  /* ---------- Ask h2: market read (Worker if deployed, local engine otherwise) ---------- */
  const ask = $('[data-ask]'), q = $('#ask-q'), out = $('[data-ask-out]'), note = $('[data-ask-note]');
  const ASK_URL = ask.dataset.askUrl || (location.hostname.endsWith('pages.dev') ? '' : ''); // set data-ask-url on the form once the Worker is live
  const setOut = (k, v) => { $(`[data-out="${k}"]`).textContent = v; };
  const localRead = (raw) => {
    const s = raw.toLowerCase();
    const us = /new york|nyc|boston|san fran|sf|austin|us\b|usa|\$/.test(s), eu = /paris|berlin|amsterdam|dublin|europe/.test(s);
    const cur = us ? '$' : eu ? '€' : '£';
    const seat = /vp|head of|cro|director|leader/.test(s) ? 'lead' : /enterprise|strategic/.test(s) ? 'ent' : /sdr|bdr/.test(s) ? 'sdr' : /marketing|gtm/.test(s) ? 'gtm' : 'ae';
    const founding = /founding|first/.test(s);
    const stage = /seed|pre-seed/.test(s) ? 'seed' : /series a/.test(s) ? 'a' : /series b/.test(s) ? 'b' : /series c|growth|scale/.test(s) ? 'c' : 'a';
    const bands = { sdr: [45, 70], ae: [110, 170], ent: [200, 300], lead: [220, 380], gtm: [110, 190] };
    let [lo, hi] = bands[seat]; if (us) { lo *= 1.5; hi *= 1.55; } if (founding) { lo *= 1.1; hi *= 1.15; } if (stage === 'seed') { lo *= .9; hi *= .95; } if (stage === 'c') { lo *= 1.05; hi *= 1.1; }
    const R = (n) => Math.round(n / 5) * 5;
    const comp = `${cur}${R(lo)}K–${R(hi)}K OTE${founding ? ' + equity' : ''}`;
    const where = us ? 'Series B+ SaaS in NYC and Boston; UK sellers relocating' : eu ? 'Local enterprise SaaS plus UK sellers with EU territory' : seat === 'sdr' ? 'PLG and outbound-heavy startups, 12–24 months in seat' : seat === 'lead' ? 'Second-line leaders at Series B–D, ready for the top job' : 'Sellers 2–4 years into a comparable ACV and motion';
    const time = seat === 'sdr' ? '5–7 working days' : seat === 'lead' ? '10–14 working days' : founding ? '8–10 working days' : '7–9 working days';
    const pool = `${seat === 'sdr' ? 480 : seat === 'lead' ? 140 : seat === 'ent' ? 210 : 330}${us ? '' : '+'} matched in network`;
    const text = `Read: a ${founding ? 'founding ' : ''}${{ sdr: 'SDR', ae: 'Account Executive', ent: 'Enterprise AE', lead: 'sales leadership', gtm: 'GTM' }[seat]} hire at ${stage === 'seed' ? 'seed' : 'Series ' + stage.toUpperCase()} stage${us ? ' in the US' : eu ? ' in Europe' : ' in the UK'}. ${founding ? 'Founding sellers price on equity and autonomy as much as OTE, so the base split matters more than the headline. ' : ''}${seat === 'ent' ? 'Enterprise sellers move for territory and pipeline maturity; expect to talk about existing logos before comp. ' : ''}We would open outreach tonight and have the first conversations back by the end of the week.`;
    return { comp, where, time, pool, text };
  };
  const render = (o) => { setOut('comp', o.comp); setOut('where', o.where); setOut('time', o.time); setOut('pool', o.pool); setOut('text', o.text); out.hidden = false; };
  ask.addEventListener('submit', async (e) => {
    e.preventDefault(); const text = q.value.trim(); if (!text) { q.focus(); return; }
    ask.classList.add('is-busy'); note.textContent = 'Reading the market…';
    let res = null;
    if (ASK_URL) { try { const r = await fetch(ASK_URL, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ query: text }) }); if (r.ok) res = await r.json(); } catch (_) {} }
    setTimeout(() => { render(res && res.comp ? res : localRead(text)); ask.classList.remove('is-busy'); note.textContent = 'Indicative. A consultant confirms every number.'; }, res ? 0 : 700);
  });
  $$('[data-chips] button').forEach((b) => b.addEventListener('click', () => { q.value = b.textContent; ask.requestSubmit(); }));

  /* ---------- cursor + magnetic buttons ---------- */
  const cur = $('[data-cursor]');
  if (cur && matchMedia('(hover:hover)').matches && !reduced) {
    let cx = 0, cy = 0, tx = 0, ty = 0;
    addEventListener('pointermove', (e) => { tx = e.clientX; ty = e.clientY; cur.classList.add('is-on'); }, { passive: true });
    addEventListener('pointerleave', () => cur.classList.remove('is-on'));
    const loop = () => { cx += (tx - cx) * .18; cy += (ty - cy) * .18; cur.style.left = cx + 'px'; cur.style.top = cy + 'px'; requestAnimationFrame(loop); }; loop();
    $$('a,button').forEach((el) => { el.addEventListener('pointerenter', () => cur.style.setProperty('--s', 3)); el.addEventListener('pointerleave', () => cur.style.setProperty('--s', 1)); });
    $$('.btn').forEach((el) => { el.classList.add('magnet'); el.addEventListener('pointermove', (e) => { const r = el.getBoundingClientRect(); el.style.transform = `translate(${(e.clientX - r.left - r.width / 2) * .18}px,${(e.clientY - r.top - r.height / 2) * .3}px)`; }); el.addEventListener('pointerleave', () => { el.style.transform = ''; }); });
  }
})();
