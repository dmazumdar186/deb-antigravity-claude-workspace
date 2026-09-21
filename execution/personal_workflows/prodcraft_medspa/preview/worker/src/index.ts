// ProdCraft med-spa concept preview host.
//
// Serves static preview sites out of R2 on wildcard hosts of the shape
// {slug}-{suffix}.preview.prodcraft.fyi. The Python builder
// (preview/build_preview.py) uploads files to R2 directly via the S3
// API under key prefix `previews/{slug}-{suffix}/`, then calls
// POST /api/publish on this Worker to arm the host in KV. See
// CONTRACTS.md ("Layout", "business.json", Worker description under
// preview/) for the full contract this file implements.
//
// Exports handleRequest/handleScheduled directly (not just the default
// export) so test/index.test.ts can call them without miniflare.

import { expiredPage, notFoundPage, removeConfirmForm, removeConfirmedPage, takedownPage } from "./html";

export interface Env {
  PREVIEWS: R2Bucket;
  META: KVNamespace;
  PREVIEW_BASE_DOMAIN: string;
  // Secrets — undefined in local/dev unless set via `wrangler secret put`.
  SUPABASE_URL?: string;
  SUPABASE_SERVICE_KEY?: string;
  REMOVE_WEBHOOK_SECRET?: string;
}

export interface PreviewMeta {
  expires_at: string; // ISO date/datetime
  takedown: boolean;
  business_id: string;
  preview_id: string;
  status?: "active" | "expired" | "takedown";
  takedown_at?: string;
}

const SECURITY_HEADERS: Record<string, string> = {
  "X-Robots-Tag": "noindex, nofollow",
  "Content-Security-Policy":
    "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; frame-ancestors 'none'",
};

const CONTENT_TYPES: Record<string, string> = {
  html: "text/html; charset=utf-8",
  css: "text/css; charset=utf-8",
  js: "application/javascript; charset=utf-8",
  json: "application/json; charset=utf-8",
  png: "image/png",
  jpg: "image/jpeg",
  jpeg: "image/jpeg",
  webp: "image/webp",
  svg: "image/svg+xml",
  ico: "image/x-icon",
  woff2: "font/woff2",
  txt: "text/plain; charset=utf-8",
  xml: "application/xml; charset=utf-8",
};

function contentTypeFor(path: string): string {
  const ext = path.split(".").pop()?.toLowerCase() ?? "";
  return CONTENT_TYPES[ext] ?? "application/octet-stream";
}

/** First label of the host is the {slug}-{suffix} KV key / R2 prefix segment. */
export function slugSuffixFromHost(host: string): string {
  return host.split(".")[0] ?? "";
}

function metaKey(slugSuffix: string): string {
  return `meta:${slugSuffix}`;
}

function r2Prefix(slugSuffix: string): string {
  return `previews/${slugSuffix}/`;
}

function htmlResponse(body: string, status = 200, extraHeaders: Record<string, string> = {}): Response {
  return new Response(body, {
    status,
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      ...SECURITY_HEADERS,
      ...extraHeaders,
    },
  });
}

async function getMeta(env: Env, slugSuffix: string): Promise<PreviewMeta | null> {
  const raw = await env.META.get(metaKey(slugSuffix));
  if (!raw) return null;
  try {
    return JSON.parse(raw) as PreviewMeta;
  } catch {
    return null;
  }
}

async function putMeta(env: Env, slugSuffix: string, meta: PreviewMeta): Promise<void> {
  await env.META.put(metaKey(slugSuffix), JSON.stringify(meta));
}

function isExpired(meta: PreviewMeta, now: Date): boolean {
  const expires = new Date(meta.expires_at);
  return !Number.isNaN(expires.getTime()) && now.getTime() > expires.getTime();
}

/** Resolve a request path (under a preview host) to an R2 object key. */
function objectKeyFor(slugSuffix: string, pathname: string): string {
  const prefix = r2Prefix(slugSuffix);
  let rel = pathname.replace(/^\/+/, "");
  if (rel === "" || rel.endsWith("/")) {
    rel = `${rel}index.html`;
  }
  return `${prefix}${rel}`;
}

