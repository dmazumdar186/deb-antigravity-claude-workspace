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
