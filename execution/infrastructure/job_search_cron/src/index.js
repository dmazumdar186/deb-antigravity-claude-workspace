// job-search-cron — external Cloudflare Cron Trigger that dispatches the
// GitHub Actions `job_search_daily.yml` workflow.
//
// Why this Worker exists: GitHub Actions scheduled workflows are dropped
// silently under platform load. 2026-06-30 dropped the entire scheduled fire
// on this repo; 2026-06-29 delayed it 4h41m. This Worker fires the same
// workflow via workflow_dispatch (which GH does NOT drop). It runs from
// Cloudflare's edge with a documented 99.9% SLA.
//
// The `scheduled` handler runs on the crons defined in wrangler.toml. It
// detects DST via month number so we don't double-fire on transition weeks
// (the wrangler.toml has TWO crons, one for CEST months, one for CET).
//
// GITHUB_PAT is a secret injected via `wrangler secret put GITHUB_PAT`. Must
// have `workflow` scope. Rotate anytime with the same command.

// Fires the actual workflow_dispatch. Extracted so both scheduled and
// manual-trigger paths can share it without inheriting each other's guards.
async function dispatchWorkflow(env) {
  const url = `https://api.github.com/repos/${env.GITHUB_OWNER}/${env.GITHUB_REPO}/actions/workflows/${env.WORKFLOW_FILE}/dispatches`;
  const resp = await fetch(url, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${env.GITHUB_PAT}`,
      "Accept": "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "job-search-cron-worker",
    },
    body: JSON.stringify({ ref: env.REF }),
  });
  if (!resp.ok) {
    // Log status + response body length only. Prior form echoed the full
    // GitHub API error body to console.error, which surfaces in `wrangler
    // tail` / CF dashboard Logs. GH error bodies for workflow-scope
    // failures can echo partial token/scope info; keep them out of the
    // Worker log stream. (2026-07-01 security audit.)
    const text = await resp.text();
    console.error(`dispatch failed: ${resp.status} (body len=${text.length})`);
    throw new Error(`dispatch failed: ${resp.status}`);
  }
  return resp.status;
}

export default {
  async scheduled(event, env, ctx) {
    // DST-accurate cron guard: wrangler.toml declares TWO crons (07:15 and
    // 08:15 UTC) year-round. Only one should actually dispatch on any
    // given day — the one that corresponds to 09:15 Paris local time.
    //
    // Prior form used `month >= 4 && month <= 10` to detect CEST, which
    // is 3-7 days wrong at each transition (Paris switches on the last
    // Sunday of March / October, not on month boundary). Result: on ~10
    // days per year the Worker fires ZERO triggers because both crons
    // are skipped by the wrong hour check.
    //
    // Correct: compute the actual Paris local hour via Intl.DateTimeFormat
    // with timeZone: 'Europe/Paris'. This uses the runtime's built-in
    // tzdata, so DST transitions are handled exactly.
    const now = new Date(event.scheduledTime);
    const parisHour = parseInt(
      new Intl.DateTimeFormat("en-US", {
        hour: "numeric",
        hour12: false,
        timeZone: "Europe/Paris",
      }).format(now),
      10,
    );
    const TARGET_PARIS_HOUR = 9;  // 09:15 Paris local time
    if (parisHour !== TARGET_PARIS_HOUR) {
      console.log(`skip: paris_hour=${parisHour} target=${TARGET_PARIS_HOUR} (wrong half of DST split fires)`);
      return;
    }
    const status = await dispatchWorkflow(env);
    console.log(`dispatched ${env.WORKFLOW_FILE} on ${env.REF} — status ${status}`);
  },

  // Manual-trigger endpoint. Auth: WORKER_SECRET MUST be set as a Worker
  // secret AND the caller MUST present it in the X-Worker-Secret header
  // (NOT the URL query string, which leaks into CF request logs, shell
  // history, and browser history — 2026-07-01 security audit finding).
  // If the secret isn't set, all fetches are rejected (fail-closed).
  //   wrangler secret put WORKER_SECRET
  //   curl -H "X-Worker-Secret: <value>" https://job-search-cron.<subdomain>.workers.dev/
  async fetch(req, env, ctx) {
    if (!env.WORKER_SECRET) {
      return new Response("forbidden (WORKER_SECRET not configured on this Worker)", { status: 403 });
    }
    const presented = req.headers.get("X-Worker-Secret");
    if (presented !== env.WORKER_SECRET) {
      return new Response("forbidden", { status: 403 });
    }
    try {
      const status = await dispatchWorkflow(env);
      return new Response(`dispatched (gh status ${status})`, { status: 200 });
    } catch (err) {
      return new Response(`dispatch error: ${err.message}`, { status: 502 });
    }
  },
};
