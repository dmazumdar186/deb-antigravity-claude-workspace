// Pages Function proxy for POST /api/refresh-profile.
// Same auth pattern as optimize.js — secret stays server-side.

export async function onRequestPost({ env }) {
  if (!env.WORKER_URL || !env.WORKER_SECRET) {
    return new Response(
      JSON.stringify({ error: "pages_function_misconfigured" }),
      { status: 500, headers: { "Content-Type": "application/json" } }
    );
  }

  const target = `${env.WORKER_URL.replace(/\/$/, "")}/api/refresh-profile`;
  const ctrl = new AbortController();
  const timeoutId = setTimeout(() => ctrl.abort(), 15_000);

  let resp;
  try {
    resp = await fetch(target, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Worker-Secret": env.WORKER_SECRET,
      },
      body: "{}",
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

  const body = await resp.text();
  return new Response(body, {
    status: resp.status,
    headers: { "Content-Type": "application/json" },
  });
}
