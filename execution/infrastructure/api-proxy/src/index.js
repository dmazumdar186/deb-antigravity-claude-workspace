/**
 * Accessory Masters API Proxy — Cloudflare Worker
 *
 * Routes:
 *   POST /api/form-submit    — Contact form -> GoHighLevel
 *   GET  /api/dashboard      — Aggregated metrics from Instantly + GHL
 *   POST /api/webhook/reply  — Instantly reply webhook receiver
 *
 * Secrets (wrangler secret put):
 *   GHL_API_KEY, INSTANTLY_API_KEY
 *
 * Env vars (wrangler.toml [vars]):
 *   GHL_LOCATION_ID, ALLOWED_ORIGINS
 */

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const { pathname } = url;
    const method = request.method;

    // --- CORS preflight ---
    if (method === "OPTIONS") {
      return corsResponse(request, env, new Response(null, { status: 204 }));
    }

    try {
      // --- Routing ---
      if (method === "POST" && pathname === "/api/form-submit") {
        return corsResponse(request, env, await handleFormSubmit(request, env));
      }

      if (method === "GET" && pathname === "/api/dashboard") {
        return corsResponse(request, env, await handleDashboard(url, env));
      }

      if (method === "POST" && pathname === "/api/webhook/reply") {
        return corsResponse(request, env, await handleReplyWebhook(request));
      }

      if (method === "GET" && pathname === "/api/variants") {
        return corsResponse(request, env, await handleVariants(url, env));
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
};

// ---------------------------------------------------------------------------
// Route handlers
// ---------------------------------------------------------------------------

/**
 * POST /api/form-submit
 * Receives contact form data and creates a GHL contact.
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

  const { firstName, lastName } = parseName(name);

  const ghlBody = {
    locationId: env.GHL_LOCATION_ID,
    firstName,
    lastName,
    email,
    companyName: company || "",
    source: "website",
    tags: ["website lead"],
    customFields: [{ key: "revenue_range", value: revenue || "" }],
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
 * Aggregates metrics from Instantly.ai and GoHighLevel.
 */
async function handleDashboard(url, env) {
  const range = url.searchParams.get("range") || "7d";
  if (!["7d", "30d", "all"].includes(range)) {
    return jsonResponse({ error: "Invalid range. Use 7d, 30d, or all." }, 400);
  }

  const startDate = rangeToDate(range);

  // Fetch both sources in parallel; tolerate partial failures.
  const [emailData, crmData] = await Promise.allSettled([
    fetchInstantlyMetrics(env, startDate),
    fetchGHLMetrics(env, startDate),
  ]);

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

  return jsonResponse(response);
}

/**
 * POST /api/webhook/reply
 * Receives Instantly reply webhooks. Logs and returns 200 OK.
 */
async function handleReplyWebhook(request) {
  let payload;
  try {
    payload = await request.json();
  } catch {
    return jsonResponse({ success: false, error: "Invalid JSON body" }, 400);
  }

  // Log the payload for future wiring into the classification pipeline.
  console.log("Reply webhook received:", JSON.stringify(payload));

  return jsonResponse({ success: true, received: true });
}

/**
 * GET /api/variants?campaign_id=X
 * Fetches per-step analytics from Instantly for variant performance.
 */
async function handleVariants(url, env) {
  const campaignId = url.searchParams.get("campaign_id");
  if (!campaignId) {
    return jsonResponse({ error: "campaign_id parameter required" }, 400);
  }

  try {
    const res = await fetch(
      `https://api.instantly.ai/api/v2/campaigns/${campaignId}/analytics/steps`,
      {
        headers: { Authorization: `Bearer ${env.INSTANTLY_API_KEY}` },
      },
    );

    if (!res.ok) {
      throw new Error(`Instantly API ${res.status}: ${await res.text()}`);
    }

    const data = await res.json();
    const steps = data.steps || data.data || [];

    const variants = steps.map((step, i) => ({
      step_id: step.id || step.step_id || `step_${i}`,
      label: step.subject || step.name || `Step ${i + 1}`,
      emails_sent: step.total_sent ?? step.sent ?? 0,
      replies: step.total_replied ?? step.replied ?? 0,
      response_rate_pct: (step.total_sent ?? step.sent ?? 0) > 0
        ? +((step.total_replied ?? step.replied ?? 0) / (step.total_sent ?? step.sent ?? 0) * 100).toFixed(1)
        : 0,
    }));

    return jsonResponse({ campaign_id: campaignId, variants });
  } catch (err) {
    console.error("Variants fetch failed:", err);
    return jsonResponse(
      { error: "Failed to fetch variant analytics" },
      502,
    );
  }
}

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

async function fetchInstantlyMetrics(env, startDate) {
  const params = new URLSearchParams();
  if (startDate) {
    params.set("start_date", startDate);
  }

  const url = `https://api.instantly.ai/api/v2/campaigns/analytics/overview?${params.toString()}`;

  const res = await fetch(url, {
    headers: { Authorization: `Bearer ${env.INSTANTLY_API_KEY}` },
  });

  if (!res.ok) {
    throw new Error(`Instantly API ${res.status}: ${await res.text()}`);
  }

  const data = await res.json();

  const sent = data.total_sent ?? 0;
  const delivered = data.total_delivered ?? sent;
  const opened = data.total_opened ?? 0;
  const replies = data.total_replied ?? 0;
  const bounces = data.total_bounced ?? 0;

  return {
    emails_sent: sent,
    emails_delivered: delivered,
    deliverability_pct: sent ? +(delivered / sent * 100).toFixed(1) : 0,
    open_rate_pct: delivered ? +(opened / delivered * 100).toFixed(1) : 0,
    replies,
    reply_rate_pct: delivered ? +(replies / delivered * 100).toFixed(1) : 0,
    bounces,
    bounce_rate_pct: sent ? +(bounces / sent * 100).toFixed(1) : 0,
    unsubscribes: data.total_unsubscribed ?? 0,
  };
}

async function fetchGHLMetrics(env, startDate) {
  const headers = {
    Authorization: `Bearer ${env.GHL_API_KEY}`,
    "Content-Type": "application/json",
    Version: "2021-07-28",
  };

  const locationId = env.GHL_LOCATION_ID;

  // Contacts count
  const contactsUrl = new URL(
    "https://services.leadconnectorhq.com/contacts/",
  );
  contactsUrl.searchParams.set("locationId", locationId);
  contactsUrl.searchParams.set("limit", "1"); // we only need the total
  if (startDate) {
    contactsUrl.searchParams.set("startAfter", startDate);
  }

  // Opportunities
  const oppsUrl = new URL(
    "https://services.leadconnectorhq.com/opportunities/search",
  );
  oppsUrl.searchParams.set("location_id", locationId);

  const [contactsRes, oppsRes] = await Promise.all([
    fetch(contactsUrl.toString(), { headers }),
    fetch(oppsUrl.toString(), { headers }),
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

  return {
    contacts_created: contactsCreated,
    opportunities_total: opportunitiesTotal,
    opportunities_open: opportunitiesOpen,
    opportunities_won: opportunitiesWon,
    appointments_booked: 0,
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

/**
 * Convert a range string to an ISO date string for the start of the window.
 * Returns null for "all".
 */
function rangeToDate(range) {
  if (range === "all") return null;
  const days = range === "30d" ? 30 : 7;
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().split("T")[0]; // YYYY-MM-DD
}

function jsonResponse(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/**
 * Wrap a Response with CORS headers. Only allows listed origins.
 */
function corsResponse(request, env, response) {
  const origin = request.headers.get("Origin") || "";
  const allowed = (env.ALLOWED_ORIGINS || "").split(",").map((s) => s.trim());

  const headers = new Headers(response.headers);
  headers.set("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  headers.set("Access-Control-Allow-Headers", "Content-Type, Authorization");
  headers.set("Access-Control-Max-Age", "86400");

  if (allowed.includes(origin)) {
    headers.set("Access-Control-Allow-Origin", origin);
  }

  return new Response(response.body, {
    status: response.status,
    headers,
  });
}
