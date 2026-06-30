// vapi-dental-fr Worker.
//
// Serves the demo HTML widget at `/` (Vapi Web SDK) and exposes two Vapi tool-call webhooks:
//   POST /vapi/tools/list_slots  -> Cal.com v2 GET /v2/slots
//   POST /vapi/tools/book_slot   -> Cal.com v2 POST /v2/bookings
// All Vapi-side audio + LLM + TTS handled by Vapi backend. This worker is pure HTTP.
//
// Auth model: GET / and the /vapi/tools/* webhooks are public (Vapi calls them from
// its backend). /api/health is dual-mode: public summary by default; full calendar
// probe when X-Voice-Agent-Secret matches WORKER_SECRET.

import { renderWidget } from "./widget.js";
import { calListSlots, calBookSlot } from "./calcom.js";

export interface Env {
  // [vars]
  APP_VERSION: string;
  CLINIC_NAME: string;
  CLINIC_PHONE: string;
  DEMO_MODE: string;
  // Secrets (wrangler secret put):
  CALCOM_API_KEY?: string;
  CALCOM_USERNAME?: string;
  CALCOM_EVENT_SLUG?: string;
  CALCOM_TIMEZONE?: string;
  VAPI_PUBLIC_KEY?: string;
  VAPI_ASSISTANT_ID?: string;
  WORKER_SECRET?: string;
}

/**
 * Constant-time string comparison (per workspace pattern from cv_optimizer_v2/worker/src/index.ts:39-48).
 */
function safeEqual(a: string, b: string): boolean {
  const la = a.length;
  const lb = b.length;
  let diff = la ^ lb;
  const len = Math.max(la, lb);
  for (let i = 0; i < len; i++) {
    diff |= a.charCodeAt(i % la) ^ b.charCodeAt(i % lb);
  }
  return diff === 0;
}

function corsHeaders(): HeadersInit {
  return {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, X-Voice-Agent-Secret",
  };
}

interface VapiToolCall {
  id: string;
  type?: string;
  function?: { name?: string; arguments?: string | Record<string, unknown> };
}

function extractToolCalls(payload: unknown): VapiToolCall[] {
  if (!payload || typeof payload !== "object") return [];
  const root = payload as Record<string, unknown>;
  const msg = (root.message ?? root) as Record<string, unknown>;
  const raw =
    (msg.toolCalls as unknown[]) ??
    (msg.tool_calls as unknown[]) ??
    [];
  return raw.filter(
    (c): c is VapiToolCall =>
      !!c && typeof c === "object" && typeof (c as VapiToolCall).id === "string"
  );
}

function parseArgs(tc: VapiToolCall): Record<string, unknown> {
  const raw = tc.function?.arguments ?? {};
  if (typeof raw === "string") {
    try {
      return JSON.parse(raw || "{}");
    } catch {
      return {};
    }
  }
  return (raw as Record<string, unknown>) ?? {};
}

async function handleHealth(req: Request, env: Env): Promise<Response> {
  const secret = req.headers.get("X-Voice-Agent-Secret") ?? "";
  const expected = env.WORKER_SECRET ?? "";
  const authed = expected.length > 0 && safeEqual(secret, expected);

  const body: Record<string, unknown> = {
    ok: true,
    build: "vapi-dental-fr",
    version: env.APP_VERSION,
    demo_mode: env.DEMO_MODE === "true",
    secrets_present: {
      calcom: !!env.CALCOM_API_KEY,
      vapi_public: !!env.VAPI_PUBLIC_KEY,
      vapi_assistant_id: !!env.VAPI_ASSISTANT_ID && env.VAPI_ASSISTANT_ID !== "pending",
      worker: expected.length > 0,
    },
  };

  if (authed) {
    try {
      const slots = await calListSlots(env, "consultation", 0);
      body.cal_reachable = true;
      body.sample_slot = slots[0]?.display ?? null;
    } catch (err) {
      body.cal_reachable = false;
      body.cal_error = (err instanceof Error ? err.message : String(err)).slice(0, 200);
    }
  }

  return Response.json(body, { headers: corsHeaders() });
}

