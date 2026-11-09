// Page shells and small form helpers. Plain French, no JavaScript required.
import { html, raw } from './lib.js';
import { DEMO_BUSY, DEMO_PAUSE } from './data.js';
const banner = (busy) => (busy === 'pause' ? DEMO_PAUSE : DEMO_BUSY);

// Bump when app.css or app.js change: assets are cached for a year under a versioned URL.
export const ASSET_V = '8';

const head = (title, description) => html`<html lang="fr"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>${title}</title>
<meta name="description" content="${description}">
<meta name="robots" content="noindex,nofollow">
<meta name="theme-color" content="#0a1f30">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="preload" href="/assets/fonts/EBGaramond.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="/assets/fonts/Inter.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/assets/app.css?v=${ASSET_V}">
<script src="/assets/app.js?v=${ASSET_V}" defer></script>
</head>`;

export function publicPage({ title, description = 'Démonstration ASSET Voyages : catalogue des congrès et demande de devis vol. Données fictives.', body, current = 'cat', busy = false }) {
  return html`${head(title, description)}
<body class="pub">
<a class="skip" href="#main">Aller au contenu</a>
<header class="top">
  <a class="brand" href="/" aria-label="ASSET Voyages, catalogue des congrès">ASSET <span>Voyages</span></a>
  <p class="top__note">Démonstration avec des données fictives</p>
  <nav class="top__nav" aria-label="Navigation principale">
    <a href="/"${current === 'cat' ? raw(' aria-current="page"') : ''}>Congrès</a>
    <a href="/console">Espace équipe</a>
  </nav>
</header>
<main id="main">${busy ? html`<p class="busy" role="status" tabindex="-1" data-focus>${banner(busy)}</p>` : ''}${body}</main>
<footer class="foot">
  <div class="foot__in">
    <p class="foot__brand">ASSET <span>Voyages</span></p>
    <p>Voyages d’affaires, séminaires et congrès internationaux. Cette démonstration montre la plateforme sur mesure proposée (option B) ; congrès, demandes et codes tarifaires sont des exemples.</p>
    <p><a href="/">Catalogue des congrès</a><br><a href="/console">Espace équipe</a></p>
  </div>
</footer>
</body></html>`;
}

// « Lien de groupe » public pages: the same shell, without the catalogue navigation or any mention of fares.
export function groupPage({ title, body }) {
  return html`${head(title, 'Voyage de groupe ASSET Voyages : vos informations de voyage. Démonstration, données fictives.')}
<body class="pub">
<a class="skip" href="#main">Aller au contenu</a>
<header class="top">
  <p class="brand">ASSET <span>Voyages</span></p>
  <p class="top__note">Démonstration avec des données fictives</p>
</header>
<main id="main">${body}</main>
<footer class="foot">
  <div class="foot__in">
    <p class="foot__brand">ASSET <span>Voyages</span></p>
    <p>Voyages d’affaires, séminaires et congrès internationaux. Ce lien sert uniquement à recueillir les informations de voyage des participants d’un groupe.</p>
  </div>
</footer>
</body></html>`;
}

const NAV = [
  { key: 'dash', href: '/console', label: 'Tableau de bord', roles: ['direction', 'equipe', 'contributeur'] },
  { key: 'cg', href: '/console/congres', label: 'Congrès', roles: ['direction', 'equipe', 'contributeur'] },
  { key: 'dem', href: '/console/demandes', label: 'Demandes', roles: ['direction', 'equipe'] },
  // Labels follow 29_Glossary_Labels.md (CE-B6): one name per thing in the hub, Option A and Option B.
  { key: 'notif', href: '/console/notifications', label: 'Journal des notifications', roles: ['direction', 'equipe'] },
  // The group heading is itself a link to the codes (CE-C10-002: the hub says « open Codes GM&E »).
  { group: 'Codes GM&E', href: '/console/gme', roles: ['direction', 'equipe'] },
  { key: 'gme', href: '/console/gme', label: 'Codes', roles: ['direction', 'equipe'], sub: true },
  { key: 'acces', href: '/console/gme/acces', label: 'Demandes d’accès', srSuffix: ' GM&E', roles: ['direction'], sub: true },
  { key: 'journal', href: '/console/gme/journal', label: 'Journal d’accès GM&E', roles: ['direction'], sub: true },
];

