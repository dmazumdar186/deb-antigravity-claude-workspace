// Server-rendered board pages: the static redesign's _shell / job / jobs templates (frozen into
// site_assets.gen.js by tools/export_site_assets.py) filled from D1 rows. Paths mirror the static tree
// (/{site}/jobs/<slug>/), so the templates' relative links (../../index.html, ../index.html?sector=)
// land on the same pages as in the static build. Every value is escaped; descriptions are sanitised.

import { ANALYTICS, BRIEF, MAPS, SHELL, TEMPLATES } from '../site_assets.gen.js';
import {
  CONTRACT_LABEL, LOC_LABEL, SAVE_ICON, TAXONOMY, UNVERIFIED_NOTE, UNVERIFIED_SOURCE, WORKPLACE_LABEL, ago, contractRow,
  currencyNote, dateLong, edition, esc, isClosed, jobJsonLdPayload, jsonEmbed, jsonLd, locBadge, logoImg, noBreakDash, qs,
  roleCard, salaryLabel, salaryStrip, similarJobs, isUnverified, sepPair,
} from './lib.js';

export const NAV = [['jobs/index.html', 'Jobs'], ['sectors/index.html', 'Sectors'], ['insights/index.html', 'Salary explorer'],
  ['compass/index.html', 'Career compass'], ['employers/index.html', 'Employers']];
const BCORP_ALT = 'Certified B Corporation';
const BCORP_NOTE = 'B Corps are businesses independently certified for social and environmental performance, accountability and transparency.';
const MULTI_COUNT_NOTE = 'A role advertised in several {units} or sectors is counted in each, so totals can exceed the number of live roles.';
export const ROOT = '/';

/** render(): {{key}} substitution; values are already HTML; an unknown key throws (as in build_site.py). */
export function render(template, ctx) {
  return template.replace(/\{\{([a-zA-Z0-9_:]+)\}\}/g, (m, key) => {
    if (!Object.prototype.hasOwnProperty.call(ctx, key)) throw new Error(`template key {{${key}}} has no value`);
    return ctx[key];
  });
}

export const plural = (unit) => (unit.endsWith('y') && !'aeiou'.includes(unit.slice(-2, -1)) ? unit.slice(0, -1) + 'ies' : unit + 's');
const host = (url) => url.replace(/^https?:\/\/(www\.)?/, '').split('/')[0];

/**
 * analytics_ctx(): GA4 + Consent Mode v2 banner, ONLY when the request host is one of the edition's production
 * hosts (src/analytics.json production_hosts). Any other host (workers.dev staging, tests) gets the no-tracking
 * banner and no tag, meta or script, exactly as build_site.py --analytics off.
 */
export function analyticsCtx(site, host, root = ROOT) {
  const a = ANALYTICS[site];
  const h = String(host || '').toLowerCase().replace(/:\d+$/, '');
  if (!a || !h || !a.hosts.includes(h)) {
    return { analytics_head: '', analytics_script: '', cookie_attr: '', cookie_reject: '', cookie_accept: 'Accept',
      cookie_text: 'This site uses only essential storage (your theme, saved roles, and this choice). No tracking.' };
  }
  let head = `<meta name="gj-ga4" content="${esc(a.ga4)}" data-hosts="${esc(a.hosts.join(','))}">`;
  if (a.gsc_token) head = `<meta name="google-site-verification" content="${esc(a.gsc_token)}">` + head;
  return { analytics_head: head, analytics_script: `<script src="${root}js/analytics.js" defer></script>`,
    cookie_attr: ' data-cookie-ga', cookie_accept: 'Accept analytics',
    cookie_reject: '<button class="btn" type="button" data-cookie-reject>Essential only</button>',
    cookie_text: 'We use essential storage, and with your OK Google Analytics to see which pages help. Nothing analytics-related loads until you accept.' };
}