async function serveStaticAsset(env: Env, slugSuffix: string, pathname: string): Promise<Response> {
  const key = objectKeyFor(slugSuffix, pathname);
  let obj = await env.PREVIEWS.get(key);
  if (!obj) {
    const notFoundKey = `${r2Prefix(slugSuffix)}404.html`;
    obj = await env.PREVIEWS.get(notFoundKey);
    if (!obj) {
      return htmlResponse(notFoundPage(), 404);
    }
    return new Response(obj.body, {
      status: 404,
      headers: {
        "Content-Type": "text/html; charset=utf-8",
        "Cache-Control": "public, max-age=300",
        ...SECURITY_HEADERS,
      },
    });
  }
  return new Response(obj.body, {
    status: 200,
    headers: {
      "Content-Type": contentTypeFor(key),
      "Cache-Control": "public, max-age=300",
      ...SECURITY_HEADERS,
    },
  });
}

async function deleteAllUnderPrefix(env: Env, prefix: string): Promise<number> {
  let deleted = 0;
  let cursor: string | undefined;
  do {
    const listing: R2Objects = await env.PREVIEWS.list({ prefix, cursor });
    if (listing.objects.length > 0) {
      await env.PREVIEWS.delete(listing.objects.map((o) => o.key));
      deleted += listing.objects.length;
    }
    cursor = listing.truncated ? listing.cursor : undefined;
  } while (cursor);
  return deleted;
}

function unauthorized(): Response {
  return new Response(JSON.stringify({ error: "unauthorized" }), {
    status: 401,
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
}

function isAuthorized(request: Request, env: Env): boolean {
  if (!env.REMOVE_WEBHOOK_SECRET) return false;
  const header = request.headers.get("Authorization") ?? "";
  return header === `Bearer ${env.REMOVE_WEBHOOK_SECRET}`;
}

async function supabasePatch(env: Env, table: string, filterQuery: string, patch: Record<string, unknown>): Promise<void> {
  if (!env.SUPABASE_URL || !env.SUPABASE_SERVICE_KEY) return;
  const url = `${env.SUPABASE_URL.replace(/\/+$/, "")}/rest/v1/${table}?${filterQuery}`;
  await fetch(url, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      apikey: env.SUPABASE_SERVICE_KEY,
      Authorization: `Bearer ${env.SUPABASE_SERVICE_KEY}`,
      Prefer: "return=minimal",
    },
    body: JSON.stringify(patch),
  });
}

async function supabaseGet(env: Env, table: string, filterQuery: string): Promise<Array<Record<string, unknown>>> {
  if (!env.SUPABASE_URL || !env.SUPABASE_SERVICE_KEY) return [];
  const url = `${env.SUPABASE_URL.replace(/\/+$/, "")}/rest/v1/${table}?${filterQuery}`;
  const res = await fetch(url, {
    headers: {
      apikey: env.SUPABASE_SERVICE_KEY,
      Authorization: `Bearer ${env.SUPABASE_SERVICE_KEY}`,
    },
  });
  if (!res.ok) return [];
  try {
    return (await res.json()) as Array<Record<string, unknown>>;
  } catch {
    return [];
  }
}

