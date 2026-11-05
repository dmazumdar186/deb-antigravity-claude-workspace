// Staff console: sessions, roles, congresses, enquiries, notifications, GM&E codes and their authorisation.
import {
  html, raw, esc, today, nowIso, isIsoDate, frRange, frNumDate, frDateTime, clean, norm, slugify,
  readForm, sameOrigin, makeFormToken, checkFormToken, ipHash, rateHit, rateBlocked, redirect, htmlResponse,
  getCookie, sha256hex, randomToken, safeEqual, hashPassword, encryptCode, decryptCode, csvCell,
} from './lib.js';
import { consolePage, loginPage, errorPage, field, select, pill, csrfInput, errorSummary } from './views.js';
import { STATUS_LABELS, STATUS_PLURAL, CG_STATUS, GME_STATUS, congressSearch, congressSlug, resetSandbox, materialize, nbsp } from './data.js';

export const COOKIE = '__Host-av_session';
const SESSION_TTL = 8 * 3600;
const GRANT_HOURS = 24;
const MASK = '•••• •••• ••••';
// Only a checked code can be shown or requested: « Détecté » is unverified, « Expiré » is no longer sellable.
const REVEALABLE = ['verifie', 'approuve'];
const STAFF = ['direction', 'equipe'];
const ALL = ['direction', 'equipe', 'contributeur'];
const ST_KIND = { nouvelle: 'new', qualifiee: 'wip', devis: 'wip', gagnee: 'done', perdue: 'lost' };
const CG_KIND = { brouillon: 'draft', a_relire: 'rev', publie: 'pub', archive: 'arch' };
const GME_KIND = { detecte: 'draft', verifie: 'rev', approuve: 'pub', expire: 'arch' };
const CG_PLURAL = { brouillon: 'Brouillons', a_relire: 'À relire', publie: 'Publiés', archive: 'Archivés' };
const NO_STORE = { 'cache-control': 'no-store, private' };
const nw = (t) => html`<span class="nw">${t}</span>`;


// ---------------------------------------------------------------- sessions
async function getSession(req, env) {
  const tok = getCookie(req, COOKIE);
  if (!tok || tok.length > 100) return null;
  const id = await sha256hex(tok);
  const row = await env.DB.prepare(`SELECT s.csrf, s.expires_at, u.id, u.username, u.display_name, u.role FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.id = ?`).bind(id).first();
  if (!row || row.expires_at < Math.floor(Date.now() / 1000)) return null;
  return { sid: id, csrf: row.csrf, user: { id: row.id, username: row.username, display_name: row.display_name, role: row.role } };
}
const cookie = (val, maxAge) => `${COOKIE}=${val}; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=${maxAge}`;