/** shell_ctx() with absolute paths: root "/" and the edition home "/{site}/". */
export function shellCtx(site, { page, title, desc, samePath = '', switchPath = '', canonical = '', nJobs = 0, today, bodyAttrs = '', indexable = false, reqHost = '' }) {
  const ed = edition(site);
  const data = SHELL[site];
  const root = ROOT;
  const home = `${root}${site}/`;
  const other = ed.other;
  const otherPath = switchPath || samePath || 'index.html';
  const cur = ' aria-current="page"';
  const nav = NAV.map(([href, label]) => `<a href="${home}${href}"${page === href.split('/')[0] ? cur : ''}>${label}</a>`).join('');
  const edsw = `<a href="${root}ie/${other === 'ie' ? otherPath : samePath || 'index.html'}" data-edswitch="ie" aria-current="${site === 'ie' ? 'true' : 'false'}" hreflang="en-IE">IE</a>`
    + `<a href="${root}uk/${other === 'uk' ? otherPath : samePath || 'index.html'}" data-edswitch="uk" aria-current="${site === 'uk' ? 'true' : 'false'}" hreflang="en-GB">UK</a>`;
  const net = data.network_sites.filter((s) => String(s.url || '').startsWith('http')).map((s) => `<li><a href="${esc(s.url)}" rel="noopener">${esc(s.name)}</a></li>`).join('');
  const raw = (data.contact.phones || []).filter(([, num]) => num).map(([lbl, num]) => [String(lbl), String(num)]);
  const ukNums = raw.filter(([lbl, n]) => lbl.toLowerCase().includes('outside') || n.trim().startsWith('+44')).map(([, n]) => n);
  const ieNums = raw.filter(([, n]) => !ukNums.includes(n)).map(([, n]) => n);
  let ordered = [...ukNums.slice(0, 1).map((n) => ['Calling from the UK', n]), ...ieNums.slice(0, 1).map((n) => ['Calling from Ireland', n])];
  if (site === 'ie') ordered = ordered.reverse();
  const phones = ordered.map(([lbl, num]) => `<li>${esc(lbl)}: <a href="tel:${esc(num.replace(/[^+0-9]/g, ''))}">${esc(num)}</a></li>`).join('');
  const emails = [...new Set(data.contact.emails || [])].map((e) => `<li><a href="mailto:${esc(e)}">${esc(e)}</a></li>`).join('');
  let bcorp = '';
  let hdrBcorp = '';
  let onepct = '';
  let bcorpFooter = '';
  if (BRIEF.b_corp && BRIEF.bcorp_size) {
    const [w, h] = BRIEF.bcorp_size;
    bcorp = `<img class="bcorp" src="${root}assets/logos/b-corp-logo.svg" alt="${BCORP_ALT}" title="${BCORP_NOTE}" width="${w}" height="${h}" loading="lazy">`;
    hdrBcorp = `<span class="hdr__bcorp" title="${BCORP_NOTE}"><img src="${root}assets/logos/b-corp-logo.svg" alt="${BCORP_ALT}" width="${w}" height="${h}"></span>`;
    bcorpFooter = `<p class="bcorp-line bcorp-line--footer">${bcorp}<span>${BCORP_NOTE}</span></p>`;
  }
  if (BRIEF.onepct_size) {
    const [w, h] = BRIEF.onepct_size;
    onepct = `<img src="${root}assets/logos/1fortheplanet.svg" alt="1% for the Planet member" width="${w}" height="${h}" loading="lazy" style="height:44px;width:auto;margin-top:12px;filter:brightness(1.4)">`;
  }
  const social = (data.social || []).slice(0, 4).map((u) => `<a href="${esc(u)}" rel="noopener" aria-label="${esc(host(u))}"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="1.8"/></svg></a>`).join('');
  return {
    head_extra: canonical ? `<link rel="canonical" href="${esc(canonical)}">` : '',
    ...analyticsCtx(site, reqHost, root),
    lang: ed.lang, title: esc(title), desc: esc(desc), root, home, ed: site, ED: ed.short, domain: esc(data.site), nav, menu_links: nav, edsw,
    hdr_cls: '', body_attrs: bodyAttrs, live_api: '1', api_base: '', net_sites: net, phones, emails, bcorp, hdr_bcorp: hdrBcorp, social,
    year: today.slice(0, 4), n_jobs: String(nJobs), fetched: esc(today), fetched_long: esc(dateLong(today)),
    social_wrap: social ? `<div class="ftr__social">${social}</div>` : '', demo_note: '', // a client board: no demo wording (eye r2 m1) canonical: canonical ? esc(canonical) : '',
    nav_list: NAV.map(([href, label]) => `<li><a href="${home}${href}">${label}</a></li>`).join(''),
    onepct, scripts: '', page, country: esc(ed.name), bcorp_footer: bcorpFooter, _indexable: indexable,
  };
}

