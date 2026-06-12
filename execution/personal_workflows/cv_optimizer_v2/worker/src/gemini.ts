// Gemini Flash REST wrapper — responseSchema mode, no SDK.
// Workers can't run Node; plain fetch only.

import type { CVSpec } from "./cv_schema.js";
import { isCVSpec } from "./cv_schema.js";

export async function optimizeCv(
  cvText: string,
  jdText: string,
  systemPrompt: string,
  responseSchema: object,
  apiKey: string,
): Promise<CVSpec> {
  const endpoint = `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=${apiKey}`;

  const body = {
    contents: [
      {
        role: "user",
        parts: [
          {
            text: `${systemPrompt}\n\n---\n\nCV:\n${cvText}\n\n---\n\nJD:\n${jdText}`,
          },
        ],
      },
    ],
    generationConfig: {
      responseMimeType: "application/json",
      responseSchema,
    },
  };

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 60_000);

  let res: Response;
  try {
    res = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
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
    candidates?: { content?: { parts?: { text?: string }[] } }[];
  };

  const text = respJson?.candidates?.[0]?.content?.parts?.[0]?.text;
  if (!text) {
    throw new Error("gemini_empty_response");
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch (err) {
    throw new Error(`gemini_invalid_json: ${err instanceof Error ? err.message : String(err)}`);
  }

  if (!isCVSpec(parsed)) {
    throw new Error("gemini_response_shape_mismatch");
  }

  return parsed;
}
