// Per-field language validator for CVSpec.
//
// Approach: word-frequency heuristics over a curated stopword list per locale.
// No external dependency — deterministic, network-free, runs at the edge.
//
// Why heuristics instead of franc-min or langdetect:
//   - franc-min is Node-only (trigram tables are too large for Workers bundle).
//   - The domain is narrow: we know the expected language from request.language_detected
//     and just need to confirm each free-text field isn't accidentally in another locale.
//   - Stopwords are the most reliable signal for short strings (1–3 sentences, bullets).
//
// Coverage: en, fr, es, de — matches the Language type in cv_schema.ts.
// Skills are language-neutral (tech terms, tool names) and intentionally excluded.

import type { CVSpec } from "./cv_schema.js";

// Fingerprint so /api/health can confirm the validator version.
export const LANG_VALIDATOR_FINGERPRINT = "v1.0-heuristic-stopword";

// ---------------------------------------------------------------------------
// Stopword tables — ~25 high-frequency, low-ambiguity function words per locale.
// ---------------------------------------------------------------------------

const STOPWORDS: Record<string, Set<string>> = {
  en: new Set([
    "the", "and", "for", "with", "that", "this", "from", "have", "has",
    "was", "are", "were", "been", "will", "their", "they", "which", "not",
    "but", "our", "more", "when", "also", "than", "into", "its", "all",
  ]),
  fr: new Set([
    "les", "des", "une", "pour", "dans", "avec", "sur", "par", "cette",
    "qui", "que", "est", "son", "ses", "leur", "leurs", "aux", "entre",
    "ainsi", "lors", "tout", "elle", "nous", "vous", "ils", "afin", "dont",
  ]),
  es: new Set([
    "los", "las", "una", "para", "con", "que", "del", "los", "sus", "por",
    "esta", "este", "son", "han", "fue", "más", "también", "entre", "como",
    "donde", "cuando", "pero", "sin", "ser", "desde", "hasta", "durante",
  ]),
  de: new Set([
    "die", "der", "das", "und", "für", "mit", "ist", "auf", "den", "ein",
    "eine", "sind", "hat", "haben", "wurde", "bei", "als", "auch", "nach",
    "oder", "wird", "nicht", "durch", "mehr", "wie", "von", "aus", "dabei",
  ]),
};

// ---------------------------------------------------------------------------
// Core detection
// ---------------------------------------------------------------------------

/**
 * Detect the most likely locale for a short string using stopword frequency.
 * Returns the winning locale code or null if the text is too short / ambiguous.
 *
 * Min words: 4 — shorter strings (single tech terms, proper nouns) return null,
 * meaning "skip validation" rather than "wrong language." This avoids false
 * positives on company names, job titles with mixed proper nouns, etc.
 */
export function detectLocale(text: string): string | null {
  // Tokenise: lowercase, alpha-only tokens (strip punctuation, numbers).
  const words = text
    .toLowerCase()
    .split(/[\s\-–—,.;:!?()[\]{}'"]+/)
    .filter((w) => /^[a-záéíóúàâèêîôùûäëïöüçñß]+$/.test(w) && w.length > 1);

  if (words.length < 4) return null; // too short to be reliable

  const scores: Record<string, number> = { en: 0, fr: 0, es: 0, de: 0 };
  for (const word of words) {
    for (const [lang, stops] of Object.entries(STOPWORDS)) {
      if (stops.has(word)) scores[lang]++;
    }
  }

  // Winner must clear a minimum hit count to avoid noise.
  const MIN_HITS = 2;
  const entries = Object.entries(scores).sort((a, b) => b[1] - a[1]);
  if (entries[0][1] < MIN_HITS) return null; // low signal — skip
  if (entries[0][1] === entries[1][1]) return null; // tie — ambiguous

  return entries[0][0];
}

// ---------------------------------------------------------------------------
// CVSpec field harvester
// ---------------------------------------------------------------------------

/**
 * Collect all free-text fields from a CVSpec into named segments for validation.
 *
 * Excluded: skills (language-neutral — tech terms, tool names, frameworks),
 * contact fields, name, certifications, languages array (proper nouns / codes).
 *
 * Included: summary, summary_kpis, experience bullets, experience roles,
 * projects, recommendations.
 */
export function harvestFreeTextFields(spec: CVSpec): { field: string; text: string }[] {
  const segments: { field: string; text: string }[] = [];

  if (spec.summary) segments.push({ field: "summary", text: spec.summary });
  if (spec.summary_kpis) segments.push({ field: "summary_kpis", text: spec.summary_kpis });

  for (let i = 0; i < spec.experience.length; i++) {
    const exp = spec.experience[i];
    // Role / company_line may be proper nouns — include role (job title) but not company.
    if (exp.role) segments.push({ field: `experience[${i}].role`, text: exp.role });
    for (let j = 0; j < exp.bullets.length; j++) {
      const b = exp.bullets[j];
      if (b) segments.push({ field: `experience[${i}].bullets[${j}]`, text: b });
    }
  }

  if (spec.projects) {
    for (let i = 0; i < spec.projects.length; i++) {
      if (spec.projects[i]) segments.push({ field: `projects[${i}]`, text: spec.projects[i] });
    }
  }

  for (let i = 0; i < spec.recommendations.length; i++) {
    if (spec.recommendations[i]) {
      segments.push({ field: `recommendations[${i}]`, text: spec.recommendations[i] });
    }
  }

  return segments;
}

// ---------------------------------------------------------------------------
// Main validator
// ---------------------------------------------------------------------------

export interface LangMismatch {
  field: string;
  detected: string;
  expected: string;
}

export interface LangValidationResult {
  ok: boolean;
  mismatches: LangMismatch[];
  /** Segments where detection was skipped (too short / ambiguous). */
  skipped: number;
  /** Total segments checked. */
  checked: number;
}

/**
 * Validate that all free-text CVSpec fields are written in `expectedLang`.
 *
 * A field is a mismatch only if detectLocale returns a different (non-null) locale.
 * Fields where detectLocale returns null (ambiguous / too short) are counted as skipped,
 * not as failures — this avoids false positives on short bullets like "Node.js, React".
 */
export function validateCvSpecLanguage(spec: CVSpec, expectedLang: string): LangValidationResult {
  const segments = harvestFreeTextFields(spec);
  const mismatches: LangMismatch[] = [];
  let skipped = 0;

  for (const { field, text } of segments) {
    const detected = detectLocale(text);
    if (detected === null) {
      skipped++;
      continue;
    }
    if (detected !== expectedLang) {
      mismatches.push({ field, detected, expected: expectedLang });
    }
  }

  return {
    ok: mismatches.length === 0,
    mismatches,
    skipped,
    checked: segments.length,
  };
}
