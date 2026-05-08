/**
 * Accessory Masters API + AI Responder — Cloudflare Worker
 *
 * HTTP Routes:
 *   POST /api/form-submit       — Contact form -> GoHighLevel
 *   GET  /api/dashboard         — Aggregated metrics from Instantly + GHL
 *   POST /api/webhook/reply     — Instantly reply webhook (triggers processing)
 *   GET  /api/variants          — Campaign variant analytics
 *   POST /api/process-replies   — Manual trigger for reply processing
 *
 * Scheduled:
 *   Cron every 30 min           — Poll Instantly for new replies, classify, route, auto-reply
 *
 * Secrets (wrangler secret put):
 *   GHL_API_KEY, INSTANTLY_API_KEY, OPENROUTER_API_KEY
 *   TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID (when provided)
 *
 * KV Namespace:
 *   REPLY_STATE — tracks processed reply IDs
 */

// ---------------------------------------------------------------------------
// Config (from config/accessory_masters.json — embedded for performance)
// ---------------------------------------------------------------------------

const CONFIG = {
  classification: {
    model: "anthropic/claude-haiku-4.5",
    system_prompt:
      "Classify this cold email reply as exactly one of: hot_positive, positive, negative, neutral.\n" +
      "hot_positive = prospect gives a phone number, says ready to sell, wants to schedule a call immediately\n" +
      "positive = interested in selling, wants to talk, asks about the process, engages with conditions or involves others (accountant, partner)\n" +
      "negative = not interested, asks to be removed, hostile, unsubscribe, already sold the business\n" +
      "neutral = out of office, auto-reply, bounce, unclear intent, vague hedging with no engagement\n\n" +
      "Examples:\n" +
      '"Call me at 713-555-0888, I\'m ready to sell." -> hot_positive\n' +
      '"Yes, tell me more about the process." -> positive\n' +
      '"I\'m interested but not ready yet. Maybe next year." -> positive\n' +
      '"If the price is right, I\'d consider it." -> positive\n' +
      '"Yes" -> positive\n' +
      '"Not interested, remove me from your list." -> negative\n' +
      '"Too late, sold the business last month." -> negative\n' +
      '"Don\'t call me at 555-0199 again. Remove me." -> negative\n' +
      '"Out of office until Monday." -> neutral\n' +
      '"Maybe. Depends on the price." -> neutral\n\n' +
      "Reply with exactly one word: hot_positive, positive, negative, or neutral.",
    valid_classes: ["hot_positive", "positive", "negative", "neutral"],
  },
  auto_reply: {
    enabled: true,
    model: "anthropic/claude-haiku-4.5",
    max_sentences: 3,
    max_words: 60,
    sender_persona:
      "Aleksandar, business broker backed by Hedgestone Capital Group",
    guard_rails: [
      "Never promise specific valuations",
      "Never use exclamation marks",
      "Never write more than 3 sentences",
      "Never mention AI or automation",
      "Never use sales-y or corporate language",
    ],
    hot_lead_signals: [
      "phone number",
      "my number",
      "call me at",
      "ready to sell",
      "want to sell",
      "schedule a call",
    ],
    objection_responses: {
      not_ready: {
        triggers: [
          "not ready",
          "not right now",
          "maybe later",
          "not the right time",
        ],
        response:
          "Totally understand. Actually, now's a great time to at least get a valuation — the market's moving fast. No pressure, happy to chat whenever.",
      },
      valuation: {
        triggers: [
          "how much",
          "what's it worth",
          "business worth",
          "valuation",
        ],
        response:
          "Depends on a few things — revenue, industry, location. I can give you a rough range on a quick call. Want to set one up?",
      },
      who_are_you: {
        triggers: [
          "who are you",
          "who is this",
          "what company",
          "never heard of",
        ],
        response:
          "I'm Alex with Accessory Masters, backed by Hedgestone Capital Group. We've closed over $100M in deals. Happy to share more on a call.",
      },
    },
  },
  ghl: {
    api_url: "https://services.leadconnectorhq.com",
    api_version: "2021-07-28",
    pipeline_id: "WbV29bqIWVC0idhvmvqg",
    pipeline_stages: {
      new: "b8a7ff51-11c5-4775-a229-d3d9d19b1c9a",
      interested: "5729dba8-bd1d-4333-89e3-7ce804a71f57",
    },
    tags: ["cold email", "positive reply"],
    source: "cold email pipeline",
    calendar_id: "0bwcyzJOtxKScDfIDCRw",
    custom_fields: { reply_text: "tUwBgk4HB3kS3ZDje45P", revenue_range: "RC5rvAO6J65tGFFHs0Ib" },
  },
  tone: {
    voice: "I",
    sender_name: "Aleksandar",
    tone_description:
      "Blunt, direct, no fluff. Like a text message from someone who doesn't waste your time. No exclamation marks. No sales-y language.",
    auto_reply_instruction:
      "Write 2-3 short sentences max. Sound like a human text.",
    opener_instruction:
      "Write a single sentence referencing something specific about the prospect's business — their industry, location, review count, or a notable detail. Keep it under 20 words. No exclamation marks. No questions. Just a factual observation that shows you looked them up.",
    never_say: [
      "exciting opportunity", "game-changing", "transform your", "synergy",
      "leverage", "utilize", "solution", "partnership", "disrupt",
      "innovative", "cutting-edge", "best-in-class", "reach out",
      "touch base", "circle back", "take it to the next level",
    ],
    example_openers: [
      "I noticed your car wash on Main St has been open since 2012.",
      "Your pizzeria has 200+ reviews and a 4.7 rating — that's hard to pull off in Houston.",
      "I saw your laundromat expanded to a second location last year.",
    ],
  },
  icp: {
    industries: [
      "car wash", "pizzeria", "laundromat", "marina", "small oil company",
      "auto repair", "dry cleaner", "bakery", "printing shop", "pest control",
      "manufacturing", "professional services",
    ],
    geography: {
      city: "Houston",
      state: "TX",
      include_suburbs: true,
      suburbs: ["Katy", "Sugar Land", "The Woodlands", "Pearland", "Pasadena"],
    },
  },
  sourcing: {
    serper_results_per_query: 100,
    serper_api_url: "https://google.serper.dev/maps",
    use_prospeo_for: [],
  },
  enrichment: {
    anymailfinder_person_url: "https://api.anymailfinder.com/v5.0/search/person.json",
    anymailfinder_company_url: "https://api.anymailfinder.com/v5.0/search/company.json",
    anymailfinder_min_confidence: 50,
    million_verifier_url: "https://api.millionverifier.com/api/v3",
    million_verifier_accept: ["ok", "catch_all", "unknown"],
  },
  personalization: {
    model: "anthropic/claude-haiku-4.5",
    max_opener_tokens: 100,
    batch_size: 50,
  },
  instantly: {
    api_url: "https://api.instantly.ai/api/v2",
    upload_rate_limit_ms: 200,
    field_mapping: {
      email: "owner_email",
      first_name_from: "owner_name",
      last_name_from: "owner_name",
      company_name: "business_name",
      custom_variables: { opener: "personalized_opener", industry: "industry", city: "city" },
    },
  },
};

const VALID_CLASSES = new Set(CONFIG.classification.valid_classes);

