'use strict';
/* Cloudflare Worker stub for "Ask GreenJobs" (phase 2, not deployed by the demo).
   POST /ask { edition, query, limit } → { matches:[{id, why, terms}] }.
   The OpenRouter key lives in a Worker secret; the page never sees it. */

const MODELS = { 'z-ai/glm-5.3': true, 'moonshotai/kimi-k3': true };
const memRate = new Map();

async function rateOk(env, ip) {
  const limit = Number(env.RATE_PER_MINUTE || 12);
  const key = `rate:${ip}:${Math.floor(Date.now() / 60000)}`;
  if (env.RATE) {
    const n = Number((await env.RATE.get(key)) || 0) + 1;
    await env.RATE.put(key, String(n), { expirationTtl: 120 });
    return n <= limit;
  }
  const n = (memRate.get(key) || 0) + 1;
  memRate.set(key, n);
  if (memRate.size > 5000) memRate.clear();
  return n <= limit;
}

async function loadJobs(env, edition, origin) {
  // The static site publishes data/jobs.json per edition; the Worker reads it
  // from the same origin it serves, so there is one source of truth.
  const res = await fetch(`${origin}/${edition}/data/jobs.json`, { cf: { cacheTtl: 600, cacheEverything: true } });
  if (!res.ok) throw new Error(`dataset ${res.status}`);
  const data = await res.json();
  return data.jobs.map((j) => ({ id: j.id, title: j.title, employer: j.employer, location: j.location, sectors: j.sectors, salary: j.sal_text || '', summary: (j.summary || '').slice(0, 240) }));
}

function json(body, status = 200, origin = '*') {
  return new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json; charset=utf-8', 'access-control-allow-origin': origin, 'access-control-allow-headers': 'content-type', 'access-control-allow-methods': 'POST, OPTIONS', 'cache-control': 'no-store' } });
}

export default {
  async fetch(request, env) {
    const origin = env.ALLOWED_ORIGIN || '*';
    if (request.method === 'OPTIONS') return json({}, 204, origin);
    const url = new URL(request.url);
    if (request.method !== 'POST' || url.pathname !== '/ask') return json({ error: 'POST /ask' }, 404, origin);
    if (origin !== '*' && request.headers.get('origin') !== origin) return json({ error: 'origin not allowed' }, 403, origin);
    const ip = request.headers.get('cf-connecting-ip') || 'unknown';
    if (!(await rateOk(env, ip))) return json({ error: 'slow down' }, 429, origin);
    let body;
    try { body = await request.json(); } catch (e) { return json({ error: 'bad json' }, 400, origin); }
    const edition = body.edition === 'uk' ? 'uk' : 'ie';
    const query = String(body.query || '').slice(0, Number(env.MAX_QUERY_CHARS || 4000)).trim();
    const limit = Math.min(10, Math.max(1, Number(body.limit) || 5));
    if (query.length < 3) return json({ error: 'query too short' }, 400, origin);
    const model = MODELS[env.MODEL] ? env.MODEL : 'z-ai/glm-5.3';
    if (!env.OPENROUTER_API_KEY) return json({ error: 'assistant not configured' }, 503, origin);
    let jobs;
    try { jobs = await loadJobs(env, edition, origin === '*' ? url.origin : origin); } catch (e) { return json({ error: 'dataset unavailable' }, 502, origin); }
    const system = 'You match a candidate\'s text to live job listings. You receive the listings as a JSON array (id, title, employer, location, sectors, salary, summary). Return ONLY a JSON object {"matches":[{"id","why","terms"}]} with at most ' + limit + ' entries, best first. Match on skills, sector vocabulary, seniority and location. Never invent an id. If nothing fits, return an empty array. Write "why" in one plain sentence a candidate would find useful.';
    const payload = {
      model, temperature: 0, max_tokens: 400, response_format: { type: 'json_object' },
      messages: [
        { role: 'system', content: system },
        { role: 'user', content: [{ type: 'text', text: 'LISTINGS:\n' + JSON.stringify(jobs), cache_control: { type: 'ephemeral' } }, { type: 'text', text: '\n\nCANDIDATE:\n' + query }] }
      ]
    };
    let out;
    try {
      const r = await fetch('https://openrouter.ai/api/v1/chat/completions', {
        method: 'POST',
        headers: { authorization: `Bearer ${env.OPENROUTER_API_KEY}`, 'content-type': 'application/json', 'http-referer': origin, 'x-title': 'Ask GreenJobs' },
        body: JSON.stringify(payload)
      });
      if (!r.ok) return json({ error: 'model error ' + r.status }, 502, origin);
      const data = await r.json();
      out = JSON.parse(data.choices[0].message.content);
    } catch (e) {
      return json({ error: 'model unavailable' }, 502, origin);
    }
    const known = new Set(jobs.map((j) => j.id));
    const matches = (Array.isArray(out.matches) ? out.matches : [])
      .filter((m) => m && known.has(String(m.id)))
      .slice(0, limit)
      .map((m) => ({ id: String(m.id), why: String(m.why || '').slice(0, 240), terms: Array.isArray(m.terms) ? m.terms.slice(0, 6).map(String) : [] }));
    return json({ matches, model }, 200, origin);
  }
};
