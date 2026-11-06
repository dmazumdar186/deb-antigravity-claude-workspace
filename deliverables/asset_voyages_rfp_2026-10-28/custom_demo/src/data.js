// Schema, seed and reset. Everything here is fictional demo data.
import { encryptCode, hashPassword, newSalt, slugify, norm, PBKDF2_ITER, nowIso, addDays, today, rateHit, hmac } from './lib.js';

// Schema v6: every demo row carries `sbx`. '' is the shared seed; any other value is one browser's private sandbox.
// Row-level copy-on-write (see T() and cow() below): a sandbox only holds the rows that browser created or changed.
// Write budget: keyed tables are WITHOUT ROWID (the primary key is the table: one written row per insert, no extra
// autoindex), log tables are clustered on (sbx, parent, id), notifications and creation events are derived on read.
export const SCHEMA_VERSION = 10;
export const SCHEMA = [
  `CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT NOT NULL) WITHOUT ROWID`,
  `CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, display_name TEXT NOT NULL, role TEXT NOT NULL CHECK (role IN ('direction','equipe','contributeur')), pw_hash TEXT NOT NULL, pw_salt TEXT NOT NULL, pw_iter INTEGER NOT NULL)`,
  // Sessions are signed cookies; only logged-out session nonces are stored, until their expiry.
  `CREATE TABLE IF NOT EXISTS revoked (n TEXT PRIMARY KEY, exp INTEGER NOT NULL) WITHOUT ROWID`,
  `CREATE TABLE IF NOT EXISTS sandboxes (id TEXT PRIMARY KEY, created_at TEXT NOT NULL) WITHOUT ROWID`,
  `CREATE TABLE IF NOT EXISTS congresses (sbx TEXT NOT NULL DEFAULT '', id INTEGER NOT NULL, ref TEXT NOT NULL, slug TEXT NOT NULL, title TEXT NOT NULL, discipline TEXT NOT NULL, city TEXT NOT NULL, country TEXT NOT NULL, start_date TEXT NOT NULL, end_date TEXT NOT NULL, venue TEXT NOT NULL, official_url TEXT NOT NULL, verified_on TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', status TEXT NOT NULL CHECK (status IN ('brouillon','a_relire','publie','archive')), search_text TEXT NOT NULL, created_at TEXT NOT NULL, created_by INTEGER, updated_at TEXT NOT NULL, updated_by INTEGER, PRIMARY KEY (sbx, id)) WITHOUT ROWID`,
  `CREATE TABLE IF NOT EXISTS congress_events (sbx TEXT NOT NULL DEFAULT '', congress_id INTEGER NOT NULL, id TEXT NOT NULL, at TEXT NOT NULL, user_id INTEGER, kind TEXT NOT NULL, from_val TEXT, to_val TEXT, PRIMARY KEY (sbx, congress_id, id)) WITHOUT ROWID`,
  `CREATE TABLE IF NOT EXISTS enquiries (sbx TEXT NOT NULL DEFAULT '', id INTEGER NOT NULL, ref TEXT NOT NULL, congress_id INTEGER NOT NULL, name TEXT NOT NULL, email TEXT NOT NULL, phone TEXT NOT NULL, company TEXT NOT NULL DEFAULT '', departure_city TEXT NOT NULL, date_out TEXT NOT NULL, date_back TEXT NOT NULL, passengers INTEGER NOT NULL, message TEXT NOT NULL DEFAULT '', consent_at TEXT NOT NULL, status TEXT NOT NULL CHECK (status IN ('nouvelle','qualifiee','devis','gagnee','perdue')), owner_id INTEGER, form_nonce TEXT UNIQUE, ip_hash TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, PRIMARY KEY (sbx, id)) WITHOUT ROWID`,
  `CREATE TABLE IF NOT EXISTS enquiry_events (sbx TEXT NOT NULL DEFAULT '', enquiry_id INTEGER NOT NULL, id TEXT NOT NULL, at TEXT NOT NULL, user_id INTEGER, kind TEXT NOT NULL CHECK (kind IN ('statut','responsable','note')), from_val TEXT, to_val TEXT, PRIMARY KEY (sbx, enquiry_id, id)) WITHOUT ROWID`,
  // Append-only at the database level: history rows can never be edited (only a whole sandbox is ever deleted).
  `CREATE TRIGGER IF NOT EXISTS enquiry_events_no_update BEFORE UPDATE ON enquiry_events BEGIN SELECT RAISE(ABORT, 'append-only'); END`,
  `CREATE TABLE IF NOT EXISTS gme_codes (sbx TEXT NOT NULL DEFAULT '', congress_id INTEGER NOT NULL, code_enc TEXT, status TEXT NOT NULL CHECK (status IN ('detecte','verifie','approuve','expire')), valid_from TEXT, valid_to TEXT, evidence TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL, updated_by INTEGER, PRIMARY KEY (sbx, congress_id)) WITHOUT ROWID`,
  `CREATE TABLE IF NOT EXISTS gme_requests (sbx TEXT NOT NULL DEFAULT '', id INTEGER NOT NULL, congress_id INTEGER NOT NULL, user_id INTEGER NOT NULL, reason TEXT NOT NULL, status TEXT NOT NULL CHECK (status IN ('en_attente','approuvee','refusee','revoquee')), created_at TEXT NOT NULL, decided_at TEXT, decided_by INTEGER, expires_at TEXT, PRIMARY KEY (sbx, id)) WITHOUT ROWID`,
  `CREATE TABLE IF NOT EXISTS gme_access_log (sbx TEXT NOT NULL DEFAULT '', id TEXT NOT NULL, at TEXT NOT NULL, user_id INTEGER NOT NULL, congress_id INTEGER NOT NULL, result TEXT NOT NULL, PRIMARY KEY (sbx, id)) WITHOUT ROWID`,
  // Managed lists for the congress form (Direction adds values), so a typo cannot create a duplicate filter.
  `CREATE TABLE IF NOT EXISTS options (sbx TEXT NOT NULL DEFAULT '', kind TEXT NOT NULL CHECK (kind IN ('discipline','pays')), value TEXT NOT NULL, norm TEXT NOT NULL, PRIMARY KEY (sbx, kind, norm)) WITHOUT ROWID`,
  // « Lien de groupe » (EXTRA_GROUP.md). One link per enquiry and sandbox. The URL token is never stored: the row keeps a
  // 128-bit random salt (the token is HMAC(group-v1, salt), so the console can show it again) and the lookup MAC
  // HMAC(group-v1, token). origin_sbx is the sandbox that created the link ('' for the seed link): a delegate's write goes there.
  `CREATE TABLE IF NOT EXISTS group_links (sbx TEXT NOT NULL DEFAULT '', enquiry_id INTEGER NOT NULL, origin_sbx TEXT NOT NULL, token_mac TEXT NOT NULL, tok_salt TEXT NOT NULL, created_at TEXT NOT NULL, created_by INTEGER, expires_at TEXT NOT NULL, revoked_at TEXT, revoked_by INTEGER, PRIMARY KEY (sbx, enquiry_id)) WITHOUT ROWID`,
  `CREATE INDEX IF NOT EXISTS group_links_mac ON group_links (token_mac)`,
  // One row per delegate and enquiry, keyed on the normalised e-mail. `owner` is HMAC(delegate-v1) of the random id in
  // the signed cookie of the browser that created the entry: only that browser may update it directly.
  `CREATE TABLE IF NOT EXISTS group_delegates (sbx TEXT NOT NULL DEFAULT '', enquiry_id INTEGER NOT NULL, email_norm TEXT NOT NULL, id TEXT NOT NULL, name TEXT NOT NULL, email TEXT NOT NULL, departure_city TEXT NOT NULL, date_out TEXT NOT NULL, date_back TEXT NOT NULL, consent_at TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, owner TEXT NOT NULL DEFAULT '', PRIMARY KEY (sbx, enquiry_id, email_norm)) WITHOUT ROWID`,
  // A change to an existing entry sent from another browser waits here (one per e-mail, the latest wins) until staff accept or refuse it.
  `CREATE TABLE IF NOT EXISTS group_pending (sbx TEXT NOT NULL DEFAULT '', enquiry_id INTEGER NOT NULL, email_norm TEXT NOT NULL, id TEXT NOT NULL, name TEXT NOT NULL, email TEXT NOT NULL, departure_city TEXT NOT NULL, date_out TEXT NOT NULL, date_back TEXT NOT NULL, consent_at TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY (sbx, enquiry_id, email_norm)) WITHOUT ROWID`,
  // A link replaced by « Créer un nouveau lien » leaves its lookup MAC here, so the old URL says « plus actif » (USAB-X-001).
  `CREATE TABLE IF NOT EXISTS group_replaced (token_mac TEXT NOT NULL, sbx TEXT NOT NULL DEFAULT '', enquiry_id INTEGER NOT NULL, replaced_at TEXT NOT NULL, PRIMARY KEY (token_mac, sbx)) WITHOUT ROWID`,
  `CREATE TABLE IF NOT EXISTS settings (sbx TEXT NOT NULL DEFAULT '', k TEXT NOT NULL, v TEXT NOT NULL, PRIMARY KEY (sbx, k)) WITHOUT ROWID`,
  `CREATE TABLE IF NOT EXISTS rate_limits (key TEXT PRIMARY KEY, count INTEGER NOT NULL, reset_at INTEGER NOT NULL) WITHOUT ROWID`,
];
const DATA_TABLES = ['group_replaced', 'group_pending', 'group_delegates', 'group_links', 'settings', 'options', 'congress_events', 'enquiry_events', 'enquiries', 'gme_access_log', 'gme_requests', 'gme_codes', 'congresses'];
// Columns copied when a seed row is first changed in a sandbox (cow).
const COPY_COLS = {
  congresses: 'id, ref, slug, title, discipline, city, country, start_date, end_date, venue, official_url, verified_on, description, status, search_text, created_at, created_by, updated_at, updated_by',
  enquiries: 'id, ref, congress_id, name, email, phone, company, departure_city, date_out, date_back, passengers, message, consent_at, status, owner_id, created_at, updated_at',
  gme_codes: 'congress_id, code_enc, status, valid_from, valid_to, evidence, updated_at, updated_by',
  gme_requests: 'id, congress_id, user_id, reason, status, created_at, decided_at, decided_by, expires_at',
};
// Event and log ids: time first, so ordering by id is chronological.
let evSeq = 0;
export const eventId = (at = nowIso()) => `${at}-${(evSeq = (evSeq + 1) % 1e6).toString(36).padStart(4, '0')}${Math.random().toString(36).slice(2, 6)}`;
const DROP_OLD = ['group_replaced', 'group_pending', 'group_delegates', 'group_links', 'settings', 'options', 'congress_events', 'enquiry_events', 'notifications', 'enquiries', 'gme_access_log', 'gme_requests', 'gme_codes', 'congresses', 'sandboxes', 'sessions', 'revoked', 'rate_limits', 'meta'];