export function consolePage({ title, user, csrf, current, body, badges = {}, busy = false }) {
  return html`${head(title + ' | Console ASSET', 'Console ASSET (démonstration) : congrès, demandes et codes GM&E.')}
<body class="con">
<a class="skip" href="#main">Aller au contenu</a>
<header class="ctop">
  <a class="brand" href="/console">ASSET <span>Console</span></a>
  <p class="ctop__who">${user.display_name}</p>
  <form method="post" action="/console/deconnexion" class="ctop__out"><input type="hidden" name="_csrf" value="${csrf}"><button class="btn btn--ghost" type="submit">Se déconnecter</button></form>
</header>
<div class="shell">
  <nav class="side" aria-label="Console">
    ${NAV.filter((n) => n.roles.includes(user.role)).map((n) => n.group ? html`<a class="side__h" href="${n.href}">${n.group}</a>` : html`<a href="${n.href}"${n.sub ? raw(' class="side__sub"') : ''}${n.key === current ? raw(' aria-current="page"') : ''}>${n.label}${n.srSuffix ? html`<span class="sr">${n.srSuffix}</span>` : ''}${badges[n.key] ? html` <span class="count">${badges[n.key]}</span><span class="sr"> en attente</span>` : ''}</a>`)}
    <a href="/">Voir le site public</a>
  </nav>
  <main id="main" class="cmain">
    ${busy ? html`<p class="busy" role="status" tabindex="-1" data-focus>${banner(busy)}</p>` : ''}
    <p class="sandbox">Bac à sable privé : données fictives, vos essais ne sont visibles que dans ce navigateur, aucun e-mail réel n’est envoyé.</p>
    ${body}
  </main>
</div>
</body></html>`;
}

export function loginPage({ token, error, next, notice }) {
  return html`${head('Connexion | Console ASSET', 'Connexion à la console ASSET (démonstration).')}
<body class="con con--login">
<a class="skip" href="#main">Aller au contenu</a>
<main id="main" class="login">
  <div class="login__card">
    <a class="brand brand--ink" href="/">ASSET <span>Voyages</span></a>
    <h1 class="h1">Espace équipe</h1>
    <p class="private">Votre bac à sable est privé : vos essais ne sont visibles que dans ce navigateur.</p>
    ${notice ? html`<p class="ok" role="status" tabindex="-1" data-focus>${notice}</p>` : ''}
    ${error ? html`<p class="alert" role="alert" tabindex="-1" data-focus>${error}</p>` : ''}
    <form method="post" action="/console/connexion" class="stack">
      <input type="hidden" name="_token" value="${token}">
      <input type="hidden" name="next" value="${next || ''}">
      <div class="field"><label for="u">Identifiant</label><input id="u" name="username" autocomplete="username" required autocapitalize="none" spellcheck="false"></div>
      <div class="field"><label for="p">Mot de passe</label><input id="p" name="password" type="password" autocomplete="current-password" required></div>
      <button class="btn" type="submit">Se connecter</button>
    </form>
  </div>
  <aside class="login__demo" aria-labelledby="demo-h">
    <h2 id="demo-h" class="h3">Comptes de démonstration</h2>
    <p>Mot de passe pour les trois comptes : <code>demo-asset</code> (bac à sable).</p>
    <dl class="accounts">
      <div><dt><code>direction</code></dt><dd>Hélène Martin, Direction ASSET : tout, y compris les codes GM&amp;E et les autorisations.</dd></div>
      <div><dt><code>equipe</code></dt><dd>Karim Benali, Équipe ASSET : congrès et demandes ; codes GM&amp;E masqués, accès sur demande.</dd></div>
      <div><dt><code>contributeur</code></dt><dd>Julie Roux, contributrice : prépare des brouillons et les soumet à relecture, sans publier.</dd></div>
    </dl>
  </aside>
</main>
</body></html>`;
}

