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
      body.sample_slot = slots[0]?.human_fr ?? null;
    } catch (err) {
      body.cal_reachable = false;
      body.cal_error = (err instanceof Error ? err.message : String(err)).slice(0, 200);
    }
  }

  return Response.json(body, { headers: corsHeaders() });
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
        return { toolCallId: tc.id, result: { slots } };
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
        return { toolCallId: tc.id, result: booking };
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

    return new Response("not found", { status: 404, headers: corsHeaders() });
  },
} satisfies ExportedHandler<Env>;
