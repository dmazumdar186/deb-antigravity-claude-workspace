// Visitor side: catalogue, congress page, flight enquiry. Server-rendered, works without JavaScript.
import {
  html, raw, today, addDays, isIsoDate, frRange, frDate, rangeParts, norm, clean, MOIS_LONG,
  readForm, makeFormToken, checkFormToken, ipHash, rateHit, redirect, htmlResponse, nowIso, hmac, safeEqual,
} from './lib.js';
import { publicPage, field, errorPage } from './views.js';
import { notificationFor, TEAM_INBOX } from './data.js';

const PER_PAGE = 9;
const MIN_FILL_MS = 3000;
export const ENQ_LIMIT = 5; // accepted enquiries per IP hash per window
export const ENQ_WINDOW = 600;

function catalogueQuery(sp) {
  const q = clean(sp.get('q'), 200).slice(0, 200);
  const d = clean(sp.get('discipline'), 80).slice(0, 80);
  const pays = clean(sp.get('pays'), 80).slice(0, 80);
  const mois = /^\d{4}-\d{2}$/.test(sp.get('mois') || '') ? sp.get('mois') : '';
  const page = Math.max(1, Math.min(1000, parseInt(sp.get('page') || '1', 10) || 1));
  return { q, d, pays, mois, page };
}
function qs(f, over = {}) {
  const p = new URLSearchParams();
  const v = { ...f, ...over };
  if (v.q) p.set('q', v.q);
  if (v.d) p.set('discipline', v.d);
  if (v.pays) p.set('pays', v.pays);
  if (v.mois) p.set('mois', v.mois);
  if (v.page && v.page > 1) p.set('page', String(v.page));
  const s = p.toString();
  return s ? `/?${s}` : '/';
}
const monthLabel = (ym) => { const [y, m] = ym.split('-').map(Number); return `${MOIS_LONG[m - 1]} ${y}`; };

