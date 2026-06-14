// Anthropic Sonnet 4.6 wrapper — uses tool_use to enforce CVSpec output shape.
// Replaces gemini.ts as the primary optimizer; gemini.ts kept as legacy fallback.
//
// Why Anthropic over Gemini for this task:
// - Better structured reasoning on CV/JD matching (operator preference)
// - tool_use is more reliable than Gemini's responseSchema mode
// - Faster typical completion (8-12s vs Gemini Flash's 15-25s with schema)
// - Cost is trivial at personal scale (~$0.07/call, ~$3.50/yr at 50 runs/yr)

import type { CVSpec } from "./cv_schema.js";
import { isCVSpec } from "./cv_schema.js";

const ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages";

// Model selection — measured 2026-06-13 with the live system prompt + cv_response_schema:
//   - Sonnet 4.6:    53s on real CV+JD (TIMES OUT under 30s Cloudflare Pages wall)
//   - Haiku 4.5:     25s on same input  (FITS — same ATS score, same correct language detection)
//   - Opus 4.8:      not benchmarked (would be slower than Sonnet; not viable for sync request)
// Haiku 4.5 also ~4x cheaper. Upgrade to Sonnet only if quality degrades on real use.
const DEFAULT_MODEL = "claude-haiku-4-5";

export async function optimizeCvAnthropic(
  cvText: string,
  jdText: string,
  systemPrompt: string,
  responseSchema: object,
  apiKey: string,
  profileContext?: string,
  modelOverride?: string,
): Promise<CVSpec> {
  const model = modelOverride || DEFAULT_MODEL;

  // Direct JSON output mode (not tool_use) — measured 2-3s faster on Haiku 4.5 for the
  // CVSpec schema. We validate the parsed JSON with isCVSpec() before returning, so the
  // robustness of tool_use is not actually needed.
  const schemaInstruction = `\n\nYou MUST respond ONLY with a JSON object matching this exact schema. No prose, no markdown code fences, no preamble. Just the raw JSON object:\n\n${JSON.stringify(responseSchema)}`;

  // User message assembly: CV → [optional Current activity] → JD.
  // Profile context is fact, not fabrication — it comes from verified external sources
  // (GitHub API, etc.) and supplements the static CV with recent projects.
  const profileBlock = profileContext && profileContext.trim().length > 0
    ? `\n\n---\n\n${profileContext.trim()}`
    : "";

  const userMessage = `CV (original):\n${cvText}${profileBlock}\n\n---\n\nJD (target):\n${jdText}\n\nReturn the optimized CV JSON now.`;

  const body = {
    model,
    // 3200 tokens — enough for the full CVSpec JSON in French (most verbose case).
    // Lower caps (2400) caused truncated JSON output and parse failures.
    max_tokens: 3200,
    system: systemPrompt + schemaInstruction,
    messages: [{ role: "user", content: userMessage }],
  };

  // 60s internal timeout. Post-Phase-A, /api/optimize is LLM-only and Pages Function
  // gives it a 65s budget — no longer racing the old 29.5s Pages wall. Haiku 4.5 with
  // real CV+JD is 21-28s typical, p99 ~35s. 60s leaves comfortable headroom for variance
  // while still failing fast on genuine upstream outage. Cloudflare edge gateway timeout
  // is ~100s, so we're well within platform limits.
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 60_000);

  let res: Response;
  try {
    res = await fetch(ANTHROPIC_API_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": apiKey,
        "anthropic-version": "2023-06-01",
      },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
  } finally {
    clearTimeout(timeout);
  }

  if (!res.ok) {
    const errText = await res.text();
    throw new Error(`anthropic_http_${res.status}: ${errText.slice(0, 400)}`);
  }

  const respJson = await res.json() as {
    content?: Array<{ type: string; text?: string }>;
    stop_reason?: string;
  };

  // Extract the text block.
  const textBlock = respJson.content?.find((b) => b.type === "text");
  const rawText = textBlock?.text ?? "";

  if (!rawText) {
    throw new Error(
      `anthropic_no_text_content: stop_reason=${respJson.stop_reason}, content_types=${
        respJson.content?.map((b) => b.type).join(",") ?? "none"
      }`,
    );
  }

  const parsed = extractJsonObject(rawText);

  if (!isCVSpec(parsed)) {
    throw new Error("anthropic_response_shape_mismatch");
  }

  return parsed;
}

/**
 * Robust JSON object extraction from LLM output. Handles:
 *   - markdown code fences (```json ... ```) that Claude sometimes adds
 *   - leading/trailing prose ("Here is the optimized CV: { ... }")
 *   - truncated output (no closing fence) — slice still works as long as last `}` exists
 *
 * Throws with a diagnostic message if no braces found or parse fails.
 * Exported so it's unit-testable without network calls.
 */
export function extractJsonObject(rawText: string): unknown {
  const firstBrace = rawText.indexOf("{");
  const lastBrace = rawText.lastIndexOf("}");
  if (firstBrace < 0 || lastBrace < firstBrace) {
    throw new Error(`anthropic_no_json_braces: first_200=${rawText.slice(0, 200)}`);
  }
  const jsonText = rawText.slice(firstBrace, lastBrace + 1);

  try {
    return JSON.parse(jsonText);
  } catch (err) {
    throw new Error(`anthropic_invalid_json: ${err instanceof Error ? err.message : String(err)}; first_200=${jsonText.slice(0, 200)}`);
  }
}
