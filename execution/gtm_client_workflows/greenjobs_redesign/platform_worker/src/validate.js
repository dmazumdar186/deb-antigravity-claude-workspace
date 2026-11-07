// Pure input validation. No I/O, no globals: every function is unit-tested offline.
// Floors and ceilings mirror the CHECK constraints in build/d1/schema.sql.

// C0 controls except TAB/LF/CR, plus DEL and C1 controls. NUL is always removed.
const CONTROL_RE = /[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F-\u009F]/g;
const LINE_BREAK_RE = /[\r\n\u2028\u2029]/;

export function stripControl(s) {
  return String(s).replace(CONTROL_RE, '');
}

export function hasHeaderInjection(s) {
  return typeof s === 'string' && LINE_BREAK_RE.test(s);
}

/**
 * Clean one free-text field. Returns {ok:true, value} or {ok:false, error}.
 * opts: {min, max, multiline=false, required=true, header=false}
 *  - header: the value reaches an email header, so a raw CR/LF is rejected outright.
 *  - single-line fields have line breaks and tabs collapsed to spaces.
 */
export function cleanText(raw, opts = {}) {
  const { min = 0, max = 1000, multiline = false, required = true, header = false } = opts;
  if (raw === undefined || raw === null || raw === '') {
    return required ? { ok: false, error: 'required' } : { ok: true, value: null };
  }
  if (typeof raw !== 'string' && typeof raw !== 'number') return { ok: false, error: 'type' };
  let s = String(raw);
  if (header && hasHeaderInjection(s)) return { ok: false, error: 'header_injection' };
  s = stripControl(s).normalize('NFC');
  s = multiline ? s.replace(/\r\n?/g, '\n') : s.replace(/\s+/g, ' ');
  s = s.trim();
  if (!s) return required ? { ok: false, error: 'required' } : { ok: true, value: null };
  if (s.length < min) return { ok: false, error: 'too_short' };
  if (s.length > max) return { ok: false, error: 'too_long' };
  return { ok: true, value: s };
}

const EMAIL_RE =
  /^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]{1,64}@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$/;

export function normEmail(s) {
  return String(s || '').trim().toLowerCase();
}

export function isValidEmail(raw) {
  if (typeof raw !== 'string' || hasHeaderInjection(raw)) return false;
  const s = raw.trim();
  if (s.length < 3 || s.length > 254) return false;
  if (s.includes('..')) return false;
  return EMAIL_RE.test(s);
}

