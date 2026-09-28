'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const GJ = require('./lib.js');

const J = [
  { id: '1', title: 'Senior Ecologist', employer: 'A', location: 'Dublin', regions: ['Dublin'], type: 'Permanent', sectors: ['Ecology & conservation'], sal_min: 55000, sal_max: 65000, cur: 'EUR', period: 'year', posted: '2026-09-20', summary: 'bats', text: 'bird surveys and impact assessment' },
  { id: '2', title: 'Solar Project Manager', employer: 'B', location: 'Cork', regions: ['Cork'], type: 'Contract', sectors: ['Solar'], sal_min: null, sal_max: null, cur: null, period: null, posted: '2026-09-19', summary: 'solar farms', text: 'ground mounted solar portfolio' },
  { id: '3', title: 'Water Engineer', employer: 'C', location: 'Galway', regions: ['Galway'], type: 'Permanent', sectors: ['Water'], sal_min: 30, sal_max: 30, cur: 'EUR', period: 'hour', posted: '2026-09-18', summary: 'flood', text: 'drainage design flood risk' },
];

test('salaryLabel formats ranges, singles and rates', () => {
  assert.equal(GJ.salaryLabel(J[0]), '€55k–65k');
  assert.equal(GJ.salaryLabel(J[1]), '');
  assert.equal(GJ.salaryLabel(J[2]), '€30/hr');
  assert.equal(GJ.salaryLabel({ sal_min: 50000, sal_max: null, cur: 'GBP', period: 'year', sal_text: 'up to £50,000' }), 'up to £50k');
});

test('annual annualises hourly and rejects junk', () => {
  assert.equal(GJ.annual(J[0]).mid, 60000);
  assert.equal(GJ.annual(J[2]).lo, 30 * 1950);
  assert.equal(GJ.annual(J[1]), null);
  assert.equal(GJ.annual({ sal_min: 35, sal_max: 45, period: 'year' }), null);
});

test('filterJobs honours every state key and sorts', () => {
  assert.deepEqual(GJ.filterJobs(J, { q: 'ecologist' }).map(j => j.id), ['1']);
  assert.deepEqual(GJ.filterJobs(J, { loc: 'cork' }).map(j => j.id), ['2']);
  assert.deepEqual(GJ.filterJobs(J, { sector: 'water' }).map(j => j.id), ['3']);
  assert.deepEqual(GJ.filterJobs(J, { type: 'Permanent', sal: '1' }).map(j => j.id), ['1', '3']);
  assert.deepEqual(GJ.filterJobs(J, { sort: 'az' }).map(j => j.id), ['1', '2', '3']);
  assert.deepEqual(GJ.filterJobs(J, { sort: 'salary' }).map(j => j.id), ['1', '3', '2']);
  assert.deepEqual(GJ.filterJobs(J, {}).map(j => j.id), ['1', '2', '3']);
  assert.deepEqual(GJ.filterJobs(J, { q: 'senior ecologist dublin' }).map(j => j.id), ['1']);
});

test('URL state round-trips and drops defaults', () => {
  const st = { q: 'wind & solar', sector: 'Water', sort: 'newest', view: 'list', sal: '1' };
  const qs = GJ.toQuery(st);
  assert.ok(!/sort=/.test(qs) && !/view=/.test(qs));
  assert.deepEqual(GJ.parseState(qs), { q: 'wind & solar', sector: 'Water', sal: '1' });
  assert.deepEqual(GJ.parseState('?bogus=1&q=a+b'), { q: 'a b' });
});

test('parseState skips malformed percent-escapes instead of throwing', () => {
  assert.deepEqual(GJ.parseState('?q=%E0'), {});
  assert.deepEqual(GJ.parseState('?q=%E0&loc=Cork'), { loc: 'Cork' });
});

