// Smoke test for the Jev feed filter extension.
//   node test/smoke.mjs            unit + live Jev call + Playwright
//   node test/smoke.mjs --offline  unit + Playwright (no network spend)
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";
import { buildRequest, parseAnswers, chunk, hashText, callJev, BATCH_SIZE } from "../jev_api.js";

const HERE = dirname(fileURLToPath(import.meta.url));
const EXT = resolve(HERE, "..");
const OFFLINE = process.argv.includes("--offline");
const posts = JSON.parse(readFileSync(join(HERE, "posts.json"), "utf-8"));

// ---- 1. unit tests --------------------------------------------------------
const items = posts.map((p, i) => ({ id: "p" + i, text: p.text }));
const req = buildRequest(items, "slop");
assert.equal(req.model, "typesafe/jev-1.13");
assert.equal(req.state.items.length, 6);
assert.deepEqual(Object.keys(req.questions), ["slop_0", "slop_1", "slop_2", "slop_3", "slop_4", "slop_5"]);
assert.equal(req.questions.slop_3.type, "noul");
assert.ok(req.questions.slop_3.criteria.true && req.questions.slop_3.criteria.false);
const junk = buildRequest([{ id: "u0", text: "x".repeat(500) }], "unclutter");
assert.ok("junk_0" in junk.questions);
assert.equal(junk.state.items[0].text.length, 200);
const many = Array.from({ length: 45 }, (_, i) => ({ id: "m" + i, text: "t" + i }));
assert.deepEqual(chunk(many).map((c) => c.length), [BATCH_SIZE, BATCH_SIZE, 5]);
const parsed = parseAnswers({ answers: { slop_0: { type: "noul", noul: 0.9 }, slop_1: { type: "noul", noul: "bad" } }, usage: { cost: 0.0001 } }, items, "slop");
assert.deepEqual(parsed.probs, { p0: 0.9 });
assert.equal(parsed.cost, 0.0001);
assert.equal(hashText("abc"), hashText("abc"));
assert.notEqual(hashText("abc"), hashText("abd"));
let calls = 0;
const fakeFetch = async (_u, o) => {
  calls++;
  const b = JSON.parse(o.body);
  const answers = Object.fromEntries(Object.keys(b.questions).map((k) => [k, { type: "noul", noul: 0.5 }]));
  return { ok: true, json: async () => ({ answers, usage: { cost: 0.0001 } }) };
};
const r = await callJev(fakeFetch, "k", many, "slop");
assert.equal(calls, 3);
assert.equal(Object.keys(r.probs).length, 45);
await assert.rejects(callJev(async () => ({ ok: false, status: 401 }), "k", items, "slop"));
console.log("[1] unit tests: PASS");

// ---- 2. live Jev call -----------------------------------------------------
if (OFFLINE) {
  console.log("[2] live Jev call: SKIPPED (--offline)");
} else {
  const key = process.env.OPENROUTER_API_KEY || process.env.OPENROUTER_API_TOEKN;
  if (!key) {
    console.log("[2] live Jev call: SKIPPED (no OPENROUTER_API_KEY)");
  } else {
    const t0 = Date.now();
    const live = await callJev(fetch, key, items, "slop");
    console.log(`[2] live Jev call (${Date.now() - t0} ms, cost $${live.cost}):`);
    posts.forEach((p, i) => console.log(`    p${i} ${p.slop ? "SLOP   " : "GENUINE"} ${(live.probs["p" + i] ?? NaN).toFixed(3)}  ${p.text.slice(0, 60)}`));
    const ok = posts.every((p, i) => (live.probs["p" + i] >= 0.7) === p.slop);
    console.log(`    separation at 0.7: ${ok ? "PASS" : "MISMATCH (informational)"}`);
  }
}

// ---- 3. Playwright with the extension loaded ------------------------------
let chromium;
try {
  ({ chromium } = await import("playwright"));
} catch {
  const req2 = createRequire(import.meta.url);
  for (const p of ["/opt/node-tools/node_modules/playwright", join(process.env.npm_config_prefix || "", "lib/node_modules/playwright")]) {
    try { ({ chromium } = req2(p)); break; } catch { /* next */ }
  }
}
if (!chromium) { console.error("[3] playwright not found"); process.exit(1); }

const fixture = readFileSync(join(HERE, "fixture_feed.html"), "utf-8");
const slopTexts = posts.filter((p) => p.slop).map((p) => p.text.slice(0, 40));
const ctx = await chromium.launchPersistentContext("", {
  headless: true,
  channel: "chromium", // full Chromium new-headless; headless_shell cannot load extensions
  args: [`--disable-extensions-except=${EXT}`, `--load-extension=${EXT}`]
});
let mode = "extension";
try {
  let [sw] = ctx.serviceWorkers();
  if (!sw) sw = await ctx.waitForEvent("serviceworker", { timeout: 10000 });
  for (let i = 0; i < 50 && !(await sw.evaluate(() => !!(self.chrome && chrome.storage))); i++) await new Promise((r) => setTimeout(r, 100));
  // Stub OpenRouter inside the service worker (page.route does not see SW fetches).
  await sw.evaluate(async (slop) => {
    await chrome.storage.local.set({ openrouterKey: "test-key", slopEnabled: true, threshold: 0.7 });
    self.fetch = async (_url, opts) => {
      const b = JSON.parse(opts.body);
      const answers = {};
      b.state.items.forEach((it) => {
        const isSlop = slop.some((s) => it.text.includes(s));
        answers["slop_" + it.i] = { type: "noul", noul: isSlop ? 0.93 : 0.08 };
      });
      return new Response(JSON.stringify({ answers, usage: { cost: 0.00003 } }), { status: 200, headers: { "content-type": "application/json" } });
    };
  }, slopTexts);
  const page = await ctx.newPage();
  await page.route("https://x.com/**", (route) => route.fulfill({ status: 200, contentType: "text/html", body: fixture }));
  await page.goto("https://x.com/home");
  await page.waitForFunction(() => document.querySelectorAll('[data-jev-score]').length === 6, null, { timeout: 15000 });
  const res = await page.evaluate(() => [...document.querySelectorAll('article[data-testid="tweet"]')].map((a) => ({
    expect: a.dataset.expect, folded: a.dataset.jevFolded === "1", hidden: a.style.display === "none",
    bar: a.previousElementSibling ? a.previousElementSibling.textContent : ""
  })));
  const folded = res.filter((x) => x.folded).length;
  for (const x of res) assert.equal(x.folded, x.expect === "1");
  assert.ok(res.filter((x) => x.folded).every((x) => x.hidden && x.bar.startsWith("Folded by Jev (0.93)")));
  // click-to-expand keeps the node
  await page.click(".jev-fold-bar");
  assert.equal(await page.locator('article[data-testid="tweet"]').count(), 6);
  console.log(`[3] Playwright (${mode}): ${folded} folded, ${6 - folded} kept -> PASS`);
} finally {
  await ctx.close();
}
