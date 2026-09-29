// Headless-Chromium UI-layout regression suite for the GreenJobs redesign.
// description: Loads every page type of both editions at 1440x900, 1024x768
//   and 390x844 in light and dark themes and asserts, from DOM geometry, the
//   eleven defect classes a human found by eye on 2026-09-28
//   (research/qa_2026-09-28/visual_issues*.md): horizontal overflow, chip
//   height / orphaned dot, chip rows off their line, broken comparison
//   tables, overlapping text, clipped controls, uneven button rows, hero
//   trust block wrapping, unreachable filter controls, console/network
//   errors and text contrast. Also writes a viewport screenshot per
//   page/viewport/theme to .tmp/layout_baseline/ and, when
//   tests/greenjobs_redesign/layout_baseline/ holds a JPEG for that shot,
//   compares the two in-page via canvas (pixelmatch-style, no deps) and fails
//   above 1.5 % differing pixels. Skips (exit 0) when Chromium or Playwright
//   is absent.
// inputs: optional site dir argument or SITE env (default:
//   deliverables/greenjobs_redesign_2026-09-22/site, built with build_site.py
//   when missing); PORT env (default 8763); PW_CHROMIUM env (default
//   /opt/pw-browsers/chromium); --update-baseline refreshes the committed
//   JPEG baseline (1440-light and 390-dark sets only, quality 40);
//   --only=<substring> restricts page keys; --quick runs 1440 light only.
// outputs: one PASS/FAIL/KNOWN line per assertion with page/viewport/theme;
//   exit 1 on any FAIL
// Run: node tests/greenjobs_redesign/layout.test.mjs [site-dir] [--update-baseline]
import { spawn, spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HERE, '..', '..');
const DELIV = join(REPO, 'deliverables', 'greenjobs_redesign_2026-09-22');
const CHROMIUM = process.env.PW_CHROMIUM || '/opt/pw-browsers/chromium';
const PORT = Number(process.env.PORT || 8763);
const ARGS = process.argv.slice(2);
const UPDATE = ARGS.includes('--update-baseline');
const QUICK = ARGS.includes('--quick');
const ONLY = (ARGS.find((a) => a.startsWith('--only=')) || '').slice(7);
const SHOTS = join(REPO, '.tmp', 'layout_baseline');
const BASELINE = join(HERE, 'layout_baseline');
const DIFF_LIMIT = 0.015;

// Real defects the suite catches that are documented and not yet fixed. A
// matching failure prints KNOWN instead of FAIL and does not fail the run;
// remove the entry once the defect is fixed so the rule guards it again.
const KNOWN_DEFECTS = [
];

const results = [];
const known = [];
function check(ok, label) {
  if (!ok) {
    const k = KNOWN_DEFECTS.find((d) => (d.rule == null || label.startsWith(`R${d.rule} `)) && d.match.test(label));
    if (k) { known.push(label + ' — ' + k.note); console.log('KNOWN ' + label + ' — ' + k.note); return; }
  }
  results.push([ok, label]);
  console.log((ok ? 'PASS  ' : 'FAIL  ') + label);
}

const require = createRequire(import.meta.url);
let chromium = null;
for (const mod of ['playwright', '/opt/node22/lib/node_modules/playwright']) {
  try { ({ chromium } = require(mod)); break; } catch { /* try the next location */ }
}
if (!chromium || !existsSync(CHROMIUM)) {
  console.log(`SKIP  layout regression: ${!chromium ? 'playwright is not installed' : 'chromium missing at ' + CHROMIUM}`);
  process.exit(0);
}

let site = ARGS.find((a) => !a.startsWith('--')) || process.env.SITE || join(DELIV, 'site');
site = resolve(site);
if (!existsSync(join(site, 'ie', 'index.html'))) {
  const build = spawnSync('python3', [join(REPO, 'execution', 'gtm_client_workflows', 'greenjobs_redesign', 'build_site.py'), '--src', join(DELIV, 'src'), '--out', site, '--edition', 'both'], { encoding: 'utf8' });
  if (build.status !== 0) { console.log('FAIL  layout regression: site build failed\n' + build.stderr); process.exit(1); }
}
mkdirSync(SHOTS, { recursive: true });
if (UPDATE) mkdirSync(BASELINE, { recursive: true });

