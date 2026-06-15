// Gemini 2.5 Flash REST wrapper — responseSchema mode for guaranteed JSON shape.
// No SDK; Workers can't run Node, plain fetch only.
//
// Why Gemini: free tier (1500 req/day on 2.5 Flash) — keeps this project at $0 to run.
// Anthropic API requires a $20 minimum top-up which is the wrong economics for a personal
// tool that runs ~50 calls/year. Quality on multi-lingual structured output (CVSpec) is
// adequate; deeper consistency comes from prompt + per-field validation, not model choice.

import type { CVSpec } from "./cv_schema.js";
import { isCVSpec } from "./cv_schema.js";
import { validateCvSpecLanguage } from "./lang_validator.js";

const GEMINI_MODEL = "gemini-2.5-flash";
const GEMINI_ENDPOINT = `https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_MODEL}:generateContent`;

/**
 * Inner call to Gemini — extracted so we can call it twice on lang-mismatch retry.
 */
async function callGemini(
  userText: string,
  responseSchema: object,
  apiKey: string,
): Promise<CVSpec> {
  const body = {
    contents: [
      {
        role: "user",
        parts: [{ text: userText }],
      },
    ],
    generationConfig: {
      responseMimeType: "application/json",
      responseSchema,
      // Lower temperature for more deterministic schema adherence + language consistency.
      temperature: 0.3,
      // 8192 — measured: FR CVSpec with profile context truncates at 4096.
      // Gemini 2.5 Flash supports up to 65k output; 8192 leaves comfortable headroom.
      maxOutputTokens: 8192,
    },
  };

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 60_000);

  let res: Response;
  try {
    res = await fetch(GEMINI_ENDPOINT, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-goog-api-key": apiKey,
      },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
  } finally {
    clearTimeout(timeout);
  }

  if (!res.ok) {
    const errText = await res.text();
    if (res.status === 429 || /resource_exhausted/i.test(errText)) {
      let retryAfterSeconds: number | undefined;
      try {
        const parsed = JSON.parse(errText) as {
          error?: { details?: { '@type'?: string; retryDelay?: string }[] };
        };
        const retry = parsed?.error?.details?.find(
          (d) => typeof d?.retryDelay === "string",
        )?.retryDelay;
        if (retry) {
          const m = /^(\d+)(?:\.\d+)?s$/.exec(retry);
          if (m) retryAfterSeconds = parseInt(m[1], 10);
        }
      } catch {
        // Body wasn't JSON — leave retryAfterSeconds undefined.
      }
      const err = new Error(
        `gemini_quota_exhausted: free-tier limit reached${retryAfterSeconds ? `; retry in ${retryAfterSeconds}s` : ""}`,
      );
      (err as Error & { code?: string; retryAfterSeconds?: number }).code = "gemini_quota_exhausted";
      (err as Error & { retryAfterSeconds?: number }).retryAfterSeconds = retryAfterSeconds;
      throw err;
    }
    throw new Error(`gemini_http_${res.status}: ${errText.slice(0, 400)}`);
  }

  const respJson = await res.json() as {
    candidates?: { content?: { parts?: { text?: string }[] }; finishReason?: string }[];
    promptFeedback?: { blockReason?: string };
  };

  if (respJson.promptFeedback?.blockReason) {
    throw new Error(`gemini_safety_block: ${respJson.promptFeedback.blockReason}`);
  }

  const text = respJson?.candidates?.[0]?.content?.parts?.[0]?.text;
  if (!text) {
    const finish = respJson?.candidates?.[0]?.finishReason;
    throw new Error(`gemini_empty_response: finish_reason=${finish ?? "unknown"}`);
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch (err) {
    throw new Error(`gemini_invalid_json: ${err instanceof Error ? err.message : String(err)}; first_200=${text.slice(0, 200)}`);
  }

  if (!isCVSpec(parsed)) {
    throw new Error("gemini_response_shape_mismatch");
  }

  return parsed;
}

export async function optimizeCvGemini(
  cvText: string,
  jdText: string,
  systemPrompt: string,
  responseSchema: object,
  apiKey: string,
  profileContext?: string,
): Promise<CVSpec> {
  // User message assembly: CV → [optional Current activity] → JD.
  // Same shape as anthropic.ts — keeps prompt-engineering portable across providers.
  const profileBlock = profileContext && profileContext.trim().length > 0
    ? `\n\n---\n\n${profileContext.trim()}`
    : "";

  const userText = `${systemPrompt}\n\n---\n\nCV (original):\n${cvText}${profileBlock}\n\n---\n\nJD (target):\n${jdText}\n\nReturn the optimized CV JSON now.`;

  // First attempt.
  const cvSpec = await callGemini(userText, responseSchema, apiKey);
  const expectedLang = cvSpec.language_detected;

  // Per-field language validation (eval-first.md — no summary-only check).
  // On mismatch: retry once with an explicit per-field language reinforcement.
  // Rationale: one retry is cheap (free tier); a second retry risks burning quota.
  const validation = validateCvSpecLanguage(cvSpec, expectedLang);
  if (!validation.ok) {
    const mismatched = validation.mismatches.map((m) => m.field).join(", ");
    console.warn(
      `[lang-validator] ${validation.mismatches.length} field(s) in wrong language (expected=${expectedLang}): ${mismatched}. Retrying with stronger language instruction.`,
    );

    // Build a retry prompt that names the problem fields explicitly.
    const langHint =
      `\n\nCRITICAL LANGUAGE RULE: Every single field in the JSON output MUST be written in ${expectedLang.toUpperCase()}. ` +
      `The previous attempt had the wrong language in: ${mismatched}. ` +
      `Do not use any ${expectedLang === "fr" ? "English" : expectedLang === "en" ? "French/Spanish/German" : "other-language"} words in those fields. ` +
      `ALL bullets, roles, summary, projects, and recommendations must be in ${expectedLang.toUpperCase()} only.`;

    const retryText = userText + langHint;
    const retried = await callGemini(retryText, responseSchema, apiKey);
    return retried;
  }

  console.log(
    `[lang-validator] ok (expected=${expectedLang} checked=${validation.checked} skipped=${validation.skipped})`,
  );
  return cvSpec;
}
