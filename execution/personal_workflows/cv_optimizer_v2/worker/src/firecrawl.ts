// Firecrawl REST wrapper — minimal, login-wall aware, retry on transient failure.
// No SDK — Workers don't run Node; plain fetch only.

export interface FirecrawlResult {
  ok: boolean;
  markdown?: string;
  reason?: string;
  attempts?: number;
}

export const LOGIN_WALL_KEYWORDS = [
  "sign in to view",
  "sign in to apply",
  "log in to view",
  "join linkedin",
  "join now to see",
  "please sign in",
  "log in or sign up",
  "join to apply",
];

/**
 * Returns the matched login-wall keyword if `markdown` contains one, else null.
 * Exported for unit tests.
 */
export function detectLoginWall(markdown: string): string | null {
  const lowered = markdown.toLowerCase();
  for (const kw of LOGIN_WALL_KEYWORDS) {
    if (lowered.includes(kw)) return kw;
  }
  return null;
}

const MAX_JD_CHARS = 3500;
const FIRST_ATTEMPT_TIMEOUT_MS = 10_000;
const RETRY_TIMEOUT_MS = 5_000;

// Outcome categories — we retry on the first three only.
type AttemptOutcome =
  | { kind: "ok"; markdown: string }
  | { kind: "transient"; reason: string }  // 5xx, timeout, network error, invalid JSON
  | { kind: "permanent"; reason: string }; // 4xx auth/quota, thin_content, login_wall

async function tryScrape(url: string, apiKey: string, timeoutMs: number): Promise<AttemptOutcome> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  let res: Response;
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
        onlyMainContent: true,
        maxAge: 86400000,  // Firecrawl-side 24h cache — backstops our KV cache
      }),
      signal: controller.signal,
    });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return { kind: "transient", reason: `firecrawl_request_failed: ${msg}` };
  } finally {
    clearTimeout(timeout);
  }

  // 4xx = permanent (auth, quota, malformed URL). 5xx = transient (Firecrawl-side).
  if (!res.ok) {
    if (res.status >= 500) {
      return { kind: "transient", reason: `firecrawl_http_${res.status}` };
    }
    return { kind: "permanent", reason: `firecrawl_http_${res.status}` };
  }

  let body: { data?: { markdown?: string } };
  try {
    body = await res.json() as { data?: { markdown?: string } };
  } catch {
    return { kind: "transient", reason: "firecrawl_invalid_json" };
  }

  const markdown = body?.data?.markdown ?? "";

  if (markdown.length < 200) {
    return { kind: "permanent", reason: "thin_content" };
  }

  const wall = detectLoginWall(markdown);
  if (wall) {
    return { kind: "permanent", reason: `login_wall: "${wall}"` };
  }

  return { kind: "ok", markdown };
}

/**
 * Strip leading page chrome (cookie banners, GDPR consent, nav) and cap length.
 * Looks for the first markdown H2 heading (reliable job-title anchor across
 * WTTJ/Greenhouse/Lever) and keeps content from there. Caps at MAX_JD_CHARS.
 * Exported for unit tests.
 */
export function trimToJdBody(markdown: string): string {
  // Strip leading cookie-banner / GDPR-consent chrome. Find the first markdown H2
  // (job title across WTTJ, Greenhouse, Lever) and keep content from there.
  let jdBody = markdown;
  const h2Index = markdown.search(/\n##\s+\S/);
  if (h2Index > 0) {
    jdBody = markdown.slice(h2Index + 1);
  }
  return jdBody.length > MAX_JD_CHARS ? jdBody.slice(0, MAX_JD_CHARS) : jdBody;
}

export async function scrapeUrl(url: string, apiKey: string): Promise<FirecrawlResult> {
  // Attempt 1: full 10s budget.
  const first = await tryScrape(url, apiKey, FIRST_ATTEMPT_TIMEOUT_MS);

  if (first.kind === "ok") {
    return { ok: true, markdown: trimToJdBody(first.markdown), attempts: 1 };
  }

  if (first.kind === "permanent") {
    // login_wall, thin_content, 4xx — retry will not change anything.
    return { ok: false, reason: first.reason, attempts: 1 };
  }

  // Transient (5xx, timeout, network error, invalid JSON) — one retry with 5s cap.
  console.warn(`[firecrawl] attempt 1 transient (${first.reason}); retrying with ${RETRY_TIMEOUT_MS}ms cap`);
  const second = await tryScrape(url, apiKey, RETRY_TIMEOUT_MS);

  if (second.kind === "ok") {
    return { ok: true, markdown: trimToJdBody(second.markdown), attempts: 2 };
  }

  // Surface both failure reasons to aid debugging.
  return {
    ok: false,
    reason: `${first.reason} | retry: ${second.reason}`,
    attempts: 2,
  };
}
