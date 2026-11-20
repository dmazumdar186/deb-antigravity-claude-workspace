// Parity gate: the Worker renders job pages and /api/stats from D1 exactly as build_site.py renders
// them from the scraped JSON. parity_bridge.py normalises the redesign fixture with the Python build,
// renders it statically and emits the equivalent D1 rows; this file seeds a real SQLite-backed FakeD1
// (schema + every migration) with those rows, renders through the Worker and fails on drift in:
//   job pages : heading sequence, element/class sequence, facts-panel labels, JSON-LD key paths
//   jobs list : every class the static list page uses is present (the Worker adds server rows on top)
//   /api/stats: salary_stats, sector tiles, regions and dashboard_kpis equal the Python figures exactly
//   helpers   : salary_label, level_of, is_agency, sanitise_html on the same inputs
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { resolve } from 'node:path';
import test from 'node:test';
import { makeWorld, REPO, workerModule } from './helpers.mjs';

const bridge = spawnSync('python3', [resolve(REPO, 'tests/greenjobs_redesign/platform/parity_bridge.py')], { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 });
if (bridge.status !== 0) throw new Error(`parity_bridge.py failed: ${bridge.stderr.slice(-2000)}`);
const B = JSON.parse(bridge.stdout);
const HOST = { ie: 'greenjobs.ie', uk: 'greenjobs.co.uk' };

/** Insert the bridge rows (an import's jobs + employers + job_facets) into a world's D1. */
export function seedRows(world, site, rows) {
  const db = world.db.sqlite;
  const ts = '2026-09-01T09:00:00Z';
  for (const r of rows) {
    db.prepare(`INSERT OR IGNORE INTO employers (id, site, source, source_id, name, name_norm, created_at, updated_at) VALUES (?1, ?2, 'strategies', ?3, ?4, ?5, ?6, ?6)`)
      .run(r.employer_id, site, r.employer_id.split(':').pop(), r.employer, r.employer.toLowerCase(), ts);
    db.prepare(`INSERT INTO jobs (id, site, source, source_id, employer_id, title, location, region, job_type, sal_min, sal_max, currency, period, sal_text, sectors_json, summary,
      description, apply_mode, apply_email, apply_url, status, posted_at, closing_at, created_by, created_at, updated_at)
      VALUES (?1, ?2, 'strategies', ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12, ?13, ?14, ?15, ?16, ?17, NULL, ?18, 'live', ?19, ?20, 'import', ?21, ?21)`)
      .run(r.id, site, r.id.split(':').pop(), r.employer_id, r.title, r.location, r.region, r.job_type, r.sal_min, r.sal_max, r.currency, r.period, r.sal_text,
        JSON.stringify(r.facets.sectors), r.summary, r.description, r.apply_mode, r.apply_url, r.posted_at, r.closing_at, ts);
    const f = r.facets;
    db.prepare(`INSERT INTO job_facets (job_id, sectors_json, regions_json, job_type, workplace, contract_json, loc_class, level, is_agency, salary_display, unverified_cur, taxonomy_version, set_by, updated_at, search_text)
      VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, 1, 'import', ?12, ?13)`)
      .run(r.id, JSON.stringify(f.sectors), JSON.stringify(f.regions), f.job_type, f.workplace, JSON.stringify(f.contract), f.loc_class, f.level || null, f.is_agency, f.salary_display, f.unverified_cur, ts, f.search_text);
  }
}

// ---- a small HTML structure reader (no dependencies) -------------------------------------------
export function structure(html) {
  const body = html.replace(/<script\b[^>]*type="application\/ld\+json"[^>]*>[\s\S]*?<\/script>/g, '').replace(/<!--[\s\S]*?-->/g, '');
  const classes = [];
  const tags = [];
  for (const m of body.matchAll(/<([a-zA-Z][a-zA-Z0-9]*)\b([^>]*)>/g)) {
    const tag = m[1].toLowerCase();
    const cls = /\sclass="([^"]*)"/.exec(m[2]);
    if (cls) classes.push(`${tag}.${cls[1].trim().split(/\s+/).sort().join('.')}`);
    if (['main', 'section', 'article', 'aside', 'nav', 'dl', 'form', 'details', 'table', 'h1', 'h2', 'h3', 'svg', 'dialog'].includes(tag)) tags.push(tag);
  }
  const text = (s) => s.replace(/<[^>]+>/g, '').replace(/&nbsp;| /g, ' ').replace(/\s+/g, ' ').trim();
  const headings = [...body.matchAll(/<(h[1-3])\b[^>]*>([\s\S]*?)<\/\1>/g)].map((m) => `${m[1]}:${text(m[2])}`);
  const dts = [...body.matchAll(/<dt>([\s\S]*?)<\/dt>/g)].map((m) => text(m[1]));
  const jsonld = [...html.matchAll(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/g)].map((m) => keyPaths(JSON.parse(m[1])).sort());
  return { classes, tags, headings, dts, jsonld };
}
function keyPaths(v, pre = '') {
  if (Array.isArray(v)) return [...new Set(v.flatMap((x) => keyPaths(x, `${pre}[]`)))];
  if (v && typeof v === 'object') return Object.entries(v).flatMap(([k, x]) => [`${pre}${k}`, ...keyPaths(x, `${pre}${k}.`)]);
  return [];
}
const mainOf = (html) => html.slice(html.indexOf('<main'), html.indexOf('</main>'));