export const USERS = [
  { id: 1, username: 'direction', display_name: 'Hélène Martin, Direction', role: 'direction' },
  { id: 2, username: 'equipe', display_name: 'Karim Benali, Équipe', role: 'equipe' },
  { id: 3, username: 'contributeur', display_name: 'Julie Roux, Contributrice', role: 'contributeur' },
];
export const DEMO_PASSWORD = 'demo-asset';

const FICTION = 'Fiche d’exemple pour la démonstration : congrès, lieu et site officiel sont fictifs.';
// Non-breaking spaces on both sides of the dash: « — exemple » never breaks from its title nor leaves « exemple » alone.
export const nbsp = (t) => String(t).replace(/[ \u00a0]+—[ \u00a0]+/g, '\u00a0—\u00a0');
const C = (n, title, discipline, city, country, start, end, venue, blurb, status = 'publie') => ({
  id: n, ref: `CG-0${n}`, title: nbsp(title), discipline, city, country, start, end, venue: nbsp(venue), status,
  description: `${blurb} ${FICTION}`,
});
export const CONGRESSES = [
  C(101, 'Congrès européen de cardiologie — exemple', 'Cardiologie', 'Madrid', 'Espagne', '2027-08-27', '2027-08-30', 'Centre de congrès de Madrid — exemple', 'Quatre jours de sessions sur l’insuffisance cardiaque, la prévention et l’imagerie.'),
  C(102, 'Congrès international d’oncologie — exemple', 'Oncologie', 'Berlin', 'Allemagne', '2027-10-15', '2027-10-19', 'Palais des expositions de Berlin — exemple', 'Essais cliniques, immunothérapies et parcours patient, en sessions parallèles.'),
  C(103, 'Journées françaises de diabétologie — exemple', 'Diabétologie', 'Lyon', 'France', '2027-03-23', '2027-03-26', 'Centre de congrès de Lyon — exemple', 'Le rendez-vous francophone du diabète : recherche, pratique et éducation thérapeutique.'),
  C(104, 'Congrès mondial de neurologie — exemple', 'Neurologie', 'Vienne', 'Autriche', '2027-06-19', '2027-06-22', 'Centre international de Vienne — exemple', 'Maladies neurodégénératives, AVC et neuro-imagerie.'),
  C(105, 'Congrès européen de dermatologie — exemple', 'Dermatologie', 'Amsterdam', 'Pays-Bas', '2027-09-29', '2027-10-02', 'Parc des congrès d’Amsterdam — exemple', 'Dermatologie clinique, chirurgicale et esthétique.'),
  C(106, 'Congrès international de pneumologie — exemple', 'Pneumologie', 'Milan', 'Italie', '2027-09-04', '2027-09-08', 'Centre des congrès de Milan — exemple', 'Asthme, BPCO, sommeil et soins intensifs respiratoires.'),
  C(107, 'Rencontres d’ophtalmologie — exemple', 'Ophtalmologie', 'Paris', 'France', '2027-05-08', '2027-05-11', 'Palais des congrès de Paris — exemple', 'Chirurgie réfractive, rétine et glaucome.'),
  C(108, 'Congrès européen de radiologie — exemple', 'Radiologie', 'Vienne', 'Autriche', '2027-02-24', '2027-02-28', 'Centre des congrès de Vienne — exemple', 'Imagerie diagnostique et interventionnelle, intelligence artificielle en radiologie.'),
  C(109, 'Sommet RH et mobilité — exemple', 'Ressources humaines', 'Lisbonne', 'Portugal', '2027-04-13', '2027-04-14', 'Centre de congrès de Lisbonne — exemple', 'Deux jours sur la mobilité internationale des collaborateurs.'),
  C(110, 'Forum des directions financières — exemple', 'Finance', 'Londres', 'Royaume-Uni', '2027-11-17', '2027-11-18', 'Centre de conférences de Londres — exemple', 'Pilotage, trésorerie et maîtrise des coûts de déplacement.'),
  C(111, 'Congrès nord-américain de cardiologie — exemple', 'Cardiologie', 'Chicago', 'États-Unis', '2027-11-13', '2027-11-16', 'Centre des congrès de Chicago — exemple', 'Cardiologie interventionnelle et rythmologie.'),
  C(112, 'Journées d’oncologie digestive — exemple', 'Oncologie', 'Marseille', 'France', '2027-01-28', '2027-01-30', 'Palais du Pharo — exemple', 'Cancers digestifs : diagnostic, traitements et soins de support.'),
  C(113, 'Journées de rhumatologie — exemple', 'Rhumatologie', 'Bordeaux', 'France', '2027-06-10', '2027-06-12', 'Palais des congrès de Bordeaux — exemple', 'Brouillon en préparation, pas encore relu.', 'brouillon'),
];
const EXTRA_DISCIPLINES = ['Gastro-entérologie', 'Pédiatrie', 'Urologie'];
const EXTRA_PAYS = ['Belgique', 'Suisse', 'Canada', 'Danemark', 'Suède'];
export const congressSearch = (c) => norm([c.title, c.city, c.discipline, c.country, c.ref].join(' '));
export const congressSlug = (title, ref) => `${slugify(title.replace(/[\s\u00a0]*—[\s\u00a0]*exemple\s*$/i, ''))}-${ref.toLowerCase()}`;

