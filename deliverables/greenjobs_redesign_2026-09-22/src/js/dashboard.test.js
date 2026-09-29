'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const D = require('./dashboard.js');

test('csvCell quotes commas, quotes and newlines only when needed', () => {
  assert.equal(D.csvCell('plain'), 'plain');
  assert.equal(D.csvCell('a,b'), '"a,b"');
  assert.equal(D.csvCell('say "hi"'), '"say ""hi"""');
  assert.equal(D.csvCell(null), '');
  assert.equal(D.csvCell(42), '42');
});

test('toCsv joins rows with CRLF and a trailing newline', () => {
  assert.equal(D.toCsv([['a', 'b'], [1, 'x,y']]), 'a,b\r\n1,"x,y"\r\n');
});

test('kpiRows flattens the payload with a header and every sector, region and score', () => {
  const k = { live: 3, new7: 1, closing7: 0, sal_pct: 33, sal_n: 1, sal_median: 60000, top_share: 67, top_employer: 'A', agency_pct: 0,
    days_to_close: 30, remote_pct: 33, sectors: [{ l: 'Water', v: 2 }], regions: [{ l: 'Cork', v: 1 }, { l: 'Dublin', v: 2 }], quality: [0, 1, 1, 1, 0] };
  const rows = D.kpiRows(k, '€');
  assert.deepEqual(rows[0], ['metric', 'value', 'how we measure it']);
  assert.equal(rows.length, 1 + 9 + 1 + 2 + 5);
  assert.deepEqual(rows[5], ['Median disclosed salary', '€60000', 'median of annualised midpoints']);
  assert.ok(rows.some(r => r[0] === 'Region: Dublin' && r[1] === 2));
  assert.equal(D.kpiRows({ ...k, sal_median: null, days_to_close: null }, '£')[5][1], '');
});

test('csvCell neutralises spreadsheet formula prefixes', () => {
  assert.equal(D.csvCell('=SUM(A1)'), "'=SUM(A1)");
  assert.equal(D.csvCell('+1'), "'+1");
  assert.equal(D.csvCell('-5'), "'-5");
  assert.equal(D.csvCell('@cmd'), "'@cmd");
  assert.equal(D.csvCell('=a,b'), '"\'=a,b"');
  assert.equal(D.csvCell(-5), "'-5");
});

test('kpiRows labels the advertised window and describes the agency rule', () => {
  const k = { live: 1, new7: 0, closing7: 0, sal_pct: 0, sal_n: 0, sal_median: null, top_share: 100, top_employer: 'A', agency_pct: 0, days_to_close: 12, remote_pct: 0, sectors: [], regions: [], quality: [1, 0, 0, 0, 0] };
  const rows = D.kpiRows(k, '€');
  assert.ok(rows.some(r => r[0] === 'Advertised window, days' && r[1] === 12));
  assert.ok(!rows.some(r => r[0] === 'Median days to close'));
  assert.ok(rows.find(r => r[0] === 'Agency share %')[2].includes('recruit/talent/staffing'));
});
