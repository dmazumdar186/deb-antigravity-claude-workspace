// Pure-logic unit tests. No network, no KV, no API keys needed.
// Run with: npm test  (which calls `node --experimental-strip-types --test`).
//
// These tests catch regressions in:
//   - JSON extraction from LLM responses (code fences, prose, truncation)
//   - CVSpec schema validator (acceptance + rejection)
//   - Login-wall detection
//   - JD-body trim logic
//   - Prompt fingerprint match against source file (no drift)

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { extractJsonObject } from "../src/anthropic.ts";
import { isCVSpec } from "../src/cv_schema.ts";
import { detectLoginWall, trimToJdBody } from "../src/firecrawl.ts";
import { composeProfileContext } from "../src/profile.ts";
import { PROMPT_FINGERPRINT, SCHEMA_FINGERPRINT, SYSTEM_PROMPT, RESPONSE_SCHEMA } from "../src/embedded.generated.ts";
import { detectLocale, validateCvSpecLanguage, harvestFreeTextFields, LANG_VALIDATOR_FINGERPRINT } from "../src/lang_validator.ts";

const here = dirname(fileURLToPath(import.meta.url));

// ---------------------------------------------------------------------------
// extractJsonObject — robust JSON extraction
// ---------------------------------------------------------------------------

test("extractJsonObject: plain JSON object", () => {
  const got = extractJsonObject('{"a":1,"b":"two"}') as { a: number; b: string };
  assert.equal(got.a, 1);
  assert.equal(got.b, "two");
});

test("extractJsonObject: markdown code fence wrapper", () => {
  const raw = '```json\n{"a":1}\n```';
  const got = extractJsonObject(raw) as { a: number };
  assert.equal(got.a, 1);
});

test("extractJsonObject: prose before and after", () => {
  const raw = 'Here is the result: {"a":1, "b":[1,2,3]} — let me know if you need more.';
  const got = extractJsonObject(raw) as { a: number; b: number[] };
  assert.equal(got.a, 1);
  assert.deepEqual(got.b, [1, 2, 3]);
});

test("extractJsonObject: nested objects don't confuse brace finder", () => {
  const raw = '{"outer": {"inner": {"deep": true}}}';
  const got = extractJsonObject(raw) as { outer: { inner: { deep: boolean } } };
  assert.equal(got.outer.inner.deep, true);
});

test("extractJsonObject: no braces throws", () => {
  assert.throws(() => extractJsonObject("plain text no braces"), /anthropic_no_json_braces/);
});

test("extractJsonObject: malformed JSON between braces throws diagnostic", () => {
  // Has braces but invalid syntax inside.
  assert.throws(() => extractJsonObject('{"key": invalid_value}'), /anthropic_invalid_json/);
});

// ---------------------------------------------------------------------------
// isCVSpec — schema validator
// ---------------------------------------------------------------------------

const validCvSpec = {
  language_detected: "en",
  ats_score: 87,
  name: "Jane Doe",
  title: "Senior PM",
  contact: { email: "j@d.com", phone: "+1", location: "Paris" },
  summary: "Strong PM",
  summary_kpis: "10y PM | shipped X",
  experience: [{ role: "PM", company_line: "X", bullets: ["led X"], is_oneliner: false }],
  skills: [{ category: "Product", value: "PRDs, OKRs" }],
  education: [{ degree: "MBA", institution_line: "HEC" }],
  languages: ["English"],
  recommendations: ["Add X", "Add Y", "Add Z", "Add W", "Add V"],
};

test("isCVSpec: valid spec passes", () => {
  assert.equal(isCVSpec(validCvSpec), true);
});

test("isCVSpec: null fails", () => {
  assert.equal(isCVSpec(null), false);
});

test("isCVSpec: missing language_detected fails", () => {
  const x = { ...validCvSpec } as Record<string, unknown>;
  delete x.language_detected;
  assert.equal(isCVSpec(x), false);
});