// At phone width each table row becomes a card: every cell gets its column name as data-label.
function labelTables(markup) {
  return markup.replace(/<table class="tbl">([\s\S]*?)<\/table>/g, (tbl) => {
    const heads = [...tbl.matchAll(/<th scope="col">([\s\S]*?)<\/th>/g)].map((m) => m[1].replace(/<[^>]+>/g, '').replace(/"/g, '&quot;'));
    return tbl.replace(/<tr>([\s\S]*?)<\/tr>/g, (tr, inner) => {
      if (inner.includes('<th scope="col">')) return tr;
      let i = 0;
      // the cell content is wrapped once so a multi-line value stays in the value column of a phone card
      return '<tr>' + inner.replace(/<td([^>]*)>([\s\S]*?)<\/td>/g, (m, attrs, content) => `<td data-label="${heads[i++] || ''}"${attrs}><span class="v">${content}</span></td>`) + '</tr>';
    });
  });
}
function page(ctx, title, current, body, status = 200) {
  body = raw(labelTables(String(body)));
  return htmlResponse(consolePage({ title, user: ctx.user, csrf: ctx.csrf, current, body, badges: ctx.badges, busy: ctx.url.searchParams.get('demo') === 'complet' }), status, NO_STORE);
}
function deny(ctx, text = 'Votre rôle ne donne pas accès à cette page.', status = 403) {
  return htmlResponse(errorPage({ status, title: 'Accès refusé', text, user: ctx.user, csrf: ctx.csrf, back: '/console' }), status, NO_STORE);
}
async function badges(env, user) {
  if (!STAFF.includes(user.role)) return {};
  const r = await env.DB.batch([
    env.DB.prepare(`SELECT COUNT(*) AS n FROM enquiries WHERE sbx = ? AND status = 'nouvelle'`).bind(env.SBX_EFF),
    env.DB.prepare(`SELECT COUNT(*) AS n FROM gme_requests WHERE sbx = ? AND status = 'en_attente'`).bind(env.SBX_EFF),
  ]);
  return { dem: r[0].results[0].n, acces: user.role === 'direction' ? r[1].results[0].n : 0 };
}

// ---------------------------------------------------------------- login / logout
export async function loginGet(req, env, { error, status = 200 } = {}) {
  const url = new URL(req.url);
  const notice = url.searchParams.get('reinit') ? 'La démonstration a été réinitialisée.' : url.searchParams.get('sortie') ? 'Vous êtes déconnecté.' : '';
  const s = await getSession(req, env);
  if (s && !error) return redirect('/console');
  return htmlResponse(loginPage({ token: await makeFormToken(env, 'login'), error, next: url.searchParams.get('next') || '', notice }), status, NO_STORE);
}
export async function loginPost(req, env) {
  const form = await readForm(req);
  if (form.error) return loginGet(req, env, { error: 'Formulaire invalide.', status: form.error });
  const tok = await checkFormToken(env, 'login', form.get('_token'));
  if (!tok.ok || !sameOrigin(req)) return loginGet(req, env, { error: 'Le formulaire a expiré : rechargez la page et réessayez.', status: 403 });
  const ip = await ipHash(env, req);
  const username = clean(form.get('username'), 40).toLowerCase();
  // Throttle: 10 failures per account per connection, 50 per connection overall, 15 minutes.
  // Throttle, all counters incremented atomically BEFORE the password check (attempts, not failures); a success clears them.
  // Demo mode (ACCOUNT_LOCKOUT=off): keyed per browser sandbox + account (10) and per IP + account (50). A flood from one
  // browser or one address never locks the shared demo accounts for other visitors.
  // Production mode (ACCOUNT_LOCKOUT=on): per IP + account drops to 10 and an account-wide ceiling (30, any IP) is added.
  const lockout = env.ACCOUNT_LOCKOUT === 'on';
  const u40 = username.slice(0, 40);
  const kSbx = `login-sbx:${env.SBX || 'none'}:${u40}`; const kUser = `login:${ip}:${u40}`; const kAcct = `login-account:${u40}`; const kIp = `login:${ip}`;
  const tooMany = () => loginGet(req, env, { error: 'Trop d’essais. Réessayez dans un quart d’heure.', status: 429 });
  // Per IP: incremented first, atomically (a parallel burst over many usernames cannot slip past); a success gives its
  // attempt back below, so only failures accumulate.
  if (!(await rateHit(env, kIp, 50, 900))) return tooMany();
  if (!(await rateHit(env, kSbx, 10, 900))) return tooMany();
  if (!(await rateHit(env, kUser, lockout ? 10 : 50, 900))) return tooMany();
  if (lockout && !(await rateHit(env, kAcct, 30, 900))) return tooMany();
  const password = String(form.get('password') || '').slice(0, 200);
  const u = await env.DB.prepare('SELECT * FROM users WHERE username = ?').bind(username).first();
  const ok = u ? safeEqual(await hashPassword(password, u.pw_salt, u.pw_iter), u.pw_hash) : false;
  if (!ok) {
    return loginGet(req, env, { error: 'Identifiant ou mot de passe incorrect.', status: 401 });
  }
  await env.DB.batch([
    env.DB.prepare('DELETE FROM rate_limits WHERE key IN (?, ?, ?)').bind(kSbx, kUser, kAcct),
    env.DB.prepare('UPDATE rate_limits SET count = MAX(count - 1, 0) WHERE key = ?').bind(kIp),
  ]);
  const token = randomToken(32);
  await env.DB.prepare('INSERT INTO sessions (id, user_id, csrf, created_at, expires_at) VALUES (?,?,?,?,?)')
    .bind(await sha256hex(token), u.id, randomToken(24), nowIso(), Math.floor(Date.now() / 1000) + SESSION_TTL).run();
  const next = form.get('next');
  const dest = /^\/console(\/[A-Za-z0-9/_.-]*)?(\?[A-Za-z0-9=&_.%-]*)?$/.test(next) && !next.includes('//') ? next : '/console';
  return redirect(dest, { 'set-cookie': cookie(token, SESSION_TTL) });
}

// ---------------------------------------------------------------- router
export async function consoleRoute(req, env, path) {
  const method = req.method;
  if (path === '/console/connexion') return method === 'POST' ? loginPost(req, env) : loginGet(req, env);
  const s = await getSession(req, env);
  if (!s) {
    if (method === 'GET') return redirect('/console/connexion?next=' + encodeURIComponent(path));
    return htmlResponse(errorPage({ status: 401, title: 'Session requise', text: 'Connectez-vous pour effectuer cette action. Rien n’a été modifié.', back: '/console/connexion' }), 401, NO_STORE);
  }
  const ctx = { req, env, user: s.user, csrf: s.csrf, sid: s.sid, url: new URL(req.url) };
  if (method === 'POST') {
    ctx.form = await readForm(req);
    if (ctx.form.error) return deny(ctx, 'Formulaire trop volumineux ou mal formé. Rien n’a été modifié.', ctx.form.error);
    // CSRF is checked before anything is written: a forged request leaves no row anywhere, not even in the journal.
    if (!sameOrigin(req) || !safeEqual(String(ctx.form.get('_csrf')), s.csrf)) {
      return deny(ctx, 'Formulaire expiré ou invalide (jeton de sécurité manquant). Rien n’a été modifié : rechargez la page.');
    }
  } else if (method !== 'GET' && method !== 'HEAD') {
    return new Response('Méthode non autorisée', { status: 405, headers: { allow: 'GET, POST' } });
  }
  // Every accepted console write lands in this browser's private sandbox (copied from the seed on first write).
  if (method === 'POST' && path !== '/console/deconnexion' && path !== '/console/reinitialiser') await materialize(env);
  ctx.badges = await badges(env, s.user);
  const role = s.user.role;
  const allow = (roles) => roles.includes(role);
  let m;

  if (path === '/console/deconnexion' && method === 'POST') {
    await env.DB.prepare('DELETE FROM sessions WHERE id = ?').bind(s.sid).run();
    return redirect('/console/connexion?sortie=1', { 'set-cookie': cookie('', 0) });
  }
  if (path === '/console' || path === '/console/') return method === 'GET' ? dashboard(ctx) : notFound(ctx);
  if (path === '/console/reinitialiser' && method === 'POST') {
    if (role !== 'direction') return deny(ctx);
    await resetSandbox(env);
    return redirect('/console?reinit=1');
  }
  // congresses
  if (path === '/console/congres') return congressList(ctx);
  if (path === '/console/congres/nouveau') return method === 'POST' ? congressSave(ctx, null) : congressForm(ctx, null);
  if ((m = /^\/console\/congres\/(\d+)$/.exec(path))) return method === 'POST' ? congressSave(ctx, +m[1]) : congressForm(ctx, +m[1]);
  if (path === '/console/listes' && method === 'POST') return role === 'direction' ? addOption(ctx) : deny(ctx, 'Seule la Direction complète les listes.');
  if ((m = /^\/console\/congres\/(\d+)\/gme$/.exec(path)) && method === 'POST') return role === 'direction' ? gmeSave(ctx, +m[1]) : deny(ctx);
  // enquiries
  if (!allow(STAFF) && /^\/console\/(demandes|notifications|gme)/.test(path)) return deny(ctx);
  if (path === '/console/demandes') return enquiryList(ctx);
  if (path === '/console/demandes/export.csv') return enquiryCsv(ctx);
  if ((m = /^\/console\/demandes\/(\d+)$/.exec(path))) return method === 'POST' ? enquiryAction(ctx, +m[1]) : enquiryDetail(ctx, +m[1]);
  if (path === '/console/notifications') return notifications(ctx);
  // GM&E
  if (path === '/console/gme') return gmeList(ctx, {});
  if ((m = /^\/console\/gme\/(\d+)\/demande$/.exec(path)) && method === 'POST') return gmeRequest(ctx, +m[1]);
  if ((m = /^\/console\/gme\/(\d+)\/afficher$/.exec(path)) && method === 'POST') return gmeReveal(ctx, +m[1]);
  if (path === '/console/gme/acces') return role === 'direction' ? gmeAccess(ctx) : deny(ctx, 'Seule la Direction gère les accès GM&E.');
  if ((m = /^\/console\/gme\/acces\/(\d+)$/.exec(path)) && method === 'POST') return role === 'direction' ? gmeDecide(ctx, +m[1]) : deny(ctx, 'Seule la Direction gère les accès GM&E.');
  if (path === '/console/gme/journal') return role === 'direction' ? gmeJournal(ctx) : deny(ctx, 'Le journal d’accès est réservé à la Direction.');
  return notFound(ctx);
}
const notFound = (ctx) => htmlResponse(errorPage({ status: 404, title: 'Page introuvable', text: 'Cette page de la console n’existe pas.', user: ctx.user, csrf: ctx.csrf, back: '/console' }), 404, NO_STORE);

// ---------------------------------------------------------------- dashboard
async function dashboard(ctx) {
  const { env, user } = ctx;
  const notice = ctx.url.searchParams.get('reinit') ? html`<p class="ok" role="status" tabindex="-1" data-focus>La démonstration a été réinitialisée : données d’exemple restaurées.</p>` : '';
  const cgCounts = Object.fromEntries(((await env.DB.prepare('SELECT status, COUNT(*) AS n FROM congresses WHERE sbx = ? GROUP BY status').bind(env.SBX_EFF).all()).results || []).map((r) => [r.status, r.n]));
  let body;
  if (user.role === 'contributeur') {
    body = html`<h1 class="h1">Tableau de bord</h1>${notice}
      <p class="intro">Vous préparez les fiches congrès. La publication sur le site est faite par l’équipe ou la Direction.</p>
      <div class="tiles">${['brouillon', 'a_relire', 'publie'].map((s) => html`<a class="tile" href="/console/congres?statut=${s}"><b>${cgCounts[s] || 0}</b><span>${(cgCounts[s] || 0) > 1 ? CG_PLURAL[s] : CG_STATUS[s]}</span></a>`)}</div>
      <p class="actions"><a class="btn" href="/console/congres/nouveau">Nouveau congrès</a></p>`;
    return page(ctx, 'Tableau de bord', 'dash', body);
  }
  const counts = Object.fromEntries(((await env.DB.prepare('SELECT status, COUNT(*) AS n FROM enquiries WHERE sbx = ? GROUP BY status').bind(env.SBX_EFF).all()).results || []).map((r) => [r.status, r.n]));
  const latest = (await env.DB.prepare(`SELECT e.id, e.ref, e.name, e.status, e.created_at, c.title FROM enquiries e JOIN congresses c ON c.id = e.congress_id AND c.sbx = e.sbx WHERE e.sbx = ? ORDER BY e.created_at DESC, e.id DESC LIMIT 5`).bind(env.SBX_EFF).all()).results || [];
  const unassigned = (await env.DB.prepare(`SELECT COUNT(*) AS n FROM enquiries WHERE sbx = ? AND status = 'nouvelle' AND owner_id IS NULL`).bind(env.SBX_EFF).first()).n;
  const pendingReq = (await env.DB.prepare(`SELECT COUNT(*) AS n FROM gme_requests WHERE sbx = ? AND status = 'en_attente'`).bind(env.SBX_EFF).first()).n;
  const verified = (await env.DB.prepare(`SELECT COUNT(*) AS n FROM gme_codes WHERE sbx = ? AND status = 'verifie'`).bind(env.SBX_EFF).first()).n;
  const todo = [];
  if (unassigned) todo.push(html`<li><a href="/console/demandes?statut=nouvelle">${unassigned} nouvelle${unassigned > 1 ? 's' : ''} demande${unassigned > 1 ? 's' : ''} sans responsable</a></li>`);
  if (cgCounts.a_relire) todo.push(html`<li><a href="/console/congres?statut=a_relire">${cgCounts.a_relire} congrès à relire avant publication</a></li>`);
  if (user.role === 'direction' && pendingReq) todo.push(html`<li><a href="/console/gme/acces">${pendingReq} demande${pendingReq > 1 ? 's' : ''} d’accès GM&amp;E à décider</a></li>`);
  if (user.role === 'direction' && verified) todo.push(html`<li><a href="/console/gme">${verified} code${verified > 1 ? 's' : ''} GM&amp;E vérifié${verified > 1 ? 's' : ''}, à approuver pour la vente</a></li>`);
  if (user.role === 'equipe' && pendingReq) todo.push(html`<li><a href="/console/gme">Votre demande d’accès GM&amp;E est en attente de la Direction</a></li>`);
  body = html`<h1 class="h1">Tableau de bord</h1>${notice}
    <section aria-labelledby="h-st"><h2 class="h2" id="h-st">Demandes par statut</h2>
      <div class="tiles">${Object.entries(STATUS_LABELS).map(([k, l]) => html`<a class="tile tile--${ST_KIND[k]}" href="/console/demandes?statut=${k}" data-count="${k}"><b>${counts[k] || 0}</b><span>${(counts[k] || 0) > 1 ? STATUS_PLURAL[k] : l}</span></a>`)}</div>
    </section>
    <div class="cols">
      <section aria-labelledby="h-new"><h2 class="h2" id="h-new">Dernières demandes</h2>
        <ul class="feed">${latest.map((e) => html`<li><a href="/console/demandes/${e.id}"><b class="nw">${e.ref}</b> ${e.name}</a><span>${e.title}</span><span>${frDateTime(e.created_at)} ${pill(ST_KIND[e.status], STATUS_LABELS[e.status])}</span></li>`)}</ul>
        <p><a class="lnk" href="/console/demandes">Toutes les demandes</a></p>
      </section>
      <section aria-labelledby="h-todo"><h2 class="h2" id="h-todo">À traiter</h2>
        ${todo.length ? html`<ul class="todo">${todo}</ul>` : html`<p class="quiet">Rien en attente.</p>`}
        ${user.role === 'direction' ? html`<form method="post" action="/console/reinitialiser" class="reset" data-confirm="Réinitialiser la démonstration ? Vos modifications dans ce navigateur seront effacées.">
          ${csrfInput(ctx.csrf)}<h3 class="h3">Bac à sable</h3><p class="quiet">Votre bac à sable est privé : vos essais ne sont visibles que dans ce navigateur. Ce bouton remet les données d’exemple ; les bacs à sable de plus de 24 h sont effacés chaque nuit à 3 h (UTC).</p>
          <button class="btn btn--line" type="submit">Réinitialiser la démo</button></form>` : ''}
      </section>
    </div>`;
  return page(ctx, 'Tableau de bord', 'dash', body);
}

// ---------------------------------------------------------------- congresses
async function congressList(ctx) {
  const { env, user } = ctx;
  const st = ctx.url.searchParams.get('statut');
  const valid = CG_STATUS[st] ? st : '';
  const rows = (await env.DB.prepare(`SELECT c.id, c.ref, c.title, c.city, c.country, c.start_date, c.end_date, c.status, c.verified_on, g.status AS gme FROM congresses c LEFT JOIN gme_codes g ON g.congress_id = c.id AND g.sbx = c.sbx WHERE c.sbx = ? ${valid ? 'AND c.status = ?' : ''} ORDER BY c.start_date, c.id`).bind(env.SBX_EFF, ...(valid ? [valid] : [])).all()).results || [];
  const showGme = STAFF.includes(user.role);
  const body = html`<div class="head"><h1 class="h1">Congrès</h1><a class="btn" href="/console/congres/nouveau">Nouveau congrès</a></div>
    <nav class="chips" aria-label="Filtrer par statut"><a class="chip" href="/console/congres"${!valid ? raw(' aria-current="true"') : ''}>Tous</a>${Object.entries(CG_STATUS).map(([k, l]) => html`<a class="chip" href="/console/congres?statut=${k}"${valid === k ? raw(' aria-current="true"') : ''}>${l}</a>`)}</nav>
    <div class="wrap" role="region" aria-label="Liste des congrès" tabindex="0"><table class="tbl">
      <thead><tr><th scope="col">Réf.</th><th scope="col">Congrès</th><th scope="col">Dates</th><th scope="col">Ville</th><th scope="col">Sur le site</th>${showGme ? html`<th scope="col">Code GM&amp;E</th>` : ''}<th scope="col">Vérifié le</th></tr></thead>
      <tbody>${rows.map((c) => html`<tr><td>${c.ref}</td><td class="wide"><a href="/console/congres/${c.id}">${c.title}</a></td><td>${frRange(c.start_date, c.end_date)}</td><td>${c.city}</td><td>${pill(CG_KIND[c.status], CG_STATUS[c.status])}</td>${showGme ? html`<td>${c.gme ? GME_STATUS[c.gme] : html`<span class="quiet">Aucun</span>`}</td>` : ''}<td>${frNumDate(c.verified_on)}</td></tr>`)}</tbody>
    </table></div>
    ${rows.length ? '' : html`<p class="quiet">Aucun congrès avec ce statut.</p>`}`;
  return page(ctx, 'Congrès', 'cg', body);
}

function congressValidate(get) {
  const v = {
    title: clean(get('title'), 160), discipline: clean(get('discipline'), 80), city: clean(get('city'), 80), country: clean(get('country'), 80),
    start_date: clean(get('start_date'), 10), end_date: clean(get('end_date'), 10), venue: clean(get('venue'), 160),
    official_url: clean(get('official_url'), 300), verified_on: clean(get('verified_on'), 10), description: clean(get('description'), 4000),
  };
  const e = {};
  const req = (k, msg, max) => { if (!v[k]) e[k] = msg; else if (v[k].length > max) e[k] = `${max} caractères au maximum.`; };
  req('title', 'Indiquez le titre.', 160); req('discipline', 'Indiquez la discipline.', 80); req('city', 'Indiquez la ville.', 80);
  req('country', 'Indiquez le pays.', 80); req('venue', 'Indiquez le lieu.', 160);
  if (!isIsoDate(v.start_date)) e.start_date = 'Indiquez une date de début valide.';
  if (!isIsoDate(v.end_date)) e.end_date = 'Indiquez une date de fin valide.';
  else if (!e.start_date && v.end_date < v.start_date) e.end_date = 'La date de fin doit être le jour du début ou après.';
  let u = null;
  try { u = new URL(v.official_url); } catch { u = null; }
  if (!v.official_url) e.official_url = 'Indiquez l’adresse du site officiel.';
  else if (!u || u.protocol !== 'https:' || !u.hostname.includes('.') || v.official_url.length > 300) e.official_url = 'Adresse invalide : elle doit commencer par https:// (exemple : https://www.congres.org).';
  if (!isIsoDate(v.verified_on)) e.verified_on = 'Indiquez la date de vérification.';
  else if (v.verified_on > today()) e.verified_on = 'La vérification ne peut pas être datée dans le futur.';
  if (v.description.length > 4000) e.description = '4 000 caractères au maximum.';
  return { v, e };
}

const TRANSITIONS = {
  save: { label: 'Enregistrer' },
  review: { to: 'a_relire', from: ['brouillon'], roles: ALL, label: 'Soumettre à relecture' },
  publish: { to: 'publie', from: ['brouillon', 'a_relire', 'archive'], roles: STAFF, label: 'Publier' },
  archive: { to: 'archive', from: ['publie'], roles: STAFF, label: 'Archiver' },
  draft: { to: 'brouillon', from: ['a_relire', 'publie', 'archive'], roles: ALL, label: 'Repasser en brouillon' },
};
const canEditCongress = (role, status) => STAFF.includes(role) || ['brouillon', 'a_relire'].includes(status);
function allowedActions(role, status) {
  return Object.entries(TRANSITIONS).filter(([k, t]) => k !== 'save' && t.from.includes(status) && t.roles.includes(role)
    && !(role === 'contributeur' && k === 'draft' && status !== 'a_relire')).map(([k]) => k);
}

const CG_LABELS = { title: 'Titre', discipline: 'Discipline', venue: 'Lieu', city: 'Ville', country: 'Pays', start_date: 'Date de début', end_date: 'Date de fin', official_url: 'Site officiel', verified_on: 'Vérifié le', description: 'Description' };
const CG_IDS = { title: 'c-title', discipline: 'c-disc', venue: 'c-venue', city: 'c-city', country: 'c-country', start_date: 'c-start', end_date: 'c-end', official_url: 'c-url', verified_on: 'c-ver', description: 'c-desc' };
async function loadOptions(env) {
  const rows = (await env.DB.prepare('SELECT kind, value FROM options WHERE sbx = ? ORDER BY value').bind(env.SBX_EFF).all()).results || [];
  const out = { discipline: [], pays: [] };
  for (const r of rows) out[r.kind].push(r.value);
  for (const k of Object.keys(out)) out[k].sort((a, b) => a.localeCompare(b, 'fr'));
  return out;
}
function listSelect(id, name, label, values, value, error, editable) {
  const opts = [['', 'Choisir dans la liste'], ...values.map((x) => [x, x])];
  if (value && !values.includes(value)) opts.push([value, `${value} (hors liste)`]);
  return select({ id, name, label, options: opts, value: value || '', error, required: true, attrs: editable ? '' : 'disabled' });
}
async function addOption(ctx) {
  const { env, form } = ctx;
  const kind = form.get('kind');
  const back = /^\d+$/.test(form.get('back')) ? `/console/congres/${form.get('back')}` : '/console/congres/nouveau';
  if (!['discipline', 'pays'].includes(kind)) return deny(ctx, 'Liste inconnue.', 400);
  const value = clean(form.get('value'), 60).replace(/\s+/g, ' ');
  const n = norm(value);
  if (value.length < 2 || value.length > 60 || !/^[\p{L}][\p{L}\p{M}' ’.-]*(?: [\p{L}\p{M}' ’.-]+)*$/u.test(value)) return redirect(`${back}?liste=invalide`);
  const exists = await env.DB.prepare('SELECT value FROM options WHERE sbx = ? AND kind = ? AND norm = ?').bind(env.SBX_EFF, kind, n).first();
  if (exists) return redirect(`${back}?liste=existe`);
  const pretty = value.charAt(0).toUpperCase() + value.slice(1);
  await env.DB.prepare('INSERT INTO options (sbx, kind, value, norm) VALUES (?,?,?,?)').bind(env.SBX_EFF, kind, pretty, n).run();
  return redirect(`${back}?liste=ajoute`);
}

async function congressForm(ctx, id, { values, errors, status = 200, notice } = {}) {
  const { env, user } = ctx;
  let c = null;
  if (id) {
    c = await env.DB.prepare('SELECT * FROM congresses WHERE sbx = ? AND id = ?').bind(env.SBX_EFF, id).first();
    if (!c) return notFound(ctx);
  }
  const v = values || c || { verified_on: today() };
  const e = errors || {};
  const stat = c ? c.status : 'brouillon';
  const editable = !c || canEditCongress(user.role, stat);
  const lists = await loadOptions(env);
  const actions = c ? allowedActions(user.role, stat) : (STAFF.includes(user.role) ? ['publish'] : ['review']);
  const saved = ctx.url.searchParams.get('ok');
  const listMsg = { ajoute: ['ok', 'Valeur ajoutée à la liste.'], existe: ['alert', 'Cette valeur existe déjà dans la liste (accents et majuscules ignorés).'], invalide: ['alert', 'Valeur refusée : 2 à 60 lettres.'] }[ctx.url.searchParams.get('liste')];
  const history = c ? (await env.DB.prepare(`SELECT ev.*, u.display_name FROM congress_events ev LEFT JOIN users u ON u.id = ev.user_id WHERE ev.sbx = ? AND congress_id = ? ORDER BY ev.id DESC LIMIT 12`).bind(env.SBX_EFF, id).all()).results || [] : [];
  const f = (o) => field({ ...o, value: v[o.name], error: e[o.name], required: o.optional ? false : true, attrs: (o.attrs || '') + (editable ? '' : ' disabled') });
  const primary = !c ? (STAFF.includes(user.role) ? 'publish' : 'save') : 'save';
  const secondaries = !c ? (STAFF.includes(user.role) ? ['save'] : ['review']) : actions;
  const btnLabel = (k) => (!c && k === 'save') ? 'Enregistrer le brouillon' : (k === 'publish' && stat === 'archive') ? 'Republier' : TRANSITIONS[k].label;

  const gmePanel = c && STAFF.includes(user.role) ? await gmeCard(ctx, c, { context: 'congress' }) : '';
  const body = html`<nav class="crumbs" aria-label="Fil d’Ariane"><a href="/console/congres">Congrès</a><span aria-hidden="true">/</span><span>${c ? c.ref : 'Nouveau'}</span></nav>
    <div class="head"><h1 class="h1">${c ? c.title : 'Nouveau congrès'}</h1>${c ? html`<p>${pill(CG_KIND[stat], CG_STATUS[stat])}${stat === 'publie' ? html` <a class="lnk" href="/congres/${c.slug}">Voir la fiche publique</a>` : ''}</p>` : ''}</div>
    ${saved ? html`<p class="ok" role="status" tabindex="-1" data-focus>${savedMessage(saved, stat)}</p>` : ''}
    ${notice ? html`<p class="alert" role="alert" tabindex="-1" data-focus>${notice}</p>` : ''}
    ${listMsg ? html`<p class="${listMsg[0]}" role="status" tabindex="-1" data-focus>${listMsg[1]}</p>` : ''}
    ${errorSummary(e, CG_LABELS, CG_IDS)}
    <div class="edit">
      <form method="post" action="${c ? `/console/congres/${c.id}` : '/console/congres/nouveau'}" class="card form" novalidate>
        ${csrfInput(ctx.csrf)}
        ${!editable ? html`<p class="field--full quiet">Ce congrès est ${CG_STATUS[stat].toLowerCase()} : seules l’équipe et la Direction peuvent le modifier.</p>` : ''}
        ${f({ id: 'c-title', name: 'title', label: 'Titre', attrs: 'maxlength="160"', full: true })}
        ${listSelect('c-disc', 'discipline', 'Discipline', lists.discipline, v.discipline, e.discipline, editable)}
        ${f({ id: 'c-venue', name: 'venue', label: 'Lieu', attrs: 'maxlength="160"' })}
        ${f({ id: 'c-city', name: 'city', label: 'Ville', attrs: 'maxlength="80"' })}
        ${listSelect('c-country', 'country', 'Pays', lists.pays, v.country, e.country, editable)}
        ${f({ id: 'c-start', name: 'start_date', label: 'Date de début', type: 'date' })}
        ${f({ id: 'c-end', name: 'end_date', label: 'Date de fin', type: 'date' })}
        ${f({ id: 'c-url', name: 'official_url', label: 'Site officiel', type: 'url', hint: 'Adresse complète, par exemple https://www.congres.org', attrs: 'maxlength="300" inputmode="url"' })}
        ${f({ id: 'c-ver', name: 'verified_on', label: 'Vérifié le', type: 'date', hint: 'Date à laquelle les informations ont été contrôlées sur le site officiel.' })}
        ${f({ id: 'c-desc', name: 'description', label: 'Description', type: 'textarea', optional: true, attrs: 'rows="4" maxlength="4000"', full: true })}
        <p class="form__legend field--full"><span class="req" aria-hidden="true">*</span> Champ obligatoire.</p>
        ${editable ? html`<div class="form__actions">
          <button class="btn" type="submit" name="action" value="${primary}">${btnLabel(primary)}</button>
          ${secondaries.filter((k) => k !== primary).map((k) => html`<button class="btn btn--line" type="submit" name="action" value="${k}">${btnLabel(k)}</button>`)}
        </div>` : ''}
      </form>
      <aside class="edit__side">
        <section class="card"><h2 class="h3">Mise en ligne</h2>
          <ol class="flow">${Object.entries(CG_STATUS).map(([k, l]) => html`<li${k === stat ? raw(' aria-current="step"') : ''}>${l}</li>`)}</ol>
          <p class="quiet">${user.role === 'contributeur' ? 'Vous pouvez enregistrer et soumettre à relecture. La publication est faite par l’équipe ou la Direction.' : 'Seule une fiche publiée apparaît sur le site public.'}</p>
          ${history.length ? html`<h3 class="h4">Historique</h3><ul class="hist hist--sm">${history.map((h) => html`<li><time>${frDateTime(h.at)}</time> ${h.display_name || 'Système'} : ${h.kind === 'creation' ? 'création' : html`${CG_STATUS[h.from_val] || h.from_val} vers ${CG_STATUS[h.to_val] || h.to_val}`}</li>`)}</ul>` : ''}
        </section>
        ${user.role === 'direction' ? html`<section class="card" aria-labelledby="h-lists"><h2 class="h3" id="h-lists">Listes du formulaire</h2>
          <p class="quiet">Discipline et pays se choisissent dans une liste : une faute de frappe ne crée pas de doublon dans les filtres du site.</p>
          ${[['discipline', 'Ajouter une discipline'], ['pays', 'Ajouter un pays']].map(([kind, label]) => html`<form method="post" action="/console/listes" class="inline">${csrfInput(ctx.csrf)}
            <input type="hidden" name="kind" value="${kind}"><input type="hidden" name="back" value="${c ? c.id : 'nouveau'}">
            ${field({ id: `add-${kind}`, name: 'value', label, attrs: 'maxlength="60" autocomplete="off"' })}
            <button class="btn btn--line" type="submit">Ajouter</button></form>`)}
        </section>` : ''}
        ${gmePanel}
      </aside>
    </div>`;
  return page(ctx, c ? c.title : 'Nouveau congrès', 'cg', body, status);
}

function savedMessage(code, stat) {
  const created = code.startsWith('cree');
  const action = code.replace(/^cree-?/, '');
  const what = { review: 'Soumis à relecture.', publish: 'Publié : la fiche est en ligne.', archive: 'Archivé : la fiche n’est plus sur le site.', draft: 'Repassé en brouillon : la fiche n’est plus sur le site.' }[action];
  if (created) return `Congrès créé. ${what || (stat === 'brouillon' ? 'Enregistré comme brouillon.' : '')}`.trim();
  if (what) return what;
  return `Modifications enregistrées.${stat === 'publie' ? ' La fiche publique est à jour.' : ''}`;
}
async function congressSave(ctx, id) {
  const { env, user, form } = ctx;
  const action = form.get('action') || 'save';
  if (!TRANSITIONS[action]) return deny(ctx, 'Action inconnue. Rien n’a été modifié.', 400);
  let c = null;
  if (id) { c = await env.DB.prepare('SELECT * FROM congresses WHERE sbx = ? AND id = ?').bind(env.SBX_EFF, id).first(); if (!c) return notFound(ctx); }
  const from = c ? c.status : 'brouillon';
  if (c && !canEditCongress(user.role, from)) return deny(ctx, 'Ce congrès est publié : seules l’équipe et la Direction peuvent le modifier. Rien n’a été modifié.');
  const t = TRANSITIONS[action];
  let to = from;
  if (action !== 'save') {
    if (!t.roles.includes(user.role) || (!t.from.includes(from) && !(!c && action === 'publish'))) {
      return deny(ctx, user.role === 'contributeur' && action === 'publish' ? 'Un contributeur ne peut pas publier : soumettez le congrès à relecture. Rien n’a été publié.' : 'Ce changement de statut n’est pas permis. Rien n’a été modifié.');
    }
    if (user.role === 'contributeur' && action === 'draft' && from !== 'a_relire') return deny(ctx, 'Ce changement de statut n’est pas permis.');
    to = t.to;
  }
  const { v, e } = congressValidate(form.get);
  v.title = nbsp(v.title); v.venue = nbsp(v.venue);
  const lists = await loadOptions(env);
  if (!e.discipline && !lists.discipline.includes(v.discipline)) e.discipline = 'Choisissez une discipline de la liste.';
  if (!e.country && !lists.pays.includes(v.country)) e.country = 'Choisissez un pays de la liste.';
  if (Object.keys(e).length) return congressForm(ctx, id, { values: v, errors: e, status: 200 });
  const now = nowIso();
  const search = congressSearch({ ...v, ref: c?.ref || '' });
  if (!c) {
    const maxId = (await env.DB.prepare('SELECT COALESCE(MAX(id), 100) AS m FROM congresses WHERE sbx = ?').bind(env.SBX_EFF).first()).m;
    const nid = maxId + 1;
    const ref = `CG-${String(nid).padStart(4, '0')}`;
    await env.DB.batch([
      env.DB.prepare(`INSERT INTO congresses (sbx, id, ref, slug, title, discipline, city, country, start_date, end_date, venue, official_url, verified_on, description, status, search_text, created_at, updated_at, updated_by) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)`)
        .bind(env.SBX_EFF, nid, ref, congressSlug(v.title, ref) || `congres-${ref.toLowerCase()}`, v.title, v.discipline, v.city, v.country, v.start_date, v.end_date, v.venue, v.official_url, v.verified_on, v.description, to, norm(search + ' ' + ref), now, now, user.id),
      env.DB.prepare(`INSERT INTO congress_events (sbx, congress_id, at, user_id, kind, from_val, to_val) VALUES (?,?,?,?,'creation',NULL,?)`).bind(env.SBX_EFF, nid, now, user.id, 'brouillon'),
      ...(to !== 'brouillon' ? [env.DB.prepare(`INSERT INTO congress_events (sbx, congress_id, at, user_id, kind, from_val, to_val) VALUES (?,?,?,?,'statut','brouillon',?)`).bind(env.SBX_EFF, nid, now, user.id, to)] : []),
    ]);
    return redirect(`/console/congres/${nid}?ok=cree-${action}`);
  }
  const stmts = [env.DB.prepare(`UPDATE congresses SET title=?, discipline=?, city=?, country=?, start_date=?, end_date=?, venue=?, official_url=?, verified_on=?, description=?, status=?, search_text=?, updated_at=?, updated_by=? WHERE sbx=? AND id=?`)
    .bind(v.title, v.discipline, v.city, v.country, v.start_date, v.end_date, v.venue, v.official_url, v.verified_on, v.description, to, search, now, user.id, env.SBX_EFF, id)];
  if (to !== from) stmts.push(env.DB.prepare(`INSERT INTO congress_events (sbx, congress_id, at, user_id, kind, from_val, to_val) VALUES (?,?,?,?,'statut',?,?)`).bind(env.SBX_EFF, id, now, user.id, from, to));
  await env.DB.batch(stmts);
  return redirect(`/console/congres/${id}?ok=${action}`);
}

// ---------------------------------------------------------------- enquiries
function enquiryFilter(ctx) {
  const sp = ctx.url.searchParams;
  const statut = STATUS_LABELS[sp.get('statut')] ? sp.get('statut') : '';
  const q = clean(sp.get('q'), 100).slice(0, 100);
  return { statut, q };
}
const ENQ_SELECT = `SELECT e.*, c.title AS cg_title, c.ref AS cg_ref, u.display_name AS owner_name FROM enquiries e JOIN congresses c ON c.id = e.congress_id AND c.sbx = e.sbx LEFT JOIN users u ON u.id = e.owner_id WHERE e.sbx = ?`;

async function enquiryList(ctx) {
  const { env } = ctx;
  const f = enquiryFilter(ctx);
  // Accent-insensitive name search: compare against a normalised copy in JS for names stored with accents.
  const rowsAll = (await env.DB.prepare(`${ENQ_SELECT} ${f.statut ? 'AND e.status = ?' : ''} ORDER BY e.created_at DESC, e.id DESC LIMIT 500`).bind(env.SBX_EFF, ...(f.statut ? [f.statut] : [])).all()).results || [];
  const words = norm(f.q).split(/\s+/).filter(Boolean);
  const rows = rowsAll.filter((r) => words.every((w) => norm([r.ref, r.name, r.email, r.company, r.departure_city, r.cg_title, r.cg_ref].join(' ')).includes(w)));
  const counts = Object.fromEntries(((await env.DB.prepare('SELECT status, COUNT(*) AS n FROM enquiries WHERE sbx = ? GROUP BY status').bind(env.SBX_EFF).all()).results || []).map((r) => [r.status, r.n]));
  const total = Object.values(counts).reduce((a, b) => a + b, 0);
  const exportQs = new URLSearchParams({ ...(f.statut ? { statut: f.statut } : {}), ...(f.q ? { q: f.q } : {}) }).toString();
  const body = html`<div class="head"><h1 class="h1">Demandes</h1><a class="btn btn--line" href="/console/demandes/export.csv${exportQs ? '?' + exportQs : ''}" download>Exporter (tableur CSV)</a></div>
    <nav class="chips" aria-label="Filtrer par statut"><a class="chip" href="/console/demandes${f.q ? '?q=' + encodeURIComponent(f.q) : ''}"${!f.statut ? raw(' aria-current="true"') : ''}>Toutes (${total})</a>${Object.entries(STATUS_LABELS).map(([k, l]) => html`<a class="chip" href="/console/demandes?statut=${k}${f.q ? '&q=' + encodeURIComponent(f.q) : ''}"${f.statut === k ? raw(' aria-current="true"') : ''}>${l} (${counts[k] || 0})</a>`)}</nav>
    <form class="search" method="get" action="/console/demandes" role="search">
      ${f.statut ? html`<input type="hidden" name="statut" value="${f.statut}">` : ''}
      <div class="field"><label for="dq">Rechercher (nom, référence, société, ville)</label><input id="dq" name="q" type="search" value="${f.q}" maxlength="100"></div>
      <button class="btn btn--line" type="submit">Rechercher</button>${f.q || f.statut ? html`<a class="lnk" href="/console/demandes">Effacer</a>` : ''}
    </form>
    <p class="bar" aria-live="polite">${rows.length} demande${rows.length > 1 ? 's' : ''}</p>
    ${rows.length ? html`<div class="wrap" role="region" aria-label="Liste des demandes" tabindex="0"><table class="tbl">
      <thead><tr><th scope="col">Réf.</th><th scope="col">Statut</th><th scope="col">Reçue</th><th scope="col">Congrès</th><th scope="col">Contact</th><th scope="col">Voyage</th><th scope="col">Responsable</th></tr></thead>
      <tbody>${rows.map((r) => html`<tr><td><a href="/console/demandes/${r.id}" class="nw">${r.ref}</a></td><td>${pill(ST_KIND[r.status], STATUS_LABELS[r.status])}</td><td>${frDateTime(r.created_at)}</td><td class="wide">${r.cg_title}</td><td class="wide">${r.name}<br><span class="quiet">${r.company || r.email}</span></td><td class="wide">Départ de ${r.departure_city}<br>${nw(`${frNumDate(r.date_out)} au ${frNumDate(r.date_back)}`)}<br>${r.passengers} passager${r.passengers > 1 ? 's' : ''}</td><td>${r.owner_name || html`<span class="quiet">À attribuer</span>`}</td></tr>`)}</tbody>
    </table></div>` : html`<div class="empty"><p>Aucune demande ne correspond.</p><p><a class="lnk" href="/console/demandes">Voir toutes les demandes</a></p></div>`}`;
  return page(ctx, 'Demandes', 'dem', body);
}

async function enquiryCsv(ctx) {
  const { env } = ctx;
  const f = enquiryFilter(ctx);
  const all = (await env.DB.prepare(`${ENQ_SELECT} ${f.statut ? 'AND e.status = ?' : ''} ORDER BY e.created_at DESC, e.id DESC LIMIT 5000`).bind(env.SBX_EFF, ...(f.statut ? [f.statut] : [])).all()).results || [];
  const words = norm(f.q).split(/\s+/).filter(Boolean);
  const rows = all.filter((r) => words.every((w) => norm([r.ref, r.name, r.email, r.company, r.departure_city, r.cg_title, r.cg_ref].join(' ')).includes(w)));
  const head = ['Référence', 'Reçue le', 'Congrès', 'Réf. congrès', 'Nom', 'E-mail', 'Téléphone', 'Société', 'Ville de départ', 'Aller', 'Retour', 'Passagers', 'Statut', 'Responsable', 'Message'];
  const lines = [head.map(csvCell).join(';')];
  for (const r of rows) {
    lines.push([r.ref, frDateTime(r.created_at), r.cg_title, r.cg_ref, r.name, r.email, r.phone, r.company, r.departure_city, r.date_out, r.date_back, r.passengers, STATUS_LABELS[r.status], r.owner_name || '', r.message].map(csvCell).join(';'));
  }
  return new Response('\uFEFF' + lines.join('\r\n') + '\r\n', {
    headers: { 'content-type': 'text/csv; charset=utf-8', 'content-disposition': `attachment; filename="demandes-${today()}.csv"`, ...NO_STORE },
  });
}

async function enquiryDetail(ctx, id, { notice } = {}) {
  const { env, user } = ctx;
  const r = await env.DB.prepare(`${ENQ_SELECT} AND e.id = ?`).bind(env.SBX_EFF, id).first();
  if (!r) return notFound(ctx);
  const staff = (await env.DB.prepare(`SELECT id, display_name FROM users WHERE role IN ('direction','equipe') ORDER BY id`).all()).results || [];
  const names = Object.fromEntries(staff.map((u) => [String(u.id), u.display_name]));
  const events = (await env.DB.prepare(`SELECT ev.*, u.display_name FROM enquiry_events ev LEFT JOIN users u ON u.id = ev.user_id WHERE ev.sbx = ? AND enquiry_id = ? ORDER BY ev.at ASC, ev.id ASC`).bind(env.SBX_EFF, id).all()).results || [];
  const ok = ctx.url.searchParams.get('ok');
  const evText = (ev) => {
    if (ev.kind === 'creation') return 'Demande reçue depuis le site';
    if (ev.kind === 'statut') return html`Statut : ${STATUS_LABELS[ev.from_val] || ev.from_val} vers ${STATUS_LABELS[ev.to_val] || ev.to_val}`;
    if (ev.kind === 'responsable') return html`Responsable : ${names[ev.from_val] || 'aucun'} vers ${names[ev.to_val] || 'aucun'}`;
    return html`Note interne : <q>${ev.to_val}</q>`;
  };
  const body = html`<nav class="crumbs" aria-label="Fil d’Ariane"><a href="/console/demandes">Demandes</a><span aria-hidden="true">/</span><span>${r.ref}</span></nav>
    <div class="head"><h1 class="h1">${r.ref}</h1><p>${pill(ST_KIND[r.status], STATUS_LABELS[r.status])}</p></div>
    ${ok ? html`<p class="ok" role="status" tabindex="-1" data-focus>${ok.startsWith('statut-') && STATUS_LABELS[ok.slice(7)] ? `Statut mis à jour : ${STATUS_LABELS[ok.slice(7)]}.` : ok === 'responsable' ? `Responsable : ${r.owner_name || 'personne'}.` : ok === 'note' ? 'Note ajoutée à l’historique.' : 'Enregistré.'}</p>` : ''}
    ${notice ? html`<p class="alert" role="alert" tabindex="-1" data-focus>${notice}</p>` : ''}
    <form method="post" action="/console/demandes/${r.id}" class="card status-bar">
      ${csrfInput(ctx.csrf)}<input type="hidden" name="action" value="status">
      <h2 class="h3" id="st-h">Changer le statut</h2>
      <div class="seg" role="group" aria-labelledby="st-h">${Object.entries(STATUS_LABELS).map(([k, l]) => html`<button type="submit" name="to" value="${k}" class="seg__b"${k === r.status ? raw(' aria-pressed="true" disabled') : raw(' aria-pressed="false"')}>${l}</button>`)}</div>
    </form>
    <div class="edit">
      <section class="card" aria-labelledby="h-c"><h2 class="h3" id="h-c">Demande de devis vol</h2>
        <dl class="facts facts--tight">
          <div><dt>Congrès</dt><dd>${r.cg_title} (${nw(r.cg_ref)})</dd></div>
          <div><dt>Nom</dt><dd>${r.name}</dd></div>
          <div><dt>E-mail</dt><dd><a class="lnk" href="mailto:${r.email}">${r.email}</a></dd></div>
          <div><dt>Téléphone</dt><dd>${nw(r.phone)}</dd></div>
          <div><dt>Société</dt><dd>${r.company || html`<span class="quiet">Non renseignée</span>`}</dd></div>
          <div><dt>Ville de départ</dt><dd>${r.departure_city}</dd></div>
          <div><dt>Aller</dt><dd>${frNumDate(r.date_out)}</dd></div>
          <div><dt>Retour</dt><dd>${frNumDate(r.date_back)}</dd></div>
          <div><dt>Passagers</dt><dd>${r.passengers}</dd></div>
          <div><dt>Message</dt><dd class="pre">${r.message || html`<span class="quiet">Aucun</span>`}</dd></div>
          <div><dt>Reçue le</dt><dd>${frDateTime(r.created_at)}</dd></div>
          <div><dt>Consentement</dt><dd>Donné le ${frDateTime(r.consent_at)}</dd></div>
        </dl>
      </section>
      <aside class="edit__side">
        <section class="card" aria-labelledby="h-o"><h2 class="h3" id="h-o">Responsable</h2>
          <p>${r.owner_name || html`<span class="quiet">À attribuer</span>`}</p>
          <form method="post" action="/console/demandes/${r.id}" class="inline">${csrfInput(ctx.csrf)}<input type="hidden" name="action" value="owner">
            ${select({ id: 'own', name: 'owner', label: 'Attribuer à', value: r.owner_id || '', options: [['', 'Personne'], ...staff.map((u) => [u.id, u.display_name])] })}
            <button class="btn btn--line" type="submit">Attribuer</button></form>
          ${r.owner_id !== user.id ? html`<form method="post" action="/console/demandes/${r.id}">${csrfInput(ctx.csrf)}<input type="hidden" name="action" value="owner"><input type="hidden" name="owner" value="${user.id}"><button class="btn btn--line" type="submit">Me l’attribuer</button></form>` : ''}
        </section>
        <section class="card" aria-labelledby="h-n"><h2 class="h3" id="h-n">Note interne</h2>
          <form method="post" action="/console/demandes/${r.id}" class="stack">${csrfInput(ctx.csrf)}<input type="hidden" name="action" value="note">
            ${field({ id: 'note', name: 'note', label: 'Visible uniquement par l’équipe', type: 'textarea', attrs: 'rows="3" maxlength="2000" required' })}
            <button class="btn btn--line" type="submit">Ajouter la note</button></form>
        </section>
      </aside>
    </div>
    <section class="card" aria-labelledby="h-h" id="historique"><h2 class="h3" id="h-h">Historique</h2>
      <p class="quiet">Chaque changement est conservé : il ne peut être ni modifié ni supprimé.</p>
      <ol class="hist">${events.map((ev) => html`<li><time datetime="${ev.at}">${frDateTime(ev.at)}</time><span class="hist__who">${ev.display_name || 'Site public'}</span><span>${evText(ev)}</span></li>`)}</ol>
    </section>`;
  return page(ctx, r.ref, 'dem', body);
}

async function enquiryAction(ctx, id) {
  const { env, user, form } = ctx;
  const r = await env.DB.prepare('SELECT * FROM enquiries WHERE sbx = ? AND id = ?').bind(env.SBX_EFF, id).first();
  if (!r) return notFound(ctx);
  const now = nowIso();
  const action = form.get('action');
  const ev = (kind, from, to) => env.DB.prepare('INSERT INTO enquiry_events (sbx, enquiry_id, at, user_id, kind, from_val, to_val) VALUES (?,?,?,?,?,?,?)').bind(env.SBX_EFF, id, now, user.id, kind, from, to);
  if (action === 'status') {
    const to = form.get('to');
    if (!STATUS_LABELS[to]) return enquiryDetail(ctx, id, { notice: 'Statut inconnu : rien n’a été modifié.' });
    if (to !== r.status) await env.DB.batch([env.DB.prepare('UPDATE enquiries SET status = ?, updated_at = ? WHERE sbx = ? AND id = ?').bind(to, now, env.SBX_EFF, id), ev('statut', r.status, to)]);
  } else if (action === 'owner') {
    const raw = form.get('owner');
    let owner = null;
    if (raw) {
      const u = await env.DB.prepare(`SELECT id FROM users WHERE id = ? AND role IN ('direction','equipe')`).bind(parseInt(raw, 10) || 0).first();
      if (!u) return enquiryDetail(ctx, id, { notice: 'Responsable inconnu : rien n’a été modifié.' });
      owner = u.id;
    }
    if (owner !== r.owner_id) await env.DB.batch([env.DB.prepare('UPDATE enquiries SET owner_id = ?, updated_at = ? WHERE sbx = ? AND id = ?').bind(owner, now, env.SBX_EFF, id), ev('responsable', r.owner_id == null ? null : String(r.owner_id), owner == null ? null : String(owner))]);
  } else if (action === 'note') {
    const note = clean(form.get('note'), 2000);
    if (!note) return enquiryDetail(ctx, id, { notice: 'La note est vide : rien n’a été ajouté.' });
    if (note.length > 2000) return enquiryDetail(ctx, id, { notice: 'Note trop longue (2 000 caractères au maximum).' });
    await env.DB.batch([env.DB.prepare('UPDATE enquiries SET updated_at = ? WHERE sbx = ? AND id = ?').bind(now, env.SBX_EFF, id), ev('note', null, note)]);
  } else {
    return enquiryDetail(ctx, id, { notice: 'Action inconnue : rien n’a été modifié.' });
  }
  const okq = action === 'status' ? `statut-${form.get('to')}` : action === 'owner' ? 'responsable' : 'note';
  return redirect(`/console/demandes/${id}?ok=${okq}`);
}

// Mail text for display: references and phone numbers never break; URLs only break after a slash.
function mailBody(text) {
  return raw(esc(text)
    .replace(/(?:DV|CG)-\d{4}(?:-\d{4})?/g, (m) => `<span class="nw">${m}</span>`)
    .replace(/\b0\d(?: \d\d){4}\b/g, (m) => `<span class="nw">${m}</span>`)
    .replace(/(https?:\/\/\S+)/g, (m) => m.replace(/\//g, '/<wbr>')));
}
async function notifications(ctx) {
  const rows = (await ctx.env.DB.prepare(`SELECT n.*, e.ref FROM notifications n JOIN enquiries e ON e.id = n.enquiry_id AND e.sbx = n.sbx WHERE n.sbx = ? ORDER BY n.at DESC, n.id DESC LIMIT 100`).bind(ctx.env.SBX_EFF).all()).results || [];
  const body = html`<h1 class="h1">Notifications</h1>
    <p class="intro">Le message que l’équipe recevrait à chaque nouvelle demande. Dans la démonstration, aucun e-mail n’est réellement envoyé : il est seulement consigné ici.</p>
    <ol class="mails">${rows.map((n) => html`<li class="card mail"><h2 class="h4">${n.subject}</h2><p class="quiet">Envoi simulé à ${n.to_addr}, le ${frDateTime(n.at)}</p><pre>${mailBody(n.body)}</pre><p><a class="lnk" href="/console/demandes/${n.enquiry_id}">Ouvrir ${n.ref}</a></p></li>`)}</ol>`;
  return page(ctx, 'Notifications', 'notif', body);
}

// ---------------------------------------------------------------- GM&E
async function activeGrant(env, userId, congressId) {
  return env.DB.prepare(`SELECT * FROM gme_requests WHERE sbx = ? AND congress_id = ? AND user_id = ? AND status = 'approuvee' AND expires_at > ? ORDER BY id DESC LIMIT 1`).bind(env.SBX_EFF, congressId, userId, nowIso()).first();
}
async function logAccess(env, userId, congressId, result) {
  if (!Number.isFinite(congressId)) return;
  await env.DB.prepare('INSERT INTO gme_access_log (sbx, at, user_id, congress_id, result) VALUES (?,?,?,?,?)').bind(env.SBX_EFF, nowIso(), userId, congressId, result).run();
}

async function gmeCard(ctx, c, { context = 'list', revealed = null, reqError = '', reqValue = '' } = {}) {
  const { env, user } = ctx;
  const g = await env.DB.prepare('SELECT congress_id, status, valid_from, valid_to, evidence, updated_at, (code_enc IS NOT NULL) AS has_code FROM gme_codes WHERE sbx = ? AND congress_id = ?').bind(env.SBX_EFF, c.id).first();
  const isDir = user.role === 'direction';
  const title = context === 'congress' ? html`<h2 class="h3">Code GM&amp;E</h2>` : html`<h2 class="h3"><a href="/console/congres/${c.id}">${c.title}</a></h2>`;
  if (!g && !isDir) return context === 'congress' ? html`<section class="card gme">${title}<p class="quiet">Aucun code GM&amp;E pour ce congrès.</p></section>` : '';
  const grant = !isDir && g ? await activeGrant(env, user.id, c.id) : null;
  const pending = !isDir && g ? await env.DB.prepare(`SELECT id FROM gme_requests WHERE sbx = ? AND congress_id = ? AND user_id = ? AND status = 'en_attente'`).bind(env.SBX_EFF, c.id, user.id).first() : null;
  const codeLine = revealed
    ? html`<p class="code code--on" data-revealed><span class="sr">Code : </span>${revealed}</p><p class="quiet">Affichage enregistré dans le journal d’accès.</p><p><a class="btn btn--line" href="/console/gme#gme-${c.id}">Masquer le code</a></p>`
    : html`<p class="code"><span aria-hidden="true">${MASK}</span><span class="sr">Code masqué</span></p>`;
  const meta = g ? html`<dl class="facts facts--tight">
      <div><dt>Statut</dt><dd>${pill(GME_KIND[g.status], GME_STATUS[g.status])}</dd></div>
      <div><dt>Validité</dt><dd>${g.valid_from || g.valid_to ? `${g.valid_from ? frNumDate(g.valid_from) : '…'} au ${g.valid_to ? frNumDate(g.valid_to) : '…'}` : 'À préciser'}</dd></div>
      <div><dt>Justificatif</dt><dd>${g.evidence || 'Aucun'}</dd></div>
    </dl>` : '';
  let action = '';
  if (g && g.has_code && !REVEALABLE.includes(g.status)) {
    action = html`<p class="wait">${g.status === 'expire' ? 'Code expiré : il ne peut plus être affiché ni demandé.' : 'Code non vérifié : il pourra être affiché ou demandé une fois vérifié.'}</p>`;
  } else if (g && g.has_code && !revealed) {
    if (isDir || grant) {
      action = html`<form method="post" action="/console/gme/${c.id}/afficher">${csrfInput(ctx.csrf)}<button class="btn" type="submit">Afficher le code</button></form>
        ${grant ? html`<p class="quiet">Accès accordé jusqu’au ${frDateTime(grant.expires_at)}.</p>` : ''}`;
    } else if (pending) {
      action = html`<p class="wait">Demande d’accès envoyée : en attente de la Direction.</p>`;
    } else {
      action = html`<form method="post" action="/console/gme/${c.id}/demande" class="stack req-form" novalidate>${csrfInput(ctx.csrf)}
        ${field({ id: `why-${c.id}`, name: 'reason', label: 'Motif de la demande', required: true, value: reqValue, error: reqError, attrs: 'maxlength="500" placeholder="Ex. : devis DV-2026-0002"' })}
        <button class="btn btn--line" type="submit">Demander l’accès</button></form>`;
    }
  }
  const manage = isDir && context === 'congress' ? html`<details class="manage"${g ? '' : raw(' open')}><summary class="btn btn--line">${g ? 'Modifier le code GM&E' : 'Ajouter un code GM&E'}</summary>
    <form method="post" action="/console/congres/${c.id}/gme" class="stack" novalidate>${csrfInput(ctx.csrf)}
      ${field({ id: 'g-code', name: 'code', label: g ? 'Nouveau code (laisser vide pour garder l’actuel)' : 'Code', attrs: 'maxlength="40" autocomplete="off" spellcheck="false" autocapitalize="characters"', required: !g })}
      ${select({ id: 'g-st', name: 'status', label: 'Statut', value: g?.status || 'detecte', options: Object.entries(GME_STATUS) })}
      ${field({ id: 'g-from', name: 'valid_from', label: 'Valable du', type: 'date', value: g?.valid_from || '' })}
      ${field({ id: 'g-to', name: 'valid_to', label: 'Valable au', type: 'date', value: g?.valid_to || '' })}
      ${field({ id: 'g-ev', name: 'evidence', label: 'Justificatif (note)', type: 'textarea', value: g?.evidence || '', attrs: 'rows="2" maxlength="1000"' })}
      <button class="btn btn--line" type="submit">Enregistrer le code</button>
    </form></details>` : '';
  return html`<section class="card gme" id="gme-${c.id}">${title}${g ? codeLine : html`<p class="quiet">Aucun code GM&amp;E pour ce congrès.</p>`}${meta}${action}${manage}</section>`;
}

async function gmeList(ctx, { revealFor = null, revealed = null, reqFor = null, reqError = '', reqValue = '', notice = '', status = 200 } = {}) {
  const { env, user } = ctx;
  const rows = (await env.DB.prepare(`SELECT c.id, c.title, c.ref FROM gme_codes g JOIN congresses c ON c.id = g.congress_id AND c.sbx = g.sbx WHERE g.sbx = ? ORDER BY CASE g.status WHEN 'approuve' THEN 0 WHEN 'verifie' THEN 1 WHEN 'detecte' THEN 2 ELSE 3 END, c.start_date`).bind(env.SBX_EFF).all()).results || [];
  const cards = [];
  for (const c of rows) cards.push(await gmeCard(ctx, c, { revealed: revealFor === c.id ? revealed : null, reqError: reqFor === c.id ? reqError : '', reqValue: reqFor === c.id ? reqValue : '' }));
  const ok = ctx.url.searchParams.get('ok');
  const body = html`<h1 class="h1">Codes GM&amp;E</h1>
    <p class="intro">${user.role === 'direction'
      ? 'Codes tarifaires Air France-KLM Global Meetings & Events, chiffrés en base. Chaque affichage est enregistré. Pour ajouter ou modifier un code, ouvrez le congrès.'
      : 'Les codes sont masqués. Pour en voir un, demandez l’accès avec un motif : la Direction l’accorde pour 24 heures.'}</p>
    ${ok === 'demande' ? html`<p class="ok" role="status" tabindex="-1" data-focus>Demande envoyée à la Direction.</p>` : ''}
    ${notice ? html`<p class="alert" role="alert" tabindex="-1" data-focus>${notice}</p>` : ''}
    <div class="gme-grid">${cards}</div>`;
  return page(ctx, 'Codes GM&E', 'gme', body, status);
}

async function gmeRequest(ctx, cid) {
  const { env, user, form } = ctx;
  if (user.role !== 'equipe') return deny(ctx, 'La Direction voit déjà les codes : aucune demande nécessaire.');
  const g = await env.DB.prepare(`SELECT congress_id, status FROM gme_codes WHERE sbx = ? AND congress_id = ? AND code_enc IS NOT NULL`).bind(env.SBX_EFF, cid).first();
  if (!g) return notFound(ctx);
  if (!REVEALABLE.includes(g.status)) return deny(ctx, 'Ce code n’est pas vérifié ou a expiré : aucune demande d’accès possible.');
  const reason = clean(form.get('reason'), 500);
  if (reason.length < 5) return gmeList(ctx, { reqFor: cid, reqValue: reason, reqError: 'Indiquez le motif de la demande (au moins 5 caractères).', status: 200 });
  if (reason.length > 500) return gmeList(ctx, { reqFor: cid, reqValue: reason.slice(0, 500), reqError: '500 caractères au maximum.', status: 200 });
  const pending = await env.DB.prepare(`SELECT id FROM gme_requests WHERE sbx = ? AND congress_id = ? AND user_id = ? AND status = 'en_attente'`).bind(env.SBX_EFF, cid, user.id).first();
  if (!pending) await env.DB.prepare(`INSERT INTO gme_requests (sbx, id, congress_id, user_id, reason, status, created_at) VALUES (?1, (SELECT COALESCE(MAX(id), 0) + 1 FROM gme_requests WHERE sbx = ?1), ?2, ?3, ?4, 'en_attente', ?5)`).bind(env.SBX_EFF, cid, user.id, reason, nowIso()).run();
  return redirect('/console/gme?ok=demande');
}

async function gmeReveal(ctx, cid) {
  const { env, user } = ctx;
  const c = await env.DB.prepare('SELECT c.id, c.title, g.status AS gme_status FROM congresses c JOIN gme_codes g ON g.congress_id = c.id AND g.sbx = c.sbx WHERE c.sbx = ? AND c.id = ? AND g.code_enc IS NOT NULL').bind(env.SBX_EFF, cid).first();
  if (!c) return notFound(ctx);
  if (!REVEALABLE.includes(c.gme_status)) {
    await logAccess(env, user.id, cid, 'refuse_statut');
    return deny(ctx, 'Ce code n’est pas vérifié ou a expiré : il ne peut pas être affiché. La tentative est enregistrée.');
  }
  let allowed = user.role === 'direction';
  if (user.role === 'equipe') allowed = !!(await activeGrant(env, user.id, cid));
  if (!allowed) {
    await logAccess(env, user.id, cid, 'refuse');
    return deny(ctx, user.role === 'equipe' ? 'Accès refusé : aucune autorisation active pour ce code (jamais accordée, révoquée ou expirée). La tentative est enregistrée.' : 'Votre rôle ne permet pas de voir les codes GM&E.');
  }
  const enc = (await env.DB.prepare('SELECT code_enc FROM gme_codes WHERE sbx = ? AND congress_id = ?').bind(env.SBX_EFF, cid).first()).code_enc;
  const code = await decryptCode(env, enc);
  await logAccess(env, user.id, cid, 'affiche');
  return gmeList(ctx, { revealFor: cid, revealed: code });
}

async function gmeSave(ctx, cid) {
  const { env, user, form } = ctx;
  const c = await env.DB.prepare('SELECT * FROM congresses WHERE sbx = ? AND id = ?').bind(env.SBX_EFF, cid).first();
  if (!c) return notFound(ctx);
  const g = await env.DB.prepare('SELECT congress_id FROM gme_codes WHERE sbx = ? AND congress_id = ?').bind(env.SBX_EFF, cid).first();
  const code = clean(form.get('code'), 40).toUpperCase();
  const status = form.get('status');
  const from = clean(form.get('valid_from'), 10); const to = clean(form.get('valid_to'), 10);
  const evidence = clean(form.get('evidence'), 1000);
  let err = '';
  if (!GME_STATUS[status]) err = 'Statut inconnu.';
  else if (!g && !code) err = 'Indiquez le code.';
  else if (code && !/^[A-Z0-9-]{4,40}$/.test(code)) err = 'Le code ne contient que des lettres, chiffres et tirets (4 à 40).';
  else if ((from && !isIsoDate(from)) || (to && !isIsoDate(to))) err = 'Dates de validité invalides.';
  else if (from && to && to < from) err = 'La fin de validité doit suivre le début.';
  else if (evidence.length > 1000) err = 'Justificatif trop long.';
  if (err) return congressForm(ctx, cid, { notice: `Code GM&E non enregistré : ${err}`, status: 200 });
  const now = nowIso();
  if (g) {
    if (code) await env.DB.prepare('UPDATE gme_codes SET code_enc=?, status=?, valid_from=?, valid_to=?, evidence=?, updated_at=?, updated_by=? WHERE sbx=? AND congress_id=?').bind(await encryptCode(env, code), status, from || null, to || null, evidence, now, user.id, env.SBX_EFF, cid).run();
    else await env.DB.prepare('UPDATE gme_codes SET status=?, valid_from=?, valid_to=?, evidence=?, updated_at=?, updated_by=? WHERE sbx=? AND congress_id=?').bind(status, from || null, to || null, evidence, now, user.id, env.SBX_EFF, cid).run();
  } else {
    await env.DB.prepare('INSERT INTO gme_codes (sbx, congress_id, code_enc, status, valid_from, valid_to, evidence, updated_at, updated_by) VALUES (?,?,?,?,?,?,?,?,?)').bind(env.SBX_EFF, cid, await encryptCode(env, code), status, from || null, to || null, evidence, now, user.id).run();
  }
  return redirect(`/console/congres/${cid}?ok=1`);
}

async function gmeAccess(ctx) {
  const { env } = ctx;
  const now = nowIso();
  const q = (where) => env.DB.prepare(`SELECT r.*, u.display_name, c.title, c.ref, d.display_name AS decider FROM gme_requests r JOIN users u ON u.id = r.user_id JOIN congresses c ON c.id = r.congress_id AND c.sbx = r.sbx LEFT JOIN users d ON d.id = r.decided_by WHERE r.sbx = ?1 AND (${where}) ORDER BY r.id DESC LIMIT 50`);
  const pending = (await q(`r.status = 'en_attente'`).bind(env.SBX_EFF).all()).results || [];
  const active = (await q(`r.status = 'approuvee' AND r.expires_at > ?2`).bind(env.SBX_EFF, now).all()).results || [];
  const past = (await q(`r.status IN ('refusee','revoquee') OR (r.status = 'approuvee' AND r.expires_at <= ?2)`).bind(env.SBX_EFF, now).all()).results || [];
  const label = (r) => r.status === 'refusee' ? 'Refusée' : r.status === 'revoquee' ? 'Révoquée' : 'Expirée';
  const ok = ctx.url.searchParams.get('ok');
  const msg = { approuvee: 'Accès accordé pour 24 heures.', refusee: 'Demande refusée.', revoquee: 'Accès révoqué immédiatement.' }[ok];
  const btn = (r, act, text, cls = 'btn') => html`<form method="post" action="/console/gme/acces/${r.id}">${csrfInput(ctx.csrf)}<button class="${cls}" type="submit" name="decision" value="${act}">${text}</button></form>`;
  const body = html`<h1 class="h1">Demandes d’accès aux codes GM&amp;E</h1>
    ${msg ? html`<p class="ok" role="status" tabindex="-1" data-focus>${msg}</p>` : ''}
    <section aria-labelledby="h-p"><h2 class="h2" id="h-p">Demandes en attente</h2>
      ${pending.length ? html`<ul class="reqs">${pending.map((r) => html`<li class="card req"><div><p><b>${r.display_name}</b> demande l’accès au code de <b>${r.title}</b></p><p class="quiet">Le ${frDateTime(r.created_at)}. Motif : <q>${r.reason}</q></p></div>
        <div class="req__act">${btn(r, 'approuver', 'Approuver pour 24 h')}${btn(r, 'refuser', 'Refuser', 'btn btn--line')}</div></li>`)}</ul>` : html`<p class="quiet">Aucune demande en attente.</p>`}
    </section>
    <section aria-labelledby="h-a"><h2 class="h2" id="h-a">Accès actifs</h2>
      ${active.length ? html`<ul class="reqs">${active.map((r) => html`<li class="card req"><div><p><b>${r.display_name}</b> peut afficher le code de <b>${r.title}</b></p><p class="quiet">Accordé par ${r.decider || 'la Direction'} le ${frDateTime(r.decided_at)}, jusqu’au ${frDateTime(r.expires_at)}.</p></div>
        <div class="req__act">${btn(r, 'revoquer', 'Révoquer maintenant', 'btn btn--line')}</div></li>`)}</ul>` : html`<p class="quiet">Aucun accès actif.</p>`}
    </section>
    ${past.length ? html`<section aria-labelledby="h-o"><h2 class="h2" id="h-o">Décisions passées</h2>
      <div class="wrap" role="region" aria-label="Décisions passées" tabindex="0"><table class="tbl"><thead><tr><th scope="col">Demandeur</th><th scope="col">Congrès</th><th scope="col">Motif</th><th scope="col">Décision</th><th scope="col">Par</th><th scope="col">Le</th></tr></thead>
      <tbody>${past.map((r) => html`<tr><td>${r.display_name}</td><td class="wide">${r.title}</td><td class="wide">${r.reason}</td><td>${label(r)}</td><td>${r.decider || 'Direction'}</td><td>${frDateTime(r.decided_at)}</td></tr>`)}</tbody></table></div></section>` : ''}`;
  return page(ctx, 'Demandes d’accès GM&E', 'acces', body);
}

async function gmeDecide(ctx, rid) {
  const { env, user, form } = ctx;
  const r = await env.DB.prepare('SELECT * FROM gme_requests WHERE sbx = ? AND id = ?').bind(env.SBX_EFF, rid).first();
  if (!r) return notFound(ctx);
  const d = form.get('decision');
  const now = new Date();
  if (d === 'approuver' && r.status === 'en_attente') {
    const exp = new Date(now.getTime() + GRANT_HOURS * 3600 * 1000).toISOString();
    await env.DB.prepare(`UPDATE gme_requests SET status='approuvee', decided_at=?, decided_by=?, expires_at=? WHERE sbx=? AND id=? AND status='en_attente'`).bind(now.toISOString(), user.id, exp, env.SBX_EFF, rid).run();
    return redirect('/console/gme/acces?ok=approuvee');
  }
  if (d === 'refuser' && r.status === 'en_attente') {
    await env.DB.prepare(`UPDATE gme_requests SET status='refusee', decided_at=?, decided_by=? WHERE sbx=? AND id=? AND status='en_attente'`).bind(now.toISOString(), user.id, env.SBX_EFF, rid).run();
    return redirect('/console/gme/acces?ok=refusee');
  }
  if (d === 'revoquer' && r.status === 'approuvee') {
    await env.DB.prepare(`UPDATE gme_requests SET status='revoquee', decided_at=?, decided_by=? WHERE sbx=? AND id=? AND status='approuvee'`).bind(now.toISOString(), user.id, env.SBX_EFF, rid).run();
    return redirect('/console/gme/acces?ok=revoquee');
  }
  return redirect('/console/gme/acces');
}

async function gmeJournal(ctx) {
  const rows = (await ctx.env.DB.prepare(`SELECT l.*, u.display_name, c.title, c.ref FROM gme_access_log l JOIN users u ON u.id = l.user_id JOIN congresses c ON c.id = l.congress_id AND c.sbx = l.sbx WHERE l.sbx = ? ORDER BY l.id DESC LIMIT 200`).bind(ctx.env.SBX_EFF).all()).results || [];
  const res = { affiche: 'Code affiché', refuse: 'Refusé : aucune autorisation', refuse_statut: 'Refusé : code non vérifié ou expiré' };
  const body = html`<h1 class="h1">Journal d’accès</h1>
    <p class="intro">Chaque affichage d’un code GM&amp;E, et chaque tentative refusée, est enregistré ici. Réservé à la Direction.</p>
    ${rows.length ? html`<div class="wrap" role="region" aria-label="Journal d’accès" tabindex="0"><table class="tbl"><thead><tr><th scope="col">Quand</th><th scope="col">Qui</th><th scope="col">Congrès</th><th scope="col">Résultat</th></tr></thead>
    <tbody>${rows.map((l) => html`<tr><td>${frDateTime(l.at)}</td><td>${l.display_name}</td><td class="wide">${l.title} (${nw(l.ref)})</td><td>${l.result === 'affiche' ? pill('pub', res.affiche) : pill('lost', res[l.result] || l.result)}</td></tr>`)}</tbody></table></div>`
    : html`<p class="quiet">Aucun affichage enregistré pour l’instant.</p>`}`;
  return page(ctx, 'Journal d’accès', 'journal', body);
}
