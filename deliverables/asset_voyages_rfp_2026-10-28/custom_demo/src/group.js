// « Lien de groupe » (EXTRA_GROUP.md): one unguessable link per enquiry; each delegate fills in their own travel details
// on a phone; the team reads a live manifest in the console. Public side here, console side in console.js.
//
// Tokens: the URL token is HMAC(group-v1, 'tok|' + salt) where the salt is 128 random bits stored with the link; the
// row keeps only the salt and the lookup MAC HMAC(group-v1, 'id|' + token). A database dump alone gives no valid URL.
// Sandboxes: a link resolves server-side to the sandbox that created it (origin_sbx) and every delegate write lands
// there and counts against that sandbox's write budget. The seed link (origin '') behaves like all seed data: a
// browser's submission lands in that browser's own sandbox.
import {
  html, raw, parisToday, nowIso, addDays, isIsoDate, frRange, frNumDate, clean, readForm, sameOrigin, makeFormToken,
  checkFormToken, rateHit, redirect, htmlResponse, hmac, safeEqual, randomToken, getCookie,
} from './lib.js';
import { groupPage, field, errorSummary, displayWrap } from './views.js';
import { claim, validSbx, T, DEMO_BUSY, DEMO_PAUSE } from './data.js';
import { EMAIL_RE } from './public.js';

export const LINK_DAYS = 30;
export const TOKEN_RE = /^[A-Za-z0-9_-]{43}$/;
export const DEFAULT_SEUIL = 10;
export const SEUIL_MIN = 2;
export const SEUIL_MAX = 99;
export const GROUP_MIN_PAX = 2; // the panel appears from 2 passengers
export const GRP_IP_LIMIT = 20; // accepted delegate submissions per IP hash per 10 minutes (one D1 counter row)
export const GRP_WINDOW = 600;
export const GRP_MISS_LIMIT = 60; // unknown or closed tokens per IP per 10 minutes (counted in memory, costs no write)
const MIN_FILL_MS = 3000;
const CONFIRM_TTL = 3600; // the delegate's « merci » page can be reloaded for one hour
const NO_STORE = { 'cache-control': 'no-store, private' };

// ---------------------------------------------------------------- pure helpers (unit-tested in qa/B/unit_group.test.mjs)
export const tokenFor = (env, salt) => hmac(env, 'group-v1', 'tok|' + salt);
export const lookupMac = (env, token) => hmac(env, 'group-v1', 'id|' + token);
export const newSalt = () => randomToken(16); // 128 random bits
export const linkExpiry = (fromIso = parisToday()) => addDays(String(fromIso).slice(0, 10), LINK_DAYS) + 'T23:59:59Z';
export function linkState(link, now = nowIso()) {
  if (!link) return 'none';
  if (link.revoked_at) return 'revoked';
  if (link.expires_at <= now) return 'expired';
  return 'active';
}
export const emailNorm = (e) => String(e || '').trim().toLowerCase();
// At most this many distinct delegates per enquiry (updates of an existing e-mail are always accepted).
export const delegateCap = (pax) => Math.min(100, Math.max(10, 2 * (Number(pax) || 0)));
export function parseSeuil(raw) {
  const s = String(raw ?? '').trim();
  if (!/^\d{1,3}$/.test(s)) return null;
  const n = +s;
  return n >= SEUIL_MIN && n <= SEUIL_MAX ? n : null;
}
// Internal hint only (never on the public link): « proche » within 2 answers or 20 % of the threshold, « atteint » at it.
export const nearMargin = (seuil) => Math.max(2, Math.ceil(seuil * 0.2));
// When every expected traveller has answered (USAB-X-005), it says so instead of asking to chase replies.
export function seuilHint(answered, seuil, expected = Infinity) {
  if (!(seuil > 0)) return null;
  const all = answered >= expected;
  const tous = 'Tous les participants ont répondu.';
  if (answered >= seuil) return { kind: 'atteint', text: `Seuil groupe atteint : ${answered} réponse${answered > 1 ? 's' : ''} pour un seuil de ${seuil} (à confirmer).${all ? ' ' + tous : ''}` };
  if (answered >= seuil - nearMargin(seuil)) return { kind: 'proche', text: `Proche du seuil groupe : ${answered} réponse${answered > 1 ? 's' : ''} sur ${seuil} (à confirmer). ${all ? tous : 'Relancez les participants qui n’ont pas encore répondu.'}` };
  if (all) return { kind: 'tous', text: tous };
  return null;
}
export const counterText = (answered, expected) => `${answered} répondu${answered > 1 ? 's' : ''} / ${expected} attendu${expected > 1 ? 's' : ''}`;