test("isCVSpec: ats_score wrong type fails", () => {
  assert.equal(isCVSpec({ ...validCvSpec, ats_score: "87" }), false);
});

test("isCVSpec: experience not array fails", () => {
  assert.equal(isCVSpec({ ...validCvSpec, experience: "not an array" }), false);
});

// ---------------------------------------------------------------------------
// detectLoginWall — keyword detection
// ---------------------------------------------------------------------------

test("detectLoginWall: clean content returns null", () => {
  assert.equal(detectLoginWall("This is a normal job description for a Senior PM role."), null);
});

test("detectLoginWall: detects 'sign in to view'", () => {
  assert.equal(
    detectLoginWall("Please sign in to view the full job posting"),
    "sign in to view",
  );
});

test("detectLoginWall: case-insensitive", () => {
  assert.equal(detectLoginWall("JOIN LINKEDIN to continue"), "join linkedin");
});

test("detectLoginWall: detects mid-content", () => {
  assert.equal(
    detectLoginWall("Some intro... join to apply ...some more"),
    "join to apply",
  );
});

// ---------------------------------------------------------------------------
// trimToJdBody — chrome stripping + cap
// ---------------------------------------------------------------------------

test("trimToJdBody: keeps content from first H2", () => {
  const md = "cookie consent dialog blah blah\n## Senior PM Role\n\nResponsibilities...";
  const out = trimToJdBody(md);
  assert.match(out, /Senior PM Role/);
  assert.ok(!out.includes("cookie consent"), "should strip pre-H2 chrome");
});

test("trimToJdBody: returns input when no H2 found", () => {
  const md = "Plain content with no H2 heading at all.";
  assert.equal(trimToJdBody(md), md);
});

test("trimToJdBody: caps at 3500 chars", () => {
  const md = "## Title\n" + "x".repeat(10_000);
  const out = trimToJdBody(md);
  assert.ok(out.length <= 3500, `got ${out.length}`);
});

// ---------------------------------------------------------------------------
// Prompt fingerprint integrity — generated file must match source file
// ---------------------------------------------------------------------------

function fnv1a(s: string): string {
  let h = 0x811c9dc5;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = (h + ((h << 1) + (h << 4) + (h << 7) + (h << 8) + (h << 24))) >>> 0;
  }
  return h.toString(16).padStart(8, "0");
}

// Normalize CRLF -> LF before fingerprinting so Windows autocrlf checkouts
// produce the same fingerprint as the embed script does.
function readLF(p: string): string {
  return readFileSync(p, "utf8").replace(/\r\n/g, "\n");
}

test("embedded prompt fingerprint matches source file (no drift)", () => {
  const sourcePath = resolve(here, "..", "..", "prompts", "system_prompt.md");
  const live = fnv1a(readLF(sourcePath));
  assert.equal(
    PROMPT_FINGERPRINT,
    live,
    `PROMPT drift detected. Source file fingerprint ${live} but embedded ${PROMPT_FINGERPRINT}. Re-run scripts/embed-prompts.mjs.`,
  );
});

test("embedded schema fingerprint matches source file (no drift)", () => {
  const sourcePath = resolve(here, "..", "..", "prompts", "cv_response_schema.json");
  const live = fnv1a(readLF(sourcePath));
  assert.equal(
    SCHEMA_FINGERPRINT,
    live,
    `SCHEMA drift detected. Source file fingerprint ${live} but embedded ${SCHEMA_FINGERPRINT}. Re-run scripts/embed-prompts.mjs.`,
  );
});

test("embedded SYSTEM_PROMPT contains language rule at top", () => {
  // Language rule should appear before "Hard constraints" — fail-fast for prompt regressions.
  const langIdx = SYSTEM_PROMPT.indexOf("Language rule");
  const hardIdx = SYSTEM_PROMPT.indexOf("Hard constraints");
  assert.ok(langIdx > 0, "Language rule section missing");
  assert.ok(hardIdx > 0, "Hard constraints section missing");
  assert.ok(langIdx < hardIdx, "Language rule should come before Hard constraints");
});

