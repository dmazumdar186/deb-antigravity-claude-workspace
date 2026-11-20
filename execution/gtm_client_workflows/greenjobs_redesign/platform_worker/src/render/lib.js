// Pure ports of build_site.py's figure and fragment functions, so a Worker-rendered job page and
// /api/stats match the static build exactly (tests/greenjobs_redesign/platform/parity.test.mjs
// renders the same fixture both ways and fails on drift). Each function names its Python twin.
// No classification happens here: sectors, regions, workplace, contract, level and agency arrive
// as stored facets (job_facets, set at write time from taxonomy.json).

import TAXONOMY from '../taxonomy.json' with { type: 'json' };

export { TAXONOMY };
export const UNVERIFIED_SOURCE = 'greenjobs.ie listing (UK-located role)';
export const UNVERIFIED_NOTE = 'Salary as listed on greenjobs.ie; the advertiser may pay in sterling';
export const STERLING_SOURCE = 'greenjobs.co.uk listing';
export const STERLING_NOTE = 'Salary figure taken from the same advert on greenjobs.co.uk, where it is advertised in sterling.';
export const FX_GBP_EUR = 1.17;
export const CUR_NAME = { EUR: 'euros', GBP: 'sterling', USD: 'US dollars' };
export const CUR_SYM = { EUR: '€', GBP: '£', USD: '$' };
export const LOC_LABEL = TAXONOMY.loc_classes;
export const WORKPLACE_LABEL = TAXONOMY.workplace;
export const CONTRACT_LABEL = TAXONOMY.contract;
export const ANNUAL_MULT = { year: 1, month: 12, week: 52, day: 230, hour: 1950 };
const COMPARABLE = new Set(['EUR', 'GBP']);
export const SALARY_EDGES = [20000, 30000, 40000, 50000, 60000, 75000, 100000];
export const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
export const SAVE_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 3h12v18l-6-4-6 4z"/></svg>';

/** EDITIONS[ed] equivalent, from taxonomy.json. */
export function edition(site) {
  const s = TAXONOMY.sites[site];
  if (!s) throw new Error('unknown_site');
  return { ...s, other: site === 'ie' ? 'uk' : 'ie' };
}

export function sectorColor(name) {
  const s = TAXONOMY.sectors.find((x) => x.name === name);
  return s ? s.color : '';
}

