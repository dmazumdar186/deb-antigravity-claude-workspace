// Sector review queue (staff only: index.js has already checked the Access JWT + STAFF_EMAILS, and on writes the
// same-origin Origin, JSON content type and Idempotency-Key).
//   GET  /admin/review                    page (no inline script; strict CSP)
//   GET  /admin/review.js                 its script
//   GET  /api/admin/review?status=queued  queued jobs with the suggested sectors + the active sector vocabulary
//   POST /api/admin/review/:id/approve    {sectors?: [...]}: one click. No sectors = accept the suggestion
//                                         ('approved'); other sectors = 'changed'. A held (draft) job goes live.
// Sectors must be active taxonomy_terms (the vocabulary the classifier wrote), 1..3 of them. A decided review
// is final (a replay answers already_decided); a closed job is never taken live (409).

import { CONSOLE_CSP, SECURITY_HEADERS, err, json, nowIso } from '../util.js';
import { cleanText, escapeHtml } from '../validate.js';
import * as Q from '../sql_0003.js';
import { parseJobId, readJson, SQL_AUDIT } from './admin.js';

const HEADERS = { ...SECURITY_HEADERS, 'Content-Security-Policy': CONSOLE_CSP, 'Cache-Control': 'no-store' };
export const REVIEW_DECIDE_PATH = /^\/api\/admin\/review\/([^/]+)\/approve$/;
const MAX_SECTORS = 3;

function parseList(s) {
  try {
    const v = JSON.parse(s || '[]');
    return Array.isArray(v) ? v.filter((x) => typeof x === 'string') : [];
  } catch {
    return [];
  }
}

async function activeSectors(db) {
  const { results } = await db.prepare(`SELECT value FROM taxonomy_terms WHERE kind = 'sector' AND active = 1 ORDER BY value`).all();
  return results.map((r) => r.value);
}

export async function listReview(ctx) {
  const { env, site, request } = ctx;
  const q = new URL(request.url).searchParams;
  const status = q.get('status') || 'queued';
  if (!['queued', 'approved', 'changed'].includes(status)) return err('invalid_status', 400);
  const limit = Math.min(200, Math.max(1, Number.parseInt(q.get('limit') || '100', 10) || 100));
  const offset = Math.min(1_000_000, Math.max(0, Number.parseInt(q.get('offset') || '0', 10) || 0));
  const { results } = await env.DB.prepare(
    `SELECT r.job_id, r.reason, r.suggested_json, r.confidence, r.hold, r.status, r.decided_by, r.decided_sectors_json,
            r.created_at, j.title, j.location, j.source, j.status AS job_status, e.name AS employer
       FROM job_review r JOIN jobs j ON j.id = r.job_id LEFT JOIN employers e ON e.id = j.employer_id
      WHERE r.site = ?1 AND r.status = ?2 ORDER BY r.created_at, r.job_id LIMIT ?3 OFFSET ?4`,
  )
    .bind(site, status, limit + 1, offset)
    .all();
  const more = results.length > limit;
  return json({
    items: results.slice(0, limit).map((r) => ({
      job_id: r.job_id, title: r.title, employer: r.employer || '', location: r.location, source: r.source,
      job_status: r.job_status, reason: r.reason, suggested: parseList(r.suggested_json), confidence: r.confidence,
      hold: r.hold === 1, status: r.status, decided_by: r.decided_by, decided: r.decided_sectors_json ? parseList(r.decided_sectors_json) : null,
    })),
    sectors: await activeSectors(env.DB),
    next_offset: more ? offset + limit : null,
  });
}