const VIEWPORTS = [[1440, 900], [1024, 768], [390, 844]];
const THEMES = ['light', 'dark'];
const BASELINE_SETS = new Set(['1440-light', '390-dark']);
// Page keys that get a committed baseline JPEG (10 keys x 2 editions x 2 sets = 40 files).
const BASELINE_KEYS = new Set(['home', 'jobs', 'jobs-map', 'job', 'sectors', 'insights', 'compass-result', 'employers', 'dashboard', 'landing']);

function pages(ed) {
  const landing = ed === 'ie' ? 'ecology-jobs-ireland' : 'ecology-jobs-uk';
  const job = ed === 'ie' ? 'jobs/11500760/index.html' : 'jobs/11501639/index.html';
  const P = [
    ['home', 'index.html'],
    ['jobs', 'jobs/index.html'],
    ['jobs-map', 'jobs/index.html?view=map'],
    ['jobs-facets', 'jobs/index.html?sector=Sustainable+infrastructure&wp=Hybrid'],
    ['job', job],
    ['sectors', 'sectors/index.html'],
    ['insights', 'insights/index.html'],
    ['compass', 'compass/index.html'],
    ['compass-result', 'compass/index.html#a=0.0.0.0.0.0.0'],
    ['employers', 'employers/index.html'],
    ['dashboard', 'dashboard/index.html'],
    ['landing', landing + '/index.html'],
    ['guides', 'guides/index.html'],
    ['salary-guide', 'guides/salary-guide/index.html'],
    ['cookie-dialog', 'index.html?popup=cookie'],
    ['subscribe-dialog', 'index.html?popup=subscribe'],
    ['filter-sheet', 'jobs/index.html', { sheet: true }],
  ];
  return P.map(([key, path, opt]) => ({ key: `${ed}/${key}`, url: `${ed}/${path}`, ...(opt || {}) }));
}
const PAGES = [...pages('ie'), ...pages('uk'), { key: 'root/404', url: '404.html' }].filter((p) => !ONLY || p.key.includes(ONLY));

