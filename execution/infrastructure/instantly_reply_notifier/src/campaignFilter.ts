/**
 * Campaign allowlist for Telegram notifications (operator 2026-11-10): notify only for the operator's own
 * campaigns that are currently active. "Own" = a campaign carrying an Instantly custom tag whose label starts with
 * one of NOTIFY_TAG_PREFIXES (default "Deb", which covers Deb_03Sep26 / Deb_Oct 6 26 / Deb_16 Oct 26 / Debanjan).
 * Siva's campaigns carry Siva / EM / other tags and are never notified.
 *
 * The list is read from the Instantly API and cached in KV for CACHE_TTL_SECONDS, so a newly tagged campaign is
 * picked up within minutes without a redeploy. Any API failure returns null and the caller FAILS OPEN (notifies):
 * a dropped reply is the one outcome this worker exists to prevent.
 */

const API = "https://api.instantly.ai/api/v2";
const CACHE_KEY = "allow:campaigns:v1";
export const CACHE_TTL_SECONDS = 600;

interface Paged<T> {
  items?: T[];
  next_starting_after?: string;
}

async function paged<T>(path: string, key: string, maxPages = 30): Promise<T[]> {
  const out: T[] = [];
  let after: string | undefined;
  for (let i = 0; i < maxPages; i++) {
    const url = new URL(API + path);
    url.searchParams.set("limit", "100");
    if (after) url.searchParams.set("starting_after", after);
    const r = await fetch(url.toString(), { headers: { Authorization: `Bearer ${key}` } });
    if (!r.ok) throw new Error(`Instantly ${path} HTTP ${r.status}`);
    const j = (await r.json()) as Paged<T>;
    out.push(...(j.items ?? []));
    after = j.next_starting_after;
    if (!after) return out;
  }
  throw new Error(`Instantly ${path}: more than ${maxPages} pages`);
}

/** Pure selection logic (unit-testable): campaigns tagged with an owner prefix, optionally only status 1. */
export function selectCampaigns(
  tags: { id: string; label: string }[],
  mappings: { tag_id: string; resource_id: string; resource_type: number }[],
  campaigns: { id: string; status: number }[],
  prefixes: string[],
  activeOnly: boolean,
): string[] {
  const ownTags = new Set(tags.filter((t) => prefixes.some((p) => t.label.startsWith(p))).map((t) => t.id));
  const own = new Set(mappings.filter((m) => m.resource_type === 2 && ownTags.has(m.tag_id)).map((m) => m.resource_id));
  return campaigns.filter((c) => own.has(c.id) && (!activeOnly || c.status === 1)).map((c) => c.id);
}

export async function allowedCampaignIds(
  env: { INSTANTLY_API_KEY?: string; DEDUP_KV: KVNamespace; NOTIFY_TAG_PREFIXES?: string; NOTIFY_ACTIVE_ONLY?: string },
): Promise<Set<string> | null> {
  try {
    const cached = await env.DEDUP_KV.get(CACHE_KEY);
    if (cached) return new Set(JSON.parse(cached) as string[]);
  } catch (e) {
    console.error("[filter] KV read failed:", e);
  }
  const key = env.INSTANTLY_API_KEY;
  if (!key) {
    console.error("[filter] INSTANTLY_API_KEY not bound - cannot filter, failing open");
    return null;
  }
  try {
    const prefixes = (env.NOTIFY_TAG_PREFIXES ?? "Deb").split(",").map((s) => s.trim()).filter(Boolean);
    const activeOnly = (env.NOTIFY_ACTIVE_ONLY ?? "true") !== "false";
    const [tags, mappings, campaigns] = await Promise.all([
      paged<{ id: string; label: string }>("/custom-tags", key),
      paged<{ tag_id: string; resource_id: string; resource_type: number }>("/custom-tag-mappings", key),
      paged<{ id: string; status: number }>("/campaigns", key),
    ]);
    const ids = selectCampaigns(tags, mappings, campaigns, prefixes, activeOnly);
    try {
      await env.DEDUP_KV.put(CACHE_KEY, JSON.stringify(ids), { expirationTtl: CACHE_TTL_SECONDS });
    } catch (e) {
      console.error("[filter] KV write failed:", e);
    }
    return new Set(ids);
  } catch (e) {
    console.error("[filter] Instantly lookup failed, failing open:", e);
    return null;
  }
}
