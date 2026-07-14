/**
 * self_outbound_webhook_worker
 * ===========================
 * Cloudflare Worker that receives Instantly webhook events for the
 * self_outbound_system_v2 campaign, HMAC-verifies the signature, persists the
 * event to KV (SUPP_EVENTS binding), and fires a Telegram alert.
 *
 * Endpoints:
 *   GET  /health        -> 200 {ok, ts}
 *   POST /instantly     -> ingests an Instantly webhook payload
 *   POST /manual        -> operator-only: manually add a suppression (X-Worker-Secret required)
 *
 * KV shape:
 *   key   = `event:<iso-timestamp>:<random-suffix>`
 *   value = { type, email, reason, source, campaign_tag, received_at,
 *             raw: <full instantly payload> }
 *
 * The local sync script pulls all `event:*` keys, calls
 * suppression_writer.add_bulk(), and deletes consumed keys.
 *
 * Event mapping (Instantly type -> suppression reason):
 *   reply_received (+ negative sentiment upstream) -> negative_reply
 *   email_bounced                                  -> hard_bounce
 *   unsubscribed                                   -> unsubscribe_click
 *   marked_as_spam                                 -> spam_complaint
 *   other                                          -> other (still logged)
 *
 * Auth:
 *   Instantly HMAC-SHA256 signature in header `X-Instantly-Signature`
 *   (hex-encoded). We recompute over the raw body with INSTANTLY_WEBHOOK_SECRET.
 *   Constant-time compare to prevent timing side-channels.
 */

// Map Instantly event types to our suppression reasons.
const REASON_MAP = {
  reply_received: "negative_reply", // upstream sentiment classifier should filter to negatives before firing
  email_bounced: "hard_bounce",
  bounce: "hard_bounce",
  unsubscribed: "unsubscribe_click",
  unsubscribe: "unsubscribe_click",
  marked_as_spam: "spam_complaint",
  spam_complaint: "spam_complaint",
};

const JSON_HEADERS = { "content-type": "application/json; charset=utf-8" };

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), { status, headers: JSON_HEADERS });
}