// Dummy GM&E codes: seeded only through encryption, never stored or rendered in clear.
export const GME_SEED = [
  { congress_id: 112, code: 'DEMO-GME-4821', status: 'approuve', valid_from: '2026-10-01', valid_to: '2027-01-30', evidence: 'Courriel de l’organisateur (exemple) reçu le 12/10/2026.' },
  { congress_id: 103, code: 'DEMO-GME-2954', status: 'approuve', valid_from: '2026-10-15', valid_to: '2027-03-26', evidence: 'Confirmation du programme GM&E (exemple), dossier n° 0000.' },
  { congress_id: 108, code: 'DEMO-GME-7310', status: 'verifie', valid_from: '2026-11-01', valid_to: '2027-02-28', evidence: 'Code vérifié auprès de la compagnie (exemple), en attente de validation Direction.' },
  { congress_id: 101, code: 'DEMO-GME-6147', status: 'detecte', valid_from: null, valid_to: null, evidence: 'Repéré sur le site de l’organisateur (exemple), à vérifier.' },
  { congress_id: 105, code: 'DEMO-GME-1088', status: 'expire', valid_from: '2026-01-01', valid_to: '2026-06-30', evidence: 'Ancienne édition (exemple).' },
];
export const GME_SEED_CODES = GME_SEED.map((g) => g.code);