// ---------------------------------------------------------------------------
// Main Worker
// ---------------------------------------------------------------------------

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const { pathname } = url;
    const method = request.method;

    if (method === "OPTIONS") {
      return corsResponse(request, env, new Response(null, { status: 204 }));
    }

    try {
      if (method === "POST" && pathname === "/api/form-submit") {
        return corsResponse(request, env, await handleFormSubmit(request, env));
      }

      if (method === "GET" && pathname === "/api/dashboard") {
        if (!checkAdminAuth(request, env)) {
          return corsResponse(request, env, jsonResponse({ error: "Unauthorized" }, 401));
        }
        return corsResponse(request, env, await handleDashboard(url, env));
      }

      if (method === "POST" && pathname === "/api/webhook/reply") {
        return corsResponse(
          request,
          env,
          await handleReplyWebhook(request, env),
        );
      }

      if (method === "GET" && pathname === "/api/variants") {
        if (!checkAdminAuth(request, env)) {
          return corsResponse(request, env, jsonResponse({ error: "Unauthorized" }, 401));
        }
        return corsResponse(request, env, await handleVariants(url, env));
      }

      if (method === "POST" && pathname === "/api/process-replies") {
        if (!checkAdminAuth(request, env)) {
          return corsResponse(request, env, jsonResponse({ error: "Unauthorized" }, 401));
        }
        return corsResponse(
          request,
          env,
          await handleManualProcess(request, env),
        );
      }

      if (method === "POST" && pathname === "/api/run-pipeline") {
        if (!checkAdminAuth(request, env)) {
          return corsResponse(request, env, jsonResponse({ error: "Unauthorized" }, 401));
        }
        return corsResponse(
          request,
          env,
          await handleRunPipeline(request, env),
        );
      }

      if (method === "GET" && pathname === "/api/pipeline-status") {
        if (!checkAdminAuth(request, env)) {
          return corsResponse(request, env, jsonResponse({ error: "Unauthorized" }, 401));
        }
        return corsResponse(
          request,
          env,
          await handlePipelineStatus(env),
        );
      }

      if (method === "POST" && pathname === "/api/weekly-report") {
        if (!checkAdminAuth(request, env)) {
          return corsResponse(request, env, jsonResponse({ error: "Unauthorized" }, 401));
        }
        return corsResponse(
          request,
          env,
          await handleWeeklyReport(env),
        );
      }

      return corsResponse(
        request,
        env,
        jsonResponse({ error: "Not found" }, 404),
      );
    } catch (err) {
      console.error("Unhandled error:", err);
      return corsResponse(
        request,
        env,
        jsonResponse({ success: false, error: "Internal server error" }, 500),
      );
    }
  },

  async scheduled(event, env, ctx) {
    const cron = event.cron;
    if (cron === "0 6 * * *") {
      ctx.waitUntil(runDailyPipeline(env));
    } else if (cron === "0 7 * * 1") {
      ctx.waitUntil(runWeeklyReport(env));
    } else {
      // Every 30 min: process delayed replies first, then poll for new ones
      ctx.waitUntil(
        processDelayedReplies(env).then(() => pollAndProcessReplies(env)),
      );
    }
  },
};

// ===================================================================
// AI RESPONDER PIPELINE
// ===================================================================

/**
 * Main orchestration: poll Instantly, classify, route, auto-reply.
 */
async function pollAndProcessReplies(env) {
  if (!env.INSTANTLY_API_KEY) {
    console.warn("INSTANTLY_API_KEY not set — skipping reply polling");
    return { processed: 0 };
  }
  console.log("Cron: starting reply polling");

  let replies;
  try {
    replies = await fetchInstantlyReplies(env);
  } catch (err) {
    console.error("Failed to fetch replies from Instantly:", err);
    return { error: "fetch_failed", detail: err.message };
  }

  if (!replies || replies.length === 0) {
    console.log("No new replies found");
    return { processed: 0 };
  }

  const processed = [];
  for (const raw of replies) {
    const reply = normalizeReply(raw);

    if (reply.is_auto_reply) continue;

    const replyId =
      raw.id || raw.message_id || `fallback_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;

    const already = await isAlreadyProcessed(env, replyId);
    if (already) {
      continue;
    }

    await markProcessed(env, replyId, { status: "processing", started: Date.now() });

    try {
      const result = await processReply(reply, env);
      await markProcessed(env, replyId, result);
      processed.push({ email: reply.from_email, ...result });
    } catch (err) {
      await env.REPLY_STATE?.delete(replyId);
      console.error(`Reply processing failed for ${replyId}:`, err.message);
    }
  }

  console.log(`Cron complete: ${processed.length} replies processed`);
  return { processed: processed.length, results: processed };
}

/**
 * Process a single reply: classify → route → auto-reply.
 */
async function processReply(reply, env) {
  const body = reply.body || "";

  const classification = await classifyReply(body, env);
  reply.classification = classification;
  console.log(`Classified ${reply.from_email}: ${classification}`);

  const result = { classification, action: "skip" };

  if (classification === "hot_positive" || classification === "positive") {
    const ghlResult = await routeToGHL(reply, env, classification);
    result.ghl = ghlResult;
    reply.contact_id = ghlResult?.contact_id || null;

    await sendTelegramNotification(reply, env);
    await sendSlackNotification(reply, env);

    if (classification === "hot_positive") {
      result.action = "handoff";
      result.reason = "hot lead — human takeover";
      return result;
    }
  }

  if (classification === "positive") {
    if (CONFIG.auto_reply.enabled) {
      const replyText = await generateAndSendAutoReply(reply, env);
      if (replyText) {
        result.action = "auto_reply";
        result.reply_text = replyText;
      } else {
        result.action = "ghl_only";
      }
    } else {
      result.action = "ghl_only";
    }
  }

  if (classification === "negative" || classification === "neutral") {
    result.reason = "not actionable";
  }

  return result;
}

// ---------------------------------------------------------------------------
// Reply Classification (port of reply_classifier.py:classify_real)
// ---------------------------------------------------------------------------

async function classifyReply(body, env) {
  if (!env.OPENROUTER_API_KEY) {
    console.warn("OPENROUTER_API_KEY not set — using mock classifier");
    return classifyMock(body);
  }

  try {
    const raw = await callOpenRouter(
      CONFIG.classification.system_prompt,
      body || "",
      CONFIG.classification.model,
      10,
      env,
    );

    let result = raw.trim().replace(/[.,!?"']/g, "").toLowerCase();
    result = result.replace(/\bhot\s+positive\b/i, "hot_positive");
    if (VALID_CLASSES.has(result)) return result;

    const firstWord = result.split(/\s+/)[0] || "";
    if (VALID_CLASSES.has(firstWord)) return firstWord;

    console.warn(`Unexpected classifier output: "${raw}" — defaulting to neutral`);
    return "neutral";
  } catch (err) {
    console.error("Classification failed:", err);
    return "neutral";
  }
}

function classifyMock(body) {
  const text = (body || "").toLowerCase();
  const signals = {
    hot_positive: [
      "phone number", "call me at", "my number is",
      "ready to sell", "want to sell now", "schedule a call",
    ],
    negative: [
      "not interested", "remove", "stop", "unsubscribe",
      "no thanks", "don't contact", "don't email", "don't call",
      "no longer", "already sold", "sold the business", "too late",
    ],
    neutral: ["out of office", "auto-reply", "vacation", "will return"],
    positive: [
      "interested", "sell", "process", "tell me more", "call me", "yes",
    ],
  };

  for (const signal of signals.hot_positive) {
    if (text.includes(signal)) return "hot_positive";
  }
  for (const signal of signals.negative) {
    if (text.includes(signal)) return "negative";
  }
  for (const signal of signals.neutral) {
    if (text.includes(signal)) return "neutral";
  }
  for (const signal of signals.positive) {
    if (text.includes(signal)) return "positive";
  }
  return "neutral";
}

// ---------------------------------------------------------------------------
// Auto-Reply Generation (port of auto_reply.py)
// ---------------------------------------------------------------------------

function isHotLead(body) {
  const text = (body || "").toLowerCase();
  return CONFIG.auto_reply.hot_lead_signals.some((s) => text.includes(s));
}

function matchObjection(body) {
  if (!body) return null;
  const text = body.toLowerCase();
  for (const [, obj] of Object.entries(CONFIG.auto_reply.objection_responses)) {
    if (obj.triggers.some((t) => text.includes(t))) {
      return obj;
    }
  }
  return null;
}

async function generateAndSendAutoReply(reply, env) {
  const body = reply.body || "";
  const context = `From: ${reply.from_name || ""} at ${reply.company || ""} (${reply.from_email || ""})`;

  if (isHotLead(body)) {
    console.log(`Hot lead detected for ${reply.from_email} — skipping auto-reply`);
    return null;
  }

  let replyText;
  if (!env.OPENROUTER_API_KEY) {
    const objection = matchObjection(body);
    replyText = objection
      ? objection.response
      : "Thanks for reaching out. I'd love to learn more about your business. Would a quick call this week work?";
  } else {
    replyText = await generateReplyViaLLM(body, context, env);
  }

  replyText = applyGuardRails(replyText);

  if (!replyText || !replyText.trim()) {
    console.warn(`Auto-reply for ${reply.from_email} was fully stripped by guardrails`);
    return null;
  }

  if (reply.id && reply.lead_email && env.INSTANTLY_API_KEY) {
    const delaySeconds = 120 + Math.floor(Math.random() * 300);
    const sendAfter = new Date(Date.now() + delaySeconds * 1000).toISOString();
    await queueDelayedReply(env, {
      reply_to_uuid: reply.id,
      from_email: reply.lead_email,
      reply_text: replyText,
      send_after: sendAfter,
      delay_seconds: delaySeconds,
    });
    console.log(`Auto-reply queued for ${reply.from_email} — send after ${delaySeconds}s delay`);
  } else {
    console.warn("Missing reply id, lead_email, or INSTANTLY_API_KEY — reply generated but not sent");
    return null;
  }

  return replyText;
}

async function generateReplyViaLLM(body, context, env) {
  const objection = matchObjection(body);
  let objectionSection = null;
  if (objection) {
    objectionSection =
      `The prospect's message matches this objection: "${objection.triggers[0]}"\n` +
      `Example response for this objection: "${objection.response}"\n` +
      `Use this as a guide but vary the wording naturally.`;
  }

  const systemParts = [
    CONFIG.auto_reply.sender_persona
      ? `You are ${CONFIG.auto_reply.sender_persona}.`
      : null,
    CONFIG.tone.auto_reply_instruction || "",
    CONFIG.auto_reply.guard_rails.length
      ? "Rules:\n" +
        CONFIG.auto_reply.guard_rails.map((r) => `- ${r}`).join("\n")
      : null,
    `NEVER use these words or phrases: ${CONFIG.tone.never_say.join(", ")}`,
    `NEVER mention artificial intelligence, language models, chatbots, GPT, Claude, or that you are automated.`,
    objectionSection,
  ].filter(Boolean);

  const systemPrompt = systemParts.join("\n\n");

  try {
    const result = await callOpenRouter(
      systemPrompt,
      `Reply to this email naturally:\n\n${body}\n\nContext: ${context}`,
      CONFIG.auto_reply.model,
      150,
      env,
    );
    if (!result || !result.trim()) {
      return "Thanks for getting back to me. I'll follow up shortly.";
    }
    return result;
  } catch (err) {
    console.error("Auto-reply generation failed, using fallback:", err);
    return "Thanks for getting back to me. Let me follow up with more details shortly.";
  }
}

