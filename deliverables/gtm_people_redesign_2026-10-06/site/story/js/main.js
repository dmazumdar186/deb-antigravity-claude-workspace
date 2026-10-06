/* GTM People concept v2 — scroll-story. Hand-rolled motion, zero dependencies. */
(() => {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const mobile = () => innerWidth < 800;
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  /* ---------- header + menu ---------- */
  const header = $('[data-header]'), menu = $('[data-menu]'), toggle = $('[data-menu-toggle]');
  if (header && menu && toggle) {
    const setMenu = (open) => { menu.classList.toggle('is-open', open); toggle.setAttribute('aria-expanded', String(open)); menu.inert = !open && innerWidth <= 1050; if (open) { const a = menu.querySelector('a'); if (a) a.focus(); } else toggle.focus(); };
    toggle.addEventListener('click', () => setMenu(!menu.classList.contains('is-open')));
    menu.addEventListener('click', (e) => { if (e.target.closest('a') && menu.classList.contains('is-open')) setMenu(false); });
    addEventListener('keydown', (e) => { if (e.key === 'Escape' && menu.classList.contains('is-open')) setMenu(false); });
    addEventListener('resize', () => { menu.inert = innerWidth <= 1050 && !menu.classList.contains('is-open'); });
    menu.inert = innerWidth <= 1050;
  }

  /* ---------- film hero: scroll-scrubbed pipeline on canvas ---------- */
  const hero = $('[data-film-hero]'), states = $$('[data-film-state]'), steps = $$('[data-film-step]'), canvas = $('[data-film-canvas]');
  const LAST = Math.max(0, states.length - 1);
  let stageT = 0, curState = 0;
  const show = (i) => { if (i === curState) return; curState = i; states.forEach((el, k) => el.classList.toggle('is-on', k === i)); steps.forEach((el, k) => el.classList.toggle('is-active', k === i)); };
  if (steps[0]) steps[0].classList.add('is-active');
  if (hero && reduced) hero.classList.add('is-static');

  let drawOnce = () => {};
  if (hero && canvas && !reduced) {
    const ctx = canvas.getContext('2d');
    const N = 360, P = [];
    let W = 0, H = 0, dpr = 1, px = 0.5, py = 0.5, t = 0;
    const rnd = (seed) => { let s = seed; return () => (s = (s * 16807) % 2147483647) / 2147483647; };
    const r = rnd(42);
    for (let i = 0; i < N; i++) P.push({ x: r(), y: r(), j: r(), k: r(), v: .4 + r() * .6, keep: i < 5, star: i === 0 });
    // 0 open market · 1 market map grid · 2 screening rings · 3 shortlist of 5 · 4 one hire · 5 scale outward
    const layout = (p, s, i) => {
      const ring = (rad, ph) => [0.68 + Math.cos(ph) * rad * .55, 0.5 + Math.sin(ph) * rad];
      switch (s) {
        case 0: return [p.x, p.y, .5, 1];
        case 1: { const col = i % 24, row = Math.floor(i / 24); return [0.4 + col * 0.024, 0.14 + row * 0.05 + Math.sin(p.j * 9 + t * .6) * .008, .85, 1.2]; }
        case 2: { const rad = .16 + p.j * .3; const ph = p.k * Math.PI * 2 + t * .05 * p.v; const [x, y] = ring(rad, ph); return [x, y, .5, 1]; }
        case 3: { if (p.keep) { const [x, y] = ring(.14, i * 1.2566 + t * .12); return [x, y, 1, 3.2]; } const rad = .4 + p.j * .3; const [x, y] = ring(rad, p.k * 6.283); return [x, y, .1, .8]; }
        case 4: { if (p.keep) return [0.68 + (i - 2) * .07, 0.5, 1, 3.4]; return [p.x, 1.1 + p.j * .3, 0, .5]; }
        default: { if (p.star) return [0.68, 0.5, 1, 6]; const rad = .12 + p.j * .42; const [x, y] = ring(rad, p.k * 6.283 + t * .04); return [x, y, .35, 1]; }
      }
    };
    const resize = () => { dpr = Math.min(devicePixelRatio || 1, 2); W = canvas.clientWidth; H = canvas.clientHeight; canvas.width = W * dpr; canvas.height = H * dpr; ctx.setTransform(dpr, 0, 0, dpr, 0, 0); };
    resize(); addEventListener('resize', resize);
    addEventListener('pointermove', (e) => { px = e.clientX / innerWidth; py = e.clientY / innerHeight; }, { passive: true });
    const ease = (x) => x < .5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2;
    const VIO = '124,58,237', MINT = '6,214,160';
    let running = true;
    const draw = () => {
      t += 1 / 60; ctx.clearRect(0, 0, W, H);
      const s = Math.floor(clamp(stageT, 0, LAST - .001)), f = ease(clamp(stageT - s));
      const ox = (px - .5) * -24, oy = (py - .5) * -16, mob = mobile();
      const pts = [];
      for (let i = 0; i < N; i++) {
        const p = P[i], a = layout(p, s, i), b = layout(p, Math.min(LAST, s + 1), i);
        let x = (a[0] + (b[0] - a[0]) * f), y = (a[1] + (b[1] - a[1]) * f);
        if (mob) { x = (x - .68) * 1.3 + .5; y = y * .55; }
        x = x * W + ox; y = y * H + oy;
        const al = a[2] + (b[2] - a[2]) * f, sz = a[3] + (b[3] - a[3]) * f;
        if (al < .02) continue; pts.push([x, y, al, sz, p]);
      }
      if (s <= 2) { ctx.lineWidth = .7; const lim = s === 0 ? 64 : 42; for (let i = 0; i < pts.length; i += 2) for (let j = i + 2; j < pts.length; j += 3) { const dx = pts[i][0] - pts[j][0], dy = pts[i][1] - pts[j][1]; const d = dx * dx + dy * dy; if (d < lim * lim) { ctx.strokeStyle = `rgba(${VIO},${(1 - d / (lim * lim)) * .18 * pts[i][2]})`; ctx.beginPath(); ctx.moveTo(pts[i][0], pts[i][1]); ctx.lineTo(pts[j][0], pts[j][1]); ctx.stroke(); } } }
      if (s === 3 || (s === 4 && f < .5)) { ctx.strokeStyle = `rgba(${MINT},.45)`; ctx.lineWidth = 1; const kk = pts.filter((q) => q[4].keep); for (let i = 0; i < kk.length; i++) for (let j = i + 1; j < kk.length; j++) { ctx.beginPath(); ctx.moveTo(kk[i][0], kk[i][1]); ctx.lineTo(kk[j][0], kk[j][1]); ctx.stroke(); } }
      for (const [x, y, al, sz, p] of pts) {
        const rr = (p.keep ? 2.4 : 1.6) * sz;
        if (p.star && s >= 4) { const g = ctx.createRadialGradient(x, y, 0, x, y, 120 + Math.sin(t * 2) * 12); g.addColorStop(0, `rgba(${MINT},.35)`); g.addColorStop(1, `rgba(${MINT},0)`); ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, 130, 0, 6.283); ctx.fill(); ctx.strokeStyle = `rgba(${MINT},.55)`; ctx.lineWidth = 1.5; for (let q = 1; q <= 3; q++) { const rad = 40 * q + ((t * 40) % 40); ctx.globalAlpha = 1 - rad / 160; ctx.beginPath(); ctx.arc(x, y, rad, 0, 6.283); ctx.stroke(); } ctx.globalAlpha = 1; }
        ctx.fillStyle = p.keep ? `rgba(${MINT},${al})` : `rgba(${VIO},${al * .8})`;
        ctx.beginPath(); ctx.arc(x, y, rr, 0, 6.283); ctx.fill();
      }
      if (running) requestAnimationFrame(draw);
    };
    drawOnce = draw;
    requestAnimationFrame(draw);
    // pause the loop while the hero is off-screen
    new IntersectionObserver((es) => { const on = es[0].isIntersecting; if (on && !running) { running = true; requestAnimationFrame(draw); } if (!on) running = false; }).observe(hero);
  }

  const heroFrame = () => {
    if (!hero || reduced) return;
    const rect = hero.getBoundingClientRect(), vh = innerHeight;
    const p = clamp(-rect.top / (rect.height - vh));
    const tt = Math.min(LAST, (p / .92) * LAST), s = Math.floor(Math.min(tt, LAST - .001)), f = tt - s;
    const g = clamp((f - .15) / .7);
    stageT = s + g;
    show(f < .5 ? s : Math.min(LAST, s + 1));
    steps.forEach((el, i) => el.style.setProperty('--fill', clamp(tt - i)));
  };

  /* ---------- pinned card stacks (specialisms + roles) ---------- */
  const folios = $$('[data-folio]');
  const folioFrame = () => {
    if (mobile() || reduced) return;
    folios.forEach((folio) => {
      const cards = $$('[data-card]', folio); if (!cards.length) return;
      const rect = folio.getBoundingClientRect(), p = clamp(-rect.top / (rect.height - innerHeight));
      const idx = p * (cards.length - 1);
      folio.dataset.focus = String(Math.round(idx));
      cards.forEach((c, k) => { const d = k - idx; c.style.setProperty('--d', Math.max(d, -1.2)); c.style.setProperty('--o', clamp(1 + d / .6)); c.classList.toggle('is-gone', d < -.9); c.style.zIndex = String(100 - Math.round(Math.abs(d) * 10)); });
    });
  };

  /* ---------- approach drum ---------- */
  const approach = $('[data-approach]'), stepsEls = $$('[data-step]');
  const drumFrame = () => {
    if (!approach || mobile() || reduced) return;
    const rect = approach.getBoundingClientRect(), p = clamp(-rect.top / (rect.height - innerHeight));
    const idx = Math.min(stepsEls.length - 1, Math.floor(p * stepsEls.length));
    approach.dataset.drumStep = String(idx + 1);
    stepsEls.forEach((el, k) => { const d = k - idx; el.style.setProperty('--r', d * -28); el.style.setProperty('--o', d === 0 ? 1 : 0); });
  };

  const frame = () => {
    heroFrame(); folioFrame(); drumFrame();
    if (header) { header.classList.toggle('is-scrolled', scrollY > 48); header.style.setProperty('--page-progress', clamp(scrollY / (document.documentElement.scrollHeight - innerHeight))); }
  };
  let ticking = false;
  const onScroll = () => { if (ticking) return; ticking = true; requestAnimationFrame(() => { frame(); ticking = false; }); };
  addEventListener('scroll', onScroll, { passive: true }); addEventListener('resize', onScroll); frame();

  /* ---------- reveals + count-ups + failsafe ---------- */
  const countUp = (el) => { const to = Number(el.dataset.count), t0 = performance.now(), d = 1400; if (reduced || el.dataset.done) { el.textContent = to.toLocaleString('en-GB'); return; } el.dataset.done = '1'; const step = (now) => { const k = clamp((now - t0) / d); el.textContent = Math.round(to * (1 - Math.pow(1 - k, 3))).toLocaleString('en-GB'); if (k < 1) requestAnimationFrame(step); }; requestAnimationFrame(step); };
  const reveal = (el) => { el.classList.add('is-in'); $$('[data-count]', el).forEach(countUp); };
  if ('IntersectionObserver' in window) {
    const io = new IntersectionObserver((es) => es.forEach((e) => { if (!e.isIntersecting) return; reveal(e.target); io.unobserve(e.target); }), { threshold: .01, rootMargin: '0px 0px 8% 0px' });
    $$('[data-reveal]').forEach((el) => io.observe(el));
  } else $$('[data-reveal]').forEach(reveal);
  setTimeout(() => $$('[data-reveal]:not(.is-in)').forEach(reveal), 2500);
  const bars = $('[data-bars]');
  if (bars) { bars.classList.add('is-hidden'); new IntersectionObserver((es, o) => { if (es[0].isIntersecting) { bars.classList.remove('is-hidden'); o.disconnect(); } }, { threshold: .3 }).observe(bars); setTimeout(() => bars.classList.remove('is-hidden'), 4000); }
  $$('[data-demo-form]').forEach((f) => f.addEventListener('submit', (e) => { e.preventDefault(); const ok = $('.form__ok', f), b = $('button[type=submit]', f); if (ok) ok.hidden = false; if (b) b.disabled = true; }));

  /* ---------- open roles: snapshot of the public feed, 2026-10-06 ----------
     [title, location, work_type, role_type, stage, base_min, base_max, ote_min, ote_max, currency, equity?] */
  const JOBS = [["Strategic Account Manager / Engagement Manager","New York, NY (Hybrid)","hybrid","Other","Seed",110000,150000,140000,190000,"USD",1],["Full-Stack Software Engineer","New York, NY (On-site)","onsite","Other","Seed",120000,160000,null,null,"USD",1],["Senior DevOps Engineer","New York, NY (On-site)","onsite","Other","Seed",160000,200000,null,null,"USD",1],["Sales Executive","London","hybrid","Sales",null,60000,75000,35000,40000,"GBP",0],["Account Executive","New York, NY (On-site)",null,"Sales","Seed",110000,135000,250000,250000,"USD",1],["Enterprise Account Executive (Founding Hire)","New York, NY (Hybrid)","hybrid","Sales","Seed",140000,180000,280000,300000,"USD",1],["Partner Implementation Manager","London","hybrid","CSM","Series C",70000,85000,null,null,"GBP",1],["GTM Associate (SDR)","London, UK","office","SDR/BDR","Bootstrapped",30000,50000,50000,65000,"GBP",0],["Partner Implementation Manager","New York","hybrid","CSM","Series C",90000,120000,null,null,"USD",1],["Partner Account Manager","London, UK","hybrid","Other","Series C",100000,170000,null,null,"GBP",1],["Account Manager","London","hybrid","Sales",null,65000,75000,35000,40000,"GBP",0],["Founding GTM","London","onsite","Sales","Pre-Seed",70000,140000,100000,170000,"GBP",1],["Sales Manager","London","office","Sales",null,35000,45000,40000,50000,"GBP",0],["SDR Manager","London (Hybrid)","hybrid","Sales","Series A",75000,85000,85000,95000,"GBP",0],["Senior Account Manager – Financial Data & Intelligence – London","London","office","Sales","Bootstrapped",80000,100000,120000,150000,"GBP",0],["Senior ML/AI Engineer","New York, NY (On-site)","onsite","Other","Seed",170000,230000,null,null,"USD",1],["Channel Co-Sell Director","Remote, United States","remote","Partnerships","Series C",200000,275000,null,null,"USD",0],["GTM Engineer","US / UK Remote (Austin, TX & London hubs)","remote","Sales","Seed",120000,180000,null,null,"USD",1],["Senior Account Executive - UK & Ireland","Remote (UK)","remote","Sales","Seed",90000,120000,180000,240000,"GBP",1],["Founding Client Partner","London, UK","hybrid","Sales","Seed",90000,110000,185000,220000,"GBP",1],["Forward Deployed Engineer - AI Agents (Retail & Consumer Goods)","Remote (UK/EU)","remote","Other","Seed",110000,200000,null,null,"EUR",1],["Customer Account Manager","London, UK","hybrid","Sales",null,60000,80000,120000,130000,"GBP",0],["Commercial Account Executive","Paris, France","hybrid","Sales",null,60000,60000,100000,100000,"EUR",0],["Account Executive","San Francisco","remote","Sales","Series A",125000,150000,250000,300000,"USD",0],["Product Marketing Manager (First PMM Hire)","New York, NY (On-site)","onsite","Marketing","Seed",125000,175000,null,null,"USD",1]];
  const list = $('[data-roles-list]'), count = $('[data-roles-count]'), filters = $('[data-roles-filters]');
  if (list) {
    const SYM = { GBP: '£', USD: '$', EUR: '€' };
    const k = (n) => (n >= 1000 ? Math.round(n / 1000) + 'k' : String(n));
    const range = (a, b, c) => a == null ? '—' : SYM[c] + k(a) + (b && b !== a ? '–' + SYM[c] + k(b) : '');
    const city = (l) => /^london/i.test(l) ? 'London' : /new york/i.test(l) ? 'New York' : /san francisco/i.test(l) ? 'San Francisco' : /paris/i.test(l) ? 'Paris' : /remote/i.test(l) ? 'Remote' : l;
    const WORK = { hybrid: 'Hybrid', onsite: 'On-site', office: 'Office', remote: 'Remote' };
    const locMatch = (loc, j) => !loc || (loc === 'Remote' ? j[2] === 'remote' || /remote/i.test(j[1]) : city(j[1]) === loc);
    let fType = '', fLoc = '';
    const render = () => {
      const rows = JOBS.filter((j) => (!fType || j[3] === fType) && locMatch(fLoc, j));
      list.innerHTML = rows.length ? rows.map((j, i) => `<article class="card" data-card><span class="card__n">${String(i + 1).padStart(2, '0')}</span><div class="card__body"><p class="card__meta"><span>${esc(j[1])}</span>${j[2] ? `<span>${WORK[j[2]] || esc(j[2])}</span>` : ''}${j[4] ? `<span>${esc(j[4])}</span>` : ''}<span>${esc(j[3])}</span></p><h3>${esc(j[0])}</h3><div class="card__comp"><div><span>Base</span><b>${range(j[5], j[6], j[9])}</b></div><div><span>OTE</span><b>${range(j[7], j[8], j[9])}</b></div></div>${j[10] ? '<p class="card__eq"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true"><path d="m5 13 4 4L19 7"/></svg>Equity</p>' : ''}</div></article>`).join('')
        : '<article class="card card--empty" data-card><div class="card__body"><h3>No roles match.</h3><p>Try another filter or <a href="#contact">register your interest</a>.</p></div></article>';
      if (count) count.textContent = String(rows.length);
      const folio = list.closest('[data-folio]'); if (folio) folio.style.minHeight = (mobile() || reduced) ? '' : `${Math.max(3, rows.length) * 100}svh`;
      folioFrame();
    };
    if (filters) filters.addEventListener('click', (e) => {
      const b = e.target.closest('button'); if (!b) return;
      if ('fType' in b.dataset) { fType = b.dataset.fType; $$('[data-f-type]', filters).forEach((x) => x.setAttribute('aria-pressed', String(x === b))); }
      if ('fLoc' in b.dataset) { fLoc = b.dataset.fLoc; $$('[data-f-loc]', filters).forEach((x) => x.setAttribute('aria-pressed', String(x === b))); }
      render();
      if (!mobile() && !reduced) { const top = filters.getBoundingClientRect().top + scrollY - 84; if (Math.abs(top - scrollY) > 2) scrollTo({ top, behavior: 'auto' }); }
    });
    render();
  }

  /* ---------- pricing toggle + fee calculator ---------- */
  const tg = $('[data-toggle]');
  if (tg) tg.addEventListener('click', (e) => {
    const b = e.target.closest('[data-mode]'); if (!b) return;
    $$('[data-mode]', tg).forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
    $$('[data-price],[data-year]').forEach((p) => { const v = p.dataset[b.dataset.mode]; if (v != null) p.textContent = v; });
  });
  const fees = $('[data-fees-details]'); if (fees) fees.open = innerWidth >= 1050;
  const calc = $('[data-calc]');
  if (calc) {
    const base = $('[data-calc-base]', calc), out = $('[data-calc-base-out]', calc), tier = $('[data-calc-tier]', calc), fee = $('[data-calc-fee]', calc), trad = $('[data-calc-trad]', calc), note = $('[data-calc-note]', calc);
    const T = { launchpad: { rate: .20, g: '3-month' }, scaleup: { rate: .175, g: '6-month' }, unicorn: { rate: .15, g: '12-month rolling' } };
    const gbp = (n) => '£' + Math.round(n).toLocaleString('en-GB');
    const run = () => {
      const b = Math.max(0, +base.value || 0), t = T[tier.value] || T.unicorn, ours = b * t.rate, theirs = b * .30;
      if (out) out.textContent = gbp(b); if (fee) fee.textContent = gbp(ours); if (trad) trad.textContent = gbp(theirs);
      if (note) note.textContent = `Saving ${gbp(theirs - ours)} on this hire · ${t.g} guarantee`;
    };
    [base, tier].forEach((el) => el && el.addEventListener('input', run)); run();
  }

  /* ---------- partners: audience chips + tap to open ---------- */
  const pf = $('[data-partner-filters]'), partners = $$('[data-partners] li');
  if (pf) pf.addEventListener('click', (e) => {
    const b = e.target.closest('[data-aud]'); if (!b) return;
    $$('[data-aud]', pf).forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
    const a = b.dataset.aud; partners.forEach((li) => { li.hidden = !!a && !li.dataset.aud.includes(a); });
  });
  partners.forEach((li) => { li.tabIndex = 0; li.addEventListener('click', () => li.classList.toggle('is-open')); li.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); li.classList.toggle('is-open'); } }); });
})();
