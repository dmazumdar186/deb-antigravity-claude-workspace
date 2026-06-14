// POST /api/scrape — Firecrawl-only handler with KV-backed cache.
//
// Decouples web scraping from LLM optimization. The Pages Function orchestrator
// calls /api/scrape first (returns in 0-8s) then /api/optimize (returns in 12-22s).
// Splitting them means neither sub-call races a hard wall.
//
// Cache: KV key `scrape:<sha256(url)>`, 24h TTL. Same URL twice = 0ms second time.

import { scrapeUrl } from "./firecrawl.js";

export interface ScrapeEnv {
  RATE_LIMIT: KVNamespace; // shared with rate-limit, reused for scrape cache
  FIRECRAWL_API_KEY?: string;
}

const CACHE_TTL_SECONDS = 86_400; // 24h
const CACHE_KEY_PREFIX = "scrape:";

async function sha256Hex(s: string): Promise<string> {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s));
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

export async function handleScrape(req: Request, env: ScrapeEnv): Promise<Response> {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return Response.json({ ok: false, reason: "invalid_json" }, { status: 400 });
  }

  if (typeof body !== "object" || body === null) {
    return Response.json({ ok: false, reason: "invalid_body" }, { status: 400 });
  }

  const { url } = body as Record<string, unknown>;
  if (typeof url !== "string" || url.trim().length === 0) {
    return Response.json({ ok: false, reason: "url_required" }, { status: 400 });
  }
  if (url.length > 2000) {
    return Response.json({ ok: false, reason: "url_too_long" }, { status: 400 });
  }

  // Cache lookup.
  const cacheKey = CACHE_KEY_PREFIX + (await sha256Hex(url));
  const t0 = Date.now();
  try {
    const cached = await env.RATE_LIMIT.get(cacheKey);
    if (cached) {
      console.log(`[scrape] cache HIT ${Date.now() - t0}ms url=${url.slice(0, 80)}`);
      return Response.json(
        { ok: true, markdown: cached, cached: true, ms: Date.now() - t0 },
        { status: 200 },
      );
    }
  } catch (err) {
    // KV read failure — log and continue with live scrape.
    console.error(`[scrape] KV read failed: ${err instanceof Error ? err.message : String(err)}`);
  }

  // Live scrape.
  const tScrape = Date.now();
  const result = await scrapeUrl(url, env.FIRECRAWL_API_KEY ?? "");
  console.log(`[scrape] firecrawl ${Date.now() - tScrape}ms ok=${result.ok} url=${url.slice(0, 80)}`);

  if (!result.ok || !result.markdown) {
    // Return 200 with ok:false so the orchestrator can decide fallback policy.
    // Reason string preserves the existing contract (login_wall, thin_content, etc.).
    return Response.json(
      { ok: false, reason: result.reason ?? "unknown", ms: Date.now() - t0 },
      { status: 200 },
    );
  }

  // Cache write — fire-and-forget; do not block response.
  env.RATE_LIMIT.put(cacheKey, result.markdown, { expirationTtl: CACHE_TTL_SECONDS }).catch(
    (err: unknown) => {
      console.error(`[scrape] KV write failed: ${err instanceof Error ? err.message : String(err)}`);
    },
  );

  return Response.json(
    { ok: true, markdown: result.markdown, cached: false, ms: Date.now() - t0 },
    { status: 200 },
  );
}
