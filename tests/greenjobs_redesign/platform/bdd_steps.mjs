// Step definitions for build/features/*.feature, executed against the Worker's fetch with the
// offline fakes from helpers.mjs. `this` is a fresh per-scenario world.

import assert from 'node:assert/strict';
import {
  AUD, DOC_BYTES, PDF_BYTES, adminRequest, applyRequest, docxBytes, makeWorld, seedJob, signToken, validJobBody,
} from './helpers.mjs';

const unescape = (s) => s.replace(/\\r/g, '\r').replace(/\\n/g, '\n').replace(/\\t/g, '\t');
const list = (s) => s.split(',').map((x) => x.trim()).filter(Boolean);

async function remember(world, res) {
  world.res = res;
  world.status = res.status;
  world.headers = res.headers;
  world.text = await res.text();
  try {
    world.data = JSON.parse(world.text);
  } catch {
    world.data = null;
  }
  return world.data;
}

function jobIds(world) {
  assert.ok(world.data && Array.isArray(world.data.jobs), `expected a job list, got ${world.text?.slice(0, 120)}`);
  return world.data.jobs.map((j) => j.id);
}

async function admin(world, method, path, o = {}) {
  let token = null;
  if (world.signedInAs) token = await signToken({ email: world.signedInAs, ...(world.claims || {}) }, world.signOpts || {});
  const req = await adminRequest(method, path, { token, ...o });
  return remember(world, await world.w.fetch(req));
}

async function submit(world, host, extra = {}) {
  const c = world.candidate;
  const fields = { job_id: c.job_id, name: c.name, email: c.email, ts: String(world.w.clock.now.getTime() - (c.renderedAgoMs ?? 60_000)), ...c.fields, ...extra };
  const req = applyRequest(fields, { host, cv: c.cv, cvName: c.cvName, ip: c.ip });
  return remember(world, await world.w.fetch(req));
}

function addJob(world, id, title, site, o = {}) {
  seedJob(world.w, { id, title, site, ...o });
}