test('jobUrl joins dataset hrefs onto the page-relative jobs base', () => {
  assert.equal(GJ.jobUrl('../jobs/index.html', 'abc-1/index.html'), '../jobs/abc-1/index.html');
  assert.equal(GJ.jobUrl('index.html', 'abc-1/index.html'), 'abc-1/index.html');
  assert.equal(GJ.jobUrl('jobs/index.html', 'abc-1/index.html'), 'jobs/abc-1/index.html');
});

test('histogram bins on the left edge, last band open', () => {
  const h = GJ.histogram([25000, 30000, 44999, 45000, 120000], [20000, 30000, 45000, 60000]);
  assert.deepEqual(h.map(b => b.n), [1, 2, 1, 1]);
  assert.equal(h[3].label, '60k+');
});

test('median and money', () => {
  assert.equal(GJ.median([3, 1, 2]), 2);
  assert.equal(GJ.median([4, 1, 2, 3]), 2.5);
  assert.equal(GJ.median([]), null);
  assert.equal(GJ.money(62500, 'GBP'), '£62.5k');
});

test('smart match ranks by term overlap and returns matched terms', () => {
  const idx = GJ.buildIndex(J);
  const r = GJ.smartMatch('I have done bird and bat surveys and impact assessments', J, idx, 3);
  assert.equal(r[0].job.id, '1');
  assert.ok(r[0].terms.includes('surveys'));
  assert.deepEqual(GJ.smartMatch('zzzz qqqq', J, idx), []);
});

test('suggest finds roles, sectors and places', () => {
  const s = GJ.suggest(J, 'sol');
  assert.equal(s[0].kind, 'role');
  assert.ok(s.some(x => x.kind === 'sector' && x.text === 'Solar'));
  assert.deepEqual(GJ.suggest(J, ''), []);
});

test('compass scoring is deterministic and hash round-trips', () => {
  const qs = [{ opts: [{ w: { A: 3 } }, { w: { B: 3 } }], weight: 2 }, { opts: [{ w: { A: 1, B: 1 } }] }];
  const r = GJ.scoreSectors([1, 0], qs, ['A', 'B']);
  assert.equal(r[0].sector, 'B');
  assert.equal(r[0].pct, 100);
  assert.deepEqual(GJ.decodeAnswers(GJ.encodeAnswers([1, null, 0]), 3), [1, null, 0]);
});

test('treemap fills the box exactly', () => {
  const r = GJ.treemap([{ v: 6 }, { v: 3 }, { v: 1 }], 100, 50);
  const area = r.reduce((s, x) => s + x.w * x.h, 0);
  assert.ok(Math.abs(area - 5000) < 1e-6);
  assert.equal(r.length, 3);
  r.forEach(x => assert.ok(x.x >= -1e-9 && x.y >= -1e-9 && x.x + x.w <= 100 + 1e-6 && x.y + x.h <= 50 + 1e-6));
});

test('daysAgo / ago', () => {
  const now = Date.parse('2026-09-22T12:00:00Z');
  assert.equal(GJ.daysAgo('2026-09-20', now), 2);
  assert.equal(GJ.ago('2026-09-22', now), 'Today');
  assert.equal(GJ.ago(null, now), '');
});

test('stem meets ecologist / ecology / ecological', () => {
  assert.equal(GJ.stem('ecologist'), GJ.stem('ecology'));
  assert.equal(GJ.stem('ecological'), GJ.stem('ecology'));
  assert.equal(GJ.stem('surveys'), GJ.stem('survey'));
  assert.equal(GJ.stem('wind'), 'wind');
});

test('fitMatch ranks title + place matches first and reports terms', () => {
  const idx = GJ.fitIndex(J);
  const hits = GJ.fitMatch('ecologist dublin', J, idx, 6);
  assert.equal(hits[0].job.id, '1');
  assert.ok(hits[0].terms.indexOf('ecologist') >= 0 && hits[0].terms.indexOf('dublin') >= 0);
  assert.equal(GJ.fitMatch('zzzz qqqq', J, idx, 6).length, 0);
  const bi = GJ.fitMatch('solar project', J, idx, 6);
  assert.equal(bi[0].job.id, '2');
  assert.ok(bi[0].score > GJ.fitMatch('project', J, idx, 6)[0].score, 'the bigram adds weight');
});

