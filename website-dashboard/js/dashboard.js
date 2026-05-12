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
// Admin secret helpers
// ---------------------------------------------------------------------------

/**
 * Retrieve the admin worker secret from localStorage.
 * @returns {string}
 */
function getWorkerSecret() {
  return localStorage.getItem("worker_secret") || "";
}

/**
 * Format an ISO timestamp as a human-readable relative time string.
 * @param {string|null} iso
 * @returns {string}
 */
function fmtRelativeTime(iso) {
  if (!iso) return "—";
  const now = Date.now();
  const t = new Date(iso).getTime();
  const diffMs = now - t;
  if (isNaN(diffMs)) return "—";
  const sec = Math.floor(diffMs / 1000);
  if (sec < 60) return `${sec}s ago`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const days = Math.floor(hr / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
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
// Dashboard extras: hot leads, recent activity, pipeline banner
// ---------------------------------------------------------------------------

/** Classification badge color map */
const CLASSIFICATION_COLORS = {
  hot_positive: "bg-amber-500 text-black",
  positive: "bg-emerald-600 text-white",
  negative: "bg-red-700 text-white",
  neutral: "bg-stone-600 text-white",
};

/**
 * Render hot leads into #hot-leads-container.
 * @param {Array} leads
 */
function renderHotLeads(leads) {
  const container = document.getElementById("hot-leads-container");
  const countEl = document.getElementById("hot-leads-count");
  if (!container) return;

  if (countEl) {
    countEl.textContent = leads.length ? `${leads.length} lead${leads.length === 1 ? "" : "s"}` : "";
  }

  if (!leads || !leads.length) {
    container.innerHTML =
      '<p class="text-sm text-bone-400 font-mono italic">No hot leads in this range yet — the system will surface them here the moment a prospect replies with intent.</p>';
    return;
  }

  const rows = leads.map((lead) => {
    const quote = lead.reply_quote_short
      ? `<blockquote class="mt-2 text-sm font-serif-italic text-bone-300 bg-ink-800 rounded-lg px-4 py-3 border-l-2" style="border-color:var(--accent);">${esc(lead.reply_quote_short)}</blockquote>`
      : "";
    const ghlBtn = lead.ghl_url
      ? `<a href="${esc(lead.ghl_url)}" target="_blank" rel="noopener"
            class="liquid-glass rounded-lg px-3 py-1.5 text-xs font-mono text-bone-200 hover:text-white transition whitespace-nowrap">
            Open in GHL &#x2197;
         </a>`
      : `<button disabled class="liquid-glass rounded-lg px-3 py-1.5 text-xs font-mono text-bone-400 cursor-not-allowed whitespace-nowrap opacity-50">Open in GHL</button>`;

    return `<div class="border-b hairline last:border-0 py-5 first:pt-0 last:pb-0">
      <div class="flex items-start justify-between gap-4 flex-wrap">
        <div class="flex-1 min-w-0">
          <div class="text-base font-medium text-white truncate">${esc(lead.business || "Unknown business")}</div>
          <div class="text-xs text-bone-400 font-mono mt-0.5">
            ${esc(lead.from_email || "—")} &middot; ${fmtRelativeTime(lead.processed_at)}
          </div>
          ${quote}
        </div>
        <div class="flex-shrink-0">${ghlBtn}</div>
      </div>
    </div>`;
  });

  container.innerHTML = rows.join("");
}

/**
 * Render recent activity into #recent-activity-container.
 * @param {Array} items
 */
function renderRecentActivity(items) {
  const container = document.getElementById("recent-activity-container");
  if (!container) return;

  if (!items || !items.length) {
    container.innerHTML = '<p class="text-sm text-bone-400 font-mono italic">No replies yet in this range.</p>';
    return;
  }

  const rows = items.map((item) => {
    const cls = item.classification || "neutral";
    const badgeClass = CLASSIFICATION_COLORS[cls] || "bg-stone-600 text-white";
    const email = (item.from_email || "—").slice(0, 30);
    const action = item.action || "classified";

    return `<div class="flex items-center gap-3 py-3 border-b hairline last:border-0 last:pb-0 first:pt-0 flex-wrap">
      <span class="text-[10px] font-mono px-2 py-0.5 rounded-full ${badgeClass} whitespace-nowrap">${esc(cls)}</span>
      <span class="text-sm text-bone-200 font-mono flex-1 min-w-0 truncate">${esc(email)}</span>
      <span class="text-xs text-bone-400 font-mono">${esc(action)}</span>
      <span class="text-xs text-bone-400 font-mono whitespace-nowrap">${fmtRelativeTime(item.processed_at)}</span>
    </div>`;
  });

  container.innerHTML = rows.join("");
}

/**
 * Render pipeline status banner into #pipeline-banner.
 * @param {object|null} run
 */
function renderPipelineBanner(run) {
  const banner = document.getElementById("pipeline-banner");
  if (!banner) return;

  if (!run) {
    banner.innerHTML = '<p class="text-sm text-bone-400 font-mono italic">No pipeline runs recorded yet.</p>';
    return;
  }

  const ts = run.started_at || run.generated_at || null;
  const relTime = fmtRelativeTime(ts);
  const ageMs = ts ? Date.now() - new Date(ts).getTime() : Infinity;
  const ageH = ageMs / (1000 * 60 * 60);

  let statusBadge, statusClass;
  if (run.error) {
    statusBadge = "Error";
    statusClass = "bg-red-700 text-white";
  } else if (ageH > 48) {
    statusBadge = "Stale";
    statusClass = "bg-red-700 text-white";
  } else if (ageH > 30) {
    statusBadge = "Aging";
    statusClass = "bg-amber-500 text-black";
  } else {
    statusBadge = "OK";
    statusClass = "bg-emerald-600 text-white";
  }

  const stages = run.stages || {};
  const stagePills = Object.entries(stages).map(([name, data]) => {
    const count = typeof data === "object" ? (data.count ?? data.uploaded ?? data.skipped ?? "") : data;
    return `<span class="text-xs font-mono text-bone-300 bg-ink-800 rounded px-2 py-0.5">
      <span class="text-bone-400">${esc(name)}</span>
      ${count !== "" ? `<span class="text-white ml-1">${count}</span>` : ""}
    </span>`;
  }).join("");

  const dryRunBadge = run.dry_run
    ? `<span class="text-[10px] font-mono px-2 py-0.5 rounded-full bg-amber-500 text-black ml-2">dry run</span>`
    : "";

  banner.innerHTML = `
    <div class="flex flex-wrap items-center gap-3">
      <span class="text-xs font-mono px-2 py-0.5 rounded-full ${statusClass}">${statusBadge}</span>
      <span class="text-sm text-bone-200 font-mono">${relTime}</span>
      ${dryRunBadge}
    </div>
    ${stagePills ? `<div class="flex flex-wrap gap-2 mt-3">${stagePills}</div>` : ""}
    ${run.error ? `<p class="text-xs text-red-400 font-mono mt-2">${esc(String(run.error))}</p>` : ""}
  `;
}

/**
 * Fetch /api/dashboard-extras and render hot leads, activity, and pipeline banner.
 * @param {string} range
 */
async function loadDashboardExtras(range) {
  const secret = getWorkerSecret();

  // Show secret banner if not set
  const secretBanner = document.getElementById("secretBanner");
  if (secretBanner) {
    if (!secret) {
      secretBanner.classList.remove("hidden");
    } else {
      secretBanner.classList.add("hidden");
    }
  }

  if (!secret) {
    const hotEl = document.getElementById("hot-leads-container");
    const actEl = document.getElementById("recent-activity-container");
    const plEl = document.getElementById("pipeline-banner");
    if (hotEl) hotEl.innerHTML = '<p class="text-sm text-bone-400 font-mono italic">Set admin secret to view hot leads.</p>';
    if (actEl) actEl.innerHTML = '<p class="text-sm text-bone-400 font-mono italic">Set admin secret to view activity.</p>';
    if (plEl) plEl.innerHTML = '<p class="text-sm text-bone-400 font-mono italic">Set admin secret to view pipeline status.</p>';
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/dashboard-extras?range=${encodeURIComponent(range)}`, {
      headers: { "X-Worker-Secret": secret },
    });
    if (!res.ok) {
      const msg = `Could not load extras (HTTP ${res.status})`;
      ["hot-leads-container", "recent-activity-container", "pipeline-banner"].forEach((id) => {
        const el = document.getElementById(id);
        if (el) el.innerHTML = `<p class="text-sm text-bone-400 font-mono">${esc(msg)}</p>`;
      });
      return;
    }
    const data = await res.json();
    renderHotLeads(data.hot_leads_this_week || []);
    renderRecentActivity(data.recent_activity || []);
    renderPipelineBanner(data.latest_pipeline_run || null);
  } catch (err) {
    console.error("loadDashboardExtras error:", err);
    const msg = `Network error: ${err.message || "unreachable"}`;
    ["hot-leads-container", "recent-activity-container", "pipeline-banner"].forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.innerHTML = `<p class="text-sm text-bone-400 font-mono">${esc(msg)}</p>`;
    });
  }
}

/**
 * Trigger a dry-run of the pipeline (no credits used).
 */
async function triggerDryRun() {
  const btn = document.getElementById("dryRunBtn");
  const spinner = document.getElementById("dryRunSpinner");
  const resultEl = document.getElementById("dryRunResult");
  if (!btn || !resultEl) return;

  const secret = getWorkerSecret();
  if (!secret) {
    resultEl.textContent = "Error: set the admin secret first.";
    resultEl.classList.remove("hidden");
    return;
  }

  btn.disabled = true;
  btn.classList.add("opacity-60", "cursor-not-allowed");
  if (spinner) { spinner.classList.remove("hidden"); spinner.classList.add("spin"); }
  resultEl.classList.add("hidden");
  resultEl.textContent = "";

  try {
    const res = await fetch(`${API_BASE}/run-pipeline?dry_run=true`, {
      method: "POST",
      headers: { "X-Worker-Secret": secret },
    });
    const text = await res.text();
    let pretty;
    try { pretty = JSON.stringify(JSON.parse(text), null, 2); } catch (_) { pretty = text; }
    resultEl.textContent = pretty;
    resultEl.classList.remove("hidden");
  } catch (err) {
    resultEl.textContent = `Error: ${err.message}`;
    resultEl.classList.remove("hidden");
  } finally {
    btn.disabled = false;
    btn.classList.remove("opacity-60", "cursor-not-allowed");
    if (spinner) { spinner.classList.add("hidden"); spinner.classList.remove("spin"); }
  }
}

/**
 * Simple HTML escape to prevent XSS in dynamically inserted content.
 * @param {string} str
 * @returns {string}
 */
function esc(str) {
  if (str == null) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
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
      loadDashboardExtras(currentRange);
    });
  });

  // Refresh button
  els.refreshBtn.addEventListener("click", () => {
    fetchData(currentRange);
    loadDashboardExtras(currentRange);
  });

  // Admin secret: pre-fill from localStorage
  const secretInput = document.getElementById("workerSecretInput");
  const setSecretBtn = document.getElementById("setSecretBtn");
  if (secretInput) {
    const stored = localStorage.getItem("worker_secret") || "";
    if (stored) secretInput.value = stored;
  }
  if (setSecretBtn && secretInput) {
    setSecretBtn.addEventListener("click", () => {
      const val = secretInput.value.trim();
      if (val) {
        localStorage.setItem("worker_secret", val);
      } else {
        localStorage.removeItem("worker_secret");
      }
      // Reload extras with the new secret
      loadDashboardExtras(currentRange);
    });
  }

  // Dry-run button
  const dryRunBtn = document.getElementById("dryRunBtn");
  if (dryRunBtn) {
    dryRunBtn.addEventListener("click", triggerDryRun);
  }
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------

document.addEventListener("DOMContentLoaded", () => {
  cacheElements();
  setupEventListeners();
  fetchData(currentRange);
  loadDashboardExtras(currentRange);
});
