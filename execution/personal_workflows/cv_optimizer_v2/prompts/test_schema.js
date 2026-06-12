/**
 * test_schema.js — Phase 1 HARD GATE
 *
 * Posts a dummy CV + JD to Gemini Flash using cv_response_schema.json as
 * responseSchema. Asserts: HTTP 200, JSON parses, all required CVSpec fields
 * are present with correct types.
 *
 * Run from cv_optimizer_v2/: node prompts/test_schema.js
 * Exit 0 = PASS, Exit 1 = FAIL.
 *
 * No npm dependencies. Uses Node 18+ built-in fetch + fs.
 */

import { readFileSync } from "fs";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT_DIR = resolve(__dirname, "../../../.."); // workspace root (4 up from prompts/)

// ── Load GEMINI_API_KEY ─────────────────────────────────────────────────────────
function loadEnv(envPath) {
  try {
    const raw = readFileSync(envPath, "utf-8");
    const vars = {};
    for (const line of raw.split(/\r?\n/)) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith("#")) continue;
      const eqIdx = trimmed.indexOf("=");
      if (eqIdx < 0) continue;
      const key = trimmed.slice(0, eqIdx).trim();
      // Strip surrounding quotes if present
      let val = trimmed.slice(eqIdx + 1).trim();
      if ((val.startsWith('"') && val.endsWith('"')) ||
          (val.startsWith("'") && val.endsWith("'"))) {
        val = val.slice(1, -1);
      }
      vars[key] = val;
    }
    return vars;
  } catch {
    return {};
  }
}

const envVars = loadEnv(resolve(ROOT_DIR, ".env"));
const GEMINI_API_KEY = process.env.GEMINI_API_KEY || envVars.GEMINI_API_KEY;

if (!GEMINI_API_KEY) {
  console.error("FAIL: GEMINI_API_KEY not found in .env or environment. Cannot proceed.");
  process.exit(1);
}

// ── Load schema + prompt ────────────────────────────────────────────────────────
const schemaPath = resolve(__dirname, "cv_response_schema.json");
const promptPath = resolve(__dirname, "system_prompt.md");

let responseSchema, systemPrompt;
try {
  responseSchema = JSON.parse(readFileSync(schemaPath, "utf-8"));
} catch (e) {
  console.error(`FAIL: Could not parse cv_response_schema.json — ${e.message}`);
  process.exit(1);
}
try {
  systemPrompt = readFileSync(promptPath, "utf-8");
} catch (e) {
  console.error(`FAIL: Could not read system_prompt.md — ${e.message}`);
  process.exit(1);
}

// ── Dummy CV + JD ───────────────────────────────────────────────────────────────
const DUMMY_CV = `
Jane Doe
Senior Product Manager
jane.doe@example.com | +33 6 12 34 56 78 | Paris, France
linkedin.com/in/janedoe | github.com/janedoe

SUMMARY
Product leader with 8 years of experience building B2B SaaS products in Europe.

EXPERIENCE

Senior Product Manager — Acme Corp, Paris, France — 2021 to present
- Led cross-functional team of 12 to ship a real-time analytics dashboard; increased DAU by 40%.
- Defined and executed 18-month product roadmap aligned to €5M ARR growth target.
- Reduced time-to-market from 6 weeks to 3 weeks by introducing dual-track agile.

Product Manager — Beta Solutions, Lyon, France — 2018 to 2021
- Shipped mobile app MVP in 4 months from zero, reaching 10,000 users in 6 months.
- Owned backlog for checkout flow; reduced cart abandonment by 18% via A/B testing.

Junior PM — StartupXYZ, Paris, France — 2016 to 2018
- Supported product discovery interviews (50+ users).

SKILLS
Product: Roadmapping, User Research, OKRs, A/B Testing, Agile, Scrum
Tools: Jira, Figma, Amplitude, Mixpanel, SQL
Languages: Python (basic), SQL

EDUCATION
MSc Management — ESSEC Business School — Cergy, France — 2016

LANGUAGES
French: Native | English: Bilingual | Spanish: Intermediate

CERTIFICATIONS
Product Management Certificate — Reforge — 2022
`.trim();

const DUMMY_JD = `
Senior Product Manager — Data & Analytics Platform
Acme Tech, Paris, France

We are looking for a Senior Product Manager with 5+ years of experience to lead our Data Platform team. You will define the vision for our analytics infrastructure, work closely with engineering and data science, and drive adoption of our internal data products.

Requirements:
- 5+ years of product management experience in B2B SaaS.
- Strong analytical mindset; experience with SQL, Amplitude, or Mixpanel.
- Proven ability to manage complex technical roadmaps.
- Experience with agile methodologies (Scrum, Kanban).
- Excellent communication skills in English and French.

Nice to have:
- Background in data engineering or analytics tooling.
- Experience with OKR frameworks.
`.trim();

