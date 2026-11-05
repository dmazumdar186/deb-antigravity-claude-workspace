// Schema, seed and reset. Everything here is fictional demo data.
import { encryptCode, hashPassword, newSalt, slugify, norm, PBKDF2_ITER, nowIso, addDays, today } from './lib.js';

export const SCHEMA = [
  `CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, display_name TEXT NOT NULL, role TEXT NOT NULL CHECK (role IN ('direction','equipe','contributeur')), pw_hash TEXT NOT NULL, pw_salt TEXT NOT NULL, pw_iter INTEGER NOT NULL)`,
  `CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, csrf TEXT NOT NULL, created_at TEXT NOT NULL, expires_at INTEGER NOT NULL)`,
  `CREATE TABLE IF NOT EXISTS congresses (id INTEGER PRIMARY KEY, ref TEXT UNIQUE NOT NULL, slug TEXT UNIQUE NOT NULL, title TEXT NOT NULL, discipline TEXT NOT NULL, city TEXT NOT NULL, country TEXT NOT NULL, start_date TEXT NOT NULL, end_date TEXT NOT NULL, venue TEXT NOT NULL, official_url TEXT NOT NULL, verified_on TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', status TEXT NOT NULL CHECK (status IN ('brouillon','a_relire','publie','archive')), search_text TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, updated_by INTEGER)`,
  `CREATE INDEX IF NOT EXISTS idx_cg_pub ON congresses (status, end_date, start_date)`,
  `CREATE TABLE IF NOT EXISTS congress_events (id INTEGER PRIMARY KEY, congress_id INTEGER NOT NULL, at TEXT NOT NULL, user_id INTEGER, kind TEXT NOT NULL, from_val TEXT, to_val TEXT)`,
  `CREATE TABLE IF NOT EXISTS enquiries (id INTEGER PRIMARY KEY, ref TEXT UNIQUE NOT NULL, congress_id INTEGER NOT NULL, name TEXT NOT NULL, email TEXT NOT NULL, phone TEXT NOT NULL, company TEXT NOT NULL DEFAULT '', departure_city TEXT NOT NULL, date_out TEXT NOT NULL, date_back TEXT NOT NULL, passengers INTEGER NOT NULL, message TEXT NOT NULL DEFAULT '', consent_at TEXT NOT NULL, status TEXT NOT NULL CHECK (status IN ('nouvelle','qualifiee','devis','gagnee','perdue')), owner_id INTEGER, form_nonce TEXT UNIQUE, ip_hash TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)`,
  `CREATE TABLE IF NOT EXISTS enquiry_events (id INTEGER PRIMARY KEY, enquiry_id INTEGER NOT NULL, at TEXT NOT NULL, user_id INTEGER, kind TEXT NOT NULL CHECK (kind IN ('creation','statut','responsable','note')), from_val TEXT, to_val TEXT)`,
  // Append-only at the database level: history rows can never be edited or removed.
  `CREATE TRIGGER IF NOT EXISTS enquiry_events_no_update BEFORE UPDATE ON enquiry_events BEGIN SELECT RAISE(ABORT, 'append-only'); END`,
  `CREATE TABLE IF NOT EXISTS notifications (id INTEGER PRIMARY KEY, enquiry_id INTEGER NOT NULL, at TEXT NOT NULL, to_addr TEXT NOT NULL, subject TEXT NOT NULL, body TEXT NOT NULL)`,
  `CREATE TABLE IF NOT EXISTS gme_codes (congress_id INTEGER PRIMARY KEY, code_enc TEXT, status TEXT NOT NULL CHECK (status IN ('detecte','verifie','approuve','expire')), valid_from TEXT, valid_to TEXT, evidence TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL, updated_by INTEGER)`,
  `CREATE TABLE IF NOT EXISTS gme_requests (id INTEGER PRIMARY KEY, congress_id INTEGER NOT NULL, user_id INTEGER NOT NULL, reason TEXT NOT NULL, status TEXT NOT NULL CHECK (status IN ('en_attente','approuvee','refusee','revoquee')), created_at TEXT NOT NULL, decided_at TEXT, decided_by INTEGER, expires_at TEXT)`,
  `CREATE TABLE IF NOT EXISTS gme_access_log (id INTEGER PRIMARY KEY, at TEXT NOT NULL, user_id INTEGER NOT NULL, congress_id INTEGER NOT NULL, result TEXT NOT NULL)`,
  `CREATE TABLE IF NOT EXISTS rate_limits (key TEXT PRIMARY KEY, count INTEGER NOT NULL, reset_at INTEGER NOT NULL)`,
];
const DATA_TABLES = ['congress_events', 'enquiry_events', 'notifications', 'enquiries', 'gme_access_log', 'gme_requests', 'gme_codes', 'congresses', 'rate_limits'];

export const USERS = [
  { id: 1, username: 'direction', display_name: 'Direction ASSET', role: 'direction' },
  { id: 2, username: 'equipe', display_name: 'Équipe ASSET', role: 'equipe' },
  { id: 3, username: 'contributeur', display_name: 'Contributeur (exemple)', role: 'contributeur' },
];
export const DEMO_PASSWORD = 'demo-asset';