async function handleRemove(request: Request, env: Env, host: string, slugSuffix: string): Promise<Response> {
  // Accept form-encoded or JSON bodies; body content isn't load-bearing
  // beyond the same-origin POST itself (contract: no CSRF token required).
  const contentType = request.headers.get("Content-Type") ?? "";
  try {
    if (contentType.includes("application/json")) {
      await request.json().catch(() => ({}));
    } else {
      await request.formData().catch(() => undefined);
    }
  } catch {
    // best-effort parse only
  }

  const meta = await getMeta(env, slugSuffix);
  if (!meta) {
    return htmlResponse(notFoundPage(), 404);
  }

  const takedownAt = new Date().toISOString();
  const updated: PreviewMeta = { ...meta, takedown: true, takedown_at: takedownAt, status: "takedown" };
  await putMeta(env, slugSuffix, updated);
  await deleteAllUnderPrefix(env, r2Prefix(slugSuffix));

  if (env.SUPABASE_URL && env.SUPABASE_SERVICE_KEY) {
    const subdomainUrl = `https://${host}`;
    await supabasePatch(
      env,
      "previews",
      `subdomain_url=eq.${encodeURIComponent(subdomainUrl)}`,
      { status: "takedown", takedown: true, takedown_at: takedownAt }
    );
    if (meta.business_id) {
      await supabasePatch(env, "businesses", `id=eq.${encodeURIComponent(meta.business_id)}`, {
        do_not_contact: true,
      });
    }
  }

  return htmlResponse(removeConfirmedPage());
}

