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
    const text = await resp.text();
    console.error(`dispatch failed: ${resp.status} ${text}`);
    throw new Error(`dispatch failed: ${resp.status}`);
  }
  return resp.status;
}

export default {
  async scheduled(event, env, ctx) {
    // DST split: only fire the cron that matches the current TZ offset.
    // Paris is CEST (UTC+2) Apr-Oct → primary cron at 07:15 UTC.
    // Paris is CET  (UTC+1) Nov-Mar → primary cron at 08:15 UTC.
    // wrangler.toml declares BOTH crons; this guard makes the wrong one
    // no-op on any given day. Manual fetch triggers bypass this guard.
    const now = new Date(event.scheduledTime);
    const month = now.getUTCMonth() + 1;  // 1-12
    const hour = now.getUTCHours();
    const inCest = month >= 4 && month <= 10;
    const expectedHour = inCest ? 7 : 8;
    if (hour !== expectedHour) {
      console.log(`skip: month=${month} hour=${hour} expected=${expectedHour} (DST mismatch)`);
      return;
    }
    const status = await dispatchWorkflow(env);
    console.log(`dispatched ${env.WORKFLOW_FILE} on ${env.REF} — status ${status}`);
  },

  // Manual-trigger endpoint. Auth: WORKER_SECRET MUST be set as a Worker
  // secret AND the caller MUST present it. If the secret isn't set, all
  // fetches are rejected (fail-closed, not fail-open). Unlike scheduled
  // above, this path deliberately bypasses the DST guard — the caller
  // already knows what time it is and explicitly wants a dispatch.
  //   wrangler secret put WORKER_SECRET
  //   curl https://job-search-cron.<subdomain>.workers.dev/?secret=<value>
  async fetch(req, env, ctx) {
    if (!env.WORKER_SECRET) {
      return new Response("forbidden (WORKER_SECRET not configured on this Worker)", { status: 403 });
    }
    const url = new URL(req.url);
    if (url.searchParams.get("secret") !== env.WORKER_SECRET) {
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
