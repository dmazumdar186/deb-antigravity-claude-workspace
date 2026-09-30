// proposal-tracker: hosts proposal HTML and notifies Telegram on every open.
//
// Routes
//   GET  /health              -> {ok, kv_bound, telegram_bound}
//   GET  /p/<slug>            -> proposal HTML (KV key html:<slug>); fires open alert
//   GET  /o/<slug>.gif        -> 1x1 gif; fires open alert (for pixel embeds)
//   GET  /opens/<slug>        -> JSON log of opens; needs X-Publish-Secret
//   PUT  /publish/<slug>      -> body = html; needs X-Publish-Secret
//   DELETE /publish/<slug>    -> removes proposal; needs X-Publish-Secret
//
// Notifications are suppressed for the operator's own opens when ?me=1 is
// appended (use this when previewing) and de-duplicated within 60 s for the
// same slug + IP hash so a page refresh does not spam the chat.

const GIF = Uint8Array.from(atob("R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"), c => c.charCodeAt(0));

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname.replace(/\/+$/, "");
    const kv = env.PROPOSALS;

    if (path === "/health") {
      return json({ ok: true, ts: new Date().toISOString(), kv_bound: Boolean(kv),
        telegram_bound: Boolean(env.TELEGRAM_BOT_TOKEN && env.TELEGRAM_CHAT_ID) });
    }

    let m;
    if ((m = path.match(/^\/publish\/([a-z0-9_-]+)$/))) {
      if (!authed(request, env)) return json({ error: "unauthorised" }, 401);
      if (!kv) return json({ error: "kv not bound" }, 500);
      const slug = m[1];
      if (request.method === "PUT") {
        const html = await request.text();
        if (!html || html.length < 100) return json({ error: "empty body" }, 400);
        await kv.put(`html:${slug}`, html);
        await kv.put(`meta:${slug}`, JSON.stringify({ published_at: new Date().toISOString(), bytes: html.length }));
        return json({ ok: true, slug, url: `${url.origin}/p/${slug}`, pixel: `${url.origin}/o/${slug}.gif` });
      }
      if (request.method === "DELETE") {
        await kv.delete(`html:${slug}`);
        return json({ ok: true, deleted: slug });
      }
      return json({ error: "method" }, 405);
    }

    if ((m = path.match(/^\/opens\/([a-z0-9_-]+)$/))) {
      if (!authed(request, env)) return json({ error: "unauthorised" }, 401);
      const log = (await kv?.get(`opens:${m[1]}`, "json")) || [];
      return json({ slug: m[1], count: log.length, opens: log });
    }

    if (path === "/api/track" && request.method === "POST") {
      // Same contract as Siva's Vercel api/track.js: {slug, client, event, extra}
      let body = {};
      try { body = await request.json(); } catch (e) { return json({ error: "bad json" }, 400); }
      if (!body.slug || !body.event) return json({ error: "missing_fields" }, 400);
      ctx.waitUntil(recordOpen(request, env, String(body.slug).slice(0, 64), String(body.event).slice(0, 32), url, body.extra));
      return json({ ok: true }, 200);
    }

    if ((m = path.match(/^\/o\/([a-z0-9_-]+)\.gif$/))) {
      ctx.waitUntil(recordOpen(request, env, m[1], "pixel", url));
      return new Response(GIF, { headers: { "content-type": "image/gif", "cache-control": "no-store, no-cache, must-revalidate, max-age=0", "pragma": "no-cache" } });
    }

    if ((m = path.match(/^\/p\/([a-z0-9_-]+)$/))) {
      if (!kv) return new Response("KV not bound", { status: 500 });
      const html = await kv.get(`html:${m[1]}`);
      if (!html) return new Response("Not found", { status: 404 });
      ctx.waitUntil(recordOpen(request, env, m[1], "page", url));
      return new Response(html, { headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-store", "x-robots-tag": "noindex, nofollow" } });
    }

    return new Response("Not found", { status: 404 });
  },
};

function authed(request, env) {
  const s = env.PUBLISH_SECRET;
  return Boolean(s) && request.headers.get("x-publish-secret") === s;
}

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), { status, headers: { "content-type": "application/json" } });
}

async function sha(text) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, "0")).join("").slice(0, 12);
}

async function recordOpen(request, env, slug, kind, url, extra) {
  const kv = env.PROPOSALS;
  const cf = request.cf || {};
  const ua = request.headers.get("user-agent") || "";
  const ip = request.headers.get("cf-connecting-ip") || "";
  const ipHash = await sha(ip + "|" + ua);
  const isMe = url.searchParams.get("me") === "1";
  const now = new Date();
  const entry = {
    ts: now.toISOString(), kind, country: cf.country || "?", city: cf.city || "?",
    region: cf.region || "", ua: ua.slice(0, 160), ip_hash: ipHash,
    referer: request.headers.get("referer") || "", me: isMe, extra: extra ? String(extra).slice(0, 200) : undefined,
  };
  // Bots and link previewers (Slack, LinkedIn, WhatsApp, Telegram) fetch links too; label them.
  if (/bot|crawler|spider|preview|facebookexternalhit|linkedinbot|slackbot|telegrambot|whatsapp|curl|python-requests/i.test(ua)) entry.bot = true;

  let log = [];
  if (kv) {
    log = (await kv.get(`opens:${slug}`, "json")) || [];
    const last = [...log].reverse().find(e => e.ip_hash === ipHash);
    const dup = last && (now - new Date(last.ts)) < 60_000;
    log.push(entry);
    if (log.length > 500) log = log.slice(-500);
    await kv.put(`opens:${slug}`, JSON.stringify(log));
    if (dup) return; // refresh within 60 s: log it, don't ping
  }
  if (isMe || entry.bot) return;

  const humanOpens = log.filter(e => !e.me && !e.bot).length || 1;
  const device = /mobile|iphone|android/i.test(ua) ? "mobile" : "desktop";
  const icons = { opened: "📬", viewed: "👁", signed: "✍️", pay_clicked: "💳", page: "📄", pixel: "📄" };
  const label = kind === "opened" ? "Proposal first opened" : kind === "viewed" ? "Proposal viewed again"
    : kind === "signed" ? "Proposal SIGNED" : kind === "pay_clicked" ? "Proposal: Pay clicked" : "Proposal opened";
  const text = [
    `${icons[kind] || "•"} *${label}*: \`${slug}\``,
    entry.extra ? `\`${entry.extra}\`` : null,
    `Open #${humanOpens} · ${kind}`,
    `📍 ${entry.city}, ${entry.country} · ${device}`,
    `🕒 ${now.toUTCString()}`,
    entry.referer ? `↩ ${entry.referer}` : null,
  ].filter(Boolean).join("\n");
  await telegram(env, text);
}

async function telegram(env, text) {
  const token = env.TELEGRAM_BOT_TOKEN, chatId = env.TELEGRAM_CHAT_ID;
  if (!token || !chatId) return;
  try {
    const res = await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ chat_id: chatId, text, parse_mode: "Markdown" }),
    });
    if (!res.ok) console.warn("telegram non-2xx", res.status);
  } catch (e) { console.warn("telegram failed", e.message); }
}
