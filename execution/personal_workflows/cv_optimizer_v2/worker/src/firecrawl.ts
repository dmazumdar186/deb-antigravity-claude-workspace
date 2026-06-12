// Firecrawl REST wrapper — minimal, login-wall aware.
// No SDK — Workers don't run Node; plain fetch only.

export interface FirecrawlResult {
  ok: boolean;
  markdown?: string;
  reason?: string;
}

const LOGIN_WALL_KEYWORDS = [
  "sign in to view",
  "sign in to apply",
  "log in to view",
  "join linkedin",
  "join now to see",
  "please sign in",
  "log in or sign up",
  "join to apply",
];

export async function scrapeUrl(url: string, apiKey: string): Promise<FirecrawlResult> {
  let res: Response;
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 30_000);
    try {
      res = await fetch("https://api.firecrawl.dev/v1/scrape", {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${apiKey}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          url,
          formats: ["markdown"],
        }),
        signal: controller.signal,
      });
    } finally {
      clearTimeout(timeout);
    }
  } catch (err) {
    return { ok: false, reason: `firecrawl_request_failed: ${err instanceof Error ? err.message : String(err)}` };
  }

  if (!res.ok) {
    return { ok: false, reason: `firecrawl_http_${res.status}` };
  }

  let body: { data?: { markdown?: string } };
  try {
    body = await res.json() as { data?: { markdown?: string } };
  } catch {
    // JSON parse failure — treat as unusable response
    return { ok: false, reason: "firecrawl_invalid_json" };
  }

  const markdown = body?.data?.markdown ?? "";

  // Thin content check.
  if (markdown.length < 200) {
    return { ok: false, reason: "thin_content" };
  }

  // Login-wall detection.
  const lowered = markdown.toLowerCase();
  for (const kw of LOGIN_WALL_KEYWORDS) {
    if (lowered.includes(kw)) {
      return { ok: false, reason: `login_wall: "${kw}"` };
    }
  }

  return { ok: true, markdown };
}