export async function catalogue(req, env) {
  const url = new URL(req.url);
  const f = catalogueQuery(url.searchParams);
  const t = today();
  const base = `FROM congresses WHERE status = 'publie' AND end_date >= ?`;
  const all = (await env.DB.prepare(`SELECT discipline, country, substr(start_date,1,7) AS ym ${base}`).bind(t).all()).results || [];
  const uniq = (k) => [...new Set(all.map((r) => r[k]))].sort((a, b) => a.localeCompare(b, 'fr'));
  const disciplines = uniq('discipline');
  const countries = uniq('country');
  const months = [...new Set(all.map((r) => r.ym))].sort();

  let where = base; const binds = [t];
  for (const word of norm(f.q).split(/\s+/).filter(Boolean).slice(0, 8)) {
    where += ' AND instr(search_text, ?) > 0'; // instr: no LIKE pattern limits, no wildcard escaping
    binds.push(word);
  }
  if (f.d) { where += ' AND discipline = ?'; binds.push(f.d); }
  if (f.pays) { where += ' AND country = ?'; binds.push(f.pays); }
  if (f.mois) { where += ' AND substr(start_date,1,7) = ?'; binds.push(f.mois); }
  const total = (await env.DB.prepare(`SELECT COUNT(*) AS n ${where}`).bind(...binds).first()).n;
  const pages = Math.max(1, Math.ceil(total / PER_PAGE));
  const page = Math.min(f.page, pages);
  const rows = (await env.DB.prepare(`SELECT ref, slug, title, discipline, city, country, start_date, end_date ${where} ORDER BY start_date, id LIMIT ? OFFSET ?`)
    .bind(...binds, PER_PAGE, (page - 1) * PER_PAGE).all()).results || [];
  const filtered = f.q || f.d || f.pays || f.mois;

  const chip = (label, value) => {
    const on = f.d === value;
    return html`<li><a class="chip" href="${qs(f, { d: on ? '' : value, page: 1 })}"${on ? raw(' aria-current="true"') : ''}>${label}</a></li>`;
  };
  const body = html`
<section class="cat">
  <header class="cat__head">
    <h1 class="display">Trouver son congrès. Demander son vol.</h1>
    <p class="lead">Chaque fiche indique sa source officielle et sa date de vérification ; la demande de vol se fait depuis la fiche.</p>
  </header>
  <div class="cat__grid">
    <form class="filters" method="get" action="/" role="search" aria-label="Filtrer les congrès">
      <div class="field"><label for="q">Recherche</label><input id="q" name="q" type="search" value="${f.q}" placeholder="Nom, ville ou discipline" maxlength="200" enterkeyhint="search" autocomplete="off"></div>
      ${f.d ? html`<input type="hidden" name="discipline" value="${f.d}">` : ''}
      <div class="field"><label for="pays">Pays</label><select id="pays" name="pays" data-autosubmit>
        <option value="">Tous les pays</option>${countries.map((c) => html`<option value="${c}"${c === f.pays ? raw(' selected') : ''}>${c}</option>`)}
      </select></div>
      <div class="field"><label for="mois">Mois</label><select id="mois" name="mois" data-autosubmit>
        <option value="">Tous les mois</option>${months.map((m) => html`<option value="${m}"${m === f.mois ? raw(' selected') : ''}>${monthLabel(m)}</option>`)}
      </select></div>
      <div class="filters__actions"><button class="btn" type="submit">Rechercher</button>${filtered ? html`<a class="lnk" href="/">Réinitialiser</a>` : ''}</div>
      <fieldset class="disc"><legend>Discipline</legend>
        <ul class="chips">${chip('Toutes', '')}${disciplines.map((d) => chip(d, d))}</ul>
      </fieldset>
    </form>
    <div class="list">
      <p class="bar" aria-live="polite"><span class="bar__n">${total === 0 ? 'Aucun congrès trouvé' : `${total} congrès${filtered ? (total > 1 ? ' trouvés' : ' trouvé') : ''}`}</span><span>Triés par date</span></p>
      ${rows.length ? html`<ol class="rows">${rows.map((r) => { const rp = rangeParts(r.start_date, r.end_date); return html`
        <li class="row"><a class="row__a" href="/congres/${r.slug}">
          <span class="row__date"><span class="row__days">${rp.days}</span><span class="row__months">${rp.months}</span></span>
          <span class="row__main"><span class="row__t">${r.title}</span><span class="row__d">${r.discipline}</span></span>
          <span class="row__place">${r.city}, ${r.country}</span>
          <span class="row__go">Voir la fiche</span>
        </a></li>`; })}</ol>`
      : html`<div class="empty" role="status"><h2 class="h2">Aucun congrès ne correspond.</h2><p>Essayez un autre mot, une autre discipline ou un autre mois. Un congrès absent du catalogue ? Nos conseillers le cherchent pour vous.</p><p><a class="btn btn--line" href="/">Réinitialiser la recherche</a></p></div>`}
      ${pages > 1 ? html`<nav class="pager" aria-label="Pages du catalogue">
        ${page > 1 ? html`<a class="pager__step" href="${qs(f, { page: page - 1 })}" rel="prev">Page précédente</a>` : ''}
        <ol>${Array.from({ length: pages }, (_, i) => i + 1).map((n) => html`<li><a href="${qs(f, { page: n })}"${n === page ? raw(' aria-current="page"') : ''} aria-label="Page ${n}">${n}</a></li>`)}</ol>
        ${page < pages ? html`<a class="pager__step" href="${qs(f, { page: page + 1 })}" rel="next">Page suivante</a>` : ''}
      </nav>` : ''}
    </div>
  </div>
</section>`;
  return htmlResponse(publicPage({ title: 'Catalogue des congrès | ASSET Voyages', body }), 200, { 'cache-control': 'no-cache' });
}

