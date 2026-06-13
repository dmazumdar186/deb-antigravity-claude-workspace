// Pages Function: server-side proxy.
// Runs on Cloudflare's edge, NOT in the browser.
// Reads WORKER_URL + WORKER_SECRET from Pages env vars (set via dashboard
// or `wrangler pages secret put`). The browser NEVER sees the secret.

export async function onRequestPost({ request, env }) {
  if (!env.WORKER_URL || !env.WORKER_SECRET) {
    return new Response(
      JSON.stringify({
        error: "pages_function_misconfigured",
        detail: "WORKER_URL or WORKER_SECRET not set in Pages env vars. See README step 7.",
      }),
      { status: 500, headers: { "Content-Type": "application/json" } }
    );
  }

  const body = await request.text();
  const target = `${env.WORKER_URL.replace(/\/$/, "")}/api/optimize`;

  // 25s timeout — Pages Functions have a 30s wall-clock; bail before that so we can
  // return a structured 504 instead of getting hard-killed.
  const ctrl = new AbortController();
  const timeoutId = setTimeout(() => ctrl.abort(), 25_000);

  let resp;
  try {
    resp = await fetch(target, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Worker-Secret": env.WORKER_SECRET,
      },
      body,
      signal: ctrl.signal,
    });
  } catch (err) {
    const aborted = err instanceof Error && err.name === "AbortError";
    return new Response(
      JSON.stringify({
        error: aborted ? "worker_timeout" : "worker_fetch_failed",
        detail: err instanceof Error ? err.message : String(err),
      }),
      { status: aborted ? 504 : 502, headers: { "Content-Type": "application/json" } }
    );
  } finally {
    clearTimeout(timeoutId);
  }

  const responseBody = await resp.text();
  return new Response(responseBody, {
    status: resp.status,
    headers: { "Content-Type": "application/json" },
  });
}
