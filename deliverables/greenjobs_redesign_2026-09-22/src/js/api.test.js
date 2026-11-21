'use strict';
/* api.js: live job set paging + cache, and the alert / newsletter sign-up forms (flag off posts nothing,
   flag on posts JSON with the honeypot, accessible field errors). Run: node --test api.test.js */
const test = require('node:test');
const assert = require('node:assert/strict');
const A = require('./api.js');

const attrs = (o) => ({ getAttribute: (k) => (k in o ? o[k] : null) });

test('apiBase: no API without data-live-api="1"; same origin by default; only an https origin is used as a base', () => {
  assert.equal(A.apiBase(attrs({ 'data-live-api': '0', 'data-api-base': 'https://w.example' })), null);
  assert.equal(A.apiBase(attrs({ 'data-live-api': '1', 'data-api-base': '' })), '');
  assert.equal(A.apiBase(attrs({ 'data-live-api': '1', 'data-api-base': 'https://greenjobs-platform-staging.x.workers.dev' })), 'https://greenjobs-platform-staging.x.workers.dev');
  assert.equal(A.apiBase(attrs({ 'data-live-api': '1', 'data-api-base': 'javascript:alert(1)' })), '');
  assert.equal(A.apiBase(attrs({ 'data-live-api': '1', 'data-api-base': 'http://plain.example' })), '');
});

function pager(pages) {
  const calls = [];
  const fetchFn = async (url) => {
    calls.push(url);
    const after = new URL(url).searchParams.get('after');
    const p = pages[after || ''];
    return p ? { ok: true, status: 200, json: async () => p } : { ok: false, status: 400, json: async () => ({}) };
  };
  return { calls, fetchFn };
}
const FACETS = { sectors: [{ name: 'Wind energy', n: 3 }], regions: [], types: [], contracts: [] };

test('loadJobs follows next until null and returns the whole set; rejects a changed set, a loop, a short set, a bad page', async () => {
  const ok = pager({
    '': { site: 'ie', today: '2026-11-20', total: 3, facets: FACETS, jobs: [{ id: 'a' }, { id: 'b' }], next: 'b' },
    b: { site: 'ie', today: '2026-11-20', total: 3, jobs: [{ id: 'c' }], next: null },
  });
  const r = await A.loadJobs(ok.fetchFn, 'https://w.example', 'ie', { limit: 2, text: false });
  assert.deepEqual(r.jobs.map((j) => j.id), ['a', 'b', 'c']);
  assert.equal(ok.calls[0], 'https://w.example/api/jobs?view=board&site=ie&limit=2&text=0');
  assert.match(ok.calls[1], /&after=b$/);
  const changed = pager({ '': { site: 'ie', total: 3, facets: FACETS, jobs: [{ id: 'a' }], next: 'a' }, a: { site: 'ie', total: 4, jobs: [{ id: 'b' }], next: null } });
  await assert.rejects(A.loadJobs(changed.fetchFn, 'https://w.example', 'ie'), /changed/);
  const loop = pager({ '': { site: 'ie', total: 9, facets: FACETS, jobs: [{ id: 'a' }], next: 'a' }, a: { site: 'ie', total: 9, jobs: [{ id: 'b' }], next: 'a' } });
  await assert.rejects(A.loadJobs(loop.fetchFn, 'https://w.example', 'ie'), /loop/);
  const short = pager({ '': { site: 'ie', total: 5, facets: FACETS, jobs: [{ id: 'a' }], next: null } });
  await assert.rejects(A.loadJobs(short.fetchFn, 'https://w.example', 'ie'), /incomplete/);
  const wrongSite = pager({ '': { site: 'uk', total: 0, facets: FACETS, jobs: [], next: null } });
  await assert.rejects(A.loadJobs(wrongSite.fetchFn, 'https://w.example', 'ie'), /bad page/);
  const http = pager({});
  await assert.rejects(A.loadJobs(http.fetchFn, 'https://w.example', 'ie'), /HTTP 400/);
  // ceiling: a server that never ends stops at MAX_PAGES
  let n = 0;
  const endless = async () => ({ ok: true, json: async () => ({ site: 'ie', total: 1e9, facets: FACETS, jobs: [{ id: `x${n}` }], next: `x${n++}` }) });
  await assert.rejects(A.loadJobs(endless, '', 'ie'), /too many pages/);
  assert.equal(n, A.MAX_PAGES);
});

