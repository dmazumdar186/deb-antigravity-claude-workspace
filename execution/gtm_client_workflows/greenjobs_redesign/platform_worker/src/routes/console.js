// Staff console: one form that posts to IE, UK or both; sector / region / type / workplace are dropdowns
// from the frozen taxonomy.json (rendered server-side, so no inline data or script); every field stays
// editable after posting; Close asks for confirmation; a closed job can be reopened; after Save the
// console links to the live page. No inline script or style: the JS is a same-origin static file so the
// strict CSP (default-src 'self') holds. Auth (Access JWT + allow-list) and the version lock are upstream.

import { CONSOLE_TYPES, WORKPLACES, regionChoices } from '../facets.js';
import { TAXONOMY } from '../render/lib.js';
import { CONSOLE_CSP, SECURITY_HEADERS } from '../util.js';
import { escapeHtml } from '../validate.js';

const CONSOLE_HEADERS = {
  ...SECURITY_HEADERS,
  'Content-Security-Policy': CONSOLE_CSP,
  'Cache-Control': 'no-store',
  'Cross-Origin-Opener-Policy': 'same-origin',
};

const opt = (v, label = v) => `<option value="${escapeHtml(v)}">${escapeHtml(label)}</option>`;

export function consoleHtml(site, email) {
  const sectorOpts = TAXONOMY.sectors.map((s) => opt(s.name)).join('');
  const regionSelect = (s) => `<label data-region-for="${s}">Region (${s.toUpperCase()}) <select name="region_${s}">${regionChoices(s).map((r) => opt(r)).join('')}</select></label>`;
  const html = `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>GreenJobs posting console (${escapeHtml(site)})</title>
<link rel="stylesheet" href="/admin/console.css"></head>
<body data-site="${escapeHtml(site)}" data-taxonomy-version="${TAXONOMY.version}">
<header><h1>GreenJobs posting console</h1><p>Site <strong>${escapeHtml(site)}</strong> &middot; signed in as ${escapeHtml(email)}</p></header>
<main>
<section><h2 id="form-title">Post a job</h2>
<form id="job-form" autocomplete="off">
<input type="hidden" name="id"><input type="hidden" name="version">
<fieldset id="sites"><legend>Post to</legend>
<label class="inline"><input type="checkbox" name="site_ie" value="ie"${site === 'ie' ? ' checked' : ''}> greenjobs.ie</label>
<label class="inline"><input type="checkbox" name="site_uk" value="uk"${site === 'uk' ? ' checked' : ''}> greenjobs.co.uk</label>
</fieldset>
<label>Title <input name="title" required minlength="3" maxlength="160"></label>
<label>Employer <input name="employer" required maxlength="200" list="employers"></label><datalist id="employers"></datalist>
<label>Location (as shown) <input name="location" required maxlength="120" placeholder="e.g. Cork"></label>
${regionSelect('ie')}
${regionSelect('uk')}
<label>Sector <select name="sector1" required><option value="">Choose a sector</option>${sectorOpts}</select></label>
<label>Second sector (optional) <select name="sector2"><option value="">None</option>${sectorOpts}</select></label>
<label>Third sector (optional) <select name="sector3"><option value="">None</option>${sectorOpts}</select></label>
<label>Job type <select name="job_type"><option value="">Not stated</option>${CONSOLE_TYPES.map((t) => opt(t)).join('')}</select></label>
<label>Workplace <select name="workplace">${WORKPLACES.map((k) => opt(k, TAXONOMY.workplace[k])).join('')}</select></label>
<label>Salary text <input name="sal_text" maxlength="120" placeholder="e.g. EUR 55,000 - 65,000"></label>
<label>Salary from <input name="sal_min" type="number" min="0" step="1"></label>
<label>Salary to <input name="sal_max" type="number" min="0" step="1"></label>
<label>Salary per <select name="period"><option value="">year</option><option value="month">month</option><option value="day">day</option><option value="hour">hour</option></select></label>
<label>Summary <input name="summary" maxlength="300"></label>
<label>Description <textarea name="description" required minlength="20" maxlength="20000" rows="10"></textarea></label>
<label>Closing date <input name="closing" type="date"></label>
<label>Apply via <select name="apply_mode"><option value="email">Email (on-site form)</option><option value="link">External link (ATS)</option></select></label>
<label data-apply-for="email">Apply email (blank = site default inbox) <input name="apply_email" type="email" maxlength="254"></label>
<label data-apply-for="link" hidden>Apply URL (https only) <input name="apply_url" type="url" maxlength="2000" pattern="https://.+"></label>
<label>Status <select name="status"><option value="live">Live</option><option value="draft">Draft</option></select></label>
<button type="submit">Save</button> <button type="button" id="reset">New job</button>
<p id="msg" role="status"></p>
<p id="view" hidden></p>
</form></section>
<section><h2>Jobs</h2>
<label>Search <input id="search" type="search" placeholder="Title or employer"></label>
<label>Status <select id="status-filter"><option value="">All</option><option value="live">Live</option><option value="draft">Draft</option><option value="closed">Closed</option></select></label>
<table><thead><tr><th>Title</th><th>Employer</th><th>Status</th><th>Closing</th><th></th></tr></thead><tbody id="jobs"></tbody></table></section>
</main>
<script src="/admin/console.js" defer></script>
</body></html>`;
  return new Response(html, { status: 200, headers: { 'Content-Type': 'text/html; charset=utf-8', ...CONSOLE_HEADERS } });
}

