// End-to-end gate (blocks deploy via run_tests.sh): a job posted in the staff console reaches the public
// board with no rebuild. Real SQLite-backed D1 (schema.sql + every migration), the real Worker handler,
// Access JWTs signed by a local key, no network:
//   console create (IE + UK) -> GET /jobs/<slug>/ (301) -> /ie/jobs/<slug>/ 200 with JobPosting JSON-LD
//   -> in the /ie/jobs/ list, the sector view and /sitemap-jobs.xml -> counted by /api/stats
//   -> edit (sector, employer) shows on the page -> close -> 410 with a link to the list -> reopen -> 200.
import assert from 'node:assert/strict';
import test from 'node:test';
import { adminRequest, makeWorld, seedJob, validJobBody } from './helpers.mjs';

const get = (host, path) => new Request(`https://${host}${path}`);
const jsonOf = async (r) => JSON.parse(await r.text());
const ld = (html) => [...html.matchAll(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/g)].map((m) => JSON.parse(m[1]));

test('E2E: console post -> live job page, list, sector view, sitemap, stats -> edit -> close 410 -> reopen', async () => {
  const w = await makeWorld();
  const before = await jsonOf(await w.fetch(get('greenjobs.ie', '/api/stats')));
  assert.equal(before.kpis.live, 0);

  // 1. One console form posts to both boards.
  const create = await w.fetch(await adminRequest('POST', '/api/admin/jobs', {
    body: validJobBody({
      title: 'Offshore Wind Consents Manager', employer: 'Atlantic Wind DAC', location: 'Galway', sectors: ['Wind energy', 'Policy, planning & advisory'],
      job_type: 'Permanent', workplace: 'hybrid', sal_min: 60000, sal_max: 70000, sal_text: '€60,000 - €70,000', sites: ['ie', 'uk'],
      region_by_site: { ie: 'Galway', uk: 'Ireland & abroad' }, description: 'Lead marine consents for a 900 MW offshore wind array.\n\nYou will own the EIAR and the foreshore licence.',
    }),
  }));
  assert.equal(create.status, 201);
  const made = await jsonOf(create);
  assert.equal(made.ids.length, 2);
  const [ieId, ukId] = made.ids;
  assert.match(ieId, /^ie:gj:/);
  assert.match(ukId, /^uk:gj:/);
  const slug = ieId.split(':')[2];
  assert.deepEqual(made.urls, [`/ie/jobs/gj-${slug}/`, `/uk/jobs/gj-${ukId.split(':')[2]}/`]);
  assert.deepEqual(w.db.q('SELECT job_id, loc_class, workplace, level, set_by FROM job_facets ORDER BY job_id'), [
    { job_id: ieId, loc_class: 'ie', workplace: 'hybrid', level: 'Mid-level', set_by: 'console' },
    { job_id: ukId, loc_class: 'intl', workplace: 'hybrid', level: 'Mid-level', set_by: 'console' },
  ]);

  assert.match(w.db.q('SELECT search_text FROM job_facets WHERE job_id = ?1', ieId)[0].search_text, /^Lead marine consents .* foreshore licence\.$/);

  // 2. The short path redirects to the board path; the page is live with valid JobPosting data.
  const short = await w.fetch(get('greenjobs.ie', `/jobs/gj-${slug}/`));
  assert.equal(short.status, 301);
  assert.equal(short.headers.get('Location'), `/ie/jobs/gj-${slug}/`);
  const page = await w.fetch(get('greenjobs.ie', `/ie/jobs/gj-${slug}/`));
  assert.equal(page.status, 200);
  assert.match(page.headers.get('Cache-Control'), /s-maxage=300/);
  const html = await page.text();
  assert.match(html, /<h1 class="vt-title">Offshore Wind Consents Manager<\/h1>/);
  assert.match(html, /<link rel="canonical" href="https:\/\/greenjobs\.ie\/ie\/jobs\/gj-/);
  assert.match(html, /action="\/api\/apply"/, 'email mode: on-site form, never a Strategies URL');
  assert.doesNotMatch(html.slice(html.indexOf('<main'), html.indexOf('</main>')), /strategies|\.asp\b/i);
  const posting = ld(html).find((x) => x['@type'] === 'JobPosting');
  for (const k of ['title', 'description', 'datePosted', 'validThrough', 'hiringOrganization', 'jobLocation', 'employmentType', 'baseSalary']) assert.ok(posting[k], k);
  assert.equal(posting.employmentType, 'FULL_TIME');
  assert.equal(posting.baseSalary.currency, 'EUR');
  assert.equal(posting.directApply, true);
  assert.equal(posting.url, `https://greenjobs.ie/ie/jobs/gj-${slug}/`);
  const uk = await w.fetch(get('greenjobs.co.uk', `/uk/jobs/gj-${ukId.split(':')[2]}/`));
  assert.equal(uk.status, 200);

  // 3. List, filters, sector view, sitemap, stats.
  const list = await (await w.fetch(get('greenjobs.ie', '/ie/jobs/'))).text();
  assert.match(list, new RegExp(`href="/ie/jobs/gj-${slug}/"`));
  assert.match(list, /id="gj-data"/);
  const filtered = await (await w.fetch(get('greenjobs.ie', '/ie/jobs/?sector=Solar%20energy'))).text();
  assert.doesNotMatch(filtered.slice(filtered.indexOf('data-list'), filtered.indexOf('data-list') + 4000), new RegExp(`gj-${slug}`));
  const byRegion = await (await w.fetch(get('greenjobs.ie', '/ie/jobs/?region=Galway&q=consents'))).text();
  assert.match(byRegion, /<b>1<\/b> roles/);
  const sector = await w.fetch(get('greenjobs.ie', '/ie/sectors/wind-energy/'));
  assert.equal(sector.status, 200);
  const sectorHtml = await sector.text();
  assert.match(sectorHtml, /<h1>Wind energy jobs<\/h1>/);
  assert.match(sectorHtml, new RegExp(`gj-${slug}`));
  assert.equal((await w.fetch(get('greenjobs.ie', '/ie/sectors/not-a-sector/'))).status, 404);
  const overview = await w.fetch(get('greenjobs.ie', '/ie/sectors/index.html'));
  assert.equal(overview.headers.get('X-Test-Origin'), '1', 'the static sectors overview is handed back to Pages');
  const map = await (await w.fetch(get('greenjobs.ie', '/sitemap-jobs.xml'))).text();
  assert.match(map, new RegExp(`<loc>https://greenjobs.ie/ie/jobs/gj-${slug}/</loc>`));
  assert.doesNotMatch(map, /uk:gj|\/uk\/jobs/);
  const stats = await jsonOf(await w.fetch(get('greenjobs.ie', '/api/stats')));
  assert.equal(stats.kpis.live, 1);
  assert.equal(stats.salary.n_disc, 1);
  assert.equal(stats.sectors.find((s) => s.name === 'Wind energy').n, 1);

  // 4. Every field stays editable: sector and employer change shows on the page.
  const edit = await w.fetch(await adminRequest('PUT', `/api/admin/jobs/${ieId}`, { body: { version: 1, sectors: ['Climate & carbon'], employer: 'Atlantic Offshore Ltd' } }));
  assert.equal(edit.status, 200);
  const edited = await (await w.fetch(get('greenjobs.ie', `/ie/jobs/gj-${slug}/`))).text();
  assert.match(edited, /<span>Atlantic Offshore Ltd<\/span>/);
  assert.match(edited, /<dt>Sector<\/dt><dd>Climate &amp; carbon<\/dd>/);

  // 5. Close -> 410 with a link back to the list; gone from the list, sitemap and stats.
  const close = await w.fetch(await adminRequest('POST', `/api/admin/jobs/${ieId}/close`, { body: {} }));
  assert.equal(close.status, 200);
  const gone = await w.fetch(get('greenjobs.ie', `/ie/jobs/gj-${slug}/`));
  assert.equal(gone.status, 410);
  const goneHtml = await gone.text();
  assert.match(goneHtml, /This role has closed/);
  assert.match(goneHtml, /href="\/ie\/jobs\/index.html"/);
  assert.match(goneHtml, /noindex/);
  assert.doesNotMatch(await (await w.fetch(get('greenjobs.ie', '/sitemap-jobs.xml'))).text(), new RegExp(`gj-${slug}`));
  assert.equal((await jsonOf(await w.fetch(get('greenjobs.ie', '/api/stats')))).kpis.live, 0);

  // 6. Reopen brings it back.
  const reopen = await w.fetch(await adminRequest('PUT', `/api/admin/jobs/${ieId}`, { body: { version: 3, status: 'live' } }));
  assert.equal(reopen.status, 200, JSON.stringify(await reopen.clone().json()));
  assert.equal(w.db.q('SELECT closed_at FROM jobs WHERE id = ?1', ieId)[0].closed_at, null);
  assert.equal((await w.fetch(get('greenjobs.ie', `/ie/jobs/gj-${slug}/`))).status, 200);
});

test('board: expired, draft, unknown and cross-site jobs; link mode; escaping and sanitising', async () => {
  const w = await makeWorld();
  seedJob(w, { id: 'ie:strat:9001', title: 'Expired Role', closing_at: '2026-11-01T23:59:59Z' });
  seedJob(w, { id: 'ie:strat:9002', title: 'Draft Role', status: 'draft' });
  seedJob(w, { id: 'ie:strat:9003', title: 'Ecologist <script>alert(1)</script>', apply_mode: 'link', apply_url: 'https://ats.example.com/9003',
    description: '<p>Survey bats.</p><img src=x onerror=alert(1)><a href="javascript:alert(2)">x</a><script>alert(3)</script><p onclick="y()">Field work</p>' });
  seedJob(w, { id: 'uk:strat:9004', site: 'uk', title: 'UK Role' });
  assert.equal((await w.fetch(get('greenjobs.ie', '/ie/jobs/9001/'))).status, 410, 'past closing date = closed');
  assert.equal((await w.fetch(get('greenjobs.ie', '/ie/jobs/9002/'))).status, 404, 'a draft was never public');
  assert.equal((await w.fetch(get('greenjobs.ie', '/ie/jobs/424242/'))).status, 404);
  assert.equal((await w.fetch(get('greenjobs.ie', '/ie/jobs/..%2F..%2Fetc/'))).status, 404);
  assert.equal((await w.fetch(get('greenjobs.ie', '/uk/jobs/9004/'))).status, 404, 'no cross-site render without CANONICAL_ORIGIN_UK');
  const page = await w.fetch(get('greenjobs.ie', '/ie/jobs/9003/index.html'));
  assert.equal(page.status, 200);
  const html = await page.text();
  const main = html.slice(html.indexOf('<main'), html.indexOf('</main>'));
  assert.doesNotMatch(main, /<script>alert|onerror|onclick|javascript:/);
  assert.match(main, /Ecologist &lt;script&gt;alert\(1\)&lt;\/script&gt;/);
  assert.match(main, /<a class="btn btn--lime" href="https:\/\/ats\.example\.com\/9003" rel="noopener nofollow"/);
  assert.doesNotMatch(main, /action="\/api\/apply"/, 'link mode has no on-site form');
  assert.match(html, /<meta name="robots" content="noindex,nofollow">/, 'demo shell stays noindex until ROBOTS_INDEX=1');
  const w2 = await makeWorld({ ROBOTS_INDEX: '1', CANONICAL_ORIGIN_IE: 'https://www.greenjobs.ie', CANONICAL_ORIGIN_UK: 'https://www.greenjobs.co.uk' });
  seedJob(w2, { id: 'ie:strat:9005' });
  const p2 = await (await w2.fetch(get('greenjobs.ie', '/ie/jobs/9005/'))).text();
  assert.match(p2, /<meta name="robots" content="index,follow">/);
  assert.match(p2, /<link rel="canonical" href="https:\/\/www\.greenjobs\.ie\/ie\/jobs\/9005\/">/);
  const cross = await w2.fetch(get('greenjobs.ie', '/uk/jobs/9004/'));
  assert.equal(cross.status, 301);
  assert.equal(cross.headers.get('Location'), 'https://www.greenjobs.co.uk/uk/jobs/9004/');
});

test('board list: pagination at 25 rows, ?page bounds, filters by type and q', async () => {
  const w = await makeWorld();
  for (let i = 0; i < 30; i++) seedJob(w, { id: `ie:strat:${8000 + i}`, title: `Role ${i}`, posted_at: `2026-11-0${1 + (i % 6)}T09:00:00Z` });
  const p1 = await (await w.fetch(get('greenjobs.ie', '/ie/jobs/'))).text();
  assert.equal((p1.match(/<article class="row"/g) || []).length, 25);
  assert.match(p1, /<nav class="pager" aria-label="Pages"><span>Page 1 of 2<\/span><a rel="next" href="\?page=2">Next<\/a><\/nav>/);
  const p2 = await (await w.fetch(get('greenjobs.ie', '/ie/jobs/?page=2'))).text();
  assert.equal((p2.match(/<article class="row"/g) || []).length, 5);
  const p9 = await (await w.fetch(get('greenjobs.ie', '/ie/jobs/?page=99'))).text();
  assert.match(p9, /Page 2 of 2/);
  const q = await (await w.fetch(get('greenjobs.ie', '/ie/jobs/?q=role%2029'))).text();
  assert.equal((q.match(/<article class="row"/g) || []).length, 1);
});

test('console: taxonomy dropdowns, site checkboxes, confirm on close, reopen; API guards', async () => {
  const w = await makeWorld();
  const html = await (await w.fetch(await adminRequest('GET', '/admin/'))).text();
  assert.match(html, /<select name="sector1" required><option value="">Choose a sector<\/option><option value="Wind energy">/);
  assert.match(html, /name="site_ie" value="ie" checked/);
  assert.match(html, /name="site_uk" value="uk">/);
  assert.match(html, /<select name="region_ie"><option value="Carlow">/);
  assert.match(html, /<select name="region_uk"><option value="London">/);
  assert.match(html, /<select name="job_type">/);
  assert.match(html, /<select name="workplace"><option value="office">Office-based/);
  assert.doesNotMatch(html, /style=|<script(?![^>]*\bsrc=)/);
  const js = await (await w.fetch(await adminRequest('GET', '/admin/console.js'))).text();
  assert.match(js, /window\.confirm\(/);
  assert.match(js, /'Reopen'/);
  assert.doesNotMatch(js, /innerHTML/);

  const post = async (over) => w.fetch(await adminRequest('POST', '/api/admin/jobs', { body: validJobBody(over) }));
  const bad = async (over, fields) => {
    const r = await post(over);
    assert.equal(r.status, 400, JSON.stringify(over));
    assert.deepEqual((await r.json()).fields, fields);
  };
  await bad({ sectors: ['Solar'] }, ['sectors']);
  await bad({ sectors: [] }, ['sectors']);
  await bad({ sectors: ['Solar energy', 'Wind energy', 'Water & flood', 'Climate & carbon'] }, ['sectors']);
  await bad({ region: 'Atlantis' }, ['region']);
  await bad({ sites: ['ie', 'fr'] }, ['sites']);
  await bad({ sites: [] }, ['sites']);
  await bad({ sites: ['ie', 'uk'], region_by_site: { ie: 'Cork', uk: 'Cork' } }, ['region_by_site']);
  await bad({ job_type: 'Gig' }, ['job_type']);
  await bad({ workplace: 'moon' }, ['workplace']);
  assert.equal(w.db.q('SELECT COUNT(*) AS n FROM jobs')[0].n, 0, 'nothing half-written');

  // Replay of a two-site create returns the same two ids and writes nothing new.
  const idem = crypto.randomUUID();
  const body = validJobBody({ sites: ['ie', 'uk'], region_by_site: { ie: 'Cork', uk: 'Wales' } });
  const a = await (await w.fetch(await adminRequest('POST', '/api/admin/jobs', { body, idem }))).json();
  const b = await (await w.fetch(await adminRequest('POST', '/api/admin/jobs', { body, idem }))).json();
  assert.deepEqual(b.ids, a.ids);
  assert.equal(b.replayed, true);
  assert.equal(w.db.q('SELECT COUNT(*) AS n FROM jobs')[0].n, 2);
  assert.equal(w.db.q('SELECT COUNT(*) AS n FROM job_facets')[0].n, 2);

  // Reopen of a job whose closing date has passed asks for a new date.
  const id = a.ids[0];
  await w.fetch(await adminRequest('POST', `/api/admin/jobs/${id}/close`, { body: {} }));
  w.advance(60 * 864e5);
  const r1 = await w.fetch(await adminRequest('PUT', `/api/admin/jobs/${id}`, { body: { version: 2, status: 'live' }, signOpts: { nowMs: w.clock.now.getTime() } }));
  assert.equal(r1.status, 400);
  assert.deepEqual((await r1.json()).fields, ['closing']);
  const newClosing = new Date(w.clock.now.getTime() + 10 * 864e5).toISOString().slice(0, 10);
  const r2 = await w.fetch(await adminRequest('PUT', `/api/admin/jobs/${id}`, { body: { version: 2, status: 'live', closing: newClosing }, signOpts: { nowMs: w.clock.now.getTime() } }));
  assert.equal(r2.status, 200);
  assert.equal(w.db.q('SELECT status FROM jobs WHERE id = ?1', id)[0].status, 'live');

  // A stale edit writes neither the job nor its facets.
  const stale = await w.fetch(await adminRequest('PUT', `/api/admin/jobs/${id}`, { body: { version: 1, sectors: ['Water & flood'] }, signOpts: { nowMs: w.clock.now.getTime() } }));
  assert.equal(stale.status, 409);
  assert.deepEqual(JSON.parse(w.db.q('SELECT sectors_json FROM job_facets WHERE job_id = ?1', id)[0].sectors_json), ['Solar energy']);

  // An imported job without facets edits as before (no picks needed) and stays facet-less.
  seedJob(w, { id: 'ie:strat:7001', sectors: ['Wind'] });
  const imp = await w.fetch(await adminRequest('PUT', '/api/admin/jobs/ie:strat:7001', { body: { version: 1, title: 'Renamed Wind Role' }, signOpts: { nowMs: w.clock.now.getTime() } }));
  assert.equal(imp.status, 200);
  assert.equal(w.db.q("SELECT COUNT(*) AS n FROM job_facets WHERE job_id = 'ie:strat:7001'")[0].n, 0);
});

test('migration 0002: applies twice, survives a re-run of 0001, keeps facets', async () => {
  const { MIGRATIONS } = await import('./helpers.mjs');
  const w = await makeWorld();
  seedJob(w, { id: 'ie:strat:5001' });
  w.db.sqlite.prepare(`INSERT INTO job_facets (job_id, sectors_json, taxonomy_version, set_by, updated_at) VALUES ('ie:strat:5001', '["Wind energy"]', 1, 'import', 't')`).run();
  for (const m of [...MIGRATIONS, ...MIGRATIONS]) w.db.sqlite.exec('BEGIN;\n' + m + '\nCOMMIT;');
  assert.deepEqual(w.db.q('SELECT job_id, sectors_json FROM job_facets'), [{ job_id: 'ie:strat:5001', sectors_json: '["Wind energy"]' }]);
  assert.deepEqual(w.db.q('PRAGMA foreign_key_check'), []);
  assert.throws(() => w.db.sqlite.prepare(`INSERT INTO job_facets (job_id, workplace, taxonomy_version, set_by, updated_at) VALUES ('ie:strat:5001x', 'moon', 1, 'import', 't')`).run());
});
