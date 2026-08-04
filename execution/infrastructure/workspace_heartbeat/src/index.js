// workspace_heartbeat — daily health probe of every deployed project in the
// workspace. Emits DEGRADED/OK per project, then posts a summary to Telegram
// (if TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID are set), and always writes the
// most recent report to KV under `heartbeat:latest` + `heartbeat:<YYYY-MM-DD>`.
//
// Two systemic patterns this closes (per HARDENING_BACKLOG_WORKSPACE_2026-08-04):
//   Pattern A — untracked deployed artifacts (probed here by asserting the
//               live URL returns real content, NOT a stale fallback).
//   Pattern B — "shipped" claims surviving month-long silence (probed here
//               via the freshness field in each project's /health JSON).
//
// The Worker deliberately does NOT run git operations or SAST — those live
// in freshness_monitor.py and weekly_hardening_report.py (run locally or via
// GH Actions). This Worker is the live-URL half of the check.
//
// Deploy (operator, after committing):
//   cd execution/infrastructure/workspace_heartbeat
//   npx wrangler kv namespace create HEARTBEAT_KV
//   # paste the returned id into wrangler.toml
//   npx wrangler secret put TELEGRAM_BOT_TOKEN     # optional
//   npx wrangler secret put TELEGRAM_CHAT_ID       # optional
//   npx wrangler secret put PROBE_SECRET           # required — gates POST /run
//   npx wrangler deploy
//
// Revert:
//   npx wrangler delete workspace-heartbeat
//   (KV: keep — the report history is the audit trail)

const JSON_HEADERS = { "content-type": "application/json; charset=utf-8" };

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj, null, 2), { status, headers: JSON_HEADERS });
}

function isoNow() {
  return new Date().toISOString();
}

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