// Delegate form: name as on the ID, e-mail, departure city, outbound and return dates, consent. Nothing else.
export const GRP_LABELS = { name: 'Nom et prénom', email: 'E-mail', departure_city: 'Ville de départ', date_out: 'Date aller', date_back: 'Date retour', consent: 'Consentement' };
export const GRP_IDS = { name: 'g-name', email: 'g-email', departure_city: 'g-city', date_out: 'g-out', date_back: 'g-back', consent: 'g-consent' };
export function validateDelegate(get, congress, t = parisToday()) {
  const v = {
    name: clean(get('name'), 120), email: clean(get('email'), 254), departure_city: clean(get('departure_city'), 80),
    date_out: clean(get('date_out'), 10), date_back: clean(get('date_back'), 10), consent: get('consent') === '1',
  };
  const e = {};
  if (!v.name) e.name = 'Indiquez vos nom et prénom, tels qu’ils figurent sur votre pièce d’identité.';
  else if (v.name.length > 120) e.name = '120 caractères au maximum.';
  if (!v.email) e.email = 'Indiquez votre e-mail.';
  else if (v.email.length > 254 || !EMAIL_RE.test(v.email)) e.email = 'Cette adresse e-mail n’est pas valide (exemple : prenom.nom@hopital.fr).';
  if (!v.departure_city) e.departure_city = 'Indiquez votre ville de départ.';
  else if (v.departure_city.length > 80) e.departure_city = '80 caractères au maximum.';
  // Floor and ceiling: not in the past, and within 30 days of the congress on either side.
  const lo = congress ? addDays(congress.start_date, -30) : t;
  const hi = congress ? addDays(congress.end_date, 30) : addDays(t, 760);
  const floor = lo > t ? lo : t;
  if (!v.date_out) e.date_out = 'Indiquez la date aller.';
  else if (!isIsoDate(v.date_out)) e.date_out = 'Date invalide.';
  else if (v.date_out < t) e.date_out = 'La date aller ne peut pas être passée.';
  else if (v.date_out < floor || v.date_out > hi) e.date_out = 'Choisissez une date proche du congrès (30 jours avant ou après au plus).';
  if (!v.date_back) e.date_back = 'Indiquez la date retour.';
  else if (!isIsoDate(v.date_back)) e.date_back = 'Date invalide.';
  else if (v.date_back < t) e.date_back = 'La date retour ne peut pas être passée.';
  else if (!e.date_out && v.date_back < v.date_out) e.date_back = 'La date retour doit être le jour de l’aller ou après.';
  else if (v.date_back < floor || v.date_back > hi) e.date_back = 'Choisissez une date proche du congrès (30 jours avant ou après au plus).';
  if (!v.consent) e.consent = 'Cochez cette case pour que nous puissions organiser votre voyage.';
  return { v, e };
}

// ---------------------------------------------------------------- resolution: token -> sandbox, link, enquiry, congress
// Unknown or closed tokens per IP, in memory only (no D1 write for a miss), so a crawl of /g/* stops early.
const misses = new Map();
function missBlocked(env) {
  if (env.TEST_RUN) return false;
  const win = Math.floor(Date.now() / 1000 / GRP_WINDOW);
  const e = misses.get(env.IP_HASH);
  return !!e && e.win === win && e.n >= GRP_MISS_LIMIT;
}
function noteMiss(env) {
  if (env.TEST_RUN) return;
  const win = Math.floor(Date.now() / 1000 / GRP_WINDOW);
  if (misses.size > 5000) for (const [k, v] of misses) if (v.win !== win) misses.delete(k);
  const e = misses.get(env.IP_HASH);
  if (!e || e.win !== win) misses.set(env.IP_HASH, { win, n: 1 }); else e.n += 1;
}

