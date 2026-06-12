// cv-optimizer-api Worker — Phase 2b (Firecrawl + Gemini + POST /api/optimize)
//
// EMBEDDED PROMPTS: the strings below are copied verbatim from:
//   ../prompts/system_prompt.md       → SYSTEM_PROMPT
//   ../prompts/cv_response_schema.json → RESPONSE_SCHEMA
// Workers cannot read files at runtime; they must be embedded here.
// Keep these in sync with the source files whenever you update them.

import { scrapeUrl } from "./firecrawl.js";
import { optimizeCv } from "./gemini.js";

// ---------------------------------------------------------------------------
// Embedded prompt — source: ../prompts/system_prompt.md
// ---------------------------------------------------------------------------
const SYSTEM_PROMPT = `# CV Optimizer v2 — Gemini System Prompt

You are an expert CV optimization advisor for senior product and technology roles in France and Europe. You hold the precision of an advanced ATS system and the strategic insight of an experienced human recruiter.

## Task

Given a CV and a job description (JD), produce an optimized CV that:
- Maximizes ATS keyword match for this specific JD.
- Surfaces the candidate's most relevant experience and achievements first.
- Stays completely truthful to the original CV — no fabrication of any kind.

## Hard constraints (NEVER violate)

- NEVER invent experience, dates, employers, credentials, or metrics not in the original CV.
- NEVER change company names, job titles, or dates.
- NEVER add projects, certifications, or skills the candidate does not have.
- Output MUST fit on 1–2 A4 pages when rendered at standard font sizes.
- Output MUST use ATS-friendly plain text in all bullet points (no tables, no columns, no text boxes).

## Language rule

Detect the language of the job description. Produce the entire optimized CV in that language.
Match the CV's original voice (first-person where the original uses it; otherwise third-person impersonal).
Supported: \`en\`, \`fr\`, \`es\`, \`de\`. Default to \`en\` if uncertain.

## Optimization moves allowed

1. **Rewrite bullet points** — reshape existing bullets to start with a strong action verb, emphasize JD-aligned achievements, and incorporate verbatim JD keywords where natural.
2. **Reorder bullets** within an experience entry — most JD-relevant bullet first.
3. **Surface skills** — promote skills to the top of the skills section if they appear in the JD.
4. **Drop low-signal items** — if the CV is space-constrained, omit projects or skills with zero relevance to this JD. Never drop entire experience entries.
5. **Tighten phrasing** — trim verbose bullets to one concise, impact-first line. Remove filler phrases ("responsible for", "helped with", "involved in").
6. **Quantify where the original quantifies** — do not invent numbers, but do surface existing metrics more prominently.

## Quality bar

- Every experience bullet starts with a past-tense action verb (Led, Built, Reduced, Shipped, Scaled, Defined, etc.).
- Include exact JD keywords verbatim (not paraphrased) in bullets and summary where natural — ATS systems match strings, not semantics.
- The summary (2–3 sentences) must answer: "Why is this candidate uniquely suited to THIS role?"
- The \`summary_kpis\` line is a one-liner of the candidate's most impressive hard metrics (e.g. "12+ yrs PM | $50M+ ARR shipped | Bilingual FR/EN"). Pull from original CV only.
- ATS score in \`ats_score\` reflects how well the optimized CV keyword-matches this JD (0–100 integer).

## Recommendations array

Include 5–10 short, actionable items the candidate should consider but that you did NOT auto-apply. Examples:
- "Add a link to the Slack bot project — it demonstrates async tooling ownership relevant to this JD."
- "Consider obtaining the AWS Solutions Architect cert — the JD lists it as preferred."
- "Your tenure at [Company] is thin on metrics; add a line about team size or budget if you remember them."

These are advisory only — they require human judgment or information not in the CV.

## Output format

Respond ONLY with the JSON matching the responseSchema. No prose before or after. No markdown code fences. Raw JSON only.`;