/** The shell around `content`; the demo shell's robots noindex is lifted when the board is indexable. */
export function shellPage(ctx, content, scripts) {
  let out = render(TEMPLATES._shell, { ...ctx, content, scripts: scripts.map((s) => `<script src="${ctx.root}js/${s}.js" defer></script>`).join('') });
  if (ctx._indexable) out = out.replace('<meta name="robots" content="noindex,nofollow">', '<meta name="robots" content="index,follow">');
  return out;
}

// build_site.APPLY_FORM (eye review r2 N1/N2). The Worker serves its own /api/apply, so the action is same-origin.
const APPLY_FORM = (id, action = '/api/apply') => `<form class="job__apply-form" id="apply-form" method="post" action="${action}" enctype="multipart/form-data" data-apply-form data-ev="apply_submit" data-ev-job="${id}">
<h2 class="job__apply-h">Apply for this role</h2>
<input type="hidden" name="job_id" value="${id}"><input type="hidden" name="ts" value="" data-apply-ts>
<div hidden aria-hidden="true"><label for="ap-website">Leave blank <input id="ap-website" name="website" tabindex="-1" autocomplete="off"></label></div>
<div class="field"><label for="ap-name">Name</label><input class="in" id="ap-name" name="name" required maxlength="120" autocomplete="name" aria-describedby="ap-name-err"><p class="field__err" id="ap-name-err" data-apply-err="name" hidden></p></div>
<div class="field"><label for="ap-email">Email</label><input class="in" id="ap-email" name="email" type="email" required maxlength="254" autocomplete="email" aria-describedby="ap-email-err"><p class="field__err" id="ap-email-err" data-apply-err="email" hidden></p></div>
<div class="field"><label for="ap-phone">Phone <span class="field__opt">(optional)</span></label><input class="in" id="ap-phone" name="phone" type="tel" maxlength="40" autocomplete="tel" aria-describedby="ap-phone-err"><p class="field__err" id="ap-phone-err" data-apply-err="phone" hidden></p></div>
<div class="field"><label for="ap-cover">Cover note <span class="field__opt">(optional)</span></label><textarea class="in" id="ap-cover" name="cover_note" maxlength="5000" rows="4" aria-describedby="ap-cover-err"></textarea><p class="field__err" id="ap-cover-err" data-apply-err="cover_note" hidden></p></div>
<div class="field"><label for="ap-cv">CV <span class="field__opt">(optional, PDF or Word, up to 5 MB)</span></label><input class="in in--file" id="ap-cv" name="cv" type="file" accept=".pdf,.doc,.docx" aria-describedby="ap-cv-err"><p class="field__err" id="ap-cv-err" data-apply-err="cv" hidden></p></div>
<label class="check check--apply" for="ap-consent"><input id="ap-consent" type="checkbox" name="consent" value="yes" required aria-describedby="ap-consent-err"><span>Send my application to the advertiser of this job</span></label><p class="field__err" id="ap-consent-err" data-apply-err="consent" hidden></p>
<button class="btn btn--lime" type="submit">Send application</button>
<p class="note note--live" role="status" data-apply-status hidden></p>
</form>`;

/** apply_ctx(): link mode = external button (noopener nofollow); email mode = the on-site form to /api/apply. */
export function applyCtx(j, domain) {
  if (j.apply_mode === 'link') {
    const h = (() => { try { return new URL(j.apply_url).hostname; } catch { return ''; } })();
    return { apply_url: esc(j.apply_url), apply_rel: 'noopener nofollow', apply_label: `Apply on ${esc(h)}`, apply_form: '', apply_ev: ' data-ev="apply_click"' };
  }
  return { apply_url: '#apply-form', apply_rel: 'noopener', apply_label: 'Apply now', apply_form: APPLY_FORM(esc(j.id)), apply_ev: '' };
}

/** build_site.source_line (eye review r2 N9): a link-apply role is published on its own site, not "on greenjobs.ie". */
export function sourceLine(j, domain) {
  let host = '';
  if (j.apply_mode === 'link') { try { host = new URL(j.apply_url).hostname; } catch { host = ''; } }
  return `Description as published ${host ? `on ${esc(host)}` : `by the employer on ${domain}`}; reference ${esc(j.id)}.`;
}

