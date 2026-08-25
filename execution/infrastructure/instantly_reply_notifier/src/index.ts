/**
 * Instantly Reply Notifier - Cloudflare Worker
 *
 * Receives Instantly reply webhooks, classifies replies with hybrid
 * rules + LLM logic, and sends a Telegram notification only for replies
 * a human actually needs to see (positive / booking-ready / ambiguous).
 * Out-of-office and not-interested replies are silently dropped.
 *
 * Endpoint: POST /webhook          - your primary Instantly account
 * Endpoint: POST /webhook/client   - a second Instantly account (e.g. a client's), notify-only
 * Health:   GET  /health
 *
 * Secrets / vars (see README):
 *   TELEGRAM_BOT_TOKEN       - Telegram bot token
 *   TELEGRAM_CHAT_ID         - Telegram chat/user ID to notify
 *   OPENROUTER_API_KEY       - OpenRouter API key (LLM fallback classifier)
 *   INSTANTLY_API_KEY        - Instantly API key (only needed for the optional auto-reply)
 *   WEBHOOK_SECRET           - shared secret for /webhook
 *   WEBHOOK_SECRET_CLIENT    - shared secret for /webhook/client (MUST differ from the above)
 *   CLIENT_ACCOUNT_LABEL     - plain var, banner text for the client route (optional)
 *   DEDUP_KV                 - KV namespace binding for deduplication
 */

import { classifyByRules, classifyByLlm, shouldNotify, type ClassifyResult } from "./classifier";
import { sendTelegramMessage, buildTelegramMessage } from "./telegram";
import { AUTO_REPLY_CAMPAIGNS, buildAutoReplyBody, fetchLatestEmailRecord, sendAutoReply } from "./autoReply";

export interface Env {
  TELEGRAM_BOT_TOKEN: string;
  TELEGRAM_CHAT_ID: string;
  OPENROUTER_API_KEY: string;
  INSTANTLY_API_KEY: string;
  WEBHOOK_SECRET: string;
  WEBHOOK_SECRET_CLIENT: string;
  CLIENT_ACCOUNT_LABEL?: string;
  DEDUP_KV: KVNamespace;
}

interface InstantlyWebhookPayload {
  event_type?: string;
  timestamp?: string;
  lead_email?: string;
  firstName?: string;
  lastName?: string;
  companyName?: string;
  campaign_name?: string;
  campaign_id?: string;
  email_account?: string;
  reply_text_snippet?: string;
  reply_text?: string;
  reply_subject?: string;
}

const DEDUP_TTL_SECONDS = 120;

/** Small non-cryptographic hash (djb2), used only to make dedup keys content-aware. */
function shortHash(input: string): string {
  let h = 5381;
  for (let i = 0; i < input.length; i++) {
    h = ((h << 5) + h + input.charCodeAt(i)) | 0;
  }
  return (h >>> 0).toString(36);
}

/** Constant-time string compare - a plain !== leaks the secret via timing. */
function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) {
    diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return diff === 0;
}

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);

    if (url.pathname === "/health") {
      // Report which secrets are bound (never their values). Without this, a
      // worker with no TELEGRAM_BOT_TOKEN looks identical to a healthy one
      // right up until a real reply lands and silently goes nowhere.
      return Response.json({
        status: "ok",
        timestamp: new Date().toISOString(),
        telegram_bound: Boolean(env.TELEGRAM_BOT_TOKEN && env.TELEGRAM_CHAT_ID),
        openrouter_bound: Boolean(env.OPENROUTER_API_KEY),
        kv_bound: Boolean(env.DEDUP_KV),
        webhook_secret_bound: Boolean(env.WEBHOOK_SECRET),
        client_route_secret_bound: Boolean(env.WEBHOOK_SECRET_CLIENT),
        auto_reply_campaigns: Object.keys(AUTO_REPLY_CAMPAIGNS).length,
      });
    }

    if (url.pathname === "/webhook" && request.method === "POST") {
      return handleWebhook(request, env, ctx, "own");
    }

    if (url.pathname === "/webhook/client" && request.method === "POST") {
      return handleWebhook(request, env, ctx, "client");
    }

    return Response.json({ error: "Not found" }, { status: 404 });
  },
};

type Source = "own" | "client";