/**
 * Post-processing pipeline (exact port of auto_reply.py lines 132-161).
 * Word truncation → dollar stripping → ! replacement → sentence enforcement.
 */
function applyGuardRails(text) {
  let result = text;

  // Word count truncation (prefer sentence boundary)
  const maxWords = CONFIG.auto_reply.max_words;
  let words = result.split(/\s+/);
  if (words.length > maxWords) {
    let truncated = words.slice(0, maxWords).join(" ");
    const lastDot = truncated.lastIndexOf(".");
    const lastQ = truncated.lastIndexOf("?");
    const lastBang = truncated.lastIndexOf("!");
    const lastEnd = Math.max(lastDot, lastQ, lastBang);
    if (lastEnd > truncated.length / 2) {
      result = truncated.slice(0, lastEnd + 1);
    } else {
      result = truncated.replace(/[,;:—-]+$/, "") + ".";
    }
  }

  // Dollar amount stripping
  if (/\$\s*[\d,]+/.test(result)) {
    result = result.replace(/\$\s*[\d,]+[A-Za-z]*/g, "");
    result = result.replace(/\s{2,}/g, " ").trim();
    let parts = result
      .split(/(?<=[.!?])\s+/)
      .map((s) => s.trim())
      .filter((s) => s);
    parts = parts.filter((s) => s.split(/\s+/).length >= 3);
    if (parts.length) {
      result = parts.join(" ");
    }
  }

  // Exclamation mark replacement
  if (result.includes("!")) {
    result = result.replaceAll("!", ".");
  }

  // Sentence count enforcement
  const maxSentences = CONFIG.auto_reply.max_sentences;
  const sentences = result
    .split(/(?<=[.!?])\s+/)
    .map((s) => s.trim())
    .filter((s) => s);
  if (sentences.length > maxSentences) {
    result = sentences.slice(0, maxSentences).join(" ");
    if (!/[.?!]$/.test(result)) {
      result += ".";
    }
  }

  // Remove sentences mentioning AI
  result = result.replace(/[^.!?]*\b(artificial intelligence|language model|chatbot|gpt|claude)\b[^.!?]*[.!?]/gi, "").trim();
  // Remove never_say phrases
  for (const phrase of CONFIG.tone.never_say) {
    result = result.replace(new RegExp(phrase, "gi"), "").trim();
  }
  // Clean up double spaces
  result = result.replace(/\s{2,}/g, " ").trim();

  return result;
}

// ---------------------------------------------------------------------------
// GHL Routing (port of ghl.py:route_positive_reply)
// ---------------------------------------------------------------------------

async function routeToGHL(reply, env, classification) {
  if (!env.GHL_API_KEY) {
    console.warn("GHL_API_KEY not set — skipping CRM routing");
    return { error: "GHL_API_KEY not set" };
  }

  const nameParts = (reply.from_name || "").trim().split(/\s+/);
  const firstName = nameParts[0] || "";
  const lastName = nameParts.length > 1 ? nameParts.slice(1).join(" ") : "";

  const ghlHeaders = {
    Authorization: `Bearer ${env.GHL_API_KEY}`,
    "Content-Type": "application/json",
    Version: CONFIG.ghl.api_version,
  };

  const result = { contact_id: null, opportunity_id: null, error: null };

  try {
    const contactRes = await fetch(
      `${CONFIG.ghl.api_url}/contacts/`,
      {
        method: "POST",
        headers: ghlHeaders,
        body: JSON.stringify({
          locationId: env.GHL_LOCATION_ID,
          firstName,
          lastName,
          email: reply.from_email || "",
          companyName: reply.company || "",
          source: CONFIG.ghl.source,
          tags: CONFIG.ghl.tags,
          customFields: [
            { id: CONFIG.ghl.custom_fields.reply_text, field_value: (reply.body || "").slice(0, 500) },
          ],
        }),
      },
    );

    if (!contactRes.ok) {
      const detail = await contactRes.text();
      console.error("GHL contact creation failed:", contactRes.status, detail);
      result.error = `GHL contact ${contactRes.status}`;
      return result;
    }

    const contactData = await contactRes.json();
    result.contact_id = contactData?.contact?.id;

    if (result.contact_id && CONFIG.ghl.pipeline_id) {
      const stageId = classification === "hot_positive" ? CONFIG.ghl.pipeline_stages.interested : CONFIG.ghl.pipeline_stages.new;

      const oppRes = await fetch(
        `${CONFIG.ghl.api_url}/opportunities/`,
        {
          method: "POST",
          headers: ghlHeaders,
          body: JSON.stringify({
            locationId: env.GHL_LOCATION_ID,
            pipelineId: CONFIG.ghl.pipeline_id,
            stageId,
            contactId: result.contact_id,
            name: `${reply.from_name || "Unknown"} — ${reply.company || "Unknown"}`,
            status: "open",
          }),
        },
      );

      if (oppRes.ok) {
        const oppData = await oppRes.json();
        result.opportunity_id = oppData?.opportunity?.id;
      } else {
        console.error("GHL opportunity creation failed:", oppRes.status);
      }
    }
  } catch (err) {
    console.error("GHL routing error:", err);
    result.error = err.message;
  }

  return result;
}

// ---------------------------------------------------------------------------
// Telegram Notification (port of telegram.py)
// ---------------------------------------------------------------------------

async function sendTelegramNotification(reply, env) {
  if (!env.TELEGRAM_BOT_TOKEN || !env.TELEGRAM_CHAT_ID) {
    console.warn("Telegram credentials not set — skipping notification");
    return false;
  }

  const emoji = reply.classification === "hot_positive" ? "🔥" : "✅";
  const label =
    reply.classification === "hot_positive"
      ? "Hot Lead Detected"
      : "Positive Reply Detected";

  const ghlLink = reply.contact_id
    ? `https://app.gohighlevel.com/v2/location/${env.GHL_LOCATION_ID}/contacts/detail/${reply.contact_id}`
    : "#";

  const esc = (s) => (s || "").replace(/[*_`[\]]/g, "");

  const message =
    `${emoji} *${label}*\n` +
    `*Lead:* ${esc(reply.from_name) || "Unknown"} (${esc(reply.from_email) || ""})\n` +
    `*Company:* ${esc(reply.company) || "Unknown"}\n` +
    `*Industry:* ${esc(reply.industry) || "Unknown"}\n` +
    `*Email Sent:* ${esc(reply.email_subject) || ""}\n` +
    `*Response:* ${esc((reply.body || "").slice(0, 200))}\n` +
    `*Time:* ${reply.received_at || new Date().toISOString()}\n` +
    `[View in GHL](${ghlLink})`;

  try {
    const res = await fetch(
      `https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          chat_id: env.TELEGRAM_CHAT_ID,
          text: message,
          parse_mode: "Markdown",
        }),
      },
    );

    if (!res.ok) {
      console.error("Telegram notification failed:", res.status);
      return false;
    }
    console.log("Telegram notification sent");
    return true;
  } catch (err) {
    console.error("Telegram notification error:", err);
    return false;
  }
}

// ---------------------------------------------------------------------------
// Slack Notification (port of slack.py)
// ---------------------------------------------------------------------------

