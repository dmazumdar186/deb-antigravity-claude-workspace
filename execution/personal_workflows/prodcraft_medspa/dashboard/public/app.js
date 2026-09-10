// ProdCraft Med Spa dashboard — vanilla JS, no framework, no CDN.
// Basic Auth is handled entirely by functions/_middleware.ts; the browser
// caches credentials after the first prompt, so every fetch() below is a
// plain same-origin call with no auth header of its own.

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

function toast(message, kind = 'ok') {
  const region = $('#toast-region');
  const el = document.createElement('div');
  el.className = `toast ${kind}`;
  el.textContent = message;
  region.appendChild(el);
  setTimeout(() => el.remove(), 5000);
}

async function api(path, opts = {}) {
  const res = await fetch(path, {
    ...opts,
    headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) },
  });
  let data = null;
  try {
    data = await res.json();
  } catch {
    // no body
  }
  if (!res.ok) {
    const message = (data && data.error) || `${path} failed (${res.status})`;
    throw new Error(message);
  }
  return data;
}

function escapeHtml(str) {
  return String(str ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

// ---- Tabs -----------------------------------------------------------

function initTabs() {
  $$('.tab-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      $$('.tab-btn').forEach((b) => { b.classList.remove('active'); b.setAttribute('aria-selected', 'false'); });
      btn.classList.add('active');
      btn.setAttribute('aria-selected', 'true');
      $$('.tab-panel').forEach((p) => { p.hidden = true; });
      $(`#tab-${btn.dataset.tab}`).hidden = false;
      if (btn.dataset.tab === 'previews') loadPreviews();
      if (btn.dataset.tab === 'stats') loadStats();
      if (btn.dataset.tab === 'config') loadConfig();
    });
  });
}

// ---- Queue ------------------------------------------------------------

const TOUCH_DAYS = [0, 3, 7, 12];

function scoreBadgeClass(score) {
  if (score == null) return '';
  return score >= 70 ? 'high' : '';
}

function queueCardHtml(row) {
  const b = row.business || {};
  const a = row.audit || {};
  const p = row.preview || {};
  const gaps = Array.isArray(a.gaps) ? a.gaps.slice(0, 3) : [];
  const thumb = a.screenshot_mobile_url
    ? `<img class="thumb" src="${escapeHtml(a.screenshot_mobile_url)}" alt="current site mobile screenshot" loading="lazy" />`
    : `<div class="thumb"></div>`;
  return `
  <article class="queue-card" data-id="${row.id}" data-touch="${row.touch}">
    ${thumb}
    <div class="queue-card-body">
      <div class="queue-card-head">
        <h3>${escapeHtml(b.name || 'Unknown business')}</h3>
        <span class="score-badge ${scoreBadgeClass(a.total_score)}">${a.total_score ?? '—'}</span>
        <span class="touch-badge">touch ${row.touch} · day ${TOUCH_DAYS[row.touch - 1] ?? '?'}</span>
      </div>
      <div class="muted">${escapeHtml(b.owner_first || 'unknown owner')} · ${escapeHtml(b.owner_email || 'no email')} · ${escapeHtml(b.suburb || '')}</div>
      ${p.subdomain_url ? `<a href="${escapeHtml(p.subdomain_url)}" target="_blank" rel="noopener">preview link</a>` : '<span class="muted">no preview</span>'}
      ${gaps.length ? `<ul class="gap-list">${gaps.map((g) => `<li>${escapeHtml(g.human_phrase || g.signal)}</li>`).join('')}</ul>` : ''}
      <input type="text" class="draft-subject" placeholder="Subject" value="${escapeHtml(row.draft_subject || '')}" />
      <textarea class="draft-body" rows="5" placeholder="Body">${escapeHtml(row.draft_body || '')}</textarea>
      <div class="card-actions">
        <button type="button" class="save-draft">Save draft</button>
        <button type="button" class="mark-sent primary">Mark sent</button>
        <select class="reply-sentiment">
          <option value="positive">positive</option>
          <option value="neutral">neutral</option>
          <option value="negative">negative</option>
          <option value="remove">remove</option>
          <option value="bounce">bounce</option>
        </select>
        <button type="button" class="mark-replied">Replied…</button>
        <button type="button" class="call-booked">Call booked</button>
        <button type="button" class="mark-dnc danger">DNC</button>
      </div>
    </div>
  </article>`;
}