export async function decideReview(ctx, rawId) {
  const { env, site, now, actor, idemKey } = ctx;
  const db = env.DB;
  const p = parseJobId(rawId, site);
  if (!p.ok) return p.res;
  const rb = await readJson(ctx.request);
  if (!rb.ok) return rb.res;
  const unknown = Object.keys(rb.body).filter((k) => k !== 'sectors');
  if (unknown.length) return json({ error: 'unknown_field', fields: unknown.slice(0, 5).map((k) => String(k).slice(0, 40)) }, 400);

  const row = await db
    .prepare(`SELECT r.status, r.suggested_json, j.status AS job_status FROM job_review r JOIN jobs j ON j.id = r.job_id WHERE r.job_id = ?1 AND r.site = ?2`)
    .bind(p.id, site)
    .first();
  if (!row) return err('not_found', 404);
  if (row.status !== 'queued') return json({ id: p.id, status: row.status, already_decided: true }, 200);
  if (row.job_status === 'closed') return err('job_closed', 409);

  const suggested = parseList(row.suggested_json);
  let sectors = suggested;
  if (rb.body.sectors !== undefined) {
    if (!Array.isArray(rb.body.sectors)) return json({ error: 'invalid_input', fields: ['sectors'] }, 400);
    sectors = [];
    for (const s of rb.body.sectors) {
      const c = cleanText(s, { min: 1, max: 80 });
      if (!c.ok) return json({ error: 'invalid_input', fields: ['sectors'] }, 400);
      if (!sectors.includes(c.value)) sectors.push(c.value);
    }
  }
  if (sectors.length < 1 || sectors.length > MAX_SECTORS) return json({ error: 'invalid_input', fields: ['sectors'] }, 400);
  const vocab = new Set(await activeSectors(db));
  const outside = sectors.filter((s) => !vocab.has(s));
  if (outside.length) return json({ error: 'unknown_sector', fields: ['sectors'] }, 400);

  const decision = JSON.stringify(sectors) === JSON.stringify(suggested) ? 'approved' : 'changed';
  const ts = nowIso(now);
  const sj = JSON.stringify(sectors);
  const [jobRes, revRes] = await db.batch([
    db.prepare(Q.REVIEW_APPROVE_JOB).bind(p.id, site, sj, ts),
    db.prepare(Q.REVIEW_DECIDE).bind(p.id, site, decision, actor, sj, ts),
  ]);
  if (!revRes.meta || revRes.meta.changes === 0) {
    const again = await db.prepare('SELECT status FROM job_review WHERE job_id = ?1').bind(p.id).first();
    return json({ id: p.id, status: again?.status ?? null, already_decided: true }, 200);
  }
  await db.prepare(SQL_AUDIT).bind(ts, actor, `review.${decision}`, 'job', p.id, idemKey, JSON.stringify({ fields: ['sectors', 'status'], sectors: sectors.length })).run();
  const job = await db.prepare('SELECT status, version FROM jobs WHERE id = ?1').bind(p.id).first();
  return json({ id: p.id, status: decision, job_status: job.status, version: job.version, job_updated: (jobRes.meta?.changes ?? 0) > 0 }, 200);
}

export function reviewHtml(site, email) {
  const html = `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>GreenJobs sector review (${escapeHtml(site)})</title>
<link rel="stylesheet" href="/admin/console.css"></head>
<body data-site="${escapeHtml(site)}">
<header><h1>Sector review</h1><p>Site <strong>${escapeHtml(site)}</strong> &middot; signed in as ${escapeHtml(email)} &middot; <a href="/admin/">Posting console</a></p>
<p>Jobs the classifier was not sure about. <strong>Approve</strong> takes the suggested sectors and puts a held job live; pick other sectors and press <strong>Change &amp; approve</strong> to correct it.</p></header>
<main><p id="msg" role="status"></p>
<table><thead><tr><th>Job</th><th>Why queued</th><th>Suggested</th><th>Sectors</th><th></th></tr></thead><tbody id="queue"></tbody></table></main>
<script src="/admin/review.js" defer></script>
</body></html>`;
  return new Response(html, { status: 200, headers: { 'Content-Type': 'text/html; charset=utf-8', ...HEADERS } });
}

const REVIEW_JS = `'use strict';
(function () {
  const tbody = document.getElementById('queue');
  const msg = document.getElementById('msg');
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
  async function decide(id, sectors) {
    const r = await api('POST', '/api/admin/review/' + encodeURIComponent(id) + '/approve', sectors ? { sectors } : {});
    say(r.status === 200 ? (r.data.already_decided ? 'Already decided.' : 'Saved: ' + r.data.status + (r.data.job_status === 'live' ? ', job is live.' : '.')) : 'Not saved: ' + (r.data.error || r.status));
    load();
  }
  async function load() {
    const r = await api('GET', '/api/admin/review?status=queued&limit=200');
    tbody.replaceChildren();
    const options = r.data.sectors || [];
    const items = r.data.items || [];
    if (!items.length) { say('Nothing waiting for review.'); return; }
    for (const it of items) {
      const tr = document.createElement('tr');
      tr.append(cell(it.title + ' (' + (it.employer || it.source) + ', ' + it.location + ')' + (it.hold ? ' [held]' : '')), cell(it.reason), cell((it.suggested || []).join(', ')));
      const td = document.createElement('td');
      const sel = document.createElement('select'); sel.multiple = true; sel.size = 4;
      for (const o of options) { const op = document.createElement('option'); op.value = o; op.textContent = o; op.selected = (it.suggested || []).includes(o); sel.append(op); }
      td.append(sel); tr.append(td);
      const act = document.createElement('td');
      const ok = document.createElement('button'); ok.type = 'button'; ok.textContent = 'Approve'; ok.disabled = !(it.suggested || []).length;
      ok.addEventListener('click', () => decide(it.job_id, null));
      const ch = document.createElement('button'); ch.type = 'button'; ch.textContent = 'Change & approve';
      ch.addEventListener('click', () => decide(it.job_id, [...sel.selectedOptions].map((o) => o.value)));
      act.append(ok, ' ', ch); tr.append(act);
      tbody.append(tr);
    }
  }
  load();
})();
`;

export function reviewAsset() {
  return new Response(REVIEW_JS, { headers: { 'Content-Type': 'text/javascript; charset=utf-8', ...HEADERS } });
}