const CONSOLE_CSS = `body{font:15px/1.45 system-ui,sans-serif;margin:0 auto;max-width:1100px;padding:1rem;color:#14301f}
label{display:block;margin:.4rem 0}input,select,textarea{display:block;width:100%;max-width:42rem;padding:.35rem;font:inherit}
label.inline{display:inline-block;margin-right:1.2rem}label.inline input{display:inline;width:auto}
fieldset{border:1px solid #d5e3d9;max-width:42rem}
table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid #d5e3d9;padding:.35rem;text-align:left}
button{padding:.4rem .9rem;font:inherit;cursor:pointer}#msg{min-height:1.5em}`;

const CONSOLE_JS = `'use strict';
(function () {
  const form = document.getElementById('job-form');
  const msg = document.getElementById('msg');
  const view = document.getElementById('view');
  const tbody = document.getElementById('jobs');
  const search = document.getElementById('search');
  const statusFilter = document.getElementById('status-filter');
  const SITE = document.body.getAttribute('data-site');
  let all = [];
  const say = (t) => { msg.textContent = t; };
  async function api(method, path, body) {
    const headers = { 'Content-Type': 'application/json' };
    if (method !== 'GET') headers['Idempotency-Key'] = crypto.randomUUID();
    const res = await fetch(path, { method, headers, credentials: 'same-origin', body: body ? JSON.stringify(body) : undefined });
    let data = {};
    try { data = await res.json(); } catch (e) { data = {}; }
    return { status: res.status, data };
  }
  function cell(text) { const td = document.createElement('td'); td.textContent = text == null ? '' : String(text); return td; }
  function button(label, fn) { const b = document.createElement('button'); b.type = 'button'; b.textContent = label; b.addEventListener('click', fn); return b; }
  function showView(urls) {
    view.replaceChildren();
    for (const u of urls || []) {
      const a = document.createElement('a'); a.href = u; a.target = '_blank'; a.rel = 'noopener'; a.textContent = 'View live: ' + u;
      view.append(a, ' ');
    }
    view.hidden = !(urls && urls.length);
  }
  function render() {
    const q = search.value.trim().toLowerCase();
    const st = statusFilter.value;
    tbody.replaceChildren();
    for (const j of all) {
      if (st && j.status !== st) continue;
      if (q && (j.title + ' ' + j.employer).toLowerCase().indexOf(q) < 0) continue;
      const tr = document.createElement('tr');
      tr.append(cell(j.title), cell(j.employer), cell(j.status), cell(j.closing));
      const td = document.createElement('td');
      td.append(button('Edit', () => fill(j)));
      if (j.status === 'live') {
        const a = document.createElement('a'); a.href = j.url; a.target = '_blank'; a.rel = 'noopener'; a.textContent = 'View';
        td.append(' ', a);
      }
      if (j.status !== 'closed') {
        td.append(' ', button('Close', async () => {
          if (!window.confirm('Close "' + j.title + '"? It leaves the public board (the page answers "closed"). You can reopen it later.')) return;
          const c = await api('POST', '/api/admin/jobs/' + encodeURIComponent(j.id) + '/close');
          say(c.status === 200 ? 'Closed.' : 'Close failed: ' + (c.data.error || c.status));
          load();
        }));
      } else {
        td.append(' ', button('Reopen', async () => {
          const r = await api('PUT', '/api/admin/jobs/' + encodeURIComponent(j.id), { version: j.version, status: 'live' });
          if (r.status === 400 && (r.data.fields || []).indexOf('closing') >= 0) { fill(j); form.elements.status.value = 'live'; say('The closing date has passed: set a new one and Save to reopen.'); return; }
          say(r.status === 200 ? 'Reopened.' : 'Reopen failed: ' + (r.data.error || r.status));
          if (r.status === 200) showView([r.data.url]);
          load();
        }));
      }
      tr.append(td);
      tbody.append(tr);
    }
    const dl = document.getElementById('employers');
    dl.replaceChildren();
    for (const name of Array.from(new Set(all.map((j) => j.employer).filter(Boolean))).sort()) {
      const o = document.createElement('option'); o.value = name; dl.append(o);
    }
  }
  async function load() {
    const r = await api('GET', '/api/admin/jobs?limit=200');
    all = r.data.jobs || [];
    render();
  }
  search.addEventListener('input', render);
  statusFilter.addEventListener('change', render);
  // Exactly one apply target per mode: show the matching field, clear the other so the API never sees both.
  function syncMode() {
    const mode = form.elements.apply_mode.value;
    for (const label of form.querySelectorAll('[data-apply-for]')) {
      const on = label.getAttribute('data-apply-for') === mode;
      label.hidden = !on;
      const input = label.querySelector('input');
      input.required = on && mode === 'link';
      if (!on) input.value = '';
    }
  }
  // A region select per chosen site; editing shows only the job's own site.
  function syncSites() {
    const editing = Boolean(form.elements.id.value);
    for (const s of ['ie', 'uk']) {
      const on = editing ? form.elements.id.value.indexOf(s + ':') === 0 : form.elements['site_' + s].checked;
      form.querySelector('[data-region-for="' + s + '"]').hidden = !on;
    }
    document.getElementById('sites').hidden = editing;
  }
  form.elements.apply_mode.addEventListener('change', syncMode);
  form.elements.site_ie.addEventListener('change', syncSites);
  form.elements.site_uk.addEventListener('change', syncSites);
  function fill(j) {
    for (const el of form.elements) {
      if (!el.name || el.type === 'checkbox' || /^(sector[123]|region_..)$/.test(el.name)) continue;
      const v = j[el.name];
      el.value = v == null ? '' : String(v);
    }
    const secs = j.sectors || [];
    form.elements.sector1.value = secs[0] || ''; form.elements.sector2.value = secs[1] || ''; form.elements.sector3.value = secs[2] || '';
    const site = j.id.split(':')[0];
    if (j.region) form.elements['region_' + site].value = j.region;
    form.elements.status.value = j.status === 'closed' ? 'live' : j.status;
    syncMode(); syncSites(); showView(j.status === 'live' ? [j.url] : []);
    document.getElementById('form-title').textContent = j.status === 'closed' ? 'Edit closed job (Save reopens it)' : 'Edit job';
  }
  document.getElementById('reset').addEventListener('click', () => {
    form.reset(); form.elements.id.value = ''; form.elements.version.value = '';
    form.elements['site_' + SITE].checked = true;
    syncMode(); syncSites(); showView([]);
    document.getElementById('form-title').textContent = 'Post a job';
  });
  form.addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const f = form.elements;
    const body = {};
    for (const k of ['title', 'employer', 'location', 'description', 'summary', 'closing', 'apply_mode', 'sal_text', 'status', 'job_type', 'workplace', 'period']) {
      if (f[k].value !== '') body[k] = f[k].value;
    }
    for (const k of ['sal_min', 'sal_max']) body[k] = f[k].value === '' ? null : Number(f[k].value);
    body.sectors = [f.sector1.value, f.sector2.value, f.sector3.value].filter(Boolean);
    // Always sent, blank included, so switching mode on an edit clears the old target.
    body.apply_email = f.apply_email.value;
    body.apply_url = f.apply_url.value;
    let r;
    if (f.id.value) {
      const site = f.id.value.split(':')[0];
      body.region = f['region_' + site].value;
      for (const k of ['summary', 'job_type', 'sal_text', 'period']) if (!(k in body)) body[k] = '';
      body.version = Number(f.version.value);
      r = await api('PUT', '/api/admin/jobs/' + encodeURIComponent(f.id.value), body);
    } else {
      body.sites = ['ie', 'uk'].filter((s) => f['site_' + s].checked);
      if (!body.sites.length) { say('Choose at least one site to post to.'); return; }
      body.region_by_site = {};
      for (const s of body.sites) body.region_by_site[s] = f['region_' + s].value;
      r = await api('POST', '/api/admin/jobs', body);
    }
    if (r.status === 409) say('Someone else edited this job. Reload and try again.');
    else if (r.status >= 400) say('Not saved: ' + (r.data.error || r.status) + (r.data.fields ? ' (' + r.data.fields.join(', ') + ')' : ''));
    else {
      say('Saved. It is on the public board within 5 minutes.');
      const urls = r.data.urls || (r.data.url ? [r.data.url] : []);
      document.getElementById('reset').click();
      if (body.status !== 'draft') showView(urls);
    }
    load();
  });
  syncSites();
  load();
})();
`;

export function consoleAsset(name) {
  if (name === 'console.js') return new Response(CONSOLE_JS, { headers: { 'Content-Type': 'text/javascript; charset=utf-8', ...CONSOLE_HEADERS } });
  if (name === 'console.css') return new Response(CONSOLE_CSS, { headers: { 'Content-Type': 'text/css; charset=utf-8', ...CONSOLE_HEADERS } });
  return null;
}