async function sendSlackNotification(reply, env) {
  if (!env.SLACK_WEBHOOK_URL) {
    return false;
  }

  const emoji = reply.classification === "hot_positive" ? ":fire:" : ":white_check_mark:";
  const label =
    reply.classification === "hot_positive"
      ? "Hot Lead Detected"
      : "Positive Reply Detected";

  const esc = (s) => (s || "").replace(/[*_`~<>]/g, "");

  const message =
    `${emoji} *${label}*\n` +
    `*From:* ${esc(reply.from_name) || "Unknown"} (${esc(reply.from_email) || ""})\n` +
    `*Company:* ${esc(reply.company) || "Unknown"}\n` +
    `*Reply:* ${esc((reply.body || "").slice(0, 200))}\n` +
    `*Time:* ${reply.received_at || new Date().toISOString()}`;

  try {
    const res = await fetch(env.SLACK_WEBHOOK_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: message }),
    });

    if (!res.ok) {
      console.error("Slack notification failed:", res.status);
      return false;
    }
    console.log("Slack notification sent");
    return true;
  } catch (err) {
    console.error("Slack notification error:", err);
    return false;
  }
}

// ---------------------------------------------------------------------------
// Delayed Reply Queue (human-timing: 2-7 min delay before sending)
// ---------------------------------------------------------------------------

async function queueDelayedReply(env, replyData) {
  if (!env.REPLY_STATE) return;
  const key = `pending_reply_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
  await env.REPLY_STATE.put(key, JSON.stringify(replyData), {
    expirationTtl: 60 * 60 * 24,
  });
}

async function processDelayedReplies(env) {
  if (!env.REPLY_STATE || !env.INSTANTLY_API_KEY) return 0;

  let allKeys = [];
  let listCursor = null;
  const maxEntries = 200;

  do {
    const listOpts = { prefix: "pending_reply_", limit: 50 };
    if (listCursor) listOpts.cursor = listCursor;
    const list = await env.REPLY_STATE.list(listOpts);
    allKeys.push(...list.keys);
    listCursor = list.list_complete ? null : list.cursor;
  } while (listCursor && allKeys.length < maxEntries);

  let sent = 0;

  for (const key of allKeys) {
    const val = await env.REPLY_STATE.get(key.name);
    if (!val) continue;

    let data;
    try {
      data = JSON.parse(val);
    } catch (_) {
      await env.REPLY_STATE.delete(key.name);
      continue;
    }
    if (data.sending) continue;
    const retries = data.retry_count || 0;
    if (retries >= 3) {
      console.error(`Delayed reply for ${data.reply_to_uuid} failed 3 times — giving up`);
      await env.REPLY_STATE.delete(key.name);
      continue;
    }
    const sendAfter = new Date(data.send_after);

    if (new Date() < sendAfter) continue;

    try {
      await env.REPLY_STATE.put(key.name, JSON.stringify({ ...data, sending: true }), { expirationTtl: 60 * 60 * 24 });
      await sendInstantlyReply(
        data.reply_to_uuid,
        data.from_email,
        data.reply_text,
        env,
      );
      console.log(`Delayed reply sent for ${data.reply_to_uuid}`);
      sent++;
      await env.REPLY_STATE.delete(key.name);
    } catch (err) {
      console.error(`Failed to send delayed reply for ${data.reply_to_uuid} (attempt ${retries + 1}):`, err);
      try {
        await env.REPLY_STATE.put(key.name, JSON.stringify({ ...data, sending: false, retry_count: retries + 1 }), { expirationTtl: 60 * 60 * 24 });
      } catch (_) {}
    }
  }

  return sent;
}

// ---------------------------------------------------------------------------
// Instantly API (port of instantly.py)
// ---------------------------------------------------------------------------

async function fetchInstantlyReplies(env) {
  const allReplies = [];
  let cursor = null;
  const maxPages = 10;

  for (let page = 0; page < maxPages; page++) {
    let url = `https://api.instantly.ai/api/v2/emails?email_type=received&limit=50&campaign_id=${env.CAMPAIGN_ID || ""}`;
    if (cursor) url += `&starting_after=${cursor}`;

    const res = await fetch(url, {
      headers: { Authorization: `Bearer ${env.INSTANTLY_API_KEY}` },
    });
    if (!res.ok) throw new Error(`Instantly fetch failed: ${res.status}`);
    const data = await res.json();
    const items = data.items || data.data || [];
    allReplies.push(...items);

    cursor = data.next_starting_after;
    if (!cursor || items.length === 0) break;
  }

  return allReplies;
}

function normalizeReply(raw) {
  const bodyText =
    typeof raw.body === "object" ? (raw.body?.text || raw.body?.html || "") : (raw.body || "");
  return {
    id: raw.id || raw.message_id || "",
    from_email: raw.from_address_email || "",
    from_name: raw.from_address_name || "",
    subject: raw.subject || "",
    email_subject: raw.subject || raw.email_subject || "",
    body: bodyText,
    company: raw.company_name || raw.company || "",
    industry: raw.custom_variables?.industry || raw.industry || "Unknown",
    received_at: raw.timestamp_email || raw.timestamp_created || "",
    campaign_id: raw.campaign_id || "",
    lead_email: (raw.to_address_email_list || [])[0] || "",
    is_auto_reply: raw.is_auto_reply || false,
  };
}

async function sendInstantlyReply(replyToUuid, fromEmail, replyText, env) {
  const res = await fetch("https://api.instantly.ai/api/v2/emails/reply", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.INSTANTLY_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      reply_to_uuid: replyToUuid,
      eaccount: fromEmail,
      body: replyText,
    }),
  });

  if (!res.ok) {
    throw new Error(`Instantly send reply ${res.status}: ${await res.text()}`);
  }

  return res.json();
}

// ---------------------------------------------------------------------------
// OpenRouter LLM Client (port of llm_client.py)
// ---------------------------------------------------------------------------

async function callOpenRouter(system, userMessage, model, maxTokens, env) {
  const maxRetries = 2;
  let lastErr;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      const res = await fetch("https://openrouter.ai/api/v1/chat/completions", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${env.OPENROUTER_API_KEY}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          model,
          max_tokens: maxTokens,
          messages: [
            { role: "system", content: system },
            { role: "user", content: userMessage },
          ],
        }),
      });

      if (res.status === 429 || res.status >= 500) {
        lastErr = new Error(`OpenRouter ${res.status}`);
        if (attempt < maxRetries) {
          await sleep(1000 * 2 ** attempt);
          continue;
        }
        throw lastErr;
      }

      if (!res.ok) {
        throw new Error(
          `OpenRouter ${res.status}: ${await res.text()}`,
        );
      }

      const data = await res.json();
      return (data.choices?.[0]?.message?.content || "").trim();
    } catch (err) {
      lastErr = err;
      if (attempt < maxRetries && (err.message || "").includes("429")) {
        await sleep(1000 * 2 ** attempt);
        continue;
      }
      if (attempt >= maxRetries) throw err;
    }
  }
  throw lastErr;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// ---------------------------------------------------------------------------
// KV State Management
// ---------------------------------------------------------------------------

async function isAlreadyProcessed(env, replyId) {
  if (!env.REPLY_STATE) return false;
  const val = await env.REPLY_STATE.get(replyId);
  return val !== null;
}

async function markProcessed(env, replyId, result) {
  if (!env.REPLY_STATE) return;
  await env.REPLY_STATE.put(
    replyId,
    JSON.stringify({ ...result, processed_at: new Date().toISOString() }),
    { expirationTtl: 60 * 60 * 24 * 30 },
  );
}

// ===================================================================
// EXISTING API PROXY ROUTES
// ===================================================================

/**
 * POST /api/form-submit
 */