async function worldFor(site) {
  const w = await makeWorld({ ROBOTS_INDEX: '0' });
  w.clock.now = new Date(`${B.today}T12:00:00Z`);
  seedRows(w, site, B.sites[site].rows);
  return w;
}

for (const site of ['ie', 'uk']) {
  test(`parity ${site}: job pages rendered by the Worker match build_site.py (headings, classes, facts, JSON-LD keys)`, async () => {
    const w = await worldFor(site);
    const ids = Object.keys(B.sites[site].pages);
    assert.ok(ids.length >= 3, 'bridge rendered three fixture job pages');
    for (const id of ids) {
      const res = await w.fetch(new Request(`https://${HOST[site]}/${site}/jobs/${id}/`));
      assert.equal(res.status, 200, `job ${id}`);
      const mine = await res.text();
      const want = structure(mainOf(B.sites[site].pages[id]));
      const got = structure(mainOf(mine));
      assert.deepEqual(got.headings, want.headings, `${site} ${id}: headings`);
      assert.deepEqual(got.tags, want.tags, `${site} ${id}: structural tags`);
      assert.deepEqual(got.classes, want.classes, `${site} ${id}: element/class sequence`);
      assert.deepEqual(got.dts, want.dts, `${site} ${id}: facts panel`);
      assert.deepEqual(got.jsonld, want.jsonld, `${site} ${id}: JSON-LD key paths`);
      // The shell around <main> is the same template too.
      assert.deepEqual(structure(mine.slice(0, mine.indexOf('<main'))).classes, structure(B.sites[site].pages[id].slice(0, B.sites[site].pages[id].indexOf('<main'))).classes, `${site} ${id}: header`);
    }
  });

  test(`parity ${site}: the Worker list page carries every class of the static list page`, async () => {
    const w = await worldFor(site);
    const res = await w.fetch(new Request(`https://${HOST[site]}/${site}/jobs/`));
    assert.equal(res.status, 200);
    const got = new Set(structure(mainOf(await res.text())).classes);
    const missing = structure(mainOf(B.sites[site].list_html)).classes.filter((c) => !got.has(c));
    assert.deepEqual([...new Set(missing)], []);
  });

  test(`parity ${site}: /api/stats equals build_site.py's figures exactly`, async () => {
    const w = await worldFor(site);
    const res = await w.fetch(new Request(`https://${HOST[site]}/api/stats?site=${site}`));
    assert.equal(res.status, 200);
    const s = await res.json();
    const want = B.sites[site].stats;
    assert.deepEqual(s.salary, want.salary);
    assert.deepEqual(s.sectors, want.sectors);
    assert.deepEqual(s.regions, want.regions);
    assert.deepEqual(s.kpis, want.kpis);
    assert.deepEqual(s.measures, { applications_30d: null, alert_signups_30d: null, advertiser_enquiries_30d: null });
  });
}

test('parity: dashboard.js rewrites the static KPI tiles with exactly the values render_dashboard printed', async () => {
  const { createRequire } = await import('node:module');
  const D = createRequire(import.meta.url)(resolve(REPO, 'deliverables/greenjobs_redesign_2026-09-22/src/js/dashboard.js'));
  for (const site of ['ie', 'uk']) {
    const html = B.sites[site].dashboard_html;
    const live = html.slice(html.indexOf('<div class="kpis">'), html.indexOf('data-wired'));
    const printed = [...live.matchAll(/<b class="kpi__v num">([^<]*)<\/b>/g)].map((m) => m[1]);
    assert.deepEqual(D.tileTexts(B.sites[site].stats.kpis), printed, site);
    for (const key of ['applications_30d', 'alert_signups_30d', 'advertiser_enquiries_30d']) assert.match(html, new RegExp(`data-measure="${key}"`));
    assert.match(html, /Measures to come/);
  }
});

