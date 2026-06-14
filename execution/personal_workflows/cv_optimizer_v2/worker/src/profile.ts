// Profile enrichment: fetches live activity from external sources (GitHub, etc.),
// formats it as a short markdown block, caches in KV with 7-day TTL.
//
// The /api/optimize handler reads the cached block and injects it between CV and JD
// in the LLM prompt. This lets the LLM surface recent projects/activity that may not
// be in the static CV — without inventing anything, because the data is verifiable.
//
// Sources for v1: GitHub public REST API (no auth needed, no cost).
// Future: YouTube channel scrape, personal site scrape. LinkedIn is login-walled — skip.

export interface ProfileEnv {
  RATE_LIMIT: KVNamespace;
}

// Hardcoded for single-user (Debanjan). Move to KV config if multi-user.
const PROFILE_SOURCES = {
  github_user: "dmazumdar186",
  // Set these when you have URLs you want monitored:
  youtube_channel_url: "" as string,
  personal_site_url: "" as string,
};

const PROFILE_KV_KEY = "profile:context";
const PROFILE_KV_TTL_SECONDS = 7 * 86_400;
const GITHUB_TIMEOUT_MS = 8_000;
const MAX_REPOS = 6;

interface GithubRepo {
  name: string;
  description: string | null;
  language: string | null;
  updated_at: string;
  html_url: string;
  fork: boolean;
  archived?: boolean;
  private?: boolean;
}

async function fetchGithubActivity(user: string): Promise<string> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), GITHUB_TIMEOUT_MS);

  let res: Response;
  try {
    res = await fetch(
      `https://api.github.com/users/${encodeURIComponent(user)}/repos?sort=updated&per_page=20`,
      {
        headers: {
          "User-Agent": "cv-optimizer/0.2 (workspace tooling)",
          "Accept": "application/vnd.github+json",
          "X-GitHub-Api-Version": "2022-11-28",
        },
        signal: controller.signal,
      },
    );
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    throw new Error(`github_request_failed: ${msg}`);
  } finally {
    clearTimeout(timeout);
  }

  if (!res.ok) {
    throw new Error(`github_http_${res.status}`);
  }

  const repos = (await res.json()) as GithubRepo[];

  // Skip forks/archived; keep top N by recency (the API already sorts by updated).
  const own = repos
    .filter((r) => !r.fork && !r.archived && !r.private)
    .slice(0, MAX_REPOS);

  if (own.length === 0) return "";

  const lines = own.map((r) => {
    const month = r.updated_at.slice(0, 7);
    const desc = r.description ? ` — ${r.description.trim()}` : "";
    const lang = r.language ? ` (${r.language})` : "";
    return `- ${r.name}${lang}${desc} (last updated ${month})`;
  });

  return `Recent GitHub repos (github.com/${user}):\n${lines.join("\n")}`;
}

/** Pure helper — exported for tests. Combines source sections into final block. */
export function composeProfileContext(sections: string[], generatedDate: string): string {
  const nonEmpty = sections.filter((s) => s.trim().length > 0);
  if (nonEmpty.length === 0) return "";
  return `## Current activity (verified external data — supplements the static CV; generated ${generatedDate})\n\n${nonEmpty.join("\n\n")}`;
}

async function buildProfileContext(): Promise<string> {
  const sections: string[] = [];

  if (PROFILE_SOURCES.github_user) {
    try {
      const gh = await fetchGithubActivity(PROFILE_SOURCES.github_user);
      if (gh) sections.push(gh);
    } catch (err) {
      console.warn(`[profile] github fetch failed: ${err instanceof Error ? err.message : String(err)}`);
    }
  }

  // YouTube + personal site fetchers can be added here when URLs are configured.

  return composeProfileContext(sections, new Date().toISOString().slice(0, 10));
}

/** POST /api/refresh-profile — fetches sources, writes to KV. Returns cache metadata. */
export async function handleRefreshProfile(env: ProfileEnv): Promise<Response> {
  const t0 = Date.now();
  const context = await buildProfileContext();

  if (context.length === 0) {
    return Response.json(
      {
        ok: false,
        reason: "no_sources_returned_content",
        sources_configured: Object.entries(PROFILE_SOURCES).filter(([, v]) => v).map(([k]) => k),
        ms: Date.now() - t0,
      },
      { status: 200 },
    );
  }

  try {
    await env.RATE_LIMIT.put(PROFILE_KV_KEY, context, { expirationTtl: PROFILE_KV_TTL_SECONDS });
  } catch (err) {
    return Response.json(
      { ok: false, reason: `kv_write_failed: ${err instanceof Error ? err.message : String(err)}` },
      { status: 500 },
    );
  }

  console.log(`[profile] refresh wrote ${context.length} chars in ${Date.now() - t0}ms`);
  return Response.json({
    ok: true,
    context_chars: context.length,
    cached_until: new Date(Date.now() + PROFILE_KV_TTL_SECONDS * 1000).toISOString(),
    preview: context.slice(0, 300),
    ms: Date.now() - t0,
  });
}

/** Read-only KV lookup used by /api/optimize. Returns "" on miss or KV error. */
export async function getCachedProfile(env: ProfileEnv): Promise<string> {
  try {
    return (await env.RATE_LIMIT.get(PROFILE_KV_KEY)) ?? "";
  } catch (err) {
    console.warn(`[profile] KV read failed: ${err instanceof Error ? err.message : String(err)}`);
    return "";
  }
}