export function registerSteps({ Given, When, Then }) {
  // ---------- setup ----------
  Given(/the GreenJobs platform worker with default settings/, async function () {
    this.w = await makeWorld();
  });
  Given(/today is "(\d{4}-\d{2}-\d{2})"/, function (d) {
    this.w.clock.now = new Date(`${d}T10:00:00Z`);
  });
  Given(/the worker setting "([A-Z0-9_]+)" is "([^"]*)"/, function (k, v) {
    this.w.env[k] = v;
  });
  Given(/the staff allow-list is "([^"]*)"/, function (v) {
    this.w.env.STAFF_EMAILS = v;
  });
  Given(/the site inbox for "(ie|uk)" is "([^"]+)"/, function (site, inbox) {
    this.w.env[site === 'ie' ? 'APPLY_INBOX_IE' : 'APPLY_INBOX_UK'] = inbox;
  });

  // ---------- jobs ----------
  Given(/a (live|closed|draft) job "([^"]+)" titled "([^"]+)" on site "(ie|uk)"/, function (status, id, title, site) {
    addJob(this, id, title, site, { status });
  });
  Given(/a live job "([^"]+)" titled "([^"]+)" on site "(ie|uk)" closing "(\d{4}-\d{2}-\d{2})"/, function (id, title, site, d) {
    addJob(this, id, title, site, { closing_at: `${d}T23:59:59Z` });
  });
  Given(/a live job "([^"]+)" titled "([^"]+)" on site "(ie|uk)" with description "([^"]+)"/, function (id, title, site, description) {
    addJob(this, id, title, site, { description });
  });
  Given(/a live job "([^"]+)" titled "([^"]+)" on site "(ie|uk)" with apply email "([^"]+)"/, function (id, title, site, email) {
    addJob(this, id, title, site, { apply_email: email });
  });
  Given(/a live job "([^"]+)" titled "([^"]+)" on site "(ie|uk)" applying via "([^"]+)"/, function (id, title, site, url) {
    addJob(this, id, title, site, { apply_mode: 'url', apply_url: url });
  });

  // ---------- public reads ----------
  When(/a visitor requests "([^"]+)" on host "([^"]+)"/, async function (path, host) {
    await remember(this, await this.w.fetch(new Request(`https://${host}${path}`)));
  });
  When(/a visitor from origin "([^"]+)" requests "([^"]+)" on host "([^"]+)"/, async function (origin, path, host) {
    await remember(this, await this.w.fetch(new Request(`https://${host}${path}`, { headers: { Origin: origin } })));
  });
  When(/a visitor posts to "([^"]+)" on host "([^"]+)"/, async function (path, host) {
    await remember(this, await this.w.fetch(new Request(`https://${host}${path}`, { method: 'POST', body: '{}', headers: { 'Content-Type': 'application/json' } })));
  });
  When(/the static build requests the export for site "(ie|uk)" with token "([^"]*)"/, async function (site, token) {
    await remember(this, await this.w.fetch(new Request(`https://greenjobs.ie/api/export/jobs?site=${site}`, { headers: { Authorization: `Bearer ${token}` } })));
  });
  When(/the static build requests the export for site "(ie|uk)" with the configured token/, async function (site) {
    await remember(this, await this.w.fetch(new Request(`https://greenjobs.ie/api/export/jobs?site=${site}`, { headers: { Authorization: `Bearer ${this.w.env.BUILD_TOKEN}` } })));
  });
  Then(/the job list contains "([^"]+)"/, function (id) {
    assert.ok(jobIds(this).includes(id), `${id} not in ${jobIds(this)}`);
  });
  Then(/the job list does not contain "([^"]+)"/, function (id) {
    assert.ok(!jobIds(this).includes(id), `${id} unexpectedly listed`);
  });
  Then(/the job list on host "([^"]+)" does not contain "([^"]+)"/, async function (host, id) {
    await remember(this, await this.w.fetch(new Request(`https://${host}/api/jobs`)));
    assert.ok(!jobIds(this).includes(id));
  });
  Then(/every listed job has exactly the fields "([^"]+)"/, function (fields) {
    const want = list(fields).sort();
    assert.ok(this.data.jobs.length > 0, 'no jobs listed');
    for (const j of this.data.jobs) assert.deepEqual(Object.keys(j).sort(), want);
  });

  // ---------- generic response checks ----------
  Then(/the response status is (\d{3})/, function (code) {
    assert.equal(this.status, Number(code), `body: ${this.text?.slice(0, 200)}`);
  });
  Then(/the response error is "([^"]+)"/, function (code) {
    assert.equal(this.data?.error, code);
  });
  Then(/the response field "([^"]+)" is "([^"]*)"/, function (k, v) {
    assert.equal(this.data?.[k], v);
  });
  Then(/the response field "([^"]+)" is (\d+|true|false)/, function (k, v) {
    assert.equal(this.data?.[k], v === 'true' ? true : v === 'false' ? false : Number(v));
  });
  Then(/the response field "([^"]+)" does not contain "([^"]+)"/, function (k, s) {
    assert.equal(typeof this.data?.[k], 'string');
    assert.ok(!this.data[k].includes(s), `${k} contains ${s}`);
  });
  Then(/the response lists field "([^"]+)"/, function (f) {
    assert.ok(Array.isArray(this.data?.fields) && this.data.fields.includes(f), `fields: ${JSON.stringify(this.data)}`);
  });
  Then(/the response header "([^"]+)" contains "([^"]+)"/, function (h, s) {
    assert.ok((this.headers.get(h) || '').includes(s), `${h}: ${this.headers.get(h)}`);
  });
  Then(/there (?:is|are) (\d+) audit rows? for action "([^"]+)"/, function (n, action) {
    assert.equal(this.w.db.q('SELECT COUNT(*) AS n FROM audit_log WHERE action = ?1', action)[0].n, Number(n));
  });
  Then(/the audit log does not contain "([^"]+)"/, function (s) {
    const all = this.w.db.q('SELECT detail_json FROM audit_log').map((r) => r.detail_json).join('\n');
    assert.ok(!all.includes(s), 'audit detail holds a value');
  });

  // ---------- staff ----------
  Given(/I am signed in to Cloudflare Access as "([^"]+)"/, function (email) {
    this.signedInAs = email;
  });
  Given(/I am signed in to Cloudflare Access as "([^"]+)" with an? (expired|wrong-audience|wrong-issuer|tampered|unsigned|foreign-key) token/, function (email, defect) {
    this.signedInAs = email;
    const nowS = Math.floor(this.w.clock.now.getTime() / 1000);
    ({
      expired: () => (this.claims = { exp: nowS - 600 }),
      'wrong-audience': () => (this.claims = { aud: [`${AUD}-other`] }),
      'wrong-issuer': () => (this.claims = { iss: 'https://evil.cloudflareaccess.com' }),
      tampered: () => (this.signOpts = { tamper: true }),
      unsigned: () => (this.signOpts = { alg: 'none' }),
      'foreign-key': () => (this.signOpts = { wrongKey: true }),
    })[defect]();
  });
  Given(/I am not signed in/, function () {
    this.signedInAs = null;
  });
  When(/I request the admin job list/, async function () {
    await admin(this, 'GET', '/api/admin/jobs');
  });
  When(/I request the admin job list (\d+) times/, async function (n) {
    for (let i = 0; i < Number(n); i++) await admin(this, 'GET', '/api/admin/jobs');
  });
  When(/I open the console/, async function () {
    await admin(this, 'GET', '/admin/');
  });
  Then(/the page has no inline script/, function () {
    assert.doesNotMatch(this.text, /<script(?![^>]*\bsrc=)[^>]*>/);
    assert.doesNotMatch(this.text, /\son[a-z]+=/i);
  });

  const create = async (world, over = {}, o = {}) => {
    const data = await admin(world, 'POST', '/api/admin/jobs', { body: validJobBody(over), ...o });
    if (data?.id) world.createdId = data.id;
    return data;
  };
  When(/I create a job titled "([^"]+)" for employer "([^"]+)" in "([^"]+)"/, async function (title, employer, location) {
    await create(this, { title, employer, location });
  });
  When(/I create a job titled "([^"]+)" with idempotency key "([0-9a-f-]+)"/, async function (title, idem) {
    await create(this, { title }, { idem });
  });
  Given(/I have created a job titled "([^"]+)"/, async function (title) {
    await create(this, { title });
    assert.equal(this.status, 201);
  });
  When(/I create a job from origin "([^"]+)"/, async function (origin) {
    await create(this, {}, { origin });
  });
  When(/I create a job without an idempotency key/, async function () {
    await create(this, {}, { idem: null });
  });
  When(/I create an external-apply job with apply URL "([^"]+)"/, async function (url) {
    await create(this, { apply_mode: 'url', apply_url: url });
  });
  When(/I edit the created job setting title to "([^"]+)" at version (\d+)/, async function (title, v) {
    await admin(this, 'PUT', `/api/admin/jobs/${encodeURIComponent(this.createdId)}`, { body: { title, version: Number(v) } });
  });
  When(/I edit job "([^"]+)" setting title to "([^"]+)" at version (\d+)/, async function (id, title, v) {
    await admin(this, 'PUT', `/api/admin/jobs/${id}`, { body: { title, version: Number(v) } });
  });
  When(/I close job "([^"]+)"/, async function (id) {
    await admin(this, 'POST', `/api/admin/jobs/${id}/close`, { body: {} });
  });
  Then(/the created job id matches "([^"]+)"/, function (re) {
    assert.match(this.createdId, new RegExp(re));
  });
  Then(/the created job is listed on host "([^"]+)"/, async function (host) {
    const id = this.createdId;
    await remember(this, await this.w.fetch(new Request(`https://${host}/api/jobs`)));
    assert.ok(jobIds(this).includes(id));
  });
  Then(/the created job is titled "([^"]+)"/, function (title) {
    assert.equal(this.w.db.q('SELECT title FROM jobs WHERE id = ?1', this.createdId)[0].title, title);
  });
  Then(/there are (\d+) jobs stored/, function (n) {
    assert.equal(this.w.db.q('SELECT COUNT(*) AS n FROM jobs')[0].n, Number(n));
  });

  // ---------- applications ----------
  Given(/a candidate "([^"]+)" with email "([^"]+)" applying to job "([^"]+)"/, function (name, email, jobId) {
    this.candidate = { name, email, job_id: jobId, fields: {} };
  });
  Given(/the candidate is applying to job "([^"]+)"/, function (jobId) {
    this.candidate.job_id = jobId;
  });
  Given(/the candidate's name is "([^"]+)"/, function (name) {
    this.candidate.name = unescape(name);
  });
  Given(/the candidate has not ticked consent/, function () {
    this.candidate.fields.consent = undefined;
  });
  Given(/the candidate fills the hidden "([a-z_]+)" field with "([^"]*)"/, function (f, v) {
    this.candidate.fields[f] = v;
  });
  Given(/the form was rendered (\d+) seconds ago/, function (s) {
    this.candidate.renderedAgoMs = Number(s) * 1000;
  });
  const CV = { pdf: () => PDF_BYTES, doc: () => DOC_BYTES, docx: () => docxBytes() };
  Given(/the candidate attaches a "(pdf|doc|docx)" CV/, function (t) {
    this.candidate.cv = CV[t]();
  });
  Given(/the candidate attaches a "(pdf|doc|docx)" CV named "([^"]+)"/, function (t, name) {
    this.candidate.cv = CV[t]();
    this.candidate.cvName = name;
  });
  Given(/the candidate attaches a CV of (\d+) bytes/, function (n) {
    const b = new Uint8Array(Number(n));
    b.set(PDF_BYTES);
    this.candidate.cv = b;
  });
  Given(/the candidate attaches an executable named "([^"]+)"/, function (name) {
    this.candidate.cv = new Uint8Array([0x4d, 0x5a, 0x90, 0x00, 0x03, 0x00, 0x00, 0x00]);
    this.candidate.cvName = name;
  });
  When(/the candidate submits the application on host "([^"]+)"/, async function (host) {
    await submit(this, host);
  });
  When(/the candidate submits the application again with email "([^"]+)"/, async function (email) {
    await submit(this, 'greenjobs.ie', { email });
  });
  When(/(\d+) different candidates apply from IP "([^"]+)" on host "([^"]+)"/, async function (n, ip, host) {
    this.candidate.ip = ip;
    for (let i = 0; i < Number(n); i++) await submit(this, host, { email: `candidate${i}@example.ie` });
  });
  Then(/(\d+) applications? (?:is|are) stored/, function (n) {
    assert.equal(this.w.db.q('SELECT COUNT(*) AS n FROM applications')[0].n, Number(n));
  });
  Then(/(\d+) applications? (?:is|are) stored routed to "([^"]+)"/, function (n, to) {
    const rows = this.w.db.q('SELECT routed_to FROM applications');
    assert.equal(rows.length, Number(n));
    for (const r of rows) assert.equal(r.routed_to, to);
  });
  Then(/the application delivery status is "([^"]+)"/, function (s) {
    assert.deepEqual(this.w.db.q('SELECT delivery_status FROM applications').map((r) => r.delivery_status), [s]);
  });
  Then(/no email is sent/, function () {
    assert.equal(this.w.mail.calls.length, 0);
  });
  Then(/(\d+) emails? (?:is|are) sent to "([^"]+)"/, function (n, to) {
    assert.equal(this.w.mail.calls.length, Number(n));
    for (const c of this.w.mail.calls) assert.deepEqual(c.payload.to, [to]);
  });
  Then(/the email reply-to is "([^"]+)"/, function (addr) {
    assert.equal(this.w.mail.calls.at(-1).payload.reply_to, addr);
  });
  Then(/the spend ledger shows (\d+) sends/, function (n) {
    assert.equal(this.w.db.q("SELECT COUNT(*) AS n FROM audit_log WHERE action = 'mail.send'")[0].n, Number(n));
  });
  Then(/no CV is stored/, function () {
    assert.equal(this.w.r2.objects.size, 0);
  });
  Then(/the stored CV key matches "([^"]+)"/, function (re) {
    const keys = [...this.w.r2.objects.keys()];
    assert.equal(keys.length, 1);
    assert.match(keys[0], new RegExp(re));
  });
}
