/**
 * Accessory Masters API + AI Responder — Cloudflare Worker
 *
 * HTTP Routes:
 *   POST /api/form-submit       — Contact form -> GoHighLevel
 *   GET  /api/dashboard         — Aggregated metrics from Instantly + GHL
 *   POST /api/webhook/reply     — Instantly reply webhook (triggers processing)
 *   GET  /api/variants          — Campaign variant analytics
 *   POST /api/process-replies   — Manual trigger for reply processing
 *   POST /api/run-pipeline      — Manual trigger for daily pipeline
 *   GET  /api/pipeline-status   — Recent pipeline run history
 *   POST /api/weekly-report     — Manual trigger for weekly report
 *   GET  /api/dashboard-extras  — Hot leads, recent activity, latest pipeline run (from KV)
 *
 * Scheduled:
 *   Cron every 30 min           — Process delayed replies + poll Instantly for new ones
 *   Cron daily 6:00 AM UTC      — Source → Enrich → Verify → Personalize → Upload pipeline
 *   Cron Monday 7:00 AM UTC     — Weekly performance report via Telegram/Slack
 *
 * Secrets (wrangler secret put):
 *   GHL_API_KEY, INSTANTLY_API_KEY, OPENROUTER_API_KEY, WORKER_SECRET
 *   SERPER_API_KEY, ANYMAILFINDER_API_KEY, MILLION_VERIFIER_API_KEY
 *   TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, SLACK_WEBHOOK_URL (optional)
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
          "I'm Alex with Accessory Masters, backed by Hedgestone Capital Group. We acquire profitable aftermarket auto accessory businesses. Happy to share more on a call.",
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
        if (!checkWebhookAuth(request, env)) {
          return corsResponse(request, env, jsonResponse({ error: "Unauthorized" }, 401));
        }
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

      if (method === "GET" && pathname === "/api/dashboard-extras") {
        if (!checkAdminAuth(request, env)) {
          return corsResponse(request, env, jsonResponse({ error: "Unauthorized" }, 401));
        }
        return corsResponse(request, env, await handleDashboardExtras(url, env));
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
      // Stop the cold sequence in this specific campaign — prospect said yes,
      // broker is taking over. Per-campaign removal (NOT global blocklist) so
      // future re-engagement campaigns can still reach them if the deal stalls.
      if (reply.from_email) {
        await pauseLeadInInstantly(reply.from_email, reply.campaign_id || "", env);
      }
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

  if (classification === "negative") {
    result.reason = "not actionable";
    if (reply.from_email) {
      await removeFromInstantlyCampaign(reply.from_email, reply.campaign_id || "", env);
      result.action = "unsubscribed";
    }
  }

  if (classification === "neutral") {
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

  for (const signal of signals.negative) {
    if (text.includes(signal)) return "negative";
  }
  for (const signal of signals.hot_positive) {
    if (text.includes(signal) && !containsNegated(text, signal)) return "hot_positive";
  }
  for (const signal of signals.neutral) {
    if (text.includes(signal)) return "neutral";
  }
  for (const signal of signals.positive) {
    if (text.includes(signal) && !containsNegated(text, signal)) return "positive";
  }
  return "neutral";
}

// ---------------------------------------------------------------------------
// Auto-Reply Generation (port of auto_reply.py)
// ---------------------------------------------------------------------------

// Returns true if `signal` is preceded by a common negation in `text`.
// Catches: "not X", "don't X", "won't X", "never X", "no longer X", "isn't X",
// "haven't X", "wasn't X", "couldn't X", and common contractions.
// Used to suppress false positives on hot-lead signals like "ready to sell"
// matching "not ready to sell".
function containsNegated(text, signal) {
  // Build a regex: optional word boundary + any negation + optional fillers + signal
  // Negations: not, no, never, neither, none, hardly, barely
  // Contractions: don't, doesn't, didn't, won't, wouldn't, can't, couldn't,
  //               isn't, aren't, wasn't, weren't, haven't, hasn't, hadn't,
  //               shouldn't, mustn't, ain't
  // Allow up to 3 short filler words between negation and signal (e.g.,
  // "not really ready to sell", "don't quite want to sell").
  const escaped = signal.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const negationPattern =
    "\\b(?:not|no|never|neither|none|hardly|barely|" +
    "don'?t|doesn'?t|didn'?t|won'?t|wouldn'?t|can'?t|couldn'?t|" +
    "isn'?t|aren'?t|wasn'?t|weren'?t|haven'?t|hasn'?t|hadn'?t|" +
    "shouldn'?t|mustn'?t|ain'?t)\\b" +
    "(?:\\s+\\w+){0,3}\\s+" +
    escaped;
  return new RegExp(negationPattern, "i").test(text);
}

function isHotLead(body) {
  const text = (body || "").toLowerCase();
  // "call me at" requires a phone-number-like sequence after it to avoid
  // false positives like "please don't call me at the office".
  if (/call me at\s+[\d\s\-\(\)+\.]{7,}/.test(text)) return true;
  for (const signal of CONFIG.auto_reply.hot_lead_signals) {
    if (signal === "call me at") continue; // handled above with phone guard
    const sigLower = signal.toLowerCase();
    if (text.includes(sigLower) && !containsNegated(text, sigLower)) return true;
  }
  return false;
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
  if (!reply.id || !reply.lead_email || !env.INSTANTLY_API_KEY) {
    console.warn(`Missing reply id, lead_email, or INSTANTLY_API_KEY — skipping auto-reply for ${reply.from_email}`);
    return null;
  }

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

  // Houston hour with DST handled (America/Chicago = CST/CDT)
  const houstonHour = parseInt(
    new Intl.DateTimeFormat("en-US", { timeZone: "America/Chicago", hour: "numeric", hour12: false }).format(new Date()),
    10
  );
  let minDelay = 120, maxDelay = 420; // default: 2-7 min
  if (houstonHour >= 17) { minDelay = 300; maxDelay = 600; } // evening: 5-10 min
  else if (houstonHour >= 12) { minDelay = 180; maxDelay = 420; } // afternoon: 3-7 min
  const delaySeconds = minDelay + Math.floor(Math.random() * (maxDelay - minDelay));
  const sendAfter = new Date(Date.now() + delaySeconds * 1000).toISOString();
  await queueDelayedReply(env, {
    reply_to_uuid: reply.id,
    from_email: reply.lead_email,
    reply_text: replyText,
    send_after: sendAfter,
    delay_seconds: delaySeconds,
  });
  console.log(`Auto-reply queued for ${reply.from_email} — send after ${delaySeconds}s delay`);

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
  result = result.replace(/[^.!?]*\b(artificial intelligence|language model|chatbot|gpt|claude)\b[^.!?]*[.!?]?/gi, "").trim();
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
      `${CONFIG.ghl.api_url}/contacts/upsert`,
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
            { id: CONFIG.ghl.custom_fields.reply_text, value: (reply.body || "").slice(0, 500) },
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
      const pipelineStageId = classification === "hot_positive" ? CONFIG.ghl.pipeline_stages.interested : CONFIG.ghl.pipeline_stages.new;

      const searchUrl = new URL(`${CONFIG.ghl.api_url}/opportunities/search`);
      searchUrl.searchParams.set("location_id", env.GHL_LOCATION_ID);
      searchUrl.searchParams.set("pipeline_id", CONFIG.ghl.pipeline_id);
      searchUrl.searchParams.set("contact_id", result.contact_id);
      const existingRes = await fetch(searchUrl.toString(), { headers: ghlHeaders });
      const existingOpps = existingRes.ok ? ((await existingRes.json()).opportunities || []) : [];
      const openOpp = existingOpps.find((o) => o.status === "open");

      if (openOpp) {
        result.opportunity_id = openOpp.id;
        if (classification === "hot_positive" && openOpp.pipelineStageId !== CONFIG.ghl.pipeline_stages.interested) {
          const stageRes = await fetch(`${CONFIG.ghl.api_url}/opportunities/${openOpp.id}`, {
            method: "PUT",
            headers: ghlHeaders,
            body: JSON.stringify({ pipelineStageId: CONFIG.ghl.pipeline_stages.interested }),
          });
          if (!stageRes.ok) {
            const detail = await stageRes.text();
            console.error("GHL opportunity stage update failed:", stageRes.status, detail);
          }
        }
      } else {
        const oppRes = await fetch(
          `${CONFIG.ghl.api_url}/opportunities/`,
          {
            method: "POST",
            headers: ghlHeaders,
            body: JSON.stringify({
              locationId: env.GHL_LOCATION_ID,
              pipelineId: CONFIG.ghl.pipeline_id,
              pipelineStageId,
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

  const esc = (s) => (s || "").replace(/[*_`[\]()]/g, "");

  const message =
    `${emoji} *${label}*\n` +
    `*Lead:* ${esc(reply.from_name) || "Unknown"} — ${esc(reply.from_email) || ""}\n` +
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

  const esc = (s) => (s || "").replace(/[*_`~<>()[\]]/g, "");

  const message =
    `${emoji} *${label}*\n` +
    `*From:* ${esc(reply.from_name) || "Unknown"} — ${esc(reply.from_email) || ""}\n` +
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
    if (data.sending) {
      const stuckMs = Date.now() - (data.sending_since || 0);
      if (stuckMs < 5 * 60 * 1000) continue;
      console.warn(`Unsticking delayed reply ${key.name} — stuck in sending for ${Math.round(stuckMs / 1000)}s`);
      data.sending = false;
      data.retry_count = (data.retry_count || 0) + 1;
    }
    const retries = data.retry_count || 0;
    if (retries >= 3) {
      console.error(`Delayed reply for ${data.reply_to_uuid} failed 3 times — giving up`);
      await env.REPLY_STATE.delete(key.name);
      continue;
    }
    const sendAfter = new Date(data.send_after);

    if (new Date() < sendAfter) continue;

    try {
      await env.REPLY_STATE.put(key.name, JSON.stringify({ ...data, sending: true, sending_since: Date.now() }), { expirationTtl: 60 * 60 * 24 });
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

async function removeFromInstantlyCampaign(email, campaignId, env) {
  if (!env.INSTANTLY_API_KEY) return;
  try {
    const res = await fetch("https://api.instantly.ai/api/v2/block-lists-entries", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.INSTANTLY_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ bl_value: email }),
    });
    if (res.ok) {
      console.log(`Blocklisted ${email} (negative reply from campaign ${campaignId})`);
    } else {
      console.warn(`Blocklist failed for ${email}: ${res.status}`);
    }
  } catch (err) {
    console.error(`Blocklist error for ${email}:`, err);
  }
}

// Removes a single lead from one specific campaign (per-campaign, NOT global blocklist).
// Safe for hot leads — does not prevent future campaign re-engagement.
async function pauseLeadInInstantly(email, campaignId, env) {
  if (!email || !campaignId) {
    console.warn("pauseLeadInInstantly: missing email or campaignId — skipping");
    return;
  }
  if (!env.INSTANTLY_API_KEY) return;
  try {
    // Step 1: look up the lead's UUID by email + campaign
    const listRes = await fetch("https://api.instantly.ai/api/v2/leads/list", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.INSTANTLY_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ contacts: [email], campaign: campaignId }),
    });
    if (!listRes.ok) {
      console.error(`pauseLeadInInstantly: lead lookup failed for ${email}: ${listRes.status}`);
      return;
    }
    const listData = await listRes.json();
    const lead = (listData.items || [])[0];
    if (!lead?.id) {
      console.warn(`pauseLeadInInstantly: lead not found for ${email} in campaign ${campaignId}`);
      return;
    }

    // Step 2: delete the lead from this campaign only (campaign-scoped DELETE)
    const delRes = await fetch("https://api.instantly.ai/api/v2/leads", {
      method: "DELETE",
      headers: {
        Authorization: `Bearer ${env.INSTANTLY_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ campaign_id: campaignId, ids: [lead.id] }),
    });
    if (delRes.ok) {
      console.log(`Paused lead in Instantly campaign: ${email} ${campaignId}`);
    } else {
      const detail = await delRes.text();
      console.error(`Failed to pause lead in Instantly: ${email} ${delRes.status} ${detail}`);
    }
  } catch (err) {
    console.error(`pauseLeadInInstantly error for ${email}:`, err);
  }
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
    customFields: [{ id: CONFIG.ghl.custom_fields.revenue_range, value: revenue || "" }],
  };

  try {
    const res = await fetch("https://services.leadconnectorhq.com/contacts/upsert", {
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
 * GET /api/dashboard-extras?range=7d|30d|all
 * Returns hot leads, recent activity feed, and latest pipeline run from KV.
 */