function wireQueueCard(el) {
  const id = el.dataset.id;

  $('.save-draft', el).addEventListener('click', async () => {
    try {
      await api(`/api/outreach/${id}/draft`, {
        method: 'POST',
        body: JSON.stringify({
          draft_subject: $('.draft-subject', el).value,
          draft_body: $('.draft-body', el).value,
        }),
      });
      toast('Draft saved');
    } catch (err) {
      toast(err.message, 'error');
    }
  });

  $('.mark-sent', el).addEventListener('click', async () => {
    try {
      await api(`/api/outreach/${id}/transition`, {
        method: 'POST',
        body: JSON.stringify({ to: 'sent' }),
      });
      toast('Marked sent');
      loadQueue();
    } catch (err) {
      toast(err.message, 'error');
    }
  });

  $('.mark-replied', el).addEventListener('click', async () => {
    const sentiment = $('.reply-sentiment', el).value;
    try {
      await api(`/api/outreach/${id}/transition`, {
        method: 'POST',
        body: JSON.stringify({ to: 'replied', reply_sentiment: sentiment }),
      });
      toast('Marked replied');
      loadQueue();
    } catch (err) {
      toast(err.message, 'error');
    }
  });

  $('.call-booked', el).addEventListener('click', async () => {
    try {
      await api(`/api/outreach/${id}/transition`, {
        method: 'POST',
        body: JSON.stringify({ to: 'call_booked' }),
      });
      toast('Call booked!', 'ok');
      loadQueue();
    } catch (err) {
      toast(err.message, 'error');
    }
  });

  $('.mark-dnc', el).addEventListener('click', async () => {
    if (!confirm('Mark do-not-contact? This takes down the preview and cancels remaining touches.')) return;
    try {
      await api(`/api/outreach/${id}/transition`, {
        method: 'POST',
        body: JSON.stringify({ to: 'dnc' }),
      });
      toast('Marked DNC');
      loadQueue();
    } catch (err) {
      toast(err.message, 'error');
    }
  });
}

async function loadQueue() {
  const date = $('#queue-date').value;
  const list = $('#queue-list');
  const empty = $('#queue-empty');
  const banner = $('#halt-banner');
  try {
    const data = await api(`/api/queue?date=${encodeURIComponent(date)}`);
    if (data.halted) {
      banner.hidden = false;
      banner.textContent = `Queue halted: ${data.halted.reason}`;
    } else {
      banner.hidden = true;
    }
    $('#queue-cap-note').textContent = data.cap ? `cap: ${data.cap}/day` : '';
    const rows = data.queue || [];
    list.innerHTML = rows.map(queueCardHtml).join('');
    empty.hidden = rows.length > 0;
    $$('.queue-card', list).forEach(wireQueueCard);
  } catch (err) {
    toast(err.message, 'error');
  }
}

// ---- Previews -----------------------------------------------------------

function previewRowHtml(row) {
  const b = row.business || {};
  const a = row.audit || {};
  return `
  <article class="preview-row" data-id="${row.id}" data-status="${row.status}">
    <div>
      <h3>${escapeHtml(b.name || 'Unknown')} <span class="muted">(${escapeHtml(row.status)})</span></h3>
      <p class="muted">score ${a.total_score ?? '—'} · ${escapeHtml(a.bucket || '')} · ${escapeHtml(b.suburb || '')}</p>
      <p><a href="${escapeHtml(row.subdomain_url)}" target="_blank" rel="noopener">${escapeHtml(row.subdomain_url)}</a></p>
      <div class="card-actions">
        <button type="button" class="approve primary">Approve</button>
        <button type="button" class="reject">Send back to review</button>
        <button type="button" class="takedown danger">Takedown</button>
      </div>
      <pre>${escapeHtml(JSON.stringify(row.content, null, 2))}</pre>
    </div>
    <iframe src="${escapeHtml(row.subdomain_url)}" title="preview iframe" loading="lazy"></iframe>
  </article>`;
}

function wirePreviewRow(el) {
  const id = el.dataset.id;
  const act = async (status) => {
    try {
      await api(`/api/previews/${id}/status`, { method: 'POST', body: JSON.stringify({ status }) });
      toast(`Preview set to ${status}`);
      loadPreviews();
    } catch (err) {
      toast(err.message, 'error');
    }
  };
  $('.approve', el)?.addEventListener('click', () => act('approved'));
  $('.reject', el)?.addEventListener('click', () => act('review'));
  $('.takedown', el)?.addEventListener('click', () => {
    if (confirm('Takedown this preview and mark the business do-not-contact?')) act('takedown');
  });
}

async function loadPreviews() {
  const status = $('#preview-status-filter').value;
  const list = $('#preview-list');
  const empty = $('#preview-empty');
  try {
    const data = await api(`/api/previews${status ? `?status=${encodeURIComponent(status)}` : ''}`);
    const rows = data.previews || [];
    list.innerHTML = rows.map(previewRowHtml).join('');
    empty.hidden = rows.length > 0;
    $$('.preview-row', list).forEach(wirePreviewRow);
  } catch (err) {
    toast(err.message, 'error');
  }
}