// ---- escaping (html.escape(quote=True), urllib quote(safe=""), json_ld, json_embed)
export function esc(v) {
  return String(v ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#x27;');
}
export function quote(v) {
  return encodeURIComponent(String(v)).replace(/[!'()*]/g, (c) => '%' + c.charCodeAt(0).toString(16).toUpperCase());
}
export const qs = (v) => esc(quote(v));
const LS = new RegExp(String.fromCharCode(0x2028), 'g');
const PS = new RegExp(String.fromCharCode(0x2029), 'g');
export function jsonLd(payload) {
  return JSON.stringify(payload).replace(/</g, '\\u003c').replace(LS, '\\u2028').replace(PS, '\\u2029');
}
export const jsonEmbed = (payload) => JSON.stringify(payload).replace(/</g, '\\u003c');

// ---- numbers
/** rnd(): half away from zero (JS Math.round for the positive values used here), ndigits <= 0. */
export function rnd(x, ndigits = 0) {
  const f = 10 ** -ndigits;
  const v = Math.sign(x) * Math.round(Math.abs(x) / f) * f;
  return ndigits <= 0 ? Math.round(v) : v;
}
/** Python round(x): half to even. */
export function pyRound(x) {
  const f = Math.floor(x);
  const d = x - f;
  if (d > 0.5) return f + 1;
  if (d < 0.5) return f;
  return f % 2 === 0 ? f : f + 1;
}
/** Python format(x, 'g') for the magnitudes used here (< 1e6, at most one decimal). */
export function fmtG(x) {
  if (Number.isInteger(x)) return String(x);
  return String(Number(x.toPrecision(6)));
}
export function moneyK(n, sym) {
  if (n >= 1000) return n % 1000 === 0 ? `${sym}${Math.floor(n / 1000)}k` : `${sym}${fmtG(rnd(n / 100) / 10)}k`;
  return `${sym}${fmtG(n)}`;
}
export function fxConvert(amount, from, to) {
  if (from === to) return amount;
  if (from === 'GBP' && to === 'EUR') return amount * FX_GBP_EUR;
  if (from === 'EUR' && to === 'GBP') return amount / FX_GBP_EUR;
  return amount;
}

// ---- salary (salary_label, currency_note, annual_mid, median_salary, salary_bands, salary_stats)
/** Python str.lstrip(chars). */
function lstrip(text, chars) {
  let i = 0;
  while (chars && i < text.length && chars.includes(text[i])) i++;
  return text.slice(i);
}
export function salaryLabel(j, edCur = '') {
  const cur = j.cur || '';
  const sym = CUR_SYM[cur] || '';
  const money = (n, s = sym) => (n >= 1000 ? (n % 1000 === 0 ? `${s}${Math.trunc(n / 1000)}k` : `${s}${fmtG(rnd(n / 100) / 10)}k`) : `${s}${fmtG(n)}`);
  const lo = j.sal_min ?? null;
  const hi = j.sal_max ?? null;
  if (lo === null && hi === null) return '';
  const per = { year: '', month: '/mo', hour: '/hr', day: '/day', week: '/wk' }[j.period || 'year'] ?? '';
  const prefix = hi === null && lo !== null && /up to/i.test(j.sal_text || '') ? 'up to ' : '';
  const fmt = (a, b, s) => {
    if (a !== null && b !== null && a !== b) return `${money(a, s)}–${lstrip(money(b, s), s)}${per}`;
    return `${prefix}${money(a !== null ? a : b, s)}${per}`;
  };
  let label = fmt(lo, hi, sym);
  if (edCur && cur && cur !== edCur && fxConvert(1, cur, edCur) !== 1) {
    const eqLo = lo !== null ? rnd(fxConvert(lo, cur, edCur), -2) : null;
    const eqHi = hi !== null ? rnd(fxConvert(hi, cur, edCur), -2) : null;
    label += ` (advertised in ${CUR_NAME[cur] || cur}, about ${fmt(eqLo, eqHi, CUR_SYM[edCur] || '')})`;
  }
  return label;
}
export function currencyNote(j, edCur) {
  const cur = j.cur || '';
  if (!cur || cur === edCur || (j.sal_min == null && j.sal_max == null)) return '';
  return `Advertised in ${CUR_NAME[cur] || cur}`;
}
export const isUnverified = (j) => Boolean(j.unverified_cur) || j.currency_source === UNVERIFIED_SOURCE;
export function annualMid(j, edCur = '') {
  const m = ANNUAL_MULT[j.period || 'year'];
  if (!m || (j.sal_min == null && j.sal_max == null)) return null;
  if (isUnverified(j)) return null;
  if (!COMPARABLE.has(j.cur)) return null;
  let lo = (j.sal_min != null ? j.sal_min : j.sal_max) * m;
  let hi = j.sal_max != null ? j.sal_max * m : lo;
  if (edCur && j.cur && j.cur !== edCur) {
    lo = fxConvert(lo, j.cur, edCur);
    hi = fxConvert(hi, j.cur, edCur);
  }
  if (lo < 8000 || hi > 400000) return null;
  return [lo, hi, (lo + hi) / 2];
}
function median(vals) {
  if (!vals.length) return null;
  const v = [...vals].sort((a, b) => a - b);
  const k = Math.floor(v.length / 2);
  return v.length % 2 ? v[k] : (v[k - 1] + v[k]) / 2;
}
export function medianSalary(jobs, sym, edCur = '') {
  const mids = jobs.map((j) => annualMid(j, edCur)).filter(Boolean).map((a) => a[2]);
  const med = median(mids);
  return med === null ? 'n/a' : moneyK(med, sym);
}
export function salaryBands(jobs, sym, edCur = '') {
  const bands = SALARY_EDGES.map((e, i) => ({
    l: i + 1 < SALARY_EDGES.length ? `${moneyK(e, '')}–${moneyK(SALARY_EDGES[i + 1], '')}` : `${moneyK(e, '')}+`, lo: e, n: 0,
  }));
  for (const j of jobs) {
    const a = annualMid(j, edCur);
    if (!a) continue;
    for (let i = bands.length - 1; i >= 0; i--) {
      if (a[2] >= bands[i].lo) {
        bands[i].n += 1;
        break;
      }
    }
  }
  return bands.map((b) => ({ l: b.l, n: b.n }));
}
export function salaryStats(jobs, ed) {
  const disclosed = jobs.filter((j) => annualMid(j, ed.currency));
  return {
    n_jobs: jobs.length, n_disc: disclosed.length, disc_pct: pyRound((100 * disclosed.length) / Math.max(1, jobs.length)),
    median: medianSalary(jobs, ed.sym, ed.currency), bands: salaryBands(jobs, ed.sym, ed.currency),
  };
}
export function sectorStat(inSector, sym) {
  const edCur = { '€': 'EUR', '£': 'GBP' }[sym] || '';
  const disclosed = inSector.filter((j) => annualMid(j, edCur)).length;
  const med = disclosed >= 3 ? medianSalary(inSector, sym, edCur) : 'n/a';
  if (med !== 'n/a') return `median disclosed ${med}`;
  if (disclosed === 0) return 'no disclosed salaries yet';
  return `${disclosed} disclosed ${disclosed === 1 ? 'salary' : 'salaries'}`;
}

// ---- dates (date_long, ago, days_until, closing_within, new_this_week, sparkline_weeks)
const dayNum = (iso) => {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(String(iso || ''))) return null;
  const t = Date.parse(`${iso}T00:00:00Z`);
  return Number.isNaN(t) ? null : Math.round(t / 864e5);
};
export function dateLong(iso) {
  if (!iso) return '';
  const n = dayNum(String(iso).slice(0, 10));
  if (n === null) return String(iso);
  const d = new Date(n * 864e5);
  return `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}`;
}
export function daysUntil(iso, today) {
  const a = dayNum(iso);
  const b = dayNum(today);
  return a === null || b === null ? null : a - b;
}
export function ago(iso, today) {
  if (!iso) return '';
  const d0 = daysUntil(iso, today);
  if (d0 === null) return '';
  const d = -d0;
  if (d <= 0) return 'Today';
  if (d === 1) return 'Yesterday';
  if (d < 7) return `${d} days ago`;
  if (d < 30) return `${rnd(d / 7)} wk ago`;
  return `${rnd(d / 30)} mo ago`;
}
export const isClosed = (j, today) => { const d = daysUntil(j.closing || '', today); return d !== null && d < 0; };
export const closingWithin = (j, today, n = 7) => { const d = daysUntil(j.closing || '', today); return d !== null && d >= 0 && d <= n; };
export const newThisWeek = (j, today) => { const d = daysUntil(j.posted || '', today); return d !== null && d >= -6 && d <= 0; };
export function sparklineWeeks(jobs, today, weeks = 8) {
  const counts = new Array(weeks).fill(0);
  for (const j of jobs) {
    if (!j.posted) continue;
    const d = daysUntil(j.posted, today);
    if (d === null) continue;
    const idx = weeks - 1 - Math.floor(-d / 7);
    if (idx >= 0 && idx < weeks) counts[idx] += 1;
  }
  return counts;
}

// ---- dashboard_kpis (the client KPI dashboard's live-now figures)
export function dashboardKpis(jobs, sectors, regions, site, asof) {
  const ed = edition(site);
  const n = jobs.length;
  const stats = salaryStats(jobs, ed);
  const med = median(jobs.map((j) => annualMid(j, ed.currency)).filter(Boolean).map((a) => a[2]));
  const emp = new Map();
  for (const j of jobs) emp.set(j.employer, (emp.get(j.employer) || 0) + 1);
  let top = ['', 0];
  for (const [k, v] of emp) if (v > top[1] || (v === top[1] && k > top[0])) top = [k, v];
  const agency = jobs.filter((j) => j.agency).length;
  const windows = [];
  for (const j of jobs) {
    const p = dayNum(j.posted);
    const c = dayNum(j.closing);
    if (p !== null && c !== null && c >= p) windows.push(c - p);
  }
  const daysClose = median(windows);
  const remote = jobs.filter((j) => ['remote', 'hybrid'].includes(j.workplace)).length;
  const quality = [0, 0, 0, 0, 0];
  for (const j of jobs) {
    const score = Number(j.sal_min != null || j.sal_max != null) + Number(Boolean(j.closing)) + Number(Boolean(j.logo || j.has_logo)) + Number(j.text.length >= 400);
    quality[score] += 1;
  }
  return {
    asof, live: n, new7: jobs.filter((j) => newThisWeek(j, asof)).length, weeks: sparklineWeeks(jobs, asof, 4),
    closing7: jobs.filter((j) => closingWithin(j, asof, 7)).length,
    sal_n: stats.n_disc, sal_pct: pyRound((100 * stats.n_disc) / Math.max(1, n)), sal_median: med !== null ? pyRound(med) : null,
    sectors: sectors.filter((s) => s.n).map((s) => ({ l: s.name, v: s.n })),
    regions: regions.filter((r) => r.on_map).map((r) => ({ l: r.name, v: r.n })).slice(0, 12),
    top_employer: top[0], top_share: pyRound((100 * top[1]) / Math.max(1, n)), employers: emp.size,
    agency_pct: pyRound((100 * agency) / Math.max(1, n)), days_to_close: daysClose !== null ? pyRound(daysClose) : null,
    remote_pct: pyRound((100 * remote) / Math.max(1, n)), quality,
  };
}

/** normalise()'s sector and region tallies over the live set (counts only, no classification). */
export function tallies(jobs, site) {
  const ed = edition(site);
  const sc = new Map();
  for (const j of jobs) for (const s of j.sectors) sc.set(s, (sc.get(s) || 0) + 1);
  const sectors = TAXONOMY.sectors.map((s) => ({ name: s.name, n: sc.get(s.name) || 0, color: s.color, dark: s.dark }));
  sectors.sort((a, b) => b.n - a.n || (a.name < b.name ? -1 : a.name > b.name ? 1 : 0));
  const rc = new Map();
  for (const j of jobs) for (const r of j.regions) rc.set(r, (rc.get(r) || 0) + 1);
  for (const r of ed.regions) if (!rc.has(r)) rc.set(r, 0);
  const onMap = new Set(ed.regions);
  const regions = [...rc.entries()].sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0)).map(([name, n]) => ({ name, n, on_map: onMap.has(name) }));
  const tc = new Map();
  for (const j of jobs) if (j.type) tc.set(j.type, (tc.get(j.type) || 0) + 1);
  const types = [...tc.entries()].map(([name, n], i) => ({ name, n, i })).sort((a, b) => b.n - a.n || a.i - b.i).map(({ name, n }) => ({ name, n }));
  return { sectors, regions, types };
}

