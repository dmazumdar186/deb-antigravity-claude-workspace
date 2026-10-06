/* GTM People concept — command deck. Zero dependencies, one IIFE. */
(() => {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const mobile = () => innerWidth < 800;

  /* ---------- header menu ---------- */
  const menu = $('[data-menu]'), toggle = $('[data-menu-toggle]');
  if (menu && toggle) {
    const narrow = () => innerWidth <= 1050;
    const setMenu = (open) => { menu.classList.toggle('is-open', open); toggle.setAttribute('aria-expanded', String(open)); menu.inert = !open && narrow(); };
    toggle.addEventListener('click', () => setMenu(!menu.classList.contains('is-open')));
    menu.addEventListener('click', (e) => { if (e.target.closest('a')) setMenu(false); });
    addEventListener('keydown', (e) => { if (e.key === 'Escape' && menu.classList.contains('is-open')) { setMenu(false); toggle.focus(); } });
    addEventListener('resize', () => { if (!narrow()) { menu.classList.remove('is-open'); menu.inert = false; } else if (!menu.classList.contains('is-open')) menu.inert = true; });
    menu.inert = narrow();
  }

  /* ---------- panel deck: tabs + hash routing ---------- */
  const tabs = $$('[data-tabs] [role=tab]'), panels = $$('.panel[role=tabpanel]'), deck = $('[data-deck]');
  const ids = panels.map((p) => p.id);
  let current = null;
  const headerOffset = () => { const h = $('.hdr'), n = $('.pnav'); return (h ? h.offsetHeight : 0) + (n ? n.offsetHeight : 0); };
  const activate = (id, { push = true, focus = false, scroll = true, instant = false } = {}) => {
    if (!ids.includes(id)) id = ids[0];
    if (!id) return;
    panels.forEach((p) => { p.hidden = p.id !== id; });
    const tabsEl = $('[data-tabs]');
    tabs.forEach((t) => { const on = t.getAttribute('aria-controls') === id; t.setAttribute('aria-selected', String(on)); t.tabIndex = on ? 0 : -1; if (on) { if (tabsEl) tabsEl.scrollTo({ left: t.offsetLeft - (tabsEl.clientWidth - t.offsetWidth) / 2, behavior: reduced || instant ? 'auto' : 'smooth' }); if (focus) t.focus({ preventScroll: true }); } });
    if (push && location.hash !== '#' + id) history.pushState({ panel: id }, '', '#' + id);
    if (scroll) { const panel = document.getElementById(id); if (panel) { const top = panel.getBoundingClientRect().top + scrollY - headerOffset() - 4; scrollTo({ top: Math.max(0, top), behavior: reduced || instant ? 'auto' : 'smooth' }); } }
    current = id;
    $$('.panel:not([hidden]) .reveal').forEach((el, i) => setTimeout(() => el.classList.add('is-in'), mobile() || reduced ? 0 : 40 * i));
  };
  tabs.forEach((t, i) => {
    t.addEventListener('click', (e) => { e.preventDefault(); activate(t.getAttribute('aria-controls')); });
    t.addEventListener('keydown', (e) => {
      const n = e.key === 'ArrowRight' ? i + 1 : e.key === 'ArrowLeft' ? i - 1 : e.key === 'Home' ? 0 : e.key === 'End' ? tabs.length - 1 : null;
      if (n === null) return; e.preventDefault();
      const t2 = tabs[(n + tabs.length) % tabs.length]; activate(t2.getAttribute('aria-controls'), { focus: true, scroll: false });
    });
  });
  // any in-page link to a panel id switches the deck (header, hero, footer, bottom bar)
  document.addEventListener('click', (e) => {
    const a = e.target.closest('a[data-go]'); if (!a) return;
    const id = (a.getAttribute('href') || '').replace('#', ''); if (!ids.includes(id)) return;
    e.preventDefault(); activate(id);
    const pre = a.getAttribute('data-prefill'), need = $('[data-need]');
    if (pre && need && !need.value) { need.value = pre; }
  });
  const fromHash = (push) => { const id = location.hash.replace('#', ''); if (ids.includes(id)) activate(id, { push, scroll: true, instant: !current }); else if (!current) activate(ids[0], { push: false, scroll: false }); };
  addEventListener('popstate', () => fromHash(false));
  addEventListener('hashchange', () => fromHash(false));
  fromHash(false);

  /* ---------- reveals (desktop only; phones always painted via CSS) ---------- */
  const reveals = $$('.reveal');
  if (!mobile() && !reduced && 'IntersectionObserver' in window) {
    const io = new IntersectionObserver((es) => es.forEach((en) => { if (en.isIntersecting) { en.target.classList.add('is-in'); io.unobserve(en.target); } }), { threshold: 0.01, rootMargin: '0px 0px 8% 0px' });
    reveals.forEach((el) => io.observe(el));
    setTimeout(() => reveals.forEach((el) => el.classList.add('is-in')), 2500);
  } else reveals.forEach((el) => el.classList.add('is-in'));

  const dia = $('.diagram'); if (dia) setTimeout(() => dia.classList.add('is-done'), reduced ? 0 : 1500);

  /* ---------- hero counters ---------- */
  if (!reduced) $$('[data-count]').forEach((el) => {
    const end = +el.dataset.count, suf = el.dataset.suffix || '', t0 = performance.now(), d = 1100;
    const tick = (t) => { const k = Math.min(1, (t - t0) / d), e = 1 - Math.pow(1 - k, 3); el.textContent = Math.round(end * e).toLocaleString('en-GB') + suf; if (k < 1) requestAnimationFrame(tick); };
    requestAnimationFrame(tick);
  });

  /* ---------- roles table ---------- */
  // Snapshot of the public roles feed, 2026-10-06. [title, location, work_type, role_type, company_stage, base_min, base_max, ote_min, ote_max, currency, description]
  const JOBS = [["Strategic Account Manager / Engagement Manager","New York, NY (Hybrid)","hybrid","Other","Seed",110000,150000,140000,190000,"USD","Own and grow a portfolio of Fortune 500 accounts at an AI-native consumer intelligence platform. You will be the glue between clients and the product and engineering teams - translating complex business needs into deployments that stick, and helping build the customer-experience function from scratch. A product-oriented CS/engagement role for someone who thinks like a PM but owns enterprise accounts. Hiring 1-2 people, tied to upcoming enterprise deals."],["Full-Stack Software Engineer","New York, NY (On-site)","onsite","Other","Seed",120000,160000,null,null,"USD","Work across every layer of an AI-native platform for enterprise retail and consumer brands - from the backend services that process enterprise data at scale to the frontend interfaces that make that intelligence usable. In a small team, full-stack means full ownership: take features from idea to production and iterate directly with enterprise clients. Recently seed-funded by leading investors and already proven with Fortune 500 clients. On-site in New York."],["Senior DevOps Engineer","New York, NY (On-site)","onsite","Other","Seed",160000,200000,null,null,"USD","Own the infrastructure that keeps an AI-native platform running at enterprise scale - the cloud systems Fortune 500 retailers trust with their most critical data and decision-making. A hands-on, high-ownership role working closely with backend and ML engineers to keep the platform secure, scalable and relentlessly reliable, built on GitOps and infrastructure-as-code. Recently seed-funded by leading investors. On-site in New York (some remote Fridays)."],["Sales Executive","London","hybrid","Sales",null,60000,75000,35000,40000,"GBP","A leading provider of business information services for legal, tax, accounting and compliance professionals, is hiring a Sales Executive to sell new technology solutions and drive cross-sell and up-sell opportunities across their suite of online, software and AI solutions. The role involves building pipelines, conducting consultative sales conversations, and managing the end-to-end sales process within assigned UK & Ireland territories."],["Account Executive","New York, NY (On-site)",null,"Sales","Seed",110000,135000,250000,250000,"USD","Become the founder of a vertical at an AI-native consumer intelligence platform. This is a role for an industry insider with a genuine passion for a specific consumer category (food & beverage, CPG or retail): own the full commercial motion in your vertical, leverage the platform to become the authority in your space, and build a book of business that grows with you. Seed-funded and already live with Fortune 500 brands. On-site in New York."],["Enterprise Account Executive (Founding Hire)","New York, NY (Hybrid)","hybrid","Sales","Seed",140000,180000,280000,300000,"USD","A genuine ground-floor GTM opportunity: become the first dedicated Enterprise AE at an AI-native consumer intelligence platform, selling to Fortune 500 companies with USD 10B+ in revenue. Seed-funded and already live with household-name brands across CPG, beauty, retail and travel. Own the full Fortune 500 sales cycle, write the playbook future AEs inherit, and step onto a clear path to Head of Sales."],["Partner Implementation Manager","London","hybrid","CSM","Series C",70000,85000,null,null,"GBP","Uncountable is an R&D platform used by enterprise chemists and material scientists to accelerate product discovery and development. This Partner Implementation Manager role bridges Uncountable's implementation team and partner ecosystem, starting as a hands-on IC before transitioning to oversee 3-5 partner-led implementations across enterprise accounts."],["GTM Associate (SDR)","London, UK","office","SDR/BDR","Bootstrapped",30000,50000,50000,65000,"GBP","Our client is a profitable, rapidly expanding real-time data and intelligence platform serving 300+ investment firms in private markets. The GTM Associate will run outbound campaigns end-to-end, research institutional buyers (VCs and PE investors), and work directly with founders to build and refine the outbound engine."],["Partner Implementation Manager","New York","hybrid","CSM","Series C",90000,120000,null,null,"USD","Uncountable is an R&D platform used by enterprise chemists and material scientists to accelerate product discovery and development. This Partner Implementation Manager role bridges Uncountable's implementation team and partner ecosystem, starting as a hands-on IC before transitioning to oversee 3-5 partner-led implementations across enterprise accounts."],["Partner Account Manager","London, UK","hybrid","Other","Series C",100000,170000,null,null,"GBP","Partner Account Manager for a rapidly expanding technology provider (Series C) in the networking space. Own the UK installation-partner network - relationships, KPI performance management, programme-building. Hybrid London, 30-40% field travel."],["Account Manager","London","hybrid","Sales",null,65000,75000,35000,40000,"GBP",null],["Founding GTM","London","onsite","Sales","Pre-Seed",70000,140000,100000,170000,"GBP","First commercial hire at a stealth-stage AI company transforming the $3T commercial insurance market. Own outbound prospecting and closing for the world's largest insurance brokers, working directly with the founders to build the GTM engine from scratch: cold outreach + personalised LinkedIn + targeted prospecting into the top 20 global brokers; full sales cycle from first touch to pilot close; conferences and in-person meetings; manage/improve GTM tooling (CRM, Clay, automated outreach); help kick off pilots with 12 of the top 20 brokers by year end.\r\n \r\n5 days in-office in London. Relocation available; visa sponsorship / transfers on the table (OPT, H1B, TN). Looking to hire 1-2. Reports to Jedrzej Brozyna (Founders Associate).\r\n \r\nInterview process: Initial behavioural screen with Jed (30m) -> Behavioural deep-dive with Gagan, CEO (45m) -> Half-day on-site case study & working trial (GTM case + consulting-style pricing case + build a working AI demo and role-play the deal)."],["Sales Manager","London","office","Sales",null,35000,45000,40000,50000,"GBP","Expanding retail technology company seeks a driven Sales Manager to source and secure new sales opportunities for their specialised retail software solutions serving the Apparel, Footwear and General Merchandise sectors. The role involves managing the full sales pipeline from cold-calling to contract closure, with comprehensive team support and potential for future leadership responsibilities."],["SDR Manager","London (Hybrid)","hybrid","Sales","Series A",75000,85000,85000,95000,"GBP","AI-native employee-benefits (HR Tech) B2B SaaS, ~20 people, fresh off a multi-million-pound Series A and named among the UK's leading startups. First SDR Manager hire to build and own the outbound engine from scratch and scale a growing SDR/BDR team. London, hybrid (3+ days)."],["Senior Account Manager – Financial Data & Intelligence – London","London","office","Sales","Bootstrapped",80000,100000,120000,150000,"GBP","Our client is a profitable, rapidly expanding real-time data and intelligence platform serving 300+ investment firms in private markets. The founding senior account manager will run end-to-end account management function including building out the playbook and dealing with growth, renewals and all other aspects of account management in the institutional buyers (VCs and PE investors) market place,"],["Senior ML/AI Engineer","New York, NY (On-site)","onsite","Other","Seed",170000,230000,null,null,"USD","Build and deploy the intelligent systems at the core of an AI-native platform for enterprise retail and consumer brands - models and agentic architectures that power demand forecasting, consumer intelligence, competitive analysis and autonomous decision-making for some of the world's largest retailers. This is applied AI at real enterprise scale, generating meaningful value for Fortune 500 clients. Recently seed-funded by leading investors, with a small, engineering-heavy team. On-site in New York."],["Channel Co-Sell Director","Remote, United States","remote","Partnerships","Series C",200000,275000,null,null,"USD","Own and accelerate Netomi's co-sell status and marketplace strategy across AWS, Azure and GCP - unlocking committed cloud spend and co-sell motions. Analyse cloud-spend architecture (hundreds of thousands/month on AWS) to optimise routing and marketplace credit; build the hyperscaler co-sell playbook; create enablement assets (playbooks, transaction guides, pitch decks, certification); work with the VP of Alliances and cross-functional GTM/Product/SE teams; support marketplace transactions and private offers; track partner activation, marketplace pipeline and sourced/influenced revenue.\r\n \r\nFully remote (US-based). Travel 30-40%; proximity to a major airport important. Not open to visa sponsorship (US citizen / Green Card only).\r\n \r\nInterview process: GTM Team Screen (30m) -> Head of Product (Brian McDonald, 45m) -> Chief of Staff (David Herrera, 45m) -> Take-home project -> President 1:1 (Justin Wexler, 30m) -> Panel presentation (1h)."],["GTM Engineer","US / UK Remote (Austin, TX & London hubs)","remote","Sales","Seed",120000,180000,null,null,"USD","First commercial hire (GTM Engineer) a leading VC backed AI voice-agent QA platform. Full-cycle high-agency IC, AI-native tooling essential. Remote US/UK."],["Senior Account Executive - UK & Ireland","Remote (UK)","remote","Sales","Seed",90000,120000,180000,240000,"GBP","A rare first-AE opportunity to own the entire UK & Ireland patch for an AI-native automation platform for retail and FMCG enterprises, backed by a top-tier investor and approaching Series A. You will sell into enterprise operations teams, build territory from scratch, and shape the go-to-market motion alongside the founders. Fully remote in the UK, with uncapped commission and seed-stage equity."],["Founding Client Partner","London, UK","hybrid","Sales","Seed",90000,110000,185000,220000,"GBP","Founding UK Client Partner for a Seed-stage, backed by a leading US venture capital player in agentic-AI performance-marketing platform. Player-coach role owning the full UK sales cycle."],["Forward Deployed Engineer - AI Agents (Retail & Consumer Goods)","Remote (UK/EU)","remote","Other","Seed",110000,200000,null,null,"EUR","A rare Forward Deployed Engineer role with one of Europe's most exciting AI companies - embedding directly with enterprise retail and consumer-goods customers to ship agentic AI and automation into live operations. Our client is a fast-growing, venture-backed platform (world-class European investors) already trusted by some of Europe's largest retailers and brands. Fully remote across the UK/EU, with real ownership and equity upside at a genuinely early-stage business."],["Customer Account Manager","London, UK","hybrid","Sales",null,60000,80000,120000,130000,"GBP","Customer Account Manager  - cross-sell/upsell tax-tech SaaS to existing EMEA accounts. Hybrid London 1-2 times a month."],["Commercial Account Executive","Paris, France","hybrid","Sales",null,60000,60000,100000,100000,"EUR","New-business Commercial AE selling e-invoicing & indirect-tax SaaS across France. Hybrid Paris, 3 days/week."],["Account Executive","San Francisco","remote","Sales","Series A",125000,150000,250000,300000,"USD","Series B company (funded $20M) that uses AI to remake consumer underwriting for residential real estate, targeting institutional property managers and real estate investors. The Account Executive role is full-cycle sales of enterprise deals ($50K-$300K+ ARR), running prospecting through close over 2-5 month cycles."],["Product Marketing Manager (First PMM Hire)","New York, NY (On-site)","onsite","Marketing","Seed",125000,175000,null,null,"USD","The first dedicated Product Marketing hire at an AI-native consumer intelligence platform - build the PMM function from scratch with real budget and executive support. Own mid-to-bottom-funnel conversion from positioning and messaging through to sales enablement and launch execution, with measurable impact on win rates, conversion and influenced pipeline. Seed-funded, revenue-generating, and live with Fortune 500 brands."]];
  const body = $('[data-roles-body]'), sum = $('[data-role-sum]'), rc = $('[data-role-count]');
  if (body) {
    const SYM = { GBP: '£', USD: '$', EUR: '€' };
    const k = (n) => n == null ? '' : (n >= 1000 ? Math.round(n / 1000) + 'k' : n);
    const range = (a, b, c) => a == null ? '—' : SYM[c] + k(a) + (b && b !== a ? '–' + k(b) : '');
    const city = (l) => /^london/i.test(l) ? 'London' : /new york/i.test(l) ? 'New York' : /san francisco/i.test(l) ? 'San Francisco' : /paris/i.test(l) ? 'Paris' : /remote/i.test(l) ? 'Remote' : l;
    const work = { hybrid: 'Hybrid', onsite: 'On-site', office: 'Office', remote: 'Remote' };
    const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
    const rows = JOBS.map((j) => ({ t: j[0], loc: j[1], city: city(j[1]), w: work[j[2]] || '—', type: j[3] || 'Other', stage: j[4] || 'Undisclosed', b: j[5], bmax: j[6], o: j[7], omax: j[8], c: j[9], d: j[10] || '' }));
    const state = { loc: '', type: '', stage: '', q: '', sort: 0, dir: 1 };
    const render = () => {
      let list = rows.filter((r) => (!state.loc || r.city === state.loc) && (!state.type || r.type === state.type) && (!state.stage || r.stage === state.stage) && (!state.q || r.t.toLowerCase().includes(state.q)));
      const key = ['t', 'city', 'type', 'stage', 'b', 'o'][state.sort];
      list.sort((x, y) => { const a = x[key] ?? -1, b = y[key] ?? -1; return (a > b ? 1 : a < b ? -1 : 0) * state.dir; });
      body.innerHTML = list.length ? list.map((r, i) => `<tr><td><button type="button" class="rt" aria-expanded="false" aria-controls="rd${i}">${esc(r.t)}</button></td><td>${esc(r.loc)}</td><td><span class="tag p">${esc(r.type)}</span></td><td>${esc(r.stage)}</td><td>${range(r.b, r.bmax, r.c)}</td><td>${range(r.o, r.omax, r.c)}</td><td><span class="tag">${r.w}</span></td></tr><tr class="rd" id="rd${i}" hidden><td colspan="7">${esc(r.d)}</td></tr>`).join('')
        : '<tr><td colspan="7">No roles match your filters. <a href="#contact" data-go>Register your interest →</a></td></tr>';
      if (sum) sum.textContent = `${list.length} of ${rows.length} roles shown · snapshot 2026-10-06`;
      if (rc) rc.textContent = rows.length;
    };
    $$('[data-role-filters] [data-f]').forEach((el) => el.addEventListener('input', () => { state[el.dataset.f] = el.dataset.f === 'q' ? el.value.trim().toLowerCase() : el.value; render(); }));
    body.addEventListener('click', (e) => { const b = e.target.closest('.rt'); if (!b) return; const row = document.getElementById(b.getAttribute('aria-controls')); if (!row) return; row.hidden = !row.hidden; b.setAttribute('aria-expanded', String(!row.hidden)); });
    $$('[data-sort]').forEach((b) => b.addEventListener('click', () => { const s = +b.dataset.sort; state.dir = state.sort === s ? -state.dir : 1; state.sort = s; render(); }));
    render();
  }

  /* ---------- pricing toggle + fee calculator ---------- */
  const tg = $('[data-toggle]');
  if (tg) tg.addEventListener('click', (e) => {
    const b = e.target.closest('[data-mode]'); if (!b) return;
    $$('[data-mode]', tg).forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
    $$('[data-price]').forEach((p) => { p.textContent = p.dataset[b.dataset.mode]; });
  });
  const calc = $('[data-calc]');
  if (calc) {
    const base = $('[data-calc-base]', calc), tier = $('[data-calc-tier]', calc), hires = $('[data-calc-hires]', calc), fee = $('[data-calc-fee]', calc), tot = $('[data-calc-total]', calc), tn = $('[data-calc-total-note]', calc);
    const T = { launchpad: { sub: 5000, rate: .20, inc: 0, cap: 0, g: '3-month' }, scaleup: { sub: 10000, rate: .175, inc: 1, cap: 75000, g: '6-month' }, unicorn: { sub: 30000, rate: .15, inc: 2, cap: 100000, g: '12-month rolling' } };
    const gbp = (n) => '£' + Math.round(n).toLocaleString('en-GB');
    const run = () => {
      const b = Math.max(0, +base.value || 0), n = Math.max(1, +hires.value || 1), t = T[tier.value] || T.unicorn;
      const perHire = b * t.rate, trad = b * .30, included = b <= t.cap ? Math.min(n, t.inc) : 0, billed = n - included;
      const total = t.sub + billed * perHire;
      if (fee) fee.innerHTML = `${gbp(perHire)} <s>${gbp(trad)}</s>`;
      if (tot) tot.textContent = gbp(total);
      if (tn) tn.textContent = `Annual: ${gbp(t.sub)} subscription + ${billed} billed hire${billed === 1 ? '' : 's'}${included ? ` (${included} included)` : ''} · ${t.g} guarantee · vs ${gbp(n * trad)} at a traditional agency`;
    };
    [base, tier, hires].forEach((el) => el && el.addEventListener('input', run)); run();
  }

  /* ---------- partners filter ---------- */
  const pf = $('[data-pfilters]'), pc = $('[data-partners]'), pcount = $('[data-pcount]');
  if (pf && pc) pf.addEventListener('click', (e) => {
    const b = e.target.closest('[data-pf]'); if (!b) return;
    $$('[data-pf]', pf).forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
    const f = b.dataset.pf; let n = 0;
    $$('[data-for]', pc).forEach((c) => { const show = f === 'all' || c.dataset.for.split(' ').includes(f); c.hidden = !show; if (show && !c.classList.contains('want')) n++; });
    pc.scrollTo({ left: 0, behavior: 'auto' });
    if (pcount) pcount.textContent = `${n} partner${n === 1 ? '' : 's'} shown · partner logos shown as initials in this concept; links go live with the real partner URLs.`;
  });

  /* ---------- forms: concept, not wired ---------- */
  const wire = (form, notice) => { if (!form) return; form.addEventListener('submit', (e) => { e.preventDefault(); if (!form.checkValidity()) { form.reportValidity(); return; } if (notice) { notice.hidden = false; notice.scrollIntoView({ block: 'nearest' }); } }); };
  wire($('[data-contact]'), $('[data-contact-notice]'));
  wire($('[data-newsletter]'), $('[data-nl-notice]'));
})();
