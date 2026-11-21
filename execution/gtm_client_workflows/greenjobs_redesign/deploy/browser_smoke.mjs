// GreenJobs post-deploy REAL-BROWSER smoke (eye review r2 N1: the HTTP smoke posted to the API directly and missed a
// form that posted to the wrong origin). Driven by smoke.py check_browser(); never run on its own against production
// with "apply" tasks (smoke.py sends those only where the environment pins DRY_RUN).
// description: reads one JSON spec on stdin {tasks: [...]}, runs each task in Playwright Chromium (launched with no
//   options) and prints one JSON line {checks: [{name, ok, detail}]}. Tasks:
//     apply  {name, url, expect_post, email}: open the job page, fill and submit the ON-PAGE form (no CV), assert the
//            POST went to expect_post (the edition's API base), answered 200/201, and the page shows the success
//            message. DRY_RUN on the Worker: nothing is mailed; the fixed address converges on one application row.
//     link   {name, url, expect}: every Apply button on a link-apply job page points at the employer's URL (expect),
//            on another host, and the page carries no on-site form.
//     layout {name, urls, widths}: no horizontal overflow at each phone width (isMobile, as on an iPhone).
// inputs: stdin JSON; PLAYWRIGHT_BROWSERS_PATH as the host provides it
// outputs: stdout one JSON line; exit 0 when the spec ran (check outcomes are in the JSON), 2 when Chromium or the
//   spec could not start (smoke.py records that as a failed check, never a skip)
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
let pw = null;
for (const m of ['playwright', '/opt/node22/lib/node_modules/playwright']) {
  try { pw = require(m); break; } catch { /* next location */ }
}
const out = (o, code = 0) => { process.stdout.write(JSON.stringify(o) + '\n'); process.exit(code); };
const short = (s, n = 140) => String(s || '').replace(/\s+/g, ' ').trim().slice(0, n);

let input = '';
for await (const c of process.stdin) input += c;
let spec;
try { spec = JSON.parse(input); } catch { out({ error: 'bad spec' }, 2); }
if (!pw) out({ error: 'playwright not installed' }, 2);
let browser;
try { browser = await pw.chromium.launch(); } catch (e) { out({ error: `chromium did not start: ${short(e.message, 80)}` }, 2); }

const CONSENT = { name: 'gj-consent', value: '{"essential":true,"analytics":false,"marketing":false}' };
async function newPage(opts = {}) {
  const ctx = await browser.newContext(opts);
  await ctx.addInitScript((c) => { try { localStorage.setItem(c.name, c.value); } catch { /* storage off */ } }, CONSENT);
  return { ctx, page: await ctx.newPage() };
}

async function applyTask(t) {
  const { ctx, page } = await newPage({ viewport: { width: 1280, height: 900 } });
  try {
    const posts = [];
    // every POST the page makes is recorded: the one to the wrong origin (Pages, 405) must show up, not hide
    page.on('response', (r) => { if (r.request().method() === 'POST' && new URL(r.url()).pathname === '/api/apply') posts.push({ url: r.url(), status: r.status() }); });
    const t0 = Date.now();
    const nav = await page.goto(t.url, { waitUntil: 'load', timeout: 45000 });
    if (!nav || nav.status() !== 200) return { ok: false, detail: `page HTTP ${nav ? nav.status() : 0}` };
    const form = page.locator('form[data-apply-form]');
    if ((await form.count()) !== 1) return { ok: false, detail: 'no on-page apply form' };
    await form.scrollIntoViewIfNeeded();
    await page.fill('#ap-name', 'Staging Browser Smoke');
    await page.fill('#ap-email', t.email);
    await page.fill('#ap-cover', 'Automated staging browser smoke test (DRY_RUN: nothing is sent).');
    await page.check('#ap-consent');
    const wait = 4500 - (Date.now() - t0); // the Worker refuses a form younger than 3 s (anti-bot render stamp)
    if (wait > 0) await page.waitForTimeout(wait);
    await page.click('form[data-apply-form] [type="submit"]');
    const st = page.locator('form[data-apply-form] [data-apply-status]');
    await page.waitForFunction(() => {
      const s = document.querySelector('form[data-apply-form] [data-apply-status]');
      return s && s.textContent && !/^Sending/.test(s.textContent);
    }, null, { timeout: 30000 }).catch(() => {});
    const text = short(await st.textContent());
    const post = posts[0];
    const toApi = Boolean(post && post.url.startsWith(t.expect_post));
    const ok = toApi && [200, 201].includes(post.status) && /^Application received/.test(text) && (await st.isVisible());
    return { ok, detail: `POST ${post ? `${new URL(post.url).host}${new URL(post.url).pathname}${new URL(post.url).search} -> ${post.status}` : 'none'}${toApi ? '' : ` (want ${t.expect_post})`}; status "${text}"` };
  } finally { await ctx.close(); }
}

async function linkTask(t) {
  const { ctx, page } = await newPage({ viewport: { width: 1280, height: 900 } });
  try {
    const nav = await page.goto(t.url, { waitUntil: 'load', timeout: 45000 });
    if (!nav || nav.status() !== 200) return { ok: false, detail: `page HTTP ${nav ? nav.status() : 0}` };
    const hrefs = await page.$$eval('a[data-apply]', (as) => as.map((a) => a.href));
    const forms = await page.locator('form[data-apply-form]').count();
    const boardHost = new URL(t.url).host;
    const ok = hrefs.length >= 1 && hrefs.every((h) => h === t.expect) && new URL(t.expect).host !== boardHost && forms === 0;
    return { ok, detail: `${hrefs.length} Apply button(s) -> ${short([...new Set(hrefs)].join(', '), 120)}; want ${t.expect}; on-page forms ${forms}` };
  } finally { await ctx.close(); }
}

async function layoutTask(t) {
  const bad = [];
  let n = 0;
  for (const w of t.widths) {
    const { ctx, page } = await newPage({ viewport: { width: w, height: 800 }, isMobile: true, hasTouch: true, deviceScaleFactor: 1 });
    try {
      for (const url of t.urls) {
        const nav = await page.goto(url, { waitUntil: 'load', timeout: 45000 });
        const m = await page.evaluate(() => ({ vw: window.innerWidth, sw: document.documentElement.scrollWidth }));
        n++;
        if (!nav || nav.status() !== 200 || m.sw > w || m.vw !== w) bad.push(`${new URL(url).pathname}@${w}: HTTP ${nav ? nav.status() : 0}, scrollWidth ${m.sw}, viewport ${m.vw}`);
      }
    } finally { await ctx.close(); }
  }
  return { ok: bad.length === 0 && n === t.urls.length * t.widths.length, detail: `${n} page x width checks, ${bad.length} overflow${bad.length ? `: ${short(bad[0], 160)}` : ''}` };
}

const RUN = { apply: applyTask, link: linkTask, layout: layoutTask };
const checks = [];
try {
  for (const t of spec.tasks || []) {
    const fn = RUN[t.kind];
    if (!fn) { checks.push({ name: t.name || 'browser', ok: false, detail: `unknown task ${t.kind}` }); continue; }
    try {
      const r = await fn(t);
      checks.push({ name: t.name, ok: r.ok, detail: r.detail });
    } catch (e) {
      checks.push({ name: t.name, ok: false, detail: `error: ${short(e.message, 160)}` });
    }
  }
} finally {
  await browser.close();
}
out({ checks });
