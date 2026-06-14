// Gemini 2.5 Flash REST wrapper — responseSchema mode for guaranteed JSON shape.
// No SDK; Workers can't run Node, plain fetch only.
//
// Why Gemini: free tier (1500 req/day on 2.5 Flash) — keeps this project at $0 to run.
// Anthropic API requires a $20 minimum top-up which is the wrong economics for a personal
// tool that runs ~50 calls/year. Quality on multi-lingual structured output (CVSpec) is
// adequate; deeper consistency comes from prompt + per-field validation, not model choice.

import type { CVSpec } from "./cv_schema.js";
import { isCVSpec } from "./cv_schema.js";

const GEMINI_MODEL = "gemini-2.5-flash";
const GEMINI_ENDPOINT = `https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_MODEL}:generateContent`;

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
