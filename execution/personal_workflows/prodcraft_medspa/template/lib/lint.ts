// lib/lint.ts
// Content linter (PROJECT_SPEC.md §7, non-negotiable): the build must fail if any
// rendered string contains a forbidden medical-claim term, or a "$" price pattern.
// Called from app/page.tsx against every user-facing string derived from business.json.

const FORBIDDEN_TERMS = [
  'cure',
  'guaranteed results',
  'permanent',
  'fda approved',
  'fda-approved',
  'safe for everyone',
  'no side effects',
  'clinically proven',
  'before/after',
  'before & after',
  'before and after',
];

const PRICE_PATTERN = /\$\s?\d/;

export interface LintViolation {
  term: string;
  context: string;
}

/**
 * Scans a single string for forbidden terms / price patterns. Case-insensitive.
 */
export function lintString(value: string): LintViolation[] {
  const violations: LintViolation[] = [];
  const lower = value.toLowerCase();

  for (const term of FORBIDDEN_TERMS) {
    if (lower.includes(term)) {
      violations.push({ term, context: value });
    }
  }

  if (PRICE_PATTERN.test(value)) {
    violations.push({ term: '$ price pattern', context: value });
  }

  return violations;
}

/**
 * Scans an array of strings, throwing a single clear Error listing every
 * violation found (field label + violated term + offending string) if any exist.
 */
export function lintStrings(fields: Array<{ label: string; value: string }>): void {
  const allViolations: string[] = [];

  for (const { label, value } of fields) {
    const violations = lintString(value);
    for (const v of violations) {
      allViolations.push(`  - ${label}: forbidden term "${v.term}" in "${v.context}"`);
    }
  }

  if (allViolations.length > 0) {
    throw new Error(
      `Content lint failed (${allViolations.length} violation${allViolations.length === 1 ? '' : 's'}):\n` +
        allViolations.join('\n')
    );
  }
}

export { FORBIDDEN_TERMS, PRICE_PATTERN };
