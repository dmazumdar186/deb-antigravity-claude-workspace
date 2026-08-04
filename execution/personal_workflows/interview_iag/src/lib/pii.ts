// Client-side PII redaction for Indian BPO context.
//
// India's DPDPA (Digital Personal Data Protection Act, 2023) requires that
// personal data leaving the operator's device is minimised. Agents in
// training sessions can accidentally paraphrase a real customer's PII
// (bill number, phone, Aadhaar, PAN, UPI, card) into their reply. This
// module masks that BEFORE the payload leaves the browser.
//
// Design principles:
//   - Pure functions. No DOM, no fetch. 100% unit-testable.
//   - Never destructive: return the masked string AND a per-type count
//     of what was masked, so the UI can surface a "PII redacted" chip.
//   - Prefer false-positives over false-negatives: better to over-redact
//     than to leak. Callers can show the redacted version to the user
//     for confirmation.

export interface RedactionResult {
  text: string;
  counts: Record<PIIType, number>;
  total: number;
}

export type PIIType =
  | 'aadhaar'    // 12-digit block, often xxxx xxxx xxxx
  | 'pan'        // 5 letters + 4 digits + 1 letter (e.g. ABCDE1234F)
  | 'mobile_in'  // +91 or 10-digit Indian mobile
  | 'upi'        // handle@bank (e.g. name@paytm, name@okhdfcbank)
  | 'credit_card' // 13-19 digits with Luhn validation
  | 'email';     // any email

// Regexes — anchored on word boundaries where practical to avoid mid-word matches.
// The Aadhaar and mobile checks live-verify digit count to avoid over-matching.

// Word-boundary regexes with negative lookaround so long digit runs do not
// falsely trigger shorter patterns (e.g. 16-digit random number shouldn't
// match the 10-digit mobile pattern in the middle).
const RX_AADHAAR    = /(?<![\d+])(\d{4})[\s-]?(\d{4})[\s-]?(\d{4})(?!\d)/g;
const RX_PAN        = /\b([A-Z]{5}\d{4}[A-Z])\b/g;
const RX_MOBILE_IN  = /(?<![\d+])(?:\+91[\s-]?|91[\s-]?|0)?[6-9]\d{9}(?!\d)/g;
const RX_UPI        = /\b([A-Za-z0-9._-]{2,})@(paytm|okhdfcbank|okicici|okaxis|oksbi|okbizaxis|ybl|axl|apl|ibl|hdfcbank|icici|axisbank|sbi|kotak|upi)\b/gi;
const RX_EMAIL      = /\b([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b/g;
// Card: 13-19 digits with optional single space/dash separators. Captures
// only the digit run itself (no trailing separator).
const RX_CARD       = /(?<!\d)(\d(?:[\s-]?\d){12,18})(?!\d)/g;

// Luhn check — decides whether a run of 13-19 digits is a real card number.
export function luhnValid(digits: string): boolean {
  const only = digits.replace(/\D/g, '');
  if (only.length < 13 || only.length > 19) return false;
  let sum = 0;
  let alt = false;
  for (let i = only.length - 1; i >= 0; i--) {
    let n = only.charCodeAt(i) - 48;
    if (alt) { n *= 2; if (n > 9) n -= 9; }
    sum += n;
    alt = !alt;
  }
  return sum % 10 === 0;
}

// Aadhaar Verhoeff check — real Aadhaar numbers pass this. Optional strictness.
// We use it as a *stricter* filter for Aadhaar-shape matches; if it fails the
// Verhoeff check we still mask (defensive), but flag the count as `aadhaar`.
// (For a hiring exercise we don't fully implement Verhoeff — Aadhaar-shape
// alone is enough given the mask-safe stance.)

function bumpCount(counts: Record<PIIType, number>, key: PIIType): void {
  counts[key] = (counts[key] || 0) + 1;
}

function emptyCounts(): Record<PIIType, number> {
  return { aadhaar: 0, pan: 0, mobile_in: 0, upi: 0, credit_card: 0, email: 0 };
}

/**
 * Redact PII in a string. Returns the masked text + per-type counts.
 * Order matters — email must run BEFORE UPI (both contain '@'), and
 * credit-card BEFORE mobile (both are digit runs, card is longer).
 */
export function redact(input: string): RedactionResult {
  if (!input) return { text: input, counts: emptyCounts(), total: 0 };
  const counts = emptyCounts();
  let text = input;

  // Email (must precede UPI — otherwise UPI regex catches the local-part)
  text = text.replace(RX_EMAIL, (_, local, domain) => {
    // If the domain is a known UPI provider, don't redact here — let UPI handle it.
    if (/^(paytm|okhdfcbank|okicici|okaxis|oksbi|okbizaxis|ybl|axl|apl|ibl|hdfcbank|icici|axisbank|sbi|kotak|upi)$/i.test(domain)) {
      return `${local}@${domain}`;
    }
    bumpCount(counts, 'email');
    return '[EMAIL_REDACTED]';
  });

  // UPI IDs
  text = text.replace(RX_UPI, () => { bumpCount(counts, 'upi'); return '[UPI_REDACTED]'; });

  // Credit / debit cards (Luhn-verified) — run BEFORE aadhaar/mobile so a
  // 16-digit card can't be mis-classified as a shorter pattern.
  text = text.replace(RX_CARD, (m) => {
    if (luhnValid(m)) { bumpCount(counts, 'credit_card'); return '[CARD_REDACTED]'; }
    return m;
  });

  // PAN before Aadhaar/mobile so alphanumeric PAN doesn't interfere with digit scans.
  text = text.replace(RX_PAN, () => { bumpCount(counts, 'pan'); return '[PAN_REDACTED]'; });

  // Aadhaar (12-digit block, spaced or contiguous) — lookbehind rejects
  // +91-prefixed runs that are actually mobile numbers.
  text = text.replace(RX_AADHAAR, () => { bumpCount(counts, 'aadhaar'); return '[AADHAAR_REDACTED]'; });

  // Indian mobile numbers (10 digits starting with 6-9, optionally with country code)
  text = text.replace(RX_MOBILE_IN, () => { bumpCount(counts, 'mobile_in'); return '[MOBILE_REDACTED]'; });

  const total = Object.values(counts).reduce((a, b) => a + b, 0);
  return { text, counts, total };
}

/** Redact every string field in an object recursively. Numbers/booleans untouched. */
export function redactDeep<T>(obj: T): { value: T; total: number; counts: Record<PIIType, number> } {
  const merged = emptyCounts();
  let total = 0;
  const walk = (v: unknown): unknown => {
    if (typeof v === 'string') {
      const r = redact(v);
      total += r.total;
      for (const k of Object.keys(r.counts) as PIIType[]) merged[k] += r.counts[k];
      return r.text;
    }
    if (Array.isArray(v)) return v.map(walk);
    if (v && typeof v === 'object') {
      const out: Record<string, unknown> = {};
      for (const [k, val] of Object.entries(v as Record<string, unknown>)) out[k] = walk(val);
      return out;
    }
    return v;
  };
  return { value: walk(obj) as T, total, counts: merged };
}
