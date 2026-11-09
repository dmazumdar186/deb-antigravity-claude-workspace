// Text rules for the client-eye gate (28_PreMortem_Client_Eye_Gate.md). Each rule returns findings
// { check, text, element, note }. Rules never get looser to reach green: any tightening carries a comment saying
// which false positive it removes and why the defect class it guards is still caught.

const norm = (s) => String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
const clip = (s, n = 160) => { s = String(s); return s.length > n ? s.slice(0, n) + '…' : s; };

// ---------- A3: placeholder / template residue
// Case-sensitive where the word is also ordinary language: « null » is only flagged as the bare token.
const A3 = [
  [/will appear here/i, 'will appear here'], [/\bREPLACE\b/, 'REPLACE'], [/\bTODO\b/, 'TODO'], [/\blorem\b/i, 'lorem'],
  [/\bundefined\b/, 'undefined'], [/\bNaN\b/, 'NaN'], [/\bnull\b/, 'null'], [/\[object Object\]/, '[object Object]'],
  [/\{\{/, '{{'], [/%s\b|%d\b|%1\$s/, '%s'], [/\bXXX\b/, 'XXX'],
];
export function ruleA3(item) {
  const f = [];
  for (const [re, name] of A3) if (re.test(item.t)) f.push({ check: 'A3', text: clip(item.t), element: item.path + (item.a ? ` [${item.a}]` : ''), note: `contains « ${name} »` });
  return f;
}

// ---------- C8: technical residue in visible text
// Tightened: the spec's bare « at » is matched as a stack frame (« at fn (file:1:2) » or « at file.js:1 ») because
// the English hub legitimately says "at" in sentences. « stack » is matched as a word. Every other token is literal.
const C8 = [
  [/\bError:/, 'Error:'], [/\bat [\w.$<>\[\]]+ \(?[\w./:-]+:\d+(:\d+)?\)?/, 'stack frame « at … »'], [/\bstack\b/i, 'stack'], [/Exception/, 'Exception'],
  [/\bFatal\b/i, 'Fatal'], [/\bWarning:/, 'Warning:'], [/\bNotice:/, 'Notice:'], [/\bDeprecated\b/, 'Deprecated'], [/SQLITE/i, 'SQLITE'],
  [/\bD1_/, 'D1_'], [/TypeError|ReferenceError|SyntaxError/, 'JS error class'], [/\bundefined\b/, 'undefined'],
  [/[{}]/, 'brace { } (JSON / template)'], [/<!--\s*wp:/, 'raw <!-- wp: markup'], [/\b[0-9a-f]{16,}\b/i, 'hex run ≥ 16'],
  [/Worker threw|Uncaught|exceeded|Internal Server Error/i, 'runtime error text'], [/\b(content-type|x-[a-z-]+|set-cookie):/i, 'HTTP header'],
];
export function ruleC8(item) {
  const f = [];
  for (const [re, name] of C8) {
    const m = re.exec(item.t);
    if (!m) continue;
    // A 16+ hex run inside a URL path the reader is meant to copy (group link) is still reported: the reader sees it.
    f.push({ check: 'C8', text: clip(item.t), element: item.path + (item.a ? ` [${item.a}]` : ''), note: `${name}: « ${clip(m[0], 60)} »` });
  }
  return f;
}

// ---------- C9: test residue in sample data (demos only)
const C9 = [[/=cmd|=HYPERLINK|=SUM\(/i, 'formula'], [/<script|<img|onerror=|javascript:/i, 'markup'], [/AUDIT-PROBE|PROBE|\bprobe\b/i, 'probe'],
  [/\btest\b|\btests\b|\bTEST\b/i, 'test'], [/\blorem\b|ipsum/i, 'lorem'], [/\bhostile\b|\bxss\b|\bpwn|\bfoo\b|\bbar\b|\basdf|\bqwerty|\baaaa+/i, 'junk word'], [/\balert\(/i, 'alert('], [/'\);|--\s*$|DROP TABLE|DELETE FROM/i, 'SQL']];
export function ruleC9(item) {
  const f = [];
  for (const [re, name] of C9) { const m = re.exec(item.t); if (m) f.push({ check: 'C9', text: clip(item.t), element: item.path, note: `${name}: « ${m[0]} »` }); }
  return f;
}

// ---------- B1: language mixing
const EN_UI = ['Howdy', 'Dashboard', 'Posts', 'Comments', 'Appearance', 'Plugins', 'Users', 'Settings', 'Submit', 'Save', 'Loading', 'Error', 'Cancel', 'Close', 'Search', 'Update', 'Delete', 'Edit', 'View', 'Preview', 'Log Out', 'Log In', 'Logout', 'Username', 'Password', 'Remember Me', 'Lost your password', 'Add New', 'Next', 'Previous', 'Back', 'Welcome', 'Thank you', 'Please', 'Required', 'Upload', 'Download', 'Help', 'Screen Options', 'Skip to content', 'Select', 'Untitled', 'Draft', 'Published', 'Pending', 'Trash', 'Reply', 'Read more', 'Sign in', 'Sign out', 'Send', 'Yes', 'No'];
const EN_UI_RE = new RegExp('(?<![\\p{L}-])(' + EN_UI.map((w) => w.replace(/ /g, '\\s+')).join('|') + ')(?![\\p{L}-])', 'u');
// English function words that do not exist as French words (« on », « a », « or », « as », « an » removed: they are French).
const EN_STOP = new Set(['the', 'and', 'of', 'to', 'is', 'with', 'for', 'your', 'you', 'this', 'that', 'are', 'was', 'has', 'have', 'will', 'can', 'not', 'by', 'from', 'at', 'it', 'be', 'we', 'our', 'they', 'which', 'there', 'been', 'into', 'here', 'please']);
const FR_STOP = new Set(['le', 'la', 'les', 'des', 'du', 'une', 'et', 'est', 'pour', 'avec', 'dans', 'sur', 'vous', 'votre', 'vos', 'nous', 'au', 'aux', 'cette', 'sont', 'pas', 'qui', 'que', 'mais', 'où', 'être', 'été', 'ou', 'leur', 'ces']);
const tokens = (s) => (s.match(/[\p{L}’']+/gu) || []).map((w) => w.toLowerCase());
const stripUrls = (s) => s.replace(/https?:\/\/\S+/g, ' ').replace(/[\w.+-]+@[\w-]+(\.[\w-]+)+/g, ' ');
export function ruleB1French(item) {
  // French UI: no English UI words, no runs of English function words. Text inside <code>/<kbd> (usernames) is skipped.
  if (item.code) return [];
  const s = stripUrls(item.tNoCode || item.t).replace(/⟦code⟧/g, ' ');
  const f = [];
  const m = EN_UI_RE.exec(s);
  if (m) f.push({ check: 'B1', text: clip(item.t), element: item.path + (item.a ? ` [${item.a}]` : ''), note: `English UI word « ${m[1]} » in a French screen` });
  const tk = tokens(s);
  for (let i = 0; i < tk.length; i++) {
    if (tk[i] === 'the' || (EN_STOP.has(tk[i]) && EN_STOP.has(tk[i + 1]))) { f.push({ check: 'B1', text: clip(item.t), element: item.path, note: `English words « ${tk.slice(i, i + 3).join(' ')} » in a French screen` }); break; }
  }
  return f;
}
export function ruleB1English(item) {
  // English page: French only inside « ». <code> runs (usernames) are skipped.
  if (item.code) return [];
  let s = (item.tNoCode || item.t).replace(/«[^»]*»/g, ' ').replace(/⟦code⟧/g, ' ');
  s = stripUrls(s);
  const tk = tokens(s);
  const hits = tk.filter((w) => FR_STOP.has(w) || /[éèêàùçôîâœ]/.test(w));
  // Proper names that carry accents in English too (none expected): the list stays empty on purpose.
  if (!hits.length) return [];
  return [{ check: 'B1', text: clip(item.t), element: item.path + (item.a ? ` [${item.a}]` : ''), note: `French outside « »: ${[...new Set(hits)].slice(0, 6).join(', ')}` }];
}

// ---------- B2: dates
export function ruleB2(item) {
  const f = [];
  const s = item.t;
  let m;
  const iso = /(?<![\w/-])(\d{4})-(\d{2})-(\d{2})(?![\w-])/g;
  while ((m = iso.exec(s))) f.push({ check: 'B2', text: clip(s), element: item.path, note: `ISO date « ${m[0]} » shown to a reader` });
  const sl = /(?<![\w/])(\d{1,2})\/(\d{1,2})\/(\d{2,4})(?![\w/])/g;
  while ((m = sl.exec(s))) {
    const [all, d, mo, y] = m;
    const valid = (dd, mm, yy) => { const D = new Date(Date.UTC(+yy, +mm - 1, +dd)); return D.getUTCFullYear() === +yy && D.getUTCMonth() === +mm - 1 && D.getUTCDate() === +dd; };
    if (y.length !== 4 || d.length !== 2 || mo.length !== 2) f.push({ check: 'B2', text: clip(s), element: item.path, note: `date « ${all} » not in jj/mm/aaaa` });
    else if (!valid(d, mo, y)) f.push({ check: 'B2', text: clip(s), element: item.path, note: `« ${all} » is not a valid jj/mm/aaaa date${valid(mo, d, y) ? ' (reads as US mm/dd/yyyy)' : ''}` });
  }
  // English month names in a French screen are caught by B5/B1; US « Nov 6, 2026 » style:
  const us = /\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.? \d{1,2}, \d{4}\b/;
  if ((m = us.exec(s))) f.push({ check: 'B2', text: clip(s), element: item.path, note: `US date « ${m[0]} »` });
  return f;
}

// ---------- B3: plurals
const INVARIANT = new Set(['congres', 'acces', 'pays', 'mois', 'fois', 'cas', 'prix', 'plus', 'sous', 'dans', 'apres', 'tres', 'temps', 'avis', 'choix', 'mars', 'repas', 'corps', 'vols?', 'bras', 'discours', 'parcours', 'progres', 'secours', 'concours', 'jus', 'gaz', 'nez', 'voix', 'croix', 'paix', 'dix', 'six', 'deux', 'trois', 'vis', 'devis', 'ans?', 'alias', 'relais', 'virus', 'bus', 'campus', 'statuts?', 'puis', 'depuis', 'sans', 'vers', 'chez', 'toujours', 'jamais', 'moins', 'ainsi', 'assez', 'environ', 'jours?']);
const isInvariant = (w) => { const n = norm(w); for (const x of INVARIANT) { if (new RegExp('^' + x + '$').test(n) && !['ans?', 'jours?', 'vols?', 'statuts?'].includes(x)) return true; } return false; };
const FR_NOUNS_SG = ['reponse', 'demande', 'resultat', 'code', 'passager', 'participant', 'notification', 'element', 'place', 'jour', 'personne', 'voyageur', 'entree', 'ligne', 'minute', 'heure', 'seconde', 'inscription', 'acces', 'note', 'modification', 'lien', 'fiche', 'an', 'semaine', 'page', 'utilisateur', 'evenement', 'essai', 'vol', 'nuit', 'statut', 'action', 'tentative'];
export function ruleB3(item) {
  const f = [];
  const s = item.t.replace(/ | /g, ' ');
  const re = /(?<![\d.,/:-])(\d{1,3}(?: \d{3})*|\d+)\s+([\p{L}’']+)/gu;
  let m;
  while ((m = re.exec(s))) {
    const n = parseInt(m[1].replace(/ /g, ''), 10);
    const w = m[2]; const nw = norm(w);
    const before = s.slice(Math.max(0, m.index - 4), m.index);
    if (/[/:]$/.test(before.trim())) continue; // fractions like « 3 / 6 » handled through the words that follow
    // dates « 4 septembre 2027 »: month names are not counters
    if (/^(janvier|fevrier|mars|avril|mai|juin|juillet|aout|septembre|octobre|novembre|decembre|janv|fevr|avr|juil|sept|oct|nov|dec)\.?$/.test(nw)) continue;
    if (n <= 1) {
      if (isInvariant(w)) continue;
      if (/(?:s|x)$/.test(nw) && nw.length > 2) f.push({ check: 'B3', text: clip(item.t), element: item.path, note: `« ${m[0]} »: plural after ${n}` });
    } else {
      if (FR_NOUNS_SG.includes(nw)) f.push({ check: 'B3', text: clip(item.t), element: item.path, note: `« ${m[0]} »: singular after ${n}` });
      else if (/^(publie|trouve|repondu|attendu|envoye|recu|valide|qualifie|accorde|refuse|revoque|cree|modifie|archive|inscrit|attribue|confirme|verifie|approuve|enregistre|masque|affiche)e?$/.test(nw)) f.push({ check: 'B3', text: clip(item.t), element: item.path, note: `« ${m[0]} »: participle not agreed after ${n}` });
    }
  }
  // « répondus / attendus » counters: « 1 répondus »
  const ratio = /(\d+)\s+(répondu|attendu)s?\b/g;
  while ((m = ratio.exec(s))) { const n = +m[1]; const pl = m[0].endsWith('s'); if ((n <= 1 && pl) || (n >= 2 && !pl)) f.push({ check: 'B3', text: clip(item.t), element: item.path, note: `« ${m[0]} »` }); }
  return f;
}

// ---------- B7: missing accents / capitals
const B7 = [['Equipe', 'Équipe'], ['Acces', 'Accès'], ['Congres', 'Congrès'], ['Reinitialiser', 'Réinitialiser'], ['Verifie', 'Vérifié'], ['Verifiee', 'Vérifiée'], ['Qualifiee', 'Qualifiée'], ['Telephone', 'Téléphone'], ['Societe', 'Société'], ['Detecte', 'Détecté'], ['Reveler', 'Révéler'], ['Revoquer', 'Révoquer'], ['Revoque', 'Révoqué'], ['Deconnecter', 'Déconnecter'], ['Deconnexion', 'Déconnexion'], ['Desole', 'Désolé'], ['Etat', 'État'], ['Ecran', 'Écran'], ['Electronique', 'Électronique'], ['Numero', 'Numéro'], ['Precedent', 'Précédent'], ['Debut', 'Début'], ['Categorie', 'Catégorie'], ['Resultat', 'Résultat'], ['Reponse', 'Réponse'], ['Repondu', 'Répondu'], ['Verifier', 'Vérifier'], ['Prenom', 'Prénom'], ['Selectionner', 'Sélectionner'], ['Diabetologie', 'Diabétologie'], ['Hematologie', 'Hématologie'], ['Etats-Unis', 'États-Unis'], ['Fevrier', 'Février'], ['Aout', 'Août'], ['Decembre', 'Décembre'], ['Depart', 'Départ'], ['Cree', 'Créé'], ['Creer', 'Créer'], ['Modifie', 'Modifié'], ['Envoye', 'Envoyé'], ['Recu', 'Reçu'], ['Demarrer', 'Démarrer'], ['Accueil', 'Accueil'], ['Echec', 'Échec'], ['Elements', 'Éléments'], ['Evenement', 'Événement'], ['Delegue', 'Délégué'], ['Cotation', 'Cotation'], ['Ete', 'Été']]
  .filter(([a, b]) => a !== b);
export function ruleB7(item) {
  // WordPress' « Identifiant » (slug) column shows the URL slug, which is accent-free by design (td.column-slug)
  if (/column-slug/.test(item.path || '')) return [];
  if (item.code) return [];
  const f = [];
  const s = stripUrls(item.tNoCode || item.t).replace(/⟦code⟧/g, ' ');
  for (const [bad, good] of B7) {
    // case-insensitive for the body of the word; « equipe » in lower case is the login name: only flagged outside
    // <code>, and only when it starts with a capital or is preceded by « l’ » / « L’ » (then it is the word, not a login).
    const re = new RegExp(`(?<![\\p{L}/_.-])(${bad})(s?)(?![\\p{L}/_.@-])`, 'giu');
    let m;
    while ((m = re.exec(s))) {
      const w = m[1];
      if (w === w.toLowerCase() && ['equipe', 'direction'].includes(norm(w))) {
        const pre = s.slice(Math.max(0, m.index - 3), m.index);
        if (!/[lL][’']$/.test(pre)) continue;
      }
      // Only flag when the unaccented form differs from the accented form at that position (avoids « Accueil »)
      if (norm(good) !== norm(w)) continue;
      if (w === good || w.toLowerCase() === good.toLowerCase()) continue;
      f.push({ check: 'B7', text: clip(item.t), element: item.path + (item.a ? ` [${item.a}]` : ''), note: `« ${w}${m[2]} » should be « ${good}${m[2]} »` });
    }
  }
  return f;
}

// ---------- D2: real-looking people and contacts
// Fictional ranges reserved by ARCEP for fiction: 01 99 00, 02 61 91, 03 53 01, 04 65 71, 05 36 49, 06 39 98.
const FICTION = ['0199 00', '0261 91', '0353 01', '0465 71', '0536 49', '0639 98'].map((x) => x.replace(' ', ''));
export const REAL_CONGRESSES = [
  'european congress of radiology', 'congres europeen de radiologie', 'esc congress', 'congres de la societe europeenne de cardiologie', 'journees francaises de radiologie',
  'journees francophones d’hepato-gastroenterologie et d’oncologie digestive', 'jfhod', 'asco annual meeting', 'ers international congress', 'eadv congress', 'ean congress',
  'congres francais de rhumatologie', 'journees europeennes de la societe francaise de cardiologie', 'congres de la societe francaise d’ophtalmologie', 'journees de neurologie de langue francaise',
  'congres de pneumologie de langue francaise', 'congres annuel de la sfd', 'easd annual meeting', 'world congress of cardiology', 'congres de la sfd', 'ecr', 'jfr', 'cplf', 'jnlf', 'sfo',
  'congres mondial de neurologie', 'world congress of neurology', 'congres mondial de cardiologie',
];
// The client's own published contact details may appear on the concept pages (it is their site being redesigned).
// Each entry is a build-time assertion: the value must appear at the cited source line, checked by the gate.
export const CLIENT_CONTACTS = [{ value: 'direction@assetvoyages.com', source: '01_Questions_for_Veena.md', needle: 'direction@assetvoyages.com' },
  { value: '01 55 57 29 00', source: 'HANDOFF.md', needle: '« Tel: 01 55 57 29 00 »' }];
export function ruleD2(item, { allowEmails = [] } = {}) {
  const f = [];
  const s = item.t;
  let m;
  const em = /[\w.+-]+@([\w-]+(?:\.[\w-]+)+)/g;
  while ((m = em.exec(s))) {
    const dom = m[1].toLowerCase();
    if (/^example\.(com|org|net)$/.test(dom) || /\.example$|\.test$|\.invalid$/.test(dom) || allowEmails.includes(m[0].toLowerCase())) continue;
    if (!item.demo && CLIENT_CONTACTS.some((c) => c.value === m[0].toLowerCase())) continue; // client's own address, outside the demos only
    f.push({ check: 'D2', text: clip(s), element: item.path, note: `real-looking e-mail « ${m[0]} »` });
  }
  const ph = /(?<![\d])(?:\+33\s?\(?0?\)?\s?|0)([1-9])(?:[\s.-]?(\d{2})){4}(?!\d)/g;
  while ((m = ph.exec(s))) {
    const digits = m[0].replace(/\D/g, '').replace(/^33/, '0').replace(/^0?/, '0');
    if (FICTION.some((p) => digits.startsWith(p))) continue;
    if (!item.demo && CLIENT_CONTACTS.some((c) => c.value.replace(/\D/g, '') === digits)) continue; // client's own phone, outside the demos only
    f.push({ check: 'D2', text: clip(s), element: item.path, note: `phone « ${m[0]} » outside the ARCEP fiction ranges (01 99 00…, 02 61 91…, 03 53 01…, 04 65 71…, 05 36 49…, 06 39 98…) and not masked` });
  }
  const ns = norm(s).replace(/['’]/g, '’');
  for (const c of REAL_CONGRESSES) {
    const re = c.length <= 4 ? new RegExp(`\\b${c}\\b`) : null;
    if ((re && re.test(ns) && /\b[A-Z]{3,4}\b/.test(s) && s.includes(c.toUpperCase())) || (!re && ns.includes(c))) {
      f.push({ check: 'D2', text: clip(s), element: item.path, note: `matches a real congress name « ${c} »${/exemple|fictif|fictional/i.test(s) ? ' (marked as an example in the same text)' : ''}` });
    }
  }
  return f;
}

// ---------- D4: GM&E code visible
// « DEMO-GME-XXXX » is the format hint in the code field placeholder, not a code: X{4} is excluded
export const CODE_RE = /DEMO-GME-(?!XXXX)[A-Z0-9]{4}/g;