async function handleFormSubmit(request, env) {
  let body;
  try {
    body = await request.json();
  } catch {
    return jsonResponse({ success: false, error: "Invalid JSON body" }, 400);
  }

  const { name, company, email, revenue } = body;

  if (!name || !email) {
    return jsonResponse(
      { success: false, error: "Name and email are required" },
      400,
    );
  }

  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return jsonResponse(
      { success: false, error: "Invalid email format" },
      400,
    );
  }

  const { firstName, lastName } = parseName(name);

  const ghlBody = {
    locationId: env.GHL_LOCATION_ID,
    firstName,
    lastName,
    email,
    companyName: company || "",
    source: "website",
    tags: ["website lead"],
    customFields: [{ id: CONFIG.ghl.custom_fields.revenue_range, field_value: revenue || "" }],
  };

  try {
    const res = await fetch("https://services.leadconnectorhq.com/contacts/", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.GHL_API_KEY}`,
        "Content-Type": "application/json",
        Version: "2021-07-28",
      },
      body: JSON.stringify(ghlBody),
    });

    if (!res.ok) {
      const detail = await res.text();
      console.error("GHL error:", res.status, detail);
      return jsonResponse(
        { success: false, error: "Failed to create contact" },
        502,
      );
    }

    return jsonResponse({
      success: true,
      message: "Thank you! We'll be in touch.",
    });
  } catch (err) {
    console.error("GHL fetch error:", err);
    return jsonResponse(
      { success: false, error: "Failed to reach CRM" },
      502,
    );
  }
}

/**
 * GET /api/dashboard?range=7d|30d|all
 */
async function handleDashboard(url, env) {
  const range = url.searchParams.get("range") || "7d";
  if (!["7d", "30d", "all"].includes(range)) {
    return jsonResponse({ error: "Invalid range. Use 7d, 30d, or all." }, 400);
  }

  const startDate = rangeToDate(range);

  const fetches = [
    fetchInstantlyMetrics(env, startDate),
    fetchGHLMetrics(env, startDate),
  ];
  if (env.CAMPAIGN_ID) {
    fetches.push(fetchVariantData(env));
  }

  const results = await Promise.allSettled(fetches);
  const [emailData, crmData] = results;

  const response = { generated_at: new Date().toISOString() };

  if (emailData.status === "fulfilled") {
    response.email = emailData.value;
  } else {
    console.error("Instantly fetch failed:", emailData.reason);
    response.email = { error: "Email metrics unavailable" };
  }

  if (crmData.status === "fulfilled") {
    response.crm = crmData.value;
  } else {
    console.error("GHL fetch failed:", crmData.reason);
    response.crm = { error: "CRM metrics unavailable" };
  }

  if (results[2]) {
    if (results[2].status === "fulfilled") {
      response.variants = results[2].value;
    } else {
      console.error("Variants fetch failed:", results[2].reason);
    }
  }

  return jsonResponse(response);
}

/**
 * POST /api/webhook/reply — now triggers processing instead of just logging.
 */
async function handleReplyWebhook(request, env) {
  let payload;
  try {
    payload = await request.json();
  } catch {
    return jsonResponse({ success: false, error: "Invalid JSON body" }, 400);
  }

  console.log("Reply webhook received:", payload?.id || payload?.message_id || "unknown");

  if (payload && (payload.from_email || payload.from_address_email || payload.body)) {
    const reply = normalizeReply(payload);

    if (reply.is_auto_reply) {
      return jsonResponse({ success: true, skipped: "auto_reply" });
    }

    const replyId = payload.id || payload.message_id || `webhook_${Date.now()}`;

    const already = await isAlreadyProcessed(env, replyId);
    if (!already) {
      await markProcessed(env, replyId, { status: "processing", started: Date.now() });
      try {
        const result = await processReply(reply, env);
        await markProcessed(env, replyId, result);
        return jsonResponse({ success: true, received: true, processed: result });
      } catch (err) {
        await env.REPLY_STATE?.delete(replyId);
        console.error("Webhook reply processing error:", err);
        return jsonResponse({
          success: true,
          received: true,
          processing_error: err.message,
        });
      }
    }
  }

  return jsonResponse({ success: true, received: true, already_processed: true });
}

/**
 * GET /api/variants?campaign_id=X
 */
async function handleVariants(url, env) {
  const campaignId = url.searchParams.get("campaign_id");
  if (!campaignId) {
    return jsonResponse({ error: "campaign_id parameter required" }, 400);
  }

  try {
    const [campaignRes, analyticsRes] = await Promise.all([
      fetch(`https://api.instantly.ai/api/v2/campaigns?id=${campaignId}&limit=1`, {
        headers: { Authorization: `Bearer ${env.INSTANTLY_API_KEY}` },
      }),
      fetch(`https://api.instantly.ai/api/v2/campaigns/analytics/overview?id=${campaignId}`, {
        headers: { Authorization: `Bearer ${env.INSTANTLY_API_KEY}` },
      }),
    ]);

    if (!campaignRes.ok) {
      throw new Error(`Instantly campaigns API ${campaignRes.status}`);
    }

    const campaignData = await campaignRes.json();
    const campaign = campaignData.items?.[0];
    if (!campaign) {
      return jsonResponse({ error: "Campaign not found" }, 404);
    }

    const analytics = analyticsRes.ok ? await analyticsRes.json() : {};
    const steps = campaign.sequences?.[0]?.steps || [];

    const variants = steps.map((step, i) => ({
      step: i + 1,
      type: step.type || "email",
      delay_days: step.delay || 0,
      variant_count: step.variants?.length || 0,
      subjects: (step.variants || []).map((v) => v.subject || "(no subject)"),
    }));

    return jsonResponse({
      campaign_id: campaignId,
      campaign_name: campaign.name,
      status: campaign.status,
      analytics: {
        emails_sent: analytics.emails_sent_count ?? 0,
        replies: analytics.reply_count ?? 0,
        opens: analytics.open_count_unique ?? 0,
        bounces: analytics.bounced_count ?? 0,
      },
      variants,
    });
  } catch (err) {
    console.error("Variants fetch failed:", err);
    return jsonResponse(
      { error: "Failed to fetch variant analytics" },
      502,
    );
  }
}

/**
 * POST /api/process-replies — manual trigger for reply processing.
 */
async function handleManualProcess(request, env) {
  try {
    const result = await pollAndProcessReplies(env);
    return jsonResponse({ success: true, ...result });
  } catch (err) {
    console.error("Manual process error:", err);
    return jsonResponse({ success: false, error: err.message }, 500);
  }
}

// ---------------------------------------------------------------------------
// Dashboard API helpers
// ---------------------------------------------------------------------------

async function fetchInstantlyMetrics(env, startDate) {
  const params = new URLSearchParams();
  if (startDate) {
    params.set("start_date", startDate);
  }
  if (env.CAMPAIGN_ID) {
    params.set("id", env.CAMPAIGN_ID);
  }

  const url = `https://api.instantly.ai/api/v2/campaigns/analytics/overview?${params.toString()}`;

  const res = await fetch(url, {
    headers: { Authorization: `Bearer ${env.INSTANTLY_API_KEY}` },
  });

  if (!res.ok) {
    throw new Error(`Instantly API ${res.status}: ${await res.text()}`);
  }

  const data = await res.json();

  const sent = data.emails_sent_count ?? 0;
  const bounces = data.bounced_count ?? 0;
  const delivered = sent - bounces;
  const opened = data.open_count_unique ?? data.open_count ?? 0;
  const replies = data.reply_count ?? 0;

  return {
    emails_sent: sent,
    emails_delivered: delivered,
    deliverability_pct: sent ? +(((delivered / sent) * 100).toFixed(1)) : 0,
    open_rate_pct: delivered
      ? +(((opened / delivered) * 100).toFixed(1))
      : 0,
    replies,
    reply_rate_pct: delivered
      ? +(((replies / delivered) * 100).toFixed(1))
      : 0,
    bounces,
    bounce_rate_pct: sent ? +(((bounces / sent) * 100).toFixed(1)) : 0,
    unsubscribes: data.unsubscribed_count ?? 0,
  };
}

async function fetchVariantData(env) {
  const res = await fetch(
    `https://api.instantly.ai/api/v2/campaigns?id=${env.CAMPAIGN_ID}&limit=1`,
    { headers: { Authorization: `Bearer ${env.INSTANTLY_API_KEY}` } },
  );
  if (!res.ok) {
    throw new Error(`Instantly campaigns API ${res.status}`);
  }
  const data = await res.json();
  const campaign = data.items?.[0];
  if (!campaign) return [];

  const steps = campaign.sequences?.[0]?.steps || [];
  return steps.map((step, i) => ({
    step: i + 1,
    type: step.type || "email",
    delay_days: step.delay || 0,
    variant_count: step.variants?.length || 0,
    subjects: (step.variants || []).map((v) => v.subject || "(no subject)"),
  }));
}