// ---- Stats -----------------------------------------------------------

function fmtPct(x) {
  return x == null ? '—' : `${(x * 100).toFixed(1)}%`;
}

async function loadStats() {
  try {
    const data = await api('/api/stats');
    const p0 = data.phase0 || {};
    const banner = $('#phase0-banner');
    banner.className = `phase0-banner ${p0.passed ? 'passed' : ''}`;
    banner.textContent = p0.passed
      ? `Phase 0 PASSED — ${p0.calls_booked ?? 0} call(s) booked, ${p0.sends ?? 0} touch-1 sends. Queue cap open (20/day).`
      : `Phase 0 in progress — ${p0.calls_booked ?? 0} call(s) booked of 1 needed, ${p0.sends ?? 0} touch-1 sends. Queue cap locked (5/day).`;

    $('#stat-bounce').textContent = fmtPct(data.bounce_rate_30d);
    $('#stat-sends-per-reply').textContent = data.sends_per_reply == null ? '—' : data.sends_per_reply.toFixed(1);

    const replyBody = $('#reply-rate-table tbody');
    replyBody.innerHTML = Object.entries(data.reply_rate_per_touch || {})
      .map(([touch, rate]) => `<tr><td>${escapeHtml(touch)}</td><td>${fmtPct(rate)}</td></tr>`)
      .join('');

    const funnelBody = $('#funnel-table tbody');
    const funnel = data.funnel_by_metro || {};
    funnelBody.innerHTML = Object.entries(funnel)
      .map(([metro, f]) => `<tr>
        <td>${escapeHtml(metro)}</td><td>${f.businesses}</td><td>${f.audited}</td><td>${f.qualified}</td>
        <td>${f.owner_found}</td><td>${f.verified}</td><td>${f.previews_approved}</td>
        <td>${f.sent_touch1}</td><td>${f.replied}</td><td>${f.calls}</td><td>${f.closed_won}</td>
      </tr>`)
      .join('') || '<tr><td colspan="11" class="muted">No data yet.</td></tr>';

    const metroStatsBody = $('#metro-stats-table tbody');
    metroStatsBody.innerHTML = (data.metro_stats || [])
      .map((m) => `<tr>
        <td>${escapeHtml(m.metro)}</td><td>${m.sampled}</td><td>${m.qualified}</td>
        <td>${m.pct_qualified}%</td><td>${m.ci_low}–${m.ci_high}%</td>
        <td>${escapeHtml(new Date(m.measured_at).toLocaleDateString())}</td>
      </tr>`)
      .join('') || '<tr><td colspan="6" class="muted">No samples yet.</td></tr>';
  } catch (err) {
    toast(err.message, 'error');
  }
}

// ---- Config -----------------------------------------------------------

async function loadConfig() {
  try {
    const data = await api('/api/config');
    $('#cfg-proof-lines').value = (data.proof_lines || []).join('\n');
    $('#cfg-sender-name').value = data.sender?.name || '';
    $('#cfg-sender-address').value = data.sender?.physical_address || '';
    $('#cfg-sender-signature').value = data.sender?.signature || '';
    $('#cfg-phase0-passed').checked = !!data.phase0?.passed;
  } catch (err) {
    toast(err.message, 'error');
  }
}

function initConfigForm() {
  $('#config-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    try {
      await api('/api/config', {
        method: 'POST',
        body: JSON.stringify({
          proof_lines: $('#cfg-proof-lines').value.split('\n').map((l) => l.trim()).filter(Boolean),
          sender: {
            name: $('#cfg-sender-name').value,
            physical_address: $('#cfg-sender-address').value,
            signature: $('#cfg-sender-signature').value,
          },
        }),
      });
      toast('Saved proof lines + sender');
    } catch (err) {
      toast(err.message, 'error');
    }
  });

  $('#cfg-phase0-submit').addEventListener('click', async () => {
    const reason = $('#cfg-phase0-reason').value.trim();
    if (!reason) {
      toast('Reason is required for a phase0 override', 'error');
      return;
    }
    try {
      await api('/api/config', {
        method: 'POST',
        body: JSON.stringify({
          phase0: { passed: $('#cfg-phase0-passed').checked },
          reason,
        }),
      });
      toast('Phase0 override applied');
      $('#cfg-phase0-reason').value = '';
    } catch (err) {
      toast(err.message, 'error');
    }
  });
}

// ---- Init -----------------------------------------------------------

function init() {
  initTabs();
  initConfigForm();
  $('#queue-date').value = new Date().toISOString().slice(0, 10);
  $('#queue-date').addEventListener('change', loadQueue);
  $('#preview-status-filter').addEventListener('change', loadPreviews);
  loadQueue();
}

document.addEventListener('DOMContentLoaded', init);