async function loadPublicCongress(env, where, bind) {
  return env.DB.prepare(`SELECT c.*, g.status AS gme_status, g.valid_from AS gme_from, g.valid_to AS gme_to
    FROM congresses c LEFT JOIN gme_codes g ON g.congress_id = c.id WHERE c.status = 'publie' AND ${where}`).bind(bind).first();
}
export const gmeOnSale = (c, t = today()) => c.gme_status === 'approuve' && (!c.gme_from || c.gme_from <= t) && (!c.gme_to || c.gme_to >= t);

export async function congressPage(req, env, slug, { values, errors, notice, status = 200 } = {}) {
  const c = typeof slug === 'object' ? slug : await loadPublicCongress(env, 'c.slug = ?', slug);
  if (!c) return htmlResponse(errorPage({ status: 404, title: 'Congrès introuvable', text: 'Cette fiche n’existe pas ou n’est pas publiée.' }), 404);
  const t = today();
  const past = c.end_date < t;
  const v = values || { date_out: c.start_date > t ? addDays(c.start_date, -1) < t ? t : addDays(c.start_date, -1) : '', date_back: addDays(c.end_date, 1), passengers: '1' };
  const e = errors || {};
  const token = await makeFormToken(env, 'enquiry');
  const errCount = Object.keys(e).length;
  const body = html`
<article class="cg">
  <nav class="crumbs" aria-label="Fil d’Ariane"><a href="/">Catalogue des congrès</a><span aria-hidden="true">/</span><span>${c.ref}</span></nav>
  <div class="cg__grid">
    <div class="cg__main">
      <h1 class="display display--cg">${c.title}</h1>
      <p class="lead cg__when">${frRange(c.start_date, c.end_date)}, ${c.city} (${c.country})</p>
      ${gmeOnSale(c, t) ? html`<p class="gme-note">Tarif congrès négocié disponible : appliqué à votre devis.</p>` : ''}
      <dl class="facts">
        <div><dt>Dates</dt><dd>Du ${frDate(c.start_date)} au ${frDate(c.end_date)}</dd></div>
        <div><dt>Ville</dt><dd>${c.city}</dd></div>
        <div><dt>Pays</dt><dd>${c.country}</dd></div>
        <div><dt>Discipline</dt><dd>${c.discipline}</dd></div>
        <div><dt>Lieu</dt><dd>${c.venue}</dd></div>
        <div><dt>Site officiel</dt><dd><a href="${c.official_url}" rel="noopener noreferrer nofollow" class="lnk">${c.official_url.replace(/^https?:\/\//, '')}</a></dd></div>
        <div><dt>Vérifié le</dt><dd>${frDate(c.verified_on)}</dd></div>
        <div><dt>Référence</dt><dd>${c.ref}</dd></div>
      </dl>
      <div class="prose"><p>${c.description}</p></div>
    </div>
    <aside class="cg__aside" id="demande" aria-labelledby="dem-h">
      <h2 class="h2" id="dem-h">Demander un devis de vol</h2>
      ${past ? html`<p>Ce congrès est terminé : la demande de vol n’est plus ouverte.</p>` : html`
      <p class="aside__lead">Un conseiller ASSET prépare votre devis au départ de la ville de votre choix.</p>
      ${notice ? html`<p class="alert" role="alert">${notice}</p>` : ''}
      ${errCount ? html`<p class="alert" role="alert" id="form-errors" tabindex="-1">${errCount > 1 ? `${errCount} champs à corriger` : 'Un champ à corriger'} : les messages sont sous chaque champ.</p>` : ''}
      <form class="form" method="post" action="/demande" novalidate>
        <input type="hidden" name="_token" value="${token}">
        <input type="hidden" name="congress" value="${c.id}">
        <div class="field field--full"><label for="f-cg">Congrès</label><input id="f-cg" value="${c.title}, ${frRange(c.start_date, c.end_date)}" readonly aria-readonly="true" tabindex="-1"></div>
        ${field({ id: 'f-name', name: 'name', label: 'Nom et prénom', value: v.name, required: true, error: e.name, attrs: 'autocomplete="name" maxlength="120"', full: true })}
        ${field({ id: 'f-email', name: 'email', label: 'E-mail', type: 'email', value: v.email, required: true, error: e.email, attrs: 'autocomplete="email" maxlength="254" inputmode="email"' })}
        ${field({ id: 'f-phone', name: 'phone', label: 'Téléphone', type: 'tel', value: v.phone, required: true, error: e.phone, attrs: 'autocomplete="tel" maxlength="30"' })}
        ${field({ id: 'f-company', name: 'company', label: 'Société', value: v.company, optional: true, error: e.company, attrs: 'autocomplete="organization" maxlength="120"', full: true })}
        ${field({ id: 'f-city', name: 'departure_city', label: 'Ville de départ', value: v.departure_city, required: true, error: e.departure_city, attrs: 'maxlength="80" autocomplete="address-level2"', full: true })}
        ${field({ id: 'f-out', name: 'date_out', label: 'Date aller', type: 'date', value: v.date_out, required: true, error: e.date_out, attrs: `min="${t}"` })}
        ${field({ id: 'f-back', name: 'date_back', label: 'Date retour', type: 'date', value: v.date_back, required: true, error: e.date_back, attrs: `min="${t}"` })}
        ${field({ id: 'f-pax', name: 'passengers', label: 'Passagers', type: 'number', value: v.passengers, required: true, error: e.passengers, hint: 'De 1 à 50 personnes.', attrs: 'min="1" max="50" step="1" inputmode="numeric"' })}
        ${field({ id: 'f-msg', name: 'message', label: 'Message', type: 'textarea', value: v.message, optional: true, error: e.message, attrs: 'rows="3" maxlength="2000"', full: true })}
        <div class="hp" aria-hidden="true"><label for="f-web">Ne pas remplir ce champ</label><input id="f-web" name="website" tabindex="-1" autocomplete="off"></div>
        <div class="field field--full field--check${e.consent ? ' field--err' : ''}">
          <label class="check" for="f-consent"><input type="checkbox" id="f-consent" name="consent" value="1"${v.consent ? raw(' checked') : ''}${e.consent ? raw(' aria-invalid="true" aria-describedby="f-consent-e"') : ''} required>
          <span>J’accepte qu’ASSET Voyages utilise ces informations pour répondre à ma demande. Elles ne sont ni publiées ni revendues. <span class="req" aria-hidden="true">*</span></span></label>
          ${e.consent ? html`<p class="err" id="f-consent-e">${e.consent}</p>` : ''}
        </div>
        <p class="form__legend"><span class="req" aria-hidden="true">*</span> Champ obligatoire.</p>
        <div class="form__actions"><button class="btn btn--wide" type="submit">Envoyer la demande</button></div>
      </form>`}
    </aside>
  </div>
</article>`;
  return htmlResponse(publicPage({ title: `${c.title} | ASSET Voyages`, description: `${c.title} : ${frRange(c.start_date, c.end_date)}, ${c.city}. Demande de devis vol.`, body }), status, { 'cache-control': 'no-store' });
}