async function fetchGHLMetrics(env, startDate) {
  const headers = {
    Authorization: `Bearer ${env.GHL_API_KEY}`,
    "Content-Type": "application/json",
    Version: "2021-07-28",
  };

  const locationId = env.GHL_LOCATION_ID;

  const contactsUrl = new URL(
    "https://services.leadconnectorhq.com/contacts/",
  );
  contactsUrl.searchParams.set("locationId", locationId);
  contactsUrl.searchParams.set("limit", "1");
  if (startDate) {
    contactsUrl.searchParams.set("startAfter", startDate);
  }

  const oppsUrl = new URL(
    "https://services.leadconnectorhq.com/opportunities/search",
  );
  oppsUrl.searchParams.set("location_id", locationId);
  if (CONFIG.ghl.pipeline_id) {
    oppsUrl.searchParams.set("pipeline_id", CONFIG.ghl.pipeline_id);
  }

  const calendarUrl = new URL(
    "https://services.leadconnectorhq.com/calendars/events/appointments",
  );
  calendarUrl.searchParams.set("locationId", locationId);
  calendarUrl.searchParams.set("calendarId", CONFIG.ghl.calendar_id);
  if (startDate) {
    calendarUrl.searchParams.set("startTime", new Date(startDate).toISOString());
    calendarUrl.searchParams.set("endTime", new Date().toISOString());
  }

  const [contactsRes, oppsRes, calendarRes] = await Promise.all([
    fetch(contactsUrl.toString(), { headers }),
    fetch(oppsUrl.toString(), { headers }),
    fetch(calendarUrl.toString(), { headers }).catch((err) => {
      console.error("GHL calendar fetch error:", err);
      return null;
    }),
  ]);

  let contactsCreated = 0;
  if (contactsRes.ok) {
    const contactsData = await contactsRes.json();
    contactsCreated = contactsData.meta?.total ?? contactsData.total ?? 0;
  } else {
    console.error("GHL contacts error:", contactsRes.status);
  }

  let opportunitiesTotal = 0;
  let opportunitiesOpen = 0;
  let opportunitiesWon = 0;
  let pipelineValue = 0;
  if (oppsRes.ok) {
    const oppsData = await oppsRes.json();
    const opps = oppsData.opportunities || [];
    opportunitiesTotal = opps.length;
    opportunitiesOpen = opps.filter((o) => o.status === "open").length;
    opportunitiesWon = opps.filter((o) => o.status === "won").length;
    pipelineValue = opps.reduce(
      (sum, o) => sum + (o.monetaryValue || 0),
      0,
    );
  } else {
    console.error("GHL opportunities error:", oppsRes.status);
  }

  let appointmentsBooked = 0;
  if (calendarRes && calendarRes.ok) {
    const calendarData = await calendarRes.json();
    const events = calendarData.events || [];
    appointmentsBooked = events.length;
  } else if (calendarRes) {
    console.error("GHL calendar error:", calendarRes.status);
  }

  return {
    contacts_created: contactsCreated,
    opportunities_total: opportunitiesTotal,
    opportunities_open: opportunitiesOpen,
    opportunities_won: opportunitiesWon,
    appointments_booked: appointmentsBooked,
    pipeline_value: pipelineValue,
  };
}

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

function parseName(fullName) {
  const parts = fullName.trim().split(/\s+/);
  if (parts.length === 1) {
    return { firstName: parts[0], lastName: "" };
  }
  return {
    firstName: parts[0],
    lastName: parts.slice(1).join(" "),
  };
}

function rangeToDate(range) {
  if (range === "all") return null;
  const days = range === "30d" ? 30 : 7;
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().split("T")[0];
}

function checkAdminAuth(request, env) {
  if (!env.WORKER_SECRET) return false;
  return request.headers.get("X-Worker-Secret") === env.WORKER_SECRET;
}