// Vapi custom-tool webhook contract (per docs.vapi.ai/tools/custom-tools-troubleshooting,
// confirmed 2026-06-27 by deep-research after the 13:20 vapifault-google-400 incident):
//
//   - `result` and `error` MUST be SINGLE-LINE STRINGS. Objects/arrays are silently
//     stringified by Vapi with an encoding path that has mangled non-ASCII bytes
//     (this is exactly how `lundi 29 juin a 10h` arrived at Gemini as mojibake).
//   - Always return HTTP 200, even on error. Any other status is ignored.
//   - No newlines inside the string (line breaks cause parsing errors).
//
// We compose plain-English single-line summaries the LLM can read directly, with
// machine-parseable structure preserved in [brackets] so Gemini can extract slot_id
// for book_slot. Defense in depth: humanEn() already returns ASCII only.
function formatSlotsForLlm(slots: Array<{ slot_id: string; display: string }>): string {
  if (slots.length === 0) {
    return "No slots available in the next 14 days. Recommend transferring to clinic.";
  }
  const parts = slots.map((s, i) => `(${i + 1}) ${s.display} [slot_id=${s.slot_id}]`);
  return `Available slots: ${parts.join("; ")}.`;
}

function formatBookingForLlm(b: { status: string; event_id?: string; display?: string; reason?: string }): string {
  if (b.status === "confirmed") {
    return `Booking confirmed: ${b.display ?? "(time unavailable)"} [event_id=${b.event_id ?? "unknown"}].`;
  }
  if (b.status === "duplicate") {
    return `Slot already booked; tell the caller it just got taken and offer to re-list available slots.`;
  }
  return `Booking failed: ${b.reason ?? "unknown reason"}. Tell the caller you are hitting a technical issue and a staff member will call back within the hour.`;
}

async function handleListSlots(req: Request, env: Env): Promise<Response> {
  const payload = await req.json().catch(() => ({}));
  const calls = extractToolCalls(payload);
  const results = await Promise.all(
    calls.map(async (tc) => {
      try {
        const args = parseArgs(tc);
        const treatment = typeof args.treatment === "string" ? args.treatment : "consultation";
        const days_offset = typeof args.days_offset === "number" ? args.days_offset : 0;
        const slots = await calListSlots(env, treatment, days_offset);
        return { toolCallId: tc.id, result: formatSlotsForLlm(slots) };
      } catch (err) {
        return {
          toolCallId: tc.id,
          error: (err instanceof Error ? err.message : String(err)).slice(0, 200),
        };
      }
    })
  );
  return Response.json({ results }, { headers: corsHeaders() });
}

async function handleBookSlot(req: Request, env: Env): Promise<Response> {
  const payload = await req.json().catch(() => ({}));
  const calls = extractToolCalls(payload);
  const results = await Promise.all(
    calls.map(async (tc) => {
      try {
        const args = parseArgs(tc);
        const slot_id = String(args.slot_id ?? "");
        const caller_name = String(args.caller_name ?? "");
        const callback = String(args.callback ?? "");
        const treatment = String(args.treatment ?? "consultation");
        if (!slot_id || !caller_name || !callback) {
          return { toolCallId: tc.id, error: "missing required args" };
        }
        const booking = await calBookSlot(env, slot_id, caller_name, callback, treatment);
        return { toolCallId: tc.id, result: formatBookingForLlm(booking) };
      } catch (err) {
        return {
          toolCallId: tc.id,
          error: (err instanceof Error ? err.message : String(err)).slice(0, 200),
        };
      }
    })
  );
  return Response.json({ results }, { headers: corsHeaders() });
}

// --- Retell custom-function handlers ---
// Body shape (Payload: args only mode): { treatment?: string, days_offset?: number, ... }
// Response shape: arbitrary JSON; Retell pulls fields via response_variables JSON paths.

