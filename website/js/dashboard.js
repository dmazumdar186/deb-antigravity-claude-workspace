/**
 * Accessory Masters — Metrics Dashboard
 *
 * Fetches email + CRM metrics from a Cloudflare Worker proxy and
 * renders them into the dashboard UI. Falls back to demo data when
 * the API endpoint is unreachable (e.g. Worker not yet deployed).
 *
 * IMPORTANT: No API keys in client-side code. All API calls go
 * through the Worker proxy which holds the secrets.
 */

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

const API_BASE = "/api";

const DEMO_DATA = {
  email: {
    emails_sent: 850,
    emails_delivered: 830,
    deliverability_pct: 97.6,
    open_rate_pct: 42.3,
    reply_rate_pct: 3.8,
    bounce_rate_pct: 2.4,
    replies: 32,
    bounces: 20,
    unsubscribes: 2,
  },
  crm: {
    contacts_created: 12,
    opportunities_total: 8,
    opportunities_open: 5,
    opportunities_won: 3,
    appointments_booked: 4,
    pipeline_value: 285000,
  },
  variants: [
    { variant_id: "v1_cold_open", type: "human", label: "Cold Open", emails_sent: 250, replies: 10, response_rate_pct: 4.0 },
    { variant_id: "v2_bump", type: "human", label: "Bump", emails_sent: 220, replies: 7, response_rate_pct: 3.2 },
    { variant_id: "v3_case_study", type: "human", label: "Case Study", emails_sent: 200, replies: 9, response_rate_pct: 4.5 },
    { variant_id: "v4_free_value", type: "human", label: "Free Value", emails_sent: 180, replies: 5, response_rate_pct: 2.8 },
    { variant_id: "ai_20260430", type: "ai", label: "AI Challenger", emails_sent: 150, replies: 7, response_rate_pct: 4.7 },
  ],
  generated_at: new Date().toISOString(),
};

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

let currentRange = "7d";
let isDemo = false;

// ---------------------------------------------------------------------------
// DOM references
// ---------------------------------------------------------------------------

const els = {};

function cacheElements() {
  els.emailsSent = document.getElementById("metric-emails-sent");
  els.deliverability = document.getElementById("metric-deliverability");
  els.deliverabilityUnit = document.getElementById("metric-deliverability-unit");
  els.cardDeliverability = document.getElementById("card-deliverability");
  els.replyRate = document.getElementById("metric-reply-rate");
  els.replyRateUnit = document.getElementById("metric-reply-rate-unit");
  els.cardReplyRate = document.getElementById("card-reply-rate");
  els.bounceRate = document.getElementById("metric-bounce-rate");
  els.bounceRateUnit = document.getElementById("metric-bounce-rate-unit");
  els.cardBounceRate = document.getElementById("card-bounce-rate");
  els.replies = document.getElementById("metric-replies");
  els.openRate = document.getElementById("metric-open-rate");
  els.contacts = document.getElementById("metric-contacts");
  els.oppsTotal = document.getElementById("metric-opps-total");
  els.oppsOpen = document.getElementById("metric-opps-open");
  els.oppsWon = document.getElementById("metric-opps-won");
  els.appointments = document.getElementById("metric-appointments");
  els.pipelineValue = document.getElementById("metric-pipeline-value");
  els.lastUpdated = document.getElementById("lastUpdated");
  els.demoBanner = document.getElementById("demoBanner");
  els.refreshBtn = document.getElementById("refreshBtn");
  els.refreshIcon = document.getElementById("refreshIcon");
  els.variantsGrid = document.getElementById("variants-grid");
  els.variantRecommendation = document.getElementById("variant-recommendation");
  els.variantRecommendationText = document.getElementById("variant-recommendation-text");
}

// ---------------------------------------------------------------------------
// Formatting helpers
// ---------------------------------------------------------------------------

/**
 * Format an integer with comma separators.
 * @param {number} n
 * @returns {string}
 */
function fmtInt(n) {
  return Number(n).toLocaleString("en-US");
}

/**
 * Format a percentage to 1 decimal place.
 * @param {number} n
 * @returns {string}
 */
function fmtPct(n) {
  return Number(n).toFixed(1);
}

/**
 * Format a dollar value with commas and no decimals.
 * @param {number} n
 * @returns {string}
 */