function jsonResponse(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function corsResponse(request, env, response) {
  const origin = request.headers.get("Origin") || "";
  const allowed = (env.ALLOWED_ORIGINS || "").split(",").map((s) => s.trim());

  const headers = new Headers(response.headers);
  headers.set("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  headers.set("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Worker-Secret");
  headers.set("Access-Control-Max-Age", "86400");

  if (origin && allowed.includes(origin)) {
    headers.set("Access-Control-Allow-Origin", origin);
  }

  return new Response(response.body, {
    status: response.status,
    headers,
  });
}

// ===================================================================
// DAILY PIPELINE: Source → Enrich → Verify → Personalize → Upload
// ===================================================================

async function runDailyPipeline(env) {
  const runId = `run_${Date.now()}`;
  console.log(`Pipeline ${runId}: starting daily pipeline`);

  const state = { run_id: runId, started_at: new Date().toISOString(), stages: {} };

  try {
    // Stage 1: Source leads via Serper Maps
    const leads = await stageSource(env, runId);
    state.stages.source = { count: leads.length, status: "complete" };
    console.log(`Pipeline ${runId}: sourced ${leads.length} leads`);

    if (leads.length === 0) {
      state.status = "complete_no_leads";
      await savePipelineState(env, state);
      return state;
    }

    // Stage 2: Enrich with AnymailFinder
    const enriched = await stageEnrich(leads, env);
    const enrichedCount = enriched.filter((l) => l.status === "enriched").length;
    state.stages.enrich = { count: enrichedCount, status: "complete" };
    console.log(`Pipeline ${runId}: enriched ${enrichedCount}/${leads.length}`);

    // Stage 3: Verify with Million Verifier
    const verified = await stageVerify(enriched, env);
    const verifiedCount = verified.filter((l) => l.status === "verified").length;
    state.stages.verify = { count: verifiedCount, status: "complete" };
    console.log(`Pipeline ${runId}: verified ${verifiedCount}/${enrichedCount}`);

    // Stage 4: Personalize with OpenRouter
    const personalized = await stagePersonalize(verified, env);
    const personalizedCount = personalized.filter((l) => l.status === "personalized").length;
    state.stages.personalize = { count: personalizedCount, status: "complete" };
    console.log(`Pipeline ${runId}: personalized ${personalizedCount}/${verifiedCount}`);

    // Stage 5: Upload to Instantly
    const uploadResult = await stageUpload(personalized, env);
    state.stages.upload = uploadResult;
    console.log(`Pipeline ${runId}: uploaded ${uploadResult.uploaded}/${uploadResult.total}`);

    state.status = "complete";
    state.completed_at = new Date().toISOString();
  } catch (err) {
    console.error(`Pipeline ${runId} error:`, err);
    state.status = "error";
    state.error = err.message;
  }

  await savePipelineState(env, state);
  return state;
}

// ---------------------------------------------------------------------------
// Stage 1: Serper Maps Lead Sourcing
// ---------------------------------------------------------------------------

async function stageSource(env, runId) {
  if (!env.SERPER_API_KEY) {
    console.warn("SERPER_API_KEY not set — skipping sourcing");
    return [];
  }

  const industries = CONFIG.icp.industries;
  const geo = CONFIG.icp.geography;
  const cities = [`${geo.city}, ${geo.state}`];
  if (geo.include_suburbs) {
    for (const suburb of geo.suburbs) {
      cities.push(`${suburb}, ${geo.state}`);
    }
  }

  const limit = CONFIG.sourcing.serper_results_per_query;
  const allLeads = [];
  const ts = new Date().toISOString();

  for (const industry of industries) {
    for (const city of cities) {
      const query = `${industry} ${city}`;
      try {
        const places = await searchSerperMaps(query, limit, env);
        for (const place of places) {
          const lead = buildLeadFromSerper(place, industry, query, runId, ts);
          if (lead.business_name) allLeads.push(lead);
        }
      } catch (err) {
        console.error(`Serper query failed: ${query}`, err);
      }
      await sleep(100);
    }
  }

  console.log(`Sourced ${allLeads.length} raw leads`);
  return deduplicateLeads(allLeads);
}

async function searchSerperMaps(query, limit, env) {
  const res = await fetch(CONFIG.sourcing.serper_api_url, {
    method: "POST",
    headers: {
      "X-API-KEY": env.SERPER_API_KEY,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ q: query, num: limit }),
  });

  if (!res.ok) {
    throw new Error(`Serper ${res.status}: ${await res.text()}`);
  }

  const data = await res.json();
  return data.places || [];
}

function buildLeadFromSerper(place, industry, query, runId, ts) {
  const address = place.address || "";
  const { city, state } = parseAddress(address);
  const website = place.website || "";
  const domain = extractDomain(website);

  return {
    business_name: place.title || "",
    address,
    city,
    state,
    phone: place.phoneNumber || "",
    website,
    domain,
    industry,
    rating: place.rating || null,
    reviews_count: place.ratingCount || place.reviewsCount || place.reviews || null,
    source: "serper_maps",
    source_query: query,
    sourced_at: ts,
    status: "sourced",
    pipeline_run_id: runId,
  };
}

function parseAddress(address) {
  if (!address) return { city: "", state: "" };
  const parts = address.split(",").map((s) => s.trim());
  if (parts.length >= 2) {
    const last = parts[parts.length - 1];
    const tokens = last.split(/\s+/);
    const state = tokens[0] || "";
    const city = parts.length >= 3 ? parts[parts.length - 2] : parts[0];
    return { city, state };
  }
  return { city: "", state: "" };
}

function extractDomain(url) {
  if (!url) return "";
  try {
    const u = new URL(url.startsWith("http") ? url : `https://${url}`);
    return u.hostname.replace(/^www\./, "").toLowerCase();
  } catch {
    return "";
  }
}

function deduplicateLeads(leads) {
  const seen = new Set();
  return leads.filter((lead) => {
    const name = (lead.business_name || "").toLowerCase().replace(/[^a-z0-9\s]/g, "").replace(/\s+/g, " ").trim();
    const domain = (lead.domain || "").toLowerCase();
    const key = `${domain}|${name}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

// ---------------------------------------------------------------------------
// Stage 2: AnymailFinder Email Enrichment
// ---------------------------------------------------------------------------

async function stageEnrich(leads, env) {
  if (!env.ANYMAILFINDER_API_KEY) {
    console.warn("ANYMAILFINDER_API_KEY not set — skipping enrichment");
    return leads;
  }

  const minConf = CONFIG.enrichment.anymailfinder_min_confidence;

  for (const lead of leads) {
    if (lead.owner_email || !lead.domain) continue;

    try {
      const result = await findEmail(lead, env);
      if (result && result.confidence >= minConf) {
        lead.owner_name = result.name || lead.owner_name || "";
        if (!lead.owner_name) {
          lead.owner_name = lead.business_name ? lead.business_name.split(/\s+/)[0] : "there";
        }
        lead.owner_email = result.email;
        lead.email_confidence = result.confidence;
        lead.email_type = result.type;
        lead.enriched_at = new Date().toISOString();
        lead.status = "enriched";
      } else if (result) {
        lead.status = "low_confidence";
        lead.email_confidence = result.confidence;
      } else {
        lead.status = "no_email_found";
      }
    } catch (err) {
      console.error(`Enrichment failed for ${lead.domain}:`, err);
      lead.status = "error";
    }

    await sleep(200);
  }

  return leads;
}

async function findEmail(lead, env) {
  const ownerName = lead.owner_name || "";
  if (ownerName && ownerName.includes(" ")) {
    const [first, ...rest] = ownerName.trim().split(/\s+/);
    const last = rest.join(" ");
    const personResult = await findEmailPerson(lead.domain, first, last, env);
    if (personResult) return personResult;
  }

  return findEmailCompany(lead.domain, lead.business_name || "", env);
}

async function findEmailPerson(domain, firstName, lastName, env) {
  const res = await fetch(CONFIG.enrichment.anymailfinder_person_url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.ANYMAILFINDER_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ domain, first_name: firstName, last_name: lastName }),
  });

  if (!res.ok) return null;
  const data = await res.json();
  if (!data.email) return null;

  return {
    email: data.email,
    name: `${firstName} ${lastName}`.trim(),
    confidence: data.validation === "valid" ? 90 : 60,
    type: isGenericEmail(data.email) ? "generic" : "personal",
  };
}

async function findEmailCompany(domain, companyName, env) {
  const res = await fetch(CONFIG.enrichment.anymailfinder_company_url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.ANYMAILFINDER_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ domain, company_name: companyName }),
  });

  if (!res.ok) return null;
  const data = await res.json();
  const emails = data.emails || [];
  if (!emails.length) return null;

  const sorted = [...emails].sort((a, b) => {
    const aGeneric = isGenericEmail(a) ? 1 : 0;
    const bGeneric = isGenericEmail(b) ? 1 : 0;
    return aGeneric - bGeneric;
  });
  const email = sorted[0];
  return {
    email,
    name: "",
    confidence: data.validation === "valid" ? 70 : 50,
    type: isGenericEmail(email) ? "generic" : "personal",
  };
}

function isGenericEmail(email) {
  const genericPrefixes = new Set([
    "info", "contact", "admin", "support", "hello", "office", "sales", "team",
  ]);
  const local = email.split("@")[0].toLowerCase();
  return genericPrefixes.has(local);
}

// ---------------------------------------------------------------------------
// Stage 3: Million Verifier Email Verification
// ---------------------------------------------------------------------------

async function stageVerify(leads, env) {
  if (!env.MILLION_VERIFIER_API_KEY) {
    console.warn("MILLION_VERIFIER_API_KEY not set — promoting enriched leads to verified");
    for (const lead of leads) {
      if (lead.status === "enriched" && lead.owner_email) {
        lead.status = "verified";
        lead.email_verified = true;
        lead.email_verification_result = "skipped";
      }
    }
    return leads;
  }

  const acceptResults = new Set(CONFIG.enrichment.million_verifier_accept);

  for (const lead of leads) {
    if (lead.status !== "enriched" || !lead.owner_email) continue;

    try {
      const result = await verifyEmail(lead.owner_email, env);
      lead.email_verification_result = result.result;
      lead.email_quality_score = result.quality_score;
      lead.verified_at = new Date().toISOString();

      if (acceptResults.has(result.result)) {
        lead.email_verified = true;
        lead.status = "verified";
      } else {
        lead.email_verified = false;
        lead.status = "email_invalid";
      }
    } catch (err) {
      console.error(`Verification failed for ${lead.owner_email}:`, err);
      lead.status = "error";
    }

    await sleep(200);
  }

  return leads;
}

async function verifyEmail(email, env) {
  const url = `${CONFIG.enrichment.million_verifier_url}/?api=${env.MILLION_VERIFIER_API_KEY}&email=${encodeURIComponent(email)}`;
  const res = await fetch(url);

  if (!res.ok) {
    throw new Error(`Million Verifier ${res.status}`);
  }

  const data = await res.json();
  return {
    result: data.result || "unknown",
    quality_score: data.quality || 0,
  };
}

// ---------------------------------------------------------------------------
// Stage 4: AI Opener Personalization
// ---------------------------------------------------------------------------

async function stagePersonalize(leads, env) {
  if (!env.OPENROUTER_API_KEY) {
    console.warn("OPENROUTER_API_KEY not set — using mock openers");
  }

  const systemPrompt = buildOpenerSystemPrompt();

  for (const lead of leads) {
    if (lead.status !== "verified") continue;

    let opener;
    if (env.OPENROUTER_API_KEY) {
      opener = await generateOpener(lead, systemPrompt, env);
    } else {
      opener = getMockOpener(lead);
    }

    lead.personalized_opener = opener;
    lead.opener_model = env.OPENROUTER_API_KEY ? CONFIG.personalization.model : "mock";
    lead.personalized_at = new Date().toISOString();
    lead.status = "personalized";
  }

  return leads;
}

function buildOpenerSystemPrompt() {
  const t = CONFIG.tone;
  let prompt =
    `You write personalized cold email opening lines for ${t.sender_name}.\n\n` +
    `VOICE: Use "${t.voice}" (first person).\n\n` +
    `TONE: ${t.tone_description}\n\n` +
    `TASK: ${t.opener_instruction}\n\n` +
    "CONSTRAINTS:\n" +
    "- Exactly one sentence, 5-25 words\n" +
    "- No exclamation marks\n" +
    "- No questions\n" +
    '- No sales language ("exciting opportunity", "game-changing", "transform")\n' +
    '- No compliments that feel fake ("impressive", "amazing", "incredible")\n' +
    "- Reference something specific and factual about the prospect";

  if (t.never_say.length) {
    prompt += "\n- NEVER say: " + t.never_say.map((w) => `"${w}"`).join(", ");
  }

  if (t.example_openers.length) {
    prompt += "\n\nEXAMPLES OF GOOD OPENERS:\n";
    for (const ex of t.example_openers) {
      prompt += `- ${ex}\n`;
    }
  }

  return prompt;
}

function buildOpenerUserPrompt(lead) {
  const parts = [`Business: ${lead.business_name || "Unknown"}`];
  if (lead.industry) parts.push(`Industry: ${lead.industry}`);
  if (lead.city && lead.state) parts.push(`Location: ${lead.city}, ${lead.state}`);
  if (lead.rating) parts.push(`Rating: ${lead.rating} stars`);
  if (lead.reviews_count) parts.push(`Reviews: ${lead.reviews_count}`);
  if (lead.website) parts.push(`Website: ${lead.website}`);
  if (lead.owner_name) parts.push(`Owner: ${lead.owner_name}`);
  return "Write one personalized opener for this business.\n\n" + parts.join("\n");
}

async function generateOpener(lead, systemPrompt, env) {
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      const raw = await callOpenRouter(
        systemPrompt,
        buildOpenerUserPrompt(lead),
        CONFIG.personalization.model,
        CONFIG.personalization.max_opener_tokens,
        env,
      );
      const opener = raw.replace(/^["']|["']$/g, "");
      if (validateOpener(opener)) return opener;
    } catch (err) {
      console.error(`Opener generation failed for ${lead.business_name}:`, err);
    }
  }
  return getMockOpener(lead);
}

function validateOpener(opener) {
  if (!opener) return false;
  const words = opener.split(/\s+/);
  if (words.length < 5 || words.length > 25) return false;
  if (opener.includes("!")) return false;
  const lower = opener.toLowerCase();
  for (const phrase of CONFIG.tone.never_say) {
    if (lower.includes(phrase.toLowerCase())) return false;
  }
  return true;
}

function getMockOpener(lead) {
  const name = lead.business_name || "your business";
  const industry = lead.industry || "business";
  const city = lead.city || "Houston";
  if (lead.rating && lead.reviews_count && lead.reviews_count > 50) {
    return `I noticed ${name} has a ${lead.rating} rating with ${lead.reviews_count}+ reviews in ${city}.`;
  }
  if (lead.rating) {
    return `I saw ${name} has a solid ${lead.rating}-star rating in ${city}.`;
  }
  return `I came across ${name} while researching ${industry} businesses in ${city}.`;
}

// ---------------------------------------------------------------------------
// Stage 5: Upload to Instantly
// ---------------------------------------------------------------------------

async function stageUpload(leads, env) {
  if (!env.INSTANTLY_API_KEY || !env.CAMPAIGN_ID) {
    console.warn("INSTANTLY_API_KEY or CAMPAIGN_ID not set — skipping upload");
    return { uploaded: 0, errors: 0, total: 0 };
  }

  const personalized = leads.filter((l) => l.status === "personalized");
  if (!personalized.length) {
    return { uploaded: 0, errors: 0, total: 0 };
  }

  let uploaded = 0;
  let errors = 0;

  for (const lead of personalized) {
    let success = false;
    for (let attempt = 0; attempt < 3; attempt++) {
      try {
        const payload = buildInstantlyPayload(lead, env.CAMPAIGN_ID);
        const res = await fetch(`${CONFIG.instantly.api_url}/leads`, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${env.INSTANTLY_API_KEY}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify(payload),
        });

        if (res.ok) {
          lead.uploaded_to_instantly = true;
          lead.campaign_id = env.CAMPAIGN_ID;
          lead.status = "uploaded";
          uploaded++;
          success = true;
          break;
        } else if (res.status >= 500 || res.status === 429) {
          console.warn(`Instantly upload attempt ${attempt + 1} failed for ${lead.owner_email}: ${res.status}`);
          if (attempt < 2) await sleep(2000 * (attempt + 1));
        } else {
          console.error(`Instantly upload failed for ${lead.owner_email}: ${res.status}`);
          break;
        }
      } catch (err) {
        console.warn(`Upload attempt ${attempt + 1} error for ${lead.owner_email}:`, err.message);
        if (attempt < 2) await sleep(2000 * (attempt + 1));
      }
    }
    if (!success) {
      lead.status = "error";
      errors++;
    }

    await sleep(CONFIG.instantly.upload_rate_limit_ms);
  }

  return { uploaded, errors, total: personalized.length };
}

function buildInstantlyPayload(lead, campaignId) {
  const mapping = CONFIG.instantly.field_mapping;
  const ownerName = lead[mapping.first_name_from] || "";
  const nameParts = ownerName.trim().split(/\s+/);
  const firstName = nameParts[0] || "";
  const lastName = nameParts.length > 1 ? nameParts.slice(1).join(" ") : "";

  const customVars = {};
  for (const [varName, leadField] of Object.entries(mapping.custom_variables)) {
    customVars[varName] = lead[leadField] || "";
  }

  return {
    campaign: campaignId,
    email: lead[mapping.email] || "",
    first_name: firstName,
    last_name: lastName,
    company_name: lead[mapping.company_name] || "",
    custom_variables: customVars,
  };
}

// ---------------------------------------------------------------------------
// Weekly Report
// ---------------------------------------------------------------------------

async function runWeeklyReport(env) {
  console.log("Weekly report: starting");

  const now = new Date();
  const weekAgo = new Date(now);
  weekAgo.setDate(weekAgo.getDate() - 7);
  const startDate = weekAgo.toISOString().split("T")[0];

  const [emailMetrics, crmMetrics] = await Promise.allSettled([
    fetchInstantlyMetrics(env, startDate),
    fetchGHLMetrics(env, startDate),
  ]);

  const email = emailMetrics.status === "fulfilled" ? emailMetrics.value : {};
  const crm = crmMetrics.status === "fulfilled" ? crmMetrics.value : {};

  const report = {
    client: "Accessory Masters",
    generated_at: now.toISOString(),
    date_range: { start: startDate, end: now.toISOString().split("T")[0] },
    email,
    crm,
  };

  if (env.TELEGRAM_BOT_TOKEN && env.TELEGRAM_CHAT_ID) {
    const msg =
      `*Accessory Masters — Weekly Report*\n` +
      `_${report.date_range.start} to ${report.date_range.end}_\n\n` +
      `*Email Performance*\n` +
      `Sent: *${email.emails_sent || 0}*  |  Deliverability: *${email.deliverability_pct || 0}%*\n` +
      `Replies: *${email.replies || 0}* (${email.reply_rate_pct || 0}%)  |  Bounces: ${email.bounce_rate_pct || 0}%\n\n` +
      `*CRM Pipeline*\n` +
      `Contacts: *${crm.contacts_created || 0}*  |  Appointments: *${crm.appointments_booked || 0}*\n` +
      `Pipeline: *$${(crm.pipeline_value || 0).toLocaleString()}*`;

    try {
      const tgRes = await fetch(
        `https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            chat_id: env.TELEGRAM_CHAT_ID,
            text: msg,
            parse_mode: "Markdown",
          }),
        },
      );
      if (!tgRes.ok) {
        console.error("Telegram weekly report failed:", tgRes.status);
      } else {
        console.log("Weekly report sent via Telegram");
      }
    } catch (err) {
      console.error("Telegram weekly report failed:", err);
    }
  }

  if (env.SLACK_WEBHOOK_URL) {
    const slackMsg =
      `:bar_chart: *Accessory Masters — Weekly Report*\n` +
      `_${report.date_range.start} to ${report.date_range.end}_\n\n` +
      `*Email Performance*\n` +
      `:envelope: Sent: *${email.emails_sent || 0}*  |  ` +
      `:dart: Deliverability: *${email.deliverability_pct || 0}%*\n` +
      `:speech_balloon: Replies: *${email.replies || 0}* (${email.reply_rate_pct || 0}%)  |  ` +
      `:warning: Bounces: ${email.bounce_rate_pct || 0}%\n\n` +
      `*CRM Pipeline*\n` +
      `:busts_in_silhouette: Contacts: *${crm.contacts_created || 0}*  |  ` +
      `:calendar: Appointments: *${crm.appointments_booked || 0}*\n` +
      `:moneybag: Pipeline: *$${(crm.pipeline_value || 0).toLocaleString()}*`;

    try {
      const slkRes = await fetch(env.SLACK_WEBHOOK_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: slackMsg }),
      });
      if (!slkRes.ok) {
        console.error("Slack weekly report failed:", slkRes.status);
      } else {
        console.log("Weekly report sent via Slack");
      }
    } catch (err) {
      console.error("Slack weekly report failed:", err);
    }
  }

  await savePipelineState(env, { ...report, type: "weekly_report" });
  return report;
}

