/* GTM People — "Brief it" ask Worker. POST {brief, parsed?} → {summary, stage, family, location, recommendedTier, faqIds}.
   Not deployed; set <html data-ask-url="https://gtm-people-ask.<account>.workers.dev"> to enable. */
const KB = {
  salary: [
    ['SDR / BDR', '£28k – £45k', 'OTE £45k – £75k', 'Seed → Series B · 60/40 base:variable'],
    ['Account Executive', '£55k – £90k', 'OTE £110k – £180k', 'Series A → Series C · 50/50 split'],
    ['Customer Success Manager', '£45k – £70k', 'OTE £60k – £95k', 'Seed → Series B · expansion-based variable'],
    ['RevOps Manager', '£55k – £80k', 'OTE £65k – £95k', 'Series A → Series C · system-bonus weighted'],
    ['Head of Sales', '£80k – £120k', 'OTE £150k – £220k', 'Series A → Series B · team quota-carry'],
    ['VP Sales / CRO', '£120k – £180k', 'OTE £220k – £320k+', 'Series B → Series C · equity + LTIP']
  ],
  tiers: [
    ['Launchpad', '£500/mo · £5,000 / year', 'No included placements · 20% per hire · 3-month replacement guarantee', 'Pre-Seed / Seed / Bootstrapped'],
    ['Scaleup', '£1,000/mo · £10,000 / year', '1 included placement / year (up to £75k base) · Then 17.5% · 6-month guarantee', 'Series A'],
    ['Unicorn', '£2,500/mo · £30,000 / year', '2 included placements / year (up to £100k base) — or 3 up to £75k · Then 15% · 12-month rolling guarantee', 'Series B / Series C'],
    ['Partner', '£8,500/mo · Monthly · min 3 months', 'A GTM recruiter embedded in your team, full-time · Unlimited hiring within capacity', '3+ hires a year']
  ],
  fees: 'We charge on base salary + guaranteed earnings only — never OTE or commission. Every placement beyond your included ones carries a £2,500 engagement retainer, credited in full. Every hire beyond your included placements is 15%. On a £100,000 role that\'s £15,000 rather than £30,000.',
  process: 'Deep Brief (60 min) → Market Map → Screen & Qualify → Curated Shortlist of 3–5 within 5 working days → Interview Support → Offer & Close (7 in 10 counter-offer acceptors leave within 9 months) → 30/60/90 day check-ins → 3-month replacement guarantee.',
  faqIds: ['what-is-gtm-recruitment', 'first-salesperson', 'sdr-vs-bdr', 'what-we-charge', 'how-long-ae', 'series-a-ae-pay', 'outside-uk', 'guarantee'],
  stats: '2,000+ GTM & Sales placements · 20+ years · 100+ SaaS & Tech clients · 5 days to first shortlist · 3-month guarantee · London-based, placing globally (UK · US · EU).'
};
const SYSTEM = 'You are the GTM People brief assistant. Facts: ' + JSON.stringify(KB) + ' Answer only from these facts; never invent prices, names or numbers. Return JSON {summary, stage, family, location, recommendedTier, faqIds} where summary is one sentence (≤ 35 words) for a founder or candidate, stage ∈ {Pre-Seed, Seed, Series A, Series B, Series C, Series D+, Bootstrapped, PE Backed, null}, family ∈ {AE, SDR, CS, RevOps, Leadership, Marketing, GTM Eng, Pre-Sales, null}, recommendedTier ∈ {Launchpad, Scaleup, Unicorn, Partner}, faqIds is up to 2 ids from the list. Output JSON only.';

const bucket = new Map(); // ip → {tokens, ts}; per-isolate token bucket (no KV)
function allow(ip) {
  const now = Date.now(), b = bucket.get(ip) || { tokens: 10, ts: now };
  b.tokens = Math.min(10, b.tokens + (now - b.ts) / 6000); b.ts = now;
  if (b.tokens < 1) { bucket.set(ip, b); return false; }
  b.tokens -= 1; bucket.set(ip, b); return true;
}
function cors(origin) {
  const ok = /^https:\/\/([a-z0-9-]+\.)*pages\.dev$/i.test(origin || '') || /^https?:\/\/localhost(:\d+)?$/.test(origin || '');
  return { 'access-control-allow-origin': ok ? origin : 'https://gtm-people-redesign.pages.dev', 'access-control-allow-methods': 'POST, OPTIONS', 'access-control-allow-headers': 'content-type', 'vary': 'origin' };
}
const json = (obj, status, headers) => new Response(JSON.stringify(obj), { status, headers: { 'content-type': 'application/json', ...headers } });

export default {
  async fetch(request, env) {
    const h = cors(request.headers.get('origin'));
    if (request.method === 'OPTIONS') return new Response(null, { status: 204, headers: h });
    if (request.method !== 'POST') return json({ error: 'POST {brief}' }, 405, h);
    const ip = request.headers.get('cf-connecting-ip') || 'anon';
    if (!allow(ip)) return json({ error: 'rate limited' }, 429, h);
    let body; try { body = await request.json(); } catch { return json({ error: 'bad json' }, 400, h); }
    const brief = String(body && body.brief || '').slice(0, 400);
    if (!brief) return json({ error: 'empty brief' }, 400, h);
    if (!env.ANTHROPIC_API_KEY) return json({ error: 'no key' }, 500, h);
    const ctl = new AbortController(); const t = setTimeout(() => ctl.abort(), 10000);
    try {
      const r = await fetch('https://api.anthropic.com/v1/messages', {
        method: 'POST', signal: ctl.signal,
        headers: { 'content-type': 'application/json', 'x-api-key': env.ANTHROPIC_API_KEY, 'anthropic-version': '2023-06-01' },
        body: JSON.stringify({ model: 'claude-fable-5-1', max_tokens: 600, system: SYSTEM, messages: [{ role: 'user', content: 'Brief: ' + brief + (body.parsed ? '\nClient-side parse: ' + JSON.stringify(body.parsed) : '') }] })
      });
      if (!r.ok) return json({ error: 'upstream ' + r.status }, 502, h);
      const data = await r.json();
      const text = (data.content || []).map((c) => c.text || '').join('');
      const m = text.match(/\{[\s\S]*\}/);
      if (!m) return json({ error: 'no json in reply' }, 502, h);
      const out = JSON.parse(m[0]);
      return json({ summary: out.summary, stage: out.stage, family: out.family, location: out.location, recommendedTier: out.recommendedTier, faqIds: out.faqIds, tiles: [] }, 200, h);
    } catch (e) {
      return json({ error: e.name === 'AbortError' ? 'timeout' : 'failed' }, 504, h);
    } finally { clearTimeout(t); }
  }
};