async function handleDashboardExtras(url, env) {
  const range = url.searchParams.get("range") || "7d";

  const emptyResponse = {
    range,
    generated_at: new Date().toISOString(),
    hot_leads_this_week: [],
    recent_activity: [],
    latest_pipeline_run: null,
    counts: { total_replies_in_range: 0, hot_leads: 0 },
  };

  if (!env.REPLY_STATE) {
    return jsonResponse(emptyResponse);
  }

  // Compute start timestamp for date-range filtering
  const startDate = rangeToDate(range);
  const startMs = startDate ? new Date(startDate).getTime() : 0;

  // Scan all KV keys (bare reply IDs only)
  const listResult = await env.REPLY_STATE.list({ limit: 1000 });
  const allReplies = [];
  const pipelineEntries = [];

  for (const key of listResult.keys) {
    const name = key.name;

    // Collect pipeline entries separately
    if (name.startsWith("pipeline_")) {
      const raw = await env.REPLY_STATE.get(name);
      if (raw) {
        try { pipelineEntries.push(JSON.parse(raw)); } catch (_) {}
      }
      continue;
    }

    // Skip non-reply system keys
    if (name.startsWith("pending_reply_") || name.startsWith("seen_business_")) {
      continue;
    }

    const raw = await env.REPLY_STATE.get(name);
    if (!raw) continue;
    let record;
    try { record = JSON.parse(raw); } catch (_) { continue; }

    // Must have classification to be a reply record
    if (!record.classification) continue;

    allReplies.push({ key: name, ...record });
  }

  // Sort all replies by timestamp descending
  allReplies.sort((a, b) => {
    const ta = new Date(a.processed_at || a.started_at || 0).getTime();
    const tb = new Date(b.processed_at || b.started_at || 0).getTime();
    return tb - ta;
  });

  // Filter replies within the date range
  const repliesInRange = allReplies.filter((r) => {
    const t = new Date(r.processed_at || r.started_at || 0).getTime();
    return t >= startMs;
  });

  // Hot leads: hot_positive in date range, top 25
  const hotLeadsRaw = repliesInRange
    .filter((r) => r.classification === "hot_positive")
    .slice(0, 25);

  const hot_leads_this_week = hotLeadsRaw.map((r) => {
    const contactId = r.contact_id || null;
    const ghlUrl = contactId && env.GHL_LOCATION_ID
      ? `https://app.gohighlevel.com/v2/location/${env.GHL_LOCATION_ID}/contacts/detail/${contactId}`
      : null;
    const replyText = r.reply_text || r.body || r.text || "";
    return {
      reply_id: r.key,
      from_email: r.from_email || r.from_address_email || null,
      from_name: r.from_name || null,
      business: r.company || r.business || null,
      processed_at: r.processed_at || r.started_at || null,
      reply_quote_short: replyText.slice(0, 240),
      classification: r.classification,
      contact_id: contactId,
      ghl_url: ghlUrl,
    };
  });

  // Recent activity: top 10 across all classifications (already sorted desc)
  const recent_activity = allReplies.slice(0, 10).map((r) => ({
    reply_id: r.key,
    from_email: r.from_email || r.from_address_email || null,
    classification: r.classification,
    action: r.action || (r.auto_reply_sent ? "auto-replied" : "classified"),
    processed_at: r.processed_at || r.started_at || null,
  }));

  // Latest pipeline run
  pipelineEntries.sort((a, b) =>
    new Date(b.started_at || b.generated_at || 0) - new Date(a.started_at || a.generated_at || 0)
  );
  const latest_pipeline_run = pipelineEntries[0] || null;

  return jsonResponse({
    range,
    generated_at: new Date().toISOString(),
    hot_leads_this_week,
    recent_activity,
    latest_pipeline_run,
    counts: {
      total_replies_in_range: repliesInRange.length,
      hot_leads: hot_leads_this_week.length,
    },
  });
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

  if (!payload || (!payload.from_email && !payload.from_address_email && !payload.body)) {
    return jsonResponse({ success: true, received: true, skipped: "unrecognized_payload" });
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

  const [oppsRes, calendarRes] = await Promise.all([
    fetch(oppsUrl.toString(), { headers }),
    fetch(calendarUrl.toString(), { headers }).catch((err) => {
      console.error("GHL calendar fetch error:", err);
      return null;
    }),
  ]);

  // Count contacts created within the date range.
  //
  // GHL v2 GET /contacts startAfter is a pagination cursor (epoch ms of the
  // last seen contact's dateAdded), not a date filter — meta.total always
  // returns the all-time location count regardless of startAfter. POST
  // /contacts/search supports field/operator/value filters but the exact
  // operator string for dateAdded is not publicly documented in a
  // machine-readable form. We therefore page through contacts sorted by
  // dateAdded desc (newest first) and count until we hit a contact older
  // than startDate, capped at 1000 contacts to prevent runaway fetches.
  let contactsCreated = 0;
  if (startDate) {
    const startMs = new Date(startDate).getTime();
    const PAGE_SIZE = 100;
    const CAP = 1000;
    let fetched = 0;
    let cursorAfter = null;
    let cursorAfterId = null;
    let done = false;

    while (!done && fetched < CAP) {
      const url = new URL("https://services.leadconnectorhq.com/contacts/");
      url.searchParams.set("locationId", locationId);
      url.searchParams.set("limit", String(PAGE_SIZE));
      url.searchParams.set("sortBy", "dateAdded");
      url.searchParams.set("sortDirection", "desc");
      if (cursorAfter !== null) url.searchParams.set("startAfter", String(cursorAfter));
      if (cursorAfterId !== null) url.searchParams.set("startAfterId", cursorAfterId);

      // eslint-disable-next-line no-await-in-loop
      const res = await fetch(url.toString(), { headers });
      if (!res.ok) {
        console.error("GHL contacts page error:", res.status);
        break;
      }
      const data = await res.json();
      const page = data.contacts || [];
      if (page.length === 0) break;

      for (const contact of page) {
        const addedMs = contact.dateAdded ? new Date(contact.dateAdded).getTime() : 0;
        if (addedMs < startMs) {
          done = true;
          break;
        }
        contactsCreated++;
        fetched++;
      }

      // Advance pagination cursors from meta
      const meta = data.meta || {};
      if (!done && meta.startAfter !== undefined && meta.startAfter !== cursorAfter) {
        cursorAfter = meta.startAfter;
        cursorAfterId = meta.startAfterId ?? null;
      } else {
        break; // no more pages or cursor didn't advance
      }
    }
  } else {
    // No date range — fall back to all-time total from a single lightweight call
    const url = new URL("https://services.leadconnectorhq.com/contacts/");
    url.searchParams.set("locationId", locationId);
    url.searchParams.set("limit", "1");
    const res = await fetch(url.toString(), { headers });
    if (res.ok) {
      const data = await res.json();
      contactsCreated = data.meta?.total ?? data.total ?? 0;
    } else {
      console.error("GHL contacts error:", res.status);
    }
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

function checkWebhookAuth(request, env) {
  if (!env.INSTANTLY_WEBHOOK_SECRET) return false;
  return request.headers.get("X-Webhook-Secret") === env.INSTANTLY_WEBHOOK_SECRET;
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

async function runDailyPipeline(env, dryRun = false) {
  const runId = `run_${Date.now()}`;
  console.log(`Pipeline ${runId}: starting daily pipeline${dryRun ? " [DRY RUN]" : ""}`);

  const state = { run_id: runId, started_at: new Date().toISOString(), stages: {}, dry_run: dryRun };

  try {
    // Stage 1: Source leads via Serper Maps
    const leads = await stageSource(env, runId, dryRun);
    state.stages.source = { count: leads.length, status: "complete" };
    console.log(`Pipeline ${runId}: sourced ${leads.length} leads`);

    if (leads.length === 0) {
      state.status = "complete_no_leads";
      await savePipelineState(env, state);
      return state;
    }

    // Stage 2: Enrich with AnymailFinder
    const enriched = await stageEnrich(leads, env, dryRun);
    const enrichedCount = enriched.filter((l) => l.status === "enriched").length;
    const skippedAlreadySeen = enriched.filter((l) => l.status === "seen_already").length;
    state.stages.enrich = { count: enrichedCount, skipped_already_seen: skippedAlreadySeen, status: "complete" };
    console.log(`Pipeline ${runId}: enriched ${enrichedCount}/${leads.length} (${skippedAlreadySeen} skipped — already seen)`);

    // Stage 3: Verify with Million Verifier
    const verified = await stageVerify(enriched, env, dryRun);
    const verifiedCount = verified.filter((l) => l.status === "verified").length;
    state.stages.verify = { count: verifiedCount, status: "complete" };
    console.log(`Pipeline ${runId}: verified ${verifiedCount}/${enrichedCount}`);

    // Stage 4: Personalize with OpenRouter
    const personalized = await stagePersonalize(verified, env, dryRun);
    const personalizedCount = personalized.filter((l) => l.status === "personalized").length;
    state.stages.personalize = { count: personalizedCount, status: "complete" };
    console.log(`Pipeline ${runId}: personalized ${personalizedCount}/${verifiedCount}`);

    // Stage 5: Upload to Instantly
    const uploadResult = await stageUpload(personalized, env, dryRun);
    state.stages.upload = uploadResult;
    console.log(`Pipeline ${runId}: uploaded ${uploadResult.uploaded}/${uploadResult.total}`);

    state.status = "complete";
    state.completed_at = new Date().toISOString();
    state.skipped_already_seen = skippedAlreadySeen;
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

async function stageSource(env, runId, dryRun = false) {
  if (dryRun) {
    console.log("stageSource [DRY RUN]: returning mock leads");
    const ts = new Date().toISOString();
    const industries = CONFIG.icp.industries;
    const mockBusinesses = [
      { name: "Sparkle Car Wash", domain: "sparklecarwash.com", city: "Houston", state: "TX", industry: industries[0], rating: 4.5, reviews_count: 213, phone: "713-555-0101" },
      { name: "Tony's Pizzeria", domain: "tonyspizzeria.com", city: "Houston", state: "TX", industry: industries[1], rating: 4.7, reviews_count: 387, phone: "713-555-0102" },
      { name: "Hometown Laundromat", domain: "hometownlaundromat.com", city: "Houston", state: "TX", industry: industries[2], rating: 4.1, reviews_count: 89, phone: "713-555-0103" },
      { name: "Gulf Coast Marina", domain: "gulfcoastmarina.com", city: "Pasadena", state: "TX", industry: industries[3], rating: 4.6, reviews_count: 145, phone: "713-555-0104" },
      { name: "Lone Star Oil Co", domain: "lonestaroil.com", city: "Katy", state: "TX", industry: industries[4], rating: 4.3, reviews_count: 62, phone: "713-555-0105" },
      { name: "Quick Fix Auto Repair", domain: "quickfixauto.com", city: "Sugar Land", state: "TX", industry: industries[5], rating: 4.8, reviews_count: 521, phone: "713-555-0106" },
      { name: "Prestige Dry Cleaners", domain: "prestigedrycleaner.com", city: "The Woodlands", state: "TX", industry: industries[6], rating: 4.4, reviews_count: 177, phone: "713-555-0107" },
      { name: "Sweet Crumbs Bakery", domain: "sweetcrumbs.com", city: "Pearland", state: "TX", industry: industries[7], rating: 4.9, reviews_count: 302, phone: "713-555-0108" },
      { name: "Houston Print House", domain: "houstonprinthouse.com", city: "Houston", state: "TX", industry: industries[8], rating: 4.2, reviews_count: 54, phone: "713-555-0109" },
      { name: "Texan Pest Solutions", domain: "texanpest.com", city: "Houston", state: "TX", industry: industries[9], rating: 4.5, reviews_count: 198, phone: "713-555-0110" },
      { name: "Bayou Manufacturing", domain: "bayoumanufacturing.com", city: "Pasadena", state: "TX", industry: industries[10], rating: 4.0, reviews_count: 41, phone: "713-555-0111" },
      { name: "Riverside Consulting Group", domain: "riversideconsulting.com", city: "Houston", state: "TX", industry: industries[11], rating: 4.6, reviews_count: 83, phone: "713-555-0112" },
      { name: "Katy Car Wash Express", domain: "katycarwash.com", city: "Katy", state: "TX", industry: industries[0], rating: 4.3, reviews_count: 156, phone: "713-555-0113" },
      { name: "Mama Rosa's Pizza", domain: "mamarosaspizza.com", city: "Sugar Land", state: "TX", industry: industries[1], rating: 4.8, reviews_count: 441, phone: "713-555-0114" },
      { name: "Sudz Laundromat", domain: "sudzlaundromat.com", city: "Katy", state: "TX", industry: industries[2], rating: 3.9, reviews_count: 67, phone: "713-555-0115" },
      { name: "Woodlands Auto Care", domain: "woodlandsautocare.com", city: "The Woodlands", state: "TX", industry: industries[5], rating: 4.7, reviews_count: 289, phone: "713-555-0116" },
      { name: "Pearl Clean Dry Cleaning", domain: "pearlcleandry.com", city: "Pearland", state: "TX", industry: industries[6], rating: 4.5, reviews_count: 102, phone: "713-555-0117" },
      { name: "Harvest Moon Bakery", domain: "harvestmoonbakery.com", city: "Katy", state: "TX", industry: industries[7], rating: 4.6, reviews_count: 234, phone: "713-555-0118" },
      { name: "Gulf Print & Signs", domain: "gulfprintsigns.com", city: "Pasadena", state: "TX", industry: industries[8], rating: 4.1, reviews_count: 38, phone: "713-555-0119" },
      { name: "Cypress Pest Control", domain: "cypresspest.com", city: "The Woodlands", state: "TX", industry: industries[9], rating: 4.4, reviews_count: 171, phone: "713-555-0120" },
    ];
    return mockBusinesses.map((b) => ({
      business_name: b.name,
      domain: b.domain,
      city: b.city,
      state: b.state,
      industry: b.industry,
      rating: b.rating,
      reviews_count: b.reviews_count,
      phone: b.phone,
      website: `https://www.${b.domain}`,
      address: `123 Main St, ${b.city}, ${b.state}`,
      source: "mock_dry_run",
      source_query: `${b.industry} ${b.city}, ${b.state}`,
      sourced_at: ts,
      status: "sourced",
      pipeline_run_id: runId,
    }));
  }

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

// --- Cross-run dedup helpers (Feature 2) ---

function buildSeenBusinessKey(lead) {
  const domain = (lead.domain || "").toLowerCase().trim();
  const name = (lead.business_name || "").toLowerCase().replace(/[^a-z0-9\s]/g, "").replace(/\s+/g, " ").trim();
  if (!domain && !name) return null;
  return `seen_business_${domain}|${name}`;
}

async function isBusinessSeen(env, lead) {
  if (!env.REPLY_STATE) return false;
  const key = buildSeenBusinessKey(lead);
  if (!key) return false;
  try {
    const val = await env.REPLY_STATE.get(key);
    return val !== null;
  } catch (err) {
    console.warn("seen-business KV read error:", err);
    return false;
  }
}

async function markBusinessSeen(env, lead) {
  if (!env.REPLY_STATE) return;
  const key = buildSeenBusinessKey(lead);
  if (!key) return;
  try {
    await env.REPLY_STATE.put(key, JSON.stringify({
      seen_at: new Date().toISOString(),
      business_name: lead.business_name,
      domain: lead.domain,
    }), { expirationTtl: 60 * 24 * 60 * 60 }); // 60 days
  } catch (err) {
    console.warn("seen-business KV write error:", err);
  }
}

// --- stageEnrich ---

async function stageEnrich(leads, env, dryRun = false) {
  if (dryRun) {
    console.log("stageEnrich [DRY RUN]: faking enrichment, skipping AnymailFinder");
    for (const lead of leads) {
      if (lead.status !== "sourced") continue;
      lead.owner_email = `owner@${lead.domain || "example.com"}`;
      lead.owner_name = lead.owner_name || lead.business_name.split(/\s+/)[0] || "there";
      lead.email_confidence = 80;
      lead.email_type = "generic";
      lead.enriched_at = new Date().toISOString();
      lead.status = "enriched";
    }
    return leads;
  }

  if (!env.ANYMAILFINDER_API_KEY) {
    console.warn("ANYMAILFINDER_API_KEY not set — skipping enrichment");
    return leads;
  }

  const minConf = CONFIG.enrichment.anymailfinder_min_confidence;

  for (const lead of leads) {
    if (lead.status !== "sourced") continue;
    if (lead.owner_email || !lead.domain) continue;

    // Cross-run dedup: skip leads we already enriched in a prior pipeline run
    const seen = await isBusinessSeen(env, lead);
    if (seen) {
      console.log(`stageEnrich: skipping already-seen business "${lead.business_name}" (${lead.domain})`);
      lead.status = "seen_already";
      continue;
    }

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
        // Mark as seen so future runs skip re-enriching this business
        await markBusinessSeen(env, lead);
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

async function stageVerify(leads, env, dryRun = false) {
  if (dryRun) {
    console.log("stageVerify [DRY RUN]: marking all enriched leads as verified, skipping Million Verifier");
    for (const lead of leads) {
      if (lead.status === "enriched" && lead.owner_email) {
        lead.status = "verified";
        lead.email_verified = true;
        lead.email_verification_result = "mock_ok";
        lead.verified_at = new Date().toISOString();
      }
    }
    return leads;
  }

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

async function stagePersonalize(leads, env, dryRun = false) {
  if (dryRun) {
    console.log("stagePersonalize [DRY RUN]: using mock openers, skipping OpenRouter");
    for (const lead of leads) {
      if (lead.status !== "verified") continue;
      lead.personalized_opener = getMockOpener(lead);
      lead.opener_model = "mock_dry_run";
      lead.personalized_at = new Date().toISOString();
      lead.status = "personalized";
    }
    return leads;
  }

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
  if (opener.includes("!") || opener.includes("?")) return false;
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

async function stageUpload(leads, env, dryRun = false) {
  const personalized = leads.filter((l) => l.status === "personalized");
  const personalizedCount = personalized.length;

  if (dryRun) {
    console.log(`stageUpload [DRY RUN]: would upload ${personalizedCount} leads — skipping Instantly POST`);
    return { uploaded: 0, errors: 0, total: personalizedCount, would_upload: personalizedCount, dry: true };
  }

  if (!env.INSTANTLY_API_KEY || !env.CAMPAIGN_ID) {
    console.warn("INSTANTLY_API_KEY or CAMPAIGN_ID not set — skipping upload");
    return { uploaded: 0, errors: 0, total: 0 };
  }

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
    const url = new URL(request.url);
    const dryRun = url.searchParams.get("dry_run") === "true";
    const result = await runDailyPipeline(env, dryRun);
    return jsonResponse({ success: true, dry_run: dryRun, ...result });
  } catch (err) {
    console.error("Pipeline error:", err);
    return jsonResponse({ success: false, error: err.message }, 500);
  }
}

async function handlePipelineStatus(env) {
  if (!env.REPLY_STATE) {
    return jsonResponse({ status: "no_kv_namespace" });
  }

  const list = await env.REPLY_STATE.list({ prefix: "pipeline_", limit: 20 });
  const states = [];
  for (const key of list.keys) {
    const val = await env.REPLY_STATE.get(key.name);
    if (val) {
      try { states.push(JSON.parse(val)); } catch (_) {}
    }
  }

  states.sort((a, b) => new Date(b.started_at || b.generated_at || 0) - new Date(a.started_at || a.generated_at || 0));
  return jsonResponse({ recent_runs: states.slice(0, 5) });
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