// Timing-safe compare for X-Probe-Secret.
function ctEqual(a, b) {
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

// Load the manifest baked into the Worker at build time. See wrangler.toml
// `[vars] MANIFEST = "..."` which is set by a small pre-deploy script that
// inlines manifest.json. Fallback: MANIFEST_JSON env var (settable via secret).
function loadManifest(env) {
  const raw = env.MANIFEST_JSON || env.MANIFEST;
  if (!raw) {
    return { projects: [] };
  }
  try {
    return JSON.parse(raw);
  } catch (err) {
    console.error("manifest parse failed:", err.message);
    return { projects: [] };
  }
}

// Compute freshness DEGRADED given a probe payload + project spec.
// Rules:
//   - if freshness_field is null → no freshness check, only HTTP status matters
//   - if the field is missing or not parseable → DEGRADED (probe returned but
//     no signal that the pipeline actually ran)
//   - if age (h) > freshness_threshold_hours → DEGRADED
function computeFreshness(project, payload) {
  const field = project.freshness_field;
  if (!field) return { checked: false, degraded: false, age_hours: null };

  const raw = payload && payload[field];
  if (!raw) {
    return {
      checked: true,
      degraded: true,
      age_hours: null,
      reason: `freshness field '${field}' missing from probe response`,
    };
  }

  const ts = Date.parse(raw);
  if (Number.isNaN(ts)) {
    return {
      checked: true,
      degraded: true,
      age_hours: null,
      reason: `freshness field '${field}' not parseable as ISO date: ${raw}`,
    };
  }

  const ageHours = (Date.now() - ts) / 3_600_000;
  const threshold = project.freshness_threshold_hours;
  return {
    checked: true,
    degraded: ageHours > threshold,
    age_hours: Math.round(ageHours * 10) / 10,
    threshold_hours: threshold,
  };
}

// One project probe. Never throws; degrades gracefully so one bad URL cannot
// take down the whole heartbeat.
async function probeProject(project) {
  const started = Date.now();
  const base = {
    slug: project.slug,
    type: project.type,
    probe_url: project.probe_url,
    checked_at: isoNow(),
  };

  // interactive_only projects have no probe URL — only freshness (git-log),
  // which the Worker can't do. Mark as SKIPPED_NO_PROBE.
  if (!project.probe_url) {
    return {
      ...base,
      status: "SKIPPED_NO_PROBE",
      degraded: false,
      note: "interactive_only project; freshness deferred to freshness_monitor.py",
      elapsed_ms: Date.now() - started,
    };
  }

  const expected = project.probe_expected_status || 200;
  let resp;
  try {
    resp = await fetch(project.probe_url, {
      method: "GET",
      headers: { "user-agent": "workspace-heartbeat/1.0" },
      signal: AbortSignal.timeout(10_000),
      redirect: "manual",
    });
  } catch (err) {
    return {
      ...base,
      status: "PROBE_ERROR",
      degraded: true,
      http_status: null,
      error: String(err && err.message || err),
      elapsed_ms: Date.now() - started,
    };
  }

  const httpOk = resp.status === expected;
  let payload = null;
  const ct = (resp.headers.get("content-type") || "").toLowerCase();
  if (httpOk && ct.includes("application/json")) {
    try {
      payload = await resp.json();
    } catch (err) {
      // Body wasn't JSON despite the header — treat as partial success.
      payload = null;
    }
  }

  const freshness = computeFreshness(project, payload);
  const degraded = !httpOk || freshness.degraded;

  return {
    ...base,
    status: degraded ? "DEGRADED" : "OK",
    degraded,
    http_status: resp.status,
    http_expected: expected,
    http_ok: httpOk,
    freshness,
    elapsed_ms: Date.now() - started,
  };
}

async function runHeartbeat(env) {
  const manifest = loadManifest(env);
  const projects = manifest.projects || [];
  const startedAt = isoNow();

  // Fan out probes in parallel — always-parallelize discipline.
  const results = await Promise.all(projects.map(probeProject));

  const summary = {
    generated_at: isoNow(),
    started_at: startedAt,
    project_count: results.length,
    ok_count: results.filter((r) => r.status === "OK").length,
    degraded_count: results.filter((r) => r.status === "DEGRADED").length,
    error_count: results.filter((r) => r.status === "PROBE_ERROR").length,
    skipped_count: results.filter((r) => r.status === "SKIPPED_NO_PROBE").length,
    results,
  };

  // Persist to KV: latest + dated snapshot (90d TTL).
  if (env.HEARTBEAT_KV) {
    try {
      await env.HEARTBEAT_KV.put("heartbeat:latest", JSON.stringify(summary));
      await env.HEARTBEAT_KV.put(
        `heartbeat:${todayIso()}`,
        JSON.stringify(summary),
        { expirationTtl: 90 * 24 * 60 * 60 },
      );
    } catch (err) {
      console.error("KV persist failed:", err.message);
    }
  }

  // Notify iff anything is degraded/errored.
  const needsAlert = summary.degraded_count + summary.error_count > 0;
  if (needsAlert) {
    await notify(env, summary);
  }

  return summary;
}

async function notify(env, summary) {
  const bot = env.TELEGRAM_BOT_TOKEN;
  const chat = env.TELEGRAM_CHAT_ID;
  if (!bot || !chat) {
    console.log("Telegram not configured; skipping alert.");
    return;
  }

  const lines = [];
  lines.push("*Workspace heartbeat — DEGRADED*");
  lines.push(
    `${summary.degraded_count} degraded · ${summary.error_count} probe-error · ${summary.ok_count} ok · ${summary.skipped_count} skipped`,
  );
  lines.push("");
  for (const r of summary.results) {
    if (r.status === "OK" || r.status === "SKIPPED_NO_PROBE") continue;
    const bits = [`*${r.slug}*: ${r.status}`];
    if (r.http_status != null) bits.push(`HTTP ${r.http_status}/${r.http_expected}`);
    if (r.freshness && r.freshness.age_hours != null) {
      bits.push(`age ${r.freshness.age_hours}h / ${r.freshness.threshold_hours}h`);
    }
    if (r.error) bits.push(`err: ${r.error.slice(0, 120)}`);
    if (r.freshness && r.freshness.reason) bits.push(r.freshness.reason.slice(0, 120));
    lines.push("- " + bits.join(" · "));
  }
  const text = lines.join("\n");

  try {
    const resp = await fetch(`https://api.telegram.org/bot${bot}/sendMessage`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        chat_id: chat,
        text,
        parse_mode: "Markdown",
        disable_web_page_preview: true,
      }),
      signal: AbortSignal.timeout(10_000),
    });
    if (!resp.ok) {
      console.error("Telegram sendMessage non-ok:", resp.status, await resp.text());
    }
  } catch (err) {
    console.error("Telegram notify failed:", err.message);
  }
}

