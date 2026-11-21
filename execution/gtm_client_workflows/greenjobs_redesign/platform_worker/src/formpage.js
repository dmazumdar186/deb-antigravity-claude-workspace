// Board host + HTML result pages for browser form posts (eye review r3 R3-2).
//   boardOrigin(env, site): the edition's configured board origin (CANONICAL_ORIGIN_<SITE>), or null when unset (then
//     the request's own host is the board, as in production before the canonical host is pinned).
//   formResultResponse(): a JSON answer from /api/apply, /api/alerts or /api/newsletter turned into the site's HTML
//     page (same status), for a form a browser posted without JavaScript (Accept: text/html). The page's CSS and links
//     point at the board origin, so it is styled even when the Worker answers on another host (staging workers.dev).

import { shellCtx, shellPage } from './render/pages.js';
import { esc } from './render/lib.js';
import { SECURITY_HEADERS } from './util.js';

const ORIGIN_RE = /^https:\/\/[a-z0-9.-]+$/i;

export function boardOrigin(env, site) {
  const v = String(env[`CANONICAL_ORIGIN_${String(site || '').toUpperCase()}`] || '').trim().replace(/\/+$/, '');
  return ORIGIN_RE.test(v) ? v : null;
}

/** True when `hostname` is a board host: the host of either edition's CANONICAL_ORIGIN, or its www./apex twin. */
export function isBoardHost(env, hostname) {
  const h = String(hostname || '').toLowerCase().replace(/^www\./, '');
  return ['ie', 'uk'].some((s) => {
    const o = boardOrigin(env, s);
    return o && new URL(o).hostname.toLowerCase().replace(/^www\./, '') === h;
  });
}

/** A form post from a browser without JS: Accept names text/html and not JSON first. fetch() sends Accept: *\/*. */
export function wantsHtml(request) {
  const a = String(request.headers.get('Accept') || '').toLowerCase();
  return a.includes('text/html') && !a.startsWith('application/json');
}

// Server-side wording, the same as api.js applyOutcome / outcome() say on the page.
export function applyMessage(status, body) {
  const e = body && body.error;
  if (status === 201) return { ok: true, h: 'Application received', text: 'Thank you: it is on its way to the advertiser.' };
  if (status === 200 && body && body.status === 'already_received') return { ok: true, h: 'Application received', text: 'We already had it, so nothing was sent twice.' };
  if (e === 'invalid_input') return { ok: false, h: 'Not sent', text: 'Some fields were missing or not valid: your name, a valid email address and the consent box are required. Please go back and check the form.' };
  if (e === 'cv_too_large') return { ok: false, h: 'Not sent', text: 'The CV is too large. Please choose a file under 5 MB.' };
  if (e === 'cv_type' || e === 'cv_empty') return { ok: false, h: 'Not sent', text: 'The CV could not be read. Please choose a PDF or Word file.' };
  if (e === 'apply_externally') return { ok: false, h: 'Apply on the employer\'s site', text: 'This role takes applications on the employer\'s own site.' };
  if (e === 'job_not_found') return { ok: false, h: 'Role closed', text: 'This role is no longer open for applications.' };
  if (status === 429) return { ok: false, h: 'Please wait', text: 'Too many applications from this connection. Please try again in 10 minutes.' };
  if (e === 'too_fast' || e === 'form_expired' || e === 'invalid_ts') return { ok: false, h: 'Not sent', text: 'The form could not be checked. Please reload the job page (with JavaScript on) and send it again.' };
  if (e === 'delivery_failed') return { ok: false, h: 'Not sent', text: 'We could not send your application just now. Please try again in a few minutes.' };
  return { ok: false, h: 'Not sent', text: 'We could not take this form just now. Please try again later.' };
}

export function signupMessage(status, body) {
  if (status >= 200 && status < 300) return { ok: true, h: 'Check your inbox', text: 'We have sent you a link to confirm. Nothing is sent until you confirm.' };
  if (status === 429) return { ok: false, h: 'Please wait', text: 'Too many sign-ups from this connection. Please try again in 10 minutes.' };
  if (body && body.error === 'not_found') return { ok: false, h: 'Not available', text: 'This sign-up is not open yet.' };
  return { ok: false, h: 'Not signed up', text: 'Please go back, check your email address and the consent box, and try again.' };
}

export async function formResultResponse({ env, site, url, today, kind, res }) {
  if (!/application\/json/i.test(res.headers.get('Content-Type') || '')) return res; // already a page (confirm/unsubscribe)
  let body = {};
  try { body = await res.clone().json(); } catch { body = {}; }
  const m = kind === 'apply' ? applyMessage(res.status, body) : signupMessage(res.status, body);
  const origin = boardOrigin(env, site) || url.origin;
  const root = `${origin}/`;
  const back = kind === 'apply' ? `${root}${site}/jobs/index.html` : `${root}${site}/index.html`;
  const content = `<div class="wrap pagehead"><h1>${esc(m.h)}</h1><p class="lede" role="${m.ok ? 'status' : 'alert'}">${esc(m.text)}</p>`
    + `<p><a class="btn btn--lime" href="${esc(back)}">${kind === 'apply' ? 'Back to all roles' : 'Back to the home page'}<span class="arw" aria-hidden="true">→</span></a></p></div>`;
  const ctx = shellCtx(site, { page: 'jobs', title: `${m.h} | GreenJobs`, desc: m.text, nJobs: 0, today, indexable: false, reqHost: url.hostname, root });
  return new Response(shellPage(ctx, content, []), {
    status: res.status,
    headers: { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store', ...SECURITY_HEADERS },
  });
}
