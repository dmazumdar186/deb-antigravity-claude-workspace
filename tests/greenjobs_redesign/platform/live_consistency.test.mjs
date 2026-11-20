// Eye review 2026-11-20 fixes, proven against the real Worker on SQLite-backed D1 (no network):
//   B1  one live rule: list, sector page, sitemap, /api/jobs (both views), /api/stats, job page, /api/apply agree
//   B2/B3/M4  the staging seed (staging_seed.py) and the static board come from one normalised set: same ids, same
//       salary figures, every static card resolves to a 200 Worker job page, sterling kept on IE
//   M1  posted date is the source's (never created_at/import time); a feed re-import carries the source date
//   M3  an apply link into the retired Strategies platform is never rendered (render-time and import-time)
//   M5  "Similar roles" fills from the same sector OR region and is hidden when nothing matches
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdirSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import test from 'node:test';
import { REPO, makeWorld, seedJob, workerModule } from './helpers.mjs';

const get = (host, path) => new Request(`https://${host}${path}`);
const IE = 'greenjobs.ie';
const body = async (r) => r.text();
const jsonOf = async (r) => JSON.parse(await r.text());

async function boardSet(w, site, host = IE) {
  const out = [];
  let after = null;
  for (let i = 0; i < 50; i++) {
    const r = await jsonOf(await w.fetch(get(host, `/api/jobs?view=board&site=${site}&limit=500${after ? `&after=${after}` : ''}`)));
    out.push(...r.jobs.map((j) => j.id));
    if (!r.next) break;
    after = r.next;
  }
  return out;
}