// ---------------------------------------------------------------------------
// Pipeline State (KV)
// ---------------------------------------------------------------------------

async function savePipelineState(env, state) {
  if (!env.REPLY_STATE) return;
  await env.REPLY_STATE.put(
    `pipeline_${state.run_id || state.type || "unknown"}_${Date.now()}`,
    JSON.stringify(state),
    { expirationTtl: 60 * 60 * 24 * 30 },
  );
}

// ---------------------------------------------------------------------------
// HTTP handlers for pipeline
// ---------------------------------------------------------------------------

async function handleRunPipeline(request, env) {
  try {
    const result = await runDailyPipeline(env);
    return jsonResponse({ success: true, ...result });
  } catch (err) {
    console.error("Pipeline error:", err);
    return jsonResponse({ success: false, error: err.message }, 500);
  }
}

async function handlePipelineStatus(env) {
  if (!env.REPLY_STATE) {
    return jsonResponse({ status: "no_kv_namespace" });
  }

  const list = await env.REPLY_STATE.list({ prefix: "pipeline_", limit: 5 });
  const states = [];
  for (const key of list.keys) {
    const val = await env.REPLY_STATE.get(key.name);
    if (val) {
      try { states.push(JSON.parse(val)); } catch (_) {}
    }
  }

  return jsonResponse({ recent_runs: states });
}

async function handleWeeklyReport(env) {
  try {
    const result = await runWeeklyReport(env);
    return jsonResponse({ success: true, ...result });
  } catch (err) {
    console.error("Weekly report error:", err);
    return jsonResponse({ success: false, error: err.message }, 500);
  }
}