test('merge keeps the static href/logo for jobs the build has, links newer jobs to the API origin, keeps edition fields', () => {
  const stat = { today: '2026-11-01', currency: 'EUR', jobsHref: 'index.html', jobs: [{ id: '1', href: '1/index.html', logo: 'L.png', lw: 10, lh: 5 }], sectors: [], regions: [] };
  const live = { today: '2026-11-20', facets: { sectors: [{ name: 'S', n: 2 }], regions: [{ name: 'Cork', n: 2, on_map: true }], types: [], contracts: [] },
    jobs: [{ id: 'gj-9', href: '/ie/jobs/gj-9/', logo: '' }, { id: '1', href: '/ie/jobs/1/', logo: '' }] };
  const d = A.merge(stat, live, 'https://w.example');
  assert.equal(d.today, '2026-11-20');
  assert.equal(d.currency, 'EUR');
  assert.equal(d.jobs[0].href, 'https://w.example/ie/jobs/gj-9/');
  assert.deepEqual([d.jobs[1].href, d.jobs[1].logo, d.jobs[1].lw], ['1/index.html', 'L.png', 10]);
  assert.equal(d.sectors[0].n, 2);
  assert.equal(d.live, true);
});

test('cache: at most five minutes, corrupt entries ignored', () => {
  const m = new Map();
  const store = { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, v) };
  A.cachePut(store, 'k', 1000, { a: 1 });
  assert.deepEqual(A.cacheGet(store, 'k', 1000 + A.TTL_MS), { a: 1 });
  assert.equal(A.cacheGet(store, 'k', 1001 + A.TTL_MS), null);
  assert.equal(A.cacheGet(store, 'k', 999), null); // clock went backwards
  m.set('k', '{not json');
  assert.equal(A.cacheGet(store, 'k', 1000), null);
  assert.equal(A.TTL_MS, 300000);
});

test('outcome: every Worker answer maps to a plain message; invalid email marks the field', () => {
  assert.equal(A.outcome('alerts', 202, { ok: true }).ok, true);
  assert.match(A.outcome('alerts', 202, {}).text, /confirm/);
  assert.equal(A.outcome('alerts', 400, { error: 'invalid_email' }).field, 'email');
  assert.match(A.outcome('alerts', 429, { error: 'rate_limited' }).text, /10 minutes/);
  assert.match(A.outcome('newsletter', 503, { error: 'try_later' }).text, /try again later/);
  const soon = A.outcome('alerts', 404, { error: 'not_found' });
  assert.equal(soon.soon, true);
  assert.match(soon.text, /coming soon[\s\S]*Your address has not been stored\./);
  assert.deepEqual(A.payload('alerts', { email: ' a@b.ie ', sector: 'Wind energy', website: '' }), { email: 'a@b.ie', consent: true, website: '', sectors: ['Wind energy'] });
  assert.deepEqual(A.payload('newsletter', { email: 'a@b.ie', sector: 'x' }), { email: 'a@b.ie', consent: true, website: '' });
});

/* A minimal DOM: one sign-up form with the elements the templates render. */
function fakePage({ kind = 'alerts', live = '1', base = 'https://w.example', email = 'ann@example.com', valid = true, newsletter = false } = {}) {
  const el = (extra = {}) => {
    const a = {};
    const cls = new Set();
    return Object.assign({ hidden: true, textContent: '', value: '', disabled: false, checked: false, focused: false,
      setAttribute: (k, v) => { a[k] = String(v); }, getAttribute: (k) => (k in a ? a[k] : null), removeAttribute: (k) => { delete a[k]; },
      hasAttribute: (k) => k in a, focus() { this.focused = true; }, classList: { toggle: (c, on) => (on ? cls.add(c) : cls.delete(c)), has: (c) => cls.has(c) } }, extra);
  };
  const input = el({ value: email, checkValidity: () => valid });
  const parts = { '[data-signup-status]': el(), 'input[type="email"]': input, '[data-signup-error]': el(), '[data-signup-newsletter]': el({ checked: newsletter }),
    '[type="submit"]': el(), '[name="website"]': el({ value: '' }), '[name="sector"]': el({ value: kind === 'alerts' ? 'Wind energy' : '' }) };
  let onSubmit = null;
  const form = el({ querySelector: (s) => parts[s] || null, addEventListener: (ev, fn) => { if (ev === 'submit') onSubmit = fn; } });
  form.setAttribute('data-signup', kind);
  const doc = { body: attrs({ 'data-live-api': live, 'data-api-base': base, 'data-edition': 'uk' }), querySelectorAll: () => [form] };
  return { doc, form, parts, input, submit: () => onSubmit({ preventDefault() {} }) };
}
function fakeApi(flags, answers = {}) {
  const calls = [];
  const fetchFn = async (url, init = {}) => {
    calls.push({ url, init });
    if (url.includes('/api/config')) return flags === 'down' ? { ok: false, status: 500, json: async () => ({}) } : { ok: true, status: 200, json: async () => flags };
    const path = new URL(url).pathname;
    const [status, body] = answers[path] || [202, { ok: true, next: 'check_email' }];
    return { ok: status < 300, status, json: async () => body };
  };
  return { calls, fetchFn, posts: () => calls.filter((c) => c.init.method === 'POST') };
}