test('B1: one live definition across every reader (UTC calendar days, closing day itself live)', async () => {
  const { isLive, liveWhere } = await workerModule('live.js');
  const w = await makeWorld(); // clock 2026-11-07T10:00Z
  const mk = (title, o) => seedJob(w, { title, sectors: ['Wind energy'], ...o });
  const yesterday = mk('Closed Yesterday Engineer', { closing_at: '2026-11-06T23:59:59Z' });
  const todayDate = mk('Closes Today Date Engineer', { closing_at: '2026-11-07' });
  const todayTs = mk('Closes Today Midnight Engineer', { closing_at: '2026-11-07T00:00:00Z' });
  const open = mk('No Closing Date Engineer', { closing_at: null });
  const closed = mk('Status Closed Engineer', { status: 'closed' });
  const draft = mk('Draft Engineer', { status: 'draft' });
  const liveIds = [todayDate, todayTs, open].sort();

  // the JS rule and the SQL predicate agree row by row
  const rows = w.db.q('SELECT id, status, closing_at FROM jobs');
  const bySql = w.db.q(`SELECT id FROM jobs WHERE ${liveWhere('', '?1')}`, '2026-11-07').map((r) => r.id).sort();
  assert.deepEqual(rows.filter((r) => isLive(r, '2026-11-07')).map((r) => r.id).sort(), bySql);
  assert.deepEqual(bySql, liveIds);

  const list = await body(await w.fetch(get(IE, '/ie/jobs/')));
  const sector = await body(await w.fetch(get(IE, '/ie/sectors/wind-energy/')));
  const sitemap = await body(await w.fetch(get(IE, '/sitemap-jobs.xml')));
  const board = (await boardSet(w, 'ie')).sort();
  const pub = (await jsonOf(await w.fetch(get(IE, '/api/jobs')))).jobs.map((j) => j.id).sort();
  const stats = await jsonOf(await w.fetch(get(IE, '/api/stats')));
  const { slugOf } = await workerModule('routes/board.js');
  for (const [id, title, live] of [[yesterday, 'Closed Yesterday', false], [todayDate, 'Closes Today Date', true], [todayTs, 'Closes Today Midnight', true],
    [open, 'No Closing Date', true], [closed, 'Status Closed', false], [draft, 'Draft Engineer', false]]) {
    assert.equal(list.includes(title), live, `list: ${title}`);
    assert.equal(sector.includes(title), live, `sector page: ${title}`);
    assert.equal(sitemap.includes(`/ie/jobs/${slugOf(id)}/`), live, `sitemap: ${title}`);
    const page = await w.fetch(get(IE, `/ie/jobs/${slugOf(id)}/`));
    assert.equal(page.status, live ? 200 : id === draft ? 404 : 410, `job page: ${title}`);
  }
  assert.deepEqual(board, liveIds.map((id) => slugOf(id)).sort()); // view=board carries public ids (slugs)
  assert.deepEqual(pub, liveIds);
  assert.equal(stats.live_jobs, 3);
  assert.equal(stats.kpis.live, 3);

  // guard fires: no route keeps its own copy of the live predicate
  for (const f of ['routes/board.js', 'routes/public.js', 'routes/apply.js', 'listmail/alerts.js']) {
    const src = readFileSync(resolve(REPO, 'execution/gtm_client_workflows/greenjobs_redesign/platform_worker/src', f), 'utf8');
    assert.ok(!/closing_at IS NULL OR/.test(src), `${f} defines its own live rule`);
    assert.ok(/liveWhere\(/.test(src), `${f} uses liveWhere`);
  }
});

test('M1: posted date is the source date; created_at (import time) is never shown as posted', async () => {
  const w = await makeWorld();
  const id = seedJob(w, { title: 'No Posted Date Ecologist', posted_at: null });
  w.db.sqlite.prepare(`UPDATE jobs SET posted_at = NULL, created_at = '2026-11-07T09:00:00Z' WHERE id = ?1`).run(id);
  const real = seedJob(w, { title: 'Real Posted Date Ecologist', posted_at: '2026-09-10T00:00:00Z' });
  const { jobs } = await jsonOf(await w.fetch(get(IE, '/api/jobs?view=board&site=ie')));
  const byTitle = Object.fromEntries(jobs.map((j) => [j.title, j]));
  assert.equal(byTitle['No Posted Date Ecologist'].posted, '');
  assert.equal(byTitle['Real Posted Date Ecologist'].posted, '2026-09-10');
  const pub = (await jsonOf(await w.fetch(get(IE, '/api/jobs')))).jobs.find((j) => j.id === id);
  assert.equal(pub.posted, '');
  const page = await body(await w.fetch(get(IE, `/ie/jobs/${real.split(':')[2]}/`)));
  assert.match(page, /Posted 10 September 2026/);
  assert.doesNotMatch(await body(await w.fetch(get(IE, '/ie/jobs/'))), /datetime="2026-11-07">Today/);

  // a feed re-import carries the source's date over a wrong stored one (FEED_JOB_UPSERT)
  const Q = await workerModule('sql_0003.js');
  w.db.sqlite.prepare(`INSERT INTO employers (id, site, source, source_id, name, name_norm, created_at, updated_at) VALUES ('ie:feed:gaia', 'ie', 'feed', 'gaia', 'Gaia Talent', 'gaia talent', 't', 't')`).run();
  const up = (posted) => w.db.sqlite.prepare(Q.FEED_JOB_UPSERT).run('ie:gaia:77', 'ie', 'gaia:77', 'ie:feed:gaia', 'gaia talent', 'Gaia Feed Ecologist', 'Cork', 'Cork', 'Permanent',
    null, '[]', null, 'Plenty of description for the feed job here.', 'link', null, 'https://gaiatalent.com/jobs/x', 'live', posted, null, '2026-11-07T09:00:00Z');
  up('2026-11-20T00:00:00Z');
  up('2026-10-02T08:00:00Z');
  assert.equal(w.db.q(`SELECT posted_at FROM jobs WHERE id = 'ie:gaia:77'`)[0].posted_at, '2026-10-02T08:00:00Z');
});

const OLD_URLS = [
  'https://www.greenjobs.ie/jobs/11501648/labs-designer-and-facilitator-uk-ireland.asp',
  'https://www.greenjobs.co.uk/jobs/11501644/labs-designer-and-facilitator-uk-ireland.asp',
  'https://greenjobs.ie/for-employers.asp',
  'https://www.greenjobs.ie/browse-jobs/commonland',
  'https://www.greenjobs.co.uk/jobboard/public/5105/clientlogos/Logo_8351.png',
  'https://www-greenjobs-co-uk.cname.strategiesuk.net/jobs/1/x.asp',
  'https://www.strategies.co.uk/anything',
];
const NEW_URLS = ['https://greenjobs.ie/ie/jobs/11488772/', 'https://www.greenjobs.co.uk/uk/employers/', 'https://gaiatalent.com/jobs/ecologist', 'https://ats.example.com/7.asp'];

test('M3: old-platform apply URLs (September shapes) are never rendered; import classifies them as email mode', async () => {
  const { isOldPlatformUrl } = await workerModule('oldplatform.js');
  for (const u of OLD_URLS) assert.equal(isOldPlatformUrl(u), true, u);
  for (const u of NEW_URLS) assert.equal(isOldPlatformUrl(u), false, u);
  // same answers as build_site.is_old_platform_url (one rule on both sides)
  const py = JSON.parse(execFileSync('python3', ['-c', `import sys,json; sys.path.insert(0, ${JSON.stringify(resolve(REPO, 'execution/gtm_client_workflows/greenjobs_redesign'))}); import validate_site as v; print(json.dumps([v.is_old_platform_url(u) for u in json.load(sys.stdin)]))`],
    { input: JSON.stringify([...OLD_URLS, ...NEW_URLS]), encoding: 'utf8' }));
  assert.deepEqual(py, [...OLD_URLS.map(() => true), ...NEW_URLS.map(() => false)]);

  const w = await makeWorld();
  const id = seedJob(w, { title: 'Old Link Hydrologist', apply_mode: 'link', apply_url: OLD_URLS[0] });
  const page = await body(await w.fetch(get(IE, `/ie/jobs/${id.split(':')[2]}/`)));
  assert.ok(!page.includes('.asp'), 'job page renders no .asp link');
  assert.match(page, /data-apply-form/);
  const pub = (await jsonOf(await w.fetch(get(IE, '/api/jobs')))).jobs;
  assert.ok(pub.length === 1);
  const one = await jsonOf(await w.fetch(get(IE, `/api/jobs/${encodeURIComponent(id)}`)));
  assert.equal(one.apply_mode, 'email');
  assert.equal(one.apply_url, null);
  const { isLinkMode } = await workerModule('routes/apply.js');
  assert.equal(isLinkMode({ apply_mode: 'link', apply_url: OLD_URLS[0] }), false);
  assert.equal(isLinkMode({ apply_mode: 'link', apply_url: NEW_URLS[2] }), true);

  const { validateImportJob } = await workerModule('routes/import.js');
  const src = { idRe: /^gaia:[0-9]+$/ };
  const TAX = JSON.parse(readFileSync(resolve(REPO, 'execution/gtm_client_workflows/greenjobs_redesign/platform_worker/src/taxonomy.json'), 'utf8'));
  const base = { source_id: 'gaia:1', title: 'Old Link Ecologist', location: 'Cork', description: 'A long enough description for the import.', sectors: [], status: 'live',
    facets: { sectors: [], regions: ['Cork'], job_type: 'Permanent', workplace: 'hybrid', contract: ['permanent'], loc_class: 'ie', level: null, is_agency: 0, salary_display: null,
      unverified_cur: 0, search_text: 'x', source_sectors: [], sector_confidence: 0.95, sector_method: 'keyword', taxonomy_version: TAX.version } };
  const conv = validateImportJob({ ...base, apply_mode: 'link', apply_url: OLD_URLS[0] }, src, new Set());
  assert.equal(conv.ok, true);
  assert.deepEqual([conv.job.apply_mode, conv.job.apply_email, conv.job.apply_url], ['email', null, null]);
  const own = validateImportJob({ ...base, apply_mode: 'link', apply_url: OLD_URLS[1], apply_email: 'Jobs@Client.ie' }, src, new Set());
  assert.deepEqual([own.job.apply_mode, own.job.apply_email], ['email', 'jobs@client.ie']);
  const keep = validateImportJob({ ...base, apply_mode: 'link', apply_url: NEW_URLS[2] }, src, new Set());
  assert.equal(keep.job.apply_mode, 'link');
});

test('M5: similar roles from the same sector or region; the block is hidden when none', async () => {
  const w = await makeWorld();
  const a = seedJob(w, { title: 'Lonely Arborist', sectors: ['Forestry & arboriculture'] });
  let page = await body(await w.fetch(get(IE, `/ie/jobs/${a.split(':')[2]}/`)));
  assert.match(page, /<section class="band--alt similar" aria-labelledby="h-sim" hidden>/);
  // a job in another sector but the same region now counts as similar
  w.db.sqlite.prepare(`UPDATE job_facets SET regions_json = '["Cork"]'`).run();
  const b = seedJob(w, { title: 'Cork Water Engineer', sectors: ['Water & wastewater'] });
  for (const id of [a, b]) {
    w.db.sqlite.prepare(`INSERT OR REPLACE INTO job_facets (job_id, sectors_json, regions_json, workplace, contract_json, loc_class, is_agency, unverified_cur, taxonomy_version, set_by, updated_at)
      VALUES (?1, ?2, '["Cork"]', 'unspecified', '[]', 'ie', 0, 0, 1, 'import', 't')`).run(id, id === a ? '["Forestry & arboriculture"]' : '["Water & wastewater"]');
  }
  page = await body(await w.fetch(get(IE, `/ie/jobs/${a.split(':')[2]}/`)));
  assert.match(page, /<section class="band--alt similar" aria-labelledby="h-sim">/);
  assert.ok(page.split('id="h-sim"')[1].includes('Cork Water Engineer'));
});

test('B2/B3/M4/M6: the staging seed in D1 equals the static board built from the same set', async () => {
  const out = resolve(REPO, '.tmp/test_staging_seed_node');
  mkdirSync(out, { recursive: true });
  execFileSync('python3', [resolve(REPO, 'execution/gtm_client_workflows/greenjobs_redesign/staging_seed.py'), '--env', 'staging', '--seed-date', '2026-11-20',
    '--gaia-feed', resolve(REPO, 'tests/greenjobs_redesign/fixtures/gaia_d1/feed_small.json'), '--out', out], { encoding: 'utf8' });
  const manifest = JSON.parse(readFileSync(resolve(out, 'manifest.json'), 'utf8'));
  const w = await makeWorld();
  w.clock.now = new Date('2026-11-20T10:00:00Z');
  w.db.sqlite.exec(readFileSync(resolve(out, 'seed.sql'), 'utf8'));
  w.db.sqlite.exec(readFileSync(resolve(out, 'seed.sql'), 'utf8')); // idempotent re-run
  const { slugOf, idOfSlug } = await workerModule('routes/board.js');
  for (const [site, host] of [['ie', 'greenjobs.ie'], ['uk', 'greenjobs.co.uk']]) {
    const want = manifest.static[site];
    const got = (await boardSet(w, site, host));
    const slugs = got; // view=board ids are the public slugs
    assert.deepEqual([...slugs].sort(), [...want.ids].sort(), `${site}: D1 live set = static board set`);
    const stats = await jsonOf(await w.fetch(get(host, `/api/stats?site=${site}`)));
    assert.equal(stats.live_jobs, want.ids.length);
    for (const k of ['n_jobs', 'n_disc', 'disc_pct', 'median']) assert.equal(String(stats.salary[k]), String(want.salary[k]), `${site} salary.${k}`);
    for (const jid of want.ids.slice(0, 40)) {
      assert.ok(idOfSlug(site, jid), `${site}: static id ${jid} has a Worker slug`);
      const r = await w.fetch(get(host, `/${site}/jobs/${jid}/`));
      assert.equal(r.status, 200, `${site}: static card ${jid} opens a live Worker page`);
    }
  }
  const all = w.db.q(`SELECT site, title, posted_at, closing_at, currency, apply_mode, apply_url, created_by FROM jobs`);
  assert.ok(all.some((r) => r.created_by === 'staging-seed') && all.some((r) => r.created_by === 'staging-seed-test'));
  assert.ok(all.filter((r) => r.created_by === 'staging-seed-test').every((r) => r.title.startsWith('[Test data] ')));
  const testPosted = all.filter((r) => r.created_by === 'staging-seed-test').map((r) => r.posted_at);
  assert.ok(new Set(testPosted).size > 10 && testPosted.filter((p) => p === '2026-11-20T00:00:00Z').length < testPosted.length / 4, 'test data keeps its re-based posted dates (not the seed time)');
  assert.ok(all.some((r) => r.closing_at), 'closing dates are seeded');
  assert.ok(all.every((r) => r.apply_mode === 'email' || !/\.asp|strategies/.test(r.apply_url)));
  assert.ok(all.some((r) => r.site === 'ie' && r.currency === 'GBP'), 'sterling roles on the IE board keep GBP');
  // M4 / client B2 (Sept): a sterling role on the IE board is served and rendered in £, never relabelled €
  const ieBoard = (await jsonOf(await w.fetch(get(IE, '/api/jobs?view=board&site=ie&limit=500')))).jobs;
  const gbp = ieBoard.find((j) => j.cur === 'GBP' && j.sal_min != null);
  assert.ok(gbp, 'IE board rows carry GBP');
  const gbpPage = await body(await w.fetch(get(IE, `/ie/jobs/${gbp.id}/`)));
  assert.match(gbpPage, /tag--sal">£[0-9]/);
  assert.doesNotMatch(gbpPage, /advertiser may pay in sterling/);
  const kpis = (await jsonOf(await w.fetch(get(IE, '/api/stats?site=ie')))).kpis;
  assert.ok(kpis.new7 < kpis.live, 'not every role is "new this week"');
});
