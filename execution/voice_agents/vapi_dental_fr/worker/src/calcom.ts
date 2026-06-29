// Cal.com v2 client — slot listing + booking creation.
// Docs: https://cal.com/docs (header `cal-api-version: 2026-02-25`)

import type { Env } from "./index.js";

const CAL_API_BASE = "https://api.cal.com/v2";
// Cal.com v2 quirk (June 2026 direct probe): per-endpoint api versions differ.
//   /v2/slots    -> 2024-09-04 works, 2026-02-25 returns 404
//   /v2/bookings -> 2024-08-13 works (returns 201), 2024-09-04 returns 404
// Verified by hitting the live endpoints with each version 2026-06-27.
const CAL_API_VERSION_SLOTS    = "2024-09-04";
const CAL_API_VERSION_BOOKINGS = "2024-08-13";

export interface Slot {
  slot_id: string;
  start_iso: string;
  display: string;
  treatment: string;
}

export interface BookingResult {
  status: "confirmed" | "duplicate" | "error";
  event_id?: string;
  display?: string;
  reason?: string;
}

// English-only demo. The prior French slot strings ("lundi 29 juin a 10h") shipped
// the U+00E0 accented character through the Worker -> Vapi -> Gemini hop and got
// double-encoded into mojibake (U+00C3 U+00A0), which Gemini's strict content
// validator rejected with HTTP 400 -- call dropped silently after Lisa said
// "One moment." (operator listen-test 2026-06-27 13:20). Switching to ASCII
// English eliminates the corruption path entirely and matches the demo's
// English-only voice (en-US-AriaNeural). All output here MUST stay ASCII.
function humanEn(iso: string, tz: string): string {
  const d = new Date(iso);
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: tz, weekday: "long", day: "numeric", month: "long",
    hour: "numeric", minute: "2-digit", hour12: true,
  }).formatToParts(d);
  const get = (t: string) => parts.find((p) => p.type === t)?.value ?? "";
  return `${get("weekday")} ${get("month")} ${get("day")} at ${get("hour")}:${get("minute")} ${get("dayPeriod")}`;
}

function calHeaders(env: Env, kind: "slots" | "bookings"): HeadersInit {
  if (!env.CALCOM_API_KEY) throw new Error("CALCOM_API_KEY not set");
  return {
    Authorization: `Bearer ${env.CALCOM_API_KEY}`,
    "cal-api-version": kind === "slots" ? CAL_API_VERSION_SLOTS : CAL_API_VERSION_BOOKINGS,
    "Content-Type": "application/json",
  };
}

export async function calListSlots(
  env: Env,
  treatment: string,
  daysOffset: number
): Promise<Slot[]> {
  const username = env.CALCOM_USERNAME ?? "debanjan-mazumdar-ben5rd";
  const slug = env.CALCOM_EVENT_SLUG ?? "30min";
  const tz = env.CALCOM_TIMEZONE ?? "Europe/Paris";

  const now = new Date();
  // Cal.com /v2/slots expects date-only YYYY-MM-DD, not ISO datetime.
  const ymd = (d: Date) => d.toISOString().slice(0, 10);
  const start = ymd(new Date(now.getTime() + Math.max(0, daysOffset) * 86400_000));
  const end = ymd(new Date(now.getTime() + (Math.max(0, daysOffset) + 14) * 86400_000));

  const params = new URLSearchParams({
    eventTypeSlug: slug,
    username,
    start,
    end,
    timeZone: tz,
  });

  const url = `${CAL_API_BASE}/slots?${params.toString()}`;
  const r = await fetch(url, { headers: calHeaders(env, "slots") });
  if (!r.ok) {
    const body = await r.text();
    throw new Error(`cal /slots ${r.status}: ${body.slice(0, 200)}`);
  }
  const body = (await r.json()) as Record<string, unknown>;
  const data = (body.data ?? body) as unknown;

  // Cal.com v2 returns slots grouped by date OR a flat list, depending on version.
  const flat: string[] = [];
  if (data && typeof data === "object" && !Array.isArray(data)) {
    for (const daySlots of Object.values(data as Record<string, unknown>)) {
      if (Array.isArray(daySlots)) {
        for (const s of daySlots) {
          const iso = (s as { time?: string; start?: string }).time ??
                      (s as { start?: string }).start;
          if (typeof iso === "string") flat.push(iso);
        }
      }
    }
  } else if (Array.isArray(data)) {
    for (const s of data) {
      const iso = (s as { time?: string; start?: string }).time ??
                  (s as { start?: string }).start;
      if (typeof iso === "string") flat.push(iso);
    }
  }

  flat.sort();
  return flat.slice(0, 3).map((iso) => ({
    slot_id: iso,
    start_iso: iso,
    display: humanEn(iso, tz),
    treatment,
  }));
}

export async function calBookSlot(
  env: Env,
  slot_id: string,
  caller_name: string,
  callback: string,
  treatment: string
): Promise<BookingResult> {
  const username = env.CALCOM_USERNAME ?? "debanjan-mazumdar-ben5rd";
  const slug = env.CALCOM_EVENT_SLUG ?? "30min";
  const tz = env.CALCOM_TIMEZONE ?? "Europe/Paris";

  // Synthetic email from the callback number; clearly demo-only.
  const digits = callback.replace(/\D/g, "") || "demo";
  const fakeEmail = `patient-${digits}@cabinet-dentylis-demo.local`;

  const payload = {
    start: slot_id,
    attendee: { name: caller_name, email: fakeEmail, timeZone: tz },
    eventTypeSlug: slug,
    username,
    metadata: {
      treatment,
      callback_phone: callback,
      source: "voice_agent_lisa",
      demo_mode: env.DEMO_MODE,
    },
  };

  const r = await fetch(`${CAL_API_BASE}/bookings`, {
    method: "POST",
    headers: calHeaders(env, "bookings"),
    body: JSON.stringify(payload),
  });

  if (r.status === 409) {
    return { status: "duplicate", reason: (await r.text()).slice(0, 200) };
  }
  if (!r.ok) {
    throw new Error(`cal /bookings ${r.status}: ${(await r.text()).slice(0, 200)}`);
  }
  const body = (await r.json()) as Record<string, unknown>;
  const data = (body.data ?? body) as Record<string, unknown>;
  const event_id = String(data.id ?? data.uid ?? "unknown");
  const startIso = String(data.start ?? slot_id);
  return {
    status: "confirmed",
    event_id,
    display: humanEn(startIso, tz),
  };
}