test('flag off (or config unreachable, or no API on the page): "coming soon" and NOTHING is posted', async () => {
  for (const [flags, live] of [[{ site: 'uk', alerts: false, newsletter: false }, '1'], ['down', '1'], [{ alerts: true }, '0']]) {
    const p = fakePage({ live });
    const api = fakeApi(flags);
    await A.initForms(p.doc, api.fetchFn);
    assert.equal(p.form.hasAttribute('data-signup-off'), true);
    await p.submit();
    assert.equal(api.posts().length, 0, JSON.stringify(flags));
    assert.equal(p.parts['[data-signup-status]'].hidden, false);
    assert.match(p.parts['[data-signup-status]'].textContent, /coming soon/);
    assert.match(p.parts['[data-signup-status]'].textContent, /Your address has not been stored\./);
  }
});

test('flag on: one JSON POST to the API origin with ?site=, consent and the honeypot; 202 says check your inbox', async () => {
  const p = fakePage();
  const api = fakeApi({ site: 'uk', alerts: true, newsletter: true });
  await A.initForms(p.doc, api.fetchFn);
  await p.submit();
  const [c] = api.posts();
  assert.equal(api.posts().length, 1);
  assert.equal(c.url, 'https://w.example/api/alerts?site=uk');
  assert.equal(c.init.headers['Content-Type'], 'application/json');
  assert.equal(c.init.credentials, 'omit');
  assert.deepEqual(JSON.parse(c.init.body), { email: 'ann@example.com', consent: true, website: '', sectors: ['Wind energy'] });
  assert.match(p.parts['[data-signup-status]'].textContent, /Check your inbox/);
  assert.equal(p.parts['[type="submit"]'].disabled, false);
});

test('flag on: the "newsletter too" box posts a second, separate double opt-in only when the newsletter flag is on', async () => {
  const p = fakePage({ newsletter: true });
  const api = fakeApi({ alerts: true, newsletter: true });
  await A.initForms(p.doc, api.fetchFn);
  await p.submit();
  assert.deepEqual(api.posts().map((c) => new URL(c.url).pathname), ['/api/alerts', '/api/newsletter']);
  const q = fakePage({ newsletter: true });
  const api2 = fakeApi({ alerts: true, newsletter: false });
  await A.initForms(q.doc, api2.fetchFn);
  await q.submit();
  assert.deepEqual(api2.posts().map((c) => new URL(c.url).pathname), ['/api/alerts']);
  assert.match(q.parts['[data-signup-status]'].textContent, /newsletter is coming soon/);
});

test('accessible errors: an invalid address is caught before posting (aria-invalid, message, focus); the Worker\'s invalid_email too', async () => {
  const p = fakePage({ email: 'not-an-email', valid: false });
  const api = fakeApi({ alerts: true });
  await A.initForms(p.doc, api.fetchFn);
  await p.submit();
  assert.equal(api.posts().length, 0);
  assert.equal(p.input.getAttribute('aria-invalid'), 'true');
  assert.equal(p.input.focused, true);
  assert.equal(p.parts['[data-signup-error]'].hidden, false);
  assert.match(p.parts['[data-signup-error]'].textContent, /valid email/);
  const q = fakePage();
  const api2 = fakeApi({ alerts: true }, { '/api/alerts': [400, { error: 'invalid_email' }] });
  await A.initForms(q.doc, api2.fetchFn);
  await q.submit();
  assert.equal(q.input.getAttribute('aria-invalid'), 'true');
  const r = fakePage();
  const api3 = fakeApi({ alerts: true }, { '/api/alerts': [429, { error: 'rate_limited' }] });
  await A.initForms(r.doc, api3.fetchFn);
  await r.submit();
  assert.match(r.parts['[data-signup-status]'].textContent, /10 minutes/);
  assert.equal(r.parts['[data-signup-status]'].classList.has('is-err'), true);
  assert.equal(r.input.getAttribute('aria-invalid'), null, 'a rate limit is not a field error');
});