// ---- card / page fragments
export function logoImg(j, root, cls = 'role__logo') {
  if (j.logo) return `<img class="${cls}" src="${root}assets/logos/${esc(j.logo)}" alt="" width="${j.lw || 200}" height="${j.lh || 80}" loading="lazy" decoding="async">`;
  return `<div class="${cls} role__logo--t" aria-hidden="true">${esc((j.employer || '?').slice(0, 1))}</div>`;
}
export function locBadge(j) {
  const lc = j.loc_class || '';
  return lc in LOC_LABEL ? `<span class="tag tag--loc" data-loc="${esc(lc)}">${esc(LOC_LABEL[lc] || '')}</span>` : '';
}
export function sepPair(text, who = '') {
  const words = esc(String(text || '')).split(' ');
  const head = words.shift();
  const emp = esc(String(who || '')).split(' ');
  const last = emp.pop();
  return `<span class="row__emp">${emp.length ? emp.join(' ') + ' ' : ''}<span class="row__pair">${last ? last + ' ' : ''}`
    + `<span class="row__sep" aria-hidden="true">· </span>${head}</span>${words.length ? ' ' + words.join(' ') : ''}</span>`;
}
export function roleCard(j, root, jobsDir, today, edCur = '') {
  const sal = salaryLabel(j, edCur);
  const chips = (sal ? `<span class="tag tag--sal">${esc(sal)}</span>` : '') + (j.type ? `<span class="tag tag--type">${esc(j.type)}</span>` : '') + locBadge(j);
  return '<article class="role reveal">'
    + `<div class="role__top">${logoImg(j, root)}<button class="save" type="button" data-save="${esc(j.id)}" data-title="${esc(j.title)}" aria-pressed="false" aria-label="Save: ${esc(j.title)}">${SAVE_ICON}</button></div>`
    + `<h3><a href="${jobsDir}${esc(j.href)}">${esc(j.title)}</a></h3>`
    + `<p class="role__emp">${sepPair(j.location, j.employer)}</p>`
    + `<div class="role__meta">${chips}<time datetime="${esc(j.posted)}">${esc(ago(j.posted, today))}</time></div>`
    + (j.currency_source === UNVERIFIED_SOURCE ? `<p class="role__note">${esc(UNVERIFIED_NOTE)}.</p>` : '') + '</article>';
}
export function contractRow(j) {
  const labels = (j.contract || []).map((c) => CONTRACT_LABEL[c]).filter(Boolean);
  const typ = String(j.type || '').trim();
  if (typ && !labels.map((l) => l.toLowerCase()).includes(typ.toLowerCase().replace(/ /g, '-')) && !['home based', 'home-based'].includes(typ.toLowerCase())) labels.push(typ);
  return labels.join(', ');
}
export const noBreakDash = (t) => String(t).replace(/ ([–—])/g, ' $1');