/** One job page: the per-job loop body of build_edition(). */
export function jobPage(j, jobs, { site, today, canonical, indexable, reqHost = '' }) {
  const ed = edition(site);
  const domain = esc(SHELL[site].site);
  const similar = similarJobs(j, jobs, ed.currency, 4);
  const sal = salaryLabel(j, ed.currency);
  const note = currencyNote(j, ed.currency);
  const loc = j.location;
  const locDup = loc.trim().toLowerCase() === String(LOC_LABEL[j.loc_class] || '').toLowerCase();
  const badgeDup = j.loc_class === 'cross' && /\bUK\b|United Kingdom/.test(loc) && loc.includes('Ireland');
  const locChip = locDup ? '' : badgeDup ? `${LOC_LABEL[j.loc_class]} (nationwide)`
    : loc.replace(/,?\s*\b(United Kingdom \(UK\)|United Kingdom|UK|Ireland|Republic of Ireland)\s*(\(nationwide\))?$/, '').replace(/^[ ,]+|[ ,]+$/g, '') || loc;
  const meta = [locChip, j.type].filter(Boolean).map((x) => `<span class="tag">${esc(x)}</span>`).join('') + (badgeDup ? '' : locBadge(j))
    + (sal ? `<span class="tag tag--sal">${esc(sal)}</span>` : '')
    + (j.workplace !== 'unspecified' ? `<span class="tag tag--wp">${esc(WORKPLACE_LABEL[j.workplace])}</span>` : '');
  const where = LOC_LABEL[j.loc_class] || '';
  let countryOnly = /^(UK|United Kingdom( \(UK\))?|Ireland|Republic of Ireland|Northern Ireland|Remote)$/i.test(loc.trim());
  const namesCountry = /\b(UK|United Kingdom|Ireland)\b/i.test(loc);
  countryOnly = countryOnly || (j.loc_class === 'cross' && badgeDup);
  const locRow = loc.trim()
    ? ((locDup || countryOnly) && where ? (['ie', 'uk', 'ni', 'cross'].includes(j.loc_class) ? `${where} (nationwide)` : where)
      : loc + (where && !namesCountry && !loc.includes('(nationwide)') && j.loc_class !== 'unspecified' ? ` (${where})` : ''))
    : where;
  const salaryCell = (j.sal_text || sal || 'Not disclosed') + (note && sal.includes('about ') ? ` (${note.toLowerCase()}, about ${sal.split('about ').slice(1).join('about ').replace(/\)+$/, '')})` : '');
  const rows = [['Location', locRow], ['Workplace', j.workplace !== 'unspecified' ? WORKPLACE_LABEL[j.workplace] : ''], ['Contract', contractRow(j)], ['Level', j.level],
    ['Salary', salaryCell], ['Salary source', salarySourceLine(j)], ['Advertised by', j.agency ? 'Recruitment agency' : 'Direct employer'],
    ['Posted', j.posted ? dateLong(j.posted) : ''], ['Closes', j.closing ? dateLong(j.closing) : ''], ['Sector', j.sectors.join(', ')]];
  const dl = rows.filter(([, v]) => v).map(([k, v]) => `<dt>${k}</dt><dd>${esc(v)}</dd>`).join('');
  const bodyHtml = j.description_html || `<p>${esc(j.summary)}</p>`;
  const salCaveat = sal && isUnverified(j) ? `<p class="job__sal-caveat muted" data-sal-caveat>${esc(UNVERIFIED_NOTE)}.</p>` : '';
  const closedChip = `<span class="tag tag--closed" data-closed-chip${isClosed(j, today) ? '' : ' hidden'}>Closed</span>`;
  const sector = j.sectors[0] || '';
  const jsonld = `<script type="application/ld+json">${jsonLd(jobJsonLdPayload(j, site))}</script>`;
  const body = {
    jsonld, title: esc(noBreakDash(j.title)), employer: esc(j.employer), logo: logoImg(j, '/', 'job__logo'), sal_caveat: salCaveat, closed_chip: closedChip,
    meta, dl, desc_html: bodyHtml, ...applyCtx(j, domain), domain, source_line: sourceLine(j, domain), id: esc(j.id), region: esc(j.regions[0] || ''), closing: esc(j.closing || ''),
    sal_sticky: `<span class="job__sticky-sal">${esc(sal || 'Salary not disclosed')}</span>`,
    similar: similar.map((s) => roleCard(s, '/', '', today, ed.currency)).join(''),
    similar_hidden: similar.length ? '' : ' hidden', // eye M5: no empty block when nothing is similar
    sector_link: `../index.html?sector=${qs(sector)}`, sector: esc(sector),
    posted_line: j.posted ? esc(`Posted ${dateLong(j.posted)}` + (j.closing ? ` · closes ${dateLong(j.closing)}` : '')) : '',
    sits: sector ? salaryStrip(j, jobs, ed.sym, ed.unit, new Set(ed.regions), ed.currency) : '',
  };
  const ctx = shellCtx(site, {
    page: 'jobs', title: `${j.title} — ${j.employer} | GreenJobs ${ed.short}`, desc: (j.summary || j.title).slice(0, 155),
    samePath: `jobs/${j.slug}/index.html`, switchPath: 'jobs/index.html', canonical, nJobs: jobs.length, today, indexable, reqHost,
  });
  return shellPage(ctx, render(TEMPLATES.job, { ...ctx, ...body }), []);
}