// ---- in-page geometry audit (serialised into the browser) ----------------
function audit(cfg) {
  const W = cfg.width;
  const out = { overflow: null, tags: [], meta: [], tables: [], overlaps: [], clipped: [], buttonRows: [], trust: null, rail: null, contrast: [] };
  const vis = (el) => {
    if (!el || !(el instanceof Element)) return false;
    if (el.closest('[hidden],dialog:not([open]),details:not([open]) :not(summary)')) return false;
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || Number(cs.opacity) === 0) return false;
    const r = el.getBoundingClientRect();
    if (r.width <= 0 || r.height <= 0) return false;
    // visually-hidden pattern (1px box, overflow hidden, clip rect) on the element or an ancestor
    for (let p = el; p && p !== document.body; p = p.parentElement) {
      const ps = p === el ? cs : getComputedStyle(p);
      if (ps.overflow === 'hidden' && ps.clip !== 'auto' && p.getBoundingClientRect().width <= 1) return false;
    }
    return true;
  };
  const rect = (el) => { const r = el.getBoundingClientRect(); return { l: r.left, t: r.top, r: r.right, b: r.bottom, w: r.width, h: r.height }; };
  const desc = (el) => (el.tagName.toLowerCase() + (el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\s+/).slice(0, 2).join('.') : '') + ' "' + (el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 40) + '"');
  const lh = (el) => { const cs = getComputedStyle(el); const v = parseFloat(cs.lineHeight); return Number.isFinite(v) ? v : parseFloat(cs.fontSize) * 1.2; };
  const textRects = (el) => {
    const rs = [];
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    let n;
    while ((n = walker.nextNode())) {
      if (!n.textContent.trim()) continue;
      const range = document.createRange(); range.selectNodeContents(n);
      for (const r of range.getClientRects()) if (r.width > 0 && r.height > 0) rs.push(r);
    }
    return rs;
  };
  // 1. horizontal overflow
  out.overflow = { scrollWidth: document.documentElement.scrollWidth, bodyScroll: document.body.scrollWidth, width: W };
  // 2. chips
  for (const tag of document.querySelectorAll('.tag')) {
    if (!vis(tag)) continue;
    const r = rect(tag); const L = lh(tag); const cs = getComputedStyle(tag);
    const inner = r.h - parseFloat(cs.paddingTop) - parseFloat(cs.paddingBottom) - parseFloat(cs.borderTopWidth) - parseFloat(cs.borderBottomWidth);
    const dot = tag.querySelector(':scope > i');
    const trs = textRects(tag);
    const textTop = trs.length ? Math.min(...trs.map((x) => x.top)) : r.t;
    const e = { d: desc(tag), h: inner, w: r.w, lh: L, ok: inner <= 2 * L + 1, dotOk: true, widthOk: true };
    if (dot && vis(dot)) {
      const dr = rect(dot); const cy = (dr.t + dr.b) / 2;
      e.dotOk = cy >= textTop - 0.5 && cy <= textTop + L + 0.5;
      e.widthOk = r.w >= dr.w + 4;
      e.dotCy = cy; e.textTop = textTop;
    }
    out.tags.push(e);
  }
  // 3. chip rows
  for (const meta of document.querySelectorAll('.row__meta')) {
    if (!vis(meta)) continue;
    const chips = [...meta.querySelectorAll(':scope > .tag, :scope > span')].filter(vis).map((c) => ({ r: rect(c), d: desc(c) }));
    if (chips.length < 2) continue;
    // group into flex lines by overlapping vertical extent, seeded in DOM order
    const lines = [];
    for (const c of chips) {
      const line = lines.find((ln) => c.r.t < ln.b - 1 && c.r.b > ln.t + 1);
      if (line) { line.items.push(c); line.t = Math.min(line.t, c.r.t); line.b = Math.max(line.b, c.r.b); } else lines.push({ t: c.r.t, b: c.r.b, items: [c] });
    }
    for (const ln of lines) {
      if (ln.items.length < 2) continue;
      const tops = ln.items.map((c) => c.r.t);
      const spread = Math.max(...tops) - Math.min(...tops);
      out.meta.push({ spread, ok: spread <= 4, d: ln.items.map((c) => c.d).join(' | ').slice(0, 160) });
    }
  }
  // 4. tables
  for (const wrap of document.querySelectorAll('.cmpwrap')) {
    if (!vis(wrap)) continue;
    const table = wrap.querySelector('table');
    const t = { ok: true, why: [] };
    if (!table) { t.ok = false; t.why.push('no table'); out.tables.push(t); continue; }
    const heads = [...table.querySelectorAll('thead th')].filter(vis).map(rect);
    const rows = [...table.querySelectorAll('tbody tr')].filter(vis);
    const tabular = rows.length && [...rows[0].children].every((c) => getComputedStyle(c).display === 'table-cell');
    t.mode = tabular ? 'table' : 'cards';
    for (const tr of rows) {
      const cells = [...tr.children].filter(vis);
      cells.forEach((c, i) => {
        const cr = rect(c); const band = heads[i];
        if (tabular && band && (cr.l < band.l - 1 || cr.r > band.r + 1)) t.why.push(`cell "${c.textContent.trim().slice(0, 20)}" outside column ${i} band`);
        if (cr.r > W + 1 || cr.l < -1) t.why.push(`cell "${c.textContent.trim().slice(0, 20)}" outside the viewport`);
        if (c.querySelector('button,.btn,[class*="pill"],[class*="chip"]')) t.why.push(`cell "${c.textContent.trim().slice(0, 20)}" renders a button/pill`);
        if (getComputedStyle(c).display === 'none') t.why.push(`cell ${i} hidden`);
      });
    }
    const hs = rows.map((tr) => rect(tr).h);
    if (tabular && hs.length && Math.max(...hs) - Math.min(...hs) > 2) t.why.push(`row heights ${Math.min(...hs).toFixed(1)}–${Math.max(...hs).toFixed(1)}`);
    if (W >= 701 && (wrap.scrollHeight > wrap.clientHeight + 1 || wrap.scrollWidth > wrap.clientWidth + 1)) t.why.push(`inner scroll ${wrap.scrollWidth}x${wrap.scrollHeight} in ${wrap.clientWidth}x${wrap.clientHeight}`);
    t.ok = t.why.length === 0; t.rows = rows.length;
    out.tables.push(t);
  }
  // 5. overlapping text within a section
  const SECTION = 'dialog,.cookie,.sheet,[data-marq],section,article,header,footer,nav,aside,form,main';
  const TEXT = 'h1,h2,h3,h4,h5,h6,p,button,a,label,.tag,.chip,li,td,th,dt,dd,legend,summary,time,small';
  const texts = [...document.querySelectorAll(TEXT)].filter((el) => vis(el) && (el.textContent || '').trim() && !el.closest('[data-marq],svg'));
  const groups = new Map();
  for (const el of texts) {
    const sec = el.closest(SECTION) || document.body;
    if (!groups.has(sec)) groups.set(sec, []);
    groups.get(sec).push({ el, r: rect(el) });
  }
  for (const items of groups.values()) {
    for (let i = 0; i < items.length; i++) for (let j = i + 1; j < items.length; j++) {
      const a = items[i], b = items[j];
      if (a.el.contains(b.el) || b.el.contains(a.el)) continue;
      const ix = Math.min(a.r.r, b.r.r) - Math.max(a.r.l, b.r.l), iy = Math.min(a.r.b, b.r.b) - Math.max(a.r.t, b.r.t);
      if (ix > 1 && iy > 1) {
        // an inline element wrapping across lines can legitimately "overlap" a sibling in bbox terms: confirm with text rects
        const ra = textRects(a.el), rb = textRects(b.el);
        const real = ra.some((x) => rb.some((y) => Math.min(x.right, y.right) - Math.max(x.left, y.left) > 1 && Math.min(x.bottom, y.bottom) - Math.max(x.top, y.top) > 1));
        if (real) out.overlaps.push(desc(a.el) + ' <> ' + desc(b.el));
      }
    }
  }
  // 6. clipped controls
  for (const el of document.querySelectorAll('button,a,input,select,textarea')) {
    if (!vis(el) || el.closest('[data-marq]')) continue;
    const r = rect(el);
    const why = [];
    if (r.r > W + 1 || r.l < -1) why.push(`outside viewport (${r.l.toFixed(0)}–${r.r.toFixed(0)})`);
    if ((el.tagName === 'BUTTON' || el.classList.contains('btn')) && el.scrollWidth > el.clientWidth + 1 && getComputedStyle(el).overflow !== 'visible') why.push(`label wider than button (${el.scrollWidth}>${el.clientWidth})`);
    if (el.tagName === 'INPUT' && el.placeholder && el.clientWidth) {
      const cs = getComputedStyle(el);
      const cv = document.createElement('canvas').getContext('2d');
      cv.font = `${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
      const inner = el.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
      const tw = cv.measureText(el.placeholder).width;
      if (tw > inner + 1) why.push(`placeholder "${el.placeholder}" ${tw.toFixed(0)}px wider than input ${inner.toFixed(0)}px`);
    }
    for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
      const cs = getComputedStyle(p);
      const ox = cs.overflowX, oy = cs.overflowY;
      if (ox === 'visible' && oy === 'visible') continue;
      const pr = p.getBoundingClientRect();
      const cl = pr.left + p.clientLeft, ct = pr.top + p.clientTop, cr = cl + p.clientWidth, cb = ct + p.clientHeight;
      const hClip = ox === 'hidden' || ox === 'clip' || !(p.classList.contains('cmpwrap') && W < 701);
      const vClip = oy === 'hidden' || oy === 'clip';
      if (hClip && (r.l < cl - 1 || r.r > cr + 1)) why.push(`horizontally outside ${desc(p).split(' "')[0]} (${r.l.toFixed(0)}–${r.r.toFixed(0)} vs ${cl.toFixed(0)}–${cr.toFixed(0)})`);
      if (vClip && (r.t < ct - 1 || r.b > cb + 1)) why.push(`vertically outside ${desc(p).split(' "')[0]}`);
      break; // nearest scroll container only
    }
    if (why.length) out.clipped.push(desc(el) + ': ' + why.join('; '));
  }
  // 7. button rows
  const byParent = new Map();
  for (const b of document.querySelectorAll('.btn')) {
    if (!vis(b) || b.closest('[data-marq]')) continue;
    const p = b.parentElement; if (!byParent.has(p)) byParent.set(p, []);
    byParent.get(p).push({ r: rect(b), d: desc(b) });
  }
  for (const items of byParent.values()) {
    if (items.length < 2) continue;
    const lines = [];
    for (const c of items) {
      const line = lines.find((ln) => c.r.t < ln.b - 1 && c.r.b > ln.t + 1 && Math.abs(c.r.t - ln.t) < c.r.h);
      if (line) { line.items.push(c); line.t = Math.min(line.t, c.r.t); line.b = Math.max(line.b, c.r.b); } else lines.push({ t: c.r.t, b: c.r.b, items: [c] });
    }
    for (const ln of lines) {
      if (ln.items.length < 2) continue;
      const hs = ln.items.map((c) => c.r.h);
      const spread = Math.max(...hs) - Math.min(...hs);
      out.buttonRows.push({ spread, ok: spread <= 2, d: ln.items.map((c) => `${c.d} ${c.r.h.toFixed(0)}px`).join(' | ').slice(0, 200) });
    }
  }
  // 8. hero trust block
  const trust = document.querySelector('.hero__trust p');
  if (trust && vis(trust)) {
    const r = rect(trust); const L = lh(trust);
    out.trust = { lines: Math.round(r.h / L), h: r.h, lh: L, limit: W >= 1024 ? 2 : 3 };
  }
  // 9. sticky filter rail
  const rail = document.querySelector('.rail');
  if (rail && vis(rail)) {
    const ctrls = [...rail.querySelectorAll('input,select,button,textarea')].filter(vis);
    const last = ctrls[ctrls.length - 1];
    if (last) {
      last.scrollIntoView({ block: 'nearest', inline: 'nearest' });
      const r = rect(last);
      const scroller = rail.closest('.sheet') || rail;
      const pr = scroller.getBoundingClientRect();
      const inScroller = r.t >= pr.top - 1 && r.b <= pr.bottom + 1 && r.l >= pr.left - 1 && r.r <= pr.right + 1;
      const inView = r.t >= -1 && r.b <= cfg.height + 1;
      out.rail = { ok: inScroller && inView, d: desc(last), r, count: ctrls.length };
      rail.scrollTop = 0;
    }
  }
  // 11. contrast
  // normalise any CSS colour (rgb, oklch, color(), named) through a 1x1 canvas
  const cvs = document.createElement('canvas'); cvs.width = cvs.height = 1; const cg = cvs.getContext('2d', { willReadFrequently: true });
  const parse = (s) => {
    if (!s || s === 'transparent') return { r: 0, g: 0, b: 0, a: 0 };
    cg.clearRect(0, 0, 1, 1); cg.fillStyle = '#000'; cg.fillStyle = s; cg.fillRect(0, 0, 1, 1);
    const d = cg.getImageData(0, 0, 1, 1).data;
    return { r: d[0], g: d[1], b: d[2], a: d[3] / 255 };
  };
  const lum = (c) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b); };
  const over = (fg, bg) => ({ r: fg.r * fg.a + bg.r * (1 - fg.a), g: fg.g * fg.a + bg.g * (1 - fg.a), b: fg.b * fg.a + bg.b * (1 - fg.a), a: 1 });
  const bgOf = (el) => {
    const layers = [];
    for (let p = el; p; p = p.parentElement) {
      const cs = getComputedStyle(p);
      if (cs.backgroundImage && cs.backgroundImage !== 'none') return null; // gradient / image: skip
      if (p !== el && Number(cs.opacity) < 1) return null;
      const c = parse(cs.backgroundColor);
      if (c && c.a > 0) { layers.push(c); if (c.a >= 1) break; }
      if (p === document.documentElement) break;
    }
    if (!layers.length || layers[layers.length - 1].a < 1) {
      const dlg = el.closest('dialog[open]');
      if (dlg) return null;
      layers.push({ r: 255, g: 255, b: 255, a: 1 });
    }
    let bg = layers.pop();
    while (layers.length) bg = over(layers.pop(), bg);
    return bg;
  };
  const CONTRAST = 'p,li,h1,h2,h3,h4,h5,h6,a,button,label,.tag,td,th,dt,dd,small,time,summary,legend,span';
  const seen = new Set();
  for (const el of document.querySelectorAll(CONTRAST)) {
    if (!vis(el) || el.closest('svg,[data-marq],[disabled]') || el.matches('[disabled],[aria-disabled="true"]')) continue;
    const own = [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
    if (!own) continue;
    const cs = getComputedStyle(el);
    const fg = parse(cs.color); if (!fg) continue;
    const bg = bgOf(el); if (!bg) continue;
    const f = fg.a < 1 ? over(fg, bg) : fg;
    const L1 = lum(f), L2 = lum(bg);
    const ratio = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
    const size = parseFloat(cs.fontSize), bold = parseInt(cs.fontWeight, 10) >= 700;
    const need = size >= 24 || (bold && size >= 18.66) ? 3 : 4.5;
    if (ratio < need) {
      const key = desc(el) + '|' + cs.color + '|' + ratio.toFixed(2);
      if (seen.has(key)) continue; seen.add(key);
      out.contrast.push(`${desc(el)} ${ratio.toFixed(2)}:1 (${cs.color} on rgb(${bg.r | 0},${bg.g | 0},${bg.b | 0}), need ${need})`);
    }
  }
  return out;
}

// ---- pixel comparison in the page (raw RGBA via canvas) ------------------
async function pixelDiff(page, currentPng, baselineJpg) {
  return page.evaluate(async ([cur, base]) => {
    const load = (src) => new Promise((res, rej) => { const i = new Image(); i.onload = () => res(i); i.onerror = rej; i.src = src; });
    const a = await load('data:image/png;base64,' + cur), b = await load('data:image/jpeg;base64,' + base);
    if (a.width !== b.width || a.height !== b.height) return { ratio: 1, note: `size ${a.width}x${a.height} vs baseline ${b.width}x${b.height}` };
    const px = (img) => { const c = document.createElement('canvas'); c.width = img.width; c.height = img.height; const g = c.getContext('2d'); g.drawImage(img, 0, 0); return g.getImageData(0, 0, img.width, img.height).data; };
    const A = px(a), B = px(b);
    let diff = 0; const n = A.length / 4;
    for (let i = 0; i < A.length; i += 4) {
      // YIQ-style perceptual distance as pixelmatch uses, with a JPEG-tolerant threshold
      const dy = 0.299 * (A[i] - B[i]) + 0.587 * (A[i + 1] - B[i + 1]) + 0.114 * (A[i + 2] - B[i + 2]);
      const di = 0.596 * (A[i] - B[i]) - 0.274 * (A[i + 1] - B[i + 1]) - 0.322 * (A[i + 2] - B[i + 2]);
      const dq = 0.211 * (A[i] - B[i]) - 0.523 * (A[i + 1] - B[i + 1]) + 0.312 * (A[i + 2] - B[i + 2]);
      if (0.5053 * dy * dy + 0.299 * di * di + 0.1957 * dq * dq > 35215 * 0.15) diff++;
    }
    return { ratio: diff / n, note: `${(100 * diff / n).toFixed(2)}% of ${n} px differ` };
  }, [currentPng.toString('base64'), baselineJpg.toString('base64')]);
}

// ---- driver ------------------------------------------------------------------
const server = spawn('python3', ['-m', 'http.server', String(PORT), '--bind', '127.0.0.1', '--directory', site], { stdio: 'ignore' });
const base = `http://127.0.0.1:${PORT}/`;
for (let i = 0; i < 50; i++) {
  try { const r = await fetch(base + 'ie/index.html'); if (r.ok) break; } catch { /* not up yet */ }
  await new Promise((r) => setTimeout(r, 100));
}

const browser = await chromium.launch({ executablePath: CHROMIUM, args: ['--no-sandbox', '--disable-gpu'] });
let pagesRun = 0;
try {
  const combos = QUICK ? [[[1440, 900], 'light']] : VIEWPORTS.flatMap((v) => THEMES.map((t) => [v, t]));
  for (const [[width, height], theme] of combos) {
    const ctx = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: 1, reducedMotion: 'reduce', colorScheme: theme });
    await ctx.addInitScript((t) => { try { localStorage.setItem('gj-theme', t); } catch { /* ignore */ } }, theme);
    const page = await ctx.newPage();
    for (const p of PAGES) {
      const tag = `${p.key} @${width}x${height} ${theme}`;
      const errors = [];
      const onConsole = (m) => { if (m.type() === 'error') errors.push('console: ' + m.text().slice(0, 120)); };
      const onErr = (e) => errors.push('pageerror: ' + String(e).slice(0, 120));
      const onFail = (r) => { if (/\.mp4$/.test(r.url()) && /ERR_ABORTED/.test((r.failure() || {}).errorText || '')) return; /* hero preload="auto" cut off by navigation */ errors.push('request failed: ' + r.url()); };
      const onResp = (r) => { if (r.status() >= 400) errors.push(`HTTP ${r.status()}: ${r.url()}`); };
      page.on('console', onConsole); page.on('pageerror', onErr); page.on('requestfailed', onFail); page.on('response', onResp);
      try {
        const url = base + p.url;
        await page.goto(url, { waitUntil: 'networkidle' });
        if (p.key.includes('jobs')) await page.waitForSelector('.row, .empty, .mapview, [data-map-list]', { timeout: 10000 }).catch(() => {});
        if (p.key.endsWith('compass-result')) await page.waitForSelector('.res', { timeout: 10000 }).catch(() => {});
        if (p.key.endsWith('dashboard')) await page.waitForSelector('[data-fig="quality"] details.tbl', { timeout: 10000 }).catch(() => {});
        if (p.sheet) {
          const btn = await page.$('[data-sheet-open]');
          const shown = btn && await btn.isVisible();
          if (!shown) { console.log(`INFO  ${tag}: filter sheet button not shown at this width, page skipped`); continue; }
          await btn.click();
          await page.waitForSelector('dialog.sheet[open]', { timeout: 5000 });
        }
        await page.evaluate(() => document.fonts.ready);
        await page.waitForTimeout(250);
        pagesRun++;
        const a = await page.evaluate(audit, { width, height });
        check(a.overflow.scrollWidth <= width && a.overflow.bodyScroll <= width, `R1 ${tag}: no horizontal overflow (scrollWidth ${a.overflow.scrollWidth} <= ${width})`);
        const badTags = a.tags.filter((t) => !t.ok || !t.dotOk || !t.widthOk);
        check(badTags.length === 0, `R2 ${tag}: ${a.tags.length} chips <= 2 lines (content box), dot on first line, wider than dot+4` + (badTags.length ? ` — ${badTags.slice(0, 3).map((t) => `${t.d} h=${t.h.toFixed(0)} lh=${t.lh.toFixed(0)}${t.dotOk ? '' : ' dot@' + t.dotCy.toFixed(0) + ' text@' + t.textTop.toFixed(0)}`).join('; ')}` : ''));
        const badMeta = a.meta.filter((m) => !m.ok);
        check(badMeta.length === 0, `R3 ${tag}: ${a.meta.length} chip lines share a top band (<=4px)` + (badMeta.length ? ` — ${badMeta.slice(0, 2).map((m) => `${m.spread.toFixed(0)}px: ${m.d}`).join('; ')}` : ''));
        if (a.tables.length) check(a.tables.every((t) => t.ok), `R4 ${tag}: ${a.tables.length} comparison table(s) (${a.tables.map((t) => t.mode).join(',')}) aligned, even rows, no pills, no inner scroll` + a.tables.filter((t) => !t.ok).map((t) => ' — ' + t.why.slice(0, 3).join('; ')).join(''));
        check(a.overlaps.length === 0, `R5 ${tag}: no overlapping text elements` + (a.overlaps.length ? ` — ${a.overlaps.slice(0, 3).join('; ')}` : ''));
        check(a.clipped.length === 0, `R6 ${tag}: no clipped controls` + (a.clipped.length ? ` — ${a.clipped.slice(0, 3).join('; ')}` : ''));
        const badRows = a.buttonRows.filter((r) => !r.ok);
        check(badRows.length === 0, `R7 ${tag}: ${a.buttonRows.length} button rows share height (+-2px)` + (badRows.length ? ` — ${badRows.slice(0, 2).map((r) => r.d).join('; ')}` : ''));
        if (a.trust) check(a.trust.lines <= a.trust.limit, `R8 ${tag}: hero trust block ${a.trust.lines} line(s) <= ${a.trust.limit}`);
        if (a.rail) check(a.rail.ok, `R9 ${tag}: last filter control reachable (${a.rail.d}, ${a.rail.count} controls)`);
        check(errors.length === 0, `R10 ${tag}: no console errors or failed requests` + (errors.length ? ` — ${[...new Set(errors)].slice(0, 3).join(' | ')}` : ''));
        check(a.contrast.length === 0, `R11 ${tag}: text contrast >= 4.5:1 on solid backgrounds` + (a.contrast.length ? ` — ${a.contrast.slice(0, 3).join('; ')}` : ''));
        // screenshot + baseline
        const name = `${p.key.replace(/\//g, '_')}_${width}_${theme}`;
        const png = await page.screenshot({ type: 'png', animations: 'disabled', caret: 'hide' });
        writeFileSync(join(SHOTS, name + '.png'), png);
        const set = `${width}-${theme}`;
        const bl = join(BASELINE, name + '.jpg');
        if (BASELINE_SETS.has(set) && BASELINE_KEYS.has(p.key.split('/')[1])) {
          if (UPDATE) {
            writeFileSync(bl, await page.screenshot({ type: 'jpeg', quality: 40, animations: 'disabled', caret: 'hide' }));
            console.log(`INFO  ${tag}: baseline written ${bl}`);
          } else if (existsSync(bl)) {
            const d = await pixelDiff(page, png, readFileSync(bl));
            check(d.ratio <= DIFF_LIMIT, `R12 ${tag}: screenshot within ${DIFF_LIMIT * 100}% of baseline (${d.note}); refresh with --update-baseline`);
          }
        }
      } catch (e) {
        check(false, `${tag}: audit threw ${String(e).slice(0, 200)}`);
      } finally {
        page.off('console', onConsole); page.off('pageerror', onErr); page.off('requestfailed', onFail); page.off('response', onResp);
      }
    }
    await ctx.close();
  }
} finally {
  await browser.close();
  server.kill();
}
const failed = results.filter(([ok]) => !ok);
console.log(`\nLayout regression: ${pagesRun} page loads, ${results.length} assertions, ${results.length - failed.length} passed, ${failed.length} failed, ${known.length} known defects; screenshots in ${SHOTS}`);
if (known.length) console.log('Known defects (not counted as failures):\n  ' + known.join('\n  '));
process.exit(failed.length ? 1 : 0);