/** similar_jobs(): same primary sector first, then a shared region, then salary closeness. */
export function similarJobs(j, jobs, edCur = '', limit = 4) {
  const mine = annualMid(j, edCur);
  const myRegions = new Set(j.regions || []);
  const mySectors = new Set(j.sectors || []);
  const key = (o) => `${String(o.title || '').trim().toLowerCase()}\u0000${String(o.employer || '').trim().toLowerCase()}`;
  const seen = new Set([key(j)]);
  const inv = (s) => [...s].map((c) => String.fromCharCode(255 - c.charCodeAt(0))).join('');
  const pre = [...jobs].sort((a, b) => cmpTuple([!a.posted, inv(a.posted || ''), a.title || ''], [!b.posted, inv(b.posted || ''), b.title || '']));
  const scored = [];
  for (const o of pre) {
    if (o.id === j.id) continue;
    const k = key(o);
    if (seen.has(k) || !(o.sectors || []).some((s) => mySectors.has(s))) continue;
    seen.add(k);
    let score = o.sectors[0] === j.sectors[0] ? 4 : 1.5;
    if ((o.regions || []).some((r) => myRegions.has(r))) score += 2;
    if (o.loc_class === j.loc_class) score += 0.5;
    const theirs = annualMid(o, edCur);
    if (mine && theirs) score += Math.max(0, 1 - Math.abs(mine[2] - theirs[2]) / Math.max(mine[2], theirs[2], 1));
    const posted = o.posted || '';
    scored.push([[-score, posted ? 0 : 1, inv(posted), o.title], o]);
  }
  scored.sort((a, b) => cmpTuple(a[0], b[0]));
  return scored.slice(0, limit).map((x) => x[1]);
}
function cmpTuple(a, b) {
  for (let i = 0; i < a.length; i++) {
    const x = typeof a[i] === 'boolean' ? Number(a[i]) : a[i];
    const y = typeof b[i] === 'boolean' ? Number(b[i]) : b[i];
    if (x < y) return -1;
    if (x > y) return 1;
  }
  return 0;
}