async function handleWebhook(request: Request, env: Env, ctx: ExecutionContext, source: Source): Promise<Response> {
  // Webhook secret validation - each source has its own secret so a leak on
  // one Instantly account's webhook config can't forge requests to the other's route.
  const expectedSecret = source === "client" ? env.WEBHOOK_SECRET_CLIENT : env.WEBHOOK_SECRET;

  // Fail CLOSED. Previously a missing secret silently disabled auth entirely,
  // so forgetting `wrangler secret put` turned the route into an open endpoint
  // that anyone knowing the URL could push fake replies into.
  if (!expectedSecret) {
    console.error(`[webhook] Refusing ${source} request: secret not configured for this route`);
    return Response.json({ error: "Route not configured" }, { status: 500 });
  }

  const secret = request.headers.get("X-Webhook-Secret");
  if (!secret || !timingSafeEqual(secret, expectedSecret)) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  let body: InstantlyWebhookPayload;
  try {
    body = (await request.json()) as InstantlyWebhookPayload;
  } catch {
    return Response.json({ error: "Invalid JSON" }, { status: 400 });
  }

  // Only process reply_received and auto_reply_received events
  const eventType = body.event_type ?? "";
  if (!["reply_received", "auto_reply_received"].includes(eventType)) {
    console.log(`[webhook] Skipping event type: ${eventType}`);
    return Response.json({ ok: true, skipped: true, reason: "not_a_reply" });
  }

  // --- Extract fields ---
  const firstName = body.firstName ?? "";
  const lastName = body.lastName ?? "";
  const name = [firstName, lastName].filter(Boolean).join(" ") || "Unknown";
  const email = body.lead_email ?? "N/A";
  const company = body.companyName ?? "N/A";
  const campaign = body.campaign_name ?? "N/A";
  const subject = body.reply_subject ?? "";
  const replyText = (body.reply_text_snippet ?? body.reply_text ?? "").substring(0, 500);
  const isAutoReply = eventType === "auto_reply_received";

  // A reply with no extractable text is still a reply. Instantly returns empty
  // text for image-only and some HTML-only bodies. Dropping these silently -
  // with no log line and no notification - loses a real lead invisibly, which
  // is the one outcome this worker exists to prevent. Fail open instead: notify
  // and let the operator open the thread in Instantly.
  const hasNoText = !replyText && !isAutoReply;
  if (hasNoText) {
    console.warn(`[webhook] Reply had no extractable text - notifying anyway | lead: ${email}`);
  }

  // --- Deduplication via KV ---
  // The key includes a hash of the reply body. Keying on subject alone collided
  // across distinct replies in one thread - email threads reuse "Re: <subject>"
  // for every message - so a lead who wrote "not interested" and then, seconds
  // later, "actually wait, tell me more" had the second message dropped as a
  // duplicate. The content hash makes distinct text a distinct event.
  const dedupKey = `dedup:${source}-${eventType}-${body.campaign_id ?? body.campaign_name ?? ""}-${body.lead_email ?? ""}-${shortHash(subject + "|" + replyText)}`;
  try {
    const existing = await env.DEDUP_KV.get(dedupKey);
    if (existing) {
      console.log(`[webhook] Duplicate event filtered`);
      return Response.json({ ok: true, skipped: true, reason: "duplicate" });
    }
    // Fire-and-forget: don't let a slow KV write block the response
    ctx.waitUntil(
      env.DEDUP_KV.put(dedupKey, "1", { expirationTtl: DEDUP_TTL_SECONDS }).catch((e) =>
        console.error("[webhook] KV dedup write failed:", e)
      )
    );
  } catch (kvErr) {
    // KV failure: log and continue without dedup (better than returning 500 to Instantly)
    console.error("[webhook] KV dedup error:", kvErr);
  }

  console.log(`[webhook] Processing reply | event: ${eventType} | campaign: ${campaign}`);

  // --- Classification ---
  let result: ClassifyResult;

  if (hasNoText) {
    // No text means nothing to classify. "unknown" is already in the notify
    // allowlist, so this reaches the phone.
    result = { category: "unknown", confidence: 0, method: "failopen" };
  } else {
  const rulesResult = classifyByRules(replyText, isAutoReply);
  if (rulesResult !== null) {
    result = rulesResult;
    console.log(`[classify] Rules -> ${result.category}`);
  } else {
    // Unknown - call LLM
    console.log(`[classify] No rule match, calling LLM...`);
    result = await classifyByLlm(replyText, env.OPENROUTER_API_KEY);
    console.log(`[classify] LLM -> ${result.category} (${result.method}, conf: ${result.confidence})`);
  }
  }

  // --- Decide whether to notify ---
  if (!shouldNotify(result)) {
    console.log(`[webhook] Not notifying - category: ${result.category}`);
    return Response.json({
      ok: true,
      notified: false,
      category: result.category,
      method: result.method,
    });
  }

  // --- Campaign-scoped auto-reply (OFF by default - read README before enabling) ---
  // Only for classifications the rules/LLM are actually confident about.
  // "unknown" is a deliberate fail-open for the human-facing Telegram ping -
  // it must NOT also trigger an unreviewed autonomous email send.
  let autoReplied = false;
  // The client route is notify-only, never auto-reply - hard gate on source,
  // independent of AUTO_REPLY_CAMPAIGNS. This gate must never regress if that map is edited.
  const eligibleForAutoReply = source === "own" && (result.category === "booking_ready" || result.category === "positive");

  if (body.campaign_id && AUTO_REPLY_CAMPAIGNS[body.campaign_id] && !isAutoReply && eligibleForAutoReply) {
    // Idempotency: one auto-reply per lead per campaign, independent of the
    // short-TTL event dedup above (which is keyed on subject/event and would
    // let a second distinct reply from the same lead through).
    const autoReplyFlagKey = `autoreplied:${body.campaign_id}:${email.toLowerCase()}`;
    try {
      const alreadySent = await env.DEDUP_KV.get(autoReplyFlagKey);
      if (alreadySent) {
        console.log(`[autoReply] Skipping - already auto-replied to lead=${email} in this campaign`);
      } else {
        const record = await fetchLatestEmailRecord(body.campaign_id, email, env.INSTANTLY_API_KEY);
        if (record) {
          const replySubject = subject ? (subject.toLowerCase().startsWith("re:") ? subject : `Re: ${subject}`) : "Re: quick follow up";
          const replyBody = buildAutoReplyBody(firstName);
          autoReplied = await sendAutoReply(record, replySubject, replyBody, env.INSTANTLY_API_KEY);
          console.log(`[autoReply] campaign=${campaign} lead=${email} sent=${autoReplied}`);
          if (autoReplied) {
            // Await (not waitUntil) so a second concurrent webhook delivery for a
            // different reply from this lead can't race past the check above.
            await env.DEDUP_KV.put(autoReplyFlagKey, "1", { expirationTtl: 60 * 60 * 24 * 180 });
          }
        } else {
          console.error(`[autoReply] No received email record found for lead=${email} campaign_id=${body.campaign_id}`);
        }
      }
    } catch (err) {
      console.error("[autoReply] Error:", err);
    }
  }

  // --- Send Telegram ---
  const message = buildTelegramMessage({
    name,
    email,
    company,
    campaign,
    subject,
    replySnippet: replyText || "(no text extracted - open the thread in Instantly)",
    category: result.category,
    autoReplied,
    accountLabel: source === "client" ? (env.CLIENT_ACCOUNT_LABEL || "Client Account") : undefined,
  });

  let notified = false;
  let notifyError: string | undefined;

  try {
    await sendTelegramMessage(env.TELEGRAM_BOT_TOKEN, env.TELEGRAM_CHAT_ID, message);
    notified = true;
    console.log(`[webhook] Telegram notified | category: ${result.category} | method: ${result.method} | autoReplied: ${autoReplied}`);
  } catch (err) {
    notifyError = String(err);
    console.error(`[webhook] Telegram send error:`, notifyError);
    // Still return 200 - Instantly retries non-2xx, and a retry would not fix a
    // bad token or an unreachable chat. But report notified:false honestly so
    // the smoke test and `wrangler tail` can tell "dropped on purpose" apart
    // from "tried to reach the phone and failed".
  }

  return Response.json({
    ok: true,
    notified,
    ...(notifyError ? { notify_error: notifyError } : {}),
    autoReplied,
    category: result.category,
    method: result.method,
  });
}