const EMAIL_RE = /^[^\s@<>()",;:]{1,64}@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$/;
export function validateEnquiry(get, t = today()) {
  const v = {
    name: clean(get('name'), 120), email: clean(get('email'), 254), phone: clean(get('phone'), 30), company: clean(get('company'), 120),
    departure_city: clean(get('departure_city'), 80), date_out: clean(get('date_out'), 10), date_back: clean(get('date_back'), 10),
    passengers: clean(get('passengers'), 6), message: clean(get('message'), 2000), consent: get('consent') === '1',
  };
  const e = {};
  const req = (k, label, max) => {
    if (!v[k]) e[k] = `Indiquez ${label}.`;
    else if (v[k].length > max) e[k] = `${max} caractères au maximum.`;
  };
  req('name', 'votre nom', 120);
  if (!v.email) e.email = 'Indiquez votre e-mail.';
  else if (v.email.length > 254 || !EMAIL_RE.test(v.email)) e.email = 'Cette adresse e-mail n’est pas valide (exemple : prenom.nom@societe.fr).';
  req('phone', 'un numéro de téléphone', 30);
  if (!e.phone && !/^[0-9+().\s-]{6,30}$/.test(v.phone)) e.phone = 'Utilisez uniquement des chiffres, espaces et les signes + ( ) . -';
  if (v.company.length > 120) e.company = '120 caractères au maximum.';
  req('departure_city', 'votre ville de départ', 80);
  if (!v.date_out) e.date_out = 'Indiquez la date aller.';
  else if (!isIsoDate(v.date_out)) e.date_out = 'Date invalide.';
  else if (v.date_out < t) e.date_out = 'La date aller ne peut pas être passée.';
  else if (v.date_out > addDays(t, 730)) e.date_out = 'Date trop lointaine (deux ans au maximum).';
  if (!v.date_back) e.date_back = 'Indiquez la date retour.';
  else if (!isIsoDate(v.date_back)) e.date_back = 'Date invalide.';
  else if (v.date_back < t) e.date_back = 'La date retour ne peut pas être passée.';
  else if (!e.date_out && v.date_back < v.date_out) e.date_back = 'La date retour doit être le jour de l’aller ou après.';
  else if (v.date_back > addDays(t, 760)) e.date_back = 'Date trop lointaine.';
  if (!/^\d{1,3}$/.test(v.passengers)) e.passengers = 'Indiquez un nombre de passagers entre 1 et 50.';
  else if (+v.passengers < 1 || +v.passengers > 50) e.passengers = 'Le nombre de passagers doit être compris entre 1 et 50. Au-delà, contactez-nous pour un groupe.';
  if (v.message.length > 2000) e.message = '2 000 caractères au maximum.';
  if (!v.consent) e.consent = 'Cochez cette case pour que nous puissions vous répondre.';
  return { v, e };
}

export async function submitEnquiry(req, env) {
  const form = await readForm(req);
  if (form.error) return htmlResponse(errorPage({ status: form.error, title: 'Demande refusée', text: 'Le formulaire envoyé est trop volumineux ou mal formé.' }), form.error);
  const cid = parseInt(form.get('congress'), 10);
  const c = Number.isFinite(cid) ? await loadPublicCongress(env, 'c.id = ?', cid) : null;
  if (!c || c.end_date < today()) return htmlResponse(errorPage({ status: 404, title: 'Congrès introuvable', text: 'Ce congrès n’est pas ou plus ouvert aux demandes.' }), 404);
  const { v, e } = validateEnquiry(form.get);

  const tok = await checkFormToken(env, 'enquiry', form.get('_token'), { minMs: MIN_FILL_MS });
  if (!tok.ok && tok.why === 'invalid') return congressPage(req, env, c, { values: v, errors: {}, notice: 'Le formulaire n’a pas pu être vérifié. Vérifiez vos informations puis renvoyez-le.', status: 403 });
  // Honeypot: answer like a success, store nothing.
  if (form.get('website')) return redirect('/demande/confirmation');
  if (tok.nonce) {
    const prior = await env.DB.prepare('SELECT ref FROM enquiries WHERE form_nonce = ?').bind(tok.nonce).first();
    if (prior) return redirect(await confirmUrl(env, prior.ref));
  }
  if (!tok.ok && tok.why === 'fast') return congressPage(req, env, c, { values: v, errors: e, notice: 'Envoi trop rapide : relisez le formulaire puis envoyez-le à nouveau.', status: 429 });
  if (!tok.ok) return congressPage(req, env, c, { values: v, errors: e, notice: 'Le formulaire a expiré. Vérifiez vos informations puis renvoyez-le.', status: 400 });
  if (Object.keys(e).length) return congressPage(req, env, c, { values: v, errors: e, status: 422 });

  const ip = await ipHash(env, req);
  if (!(await rateHit(env, 'enq:' + ip, ENQ_LIMIT, ENQ_WINDOW))) {
    return congressPage(req, env, c, { values: v, errors: {}, notice: 'Trop de demandes envoyées depuis cette connexion. Merci de réessayer dans quelques minutes ou d’appeler l’agence.', status: 429 });
  }
  const now = nowIso();
  let row;
  try {
    row = await env.DB.prepare(`INSERT INTO enquiries (ref, congress_id, name, email, phone, company, departure_city, date_out, date_back, passengers, message, consent_at, status, form_nonce, ip_hash, created_at, updated_at)
      VALUES (?,?,?,?,?,?,?,?,?,?,?,?, 'nouvelle', ?,?,?,?) RETURNING id`)
      .bind('tmp-' + tok.nonce, c.id, v.name, v.email, v.phone, v.company, v.departure_city, v.date_out, v.date_back, +v.passengers, v.message, now, tok.nonce, ip, now, now).first();
  } catch (err) {
    const prior = await env.DB.prepare('SELECT ref FROM enquiries WHERE form_nonce = ?').bind(tok.nonce).first();
    if (prior) return redirect(await confirmUrl(env, prior.ref));
    throw err;
  }
  const ref = `DV-${now.slice(0, 4)}-${String(row.id).padStart(4, '0')}`;
  const n = notificationFor({ id: row.id, ref, ...v, passengers: +v.passengers }, c);
  await env.DB.batch([
    env.DB.prepare('UPDATE enquiries SET ref = ? WHERE id = ?').bind(ref, row.id),
    env.DB.prepare(`INSERT INTO enquiry_events (enquiry_id, at, user_id, kind, from_val, to_val) VALUES (?, ?, NULL, 'creation', NULL, 'nouvelle')`).bind(row.id, now),
    env.DB.prepare('INSERT INTO notifications (enquiry_id, at, to_addr, subject, body) VALUES (?,?,?,?,?)').bind(row.id, now, TEAM_INBOX, n.subject, n.body),
  ]);
  return redirect(await confirmUrl(env, ref));
}

// The confirmation link is signed so nobody can enumerate references from the public site.
const confirmSig = async (env, ref) => (await hmac(env, 'confirm|' + ref)).slice(0, 22);
async function confirmUrl(env, ref) {
  return `/demande/confirmation?ref=${encodeURIComponent(ref)}&k=${await confirmSig(env, ref)}`;
}
export async function confirmation(req, env) {
  const sp = new URL(req.url).searchParams;
  const ref = sp.get('ref') || '';
  const row = /^DV-\d{4}-\d{4,6}$/.test(ref) && safeEqual(sp.get('k') || '', await confirmSig(env, ref))
    ? await env.DB.prepare('SELECT e.ref, c.title, c.slug FROM enquiries e JOIN congresses c ON c.id = e.congress_id WHERE e.ref = ?').bind(ref).first()
    : null;
  const body = html`<section class="thanks">
    <h1 class="display">Merci, votre demande est enregistrée.</h1>
    ${row ? html`<p class="lead">Votre référence</p><p class="ref" data-ref>${row.ref}</p>
      <p>Demande de devis vol pour <a class="lnk" href="/congres/${row.slug}">${row.title}</a>. Un conseiller ASSET vous recontacte avec une proposition ; gardez cette référence pour tout échange.</p>`
      : html`<p class="lead">Un conseiller ASSET vous recontacte avec une proposition.</p>`}
    <p><a class="btn btn--line" href="/">Retour au catalogue</a></p>
  </section>`;
  return htmlResponse(publicPage({ title: 'Demande enregistrée | ASSET Voyages', body }), 200, { 'cache-control': 'no-store' });
}
