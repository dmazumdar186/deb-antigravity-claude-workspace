'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const L = require('./live.js');
const D = require('./dashboard.js');

const STATS = {
  site: 'ie',
  salary: { n_jobs: 12, n_disc: 9, disc_pct: 75, median: '€48k', bands: [] },
  sectors: [{ name: 'Wind energy', n: 1, stat: 'no disclosed salaries yet' }, { name: 'Water & flood', n: 4, stat: 'median disclosed €52k' }],
};

test('liveValues maps /api/stats onto the [data-live] keys; a bad payload maps to null', () => {
  assert.deepEqual(L.liveValues(STATS), { n_jobs: '12', n_disc: '9', disc_pct: '75', median: '€48k' });
  assert.equal(L.liveValues(null), null);
  assert.equal(L.liveValues({}), null);
});

test('sectorCaption matches build_site.sector_tiles wording', () => {
  assert.equal(L.sectorCaption({ n: 1, stat: 'no disclosed salaries yet' }), 'role · no disclosed salaries yet');
  assert.equal(L.sectorCaption({ n: 4, stat: 'median disclosed €52k' }), 'roles · median disclosed €52k');
});

test('apply replaces values in place (text, data-count, sector tiles) and leaves unknown keys alone', () => {
  const mk = (attrs) => {
    const el = { attrs: { ...attrs }, textContent: 'old', getAttribute: (k) => el.attrs[k], hasAttribute: (k) => k in el.attrs, setAttribute: (k, v) => { el.attrs[k] = v; } };
    return el;
  };
  const a = mk({ 'data-live': 'n_jobs' });
  const b = mk({ 'data-live': 'n_disc', 'data-count': '1' });
  const c = mk({ 'data-live': 'unknown' });
  const textNode = { nodeType: 3, nodeValue: '7' };
  const small = { textContent: 'roles · x' };
  const p = { firstChild: textNode, querySelector: () => small };
  const tile = { getAttribute: () => 'Water & flood', querySelector: () => p };
  const doc = { querySelectorAll: (sel) => (sel === '[data-live]' ? [a, b, c] : [tile]) };
  assert.equal(L.apply(doc, STATS), 3);
  assert.equal(a.textContent, '12');
  assert.equal(b.textContent, '9');
  assert.equal(b.attrs['data-count'], '9');
  assert.equal(c.textContent, 'old');
  assert.equal(textNode.nodeValue, '4');
  assert.equal(small.textContent, 'roles · median disclosed €52k');
  assert.equal(L.apply(doc, null), 0);
});

test('dashboard tileTexts follows render_dashboard order and format; measures null show the dash', () => {
  const k = { live: 8, new7: 3, closing7: 1, sal_pct: 88, days_to_close: null, remote_pct: 25, top_share: 25, agency_pct: 0 };
  assert.deepEqual(D.tileTexts(k), ['8', '3', '1', '88%', 'n/a', '25%', '25%', '0%']);
  assert.equal(D.measureText(null), '—');
  assert.equal(D.measureText(14), '14');
});

test('dashboard fetchStats falls back to null without fetch, for a wrong site, or on timeout', async () => {
  assert.equal(await D.fetchStats('fr', 10), null);
  const saved = global.fetch;
  global.fetch = () => new Promise(() => {});
  try {
    assert.equal(await D.fetchStats('ie', 10), null);
    global.fetch = async () => ({ ok: true, json: async () => ({ site: 'uk', kpis: {} }) });
    assert.equal(await D.fetchStats('ie', 1000), null, 'a payload for the other edition is ignored');
    global.fetch = async () => ({ ok: true, json: async () => ({ site: 'ie', kpis: { live: 1 } }) });
    assert.deepEqual((await D.fetchStats('ie', 1000)).kpis, { live: 1 });
  } finally {
    global.fetch = saved;
  }
});