// Returns { state, env: the scoped env to read and write with, link, enquiry, congress } or { state: 'none' }.
export async function resolveLink(env, token) {
  if (!TOKEN_RE.test(String(token || ''))) return { state: 'none' };
  const mac = await lookupMac(env, token);
  const rows = (await env.DB.prepare('SELECT sbx, origin_sbx FROM group_links WHERE token_mac = ? LIMIT 50').bind(mac).all()).results || [];
  let scoped = null;
  const own = rows.find((r) => r.origin_sbx !== '' && r.sbx === r.origin_sbx);
  if (own) {
    if (!validSbx(own.origin_sbx)) return { state: 'none' };
    const exists = await env.DB.prepare('SELECT id FROM sandboxes WHERE id = ?').bind(own.origin_sbx).first();
    if (!exists) return { state: 'none' };
    // The link's own sandbox: reads overlay it on the seed, writes go there whoever submits.
    scoped = Object.create(env); scoped.SBX = own.origin_sbx; scoped.SBX_EFF = own.origin_sbx;
  } else if (rows.some((r) => r.sbx === '' && r.origin_sbx === '')) {
    scoped = env; // the seed link: the visiting browser's own view of the seed
  } else {
    // A link replaced by a newer one leaves a tombstone (USAB-X-001): « plus actif », not « introuvable ».
    const gone = await env.DB.prepare('SELECT sbx FROM group_replaced WHERE token_mac = ? LIMIT 1').bind(mac).first();
    return { state: gone ? 'replaced' : 'none' };
  }
  const link = await scoped.DB.prepare(`SELECT * FROM ${T(scoped, 'group_links')} WHERE 1=1 AND token_mac = ?`).bind(mac).first();
  if (!link) return { state: 'replaced' }; // the seed link, replaced by a newer link in this browser's sandbox
  const enquiry = await scoped.DB.prepare(`SELECT id, congress_id, passengers FROM ${T(scoped, 'enquiries')} WHERE 1=1 AND id = ?`).bind(link.enquiry_id).first();
  const congress = enquiry ? await scoped.DB.prepare(`SELECT id, title, start_date, end_date FROM ${T(scoped, 'congresses')} WHERE 1=1 AND id = ?`).bind(enquiry.congress_id).first() : null;
  if (!enquiry || !congress) return { state: 'none' };
  const state = linkState(link);
  return { state: state === 'active' && congress.end_date < parisToday() ? 'ended' : state, env: scoped, link, enquiry, congress, mac };
}

// ---------------------------------------------------------------- pages
const closedText = {
  none: ['Lien introuvable', 'Ce lien ne correspond à aucun voyage de groupe. Vérifiez l’adresse reçue ou demandez un nouveau lien à votre contact ASSET Voyages.', 404],
  replaced: ['Ce lien n’est plus actif', 'Ce lien n’est plus actif. Demandez le nouveau lien à votre agence.', 410],
  revoked: ['Ce lien n’est plus actif', 'L’agence a fermé ce lien. Si vous devez encore donner vos informations de voyage, demandez un nouveau lien à votre contact ASSET Voyages.', 410],
  expired: ['Ce lien a expiré', 'Les inscriptions par ce lien sont closes. Si vous devez encore donner vos informations de voyage, demandez un nouveau lien à votre contact ASSET Voyages.', 410],
  ended: ['Ce congrès est terminé', 'Les inscriptions au voyage de groupe sont closes.', 410],
  busy: ['Trop d’essais', 'Trop d’adresses essayées en peu de temps depuis cette connexion. Réessayez dans quelques minutes.', 429],
};
function closedPage(kind) {
  const [title, text, status] = closedText[kind];
  const body = html`<section class="msg"><h1 class="h1" tabindex="-1" data-focus>${title}</h1><p>${text}</p></section>`;
  return htmlResponse(groupPage({ title: `${title} | ASSET Voyages`, body }), status, NO_STORE);
}