function salarySourceLine(j) {
  if (j.currency_source === 'greenjobs.co.uk listing') return 'Salary figure taken from the same advert on greenjobs.co.uk, where it is advertised in sterling.';
  if (j.currency_source === UNVERIFIED_SOURCE) return UNVERIFIED_NOTE;
  return j.currency_source ? `Advertised in sterling on the ${j.currency_source}` : '';
}

// ---- the board list (jobs.html) ----------------------------------------------------------------
function selectPairs(id, label, pairs, anyLabel, selected = '') {
  const opts = pairs.map(([v, t]) => `<option value="${esc(v)}"${v === selected && selected ? ' selected' : ''}>${esc(t)}</option>`).join('');
  return `<div class="field"><label for="${id}">${label}</label><select class="in" id="${id}" name="${id.slice(2)}"><option value="">${anyLabel}</option>${opts}</select></div>`;
}

/** slim() + dataset_script(): the #gj-data block jobs.js filters client-side. */
export function slim(j, { publicId = false, text = true } = {}) {
  const out = {};
  for (const k of ['id', 'title', 'employer', 'location', 'regions', 'type', 'sal_min', 'sal_max', 'cur', 'period', 'sal_text', 'sectors', 'color', 'posted', 'closing', 'summary', 'logo', 'lw', 'lh', 'href',
    'loc_class', 'workplace', 'level', 'contract', 'agency']) out[k] = j[k];
  if (j.currency_source === UNVERIFIED_SOURCE) out.unverified_cur = true;
  if (publicId) out.id = j.slug; // the static build's id (Strategies id for imports): saved roles and hrefs line up
  if (text) out.text = j.text;
  return out;
}

/**
 * dataset_script()'s payload minus the jobs: the facet lists jobs.js / explore.js read from #gj-data.
 * Same rules as build_site.py (sectors with n > 0, on-map regions, types, contract_facet order).
 */
export function datasetFacets(site, all, tally) {
  const ed = edition(site);
  return {
    sectors: tally.sectors.filter((s) => s.n > 0), regions: tally.regions.filter((r) => r.on_map), types: tally.types,
    contracts: Object.entries(CONTRACT_LABEL).map(([k, name]) => ({ k, name, n: all.filter((j) => j.contract.includes(k)).length })).filter((c) => c.n),
    currency: ed.currency, regionUnit: ed.unit[0].toUpperCase() + ed.unit.slice(1), home: ed.home, edition: site,
  };
}

