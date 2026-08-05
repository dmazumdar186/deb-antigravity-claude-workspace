/**
 * CRM webhook receiver — Cloudflare Pages Function (or Worker).
 *
 * Path: /webhook/<provider>
 *
 * Responsibilities:
 *   1. Verify HMAC signature (provider-specific header).
 *   2. Dedup by event id via KV (WEBHOOK_DEDUP binding).
 *   3. Dispatch to a queue / Modal endpoint for actual processing (out of scope
 *      for this receiver — it stays fast so it never times out).
 *   4. Return 200 fast; retry-safe.
 *
 * Deploy from the tenant directory:
 *   wrangler deploy
 *
 * Required bindings (wrangler.toml):
 *   WEBHOOK_DEDUP  — KV namespace
 *   WEBHOOK_SECRET — secret (per-provider)
 *   DISPATCH_URL   — env var, optional; if set, POST body to it
 *
 * Signature schemes (defaults; override per provider):
 *   hubspot   — header "X-HubSpot-Signature-v3", base64(HMAC-SHA256(secret, method+uri+body+timestamp))
 *   pipedrive — HTTP Basic on the URL; verify by matching auth header
 *   attio     — header "x-attio-signature", hex(HMAC-SHA256(secret, body))
 *   clickup   — header "X-Signature",       hex(HMAC-SHA256(secret, body))
 *   airtable  — header "X-Airtable-Content-MAC", "hmac-sha256=<hex>"
 */

export interface Env {
  WEBHOOK_DEDUP: KVNamespace;
  WEBHOOK_SECRET: string;
  DISPATCH_URL?: string;
  ALLOWED_PROVIDERS?: string;  // csv, e.g. "hubspot,attio". Default: all.
}

// KV TTL for dedup entries. 7d = plenty for any retry window.
const DEDUP_TTL_SECONDS = 7 * 24 * 60 * 60;

// Max body we'll process. Reject anything larger with 413 to keep receiver
// snappy and to prevent memory blow.
const MAX_BODY_BYTES = 256 * 1024;  // 256 KB

async function hmacSha256Hex(secret: string, body: ArrayBuffer): Promise<string> {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );
  const sig = await crypto.subtle.sign("HMAC", key, body);
  return [...new Uint8Array(sig)].map(b => b.toString(16).padStart(2, "0")).join("");
}

async function hmacSha256Base64(secret: string, body: ArrayBuffer): Promise<string> {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );
  const sig = await crypto.subtle.sign("HMAC", key, body);
  return btoa(String.fromCharCode(...new Uint8Array(sig)));
}

function constantTimeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let out = 0;
  for (let i = 0; i < a.length; i++) out |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return out === 0;
}

interface VerifyResult { ok: boolean; reason?: string; }

async function verifySignature(
  provider: string,
  request: Request,
  bodyBytes: ArrayBuffer,
  secret: string,
): Promise<VerifyResult> {
  const url = new URL(request.url);

  switch (provider) {
    case "attio": {
      const got = (request.headers.get("x-attio-signature") || "").trim();
      if (!got) return { ok: false, reason: "missing x-attio-signature" };
      const expected = await hmacSha256Hex(secret, bodyBytes);
      return { ok: constantTimeEqual(expected, got), reason: "sig mismatch" };
    }
    case "clickup": {
      const got = (request.headers.get("x-signature") || "").trim();
      if (!got) return { ok: false, reason: "missing X-Signature" };
      const expected = await hmacSha256Hex(secret, bodyBytes);
      return { ok: constantTimeEqual(expected, got), reason: "sig mismatch" };
    }
    case "airtable": {
      const got = (request.headers.get("x-airtable-content-mac") || "").trim();
      if (!got) return { ok: false, reason: "missing X-Airtable-Content-MAC" };
      const expected = "hmac-sha256=" + await hmacSha256Hex(secret, bodyBytes);
      return { ok: constantTimeEqual(expected, got), reason: "sig mismatch" };
    }
    case "hubspot": {
      // HubSpot v3: HMAC over method + uri + body + timestamp
      const timestamp = request.headers.get("x-hubspot-request-timestamp") || "";
      const got = (request.headers.get("x-hubspot-signature-v3") || "").trim();
      if (!timestamp || !got) return { ok: false, reason: "missing hubspot headers" };
      const bodyStr = new TextDecoder().decode(bodyBytes);
      const rawStr = request.method + url.origin + url.pathname + bodyStr + timestamp;
      const rawBytes = new TextEncoder().encode(rawStr).buffer;
      const expected = await hmacSha256Base64(secret, rawBytes);
      return { ok: constantTimeEqual(expected, got), reason: "sig mismatch" };
    }
    case "pipedrive": {
      const authz = request.headers.get("authorization") || "";
      const expected = "Basic " + btoa("api:" + secret);
      return { ok: constantTimeEqual(expected, authz), reason: "basic auth mismatch" };
    }
    default:
      return { ok: false, reason: `unknown provider: ${provider}` };
  }
}