test('salaryPosition reports range, disclosure share and percentiles', () => {
  const idx = GJ.fitIndex(J);
  const pos = GJ.salaryPosition(GJ.fitMatch('ecologist water', J, idx, 6), J);
  assert.equal(pos.n, 2);
  assert.equal(pos.disclosed, 2);
  assert.equal(pos.share, 100);
  assert.equal(pos.lo, 55000);
  assert.equal(pos.hi, 65000);
  assert.equal(pos.board.n, 2);
  assert.equal(pos.plo, 0);
  assert.equal(pos.phi, 100);
  const none = GJ.salaryPosition([{ job: J[1] }], J);
  assert.equal(none.disclosed, 0);
  assert.equal(none.lo, null);
});

test('encodeFit / decodeFit round-trip distinct terms', () => {
  const h = GJ.encodeFit('Ecologist, Dublin. Ecologist & EIA chapters');
  assert.equal(h, 'ecologist.dublin.eia.chapters');
  assert.equal(GJ.decodeFit('#fit=' + h), 'ecologist dublin eia chapters');
  assert.equal(GJ.decodeFit('#a=1'), '');
  assert.equal(GJ.decodeFit('#fit=%E0'), '');
});

test('filmScrub holds, travels and fills the rail', () => {
  assert.equal(GJ.filmScrub(0, 4).show, 0);
  assert.equal(GJ.filmScrub(0, 4).g, 0);
  const mid = GJ.filmScrub(0.92 * 0.5 / 4, 4);
  assert.equal(mid.s, 0);
  assert.ok(mid.g > 0 && mid.g < 1);
  assert.equal(GJ.filmScrub(1, 4).show, 4);
  assert.deepEqual(GJ.filmScrub(1, 4).fills, [1, 1, 1, 1, 0]);
  assert.equal(GJ.filmScrub(0.5, 2).show, 1);
});

test('easeOutQuart and countAt', () => {
  assert.equal(GJ.easeOutQuart(0), 0);
  assert.equal(GJ.easeOutQuart(1), 1);
  assert.ok(GJ.easeOutQuart(0.5) > 0.9);
  assert.equal(GJ.countAt(0, 100, 1), 100);
  assert.equal(GJ.countAt(0, 100, 0), 0);
});

/* ---- Keith B/D (2026-09-28): currency, location class, facets */
const K = [
  { id: 'a', title: 'Ecologist', employer: 'Gaia Talent', location: 'Dublin', regions: ['Dublin'], type: 'Permanent', sectors: ['Ecology, nature recovery & biodiversity'], sal_min: 5100, sal_max: 6000, cur: 'EUR', period: 'month', posted: '2026-09-20', closing: '2026-10-03', summary: '', loc_class: 'ie', workplace: 'hybrid', level: 'Mid-level', contract: ['permanent'], agency: true },
  { id: 'b', title: 'Highways Civil Engineer', employer: 'Arup', location: 'London', regions: ['London'], type: 'Permanent', sectors: ['Sustainable infrastructure & transport'], sal_min: 40000, sal_max: 50000, cur: 'GBP', period: 'year', posted: '2026-09-19', closing: '2026-09-25', summary: '', loc_class: 'uk', workplace: 'office', level: 'Mid-level', contract: ['permanent', 'full-time'], agency: false },
  { id: 'c', title: 'Labs Facilitator', employer: 'Commonland', location: 'UK, Ireland', regions: ['Nationwide / remote'], type: 'Contract', sectors: ['Policy, planning & advisory'], sal_min: null, sal_max: null, cur: null, period: null, posted: '2026-09-18', closing: '', summary: '', loc_class: 'cross', workplace: 'remote', level: 'Senior', contract: ['contract', 'part-time'], agency: false },
];
const NOW = Date.parse('2026-09-28T12:00:00Z');