const E = (id, cg, name, email, phone, company, city, out, back, pax, msg, status, owner, created) =>
  ({ id, cg, name, email, phone, company, city, out, back, pax, msg, status, owner, created });
const ENQUIRIES = [
  E(1, 112, 'Camille Laurent (exemple)', 'camille.laurent@example.com', '01 23 45 67 01', 'Laboratoire A (exemple)', 'Lille', '2027-01-27', '2027-01-31', 6, 'Groupe de six médecins, départ groupé si possible.', 'gagnee', 1, '2026-10-20T09:12:00Z'),
  E(2, 103, 'Hugo Martin (exemple)', 'hugo.martin@example.com', '01 23 45 67 02', '', 'Toulouse', '2027-03-22', '2027-03-26', 2, 'Deux places, retour le dernier soir.', 'devis', 2, '2026-10-24T14:30:00Z'),
  E(3, 101, 'Inès Moreau (exemple)', 'ines.moreau@example.com', '01 23 45 67 03', 'Société B (exemple)', 'Nantes', '2027-08-26', '2027-08-31', 12, 'Équipe commerciale de douze personnes.', 'qualifiee', 2, '2026-10-28T08:05:00Z'),
  E(4, 108, 'Paul Lefebvre (exemple)', 'paul.lefebvre@example.com', '01 23 45 67 04', 'Clinique C (exemple)', 'Paris', '2027-02-23', '2027-02-28', 3, '', 'perdue', 1, '2026-10-30T16:45:00Z'),
  E(5, 107, 'Léa Garnier (exemple)', 'lea.garnier@example.com', '01 23 45 67 05', '', 'Marseille', '2027-05-07', '2027-05-11', 1, 'Je préfère un vol le matin.', 'nouvelle', 2, '2026-11-03T10:20:00Z'),
  E(6, 102, 'Nathan Roux (exemple)', 'nathan.roux@example.com', '01 23 45 67 06', 'Société D (exemple)', 'Lyon', '2027-10-14', '2027-10-20', 4, 'Quatre participants, dont un en fauteuil roulant.', 'nouvelle', null, '2026-11-04T17:02:00Z'),
];
const PATH = ['nouvelle', 'qualifiee', 'devis'];
// Seeded group (fictional): enquiry DV-2026-0001, congress CG-0112 (Marseille, 28 to 30 Jan. 2027), 6 expected, 3 answered.
export const GROUP_SEED = {
  enquiry_id: 1,
  salt: 'seed-groupe-dv-2026-0001-v1',
  delegates: [
    { id: 'seedA0000001', name: 'Alice Martin (exemple)', email: 'alice.martin@example.com', city: 'Lille', out: '2027-01-27', back: '2027-01-31', at: '2026-10-22T08:10:00Z' },
    { id: 'seedB0000002', name: 'Bruno Leroy (exemple)', email: 'bruno.leroy@example.com', city: 'Lille', out: '2027-01-27', back: '2027-01-30', at: '2026-10-22T12:45:00Z' },
    { id: 'seedC0000003', name: 'Chloé Petit (exemple)', email: 'chloe.petit@example.com', city: 'Paris', out: '2027-01-28', back: '2027-01-31', at: '2026-10-23T17:20:00Z' },
  ],
};