const formPurpose = (mac) => 'group:' + mac.slice(0, 22);
async function formPage(req, env, r, token, { values, errors, notice, status = 200 } = {}) {
  const c = r.congress;
  const t = parisToday();
  const v = values || { date_out: addDays(c.start_date, -1) < t ? t : addDays(c.start_date, -1), date_back: addDays(c.end_date, 1) };
  const e = errors || {};
  const tok = await makeFormToken(env, formPurpose(r.mac));
  const body = html`
<article class="cg grp">
  ${notice ? html`<p class="alert alert--top" role="alert" tabindex="-1" data-focus>${notice}</p>` : ''}
  ${Object.keys(e).length ? html`<div class="alert--top">${errorSummary(e, GRP_LABELS, GRP_IDS)}</div>` : ''}
  <div class="cg__grid">
    <div class="cg__main">
      <h1 class="display display--cg${displayWrap(c.title)}" data-congress>${c.title}</h1>
      <p class="lead cg__when" data-dates>${frRange(c.start_date, c.end_date)}</p>
      <p class="grp__by">Voyage de groupe organisé par ASSET Voyages : chaque participant donne ici ses propres informations.</p>
    </div>
    <aside class="cg__aside" aria-labelledby="g-h">
      <h2 class="h2" id="g-h">Vos informations de voyage</h2>
      <form class="form" method="post" action="/g/${token}" novalidate>
        <input type="hidden" name="_token" value="${tok}">
        ${field({ id: 'g-name', name: 'name', label: 'Nom et prénom', hint: 'Tels qu’indiqués sur la pièce d’identité.', value: v.name, required: true, error: e.name, attrs: 'autocomplete="name" maxlength="120" autocapitalize="words" spellcheck="false"', full: true })}
        ${field({ id: 'g-email', name: 'email', label: 'E-mail', type: 'email', value: v.email, required: true, error: e.email, attrs: 'autocomplete="email" maxlength="254" inputmode="email" autocapitalize="none" spellcheck="false"', full: true })}
        ${field({ id: 'g-city', name: 'departure_city', label: 'Ville de départ', value: v.departure_city, required: true, error: e.departure_city, attrs: 'maxlength="80" autocomplete="address-level2"', full: true })}
        ${field({ id: 'g-out', name: 'date_out', label: 'Date aller', type: 'date', value: v.date_out, required: true, error: e.date_out, attrs: `min="${t}"` })}
        ${field({ id: 'g-back', name: 'date_back', label: 'Date retour', type: 'date', value: v.date_back, required: true, error: e.date_back, attrs: `min="${t}"` })}
        <div class="hp" aria-hidden="true"><label for="g-zx">Laisser vide</label><input id="g-zx" name="zx_confirm" tabindex="-1" autocomplete="off" data-lpignore="true" data-1p-ignore></div>
        <div class="field field--full field--check${e.consent ? ' field--err' : ''}">
          <label class="check" for="g-consent"><input type="checkbox" id="g-consent" name="consent" value="1"${v.consent ? raw(' checked') : ''}${e.consent ? raw(' aria-invalid="true" aria-describedby="g-consent-e"') : ''} required>
          <span>J’accepte qu’ASSET Voyages utilise ces informations uniquement pour organiser le voyage de groupe de ce congrès. <span class="req" aria-hidden="true">*</span></span></label>
          ${e.consent ? html`<p class="err" id="g-consent-e">${e.consent}</p>` : ''}
        </div>
        <p class="form__legend field--full"><span class="req" aria-hidden="true">*</span> Champ obligatoire. Aucune autre donnée n’est demandée : ni numéro de passeport, ni date de naissance, ni information de santé.</p>
        <div class="form__actions"><button class="btn btn--wide" type="submit">Envoyer mes informations</button></div>
      </form>
    </aside>
    <div class="grp__more">
      <ol class="grp__steps">
        <li>Indiquez vos nom et prénom exactement comme sur la pièce d’identité de votre voyage.</li>
        <li>Choisissez votre ville de départ et vos dates.</li>
        <li>Envoyez : l’agence prépare les billets du groupe et revient vers vous.</li>
      </ol>
      <p class="quiet">Pour corriger vos informations, renvoyez le formulaire depuis ce même téléphone avec le même e-mail. Depuis un autre appareil, l’agence vérifie la modification avant de l’appliquer.</p>
    </div>
  </div>
  <section class="grp__privacy" aria-labelledby="g-p"><h2 class="h4" id="g-p">Vos données</h2>
    <p class="quiet">Responsable : ASSET Voyages. Usage : réserver les vols du groupe de ce congrès, rien d’autre ; ni publication ni revente. Seule l’équipe de l’agence voit la liste ; les autres participants ne voient pas vos informations. Conservation : jusqu’à la fin du voyage (dans cette démonstration, effacement chaque nuit). Accès, correction ou effacement : confidentialite@example.com (adresse d’exemple).</p>
  </section>
</article>`;
  return htmlResponse(groupPage({ title: `Voyage de groupe : ${c.title} | ASSET Voyages`, body }), status, NO_STORE);
}

