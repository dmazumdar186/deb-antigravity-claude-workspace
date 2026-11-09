// Shared helpers: HTML escaping, crypto (WebCrypto only), dates, forms, responses.

// ---------- HTML: every interpolation is escaped unless wrapped in raw() ----------
class Raw { constructor(s) { this.s = s; } toString() { return this.s; } }
export const raw = (s) => new Raw(String(s));
export function esc(v) {
  if (v === null || v === undefined || v === false) return '';
  if (v instanceof Raw) return v.s;
  if (Array.isArray(v)) return v.map(esc).join('');
  return String(v).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
export function html(strings, ...vals) {
  let out = strings[0];
  for (let i = 0; i < vals.length; i++) out += esc(vals[i]) + strings[i + 1];
  return new Raw(out);
}

// ---------- encoding ----------
const enc = new TextEncoder();
const dec = new TextDecoder();
export function b64(buf) {
  const bytes = buf instanceof Uint8Array ? buf : new Uint8Array(buf);
  let s = '';
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s);
}
export function unb64(str) {
  const s = atob(str);
  const out = new Uint8Array(s.length);
  for (let i = 0; i < s.length; i++) out[i] = s.charCodeAt(i);
  return out;
}
export const b64url = (buf) => b64(buf).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
export function randomToken(n = 32) { return b64url(crypto.getRandomValues(new Uint8Array(n))); }
export async function sha256hex(text) {
  const d = await crypto.subtle.digest('SHA-256', enc.encode(text));
  return [...new Uint8Array(d)].map((b) => b.toString(16).padStart(2, '0')).join('');
}
export function safeEqual(a, b) {
  if (typeof a !== 'string' || typeof b !== 'string' || a.length !== b.length) return false;
  let r = 0;
  for (let i = 0; i < a.length; i++) r |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return r === 0;
}

// ---------- keys: one Worker secret (GME_KEY, 32 random bytes, base64) ----------
// AES-GCM for GM&E codes uses it directly. Every MAC has its own key, derived with HKDF (SHA-256) from GME_KEY with a
// dedicated info label, so no MAC can ever be replayed for another purpose:
//   session-v1 (session cookies), form-v1 (anonymous form tokens), confirm-v1 (confirmation links), iphash-v1 (IP hashes),
//   group-v1 (« Lien de groupe »: link tokens, their lookup MAC and the delegate confirmation links),
//   delegate-v1 (the delegate's browser cookie that may update its own entry).
// No GME_KEY means no key at all: every request fails closed before any token or session is accepted.
export const MAC_PURPOSES = ['session-v1', 'form-v1', 'confirm-v1', 'iphash-v1', 'group-v1', 'delegate-v1'];
let keyCache = null;
export async function keys(env) {
  if (!env.GME_KEY) throw new Error('GME_KEY secret is not set');
  if (keyCache && keyCache.src === env.GME_KEY) return keyCache;
  const rawKey = unb64(env.GME_KEY);
  if (rawKey.length !== 32) throw new Error('GME_KEY must be 32 bytes, base64');
  const aes = await crypto.subtle.importKey('raw', rawKey, 'AES-GCM', false, ['encrypt', 'decrypt']);
  const hk = await crypto.subtle.importKey('raw', rawKey, 'HKDF', false, ['deriveKey']);
  const mac = {};
  for (const info of MAC_PURPOSES) {
    mac[info] = await crypto.subtle.deriveKey(
      { name: 'HKDF', hash: 'SHA-256', salt: enc.encode('asset-voyages-demo'), info: enc.encode(info) },
      hk, { name: 'HMAC', hash: 'SHA-256', length: 256 }, false, ['sign']);
  }
  keyCache = { src: env.GME_KEY, aes, mac };
  return keyCache;
}
// hmac(env, 'session-v1', text): MAC under the key of that purpose only.
export async function hmac(env, purpose, text) {
  const { mac } = await keys(env);
  if (!mac[purpose]) throw new Error('unknown MAC purpose');
  return b64url(await crypto.subtle.sign('HMAC', mac[purpose], enc.encode(text)));
}
export async function encryptCode(env, plain) {
  const { aes } = await keys(env);
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const ct = new Uint8Array(await crypto.subtle.encrypt({ name: 'AES-GCM', iv, additionalData: enc.encode('gme-v1') }, aes, enc.encode(plain)));
  const out = new Uint8Array(12 + ct.length);
  out.set(iv); out.set(ct, 12);
  return 'v1:' + b64(out);
}
export async function decryptCode(env, stored) {
  const { aes } = await keys(env);
  const bytes = unb64(String(stored).replace(/^v1:/, ''));
  const pt = await crypto.subtle.decrypt({ name: 'AES-GCM', iv: bytes.slice(0, 12), additionalData: enc.encode('gme-v1') }, aes, bytes.slice(12));
  return dec.decode(pt);
}