async function handleApiPublish(request: Request, env: Env): Promise<Response> {
  if (!isAuthorized(request, env)) return unauthorized();
  let body: { host?: string; expires_at?: string; business_id?: string; preview_id?: string };
  try {
    body = await request.json();
  } catch {
    return new Response(JSON.stringify({ error: "invalid json" }), { status: 400 });
  }
  const { host, expires_at, business_id, preview_id } = body;
  if (!host || !expires_at || !business_id || !preview_id) {
    return new Response(JSON.stringify({ error: "host, expires_at, business_id, preview_id required" }), {
      status: 400,
    });
  }
  const slugSuffix = slugSuffixFromHost(host);
  const meta: PreviewMeta = { expires_at, takedown: false, business_id, preview_id, status: "active" };
  await putMeta(env, slugSuffix, meta);
  return new Response(JSON.stringify({ ok: true, meta }), {
    status: 200,
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
}

async function handleApiExtend(request: Request, env: Env): Promise<Response> {
  if (!isAuthorized(request, env)) return unauthorized();
  let body: { host?: string; expires_at?: string };
  try {
    body = await request.json();
  } catch {
    return new Response(JSON.stringify({ error: "invalid json" }), { status: 400 });
  }
  const { host, expires_at } = body;
  if (!host || !expires_at) {
    return new Response(JSON.stringify({ error: "host, expires_at required" }), { status: 400 });
  }
  const slugSuffix = slugSuffixFromHost(host);
  const existing = await getMeta(env, slugSuffix);
  if (!existing) {
    return new Response(JSON.stringify({ error: "not found" }), { status: 404 });
  }
  const updated: PreviewMeta = { ...existing, expires_at, takedown: false, status: "active" };
  await putMeta(env, slugSuffix, updated);
  return new Response(JSON.stringify({ ok: true, meta: updated }), {
    status: 200,
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
}

async function handleApiMeta(request: Request, env: Env, url: URL): Promise<Response> {
  if (!isAuthorized(request, env)) return unauthorized();
  const host = url.searchParams.get("host");
  if (!host) {
    return new Response(JSON.stringify({ error: "host required" }), { status: 400 });
  }
  const slugSuffix = slugSuffixFromHost(host);
  const meta = await getMeta(env, slugSuffix);
  if (!meta) {
    return new Response(JSON.stringify({ error: "not found" }), { status: 404 });
  }
  return new Response(JSON.stringify(meta), {
    status: 200,
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
}

async function expiredResponse(env: Env, slugSuffix: string): Promise<Response> {
  const key = `${r2Prefix(slugSuffix)}_system/expired.html`;
  const obj = await env.PREVIEWS.get(key);
  if (obj) {
    return new Response(obj.body, {
      status: 200,
      headers: { "Content-Type": "text/html; charset=utf-8", ...SECURITY_HEADERS },
    });
  }
  return htmlResponse(expiredPage(), 200);
}

export async function handleRequest(request: Request, env: Env, _ctx: ExecutionContext): Promise<Response> {
  const url = new URL(request.url);
  const host = request.headers.get("Host") ?? url.hostname;
  const pathname = url.pathname;

  // robots.txt applies on any preview host regardless of slug state.
  if (pathname === "/robots.txt") {
    return new Response("User-agent: *\nDisallow: /\n", {
      status: 200,
      headers: { "Content-Type": "text/plain; charset=utf-8", ...SECURITY_HEADERS },
    });
  }

  // Control-plane API, not slug-scoped.
  if (pathname === "/api/publish" && request.method === "POST") {
    return handleApiPublish(request, env);
  }
  if (pathname === "/api/extend" && request.method === "POST") {
    return handleApiExtend(request, env);
  }
  if (pathname === "/api/meta" && request.method === "GET") {
    return handleApiMeta(request, env, url);
  }

  const slugSuffix = slugSuffixFromHost(host);

  if (pathname === "/remove") {
    if (request.method === "POST") {
      return handleRemove(request, env, host, slugSuffix);
    }
    if (request.method === "GET") {
      return htmlResponse(removeConfirmForm(host));
    }
  }

  const meta = await getMeta(env, slugSuffix);
  if (!meta) {
    return htmlResponse(notFoundPage(), 404);
  }
  if (meta.takedown) {
    return htmlResponse(takedownPage(), 410);
  }
  if (isExpired(meta, new Date())) {
    if (pathname === "/expired") {
      return expiredResponse(env, slugSuffix);
    }
    return new Response(null, {
      status: 302,
      headers: { Location: "/expired", ...SECURITY_HEADERS },
    });
  }

  return serveStaticAsset(env, slugSuffix, pathname);
}

export async function handleScheduled(env: Env): Promise<{ expired: number; deleted: number }> {
  const now = new Date();
  const sixtyDaysMs = 60 * 24 * 60 * 60 * 1000;
  let expiredCount = 0;
  let deletedCount = 0;
  let cursor: string | undefined;

  do {
    const listing = await env.META.list({ prefix: "meta:", cursor });
    for (const key of listing.keys) {
      const raw = await env.META.get(key.name);
      if (!raw) continue;
      let meta: PreviewMeta;
      try {
        meta = JSON.parse(raw) as PreviewMeta;
      } catch {
        continue;
      }
      const slugSuffix = key.name.slice("meta:".length);
      const expires = new Date(meta.expires_at);
      if (Number.isNaN(expires.getTime())) continue;

      if (now.getTime() > expires.getTime() && meta.status !== "expired" && !meta.takedown) {
        const updated: PreviewMeta = { ...meta, status: "expired" };
        await env.META.put(key.name, JSON.stringify(updated));
        expiredCount += 1;

        if (env.SUPABASE_URL && env.SUPABASE_SERVICE_KEY) {
          const subdomainUrl = `https://${slugSuffix}.${env.PREVIEW_BASE_DOMAIN}`;
          await supabasePatch(
            env,
            "previews",
            `subdomain_url=eq.${encodeURIComponent(subdomainUrl)}`,
            { status: "expired" }
          );
        }
      }

      // Grace period: only reclaim R2 storage 60+ days past expiry.
      if (now.getTime() - expires.getTime() > sixtyDaysMs) {
        const deleted = await deleteAllUnderPrefix(env, r2Prefix(slugSuffix));
        if (deleted > 0) deletedCount += deleted;
      }
    }
    cursor = listing.list_complete ? undefined : listing.cursor;
  } while (cursor);

  console.log(`[prodcraft-preview-host cron] expired=${expiredCount} deleted_objects=${deletedCount}`);
  return { expired: expiredCount, deleted: deletedCount };
}

export default {
  fetch: handleRequest,
  async scheduled(_event: ScheduledEvent, env: Env, ctx: ExecutionContext): Promise<void> {
    ctx.waitUntil(handleScheduled(env));
  },
};

// Re-export for tests that want direct access to Supabase helpers without
// hitting the network (kept private otherwise).
export const __testables = { supabaseGet, supabasePatch, objectKeyFor, isExpired };