const f1 = (x) => x.toFixed(1);
/** salary_strip(): this role's range against the board's disclosed distribution. */
export function salaryStrip(j, jobs, sym, unit, onMap, edCur = '') {
  const sector = j.sectors[0];
  const overall = jobs.map((o) => [o, annualMid(o, edCur)]).filter((x) => x[1]);
  const inSector = overall.filter(([o]) => o.sectors.includes(sector));
  const mine = annualMid(j, edCur);
  const jr = new Set(j.regions);
  const js = new Set(j.sectors);
  const sameCounty = jobs.filter((o) => o.id !== j.id && o.regions.some((r) => jr.has(r)) && o.sectors.some((s) => js.has(s)));
  const county = j.regions.length ? j.regions[0] : '';
  const where = onMap === null || onMap.has(county) ? `within ${esc(county)}` : unit === 'county' ? 'outside Ireland' : 'outside the UK';
  const sim = `<p class="sits__sim"><b class="num">${sameCounty.length}</b> similar ${sameCounty.length === 1 ? 'role' : 'roles'} ${where}`
    + (sameCounty.length ? ` — <a href="../index.html?loc=${qs(county)}&amp;sector=${qs(sector)}">see them</a>` : '') + '</p>';
  if (!mine) {
    let line;
    if (inSector.length) {
      const lo = Math.min(...inSector.map(([, a]) => a[0]));
      const hi = Math.max(...inSector.map(([, a]) => a[1]));
      line = `This employer hasn't published a salary. ${esc(sector)} roles that do: ${moneyK(lo, sym)}–${moneyK(hi, sym)} (${inSector.length}).`;
    } else {
      line = `This employer hasn't published a salary, and no other live ${esc(sector)} role does either.`;
    }
    return `<section class="sits sits--none" aria-labelledby="h-sits"><div class="wrap"><h2 id="h-sits">Where this role sits</h2><p class="sits__line">${line}</p>${sim}</div></section>`;
  }
  const vals = [...overall.map(([, a]) => a[2]), mine[0], mine[1]];
  const loAx = Math.floor(Math.min(...vals) / 10000) * 10000;
  const hiAx = (Math.floor(Math.max(...vals) / 10000) + 1) * 10000;
  const W = 720;
  const LH = 44;
  const PL = 8;
  const PR = 8;
  const X = (v) => PL + ((W - PL - PR) * (v - loAx)) / Math.max(1, hiAx - loAx);
  const lanes = [['Overall', overall], [sector, inSector]];
  const rowsSvg = [];
  const tableRows = [];
  let y = 26;
  for (const [label, group] of lanes) {
    const med = median(group.map(([, a]) => a[2]));
    const marks = [...group].sort((a, b) => a[1][2] - b[1][2]).map(([o, a]) => `<g class="sits__mark" tabindex="0" role="listitem" aria-label="${esc(o.title)}, ${esc(o.employer)}: ${esc(salaryLabel(o, edCur))}"><circle cx="${f1(X(a[2]))}" cy="${y + 14}" r="5"/></g>`).join('');
    const medl = med !== null ? `<line class="sits__med" x1="${f1(X(med))}" x2="${f1(X(med))}" y1="${y + 2}" y2="${y + 26}"/>` : '';
    rowsSvg.push(`<text class="sits__lbl" x="${PL}" y="${y - 6}">${esc(label)} · ${group.length} disclosed` + (med !== null ? ` · median ${moneyK(med, sym)}` : '') + `</text><g role="list">${marks}</g>${medl}`);
    tableRows.push(`<tr><th scope="row">${esc(label)}</th><td class="num">${group.length}</td><td class="num">${med !== null ? moneyK(med, sym) : '—'}</td></tr>`);
    y += LH + 16;
  }
  const mineY = y;
  const bar = `<rect class="sits__me" x="${f1(X(mine[0]))}" y="${mineY + 6}" width="${f1(Math.max(6, X(mine[1]) - X(mine[0])))}" height="16" rx="8"/>`
    + `<text class="sits__lbl sits__lbl--me" x="${PL}" y="${mineY - 6}">This role · ${esc(salaryLabel(j, edCur))}</text>`;
  const tickVals = [...new Set([loAx, hiAx, (loAx + hiAx) / 2])].sort((a, b) => a - b);
  const ticks = tickVals.map((v) => `<text class="sits__tick" x="${f1(X(v))}" y="${mineY + 44}" text-anchor="${v === loAx ? 'start' : v === hiAx ? 'end' : 'middle'}">${moneyK(v, sym)}</text>`).join('');
  const H = mineY + 52;
  const svg = `<svg class="sits__svg" viewBox="0 0 ${W} ${H}" role="img" aria-label="Salary of this role against ${overall.length} disclosed salaries on the board">`
    + `${rowsSvg.join('')}${bar}<line class="sits__axis" x1="${PL}" x2="${W - PR}" y1="${mineY + 30}" y2="${mineY + 30}"/>${ticks}</svg>`;
  const table = `<details class="sits__table"><summary>As a table</summary><table><thead><tr><th>Group</th><th class="num">Disclosed</th><th class="num">Median</th></tr></thead><tbody>${tableRows.join('')}`
    + `<tr><th scope="row">This role</th><td class="num">1</td><td class="num">${moneyK(mine[2], sym)} (midpoint)</td></tr></tbody></table></details>`;
  return `<section class="sits" aria-labelledby="h-sits"><div class="wrap"><div class="sec-head"><div><h2 id="h-sits">Where this role sits</h2>`
    + `<p>Its published range against every disclosed salary on the board, overall and in ${esc(sector)}. Midpoints per role, annualised; tab through the dots.</p></div></div>`
    + `${svg}${table}${sim}</div></section>`;
}

