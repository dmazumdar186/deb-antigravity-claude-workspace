// Reviews store (KV) shared by /api/reviews (public) and /api/review-admin (Basic auth).
// Source of truth: one key per review, `rev:<id>` -> Review. The id is sha256(name|text) so a re-submit of the
// same review is an idempotent upsert, never a duplicate.
// Read model: `reviews:snapshot` -> Snapshot (published only, newest first), rebuilt from a paginated
// `rev:` list after every write and whenever it is older than SNAPSHOT_MAX_AGE_S (KV list is eventually
// consistent, so a rebuild also merges the record just written).
import { Env, logError } from './_lib';

export type Status = 'published' | 'pending' | 'hidden';
export interface Review {
  id: string; name: string; rating: number; text: string; lang: 'en' | 'fr';
  ts: string; status: Status; hold_reason?: string; ip_hash?: string; consent_text: string;
}
export interface PublicReview { id: string; name: string; rating: number; text: string; lang: string; ts: string }
export interface Snapshot { built: string; reviews: PublicReview[] }

export const NAME_MIN = 2, NAME_MAX = 40, TEXT_MIN = 20, TEXT_MAX = 1200;
export const FEATURED_COUNT = 3, FEATURED_MIN_RATING = 4, PAGE_SIZE = 10, PAGE_MAX = 50;
export const SNAPSHOT_KEY = 'reviews:snapshot', SNAPSHOT_MAX_AGE_S = 300, STORE_MAX = 2000;

export const REVIEW_CONSENT = {
  en: 'I agree that my first name, rating, review and its date are published on this site.',
  fr: 'J’accepte que mon prénom, ma note, mon avis et sa date soient publiés sur ce site.',
};

// Collapse whitespace, strip control/format characters (incl. bidi overrides) — the text is rendered with
// textContent on the client, so this is about tidiness and spoofing, not HTML injection.
export function clean(v: unknown, max: number, multiline = false): string {
  let s = String(v ?? '').normalize('NFC').replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F\u200B-\u200F\u202A-\u202E\u2060-\u2069\uFEFF]/g, '');
  s = multiline ? s.replace(/\r\n?/g, '\n').replace(/[ \t]+/g, ' ').replace(/\n{3,}/g, '\n\n') : s.replace(/\s+/g, ' ');
  return s.trim().slice(0, max);
}

// Offensive and advertising words that hold a review for Jeevana instead of publishing it (EN + FR, whole-word, accent-folded).
const HOLD_WORDS = ['fuck', 'fucking', 'shit', 'bitch', 'cunt', 'asshole', 'whore', 'slut', 'nigger', 'faggot',
  'viagra', 'casino', 'crypto', 'bitcoin', 'porn', 'escort', 'loan',
  'merde', 'putain', 'pute', 'salope', 'connard', 'connasse', 'encule', 'batard', 'pd'];
// Not held on purpose: 'retard' (FR "en retard"), 'nique' ("pique-nique").
// Accusation words (scam, arnaque, escroc...) are deliberately NOT held: honest negative reviews must publish like any other.
const fold = (s: string) => s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();

// Returns why a review must wait for moderation, or '' to publish now.
export function holdReason(name: string, text: string): string {
  const all = name + '\n' + text;
  if (/(https?:\/\/|www\.|\b[a-z0-9-]{2,}\.(com|fr|net|org|io|ru|xyz|info|biz)\b)/i.test(all)) return 'link';
  if (/[^\s@]+@[^\s@]+\.[^\s@]+/.test(all)) return 'email';
  for (const m of all.match(/\+?\d[\d\s().-]{7,}\d/g) || []) if (m.replace(/\D/g, '').length >= 9) return 'phone'; // dates like 12.10.2026 have 8 digits
  if (fold(name).includes('jeevana')) return 'name';
  const words = new Set(fold(all).split(/[^a-z0-9]+/).filter(Boolean));
  const hit = HOLD_WORDS.find((w) => words.has(w));
  if (hit) return 'word:' + hit;
  if (/(.)\1{9,}/.test(text) || (text.replace(/[^A-Z]/g, '').length > 40 && text === text.toUpperCase())) return 'shouting';
  return '';
}