async function hmacSha256Hex(secret, message) {
  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey(
    "raw",
    enc.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );
  const sig = await crypto.subtle.sign("HMAC", key, enc.encode(message));
  return [...new Uint8Array(sig)]
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

// Timing-safe constant-time string compare. Both args must be same length.
function ctEqual(a, b) {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

function isoNow() {
  return new Date().toISOString();
}

function randomSuffix() {
  // 6-char base36 random suffix. crypto.getRandomValues -> avoid Math.random.
  const buf = new Uint32Array(1);
  crypto.getRandomValues(buf);
  return buf[0].toString(36).padStart(6, "0").slice(0, 6);
}

async function telegramAlert(env, text) {
  const token = env.TELEGRAM_BOT_TOKEN;
  const chatId = env.TELEGRAM_CHAT_ID;
  if (!token || !chatId) return; // alerts optional
  const url = `https://api.telegram.org/bot${token}/sendMessage`;
  try {
    const body = new URLSearchParams({
      chat_id: chatId,
      text,
      parse_mode: "Markdown",
    });
    const res = await fetch(url, {
      method: "POST",
      body,
      headers: { "content-type": "application/x-www-form-urlencoded" },
    });
    if (!res.ok) {
      console.warn("telegram alert non-2xx:", res.status);
    }
  } catch (err) {
    // Alert is nice-to-have. Log and swallow — don't fail the webhook write.
    console.warn("telegram alert failed (swallowed):", err.message);
  }
}

function extractEmail(payload) {
  // Instantly webhook payloads vary by event type. Try common fields.
  return (
    payload?.lead_email ||
    payload?.email ||
    payload?.recipient ||
    payload?.to ||
    payload?.data?.email ||
    ""
  ).toLowerCase().trim();
}

function extractType(payload) {
  return (payload?.event_type || payload?.type || payload?.event || "").toLowerCase();
}

async function handleInstantly(request, env) {
  const rawBody = await request.text();
  const sigHeader = request.headers.get("x-instantly-signature") || "";
  const secret = env.INSTANTLY_WEBHOOK_SECRET;

  if (!secret) {
    return json({ ok: false, error: "worker missing INSTANTLY_WEBHOOK_SECRET" }, 500);
  }
  if (!sigHeader) {
    return json({ ok: false, error: "missing X-Instantly-Signature header" }, 401);
  }

  const expected = await hmacSha256Hex(secret, rawBody);
  if (!ctEqual(sigHeader.trim().toLowerCase(), expected.toLowerCase())) {
    return json({ ok: false, error: "invalid signature" }, 401);
  }

  let payload;
  try {
    payload = JSON.parse(rawBody);
  } catch {
    return json({ ok: false, error: "invalid JSON body" }, 400);
  }

  const type = extractType(payload);
  const email = extractEmail(payload);
  const reason = REASON_MAP[type] || "other";
  const receivedAt = isoNow();

  if (!email || !email.includes("@")) {
    // Log but don't fail — some Instantly events (test webhook, campaign-level) have no email.
    console.log(`event ${type}: no email, skipping suppression enqueue`);
    return json({ ok: true, note: "no email in payload, event logged but not enqueued", type });
  }

  if (!env.SUPP_EVENTS) {
    return json({ ok: false, error: "worker missing SUPP_EVENTS KV binding" }, 500);
  }

  const record = {
    type,
    email,
    reason,
    source: "webhook",
    campaign_tag: env.CAMPAIGN_TAG || "unknown",
    received_at: receivedAt,
    raw: payload,
  };

  const key = `event:${receivedAt}:${randomSuffix()}`;
  await env.SUPP_EVENTS.put(key, JSON.stringify(record), {
    // 30-day TTL — local sync should have consumed it long before then;
    // TTL prevents runaway KV growth if sync ever stops.
    expirationTtl: 30 * 24 * 60 * 60,
  });

  const alertText =
    `*outbound-webhook* \`${type}\`\n` +
    `email: \`${email}\`\n` +
    `reason: \`${reason}\`\n` +
    `campaign: \`${record.campaign_tag}\`\n` +
    `at: \`${receivedAt}\`\n` +
    `kv-key: \`${key}\``;
  await telegramAlert(env, alertText);

  return json({ ok: true, enqueued: key, type, email, reason });
}

async function handleManual(request, env) {
  // Operator-only endpoint to manually enqueue a suppression from CLI/curl.
  // Auth via X-Worker-Secret; distinct from the Instantly HMAC so a leaked
  // Instantly key doesn't grant manual-write access.
  const workerSecret = env.WORKER_SECRET;
  if (!workerSecret) {
    return json({ ok: false, error: "worker missing WORKER_SECRET (manual endpoint disabled)" }, 500);
  }
  const provided = request.headers.get("x-worker-secret") || "";
  if (!ctEqual(provided, workerSecret)) {
    return json({ ok: false, error: "unauthorized" }, 401);
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return json({ ok: false, error: "invalid JSON body" }, 400);
  }

  const email = (body.email || "").toLowerCase().trim();
  const reason = body.reason || "manual_add";
  if (!email || !email.includes("@")) {
    return json({ ok: false, error: "email required" }, 400);
  }

  if (!env.SUPP_EVENTS) {
    return json({ ok: false, error: "worker missing SUPP_EVENTS KV binding" }, 500);
  }

  const receivedAt = isoNow();
  const record = {
    type: "manual",
    email,
    reason,
    source: "manual",
    campaign_tag: env.CAMPAIGN_TAG || "unknown",
    received_at: receivedAt,
    raw: body,
  };

  const key = `event:${receivedAt}:${randomSuffix()}`;
  await env.SUPP_EVENTS.put(key, JSON.stringify(record), {
    expirationTtl: 30 * 24 * 60 * 60,
  });

  const alertText =
    `*outbound-webhook* \`manual\`\n` +
    `email: \`${email}\`\n` +
    `reason: \`${reason}\`\n` +
    `at: \`${receivedAt}\``;
  await telegramAlert(env, alertText);

  return json({ ok: true, enqueued: key, email, reason });
}

async function handleHealth(env) {
  const kvBound = Boolean(env.SUPP_EVENTS);
  const secretBound = Boolean(env.INSTANTLY_WEBHOOK_SECRET);
  const alertBound = Boolean(env.TELEGRAM_BOT_TOKEN && env.TELEGRAM_CHAT_ID);
  const manualBound = Boolean(env.WORKER_SECRET);
  return json({
    ok: true,
    ts: isoNow(),
    campaign_tag: env.CAMPAIGN_TAG || null,
    kv_bound: kvBound,
    hmac_secret_bound: secretBound,
    telegram_alert_bound: alertBound,
    manual_endpoint_bound: manualBound,
  });
}

export default {
  async fetch(request, env, _ctx) {
    const url = new URL(request.url);
    const method = request.method.toUpperCase();

    if (method === "GET" && url.pathname === "/health") {
      return handleHealth(env);
    }
    if (method === "POST" && url.pathname === "/instantly") {
      return handleInstantly(request, env);
    }
    if (method === "POST" && url.pathname === "/manual") {
      return handleManual(request, env);
    }
    return json({ ok: false, error: "not found" }, 404);
  },
};