// ---------------------------------------------------------------------------
// Embedded schema — source: ../prompts/cv_response_schema.json
// ---------------------------------------------------------------------------
const RESPONSE_SCHEMA: object = {
  "type": "object",
  "description": "CVSpec — the full optimized CV plus metadata returned by Gemini Flash",
  "required": [
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
    "recommendations"
  ],
  "properties": {
    "language_detected": {
      "type": "string",
      "description": "ISO 639-1 language code of the job description",
      "enum": ["en", "fr", "es", "de"]
    },
    "ats_score": {
      "type": "integer",
      "description": "ATS keyword match score for the optimized CV against this JD, 0-100"
    },
    "name": {
      "type": "string",
      "description": "Candidate full name, unchanged from CV"
    },
    "title": {
      "type": "string",
      "description": "Professional headline in the JD language, tailored to this role"
    },
    "contact": {
      "type": "object",
      "description": "Contact details block",
      "required": ["email", "phone", "location"],
      "properties": {
        "email": { "type": "string", "description": "Candidate email address" },
        "phone": { "type": "string", "description": "Candidate phone number" },
        "location": { "type": "string", "description": "City and country (e.g. Paris, France)" },
        "linkedin": { "type": "string", "description": "LinkedIn profile URL if present in the CV, empty string otherwise" },
        "github": { "type": "string", "description": "GitHub profile URL if present in the CV, empty string otherwise" }
      }
    },
    "summary": {
      "type": "string",
      "description": "2-3 sentence ATS-optimized professional summary in the JD language. Must answer why this candidate fits this specific role."
    },
    "summary_kpis": {
      "type": "string",
      "description": "One-line key metrics from the CV only (e.g. 12+ yrs PM | 50M EUR ARR shipped | Bilingual FR/EN). No invented numbers."
    },
    "experience": {
      "type": "array",
      "description": "Work experience entries in reverse-chronological order. Each entry is one role.",
      "items": {
        "type": "object",
        "required": ["role", "company_line", "bullets", "is_oneliner"],
        "properties": {
          "role": { "type": "string", "description": "Job title exactly as it appears in the CV — do not change" },
          "company_line": { "type": "string", "description": "Company name, location, and date range (e.g. Wiser Solutions — Paris, France — Nov 2022 to present)" },
          "bullets": { "type": "array", "description": "Impact-first bullet points for this role, 3-6 entries. Each starts with a past-tense action verb. Include verbatim JD keywords where natural.", "items": { "type": "string" } },
          "is_oneliner": { "type": "boolean", "description": "Set true for very early-career or short roles that should be collapsed to a single line to save space" }
        }
      }
    },
    "skills": {
      "type": "array",
      "description": "Skill categories in priority order — most JD-relevant first",
      "items": {
        "type": "object",
        "required": ["category", "value"],
        "properties": {
          "category": { "type": "string", "description": "Skill category label (e.g. Product, Languages, Tooling, Data, Leadership)" },
          "value": { "type": "string", "description": "Comma-separated list of skills in this category" }
        }
      }
    },
    "education": {
      "type": "array",
      "description": "Education entries in reverse-chronological order",
      "items": {
        "type": "object",
        "required": ["degree", "institution_line"],
        "properties": {
          "degree": { "type": "string", "description": "Degree or qualification name" },
          "institution_line": { "type": "string", "description": "Institution name, location, and year (e.g. HEC Paris — Paris — 2010)" }
        }
      }
    },
    "languages": {
      "type": "array",
      "description": "Language proficiencies (e.g. English: Bilingual, French: Native)",
      "items": { "type": "string" }
    },
    "certifications": {
      "type": "array",
      "description": "Professional certifications. Empty array if none.",
      "items": { "type": "string" }
    },
    "projects": {
      "type": "array",
      "description": "Notable projects or side work. Empty array if none or if dropped for space.",
      "items": { "type": "string" }
    },
    "recommendations": {
      "type": "array",
      "description": "5-10 short advisory items the candidate should consider but were NOT auto-applied. Each is one actionable sentence.",
      "items": { "type": "string" }
    }
  }
};