export default {
  // Scheduled fire — daily at 06:00 UTC per wrangler.toml.
  async scheduled(event, env, ctx) {
    ctx.waitUntil(
      (async () => {
        try {
          const summary = await runHeartbeat(env);
          console.log(
            `heartbeat ok=${summary.ok_count} deg=${summary.degraded_count} err=${summary.error_count}`,
          );
        } catch (err) {
          console.error("heartbeat top-level failure:", err && err.stack || err);
        }
      })(),
    );
  },

  // HTTP surface:
  //   GET  /health                  -> Worker's own self-check + last KV summary meta
  //   GET  /latest                  -> full latest heartbeat report (JSON)
  //   GET  /report/YYYY-MM-DD       -> a specific day's snapshot
  //   POST /run  (X-Probe-Secret)   -> manually trigger a heartbeat run
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    if (url.pathname === "/health") {
      const manifest = loadManifest(env);
      let latestMeta = null;
      if (env.HEARTBEAT_KV) {
        try {
          const raw = await env.HEARTBEAT_KV.get("heartbeat:latest");
          if (raw) {
            const parsed = JSON.parse(raw);
            latestMeta = {
              generated_at: parsed.generated_at,
              ok: parsed.ok_count,
              degraded: parsed.degraded_count,
              error: parsed.error_count,
              skipped: parsed.skipped_count,
            };
          }
        } catch (err) {
          console.error("health read failed:", err.message);
        }
      }
      return json({
        service: "workspace-heartbeat",
        now: isoNow(),
        manifest_project_count: (manifest.projects || []).length,
        secrets: {
          telegram: Boolean(env.TELEGRAM_BOT_TOKEN && env.TELEGRAM_CHAT_ID),
          probe_secret: Boolean(env.PROBE_SECRET),
        },
        kv_bound: Boolean(env.HEARTBEAT_KV),
        latest: latestMeta,
      });
    }

    if (url.pathname === "/latest") {
      if (!env.HEARTBEAT_KV) return json({ error: "kv not bound" }, 500);
      const raw = await env.HEARTBEAT_KV.get("heartbeat:latest");
      if (!raw) return json({ error: "no heartbeat yet" }, 404);
      return new Response(raw, { headers: JSON_HEADERS });
    }

    const dateMatch = url.pathname.match(/^\/report\/(\d{4}-\d{2}-\d{2})$/);
    if (dateMatch) {
      if (!env.HEARTBEAT_KV) return json({ error: "kv not bound" }, 500);
      const raw = await env.HEARTBEAT_KV.get(`heartbeat:${dateMatch[1]}`);
      if (!raw) return json({ error: "not found" }, 404);
      return new Response(raw, { headers: JSON_HEADERS });
    }

    if (url.pathname === "/run" && request.method === "POST") {
      const supplied = request.headers.get("x-probe-secret") || "";
      if (!env.PROBE_SECRET || !ctEqual(supplied, env.PROBE_SECRET)) {
        return json({ error: "unauthorized" }, 401);
      }
      const summary = await runHeartbeat(env);
      return json(summary);
    }

    return json({ error: "not found", paths: ["/health", "/latest", "/report/YYYY-MM-DD", "POST /run"] }, 404);
  },
};