test('parity: salary_label, level_of and is_agency match build_site.py', async () => {
  const lib = await workerModule('render/lib.js');
  for (const site of ['ie', 'uk']) {
    const cur = site === 'ie' ? 'EUR' : 'GBP';
    for (const { in: x, out } of B.sites[site].labels) assert.equal(lib.salaryLabel(x, cur), out, JSON.stringify(x));
    for (const [t, lv] of Object.entries(B.sites[site].levels)) assert.equal(lib.levelOf(t), lv, t);
    for (const [n, a] of Object.entries(B.sites[site].agency)) assert.equal(lib.isAgency(n), a, n);
  }
});

test('parity: the sanitiser port matches sanitise_html on employer HTML (benign samples exactly)', async () => {
  const { sanitiseHtml } = await workerModule('render/sanitise.js');
  for (const { in: s, out } of B.sanitise) {
    const got = sanitiseHtml(s, 'https://www.greenjobs.ie/jobs/x/');
    if (/script|onerror|javascript:|data:/i.test(s)) {
      assert.ok(!/<script|onerror|javascript:|data:text/i.test(got), `unsafe output for ${s}: ${got}`);
    } else {
      assert.equal(got, out, s);
    }
  }
});

// ---- live board set (2026-11-20): the static insights charts and board search read /api/jobs?view=board through
// api.js instead of the build-time #gj-data. Fixture set: the live payload must equal build_site.py's dataset and
// every figure explore.js draws (count, disclosure, median, histogram, sector medians, region bars) must match.
const { createRequire: req0 } = await import('node:module');
const JS = (n) => req0(import.meta.url)(resolve(REPO, `deliverables/greenjobs_redesign_2026-09-22/src/js/${n}`));
const datasetOf = (html) => JSON.parse(/<script type="application\/json" id="gj-data">([\s\S]*?)<\/script>/.exec(html)[1]);

function insightFigures(GJ, data) {
  const cur = data.currency;
  const withSal = data.jobs.map((j) => GJ.annual(j, cur)).filter(Boolean);
  const mids = withSal.map((a) => a.mid);
  const bySec = {};
  data.jobs.forEach((j) => { const a = GJ.annual(j, cur); if (a) j.sectors.forEach((s) => { (bySec[s] = bySec[s] || []).push(a.mid); }); });
  return {
    n: data.jobs.length, disclosed: withSal.length, disc_pct: Math.round(100 * withSal.length / Math.max(1, data.jobs.length)),
    median: GJ.median(mids), hist: GJ.histogram(mids, [20000, 30000, 40000, 50000, 60000, 75000, 100000]).map((b) => [b.label, b.n]),
    sector_medians: Object.keys(bySec).filter((s) => bySec[s].length >= 3).sort().map((s) => [s, GJ.median(bySec[s])]),
    regions: data.regions.slice(0, 12).map((r) => [r.name, r.n]), sectors: data.sectors.map((s) => [s.name, s.n]),
  };
}

for (const site of ['ie', 'uk']) {
  test(`parity ${site}: the live board set (paginated /api/jobs?view=board via api.js) equals build_site.py's dataset and chart figures`, async () => {
    const w = await worldFor(site);
    const API = JS('api.js');
    const GJ = JS('lib.js');
    const calls = [];
    const fetchFn = async (url) => { calls.push(url); return w.fetch(new Request(url)); };
    const live = await API.loadJobs(fetchFn, `https://${HOST[site]}`, site, { limit: 2 });
    const stat = datasetOf(B.sites[site].list_html);
    assert.ok(calls.length >= 2 && calls.every((u) => u.includes(`site=${site}`)), 'paginated, edition named');
    const merged = API.merge(stat, live, '');
    assert.equal(merged.today, stat.today);
    assert.deepEqual(merged.sectors, stat.sectors);
    assert.deepEqual(merged.regions, stat.regions);
    assert.deepEqual(merged.types, stat.types);
    assert.deepEqual(merged.contracts, stat.contracts);
    assert.deepEqual(merged.jobs.map((j) => j.id), stat.jobs.map((j) => j.id), 'same jobs, same order');
    for (let i = 0; i < stat.jobs.length; i++) {
      const s = stat.jobs[i];
      const m = merged.jobs[i];
      for (const k of Object.keys(s)) if (k !== 'text') assert.deepEqual(m[k], s[k], `${site} ${s.id}.${k}`);
    }
    const figs = insightFigures(GJ, merged);
    assert.deepEqual(figs, insightFigures(GJ, stat));
    // and the figures equal what build_site.py printed (salary_stats)
    assert.equal(figs.n, B.sites[site].stats.salary.n_jobs);
    assert.equal(figs.disclosed, B.sites[site].stats.salary.n_disc);
  });
}