test("embedded SCHEMA exports language_detected enum with 4 langs", () => {
  const schema = RESPONSE_SCHEMA as { properties: { language_detected: { enum: string[] } } };
  assert.deepEqual(schema.properties.language_detected.enum, ["en", "fr", "es", "de"]);
});

test("embedded SYSTEM_PROMPT mentions Current activity block", () => {
  assert.ok(
    SYSTEM_PROMPT.includes("Current activity"),
    "Profile-enrichment instructions missing from prompt",
  );
});

// ---------------------------------------------------------------------------
// composeProfileContext — section assembly
// ---------------------------------------------------------------------------

test("composeProfileContext: empty sections returns empty string", () => {
  assert.equal(composeProfileContext([], "2026-06-14"), "");
  assert.equal(composeProfileContext(["", "  "], "2026-06-14"), "");
});

test("composeProfileContext: non-empty section gets wrapped with header", () => {
  const out = composeProfileContext(["Recent GitHub repos:\n- foo"], "2026-06-14");
  assert.match(out, /## Current activity/);
  assert.match(out, /2026-06-14/);
  assert.match(out, /Recent GitHub repos/);
});

test("composeProfileContext: filters empty sections, keeps non-empty", () => {
  const out = composeProfileContext(["", "GitHub section", "  ", "YouTube section"], "2026-06-14");
  assert.match(out, /GitHub section/);
  assert.match(out, /YouTube section/);
  // Sections joined with blank line.
  assert.match(out, /GitHub section\n\nYouTube section/);
});

// ---------------------------------------------------------------------------
// lang_validator — detectLocale
// ---------------------------------------------------------------------------

test("detectLocale: clear English text returns en", () => {
  assert.equal(
    detectLocale("Managed a team of engineers and delivered the project on time with strong results"),
    "en",
  );
});

test("detectLocale: clear French text returns fr", () => {
  assert.equal(
    detectLocale("Géré une équipe d'ingénieurs et livré les projets dans les délais avec des résultats solides"),
    "fr",
  );
});

test("detectLocale: short string below threshold returns null", () => {
  // 3 words — below the MIN_WORDS=4 threshold, should return null (skip, not fail).
  assert.equal(detectLocale("Node.js React"), null);
});

test("detectLocale: proper nouns / ambiguous returns null", () => {
  // All-caps acronyms and tech terms — no stopword hits, ambiguous.
  assert.equal(detectLocale("AWS GCP Azure Kubernetes Docker CI/CD"), null);
});

// ---------------------------------------------------------------------------
// lang_validator — validateCvSpecLanguage
// ---------------------------------------------------------------------------

// Base fixture — fully French.
const frenchCvSpec = {
  language_detected: "fr" as const,
  ats_score: 85,
  name: "Jean Dupont",
  title: "Chef de Produit Senior",
  contact: { email: "j@d.com", phone: "+33", location: "Paris" },
  summary: "Chef de produit expérimenté avec plus de dix ans dans les entreprises technologiques en France et à l'international",
  summary_kpis: "10 ans PM | 5 produits lancés | équipes de 20 personnes",
  experience: [
    {
      role: "Responsable Produit",
      company_line: "Acme Corp",
      bullets: [
        "Piloté la roadmap produit pour les clients enterprise avec des résultats mesurables",
        "Coordonné les équipes techniques et design pour livrer les fonctionnalités dans les délais",
      ],
      is_oneliner: false,
    },
  ],
  skills: [{ category: "Produit", value: "PRDs, OKRs, Roadmaps" }],
  education: [{ degree: "MBA", institution_line: "HEC Paris" }],
  languages: ["Français", "Anglais"],
  recommendations: [
    "Ajouter des métriques quantifiables dans chaque section de l'expérience professionnelle",
    "Mettre en avant les résultats commerciaux plutôt que les activités réalisées",
  ],
};

test("validateCvSpecLanguage: all-French spec passes", () => {
  const result = validateCvSpecLanguage(frenchCvSpec, "fr");
  assert.equal(result.ok, true, `mismatches: ${JSON.stringify(result.mismatches)}`);
  assert.equal(result.mismatches.length, 0);
});

// English spec validated as English must pass.
const englishCvSpec = {
  ...frenchCvSpec,
  language_detected: "en" as const,
  summary: "Experienced product manager with over ten years working in technology companies in the United States and United Kingdom",
  summary_kpis: "10y PM | launched 5 products | led teams of 20 engineers",
  experience: [
    {
      role: "Senior Product Manager",
      company_line: "Acme Corp",
      bullets: [
        "Led the product roadmap for enterprise clients and delivered measurable revenue results",
        "Coordinated engineering and design teams to ship features on time and within budget",
      ],
      is_oneliner: false,
    },
  ],
  recommendations: [
    "Add quantifiable metrics to each experience section to strengthen the impact statements",
    "Focus more on business outcomes rather than listing the activities completed",
  ],
};

test("validateCvSpecLanguage: all-English spec passes", () => {
  const result = validateCvSpecLanguage(englishCvSpec, "en");
  assert.equal(result.ok, true, `mismatches: ${JSON.stringify(result.mismatches)}`);
});

// French spec where bullets are in English — the exact Exhibit A failure mode.
const mixedFrenchSpecWithEnglishBullets = {
  ...frenchCvSpec,
  experience: [
    {
      role: "Responsable Produit",
      company_line: "Acme Corp",
      bullets: [
        "Led the product roadmap for enterprise clients and delivered measurable revenue results",
        "Coordinated engineering and design teams to ship features on time and within budget",
      ],
      is_oneliner: false,
    },
  ],
};

test("validateCvSpecLanguage: fr spec with English bullets fails", () => {
  const result = validateCvSpecLanguage(mixedFrenchSpecWithEnglishBullets, "fr");
  assert.equal(result.ok, false, "expected validation to fail on English bullets");
  assert.ok(result.mismatches.length > 0, "expected at least one mismatch");
  // At least one mismatch should point to an experience bullet.
  const bulletMismatches = result.mismatches.filter((m) => m.field.includes("bullets"));
  assert.ok(bulletMismatches.length > 0, `expected bullet mismatches, got: ${JSON.stringify(result.mismatches)}`);
});

// French spec with English recommendations — another common failure mode.
const frenchSpecWithEnglishRecs = {
  ...frenchCvSpec,
  recommendations: [
    "Add quantifiable metrics to each experience section to strengthen the impact statements",
    "Focus more on business outcomes rather than listing the activities completed",
  ],
};

test("validateCvSpecLanguage: fr spec with English recommendations fails", () => {
  const result = validateCvSpecLanguage(frenchSpecWithEnglishRecs, "fr");
  assert.equal(result.ok, false, "expected validation to fail on English recommendations");
  const recMismatches = result.mismatches.filter((m) => m.field.includes("recommendations"));
  assert.ok(recMismatches.length > 0, `expected recommendation mismatches, got: ${JSON.stringify(result.mismatches)}`);
});

test("harvestFreeTextFields: skills are excluded from validation", () => {
  // Skills are language-neutral tech terms — they must not appear in the harvested segments.
  const fields = harvestFreeTextFields(frenchCvSpec);
  const skillFields = fields.filter((f) => f.field.startsWith("skills"));
  assert.equal(skillFields.length, 0, "skills fields should be excluded from language validation");
});

test("LANG_VALIDATOR_FINGERPRINT is non-empty string", () => {
  assert.ok(typeof LANG_VALIDATOR_FINGERPRINT === "string" && LANG_VALIDATOR_FINGERPRINT.length > 0);
});