/** The jobs.js row() markup, server-rendered so the list works (and is crawlable) before or without JS. */
export function listRow(j, today, edCur) {
  const sal = salaryLabel(j, edCur);
  const lc = LOC_LABEL[j.loc_class] || '';
  const sec = j.sectors[0] ? `<span class="tag tag--sec"><i style="background:${esc(j.color || '')}"></i><span class="tag__t">${esc(j.sectors[0])}</span></span>` : '';
  return `<article class="row" data-id="${esc(j.id)}">${logoImg(j, '/')}`
    + `<div class="row__body"><h3><a href="${esc(j.href)}">${esc(j.title)}</a></h3>`
    + `<div class="row__meta">${sepPair(j.location, j.employer)}${sal ? `<span class="tag tag--sal"><span class="tag__t">${esc(sal)}</span></span>` : ''}`
    + `${lc ? `<span class="tag tag--loc" data-loc="${esc(j.loc_class)}">${esc(lc)}</span>` : ''}${sec}${j.level ? `<span class="tag tag--lvl" title="Career level">${esc(j.level)}</span>` : ''}</div>`
    + (j.currency_source === UNVERIFIED_SOURCE ? `<p class="role__note">${esc(UNVERIFIED_NOTE)}.</p>` : '') + '</div>'
    + `<div class="row__r"><time datetime="${esc(j.posted || '')}">${esc(ago(j.posted, today))}</time><span>${esc(j.type || '')}</span></div>`
    + `<button class="save" type="button" data-save="${esc(j.id)}" data-title="${esc(j.title)}" aria-pressed="false" aria-label="Save: ${esc(j.title)}">${SAVE_ICON}</button></article>`;
}

export function listPage({ site, today, all, shown, page, pages, filters, tally, canonical, indexable, heading = '', samePath = 'jobs/index.html', reqHost = '' }) {
  const ed = edition(site);
  const topRegions = tally.regions.filter((r) => r.on_map);
  const facets = datasetFacets(site, all, tally);
  const payload = {
    today, jobs: all.map((j) => slim(j)), sectors: facets.sectors, regions: facets.regions, types: facets.types, contracts: facets.contracts,
    currency: facets.currency, regionUnit: facets.regionUnit, jobsHref: `/${site}/jobs/index.html`, home: facets.home, edition: site,
    live: true, // rendered from D1 on this request: api.js does not re-fetch it
  };
  const pagesPalette = jsonEmbed([...NAV.map(([href, lbl]) => ({ t: lbl, h: `/${site}/${href}` })), { t: 'Home', h: `/${site}/index.html` }]);
  const mapList = topRegions.map((r) => `<a href="/${site}/jobs/index.html?loc=${qs(r.name)}"${r.n ? '' : ' class="is-zero"'}><span>${esc(r.name)}</span><b class="num">${r.n}</b></a>`).join('');
  const fit = render(TEMPLATES._fit, {
    jobs_href: `/${site}/jobs/index.html`, sym: ed.sym, fit_id: 'fit-q', n_jobs: String(all.length), fit_map: MAPS[site],
    fit_examples: SHELL[site].fit_examples.map((x) => `<button type="button" data-fit-eg="${esc(x)}">${esc(x)}</button>`).join(''),
    fit_placeholder: esc(SHELL[site].fit_placeholder),
  });
  const items = all.slice(0, 50).map((j, i) => ({ '@type': 'ListItem', position: i + 1, url: j.url, name: j.title }));
  const has = (pred) => all.some(pred);
  const body = {
    dataset: `<script type="application/json" id="gj-data">${jsonEmbed(payload)}</script>`,
    jsonld: `<script type="application/ld+json">${jsonLd({ '@context': 'https://schema.org', '@type': 'ItemList', itemListElement: items })}</script>`,
    loc_options: topRegions.map((r) => `<option value="${esc(r.name)}">`).join(''),
    sector_select: selectPairs('f-sector', 'Sector', tally.sectors.filter((s) => s.n).map((s) => [s.name, s.name]), 'All sectors', filters.sector),
    type_select: `<input type="hidden" id="f-type" name="type" value="${esc(filters.type)}">`,
    wp_select: selectPairs('f-wp', 'Workplace', ['office', 'hybrid', 'remote', 'site', 'unspecified'].filter((k) => has((j) => j.workplace === k)).map((k) => [k, WORKPLACE_LABEL[k]]), 'Any workplace'),
    level_select: selectPairs('f-level', 'Career level', TAXONOMY.levels.filter((lv) => has((j) => j.level === lv)).map((lv) => [lv, lv]), 'Any level'),
    ct_select: selectPairs('f-ct', 'Contract', Object.keys(CONTRACT_LABEL).filter((k) => has((j) => j.contract.includes(k))).map((k) => [k, CONTRACT_LABEL[k]]), 'Any contract'),
    close_select: selectPairs('f-close', 'Closing date', [['7', 'Closing within 7 days'], ['14', 'Closing within 14 days'], ['30', 'Closing within 30 days'], ['open', 'Hide closed roles']], 'Any closing date'),
    emp_select: selectPairs('f-emp', 'Advertised by', [['direct', 'Direct employer'], ['agency', 'Recruitment agency']], 'Employers and agencies'),
    only_label: esc(site === 'ie' ? 'Hide UK/abroad-only roles' : 'Hide Ireland/abroad-only roles'),
    only_hint: esc(site === 'ie' ? 'Keeps Ireland, Northern Ireland, remote and Ireland-and-UK roles; hides roles advertised only in the UK or abroad.' : 'Keeps UK, Northern Ireland, remote and Ireland-and-UK roles; hides roles advertised only in Ireland or abroad.'),
    cur: ed.currency, sym: ed.sym, units: plural(ed.unit), multi_note: esc(MULTI_COUNT_NOTE.replace('{units}', plural(ed.unit))),
    unit: ed.unit[0].toUpperCase() + ed.unit.slice(1), map: MAPS[site], map_counts: mapList, pages: esc(pagesPalette), n_jobs: String(all.length), fit_panel: fit,
  };
  let content = render(TEMPLATES.jobs, body);
  // Server rows + pager inside the list container; jobs.js re-renders it from #gj-data once it runs.
  const rows = shown.map((j) => listRow(j, today, ed.currency)).join('') || '<p class="muted">No live roles match these filters.</p>';
  const qsBase = new URLSearchParams(['q', 'sector', 'loc', 'type'].filter((k) => filters[k]).map((k) => [k, filters[k]]));
  const link = (p) => { const q = new URLSearchParams(qsBase); if (p > 1) q.set('page', String(p)); const s = q.toString(); return s ? `?${esc(s)}` : '?'; };
  const pager = pages > 1 ? `<nav class="pager" aria-label="Pages">${page > 1 ? `<a rel="prev" href="${link(page - 1)}">Previous</a>` : ''}<span>Page ${page} of ${pages}</span>${page < pages ? `<a rel="next" href="${link(page + 1)}">Next</a>` : ''}</nav>` : '';
  content = content.replace('<div class="list" data-list></div>', `<div class="list" data-list>${rows}</div>${pager}`);
  content = content.replace('<p class="count" data-count aria-live="polite" aria-atomic="true"><b>' + String(all.length) + '</b> roles</p>',
    `<p class="count" data-count aria-live="polite" aria-atomic="true"><b>${filters.total}</b> roles</p>`);
  if (heading) content = content.replace('<h1>Search live roles</h1>', `<h1>${esc(heading)}</h1>`);
  const ctx = shellCtx(site, {
    page: 'jobs', title: `${heading || `Green jobs across ${ed.name}`} — search ${all.length} live roles | GreenJobs ${ed.short}`,
    desc: `Filter ${all.length} live environmental and renewable energy roles by ${ed.unit}, sector, type and salary.`,
    samePath, canonical, nJobs: all.length, today, indexable, reqHost,
  });
  return shellPage(ctx, content, ['jobs', 'fit']);
}