test('salaryLabel never converts the advertised currency; it adds an approximate equivalent', () => {
  assert.equal(GJ.salaryLabel(K[0]), '€5.1k–6k/mo');
  assert.equal(GJ.salaryLabel(K[0], 'EUR'), '€5.1k–6k/mo');
  const uk = GJ.salaryLabel(K[0], 'GBP');
  assert.ok(uk.startsWith('€5.1k–6k/mo (paid in euros, about £'), uk);
  assert.ok(/£4\.4k–5\.1k\/mo\)$/.test(uk), uk);
  assert.equal(GJ.salaryLabel(K[1], 'EUR'), '£40k–50k (paid in sterling, about €46.8k–58.5k)');
  assert.equal(GJ.currencyNote(K[1], 'EUR'), 'Paid in sterling');
  assert.equal(GJ.currencyNote(K[1], 'GBP'), '');
  assert.equal(GJ.FX_GBP_EUR, 1.17);
});

test('annual compares in the edition currency but leaves the label alone', () => {
  assert.equal(GJ.annual(K[1]).mid, 45000);
  assert.ok(Math.abs(GJ.annual(K[1], 'EUR').mid - 45000 * 1.17) < 1e-6);
  assert.ok(Math.abs(GJ.annual(K[0], 'GBP').lo - 5100 * 12 / 1.17) < 1e-6);
  assert.equal(GJ.salaryLabel(K[1], 'EUR').slice(0, 8), '£40k–50k');
});

test('locLabel maps every class', () => {
  assert.deepEqual(['ie', 'uk', 'ni', 'remote', 'cross', 'intl'].map(GJ.locLabel), ['Ireland', 'UK', 'Northern Ireland', 'Remote', 'Ireland & UK', 'International']);
  assert.equal(GJ.locLabel(undefined), '');
});

test('filterJobs: workplace, level, contract, salary range, only-toggle, closing, agency', () => {
  const ids = (st, opts) => GJ.filterJobs(K, st, opts).map(j => j.id);
  assert.deepEqual(ids({ wp: 'remote' }), ['c']);
  assert.deepEqual(ids({ level: 'Senior' }), ['c']);
  assert.deepEqual(ids({ ct: 'part-time' }), ['c']);
  assert.deepEqual(ids({ ct: 'permanent' }), ['a', 'b']);
  assert.deepEqual(ids({ smin: '45000' }, { cur: 'GBP' }), ['a', 'b']);
  assert.deepEqual(ids({ smin: '52000' }, { cur: 'GBP' }), ['a']);
  assert.deepEqual(ids({ smax: '50000' }, { cur: 'EUR' }), ['b']);
  assert.deepEqual(ids({ only: '1' }, { home: ['ie', 'cross', 'remote'] }), ['a', 'c']);
  assert.deepEqual(ids({ only: '1' }, { home: ['uk', 'ni', 'cross', 'remote'] }), ['b', 'c']);
  assert.deepEqual(ids({ close: '7' }, { now: NOW }), ['a']);
  assert.deepEqual(ids({ close: 'open' }, { now: NOW }), ['a', 'c']);
  assert.deepEqual(ids({ emp: 'agency' }), ['a']);
  assert.deepEqual(ids({ emp: 'direct' }), ['b', 'c']);
  assert.deepEqual(ids({}), ['a', 'b', 'c']);
});

test('URL state carries every facet and Clear resets it', () => {
  const st = { wp: 'hybrid', level: 'Senior', ct: 'contract', smin: '30000', smax: '60000', only: '1', close: '14', emp: 'direct', sort: 'newest', view: 'list' };
  const qs = GJ.toQuery(st);
  assert.deepEqual(GJ.parseState(qs), { wp: 'hybrid', level: 'Senior', ct: 'contract', smin: '30000', smax: '60000', only: '1', close: '14', emp: 'direct' });
  assert.equal(GJ.toQuery({ sort: 'newest', view: 'list' }), '');
  assert.equal(GJ.daysUntil('2026-10-03', NOW), 5); /* calendar days: 28 Sep -> 3 Oct */
  assert.equal(GJ.daysUntil('', NOW), null);
});