export const STATUS_LABELS = { nouvelle: 'Nouvelle', qualifiee: 'Qualifiée', devis: 'Devis envoyé', gagnee: 'Gagnée', perdue: 'Perdue' };
export const CG_STATUS = { brouillon: 'Brouillon', a_relire: 'À relire', publie: 'Publié', archive: 'Archivé' };
export const GME_STATUS = { detecte: 'Détecté', verifie: 'Vérifié', approuve: 'Approuvé pour la vente', expire: 'Expiré' };
export const TEAM_INBOX = 'equipe.congres@example.com';

export const STATUS_PLURAL = { nouvelle: 'Nouvelles', qualifiee: 'Qualifiées', devis: 'Devis envoyés', gagnee: 'Gagnées', perdue: 'Perdues' };

const numDate = (iso) => { const [y, m, d] = String(iso).slice(0, 10).split('-'); return `${d}/${m}/${y}`; };
export function notificationFor(enq, congress, baseUrl) {
  const subject = `Nouvelle demande ${enq.ref} : ${congress.title}`;
  const body = [
    `Une nouvelle demande de devis vol est arrivée sur le site.`,
    ``,
    `Référence : ${enq.ref}`,
    `Congrès : ${congress.title} (${congress.ref})`,
    `Contact : ${enq.name}, ${enq.email}, ${enq.phone}${enq.company ? ', ' + enq.company : ''}`,
    `Départ : ${enq.departure_city}, aller le ${numDate(enq.date_out)}, retour le ${numDate(enq.date_back)}`,
    `Passagers : ${enq.passengers}`,
    ``,
    `Ouvrir dans la console : ${String(baseUrl || '').replace(/\/$/, '')}/console/demandes/${enq.id}`,
  ].join('\n');
  return { subject, body };
}
export const baseUrl = (env) => env.PUBLIC_URL || 'https://asset-voyages-demo.debanjan186.workers.dev';

let schemaReady = false;
export async function ensureReady(env) {
  if (schemaReady) return;
  let v = null;
  try { v = (await env.DB.prepare(`SELECT v FROM meta WHERE k = 'schema'`).first())?.v; } catch { v = null; }
  if (String(v) !== String(SCHEMA_VERSION)) {
    await env.DB.batch(DROP_OLD.map((t) => env.DB.prepare(`DROP TABLE IF EXISTS ${t}`)));
    await seedShared(env);
  }
  schemaReady = true;
}

// ---------- sandboxes ----------
const SBX_RE = /^[A-Za-z0-9_-]{16,40}$/;
export const validSbx = (id) => typeof id === 'string' && SBX_RE.test(id);
// Effective sandbox for reads: the browser's own copy once it exists, else the shared seed ('').
export async function effectiveSbx(env, id) {
  if (!validSbx(id)) return '';
  const row = await env.DB.prepare('SELECT id FROM sandboxes WHERE id = ?').bind(id).first();
  return row ? id : '';
}
// Row-level copy-on-write. A browser's sandbox writes nothing until its first write; then only the rows it touches are
// written under its id (an edited congress is copied once, a new enquiry is inserted). Reads overlay the sandbox rows on
// the shared seed: for keyed tables a sandbox row hides the seed row with the same key; log tables are a plain union.
const OVERLAY_KEYS = { congresses: ['id'], enquiries: ['id'], gme_codes: ['congress_id'], gme_requests: ['id'], group_links: ['enquiry_id'], group_delegates: ['enquiry_id', 'email_norm'], group_pending: ['enquiry_id', 'email_norm'], settings: ['k'] };
const UNION_TABLES = new Set(['congress_events', 'enquiry_events', 'gme_access_log', 'options']);
// The sandbox id is inlined as a literal: validSbx() guarantees [A-Za-z0-9_-]{16,40}, so it cannot carry SQL.
export function T(env, table) {
  const sid = env.SBX_EFF;
  if (!sid) return `(SELECT * FROM ${table} WHERE sbx = '')`;
  if (!validSbx(sid)) throw new Error('bad sandbox id');
  if (UNION_TABLES.has(table)) return `(SELECT * FROM ${table} WHERE sbx IN ('', '${sid}'))`;
  const keys = OVERLAY_KEYS[table];
  if (!keys) throw new Error('no overlay for ' + table);
  const same = keys.map((k) => `o.${k} = s.${k}`).join(' AND ');
  return `(SELECT * FROM ${table} WHERE sbx = '${sid}' UNION ALL SELECT * FROM ${table} s WHERE s.sbx = '' AND NOT EXISTS (SELECT 1 FROM ${table} o WHERE o.sbx = '${sid}' AND ${same}))`;
}
// Copy one seed row into the sandbox before it is changed (no-op when the sandbox already has its own copy).
export function cow(env, table, keyVals) {
  const keys = OVERLAY_KEYS[table];
  const cols = COPY_COLS[table];
  const where = keys.map((k) => `${k} = ?`).join(' AND ');
  return env.DB.prepare(`INSERT OR IGNORE INTO ${table} (sbx, ${cols}) SELECT ?, ${cols} FROM ${table} WHERE sbx = '' AND ${where}`).bind(env.SBX_EFF, ...keyVals);
}