export function errorPage({ status, title, text, user, csrf, back = '/' }) {
  const body = html`<section class="msg"><h1 class="h1" tabindex="-1" data-focus>${title}</h1><p>${text}</p><p><a class="btn btn--line" href="${back}">Revenir</a></p></section>`;
  if (user) return consolePage({ title, user, csrf, current: '', body });
  return publicPage({ title: `${title} | ASSET Voyages`, body, current: '' });
}

// ---------- form helpers ----------
export function field({ id, name, label, value = '', type = 'text', required = false, error, hint, attrs = '', full = false, optional = false }) {
  const describedBy = [hint ? `${id}-h` : '', error ? `${id}-e` : ''].filter(Boolean).join(' ');
  const req = required ? html` <span class="req" aria-hidden="true">*</span>` : optional ? html` <span class="opt">(facultatif)</span>` : '';
  const common = html`id="${id}" name="${name}"${required ? raw(' required aria-required="true"') : ''}${error ? raw(' aria-invalid="true"') : ''}${describedBy ? html` aria-describedby="${describedBy}"` : ''} ${raw(attrs)}`;
  const control = type === 'textarea'
    ? html`<textarea ${common}>${value}</textarea>`
    : html`<input type="${type}" value="${value}" ${common}>`;
  return html`<div class="field${full ? ' field--full' : ''}${error ? ' field--err' : ''}">
    <label for="${id}">${label}${req}</label>
    ${hint ? html`<p class="hint" id="${id}-h">${hint}</p>` : ''}
    ${control}
    ${error ? html`<p class="err" id="${id}-e">${error}</p>` : ''}
  </div>`;
}
export function select({ id, name, label, options, value = '', error, required = false, attrs = '' }) {
  return html`<div class="field${error ? ' field--err' : ''}">
    <label for="${id}">${label}${required ? html` <span class="req" aria-hidden="true">*</span>` : ''}</label>
    <select id="${id}" name="${name}"${error ? raw(' aria-invalid="true"') : ''}${error ? html` aria-describedby="${id}-e"` : ''} ${raw(attrs)}>
      ${options.map(([v, l]) => html`<option value="${v}"${String(v) === String(value) ? raw(' selected') : ''}>${l}</option>`)}
    </select>
    ${error ? html`<p class="err" id="${id}-e">${error}</p>` : ''}
  </div>`;
}
// Error summary: one link per field, « Libellé : message », focus lands here after a failed submit.
export function errorSummary(errors, labels, ids) {
  const keys = Object.keys(errors);
  if (!keys.length) return '';
  return html`<div class="alert alert--list" role="alert" id="form-errors" tabindex="-1" data-focus>
    <p>${keys.length > 1 ? `${keys.length} champs à corriger` : 'Un champ à corriger'} ; rien n’a été enregistré.</p>
    <ul>${keys.map((k) => html`<li><a href="#${ids[k] || k}">${labels[k] || k} : ${errors[k]}</a></li>`)}</ul>
  </div>`;
}
// Display titles break between words only (EYE-X-001); a run with no space at all longer than 24 characters (a URL, a
// code) is the last-resort case allowed to break inside.
export const displayWrap = (text) => (String(text).split(/[\s ]+/).some((w) => w.length > 24) ? ' display--wrap' : '');
export const pill =(kind, label) => html`<span class="st st--${kind}">${label}</span>`;
export const csrfInput = (csrf) => html`<input type="hidden" name="_csrf" value="${csrf}">`;