// ---------- passwords: PBKDF2-SHA256 (WebCrypto) ----------
// 25,000 iterations keeps a login inside the free plan's CPU budget; production raises it.
export const PBKDF2_ITER = 25000;
export async function hashPassword(password, saltB64, iter = PBKDF2_ITER) {
  const base = await crypto.subtle.importKey('raw', enc.encode(password), 'PBKDF2', false, ['deriveBits']);
  const bits = await crypto.subtle.deriveBits({ name: 'PBKDF2', hash: 'SHA-256', salt: unb64(saltB64), iterations: iter }, base, 256);
  return b64(bits);
}
export const newSalt = () => b64(crypto.getRandomValues(new Uint8Array(16)));

// ---------- dates (ISO yyyy-mm-dd) ----------
// « Today » is always the Paris calendar day (CE-B2-002): past filters, date validation, defaults and CSV file names
// must not be one day behind between 00:00 and 01:00 (02:00 in summer) Paris time.
export const parisToday = () => new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Paris', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
export const today = parisToday;
export const nowIso = () => new Date().toISOString();
export function addDays(iso, n) {
  const d = new Date(iso + 'T00:00:00Z');
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}
export function isIsoDate(s) {
  if (typeof s !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(s)) return false;
  const d = new Date(s + 'T00:00:00Z');
  return !Number.isNaN(d.getTime()) && d.toISOString().slice(0, 10) === s;
}
const MOIS = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.'];
export const MOIS_LONG = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre'];
const parts = (iso) => { const [y, m, d] = iso.split('-').map(Number); return { y, m, d }; };
export function frDate(iso) {
  if (!iso) return '';
  const { y, m, d } = parts(iso.slice(0, 10));
  return `${d} ${MOIS[m - 1]} ${y}`;
}
export function frNumDate(iso) {
  if (!iso) return '';
  const { y, m, d } = parts(iso.slice(0, 10));
  return `${String(d).padStart(2, '0')}/${String(m).padStart(2, '0')}/${y}`;
}
export function frDateTime(iso) {
  if (!iso) return '';
  const dt = new Date(iso);
  // Display in Paris time without Intl dependence: Workers ship full ICU, so Intl is safe here.
  return new Intl.DateTimeFormat('fr-FR', { timeZone: 'Europe/Paris', day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }).format(dt);
}
export function frRange(start, end) {
  const a = parts(start); const b = parts(end);
  if (a.y === b.y && a.m === b.m) return a.d === b.d ? frDate(start) : `${a.d} au ${b.d} ${MOIS[a.m - 1]} ${a.y}`;
  if (a.y === b.y) return `${a.d} ${MOIS[a.m - 1]} au ${b.d} ${MOIS[b.m - 1]} ${b.y}`;
  return `${frDate(start)} au ${frDate(end)}`;
}
export function rangeParts(start, end) {
  // Catalogue date block: big day span over the month and year; read together they form the date line.
  const a = parts(start); const b = parts(end);
  if (a.m === b.m && a.y === b.y) return { days: a.d === b.d ? `${a.d}` : `${a.d} au ${b.d}`, months: `${MOIS_LONG[a.m - 1]} ${a.y}`, cross: false };
  return { days: `${a.d}\u00a0${MOIS[a.m - 1]} au ${b.d}\u00a0${MOIS[b.m - 1]}`, months: `${b.y}`, cross: true };
}

// ---------- text ----------
export const norm = (s) => String(s || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim();
export function slugify(s) {
  return norm(s).replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 80);
}
export const clean = (v, max) => String(v ?? '').replace(/\r\n/g, '\n').replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/g, '').trim().slice(0, max + 1);