function fmtDollar(n) {
  return "$" + Math.round(n).toLocaleString("en-US");
}

/**
 * Format an ISO timestamp into a readable date/time string.
 * @param {string} iso
 * @returns {string}
 */
function fmtTimestamp(iso) {
  try {
    const d = new Date(iso);
    return d.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    }) + " at " + d.toLocaleTimeString("en-US", {
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

// ---------------------------------------------------------------------------
// Conditional color indicators
// ---------------------------------------------------------------------------

/**
 * Apply conditional CSS classes to a metric card based on thresholds.
 * Clears previous indicator classes before applying new ones.
 *
 * @param {HTMLElement} card  The card container element.
 * @param {HTMLElement} value The value text element.
 * @param {HTMLElement} unit  The unit text element (e.g. the "%" sign).
 * @param {"green"|"orange"|null} indicator  Which indicator to apply.
 */
function applyIndicator(card, value, unit, indicator) {
  // Reset
  card.classList.remove("indicator-green-bg", "indicator-orange-bg");
  value.classList.remove("indicator-green", "indicator-orange");
  if (unit) unit.classList.remove("indicator-green", "indicator-orange");

  if (indicator === "green") {
    card.classList.add("indicator-green-bg");
    value.classList.add("indicator-green");
    if (unit) unit.classList.add("indicator-green");
  } else if (indicator === "orange") {
    card.classList.add("indicator-orange-bg");
    value.classList.add("indicator-orange");
    if (unit) unit.classList.add("indicator-orange");
  }
}

// ---------------------------------------------------------------------------
// Render
// ---------------------------------------------------------------------------

/**
 * Populate all metric cards with data from the API response.
 * @param {object} data  The JSON response matching report_generator.py output.
 */
function renderData(data) {
  const email = data.email || {};
  const crm = data.crm || {};

  // --- Email Performance ---
  els.emailsSent.textContent = fmtInt(email.emails_sent || 0);
  els.deliverability.textContent = fmtPct(email.deliverability_pct || 0);
  els.replyRate.textContent = fmtPct(email.reply_rate_pct || 0);
  els.bounceRate.textContent = fmtPct(email.bounce_rate_pct || 0);
  els.replies.textContent = fmtInt(email.replies || 0);
  els.openRate.textContent = fmtPct(email.open_rate_pct || 0);

  // Deliverability indicator
  const deliv = email.deliverability_pct || 0;
  applyIndicator(
    els.cardDeliverability,
    els.deliverability,
    els.deliverabilityUnit,
    deliv >= 95 ? "green" : deliv < 90 ? "orange" : null
  );

  // Reply rate indicator
  const reply = email.reply_rate_pct || 0;
  applyIndicator(
    els.cardReplyRate,
    els.replyRate,
    els.replyRateUnit,
    reply >= 3 ? "green" : null
  );

  // Bounce rate indicator
  const bounce = email.bounce_rate_pct || 0;
  applyIndicator(
    els.cardBounceRate,
    els.bounceRate,
    els.bounceRateUnit,
    bounce > 3 ? "orange" : null
  );

  // --- CRM Pipeline ---
  els.contacts.textContent = fmtInt(crm.contacts_created || 0);
  els.oppsTotal.textContent = fmtInt(crm.opportunities_total || 0);
  els.oppsOpen.textContent = fmtInt(crm.opportunities_open || 0);
  els.oppsWon.textContent = fmtInt(crm.opportunities_won || 0);
  els.appointments.textContent = fmtInt(crm.appointments_booked || 0);
  els.pipelineValue.textContent = fmtDollar(crm.pipeline_value || 0);

  // --- Timestamp ---
  els.lastUpdated.textContent = fmtTimestamp(data.generated_at || new Date().toISOString());
}

/**
 * Render variant performance cards into the variants grid.
 * @param {Array|null} variants  Array of variant objects from the API.
 */
function renderVariants(variants) {
  if (!els.variantsGrid || !variants || !variants.length) return;

  els.variantsGrid.innerHTML = "";

  let bestRate = -1, worstRate = Infinity;
  variants.forEach((v) => {
    if (v.response_rate_pct > bestRate) bestRate = v.response_rate_pct;
    if (v.response_rate_pct < worstRate) worstRate = v.response_rate_pct;
  });

  variants.forEach((v) => {
    const isAi = v.type === "ai";
    const isBest = v.response_rate_pct === bestRate;
    const isWorst = v.response_rate_pct === worstRate;

    const card = document.createElement("div");
    card.className = "metric-card bg-ink-900 p-6" +
      (isBest ? " indicator-green-bg" : "") +
      (isWorst ? " indicator-orange-bg" : "");

    let labelHtml = `<div class="text-[10px] tracking-widest uppercase text-bone-400 font-mono mb-3">${v.label}`;
    if (isAi) {
      labelHtml += ` <span class="accent-bg text-[9px] px-1.5 py-0.5 rounded-full ml-1 normal-case tracking-normal">AI</span>`;
    }
    labelHtml += `</div>`;

    const rateClass = isBest ? "indicator-green" : isWorst ? "indicator-orange" : "";
    const rateHtml = `<div class="flex items-baseline gap-2">
      <span class="font-serif text-4xl md:text-5xl ${rateClass}" style="letter-spacing:-0.02em;">${fmtPct(v.response_rate_pct)}</span>
      <span class="text-xl accent-fg ${rateClass}">%</span>
    </div>`;

    const sentHtml = `<div class="text-xs font-mono text-bone-400 mt-2">${fmtInt(v.emails_sent)} sent &middot; ${fmtInt(v.replies)} replies</div>`;

    card.innerHTML = labelHtml + rateHtml + sentHtml;
    els.variantsGrid.appendChild(card);
  });

  const aiVariant = variants.find((v) => v.type === "ai");
  const humanVariants = variants.filter((v) => v.type === "human");
  const worstHuman = humanVariants.reduce((min, v) => v.response_rate_pct < min.response_rate_pct ? v : min, humanVariants[0]);

  if (aiVariant && worstHuman && aiVariant.response_rate_pct > worstHuman.response_rate_pct) {
    els.variantRecommendation.classList.remove("hidden");
    els.variantRecommendationText.textContent =
      `AI variant "${aiVariant.label}" (${fmtPct(aiVariant.response_rate_pct)}%) outperforms "${worstHuman.label}" (${fmtPct(worstHuman.response_rate_pct)}%). Consider replacing.`;
  } else {
    els.variantRecommendation.classList.add("hidden");
  }
}

// ---------------------------------------------------------------------------
// Data fetching
// ---------------------------------------------------------------------------

/**
 * Fetch dashboard data from the Worker endpoint.
 * Falls back to DEMO_DATA if the fetch fails.
 * @param {string} range  One of "7d", "30d", "all".
 */
async function fetchData(range) {
  // Show loading state
  setLoading(true);

  try {
    const resp = await fetch(`${API_BASE}/dashboard?range=${range}`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();

    isDemo = false;
    els.demoBanner.classList.add("hidden");
    renderData(data);
    renderVariants(data.variants || null);
  } catch {
    // Worker not reachable — fall back to demo data
    isDemo = true;
    els.demoBanner.classList.remove("hidden");
    renderData(DEMO_DATA);
    renderVariants(DEMO_DATA.variants);
  } finally {
    setLoading(false);
  }
}

/**
 * Toggle loading state on the refresh button.
 * @param {boolean} loading
 */
function setLoading(loading) {
  if (loading) {
    els.refreshIcon.classList.add("spin");
    els.refreshBtn.disabled = true;
    els.refreshBtn.classList.add("opacity-60", "cursor-not-allowed");
  } else {
    els.refreshIcon.classList.remove("spin");
    els.refreshBtn.disabled = false;
    els.refreshBtn.classList.remove("opacity-60", "cursor-not-allowed");
  }
}

// ---------------------------------------------------------------------------
// Event handlers
// ---------------------------------------------------------------------------

function setupEventListeners() {
  // Range selector buttons
  document.querySelectorAll(".range-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      currentRange = btn.dataset.range;

      // Update active state
      document.querySelectorAll(".range-btn").forEach((b) => {
        b.classList.remove("active");
        b.classList.add("text-bone-300");
      });
      btn.classList.add("active");
      btn.classList.remove("text-bone-300");

      fetchData(currentRange);
    });
  });

  // Refresh button
  els.refreshBtn.addEventListener("click", () => {
    fetchData(currentRange);
  });
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------

document.addEventListener("DOMContentLoaded", () => {
  cacheElements();
  setupEventListeners();
  fetchData(currentRange);
});