// ---------------------------------------------------------------------------
// Env bindings
// ---------------------------------------------------------------------------
export interface Env {
  RATE_LIMIT: KVNamespace;
  APP_VERSION: string;
  // Secrets (set via `wrangler secret put`):
  WORKER_SECRET?: string;
  GEMINI_API_KEY?: string;
  FIRECRAWL_API_KEY?: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Constant-time string comparison to prevent timing-based secret leaks.
 * XORs every char position; avoids early return so comparison time is O(max(a,b)).
 */
function safeEqual(a: string, b: string): boolean {
  const la = a.length;
  const lb = b.length;
  let diff = la ^ lb; // length mismatch → diff ≠ 0
  const len = Math.max(la, lb);
  for (let i = 0; i < len; i++) {
    diff |= (a.charCodeAt(i % la) ^ b.charCodeAt(i % lb));
  }
  return diff === 0;
}

/** Current UTC hour bucket string for per-IP rate limiting (e.g. "2024-01-15T13"). */
function hourBucket(): string {
  return new Date().toISOString().slice(0, 13); // "YYYY-MM-DDTHH"
}

// ---------------------------------------------------------------------------
// Router
// ---------------------------------------------------------------------------
export default {
  async fetch(req: Request, env: Env, _ctx: ExecutionContext): Promise<Response> {
    const url = new URL(req.url);

    if (req.method === "GET" && url.pathname === "/api/health") {
      return await handleHealth(env);
    }

    if (req.method === "POST" && url.pathname === "/api/optimize") {
      return await handleOptimize(req, env);
    }

    return new Response("Not found", { status: 404 });
  },
};

// ---------------------------------------------------------------------------
// GET /api/health
// ---------------------------------------------------------------------------
async function handleHealth(env: Env): Promise<Response> {
  // KV probe: write + read a short key to confirm the binding works.
  let kvOk = false;
  let kvError: string | undefined;
  try {
    await env.RATE_LIMIT.put("health:probe", String(Date.now()), { expirationTtl: 60 });
    const got = await env.RATE_LIMIT.get("health:probe");
    kvOk = got !== null;
  } catch (err) {
    kvError = err instanceof Error ? err.message : String(err);
  }

  // Secret-presence map — booleans only, NEVER values.
  const secretsPresent = {
    worker_secret: Boolean(env.WORKER_SECRET),
    gemini: Boolean(env.GEMINI_API_KEY),
    firecrawl: Boolean(env.FIRECRAWL_API_KEY),
  };

  const allSecretsPresent = Object.values(secretsPresent).every(Boolean);
  const status = kvOk && allSecretsPresent ? "ok" : "degraded";

  return Response.json({
    status,
    version: env.APP_VERSION ?? "unknown",
    kv_check: kvOk ? "pass" : `fail: ${kvError ?? "no value"}`,
    secrets_present: secretsPresent,
    timestamp: new Date().toISOString(),
  });
}

// ---------------------------------------------------------------------------
// POST /api/optimize
// ---------------------------------------------------------------------------

// Note: this Worker is called server-side by the Pages Function
// (functions/api/optimize.js), NOT directly by the browser.
// No CORS headers are required — same-origin Pages Function → Worker call only.

async function handleOptimize(req: Request, env: Env): Promise<Response> {
  // 1. Secret auth — constant-time compare.
  const incomingSecret = req.headers.get("X-Worker-Secret") ?? "";
  const expectedSecret = env.WORKER_SECRET ?? "";
  if (!expectedSecret || !safeEqual(incomingSecret, expectedSecret)) {
    return Response.json({ error: "unauthorized" }, { status: 401 });
  }

  // 2. Per-IP rate limit: 10 requests per hour via KV.
  const ip = req.headers.get("CF-Connecting-IP") ?? "unknown";
  const rlKey = `rl:${ip}:${hourBucket()}`;
  let currentCount = 0;
  try {
    const existing = await env.RATE_LIMIT.get(rlKey);
    currentCount = existing ? parseInt(existing, 10) : 0;
  } catch (err) {
    // KV read failure — log and allow through rather than hard-blocking all requests.
    // Safe to pass: a momentary KV failure shouldn't deny all users.
    console.error(`[rate-limit] KV read failed for key ${rlKey}: ${err instanceof Error ? err.message : String(err)}`);
  }

  if (currentCount >= 10) {
    const nowMs = Date.now();
    const nextHourMs = new Date(hourBucket() + ":00:00Z").getTime() + 3600_000;
    const retryAfterSeconds = Math.max(0, Math.ceil((nextHourMs - nowMs) / 1000));
    return Response.json(
      { error: "rate_limit", retry_after_seconds: retryAfterSeconds },
      { status: 429 },
    );
  }

  // Increment counter; fire-and-forget (no await) to not block the response path.
  env.RATE_LIMIT.put(rlKey, String(currentCount + 1), { expirationTtl: 3600 }).catch((err: unknown) => {
    console.error(`[rate-limit] KV write failed for key ${rlKey}: ${err instanceof Error ? err.message : String(err)}`);
  });

  // 3. Parse + validate request body.
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return Response.json({ error: "invalid_json" }, { status: 400 });
  }