/* ---- panel fixes A (2026-09-28): build-date rule, any-of sector, currency guard */
test('daysUntil / daysAgo use whole calendar days against the build date', () => {
  assert.equal(GJ.daysUntil('2026-10-05', '2026-09-28'), 7);
  assert.equal(GJ.daysUntil('2026-10-06', '2026-09-28'), 8);
  assert.equal(GJ.daysUntil('2026-09-28', '2026-09-28'), 0);
  assert.equal(GJ.daysUntil('2026-09-27', '2026-09-28'), -1);
  assert.equal(GJ.daysUntil('2026-10-03', Date.parse('2026-09-28T23:59:00Z')), 5, 'a clock value counts UTC days, not 24h blocks');
  assert.equal(GJ.daysAgo('2026-09-20', '2026-09-28'), 8);
  assert.equal(GJ.ago('2026-09-20', '2026-09-28'), '1 wk ago');
  assert.equal(GJ.daysUntil('nonsense', '2026-09-28'), null);
});

test('closingWithin (0..7) and newThisWeek (0..6) mirror build_site', () => {
  const T = '2026-09-28';
  assert.equal(GJ.closingWithin('2026-09-28', 7, T), true);
  assert.equal(GJ.closingWithin('2026-10-05', 7, T), true);
  assert.equal(GJ.closingWithin('2026-10-06', 7, T), false);
  assert.equal(GJ.closingWithin('2026-09-27', 7, T), false);
  assert.equal(GJ.closingWithin('', 7, T), false);
  assert.equal(GJ.newThisWeek('2026-09-28', T), true);
  assert.equal(GJ.newThisWeek('2026-09-22', T), true);
  assert.equal(GJ.newThisWeek('2026-09-21', T), false);
  assert.equal(GJ.newThisWeek('2026-09-29', T), false, 'a future posted date is not new');
});

test('setToday pins the build date for every date helper', () => {
  GJ.setToday('2026-10-01');
  assert.equal(GJ.today(), '2026-10-01');
  assert.equal(GJ.daysUntil('2026-10-03'), 2);
  assert.equal(GJ.ago('2026-10-01'), 'Today');
  assert.deepEqual(GJ.filterJobs(K, { close: '7' }).map(j => j.id), ['a']);
  GJ.setToday(null);
  assert.equal(GJ.today(), null);
});

test('filterJobs sector accepts "|"-joined any-of values (multi-sector landing links)', () => {
  const ids = st => GJ.filterJobs(K, st).map(j => j.id);
  assert.deepEqual(ids({ sector: 'Ecology, nature recovery & biodiversity|Policy, planning & advisory' }), ['a', 'c']);
  assert.deepEqual(ids({ sector: 'Policy, planning & advisory' }), ['c']);
  assert.deepEqual(ids({ sector: 'Nope|Also nope' }), []);
});

test('annual excludes USD and unknown currencies from comparisons; the label still shows them', () => {
  const usd = { sal_min: 50000, sal_max: 60000, cur: 'USD', period: 'year' };
  assert.equal(GJ.annual(usd), null);
  assert.equal(GJ.annual({ sal_min: 50000, sal_max: 60000, period: 'year' }), null);
  assert.equal(GJ.salaryLabel(usd), '$50k–60k');
  assert.deepEqual(GJ.filterJobs([usd].map((j, i) => Object.assign({ id: 'u', title: 'U', posted: '' }, j)), { smin: '10000' }).map(j => j.id), []);
});

test('money rounds half up like Python rnd()', () => {
  assert.equal(GJ.money(32450, 'EUR'), '€32.5k');
  assert.equal(GJ.locLabel('unspecified'), 'Location not stated');
});
