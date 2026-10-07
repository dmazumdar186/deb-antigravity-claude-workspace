import { callJev, hashText, modeKey } from "./jev_api.js";

const cache = new Map(); // mode:hash -> probability
const stats = { checked: 0, folded: 0, cost: 0 };

async function getKey() {
  const { openrouterKey } = await chrome.storage.local.get("openrouterKey");
  return openrouterKey || "";
}

async function classify(items, mode) {
  const k = modeKey(mode);
  const out = {};
  const todo = [];
  for (const it of items) {
    const ck = k + ":" + hashText(it.text || "");
    if (cache.has(ck)) out[it.id] = cache.get(ck);
    else todo.push({ ...it, ck });
  }
  if (todo.length) {
    const key = await getKey();
    if (!key) return out;
    const r = await callJev(fetch, key, todo, k);
    stats.cost += r.cost;
    for (const it of todo) {
      if (it.id in r.probs) {
        cache.set(it.ck, r.probs[it.id]);
        out[it.id] = r.probs[it.id];
      }
    }
  }
  stats.checked += items.length;
  return out;
}

chrome.runtime.onMessage.addListener((msg, _sender, reply) => {
  if (!msg || typeof msg !== "object") return false;
  if (msg.type === "classify") {
    classify(msg.items || [], msg.mode)
      .then((probs) => reply(probs))
      .catch(() => reply({})); // fail-open
    return true;
  }
  if (msg.type === "folded") { stats.folded += Number(msg.n) || 0; return false; }
  if (msg.type === "stats") { reply({ ...stats }); return false; }
  return false;
});