// ---------- requests ----------
export const MAX_BODY = 32 * 1024;
export async function readForm(req) {
  const ct = (req.headers.get('content-type') || '').toLowerCase();
  if (!ct.startsWith('application/x-www-form-urlencoded')) return { error: 415 };
  const len = Number(req.headers.get('content-length') || 0);
  if (len > MAX_BODY) return { error: 413 };
  const text = await req.text();
  if (text.length > MAX_BODY) return { error: 413 };
  const p = new URLSearchParams(text);
  const get = (k) => p.get(k) ?? '';
  return { get, all: (k) => p.getAll(k), has: (k) => p.has(k) };
}
export function sameOrigin(req) {
  const origin = req.headers.get('origin');
  if (!origin) {
    // No Origin (old browsers, some tools): fall back to Sec-Fetch-Site when present.
    const sfs = req.headers.get('sec-fetch-site');
    return !sfs || sfs === 'same-origin' || sfs === 'none';
  }
  return origin === new URL(req.url).origin;
}
export async function ipHash(env, req) {
  const ip = req.headers.get('cf-connecting-ip') || 'local';
  return (await hmac(env, 'iphash-v1', ip)).slice(0, 22);
}
export function getCookie(req, name) {
  const h = req.headers.get('cookie') || '';
  for (const part of h.split(';')) {
    const i = part.indexOf('=');
    if (i > 0 && part.slice(0, i).trim() === name) return part.slice(i + 1).trim();
  }
  return null;
}

// ---------- responses ----------
export function htmlResponse(body, status = 200, headers = {}) {
  return new Response('<!doctype html>' + esc(body), { status, headers: { 'content-type': 'text/html; charset=utf-8', ...headers } });
}
export function redirect(location, headers = {}) {
  return new Response(null, { status: 303, headers: { location, ...headers } });
}

// ---------- rate limit (fixed window, stored in D1) ----------
// One atomic statement: insert or increment (restarting the window when it has expired), then read the new count.
export async function rateHit(env, key, limit, windowSec) {
  const now = Math.floor(Date.now() / 1000);
  const row = await env.DB.prepare(`INSERT INTO rate_limits (key, count, reset_at) VALUES (?1, 1, ?2 + ?3)
    ON CONFLICT(key) DO UPDATE SET count = CASE WHEN reset_at <= ?2 THEN 1 ELSE count + 1 END,
      reset_at = CASE WHEN reset_at <= ?2 THEN ?2 + ?3 ELSE reset_at END
    RETURNING count`).bind(key, now, windowSec).first();
  return row.count <= limit;
}
export async function rateBlocked(env, key, limit) {
  const now = Math.floor(Date.now() / 1000);
  const row = await env.DB.prepare('SELECT count, reset_at FROM rate_limits WHERE key = ?').bind(key).first();
  return !!row && row.reset_at > now && row.count >= limit;
}

// ---------- signed form tokens (CSRF for anonymous forms + minimum fill time) ----------
export async function makeFormToken(env, purpose) {
  const ts = Date.now();
  const nonce = randomToken(12);
  // the form kind (enquiry, login) is a signed field of the token, under the form-v1 key
  return `${ts}.${nonce}.${await hmac(env, 'form-v1', JSON.stringify([purpose, ts, nonce]))}`;
}
export async function checkFormToken(env, purpose, token, { minMs = 0, maxMs = 2 * 3600 * 1000 } = {}) {
  const m = /^(\d{10,16})\.([A-Za-z0-9_-]{8,40})\.([A-Za-z0-9_-]{20,80})$/.exec(String(token || ''));
  if (!m) return { ok: false, why: 'invalid' };
  const [, ts, nonce, sig] = m;
  if (!safeEqual(sig, await hmac(env, 'form-v1', JSON.stringify([purpose, Number(ts), nonce])))) return { ok: false, why: 'invalid' };
  const age = Date.now() - Number(ts);
  if (age < minMs) return { ok: false, why: 'fast', nonce };
  if (age > maxMs) return { ok: false, why: 'expired', nonce };
  return { ok: true, nonce };
}

// ---------- CSV (semicolon, BOM, formula-injection neutralised) ----------
export function csvCell(v) {
  let s = String(v ?? '');
  if (/^[=+\-@\t\r]/.test(s)) s = "'" + s;
  return '"' + s.replace(/"/g, '""') + '"';
}