/** 410 for a closed / expired role, 404 for an unknown one: the shell with a link back to the list. */
export function gonePage({ site, today, status, title, nJobs, reqHost = '' }) {
  const ed = edition(site);
  const lede = status === 410 ? 'This role is no longer advertised: the employer has closed it or its closing date has passed.' : 'We could not find that role. It may have moved or never existed.';
  const content = `<div class="wrap pagehead"><h1>${status === 410 ? 'This role has closed' : 'Role not found'}</h1>`
    + `<p class="lede">${lede}${title ? ` (${esc(title)})` : ''}</p>`
    + `<p><a class="btn btn--lime" href="/${site}/jobs/index.html">See all ${nJobs} live roles<span class="arw" aria-hidden="true">→</span></a></p></div>`;
  const ctx = shellCtx(site, { page: 'jobs', title: `${status === 410 ? 'Role closed' : 'Not found'} | GreenJobs ${ed.short}`, desc: lede, samePath: 'jobs/index.html', nJobs, today, indexable: false, reqHost });
  return shellPage(ctx, content, []); // always noindex: a gone or missing role is never indexed
}

export function sitemap(urls) {
  const body = urls.map((u) => `<url><loc>${esc(u.loc)}</loc>${u.lastmod ? `<lastmod>${esc(u.lastmod)}</lastmod>` : ''}</url>`).join('');
  return `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">${body}</urlset>\n`;
}