// Change a row in the browser's sandbox in ONE written row: insert the full new version, or update the sandbox's own copy.
export function upsertRow(env, table, row) {
  const cols = COPY_COLS[table].split(', ');
  const keys = OVERLAY_KEYS[table];
  const set = cols.filter((c) => !keys.includes(c)).map((c) => `${c} = excluded.${c}`).join(', ');
  return env.DB.prepare(`INSERT INTO ${table} (sbx, ${cols.join(', ')}) VALUES (?, ${cols.map(() => '?').join(', ')}) ON CONFLICT (sbx, ${keys.join(', ')}) DO UPDATE SET ${set}`)
    .bind(env.SBX_EFF, ...cols.map((c) => (row[c] === undefined ? null : row[c])));
}

// Sandbox budget (D1 free plan: 100,000 rows written a day; index entries and deletes count as written rows).
// A sandbox costs only what its session writes: FIX3-1 measures the full S1-S5 journey (4 logins, a new and an edited
// congress, an enquiry, 3 follow-up changes, a GM&E request, approval and reveal) at 29 rows; we budget 30.
// RESERVED_ROWS covers the bounded nightly purge and reseed (about 9,400 rows, see nightly()).
export const ROWS_PER_SESSION = 30;
export const RESERVED_ROWS = 10000;
export const SBX_IP_DAILY = 20;
export const SBX_DAILY_LIMIT = Math.floor((100000 - RESERVED_ROWS) / ROWS_PER_SESSION); // 3,000
export const DEMO_BUSY = 'Démo très demandée : vous pouvez parcourir, les essais reprennent dans quelques minutes.';
// ---------- write budget guards (ADV-B-207) ----------
// Global: D1 allows 100,000 written rows a day; every request's written rows are metered (index.js) and added to an
// in-memory tally that is flushed to one `wall:<day>` counter row at most every 5 minutes or 200 rows (one write per
// flush), so counting never costs a write per write. At WALL_LIMIT (15,000 below the quota, which absorbs unflushed
// tallies, logins and the nightly job) every write path degrades to the read-only seed with the calm banner.
// Per sandbox: 60 write requests per 10 minutes, counted in memory; the count is persisted (one upsert) only once a
// browser passes 20 writes in the window, so a normal session (about 16 write requests for the whole S1-S5 journey)
// never spends a row on it.
export const WALL_LIMIT = 85000;
export const SBX_WRITE_LIMIT = 60;
const SBX_WRITE_WINDOW = 600;
const mem = { day: '', pending: 0, flushedAt: Date.now(), sbx: new Map() };
const utcDay = () => new Date().toISOString().slice(0, 10);
export function noteWrites(n) {
  if (mem.day !== utcDay()) { mem.day = utcDay(); mem.pending = 0; }
  mem.pending += n || 0;
}
export function wallFlushDue() { return mem.pending >= 200 || (mem.pending > 0 && Date.now() - mem.flushedAt > 300000); }
export async function flushWall(env) {
  const n = mem.pending; if (!n) return;
  mem.pending = 0; mem.flushedAt = Date.now();
  const end = Math.floor(Date.parse(mem.day + 'T00:00:00Z') / 1000) + 86400 + 3600;
  await env.DB.prepare(`INSERT INTO rate_limits (key, count, reset_at) VALUES (?, ?, ?) ON CONFLICT(key) DO UPDATE SET count = count + excluded.count`)
    .bind('wall:' + mem.day, n, end).run();
}
export async function wallTotal(env) {
  if (mem.day !== utcDay()) { mem.day = utcDay(); mem.pending = 0; }
  const row = await env.DB.prepare('SELECT count FROM rate_limits WHERE key = ?').bind('wall:' + mem.day).first();
  return (row ? row.count : 0) + mem.pending;
}
const fail = (code) => Object.assign(new Error(code), { code });
// Every write path calls this first, after its own role and CSRF checks: global budget, per-sandbox throttle, then the
// sandbox is registered on its first write (nothing is created for a refused request).
export async function claim(env) {
  if ((await wallTotal(env)) >= WALL_LIMIT) throw fail('SBX_LIMIT');
  const sid = env.SBX;
  if (!validSbx(sid)) throw new Error('no sandbox id');
  const win = Math.floor(Date.now() / 1000 / SBX_WRITE_WINDOW);
  let e = mem.sbx.get(sid);
  if (!e || e.win !== win) {
    if (mem.sbx.size > 5000) for (const [k, v] of mem.sbx) if (v.win !== win) mem.sbx.delete(k);
    const row = await env.DB.prepare('SELECT count FROM rate_limits WHERE key = ?').bind(`w:${sid}:${win}`).first();
    e = { win, n: row ? row.count : 0, saved: row ? row.count : 0 };
    mem.sbx.set(sid, e);
  }
  if (e.n >= SBX_WRITE_LIMIT) throw fail('WRITE_PAUSE');
  e.n += 1;
  if (e.n >= 20 && e.n - e.saved >= 10) {
    e.saved = e.n;
    await env.DB.prepare(`INSERT INTO rate_limits (key, count, reset_at) VALUES (?1, ?2, ?3) ON CONFLICT(key) DO UPDATE SET count = MAX(count, ?2)`)
      .bind(`w:${sid}:${win}`, e.n, (win + 1) * SBX_WRITE_WINDOW).run();
  }
  return materialize(env);
}
export const DEMO_PAUSE = 'Beaucoup d’essais en peu de temps : vos modifications reprennent dans quelques minutes. Vous pouvez continuer à parcourir.';