const FICTION = 'Fiche d’exemple pour la démonstration : congrès, lieu et site officiel sont fictifs.';
const C = (n, title, discipline, city, country, start, end, venue, blurb, status = 'publie') => ({
  id: n, ref: `CG-0${n}`, title, discipline, city, country, start, end, venue, status,
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
export const congressSearch = (c) => norm([c.title, c.city, c.discipline, c.country, c.ref].join(' '));
export const congressSlug = (title, ref) => `${slugify(title.replace(/\s*—\s*exemple\s*$/i, ''))}-${ref.toLowerCase()}`;

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

export const STATUS_LABELS = { nouvelle: 'Nouvelle', qualifiee: 'Qualifiée', devis: 'Devis envoyé', gagnee: 'Gagnée', perdue: 'Perdue' };
export const CG_STATUS = { brouillon: 'Brouillon', a_relire: 'À relire', publie: 'Publié', archive: 'Archivé' };
export const GME_STATUS = { detecte: 'Détecté', verifie: 'Vérifié', approuve: 'Approuvé pour la vente', expire: 'Expiré' };
export const TEAM_INBOX = 'equipe.congres@example.com';

export function notificationFor(enq, congress) {
  const subject = `Nouvelle demande ${enq.ref} : ${congress.title}`;
  const body = [
    `Une nouvelle demande de devis vol est arrivée sur le site.`,
    ``,
    `Référence : ${enq.ref}`,
    `Congrès : ${congress.title} (${congress.ref})`,
    `Contact : ${enq.name}, ${enq.email}, ${enq.phone}${enq.company ? ', ' + enq.company : ''}`,
    `Départ : ${enq.departure_city}, aller le ${enq.date_out}, retour le ${enq.date_back}`,
    `Passagers : ${enq.passengers}`,
    ``,
    `Ouvrir dans la console : /console/demandes/${enq.id}`,
  ].join('\n');
  return { subject, body };
}

let schemaReady = false;
export async function ensureReady(env) {
  if (schemaReady) return;
  let n = 0;
  try { n = (await env.DB.prepare('SELECT COUNT(*) AS n FROM users').first())?.n || 0; } catch { n = 0; }
  if (!n) await resetDemo(env, { keepSessions: false });
  schemaReady = true;
}

// Idempotent: wipes demo data and re-inserts the same seed with the same ids.
export async function resetDemo(env, { keepSessions = false } = {}) {
  const db = env.DB;
  await db.batch(SCHEMA.map((s) => db.prepare(s)));
  const stmts = DATA_TABLES.map((t) => db.prepare(`DELETE FROM ${t}`));
  if (!keepSessions) stmts.push(db.prepare('DELETE FROM sessions'));
  const now = nowIso();

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
  for (const c of CONGRESSES) {
    stmts.push(db.prepare(`INSERT INTO congresses (id, ref, slug, title, discipline, city, country, start_date, end_date, venue, official_url, verified_on, description, status, search_text, created_at, updated_at, updated_by)
      VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)`).bind(c.id, c.ref, congressSlug(c.title, c.ref), c.title, c.discipline, c.city, c.country, c.start, c.end, c.venue,
      `https://www.example.org/congres/${c.ref.toLowerCase()}`, '2026-10-12', c.description, c.status, congressSearch(c), '2026-10-01T09:00:00Z', '2026-10-12T09:00:00Z'));
  }
  for (const g of GME_SEED) {
    stmts.push(db.prepare('INSERT INTO gme_codes (congress_id, code_enc, status, valid_from, valid_to, evidence, updated_at, updated_by) VALUES (?,?,?,?,?,?,?,1)')
      .bind(g.congress_id, await encryptCode(env, g.code), g.status, g.valid_from, g.valid_to, g.evidence, '2026-10-12T09:00:00Z'));
  }
  const byId = Object.fromEntries(CONGRESSES.map((c) => [c.id, c]));
  for (const e of ENQUIRIES) {
    const ref = `DV-2026-${String(e.id).padStart(4, '0')}`;
    stmts.push(db.prepare(`INSERT INTO enquiries (id, ref, congress_id, name, email, phone, company, departure_city, date_out, date_back, passengers, message, consent_at, status, owner_id, created_at, updated_at)
      VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)`).bind(e.id, ref, e.cg, e.name, e.email, e.phone, e.company, e.city, e.out, e.back, e.pax, e.msg, e.created, e.status, e.owner, e.created, e.created));
    const ev = (at, user, kind, from, to) => stmts.push(db.prepare('INSERT INTO enquiry_events (enquiry_id, at, user_id, kind, from_val, to_val) VALUES (?,?,?,?,?,?)').bind(e.id, at, user, kind, from, to));
    ev(e.created, null, 'creation', null, 'nouvelle');
    let t = new Date(e.created).getTime();
    const step = () => new Date((t += 3 * 3600 * 1000)).toISOString();
    if (e.owner) ev(step(), 1, 'responsable', null, String(e.owner));
    const target = e.status === 'gagnee' || e.status === 'perdue' ? [...PATH, e.status] : PATH.slice(0, PATH.indexOf(e.status) + 1);
    for (let i = 1; i < target.length; i++) ev(step(), e.owner || 1, 'statut', target[i - 1], target[i]);
    const n = notificationFor({ ...e, ref, departure_city: e.city, date_out: e.out, date_back: e.back, passengers: e.pax, email: e.email, phone: e.phone }, byId[e.cg]);
    stmts.push(db.prepare('INSERT INTO notifications (enquiry_id, at, to_addr, subject, body) VALUES (?,?,?,?,?)').bind(e.id, e.created, TEAM_INBOX, n.subject, n.body));
  }
  stmts.push(db.prepare('INSERT INTO gme_requests (congress_id, user_id, reason, status, created_at) VALUES (103, 2, ?, ?, ?)')
    .bind('Préparer le devis de M. Martin (DV-2026-0002), deux places.', 'en_attente', '2026-11-04T09:30:00Z'));
  await db.batch(stmts);
  return { ok: true, at: now, today: today(), plus: addDays(today(), 0) };
}