function providerFromPath(pathname: string): string | null {
  // Expected: /webhook/<provider>
  const parts = pathname.split("/").filter(Boolean);
  if (parts.length < 2 || parts[0] !== "webhook") return null;
  return parts[1].toLowerCase();
}

function extractEventId(provider: string, body: unknown): string | null {
  // Best-effort: try a few common shapes so dedup works out of the box.
  if (!body || typeof body !== "object") return null;
  const b = body as Record<string, unknown>;
  return (
    (b.eventId as string) ||
    (b.event_id as string) ||
    (b.id as string) ||
    ((b.data as any)?.id as string) ||
    null
  );
}

async function handleWebhook(request: Request, env: Env): Promise<Response> {
  if (request.method !== "POST") {
    return new Response("method not allowed", { status: 405 });
  }

  const url = new URL(request.url);
  const provider = providerFromPath(url.pathname);
  if (!provider) {
    return new Response("bad path; expected /webhook/<provider>", { status: 404 });
  }

  const allowed = (env.ALLOWED_PROVIDERS || "hubspot,pipedrive,attio,clickup,airtable")
    .split(",").map(s => s.trim().toLowerCase());
  if (!allowed.includes(provider)) {
    return new Response(`provider not allowed: ${provider}`, { status: 403 });
  }

  if (!env.WEBHOOK_SECRET) {
    return new Response("server misconfigured: WEBHOOK_SECRET missing", { status: 500 });
  }

  const bodyBytes = await request.arrayBuffer();
  if (bodyBytes.byteLength > MAX_BODY_BYTES) {
    return new Response("payload too large", { status: 413 });
  }

  const verify = await verifySignature(provider, request, bodyBytes, env.WEBHOOK_SECRET);
  if (!verify.ok) {
    // Log the reason for observability; don't leak it to the caller.
    console.warn(`[webhook/${provider}] signature verify failed: ${verify.reason}`);
    return new Response("signature verify failed", { status: 401 });
  }

  // Parse JSON best-effort for event id extraction.
  let parsed: unknown = null;
  try {
    parsed = JSON.parse(new TextDecoder().decode(bodyBytes));
  } catch {
    // Non-JSON body is legal for some providers; use body hash as id.
    parsed = null;
  }

  const eventId = extractEventId(provider, parsed) ||
    (await hmacSha256Hex("event-id-fallback", bodyBytes));  // stable hash of body
  const dedupKey = `evt:${provider}:${eventId}`;

  const existing = await env.WEBHOOK_DEDUP.get(dedupKey);
  if (existing) {
    return new Response(
      JSON.stringify({ deduped: true, event_id: eventId }),
      { status: 200, headers: { "content-type": "application/json" } },
    );
  }

  await env.WEBHOOK_DEDUP.put(
    dedupKey,
    JSON.stringify({ received_at: new Date().toISOString(), provider }),
    { expirationTtl: DEDUP_TTL_SECONDS },
  );

  // Dispatch: POST to DISPATCH_URL if configured. Fire-and-forget with waitUntil
  // so the receiver returns fast.
  if (env.DISPATCH_URL) {
    const dispatch = fetch(env.DISPATCH_URL, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-source-provider": provider,
        "x-event-id": eventId,
      },
      body: JSON.stringify({ provider, event_id: eventId, payload: parsed }),
    }).catch((err) => {
      // Log — never bare-swallow. The webhook's KV entry still shows we accepted
      // the event; a dispatch failure is a downstream issue to investigate.
      console.error(`[webhook/${provider}] dispatch failed: ${err}`);
    });
    // waitUntil so the request handler doesn't block on dispatch completion.
    // @ts-ignore — ExecutionContext in Pages Functions differs slightly.
    (globalThis as any).ctx?.waitUntil?.(dispatch);
  }

  return new Response(
    JSON.stringify({ accepted: true, event_id: eventId, provider }),
    { status: 200, headers: { "content-type": "application/json" } },
  );
}

// --- Cloudflare Pages Function entrypoint ----------------------------------
// (For a plain Worker, replace this with `export default { fetch(request, env, ctx) { ... } }`.)
export async function onRequestPost(context: {
  request: Request;
  env: Env;
  waitUntil: (p: Promise<unknown>) => void;
}): Promise<Response> {
  // Expose ctx to the dispatch waitUntil above without threading it through.
  (globalThis as any).ctx = context;
  return handleWebhook(context.request, context.env);
}

export async function onRequest(context: {
  request: Request;
  env: Env;
  waitUntil: (p: Promise<unknown>) => void;
}): Promise<Response> {
  (globalThis as any).ctx = context;
  if (context.request.method === "POST") {
    return handleWebhook(context.request, context.env);
  }
  return new Response("POST only", { status: 405 });
}
