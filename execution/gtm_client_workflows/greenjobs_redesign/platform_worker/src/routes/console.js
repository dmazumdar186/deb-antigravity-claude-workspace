// Minimal staff console: a form and a list. No inline script or style; the JS is served as a
// static file from the same origin so the strict CSP (default-src 'self') holds.

import { CONSOLE_CSP, SECURITY_HEADERS } from '../util.js';
import { escapeHtml } from '../validate.js';

const CONSOLE_HEADERS = {
  ...SECURITY_HEADERS,
  'Content-Security-Policy': CONSOLE_CSP,
  'Cache-Control': 'no-store',
  'Cross-Origin-Opener-Policy': 'same-origin',
};

export function consoleHtml(site, email) {
  const html = `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>GreenJobs posting console (${escapeHtml(site)})</title>
<link rel="stylesheet" href="/admin/console.css"></head>
<body data-site="${escapeHtml(site)}">
<header><h1>GreenJobs posting console</h1><p>Site <strong>${escapeHtml(site)}</strong> &middot; signed in as ${escapeHtml(email)}</p></header>
<main>
<section><h2 id="form-title">Post a job</h2>
<form id="job-form" autocomplete="off">
<input type="hidden" name="id"><input type="hidden" name="version">
<label>Title <input name="title" required minlength="3" maxlength="160"></label>
<label>Employer <input name="employer" required maxlength="200"></label>
<label>Location <input name="location" required maxlength="120"></label>
<label>Type <input name="job_type" maxlength="40" placeholder="Permanent"></label>
<label>Salary text <input name="sal_text" maxlength="120"></label>
<label>Sectors (comma separated) <input name="sectors" maxlength="600"></label>
<label>Summary <input name="summary" maxlength="300"></label>
<label>Description <textarea name="description" required minlength="20" maxlength="20000" rows="10"></textarea></label>
<label>Closing date <input name="closing" type="date"></label>
<label>Apply via <select name="apply_mode"><option value="inbox">Site inbox</option><option value="consultant">Consultant email</option><option value="advertiser">Advertiser email</option><option value="url">External URL</option></select></label>
<label>Apply email <input name="apply_email" type="email" maxlength="254"></label>
<label>Apply URL (https) <input name="apply_url" type="url" maxlength="2000"></label>
<label>Status <select name="status"><option value="live">Live</option><option value="draft">Draft</option></select></label>
<button type="submit">Save</button> <button type="button" id="reset">New job</button>
<p id="msg" role="status"></p>
</form></section>
<section><h2>Jobs</h2><table><thead><tr><th>Title</th><th>Employer</th><th>Status</th><th>Closing</th><th></th></tr></thead><tbody id="jobs"></tbody></table></section>
</main>
<script src="/admin/console.js" defer></script>
</body></html>`;
  return new Response(html, { status: 200, headers: { 'Content-Type': 'text/html; charset=utf-8', ...CONSOLE_HEADERS } });
}

const CONSOLE_CSS = `body{font:15px/1.45 system-ui,sans-serif;margin:0 auto;max-width:1100px;padding:1rem;color:#14301f}
label{display:block;margin:.4rem 0}input,select,textarea{display:block;width:100%;max-width:42rem;padding:.35rem;font:inherit}
table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid #d5e3d9;padding:.35rem;text-align:left}
button{padding:.4rem .9rem;font:inherit;cursor:pointer}#msg{min-height:1.5em}`;

const CONSOLE_JS = `'use strict';
(function () {
  const form = document.getElementById('job-form');
  const msg = document.getElementById('msg');
  const tbody = document.getElementById('jobs');
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
  async function load() {
    const r = await api('GET', '/api/admin/jobs?limit=200');
    tbody.replaceChildren();
    for (const j of (r.data.jobs || [])) {
      const tr = document.createElement('tr');
      tr.append(cell(j.title), cell(j.employer), cell(j.status), cell(j.closing));
      const td = document.createElement('td');
      const edit = document.createElement('button'); edit.type = 'button'; edit.textContent = 'Edit';
      edit.addEventListener('click', () => fill(j));
      td.append(edit);
      if (j.status !== 'closed') {
        const close = document.createElement('button'); close.type = 'button'; close.textContent = 'Close';
        close.addEventListener('click', async () => {
          const c = await api('POST', '/api/admin/jobs/' + encodeURIComponent(j.id) + '/close');
          say(c.status === 200 ? 'Closed.' : 'Close failed: ' + (c.data.error || c.status));
          load();
        });
        td.append(' ', close);
      }
      tr.append(td);
      tbody.append(tr);
    }
  }
  function fill(j) {
    for (const el of form.elements) {
      if (!el.name) continue;
      const v = el.name === 'sectors' ? (j.sectors || []).join(', ') : j[el.name];
      el.value = v == null ? '' : String(v);
    }
    form.elements.employer.disabled = true;
    document.getElementById('form-title').textContent = 'Edit job';
  }
  document.getElementById('reset').addEventListener('click', () => {
    form.reset(); form.elements.id.value = ''; form.elements.version.value = '';
    form.elements.employer.disabled = false;
    document.getElementById('form-title').textContent = 'Post a job';
  });
  form.addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const f = form.elements;
    const body = {};
    for (const k of ['title', 'location', 'description', 'closing', 'apply_mode', 'apply_email', 'apply_url', 'sal_text', 'status']) {
      if (f[k].value !== '') body[k] = f[k].value;
    }
    let r;
    if (f.id.value) {
      body.version = Number(f.version.value);
      r = await api('PUT', '/api/admin/jobs/' + encodeURIComponent(f.id.value), body);
    } else {
      body.employer = f.employer.value;
      for (const k of ['job_type', 'summary']) if (f[k].value !== '') body[k] = f[k].value;
      body.sectors = f.sectors.value.split(',').map((s) => s.trim()).filter(Boolean);
      r = await api('POST', '/api/admin/jobs', body);
    }
    if (r.status === 409) say('Someone else edited this job. Reload and try again.');
    else if (r.status >= 400) say('Not saved: ' + (r.data.error || r.status) + (r.data.fields ? ' (' + r.data.fields.join(', ') + ')' : ''));
    else { say('Saved.'); document.getElementById('reset').click(); }
    load();
  });
  load();
})();
`;

export function consoleAsset(name) {
  if (name === 'console.js') return new Response(CONSOLE_JS, { headers: { 'Content-Type': 'text/javascript; charset=utf-8', ...CONSOLE_HEADERS } });
  if (name === 'console.css') return new Response(CONSOLE_CSS, { headers: { 'Content-Type': 'text/css; charset=utf-8', ...CONSOLE_HEADERS } });
  return null;
}