// First write of a browser: register its sandbox (one row, caps checked). Nothing is copied here. Returns the id.
export async function materialize(env) {
  if (env.SBX_EFF) return env.SBX_EFF;
  const id = env.SBX;
  if (!validSbx(id)) throw new Error('no sandbox id');
  const db = env.DB;
  if ((env.IP_HASH && !env.TEST_RUN && !(await rateHit(env, 'sbx-ip:' + env.IP_HASH, SBX_IP_DAILY, 86400))) || !(await rateHit(env, 'sbx:all', SBX_DAILY_LIMIT, 86400))) {
    throw Object.assign(new Error('sandbox limit'), { code: 'SBX_LIMIT' });
  }
  await db.prepare('INSERT OR IGNORE INTO sandboxes (id, created_at) VALUES (?, ?)').bind(id, nowIso()).run();
  env.SBX_EFF = id;
  return id;
}
async function deleteSandboxes(env, where, binds) {
  const db = env.DB;
  const stmts = DATA_TABLES.map((t) => db.prepare(`DELETE FROM ${t} WHERE sbx IN (SELECT id FROM sandboxes WHERE ${where})`).bind(...binds));
  stmts.push(db.prepare(`DELETE FROM sandboxes WHERE ${where}`).bind(...binds));
  await db.batch(stmts);
}
// « Réinitialiser la démo »: back to the seed for this browser only. Idempotent.
export async function resetSandbox(env) {
  if (validSbx(env.SBX)) await deleteSandboxes(env, 'id = ?', [env.SBX]);
  env.SBX_EFF = '';
}
// Nightly cron, bounded so it fits the reserved write budget (deleted rows count as written rows on D1):
// the oldest 300 sandboxes past 24 h, orphans of up to 50 vanished sandboxes, 1,000 expired logouts, 3,000 expired
// throttle rows, then the shared seed is rebuilt (about 150 rows). On a busy day the rest waits for the next nights;
// it only costs storage, never visibility (nobody else can read another browser's rows).
export const PURGE_SANDBOXES = 300;
export async function nightly(env) {
  await ensureReady(env);
  const db = env.DB;
  const cutoff = new Date(Date.now() - 24 * 3600 * 1000).toISOString();
  const now = Math.floor(Date.now() / 1000);
  const expired = `SELECT id FROM sandboxes WHERE created_at < ?1 ORDER BY created_at LIMIT ${PURGE_SANDBOXES}`;
  await db.batch([
    ...DATA_TABLES.map((t) => db.prepare(`DELETE FROM ${t} WHERE sbx IN (${expired})`).bind(cutoff)),
    db.prepare(`DELETE FROM sandboxes WHERE id IN (${expired})`).bind(cutoff),
    // orphans: rows tagged with a sandbox that no longer exists (e.g. a write that raced a reset)
    ...DATA_TABLES.map((t) => db.prepare(`DELETE FROM ${t} WHERE sbx IN (SELECT DISTINCT sbx FROM ${t} WHERE sbx <> '' AND sbx NOT IN (SELECT id FROM sandboxes) LIMIT 50)`)),
    db.prepare('DELETE FROM revoked WHERE n IN (SELECT n FROM revoked WHERE exp < ? LIMIT 1000)').bind(now),
    db.prepare('DELETE FROM rate_limits WHERE key IN (SELECT key FROM rate_limits WHERE reset_at < ? LIMIT 3000)').bind(now),
  ]);
  await seedShared(env);
}

