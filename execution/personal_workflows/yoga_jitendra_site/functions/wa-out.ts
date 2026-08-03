// Cloudflare Pages Function: /wa-out
//
// WhatsApp tap-counter proxy. All wa.me/ links on the site are rewritten to
// point here so we can count taps per source in KV (event:wa:*) before
// forwarding the user to WhatsApp.
//
// Query params:
//   ?source=<id>   REQUIRED — one of the allowlisted keys below.
//   ?text=<enc>    OPTIONAL — the WhatsApp prefill message; passed through
//                             to the final wa.me URL verbatim.
//
// Security posture:
//   The `?to=<phone>` param is NOT accepted from the querystring. Anyone
//   with a link to /wa-out?to=<attacker-phone> could otherwise use this
//   site's trusted domain as a phishing redirect to arbitrary WhatsApp
//   numbers. The phone is resolved server-side from a small in-file
//   allowlist keyed on `source`. Unknown source -> 400.
//
// The `?text=` prefill is passed through because even a malicious text
// still terminates at Jitendra's real WhatsApp (from the allowlist), which
// he can ignore. It's user-visible copy on the way in; the attacker gains
// nothing they couldn't get by crafting a wa.me URL directly.
//
// KV shape:
//   key   = `event:wa:<iso-timestamp>:<source>`
//   value = { source, ua, ref, received_at }
// TTL 90 days — the aggregator counts these per range window (7d/30d/all).
//
// Auth:
//   Public endpoint. The _middleware.ts Basic-Auth regex is
//   /^\/(dashboard|api)(\/|$)/  — it does NOT cover /wa-out, which is
//   correct: this endpoint MUST be reachable by anonymous site visitors
//   for the tap to count.

export interface Env {
  DASHBOARD_KV?: KVNamespace;
}

// Allowlisted phones per source. All three current site-CTA sources map to
// Jitendra's WhatsApp (+33 7 58 25 55 83). Add new entries here — never
// accept a phone from the querystring. Phone digits only, no + prefix
// (wa.me expects the E.164 number without the leading +).
const PHONE_BY_SOURCE: Record<string, string> = {
  hero: "33758255583",
  contact: "33758255583",
  topnav: "33758255583",
  // Dashboard-side CTA — sends the operator a message drafted for review
  // requests, per the "This week's next move" card.
  next_move_review_request: "33758255583",
  // Any future source (footer, floating-CTA, service-page, etc.) MUST be
  // registered here first.
};

function randomSuffix(): string {
  const buf = new Uint32Array(1);
  crypto.getRandomValues(buf);
  return buf[0].toString(36).padStart(6, "0").slice(0, 6);
}

function isoNow(): string {
  return new Date().toISOString();
}

export const onRequestGet: PagesFunction<Env> = async ({ request, env }) => {
  const url = new URL(request.url);
  const source = (url.searchParams.get("source") || "").trim();
  const text = url.searchParams.get("text") || "";

  const phone = PHONE_BY_SOURCE[source];
  if (!phone) {
    // 400 with a specific reason so a mis-linked CTA is easy to debug.
    return new Response(
      `Bad Request: unknown source "${source}". Allowed: ${Object.keys(PHONE_BY_SOURCE).join(", ")}`,
      { status: 400, headers: { "Cache-Control": "no-store" } },
    );
  }

  // Capture UTM params from the site's own link (utm_source/medium/content).
  // The parent site's Contact/Hero/TopNav components append these; passing
  // them through into the KV record so the aggregator/dashboard can
  // eventually attribute taps back to the CTA that produced them.
  const utm = {
    source: url.searchParams.get("utm_source") || null,
    medium: url.searchParams.get("utm_medium") || null,
    content: url.searchParams.get("utm_content") || null,
  };

  // Best-effort log — never block the redirect on a KV write failure.
  if (env.DASHBOARD_KV) {
    try {
      // Include a random suffix on the key so two taps arriving in the same
      // millisecond do not collide-and-overwrite (anneal review 2026-07-21).
      const key = `event:wa:${isoNow()}:${source}:${randomSuffix()}`;
      const record = {
        source,
        utm,
        ua: request.headers.get("User-Agent") || null,
        ref: request.headers.get("Referer") || null,
        received_at: isoNow(),
      };
      await env.DASHBOARD_KV.put(key, JSON.stringify(record), {
        expirationTtl: 90 * 24 * 60 * 60,
      });
    } catch (err) {
      // Log but swallow — a slow/failed KV write must not block the user's
      // WhatsApp jump. The tap is lost to metrics; the user still lands
      // in WhatsApp as they expect.
      console.warn("wa-out: KV write failed (swallowed):", (err as Error)?.message);
    }
  }

  // Build the target wa.me URL. Preserve the prefill text verbatim; do NOT
  // re-encode (it was encodeURIComponent'd at the source site already, and
  // .searchParams.get() has already decoded it once).
  const targetParams = new URLSearchParams();
  if (text) targetParams.set("text", text);
  const target = `https://wa.me/${phone}${text ? `?${targetParams.toString()}` : ""}`;

  return Response.redirect(target, 302);
};