// CSV/spreadsheet formula injection: store raw text, neutralise only on export.
export function toCsvCell(value) {
  if (value === null || value === undefined) return '';
  let s = String(value);
  if (/^[=+\-@\t\r]/.test(s)) s = `'${s}`;
  if (/[",\r\n]/.test(s)) s = `"${s.replace(/"/g, '""')}"`;
  return s;
}

// Prompt injection is flagged, not blocked: job text may later feed the Ask LLM.
const INJECTION_PATTERNS = [
  /ignore\s+(all\s+|any\s+|the\s+)?(previous|prior|above|earlier)\s+(instructions|prompts|messages|rules)/i,
  /disregard\s+(all\s+|any\s+|the\s+)?(previous|prior|above|earlier)/i,
  /system\s+prompt/i,
  /you\s+are\s+now\s+(a|an|the|in)\b/i,
  /<\|?(im_start|im_end|system)\|?>/i,
  /\bjailbreak\b/i,
];

export function looksLikePromptInjection(text) {
  if (typeof text !== 'string') return false;
  return INJECTION_PATTERNS.some((re) => re.test(text));
}

/** Field NAMES whose value looks like a prompt-injection attempt (values never returned). */
export function injectionFlags(obj, fields) {
  return fields.filter((f) => looksLikePromptInjection(obj?.[f]));
}

export const JOB_ID_RE = /^(ie|uk):(gj|strat|broadbean|idibu|logicmelon):[A-Za-z0-9-]{1,64}$/;

/**
 * Validate an id/key/filename taken from a URL or form. Decodes up to 3 times (so
 * %252e%252e is caught), then rejects traversal tokens before the strict regex.
 */
export function safeParam(raw, re = JOB_ID_RE) {
  if (typeof raw !== 'string' || raw.length === 0 || raw.length > 200) return { ok: false, error: 'invalid_id' };
  let s = raw;
  for (let i = 0; i < 3; i++) {
    let next;
    try {
      next = decodeURIComponent(s);
    } catch {
      return { ok: false, error: 'invalid_id' };
    }
    if (next === s) break;
    s = next;
  }
  const lower = s.toLowerCase();
  if (
    s.includes('..') || s.includes('/') || s.includes('\\') || s.includes('\u0000') ||
    lower.includes('%2e') || lower.includes('%2f') || lower.includes('%5c') || s.includes('%')
  ) {
    return { ok: false, error: 'invalid_id' };
  }
  if (!re.test(s)) return { ok: false, error: 'invalid_id' };
  return { ok: true, value: s };
}

export function validHttpsUrl(raw) {
  if (typeof raw !== 'string') return { ok: false, error: 'type' };
  const s = raw.trim();
  if (!s || s.length > 2000) return { ok: false, error: 'length' };
  if (/[\s\u0000-\u001F\u007F]/.test(s)) return { ok: false, error: 'control' };
  if (/^(javascript|data|vbscript|file):/i.test(s)) return { ok: false, error: 'scheme' };
  let u;
  try {
    u = new URL(s);
  } catch {
    return { ok: false, error: 'invalid_url' };
  }
  if (u.protocol !== 'https:') return { ok: false, error: 'scheme' };
  if (u.username || u.password) return { ok: false, error: 'credentials' };
  if (!u.hostname || !u.hostname.includes('.')) return { ok: false, error: 'host' };
  return { ok: true, value: u.toString() };
}

export function escapeHtml(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/** Plain text (stored as text) -> safe HTML paragraphs for render. */
export function renderDescription(text) {
  return String(text ?? '')
    .split(/\n{2,}/)
    .map((p) => p.trim())
    .filter(Boolean)
    .map((p) => `<p>${escapeHtml(p).replace(/\n/g, '<br>')}</p>`)
    .join('');
}

export function isIsoDate(s) {
  if (typeof s !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(s)) return false;
  const d = new Date(`${s}T00:00:00Z`);
  return !Number.isNaN(d.getTime()) && d.toISOString().slice(0, 10) === s;
}

const PHONE_RE = /^[0-9+() .-]{5,40}$/;
const SITES = ['ie', 'uk'];
const APPLY_MODES = ['inbox', 'consultant', 'advertiser', 'url'];
const PERIODS = ['year', 'day', 'hour', 'month'];
const CURRENCIES = ['EUR', 'GBP'];
const SAL_CEILING = 10_000_000;

export const JOB_FIELDS = [
  'title', 'employer', 'location', 'region', 'job_type', 'description', 'summary',
  'sal_min', 'sal_max', 'currency', 'period', 'sal_text', 'sectors',
  'apply_mode', 'apply_email', 'apply_url', 'closing', 'status',
];
export const FREE_TEXT_FIELDS = ['title', 'employer', 'location', 'description', 'summary', 'sal_text'];

function intOrNull(v) {
  if (v === undefined || v === null || v === '') return { ok: true, value: null };
  const n = typeof v === 'number' ? v : Number(v);
  if (!Number.isInteger(n) || n < 0 || n > SAL_CEILING) return { ok: false };
  return { ok: true, value: n };
}

/**
 * Validate a console job payload.
 * input: merged job object (create body, or existing row overlaid with the PUT body).
 * opts: {site, today, provided: Set of keys present in the request, allowStatus}
 * Returns {ok, value, errors: [field names], flags: [field names]}.
 */
export function validateJob(input, opts) {
  const { site, today, provided = new Set(Object.keys(input || {})), allowStatus = ['draft', 'live'] } = opts;
  const errors = [];
  const out = {};
  if (!input || typeof input !== 'object' || Array.isArray(input)) return { ok: false, errors: ['body'], flags: [] };
  if (!SITES.includes(site)) return { ok: false, errors: ['site'], flags: [] };

  const text = (k, o) => {
    const r = cleanText(input[k], o);
    if (!r.ok) errors.push(k);
    else out[k] = r.value;
  };
  text('title', { min: 3, max: 160 });
  text('employer', { min: 1, max: 200 });
  text('location', { min: 1, max: 120 });
  text('region', { max: 80, required: false });
  text('job_type', { max: 40, required: false });
  text('description', { min: 20, max: 20000, multiline: true });
  text('summary', { max: 300, required: false });
  text('sal_text', { max: 120, required: false });

  for (const k of ['sal_min', 'sal_max']) {
    const r = intOrNull(input[k]);
    if (!r.ok) errors.push(k);
    else out[k] = r.value;
  }
  if (out.sal_min != null && out.sal_max != null && out.sal_min > out.sal_max) errors.push('sal_max');

  const cur = input.currency ?? null;
  if (cur === null || cur === '') out.currency = site === 'uk' ? 'GBP' : 'EUR';
  else if (CURRENCIES.includes(cur)) out.currency = cur;
  else errors.push('currency');

  const per = input.period ?? null;
  if (per === null || per === '') out.period = null;
  else if (PERIODS.includes(per)) out.period = per;
  else errors.push('period');

  const sectors = input.sectors ?? [];
  if (!Array.isArray(sectors) || sectors.length > 10) errors.push('sectors');
  else {
    const clean = [];
    for (const s of sectors) {
      const r = cleanText(s, { min: 1, max: 60 });
      if (!r.ok) {
        errors.push('sectors');
        break;
      }
      clean.push(r.value);
    }
    out.sectors = clean;
  }

  const mode = input.apply_mode ?? 'inbox';
  if (!APPLY_MODES.includes(mode)) errors.push('apply_mode');
  out.apply_mode = mode;

  const ae = input.apply_email ?? null;
  if (ae === null || ae === '') out.apply_email = null;
  else if (isValidEmail(ae)) out.apply_email = normEmail(ae);
  else errors.push('apply_email');

  const au = input.apply_url ?? null;
  if (au === null || au === '') out.apply_url = null;
  else {
    const r = validHttpsUrl(au);
    if (!r.ok) errors.push('apply_url');
    else out.apply_url = r.value;
  }
  if (mode === 'url' && !out.apply_url && !errors.includes('apply_url')) errors.push('apply_url');

  const closing = input.closing ?? null;
  if (closing === null || closing === '') out.closing = null;
  else if (!isIsoDate(String(closing).slice(0, 10))) errors.push('closing');
  else {
    out.closing = String(closing).slice(0, 10);
    // Bounded gate: a newly set closing date is today..today+365. An unchanged one is kept.
    if (provided.has('closing') && today) {
      const max = new Date(`${today}T00:00:00Z`);
      max.setUTCDate(max.getUTCDate() + 365);
      if (out.closing < today || out.closing > max.toISOString().slice(0, 10)) errors.push('closing');
    }
  }

  const status = input.status ?? 'draft';
  if (!allowStatus.includes(status)) errors.push('status');
  out.status = status;

  return { ok: errors.length === 0, value: out, errors: [...new Set(errors)], flags: injectionFlags(input, FREE_TEXT_FIELDS) };
}

/** Validate the text fields of a public application. Returns {ok, value, errors, flags}. */
export function validateApplication(fields) {
  const errors = [];
  const out = {};
  const name = cleanText(fields.name, { min: 1, max: 120, header: true });
  if (!name.ok) errors.push('name');
  else out.name = name.value;

  if (!isValidEmail(fields.email)) errors.push('email');
  else out.email = normEmail(fields.email);

  const phone = cleanText(fields.phone, { max: 40, required: false, header: true });
  if (!phone.ok || (phone.value && !PHONE_RE.test(phone.value))) errors.push('phone');
  else out.phone = phone.value;

  const note = cleanText(fields.cover_note, { max: 5000, multiline: true, required: false });
  if (!note.ok) errors.push('cover_note');
  else out.cover_note = note.value;

  if (fields.consent !== 'yes') errors.push('consent');

  return { ok: errors.length === 0, value: out, errors, flags: injectionFlags(fields, ['name', 'cover_note']) };
}

// CV sniffing by magic bytes, never by extension or client-supplied type.
export function sniffCv(bytes) {
  const b = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
  if (b.length >= 5 && b[0] === 0x25 && b[1] === 0x50 && b[2] === 0x44 && b[3] === 0x46 && b[4] === 0x2d) {
    return { ext: 'pdf', type: 'application/pdf' };
  }
  const ole = [0xd0, 0xcf, 0x11, 0xe0, 0xa1, 0xb1, 0x1a, 0xe1];
  if (b.length >= 8 && ole.every((v, i) => b[i] === v)) return { ext: 'doc', type: 'application/msword' };
  if (b.length >= 4 && b[0] === 0x50 && b[1] === 0x4b && b[2] === 0x03 && b[3] === 0x04) {
    // A .docx is a zip whose entries live under word/; any other zip is refused.
    const needle = [0x77, 0x6f, 0x72, 0x64, 0x2f]; // "word/"
    const limit = Math.min(b.length - needle.length, 2_000_000);
    for (let i = 30; i <= limit; i++) {
      let hit = true;
      for (let j = 0; j < needle.length; j++) {
        if (b[i + j] !== needle[j]) {
          hit = false;
          break;
        }
      }
      if (hit) return { ext: 'docx', type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' };
    }
    return null;
  }
  return null;
}

export function cvKey(site, date, uuid, ext) {
  if (!SITES.includes(site) || !['pdf', 'doc', 'docx'].includes(ext)) throw new Error('cv_key_args');
  const yyyy = String(date.getUTCFullYear());
  const mm = String(date.getUTCMonth() + 1).padStart(2, '0');
  return `cv/${site}/${yyyy}/${mm}/${uuid}.${ext}`;
}

/** Parse the form render timestamp (ms or s since epoch). Bounded: >= minAgeMs and <= maxAgeMs old. */
export function checkRenderTs(raw, nowMs, minAgeMs = 3000, maxAgeMs = 24 * 3600 * 1000) {
  if (typeof raw !== 'string' || !/^\d{9,13}$/.test(raw)) return { ok: false, error: 'invalid_ts' };
  let ts = Number(raw);
  if (ts < 1e12) ts *= 1000;
  const age = nowMs - ts;
  if (age < minAgeMs) return { ok: false, error: 'too_fast' };
  if (age > maxAgeMs) return { ok: false, error: 'form_expired' };
  return { ok: true };
}