// Idempotent: rebuilds the shared seed rows (sbx = '') with the same ids. Sandboxes are untouched.
export async function seedShared(env) {
  const db = env.DB;
  await db.batch(SCHEMA.map((q) => db.prepare(q)));
  const stmts = DATA_TABLES.map((t) => db.prepare(`DELETE FROM ${t} WHERE sbx = ''`));
  stmts.push(db.prepare(`INSERT INTO meta (k, v) VALUES ('schema', ?) ON CONFLICT(k) DO UPDATE SET v = excluded.v`).bind(String(SCHEMA_VERSION)));
  const now = nowIso();
  const base = baseUrl(env);

  // users: re-hash only when missing, so a reset does not burn CPU on PBKDF2.
  const existing = await db.prepare('SELECT username FROM users').all();
  const have = new Set((existing.results || []).map((r) => r.username));
  for (const u of USERS) {
    if (have.has(u.username)) {
      stmts.push(db.prepare('UPDATE users SET id = ?, display_name = ?, role = ? WHERE username = ?').bind(u.id, u.display_name, u.role, u.username));
    } else {
      const salt = newSalt();
      const hash = await hashPassword(DEMO_PASSWORD, salt);
      stmts.push(db.prepare('INSERT INTO users (id, username, display_name, role, pw_hash, pw_salt, pw_iter) VALUES (?,?,?,?,?,?,?)').bind(u.id, u.username, u.display_name, u.role, hash, salt, PBKDF2_ITER));
    }
  }
  const lists = { discipline: new Set([...CONGRESSES.map((c) => c.discipline), ...EXTRA_DISCIPLINES]), pays: new Set([...CONGRESSES.map((c) => c.country), ...EXTRA_PAYS]) };
  for (const [kind, set] of Object.entries(lists)) for (const value of set) stmts.push(db.prepare(`INSERT INTO options (sbx, kind, value, norm) VALUES ('',?,?,?)`).bind(kind, value, norm(value)));
  for (const c of CONGRESSES) {
    stmts.push(db.prepare(`INSERT INTO congresses (sbx, id, ref, slug, title, discipline, city, country, start_date, end_date, venue, official_url, verified_on, description, status, search_text, created_at, created_by, updated_at, updated_by)
      VALUES ('',?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?,1)`).bind(c.id, c.ref, congressSlug(c.title, c.ref), c.title, c.discipline, c.city, c.country, c.start, c.end, c.venue,
      `https://www.example.org/congres/${c.ref.toLowerCase()}`, '2026-10-12', c.description, c.status, congressSearch(c), '2026-10-01T09:00:00Z', '2026-10-12T09:00:00Z'));
  }
  for (const g of GME_SEED) {
    stmts.push(db.prepare(`INSERT INTO gme_codes (sbx, congress_id, code_enc, status, valid_from, valid_to, evidence, updated_at, updated_by) VALUES ('',?,?,?,?,?,?,?,1)`)
      .bind(g.congress_id, await encryptCode(env, g.code), g.status, g.valid_from, g.valid_to, g.evidence, '2026-10-12T09:00:00Z'));
  }
  for (const e of ENQUIRIES) {
    const ref = `DV-2026-${String(e.id).padStart(4, '0')}`;
    stmts.push(db.prepare(`INSERT INTO enquiries (sbx, id, ref, congress_id, name, email, phone, company, departure_city, date_out, date_back, passengers, message, consent_at, status, owner_id, created_at, updated_at)
      VALUES ('',?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)`).bind(e.id, ref, e.cg, e.name, e.email, e.phone, e.company, e.city, e.out, e.back, e.pax, e.msg, e.created, e.status, e.owner, e.created, e.created));
    const ev = (at, user, kind, from, to) => stmts.push(db.prepare(`INSERT INTO enquiry_events (sbx, enquiry_id, id, at, user_id, kind, from_val, to_val) VALUES ('',?,?,?,?,?,?,?)`).bind(e.id, eventId(at), at, user, kind, from, to));
    let t = new Date(e.created).getTime();
    const step = () => new Date((t += 3 * 3600 * 1000)).toISOString();
    if (e.owner) ev(step(), 1, 'responsable', null, String(e.owner));
    const target = e.status === 'gagnee' || e.status === 'perdue' ? [...PATH, e.status] : PATH.slice(0, PATH.indexOf(e.status) + 1);
    for (let i = 1; i < target.length; i++) ev(step(), e.owner || 1, 'statut', target[i - 1], target[i]);
  }
  stmts.push(db.prepare(`INSERT INTO gme_requests (sbx, id, congress_id, user_id, reason, status, created_at) VALUES ('', 1, 103, 2, ?, 'en_attente', ?)`)
    .bind('Préparer le devis de M. Martin (DV-2026-0002), deux places.', '2026-11-04T09:30:00Z'));
  // « Lien de groupe »: DV-2026-0001 (6 passengers) has an active link and 3 of its 6 delegates have answered.
  // The seed salt is fixed so the link survives resets; the token itself needs GME_KEY, so it is not in the repo.
  const seedToken = await hmac(env, 'group-v1', 'tok|' + GROUP_SEED.salt);
  stmts.push(db.prepare(`INSERT INTO group_links (sbx, enquiry_id, origin_sbx, token_mac, tok_salt, created_at, created_by, expires_at) VALUES ('', ?, '', ?, ?, ?, 2, ?)`)
    .bind(GROUP_SEED.enquiry_id, await hmac(env, 'group-v1', 'id|' + seedToken), GROUP_SEED.salt, now, addDays(today(), 30) + 'T23:59:59Z'));
  for (const d of GROUP_SEED.delegates) {
    stmts.push(db.prepare(`INSERT INTO group_delegates (sbx, enquiry_id, email_norm, id, name, email, departure_city, date_out, date_back, consent_at, created_at, updated_at) VALUES ('',?,?,?,?,?,?,?,?,?,?,?)`)
      .bind(GROUP_SEED.enquiry_id, d.email.toLowerCase(), d.id, d.name, d.email, d.city, d.out, d.back, d.at, d.at, d.at));
  }
  await db.batch(stmts);
  return { ok: true, at: now, today: today(), plus: addDays(today(), 0) };
}