// ── Build Gemini request ────────────────────────────────────────────────────────
const userMessage = `${systemPrompt}\n\n---\n\nCV:\n${DUMMY_CV}\n\nJob Description:\n${DUMMY_JD}`;

const requestBody = {
  contents: [
    {
      role: "user",
      parts: [{ text: userMessage }],
    },
  ],
  generationConfig: {
    responseMimeType: "application/json",
    responseSchema: responseSchema,
  },
};

// ── Call Gemini Flash ───────────────────────────────────────────────────────────
const GEMINI_URL = `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=${GEMINI_API_KEY}`;

console.log("Calling Gemini Flash with responseSchema...");

let httpStatus;
let rawText;
try {
  const resp = await fetch(GEMINI_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(requestBody),
    signal: AbortSignal.timeout(60_000),
  });
  httpStatus = resp.status;
  rawText = await resp.text();
} catch (e) {
  console.error(`FAIL: Network error — ${e.message}`);
  process.exit(1);
}

if (httpStatus !== 200) {
  console.error(`FAIL: HTTP ${httpStatus}`);
  // Print first 800 chars of error body for debugging
  console.error("Response:", rawText.slice(0, 800));
  process.exit(1);
}

// ── Parse Gemini response wrapper ───────────────────────────────────────────────
let geminiResponse;
try {
  geminiResponse = JSON.parse(rawText);
} catch (e) {
  console.error(`FAIL: Gemini wrapper is not valid JSON — ${e.message}`);
  process.exit(1);
}

const candidateParts = geminiResponse?.candidates?.[0]?.content?.parts;
if (!candidateParts || candidateParts.length === 0) {
  console.error("FAIL: No candidates in Gemini response.");
  console.error("Response snippet:", rawText.slice(0, 600));
  process.exit(1);
}

const jsonText = candidateParts[0]?.text;
if (!jsonText) {
  console.error("FAIL: Candidate part has no text.");
  process.exit(1);
}

// ── Parse CVSpec ────────────────────────────────────────────────────────────────
let cvSpec;
try {
  cvSpec = JSON.parse(jsonText);
} catch (e) {
  console.error(`FAIL: CVSpec is not valid JSON — ${e.message}`);
  console.error("Raw CVSpec text:", jsonText.slice(0, 600));
  process.exit(1);
}

// ── Assert required top-level fields ───────────────────────────────────────────
const REQUIRED_FIELDS = [
  "language_detected",
  "ats_score",
  "name",
  "title",
  "contact",
  "summary",
  "summary_kpis",
  "experience",
  "skills",
  "education",
  "languages",
  "recommendations",
];

const failures = [];

for (const field of REQUIRED_FIELDS) {
  if (!(field in cvSpec)) {
    failures.push(`Missing required field: "${field}"`);
  }
}

// Type checks
if ("language_detected" in cvSpec && !["en", "fr", "es", "de"].includes(cvSpec.language_detected)) {
  failures.push(`language_detected must be one of en/fr/es/de, got: "${cvSpec.language_detected}"`);
}
if ("ats_score" in cvSpec && typeof cvSpec.ats_score !== "number") {
  failures.push(`ats_score must be a number, got: ${typeof cvSpec.ats_score}`);
}
if ("contact" in cvSpec && typeof cvSpec.contact !== "object") {
  failures.push(`contact must be an object, got: ${typeof cvSpec.contact}`);
}
if ("experience" in cvSpec && !Array.isArray(cvSpec.experience)) {
  failures.push(`experience must be an array`);
}
if ("experience" in cvSpec && Array.isArray(cvSpec.experience) && cvSpec.experience.length > 0) {
  const first = cvSpec.experience[0];
  for (const f of ["role", "company_line", "bullets", "is_oneliner"]) {
    if (!(f in first)) {
      failures.push(`experience[0] missing field: "${f}"`);
    }
  }
}
if ("skills" in cvSpec && !Array.isArray(cvSpec.skills)) {
  failures.push(`skills must be an array`);
}
if ("recommendations" in cvSpec && !Array.isArray(cvSpec.recommendations)) {
  failures.push(`recommendations must be an array`);
}

if (failures.length > 0) {
  console.error("FAIL: Schema validation errors:");
  for (const f of failures) {
    console.error("  -", f);
  }
  process.exit(1);
}

// ── PASS ────────────────────────────────────────────────────────────────────────
console.log("PASS");
console.log(`  language_detected: ${cvSpec.language_detected}`);
console.log(`  ats_score: ${cvSpec.ats_score}`);
console.log(`  name: ${cvSpec.name}`);
console.log(`  experience entries: ${cvSpec.experience?.length ?? 0}`);
console.log(`  recommendations: ${cvSpec.recommendations?.length ?? 0}`);