const confirmSig = (env, mac, id, exp) => hmac(env, 'group-v1', JSON.stringify(['merci', mac, id, exp]));
async function confirmUrl(env, token, mac, id) {
  const exp = Math.floor(Date.now() / 1000) + CONFIRM_TTL;
  return `/g/${token}/merci?d=${encodeURIComponent(id)}.${exp}.${await confirmSig(env, mac, id, exp)}`;
}

export async function groupRoute(req, env, token, sub) {
  const m = req.method;
  if (missBlocked(env)) return closedPage('busy');
  if (m !== 'GET' && m !== 'HEAD' && !(m === 'POST' && !sub)) return new Response('Méthode non autorisée', { status: 405, headers: { allow: 'GET, POST' } });
  const r = await resolveLink(env, token);
  if (r.state !== 'active') {
    if (r.state === 'none') noteMiss(env);
    return closedPage(r.state);
  }
  if (sub === 'merci') return thanks(req, r, token);
  if (m === 'POST') return submit(req, r, token);
  return formPage(req, r.env, r, token);
}

async function submit(req, r, token) {
  const env = r.env;
  const form = await readForm(req);
  if (form.error) return closedPageStatus(form.error);
  const { v, e } = validateDelegate(form.get, r.congress);
  const tok = await checkFormToken(env, formPurpose(r.mac), form.get('_token'), { minMs: MIN_FILL_MS });
  if ((!tok.ok && tok.why === 'invalid') || !sameOrigin(req)) return formPage(req, env, r, token, { values: v, notice: 'Le formulaire n’a pas pu être vérifié : vos informations n’ont pas été envoyées. Vérifiez-les puis renvoyez le formulaire.', status: 403 });
  if (form.get('zx_confirm')) return redirect(`/g/${token}/merci`); // honeypot: looks like a success, stores nothing
  if (!tok.ok && tok.why === 'fast') return formPage(req, env, r, token, { values: v, errors: e, notice: 'Vos informations n’ont pas été envoyées : le formulaire a été validé trop vite. Relisez-le puis cliquez de nouveau sur « Envoyer mes informations ».' });
  if (!tok.ok) return formPage(req, env, r, token, { values: v, errors: e, notice: 'Vos informations n’ont pas été envoyées : le formulaire a expiré. Vérifiez-les puis renvoyez-le.' });
  if (Object.keys(e).length) return formPage(req, env, r, token, { values: v, errors: e });
  // Per-IP limit of the public route (the test-run key skips per-IP caps only, as everywhere else).
  if (!env.TEST_RUN && !(await rateHit(env, `grp:${env.IP_HASH}`, GRP_IP_LIMIT, GRP_WINDOW))) {
    return formPage(req, env, r, token, { values: v, notice: 'Vos informations n’ont pas été envoyées : trop d’envois depuis cette connexion en 10 minutes. Réessayez dans quelques minutes.', status: 429 });
  }
  const key = emailNorm(v.email);
  const prior = await env.DB.prepare(`SELECT id, owner FROM ${T(env, 'group_delegates')} WHERE 1=1 AND enquiry_id = ? AND email_norm = ?`).bind(r.enquiry.id, key).first();
  const rid = (await delegateCookieId(env, req)) || randomToken(16);
  const owner = await ownerHash(env, rid);
  const owned = !!(prior && prior.owner && safeEqual(prior.owner, owner));
  const cap = delegateCap(r.enquiry.passengers);
  const count = async (t) => (await env.DB.prepare(`SELECT COUNT(email_norm) AS n FROM ${T(env, t)} WHERE 1=1 AND enquiry_id = ?`).bind(r.enquiry.id).first()).n;
  // SEC-X-008: the outcome never depends on whether the e-mail is registered. Direct write: the owner's own update, or a
  // new e-mail below the cap. Everything else (a registered e-mail from another browser, a new e-mail once the list is
  // full) becomes a pending change with the same redirect, cookie and page. Only when the pending list is full as well
  // is the answer refused, with one message for both cases.
  const direct = owned || (!prior && (await count('group_delegates')) < cap);
  if (!direct) {
    const already = await env.DB.prepare(`SELECT 1 AS x FROM ${T(env, 'group_pending')} WHERE 1=1 AND enquiry_id = ? AND email_norm = ?`).bind(r.enquiry.id, key).first();
    if (!already && (await count('group_pending')) >= cap) return formPage(req, env, r, token, { values: v, notice: 'Vos informations n’ont pas été envoyées : la liste de ce groupe est complète. Contactez votre interlocuteur ASSET Voyages.' });
  }
  // SEC-X-016: the form token is single-use, like the enquiry form's. Its nonce is burnt atomically (kept 2 h, the
  // token's own lifetime, then purged nightly with the other expired nonces); a replay stores nothing.
  const burnt = await env.DB.prepare('INSERT INTO revoked (n, exp) VALUES (?, ?) ON CONFLICT(n) DO NOTHING RETURNING n')
    .bind('g:' + tok.nonce, Math.floor(Date.now() / 1000) + 2 * 3600 + 60).first();
  if (!burnt) return formPage(req, env, r, token, { values: v, notice: 'Ce formulaire a déjà été envoyé : vos informations n’ont pas été envoyées une seconde fois. Pour répondre de nouveau, renvoyez le formulaire ci-dessous.' });
  let sid;
  try { sid = await claim(env); } catch (err) { // global budget, then the link's sandbox throttle (or this browser's, seed link)
    if (err && err.code === 'SBX_LIMIT') return formPage(req, env, r, token, { values: v, notice: `Vos informations n’ont pas été envoyées. ${DEMO_BUSY}` });
    if (err && err.code === 'WRITE_PAUSE') return formPage(req, env, r, token, { values: v, notice: `Vos informations n’ont pas été envoyées. ${DEMO_PAUSE}` });
    throw err;
  }
  const now = nowIso();
  // The delegate cookie is (re)sent on every accepted answer, new or not, so its presence reveals nothing.
  const cookie = { 'set-cookie': `${DLG_COOKIE}=${rid}.${await hmac(env, 'delegate-v1', 'cookie|' + rid)}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=${DLG_MAX_AGE}` };
  let id;
  if (direct) {
    // New entry, or the browser that created it: write directly. A seed delegate's row keeps its id (the sandbox row hides the seed row).
    id = prior ? prior.id : randomToken(9);
    await env.DB.prepare(`INSERT INTO group_delegates (sbx, enquiry_id, email_norm, id, name, email, departure_city, date_out, date_back, consent_at, created_at, updated_at, owner)
      VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT (sbx, enquiry_id, email_norm) DO UPDATE SET name = excluded.name, email = excluded.email,
      departure_city = excluded.departure_city, date_out = excluded.date_out, date_back = excluded.date_back, consent_at = excluded.consent_at, updated_at = excluded.updated_at`)
      .bind(sid, r.enquiry.id, key, id, v.name, v.email, v.departure_city, v.date_out, v.date_back, now, now, now, prior ? prior.owner : owner).run();
  } else {
    // A registered e-mail from another browser, or a new one once the list is full: never written directly. The change
    // waits for staff (« Modification à vérifier »).
    id = randomToken(9);
    await env.DB.prepare(`INSERT INTO group_pending (sbx, enquiry_id, email_norm, id, name, email, departure_city, date_out, date_back, consent_at, created_at)
      VALUES (?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT (sbx, enquiry_id, email_norm) DO UPDATE SET id = excluded.id, name = excluded.name, email = excluded.email,
      departure_city = excluded.departure_city, date_out = excluded.date_out, date_back = excluded.date_back, consent_at = excluded.consent_at, created_at = excluded.created_at`)
      .bind(sid, r.enquiry.id, key, id, v.name, v.email, v.departure_city, v.date_out, v.date_back, now, now).run();
  }
  return redirect(await confirmUrl(env, token, r.mac, id), cookie);
}