/* ---- eye review r2 N1/N2: the apply form posts to the edition's API base and shows per-field errors */
test('applyUrl: staging posts to the Worker origin with ?site=, production to the board host, the demo to its action', () => {
  const body = (live, base) => attrs({ 'data-live-api': live, 'data-api-base': base });
  assert.equal(A.applyUrl(body('1', 'https://greenjobs-platform-staging.x.workers.dev'), 'uk', '/api/apply'), 'https://greenjobs-platform-staging.x.workers.dev/api/apply?site=uk');
  assert.equal(A.applyUrl(body('1', ''), 'ie', '/api/apply'), '/api/apply');
  assert.equal(A.applyUrl(body('0', ''), 'ie', '/api/apply'), '/api/apply');
  assert.equal(A.applyUrl(body('1', 'javascript:x'), 'ie', '/api/apply'), '/api/apply', 'a non-https base is never used');
});

test('applyOutcome: received / duplicate are success; invalid_input marks fields; CV and limits are plain messages', () => {
  assert.equal(A.applyOutcome(201, { ok: true, status: 'received' }).ok, true);
  assert.match(A.applyOutcome(201, {}).text, /^Application received/);
  const dup = A.applyOutcome(200, { ok: true, status: 'already_received' });
  assert.equal(dup.ok, true); assert.match(dup.text, /^Application received/);
  const bad = A.applyOutcome(400, { error: 'invalid_input', fields: ['email', 'consent'] });
  assert.equal(bad.ok, false); assert.deepEqual(Object.keys(bad.fields), ['email', 'consent']);
  assert.match(A.applyOutcome(502, { error: 'delivery_failed' }).text, /try again in a few minutes/);
  assert.equal(A.applyOutcome(503, { error: 'cv_storage_unavailable' }).fields, undefined, 'eye r3 R3-1: no CV storage message left');
  assert.match(A.applyOutcome(429, { error: 'rate_limited' }).text, /10 minutes/);
  assert.match(A.applyOutcome(405, {}).text, /Not sent \(error 405\)/);
  assert.match(A.applyOutcome(400, { error: 'too_fast' }).text, /reload/);
});

function fakeApplyPage({ base = 'https://w.example', name = 'Ann', email = 'ann@example.com', valid = true, consent = true } = {}) {
  const el = (extra = {}) => {
    const a = {};
    const cls = new Set();
    return Object.assign({ hidden: true, textContent: '', value: '', disabled: false, checked: false, focused: false,
      setAttribute: (k, v) => { a[k] = String(v); }, getAttribute: (k) => (k in a ? a[k] : null), removeAttribute: (k) => { delete a[k]; },
      hasAttribute: (k) => k in a, focus() { this.focused = true; }, classList: { toggle: (c, on) => (on ? cls.add(c) : cls.delete(c)), has: (c) => cls.has(c) } }, extra);
  };
  const fields = { name: el({ value: name }), email: el({ value: email, checkValidity: () => valid }), consent: el({ checked: consent }), phone: el(), cover_note: el(), cv: el() };
  const errs = {};
  for (const k of Object.keys(fields)) { errs[k] = el(); errs[k].setAttribute('data-apply-err', k); }
  const parts = { '[data-apply-status]': el(), '[type="submit"]': el() };
  let onSubmit = null;
  const form = el({
    querySelector: (s) => {
      const m = /^\[name="(\w+)"\]$/.exec(s) || /^\[data-apply-err="(\w+)"\]$/.exec(s);
      if (m) return (s.startsWith('[name') ? fields : errs)[m[1]] || null;
      return parts[s] || null;
    },
    querySelectorAll: (s) => (s === '[data-apply-err]' ? Object.values(errs) : []),
    addEventListener: (ev, fn) => { if (ev === 'submit') onSubmit = fn; },
  });
  form.setAttribute('action', '/api/apply');
  const doc = { body: attrs({ 'data-live-api': '1', 'data-api-base': base, 'data-edition': 'uk' }), querySelectorAll: (s) => (s === 'form[data-apply-form]' ? [form] : []) };
  return { doc, form, fields, errs, status: parts['[data-apply-status]'], submit: () => onSubmit({ preventDefault() {} }) };
}
const FD = function (f) { this.form = f; };