// Every write goes through here so list metadata (status) always matches the record.
export async function putReview(kv: KVNamespace, r: Review): Promise<void> {
  await kv.put(`rev:${r.id}`, JSON.stringify(r), { metadata: { s: r.status } });
}

// Burst guard: when BURST_MAX reviews were published in the last hour, new ones wait for Jeevana.
export const BURST_MAX = 5, BURST_WINDOW_MS = 60 * 60 * 1000;
export function burst(snap: Snapshot, now = Date.now()): boolean {
  return snap.reviews.filter((r) => now - Date.parse(r.ts) < BURST_WINDOW_MS).length >= BURST_MAX;
}

export function toPublic(r: Review): PublicReview {
  return { id: r.id, name: r.name, rating: r.rating, text: r.text, lang: r.lang, ts: r.ts };
}

// onlyPublished: skip GETs for keys whose list metadata says pending/hidden (bounds KV reads per rebuild).
export async function listAll(kv: KVNamespace, onlyPublished = false): Promise<Review[]> {
  const out: Review[] = [];
  let cursor: string | undefined;
  do {
    const page = await kv.list<{ s?: Status }>({ prefix: 'rev:', cursor });
    const keys = onlyPublished ? page.keys.filter((k) => !k.metadata?.s || k.metadata.s === 'published') : page.keys;
    const vals = await Promise.all(keys.map((k) => kv.get(k.name)));
    for (const v of vals) {
      if (!v) continue;
      try { out.push(JSON.parse(v) as Review); } catch (err) { logError('reviews:parse', err); }
    }
    cursor = page.list_complete ? undefined : page.cursor;
  } while (cursor && out.length < STORE_MAX);
  return out;
}

const newestFirst = (a: { ts: string }, b: { ts: string }) => (a.ts < b.ts ? 1 : a.ts > b.ts ? -1 : 0);

// Rebuild the published snapshot; `fresh` is a just-written record that the list may not show yet.
export async function rebuild(env: Env, fresh?: Review): Promise<Snapshot> {
  const kv = env.JEEVANA_KV as KVNamespace;
  const byId = new Map<string, Review>();
  for (const r of await listAll(kv, true)) byId.set(r.id, r);
  if (fresh) byId.set(fresh.id, fresh);
  const reviews = [...byId.values()].filter((r) => r.status === 'published').sort(newestFirst).map(toPublic);
  const snap: Snapshot = { built: new Date().toISOString(), reviews };
  await kv.put(SNAPSHOT_KEY, JSON.stringify(snap));
  return snap;
}

export async function snapshot(env: Env): Promise<Snapshot> {
  const kv = env.JEEVANA_KV as KVNamespace;
  const raw = await kv.get(SNAPSHOT_KEY);
  if (raw) {
    try {
      const s = JSON.parse(raw) as Snapshot;
      if (Date.now() - Date.parse(s.built) < SNAPSHOT_MAX_AGE_S * 1000) return s;
    } catch (err) { logError('reviews:snapshot', err); }
  }
  return rebuild(env);
}

// Featured = the FEATURED_COUNT newest reviews rated >= FEATURED_MIN_RATING; the rest list newest first.
export function view(snap: Snapshot, offset: number, limit: number) {
  const all = snap.reviews;
  const featured = all.filter((r) => r.rating >= FEATURED_MIN_RATING).slice(0, FEATURED_COUNT);
  const fIds = new Set(featured.map((r) => r.id));
  const rest = all.filter((r) => !fIds.has(r.id));
  const counts = [1, 2, 3, 4, 5].map((n) => all.filter((r) => r.rating === n).length);
  const total = all.length;
  const average = total ? Math.round((all.reduce((s, r) => s + r.rating, 0) / total) * 10) / 10 : null;
  return { total, average, counts, featured, reviews: rest.slice(offset, offset + limit), rest_total: rest.length, offset, limit };
}
