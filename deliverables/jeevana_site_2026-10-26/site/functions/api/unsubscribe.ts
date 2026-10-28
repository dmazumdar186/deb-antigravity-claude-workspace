// GET /api/unsubscribe?t=<token> — deletes the newsletter record; replies with a tiny HTML page (EN/FR by the record's lang).
// The link https://<domain>/api/unsubscribe?t=<unsubscribe_token> goes into every newsletter (research/to_wire.md).
import { Env, logError } from './_lib';

const PAGE = {
  en: { t: 'Unsubscribed', h: 'You are unsubscribed.', p: 'Your address has been removed from Jeevana\'s newsletter.', bad: 'This link is not valid or has already been used.', home: 'Back to the site' },
  fr: { t: 'Désinscription', h: 'Vous êtes désinscrit·e.', p: 'Votre adresse a été retirée de la lettre d\'information de Jeevana.', bad: 'Ce lien n\'est pas valide ou a déjà été utilisé.', home: 'Retour au site' },
};

function page(lang: 'en' | 'fr', ok: boolean, status: number): Response {
  const s = PAGE[lang];
  const html = `<!DOCTYPE html><html lang="${lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex"><title>${s.t} — Jeevana</title><link rel="stylesheet" href="/css/styles.css"></head><body class="nf"><main class="nf__main"><img src="/assets/monogram.svg" alt="Jeevana" width="72" height="72"><h1>${ok ? s.h : s.t}</h1><p>${ok ? s.p : s.bad}</p><p class="ctas"><a class="btn btn--ink" href="/">${s.home}</a></p></main></body></html>`;
  return new Response(html, { status, headers: { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' } });
}

export const onRequestGet: PagesFunction<Env> = async ({ request, env }) => {
  const url = new URL(request.url);
  const t = (url.searchParams.get('t') || '').trim();
  const qlang = url.searchParams.get('lang') === 'fr' ? 'fr' : 'en';
  if (!/^[0-9a-f]{48}$/.test(t)) return page(qlang, false, 400);
  if (!env.JEEVANA_KV) return page(qlang, false, 503);
  try {
    const key = await env.JEEVANA_KV.get(`unsub:${t}`);
    if (!key) return page(qlang, false, 404);
    const raw = await env.JEEVANA_KV.get(key);
    const lang = raw && (JSON.parse(raw) as { lang?: string }).lang === 'fr' ? 'fr' : qlang;
    await env.JEEVANA_KV.delete(key);
    await env.JEEVANA_KV.delete(`unsub:${t}`);
    return page(lang, true, 200);
  } catch (err) {
    logError('unsubscribe', err);
    return page(qlang, false, 500);
  }
};
