// Shared, chrome-free ES module: batching, question building, response parsing, Jev call.
export const JEV_ENDPOINT = "https://openrouter.ai/api/alpha/decisions";
export const JEV_MODEL = "typesafe/jev-1.13";
export const BATCH_SIZE = 20;
export const MAX_TEXT = { slop: 600, junk: 200 };

export const QUESTIONS = {
  slop: {
    prefix: "slop_",
    build: (i) => ({
      type: "noul",
      instructions: `Is item ${i} low-value AI-generated engagement bait?`,
      criteria: {
        true: "generic AI-sounding filler: hype hooks, emoji lists, 'here are 10 tools', 'comment X to get', vague motivational platitudes, no specific first-hand content",
        false: "specific, human, first-hand content: concrete facts, news, data, personal experience, real question or opinion with detail"
      }
    })
  },
  junk: {
    prefix: "junk_",
    build: (i) => ({
      type: "noul",
      instructions: `Is element ${i} an ad, cookie banner, newsletter popup or promo overlay vs page content?`,
      criteria: {
        true: "advertising, sponsored unit, cookie/consent banner, newsletter or signup popup, promo/discount overlay",
        false: "real page content: navigation, header, article text, site search, the main app UI"
      }
    })
  }
};

export function modeKey(mode) {
  return mode === "unclutter" || mode === "junk" ? "junk" : "slop";
}

export function hashText(s) {
  // FNV-1a 32-bit, hex. Good enough for an in-memory cache key.
  let h = 0x811c9dc5;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h.toString(16).padStart(8, "0");
}

export function chunk(items, size = BATCH_SIZE) {
  const out = [];
  for (let i = 0; i < items.length; i += size) out.push(items.slice(i, i + size));
  return out;
}

// items: [{id, text}] (<= BATCH_SIZE). Returns the request body.
export function buildRequest(items, mode, model = JEV_MODEL) {
  const k = modeKey(mode);
  const q = QUESTIONS[k];
  const questions = {};
  const state = { items: [] };
  items.forEach((it, i) => {
    state.items.push({ i, text: String(it.text || "").slice(0, MAX_TEXT[k]) });
    questions[q.prefix + i] = q.build(i);
  });
  return { model, state, questions };
}

// Returns {probs: {id: p}, cost}. Missing answers are omitted (fail-open).
export function parseAnswers(data, items, mode) {
  const q = QUESTIONS[modeKey(mode)];
  const probs = {};
  const answers = (data && data.answers) || {};
  items.forEach((it, i) => {
    const a = answers[q.prefix + i];
    const v = a && typeof a.noul === "number" ? a.noul : null;
    if (v !== null && v >= 0 && v <= 1) probs[it.id] = v;
  });
  const cost = Number((data && data.usage && data.usage.cost) || 0) || 0;
  return { probs, cost };
}

// One Jev call per batch of <= BATCH_SIZE. Throws on HTTP/network errors.
export async function callJev(fetchFn, key, items, mode, model = JEV_MODEL) {
  let probs = {};
  let cost = 0;
  for (const batch of chunk(items)) {
    const resp = await fetchFn(JEV_ENDPOINT, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${key}`,
        "Content-Type": "application/json",
        "X-Title": "jev-feed-filter-extension"
      },
      body: JSON.stringify(buildRequest(batch, mode, model))
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const r = parseAnswers(await resp.json(), batch, mode);
    probs = { ...probs, ...r.probs };
    cost += r.cost;
  }
  return { probs, cost };
}
