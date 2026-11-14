// /api/review-admin — Jeevana's moderation page (same Basic auth as /api/export: EXPORT_USER / EXPORT_PASS).
// GET  -> HTML list, pending first, with Publish / Hide / Delete buttons.
// POST (form: id, action=publish|hide|delete) -> applies it, rebuilds the public snapshot, 303 back to GET.
// CSRF: Basic-auth credentials ride along on cross-site form posts, so POST requires a same-origin Origin/Referer.
import { Env, logError } from './_lib';
import { guardFailures } from './_auth';
import { Review, Status, listAll, rebuild, putReview } from './_reviews';

const esc = (s: unknown) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c] as string));
const HDR = { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store', 'X-Robots-Tag': 'noindex',
  'Content-Security-Policy': "default-src 'none'; style-src 'self'; font-src 'self'; img-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'",
  'X-Frame-Options': 'DENY', 'Referrer-Policy': 'same-origin' };
const LABEL: Record<Status, string> = { pending: 'En attente', published: 'Publié', hidden: 'Masqué' };

function sameOrigin(request: Request): boolean {
  const host = new URL(request.url).host;
  const src = request.headers.get('Origin') || request.headers.get('Referer') || '';
  try { return new URL(src).host === host; } catch { return false; }
}

function page(reviews: Review[], msg: string): string {
  const order: Record<Status, number> = { pending: 0, published: 1, hidden: 2 };
  const rows = [...reviews].sort((a, b) => order[a.status] - order[b.status] || (a.ts < b.ts ? 1 : -1)).map((r) => {
    const btn = (action: string, label: string) => `<button class="button button-small" name="action" value="${action}">${label}</button>`;
    const actions = [r.status !== 'published' ? btn('publish', 'Publier') : '', r.status !== 'hidden' ? btn('hide', 'Masquer') : '', btn('delete', 'Supprimer définitivement')].join('');
    return `<li class="admin-review admin-review--${r.status}"><p class="admin-meta"><strong>${esc(r.name)}</strong> · ${'★'.repeat(r.rating)}${'☆'.repeat(5 - r.rating)} · ${esc(r.ts.slice(0, 10))} · <span class="admin-status">${LABEL[r.status]}</span>${r.hold_reason ? ` · raison : ${esc(r.hold_reason)}` : ''}</p><p class="admin-text">${esc(r.text)}</p><form method="post" class="admin-actions"><input type="hidden" name="id" value="${esc(r.id)}">${actions}</form></li>`;
  }).join('');
  const pending = reviews.filter((r) => r.status === 'pending').length;
  return `<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex"><title>Avis — gestion</title><link rel="stylesheet" href="/css/styles.css"></head><body class="admin-page"><main class="container admin"><h1>Avis — gestion</h1><p>${reviews.length} avis · ${pending} en attente · <a class="quiet-link" href="/reviews/">Voir la page publique</a></p>${msg ? `<p class="form-status" role="status">${esc(msg)}</p>` : ''}<p class="admin-help">Masquer : retire l’avis de la page et bloque sa republication à l’identique (à utiliser pour le spam ou un avis abusif). Supprimer définitivement : efface toutes les données de l’avis (à utiliser pour une demande de retrait de son auteur, après lui avoir demandé de citer le texte de l’avis).</p><ul class="admin-list">${rows || '<li>Aucun avis pour le moment.</li>'}</ul></main></body></html>`;
}

export const onRequestGet: PagesFunction<Env> = async ({ request, env }) => {
  const denied = await guardFailures(env, request); if (denied) return denied;
  if (!env.JEEVANA_KV) return new Response('storage unavailable', { status: 503 });
  try {
    const msg = new URL(request.url).searchParams.get('done') === '1' ? 'Modification enregistrée.' : '';
    return new Response(page(await listAll(env.JEEVANA_KV), msg), { headers: HDR });
  } catch (err) {
    logError('review-admin:get', err);
    return new Response('internal error', { status: 500 });
  }
};

export const onRequestPost: PagesFunction<Env> = async ({ request, env }) => {
  const denied = await guardFailures(env, request); if (denied) return denied;
  if (!sameOrigin(request)) return new Response('Forbidden', { status: 403 });
  if (!env.JEEVANA_KV) return new Response('storage unavailable', { status: 503 });
  try {
    const f = await request.formData();
    const id = String(f.get('id') || ''), action = String(f.get('action') || '');
    if (!/^[0-9a-f]{20}$/.test(id) || !['publish', 'hide', 'delete'].includes(action)) return new Response('Bad request', { status: 400 });
    const key = `rev:${id}`, raw = await env.JEEVANA_KV.get(key);
    if (!raw) return new Response(null, { status: 303, headers: { Location: '/api/review-admin?done=1' } }); // already gone: idempotent
    if (action === 'delete') {
      await env.JEEVANA_KV.delete(key);
      const tomb = JSON.parse(raw) as Review; tomb.status = 'hidden'; // keep it out of the rebuild even if list still shows the key
      await rebuild(env, tomb);
    } else {
      const r = JSON.parse(raw) as Review;
      r.status = action === 'publish' ? 'published' : 'hidden';
      await putReview(env.JEEVANA_KV, r);
      await rebuild(env, r);
    }
    return new Response(null, { status: 303, headers: { Location: '/api/review-admin?done=1' } });
  } catch (err) {
    logError('review-admin:post', err);
    return new Response('internal error', { status: 500 });
  }
};