// ---------------------------------------------------------------- delegate cookie (delegate-v1)
// The cookie carries a random browser id and its MAC; the entry stores only HMAC(delegate-v1, 'owner|' + id).
export const DLG_COOKIE = '__Host-av_dlg';
const DLG_MAX_AGE = 60 * 86400;
export const ownerHash = (env, rid) => hmac(env, 'delegate-v1', 'owner|' + rid);
export async function delegateCookieId(env, req) {
  const m = /^([A-Za-z0-9_-]{22})\.([A-Za-z0-9_-]{43})$/.exec(getCookie(req, DLG_COOKIE) || '');
  if (!m) return null;
  return safeEqual(m[2], await hmac(env, 'delegate-v1', 'cookie|' + m[1])) ? m[1] : null;
}
function closedPageStatus(status) {
  const body = html`<section class="msg"><h1 class="h1" tabindex="-1" data-focus>Envoi refusé</h1><p>Le formulaire envoyé est trop volumineux ou mal formé : vos informations n’ont pas été enregistrées.</p></section>`;
  return htmlResponse(groupPage({ title: 'Envoi refusé | ASSET Voyages', body }), status, NO_STORE);
}

// The confirmation shows the delegate's own entry only, through a signed, short-lived reference; never anyone else's.
async function thanks(req, r, token) {
  const env = r.env;
  const d = new URL(req.url).searchParams.get('d') || '';
  const mm = /^([A-Za-z0-9_-]{8,16})\.(\d{10})\.([A-Za-z0-9_-]{43})$/.exec(d);
  let row = null;
  if (mm && +mm[2] > Math.floor(Date.now() / 1000) && safeEqual(mm[3], await confirmSig(env, r.mac, mm[1], +mm[2]))) {
    // The same page whether the answer was stored or is waiting for a check: it shows what this person sent, nothing more.
    for (const t of ['group_pending', 'group_delegates']) {
      row = row || await env.DB.prepare(`SELECT name, email, departure_city, date_out, date_back FROM ${T(env, t)} WHERE 1=1 AND enquiry_id = ? AND id = ?`).bind(r.enquiry.id, mm[1]).first();
    }
  }
  const body = html`<section class="thanks grp-thanks">
    <h1 class="display" tabindex="-1" data-focus>Votre réponse a bien été reçue.</h1>
    <p class="lead">Voyage de groupe : ${r.congress.title}, ${frRange(r.congress.start_date, r.congress.end_date)}. L’agence ASSET Voyages revient vers vous avec votre billet.</p>
    ${row ? html`<dl class="facts" data-own>
      <div><dt>Nom et prénom</dt><dd>${row.name}</dd></div>
      <div><dt>E-mail</dt><dd>${row.email}</dd></div>
      <div><dt>Ville de départ</dt><dd>${row.departure_city}</dd></div>
      <div><dt>Aller</dt><dd>${frNumDate(row.date_out)}</dd></div>
      <div><dt>Retour</dt><dd>${frNumDate(row.date_back)}</dd></div>
    </dl>
    <p class="quiet">Une erreur ? Renvoyez le formulaire depuis ce même téléphone avec le même e-mail.</p>` : ''}
    <p><a class="btn btn--line" href="/g/${token}">Revenir au formulaire</a></p>
  </section>`;
  return htmlResponse(groupPage({ title: 'Informations enregistrées | ASSET Voyages', body }), 200, NO_STORE);
}