// Google's JobPosting employmentType vocabulary. build_site.py writes type.upper() ("PERMANENT"), which Google
// ignores; the Worker maps the stored contract tags onto the accepted values instead (same key, valid value).
const GOOGLE_EMPLOYMENT = { 'full-time': 'FULL_TIME', 'part-time': 'PART_TIME', contract: 'CONTRACTOR', 'fixed-term': 'TEMPORARY', volunteer: 'VOLUNTEER', permanent: 'FULL_TIME' };
export function employmentType(j) {
  const out = [...new Set((j.contract || []).map((c) => GOOGLE_EMPLOYMENT[c]).filter(Boolean))];
  return out.length ? (out.length === 1 ? out[0] : out) : 'OTHER';
}

/** job_jsonld_payload(): schema.org JobPosting with the same keys as the static page. */
export function jobJsonLdPayload(j, site) {
  const lc = j.loc_class || '';
  const country = { ie: 'IE', uk: 'GB', ni: 'GB' }[lc] || (site === 'ie' ? 'IE' : 'GB');
  const p = {
    '@context': 'https://schema.org', '@type': 'JobPosting', title: j.title, description: j.description_html || `<p>${esc(j.summary)}</p>`,
    hiringOrganization: { '@type': 'Organization', name: j.employer },
    jobLocation: { '@type': 'Place', address: { '@type': 'PostalAddress', addressLocality: j.location, addressCountry: country } },
    url: j.url, directApply: j.apply_mode === 'email',
  };
  if (j.posted) p.datePosted = j.posted;
  if (j.closing) p.validThrough = `${j.closing}T23:59:59`;
  if (j.type) p.employmentType = employmentType(j);
  if (lc === 'remote' || j.workplace === 'remote') p.jobLocationType = 'TELECOMMUTE';
  if (lc === 'cross') p.applicantLocationRequirements = [{ '@type': 'Country', name: 'Ireland' }, { '@type': 'Country', name: 'United Kingdom' }];
  else if (lc === 'remote' || (j.workplace === 'remote' && ['ie', 'uk', 'ni'].includes(lc))) p.applicantLocationRequirements = { '@type': 'Country', name: { IE: 'Ireland', GB: 'United Kingdom' }[country] };
  if (['EUR', 'GBP', 'USD'].includes(j.cur) && (typeof j.sal_min === 'number' || typeof j.sal_max === 'number')) {
    const value = { '@type': 'QuantitativeValue', unitText: (j.period || 'year').toUpperCase() };
    if (j.sal_min != null) value.minValue = j.sal_min;
    if (j.sal_max != null) value.maxValue = j.sal_max;
    p.baseSalary = { '@type': 'MonetaryAmount', currency: j.cur, value };
  }
  return p;
}

// ---- write-time rules the console uses (twins of build_site.level_of / is_agency; Python stays the import path)
const LEVELS = [
  ['Director/Associate', /\b(director|associate director|head of|chief|partner|vice president|vp)\b/i],
  ['Senior/Principal', /\b(senior|principal|lead(?!-free)|chartered)\b/i],
  ['Graduate/Early career', /\b(graduate|junior|trainee|intern|internship|apprentice|entry[- ]level|assistant(?!(?:\s+\w+){0,2}\s+(?:manager|director|head|lead|engineer|ecologist|consultant)\b)|placement|student)\b/i],
];
export function levelOf(title) {
  for (const [name, re] of LEVELS) if (re.test(title)) return name;
  return 'Mid-level';
}
export function isAgency(employer) {
  const name = String(employer || '').toLowerCase().trim();
  if (TAXONOMY.agency.names.includes(name)) return true;
  return TAXONOMY.agency.words.some((w) => new RegExp('(?<![a-z0-9])' + w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '(?![a-z0-9])').test(name));
}
