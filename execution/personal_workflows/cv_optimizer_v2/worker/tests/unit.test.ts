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