test('initApply: a valid form POSTs once to the Worker origin (not the Pages origin), cross-origin without credentials', async () => {
  const p = fakeApplyPage();
  const calls = [];
  A.initApply(p.doc, async (url, init) => { calls.push({ url, init }); return { status: 201, json: async () => ({ ok: true, status: 'received', delivery: 'dry_run' }) }; }, FD);
  assert.equal(p.form.noValidate, true);
  await p.submit();
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, 'https://w.example/api/apply?site=uk');
  assert.equal(calls[0].init.method, 'POST');
  assert.equal(calls[0].init.credentials, 'omit');
  assert.equal(calls[0].init.referrerPolicy, 'strict-origin-when-cross-origin');
  assert.match(p.status.textContent, /^Application received/);
  assert.equal(p.status.classList.has('is-err'), false);
});

test('initApply: missing name / bad email / no consent are marked on their fields and nothing is posted', async () => {
  const p = fakeApplyPage({ name: ' ', valid: false, consent: false });
  const calls = [];
  A.initApply(p.doc, async (url) => { calls.push(url); return { status: 201, json: async () => ({}) }; }, FD);
  await p.submit();
  assert.equal(calls.length, 0);
  for (const k of ['name', 'email', 'consent']) {
    assert.equal(p.fields[k].getAttribute('aria-invalid'), 'true', k);
    assert.equal(p.errs[k].hidden, false, k);
  }
  assert.equal(p.fields.name.focused, true, 'focus moves to the first invalid field');
  assert.equal(p.status.classList.has('is-err'), true);
});

test('initApply: a Worker invalid_input answer marks the named field; a 405 is shown as an error, never as success', async () => {
  const p = fakeApplyPage();
  A.initApply(p.doc, async () => ({ status: 400, json: async () => ({ error: 'invalid_input', fields: ['phone'] }) }), FD);
  await p.submit();
  assert.equal(p.fields.phone.getAttribute('aria-invalid'), 'true');
  const q = fakeApplyPage();
  A.initApply(q.doc, async () => ({ status: 405, json: async () => { throw new Error('not json'); } }), FD);
  await q.submit();
  assert.equal(q.status.classList.has('is-err'), true);
  assert.doesNotMatch(q.status.textContent, /received/);
});

test('eye r3 R3-3: after "Application received" the form is reset (render stamp kept), the button is done, the sticky bar updates', async () => {
  const p = fakeApplyPage();
  const ts = { value: '1763700000000' };
  const sticky = { textContent: 'Apply now', attrs: {}, cls: new Set(), setAttribute(k, v) { this.attrs[k] = v; }, classList: { add(c) { sticky.cls.add(c); } } };
  const bar = { cls: new Set(), classList: { add(c) { bar.cls.add(c); } } };
  let resets = 0;
  p.form.reset = () => { resets++; ts.value = ''; p.fields.name.value = ''; };
  const q = p.form.querySelector;
  p.form.querySelector = (s) => (s === '[data-apply-ts]' ? ts : q(s));
  const qa = p.doc.querySelectorAll;
  p.doc.querySelectorAll = (s) => (s === '[data-sticky-apply] a[data-apply]' ? [sticky] : qa(s));
  p.doc.querySelector = (s) => (s === '[data-sticky-apply]' ? bar : null);
  A.initApply(p.doc, async () => ({ status: 201, json: async () => ({ ok: true, status: 'received' }) }), FD);
  await p.submit();
  assert.equal(resets, 1, 'form reset once');
  assert.equal(p.fields.name.value, '');
  assert.equal(ts.value, '1763700000000', 'the render stamp survives the reset');
  const btn = p.form.querySelector('[type="submit"]');
  assert.equal(btn.disabled, true);
  assert.equal(btn.textContent, 'Application sent');
  assert.equal(sticky.textContent, 'Application sent');
  assert.ok(sticky.cls.has('is-done') && bar.cls.has('is-applied'));
  assert.match(p.status.textContent, /^Application received/);
  // a failed send leaves the form as it was, button enabled
  const f2 = fakeApplyPage();
  let r2 = 0;
  f2.form.reset = () => { r2++; };
  A.initApply(f2.doc, async () => ({ status: 429, json: async () => ({ error: 'rate_limited' }) }), FD);
  await f2.submit();
  assert.equal(r2, 0);
  assert.equal(f2.form.querySelector('[type="submit"]').disabled, false);
});