  if (typeof body !== "object" || body === null) {
    return Response.json({ error: "invalid_body" }, { status: 400 });
  }

  const { cv_text, jd_url, jd_text } = body as Record<string, unknown>;

  if (typeof cv_text !== "string" || cv_text.trim().length === 0) {
    return Response.json({ error: "cv_text_required" }, { status: 400 });
  }
  if (cv_text.length > 50_000) {
    return Response.json({ error: "cv_text_too_long", max_chars: 50_000 }, { status: 400 });
  }

  const hasJdUrl = typeof jd_url === "string" && jd_url.trim().length > 0;
  const hasJdText = typeof jd_text === "string" && jd_text.trim().length > 0;

  if (!hasJdUrl && !hasJdText) {
    return Response.json({ error: "jd_required", detail: "Provide jd_url and/or jd_text." }, { status: 400 });
  }

  // 4. Resolve JD text.
  let resolvedJdText: string;

  if (hasJdUrl) {
    const firecrawlKey = env.FIRECRAWL_API_KEY ?? "";
    const scraped = await scrapeUrl(jd_url as string, firecrawlKey);

    if (scraped.ok && scraped.markdown) {
      resolvedJdText = scraped.markdown;
    } else if (hasJdText) {
      // Fallback: scrape failed but caller also supplied raw text — use it.
      console.warn(`[optimize] Firecrawl scrape failed (${scraped.reason}); falling back to jd_text.`);
      resolvedJdText = jd_text as string;
    } else {
      // No fallback available.
      return Response.json(
        {
          error: "jd_scrape_failed",
          reason: scraped.reason,
          suggestion: "paste the JD text directly",
        },
        { status: 400 },
      );
    }
  } else {
    // No URL supplied — use raw text directly.
    resolvedJdText = jd_text as string;
  }

  // 5. Optimize via Gemini.
  try {
    const cvSpec = await optimizeCv(
      cv_text,
      resolvedJdText,
      SYSTEM_PROMPT,
      RESPONSE_SCHEMA,
      env.GEMINI_API_KEY ?? "",
    );
    return Response.json(cvSpec, { status: 200 });
  } catch (err) {
    const detail = err instanceof Error ? err.message.slice(0, 200) : String(err).slice(0, 200);
    console.error(`[optimize] Gemini call failed: ${detail}`);
    return Response.json({ error: "optimize_failed", detail }, { status: 502 });
  }
}