async function handleRetellListSlots(req: Request, env: Env): Promise<Response> {
  let body: Record<string, unknown> = {};
  try {
    body = (await req.json()) as Record<string, unknown>;
  } catch {
    body = {};
  }
  const argsObj = (body.args ?? body) as Record<string, unknown>;
  const treatment = typeof argsObj.treatment === "string" ? argsObj.treatment : "consultation";
  const days_offset = typeof argsObj.days_offset === "number" ? argsObj.days_offset : 0;
  try {
    const slots = await calListSlots(env, treatment, days_offset);
    return Response.json(
      { ok: true, summary: formatSlotsForLlm(slots), slots },
      { headers: corsHeaders() }
    );
  } catch (err) {
    return Response.json(
      { ok: false, summary: "Could not retrieve slots; tell the caller you are hitting a technical issue and offer to transfer.", error: (err instanceof Error ? err.message : String(err)).slice(0, 200) },
      { headers: corsHeaders() }
    );
  }
}

async function handleRetellBookSlot(req: Request, env: Env): Promise<Response> {
  let body: Record<string, unknown> = {};
  try {
    body = (await req.json()) as Record<string, unknown>;
  } catch {
    body = {};
  }
  const argsObj = (body.args ?? body) as Record<string, unknown>;
  const slot_id = String(argsObj.slot_id ?? "");
  const caller_name = String(argsObj.caller_name ?? "");
  const callback = String(argsObj.callback ?? "");
  const treatment = String(argsObj.treatment ?? "consultation");
  if (!slot_id || !caller_name || !callback) {
    return Response.json(
      { ok: false, summary: "Missing required booking details; ask the caller for the missing item." },
      { headers: corsHeaders() }
    );
  }
  try {
    const booking = await calBookSlot(env, slot_id, caller_name, callback, treatment);
    return Response.json(
      { ok: true, summary: formatBookingForLlm(booking), booking },
      { headers: corsHeaders() }
    );
  } catch (err) {
    return Response.json(
      { ok: false, summary: "Booking failed; tell the caller you are hitting a technical issue and a staff member will call back.", error: (err instanceof Error ? err.message : String(err)).slice(0, 200) },
      { headers: corsHeaders() }
    );
  }
}

export default {
  async fetch(req: Request, env: Env, _ctx: ExecutionContext): Promise<Response> {
    const url = new URL(req.url);

    if (req.method === "OPTIONS") {
      return new Response(null, { headers: corsHeaders() });
    }

    if (req.method === "GET" && url.pathname === "/") {
      return new Response(
        renderWidget({
          publicKey: env.VAPI_PUBLIC_KEY ?? "",
          assistantId: env.VAPI_ASSISTANT_ID ?? "",
          clinicName: env.CLINIC_NAME,
        }),
        {
          headers: { "Content-Type": "text/html; charset=utf-8" },
        }
      );
    }

    if (req.method === "GET" && url.pathname === "/api/health") {
      return await handleHealth(req, env);
    }

    if (req.method === "POST" && url.pathname === "/vapi/tools/list_slots") {
      return await handleListSlots(req, env);
    }

    if (req.method === "POST" && url.pathname === "/vapi/tools/book_slot") {
      return await handleBookSlot(req, env);
    }

    // Retell custom-function endpoints. Retell ships args directly in the body
    // (when 'Payload: args only' is enabled in the function config) and expects
    // a plain JSON object back -- the 'response_variables' mapping pulls fields
    // out via JSON-path. We return the same English-formatted string the Vapi
    // path returns, plus the raw slots array for variable extraction.
    if (req.method === "POST" && url.pathname === "/retell/tools/list_slots") {
      return await handleRetellListSlots(req, env);
    }

    if (req.method === "POST" && url.pathname === "/retell/tools/book_slot") {
      return await handleRetellBookSlot(req, env);
    }

    return new Response("not found", { status: 404, headers: corsHeaders() });
  },
} satisfies ExportedHandler<Env>;
