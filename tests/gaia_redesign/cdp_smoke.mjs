#!/usr/bin/env node
// CDP-driven E2E smoke test for the Gaia Talent redesign.
// description: Drives a real headless Chromium over the Chrome DevTools
//   Protocol (not a static screenshot) to exercise the scroll-scrubbed hero
//   canvas, the pinned card stack, IntersectionObserver reveals, the
//   solidifying header, the mobile menu and the jobs filter. Captures every
//   console/Log message; any JS error fails the run. The canvas perf check
//   asserts two things over 60 rAFs while scrolling: mean rAF-to-rAF
//   interval <=17.5ms (no sustained dropped frames) and worst-case interval
//   <34ms (no double-dropped frame) — not a <=16ms mean, which is just the
//   60Hz vsync interval and can never pass regardless of canvas cost.
// inputs: env SITE_PORT (default 8899, must already be serving the built
//   site), env CDP_PORT (default 9222, a headless_shell with
//   --remote-debugging-port must already be listening), env SHOT_DIR
// outputs: PNGs under SHOT_DIR; PASS/FAIL lines on stdout; exit code 1 on any
//   FAIL or console error.
//
// Run: node tests/gaia_redesign/cdp_smoke.mjs

import { writeFile, mkdir } from 'node:fs/promises';
import path from 'node:path';

const SITE_PORT = process.env.SITE_PORT || '8899';
const CDP_PORT = process.env.CDP_PORT || '9222';
const SHOT_DIR = process.env.SHOT_DIR || '/home/user/deb-antigravity-claude-workspace/.tmp/gaia_redesign_shots/live';
const BASE = `http://localhost:${SITE_PORT}`;

let results = [];
function check(ok, label, extra) {
  results.push({ ok, label });
  console.log((ok ? 'PASS  ' : 'FAIL  ') + label + (extra ? '  (' + extra + ')' : ''));
}

async function newTab() {
  const res = await fetch(`http://127.0.0.1:${CDP_PORT}/json/new?about:blank`, { method: 'PUT' });
  return res.json();
}
async function closeTab(id) {
  await fetch(`http://127.0.0.1:${CDP_PORT}/json/close/${id}`);
}

class CDP {
  constructor(wsUrl) {
    this.ws = new WebSocket(wsUrl);
    this.id = 0;
    this.pending = new Map();
    this.consoleMessages = [];
    this.logEntries = [];
    this.pageErrors = [];
    this.ready = new Promise((resolve) => { this.ws.onopen = () => resolve(); });
    this.ws.onmessage = (ev) => this._onMessage(JSON.parse(ev.data));
  }
  _onMessage(msg) {
    if (msg.id !== undefined && this.pending.has(msg.id)) {
      const { resolve, reject } = this.pending.get(msg.id);
      this.pending.delete(msg.id);
      if (msg.error) reject(new Error(JSON.stringify(msg.error)));
      else resolve(msg.result);
      return;
    }
    if (msg.method === 'Runtime.consoleAPICalled') {
      const text = (msg.params.args || []).map((a) => a.value ?? a.description ?? '').join(' ');
      this.consoleMessages.push({ type: msg.params.type, text });
      if (msg.params.type === 'error') this.pageErrors.push('console.error: ' + text);
    }
    if (msg.method === 'Runtime.exceptionThrown') {
      const d = msg.params.exceptionDetails;
      this.pageErrors.push('exception: ' + (d.exception?.description || d.text));
    }
    if (msg.method === 'Log.entryAdded') {
      this.logEntries.push(msg.params.entry);
      if (msg.params.entry.level === 'error') this.pageErrors.push('log.error: ' + msg.params.entry.text);
    }
  }
  send(method, params = {}) {
    const id = ++this.id;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }
  async eval(expression, awaitPromise = false) {
    const r = await this.send('Runtime.evaluate', {
      expression, awaitPromise, returnByValue: true, allowUnsafeEvalBlockedByCSP: true,
    });
    if (r.exceptionDetails) {
      throw new Error('eval failed: ' + (r.exceptionDetails.exception?.description || r.exceptionDetails.text) + '\n  in: ' + expression.slice(0, 200));
    }
    return r.result.value;
  }
  async close() { try { this.ws.close(); } catch {} }
}

async function raf2() {
  return 'new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))';
}

async function drive(viewport) {
  const tab = await newTab();
  const cdp = new CDP(tab.webSocketDebuggerUrl);
  await cdp.ready;
  await cdp.send('Page.enable');
  await cdp.send('Runtime.enable');
  await cdp.send('Log.enable');
  await cdp.send('Performance.enable');

  if (viewport.mobile !== undefined || viewport.width) {
    await cdp.send('Emulation.setDeviceMetricsOverride', {
      width: viewport.width, height: viewport.height,
      deviceScaleFactor: 1, mobile: !!viewport.mobile,
    });
  }
  if (viewport.reducedMotion) {
    await cdp.send('Emulation.setEmulatedMedia', {
      features: [{ name: 'prefers-reduced-motion', value: 'reduce' }],
    });
  }

  await cdp.send('Page.navigate', { url: `${BASE}/index.html` });
  // Wait for load via Page.loadEventFired
  await new Promise((resolve) => {
    const handler = (ev) => {
      const data = JSON.parse(ev.data);
      if (data.method === 'Page.loadEventFired') { cdp.ws.removeEventListener('message', handler); resolve(); }
    };
    cdp.ws.addEventListener('message', handler);
    setTimeout(resolve, 8000); // safety net
  });
  await new Promise((r) => setTimeout(r, 300)); // let init IIFEs run

  return cdp;
}

async function clickElement(cdp, selector) {
  const rect = await cdp.eval(`(() => {
    const el = document.querySelector(${JSON.stringify(selector)});
    const r = el.getBoundingClientRect();
    return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
  })()`);
  await cdp.send('Input.dispatchMouseEvent', { type: 'mousePressed', x: rect.x, y: rect.y, button: 'left', clickCount: 1 });
  await cdp.send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: rect.x, y: rect.y, button: 'left', clickCount: 1 });
}

async function shot(cdp, name) {
  const r = await cdp.send('Page.captureScreenshot', { format: 'png' });
  await mkdir(SHOT_DIR, { recursive: true });
  const file = path.join(SHOT_DIR, name + '.png');
  await writeFile(file, Buffer.from(r.data, 'base64'));
  return file;
}

async function scrollAndSettle(cdp, y) {
  // The site sets `html { scroll-behavior: smooth }` (css/*.css:69), which turns
  // even a scripted two-arg scrollTo() into an animated scroll. A test driver
  // must force 'instant' or it reads state mid-animation. One combined
  // async-IIFE eval also halves the CDP round trips vs. two separate calls.
  await cdp.eval(
    `(async () => { window.scrollTo({ top: ${y}, left: 0, behavior: 'instant' });
      await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))); })()`,
    true
  );
  await new Promise((r) => setTimeout(r, 60)); // let the rAF-scheduled frame() run
}

async function testDesktopHero() {
  console.log('\n--- E2E: desktop hero (1440x900), scroll-scrubbed canvas + step rail ---');
  const cdp = await drive({ width: 1440, height: 900 });
  try {
    const trackHeight = await cdp.eval(
      "document.querySelector('[data-flow]').getBoundingClientRect().height"
    );
    check(trackHeight > 900 * 2, 'hero track is pinned (height > 2x viewport)', `height=${trackHeight}`);

    const fractions = [0, 0.1, 0.25, 0.4, 0.55, 0.7, 0.85, 1.0];
    const activeIndices = [];
    const fillSnapshots = [];
    const pixelSums = [];
    for (const f of fractions) {
      const y = Math.round(f * (trackHeight - 900));
      await scrollAndSettle(cdp, y);
      const state = await cdp.eval(`(() => {
        const panels = Array.from(document.querySelectorAll('[data-flow-panel]'));
        const active = panels.findIndex(p => p.classList.contains('is-on'));
        const steps = Array.from(document.querySelectorAll('[data-flow-step]'));
        const fills = steps.map(s => getComputedStyle(s).getPropertyValue('--fill').trim());
        const canvas = document.querySelector('[data-flow-scene]');
        const ctx = canvas.getContext('2d');
        let sum = 0;
        try {
          const img = ctx.getImageData(0, 0, canvas.width, canvas.height);
          for (let i = 0; i < img.data.length; i += 97) sum += img.data[i];
        } catch (e) { sum = -1; }
        return { active, fills, sum, hdrScrolled: document.querySelector('[data-header]').classList.contains('is-scrolled') };
      })()`);
      activeIndices.push(state.active);
      fillSnapshots.push(state.fills.join(','));
      pixelSums.push(state.sum);
      await shot(cdp, `desktop-hero-scroll-${Math.round(f * 100)}pct`);
    }
    console.log('  active panel indices across scroll:', activeIndices.join(' -> '));
    let monotonic = true;
    for (let i = 1; i < activeIndices.length; i++) {
      if (activeIndices[i] < activeIndices[i - 1]) monotonic = false;
    }
    check(monotonic, 'active [data-flow-panel].is-on index is monotonically non-decreasing with scroll', activeIndices.join(','));
    check(new Set(activeIndices).size >= 4, 'hero visits at least 4 distinct states across the scroll range', [...new Set(activeIndices)].join(','));
    check(new Set(fillSnapshots).size > 1, 'step rail --fill values change across scroll positions');
    check(new Set(pixelSums.filter((s) => s >= 0)).size > 1, 'canvas pixel data (sampled sum) differs between scroll positions', pixelSums.join(','));

    // header solidify: scroll to y=0 then y=200 and compare is-scrolled
    await scrollAndSettle(cdp, 0);
    const hdr0 = await cdp.eval("document.querySelector('[data-header]').classList.contains('is-scrolled')");
    await scrollAndSettle(cdp, 200);
    const hdr200 = await cdp.eval("document.querySelector('[data-header]').classList.contains('is-scrolled')");
    check(hdr0 === false && hdr200 === true, 'header gains is-scrolled after scrollY > 48', `y0=${hdr0} y200=${hdr200}`);

    console.log('\n--- E2E: pinned card stack ---');
    const stackRect = await cdp.eval("(() => { const s = document.querySelector('[data-stack]'); return s ? s.getBoundingClientRect() : null; })()");
    check(!!stackRect, 'document.querySelector([data-stack]) exists');
    const stackTop = await cdp.eval("document.querySelector('[data-stack]').offsetTop");
    await scrollAndSettle(cdp, Math.max(0, stackTop - 400));
    const varsA = await cdp.eval(`(() => {
      const c = document.querySelector('[data-stack] [data-card]');
      const s = getComputedStyle(c);
      return [s.getPropertyValue('--card-y'), s.getPropertyValue('--card-rot'), s.getPropertyValue('--card-scale'), s.getPropertyValue('--card-opacity')].join('|');
    })()`);
    await scrollAndSettle(cdp, stackTop + 300);
    const varsB = await cdp.eval(`(() => {
      const c = document.querySelector('[data-stack] [data-card]');
      const s = getComputedStyle(c);
      return [s.getPropertyValue('--card-y'), s.getPropertyValue('--card-rot'), s.getPropertyValue('--card-scale'), s.getPropertyValue('--card-opacity')].join('|');
    })()`);
    check(varsA !== varsB, 'card CSS vars (--card-y/--card-rot/--card-scale/--card-opacity) change between scroll positions', `${varsA}  vs  ${varsB}`);
    await shot(cdp, 'desktop-stack-mid-scroll');

    console.log('\n--- E2E: reveals via IntersectionObserver ---');
    await scrollAndSettle(cdp, 0);
    const beforeVisible = await cdp.eval("document.querySelectorAll('[data-reveal].is-visible').length");
    const revealTop = await cdp.eval("(() => { const el = document.querySelector('[data-reveal]:not(.is-visible)') || document.querySelector('[data-reveal]'); return el ? el.getBoundingClientRect().top + window.scrollY - 200 : -1; })()");
    if (revealTop >= 0) await scrollAndSettle(cdp, revealTop);
    await new Promise((r) => setTimeout(r, 300));
    const afterVisible = await cdp.eval("document.querySelectorAll('[data-reveal].is-visible').length");
    check(afterVisible > beforeVisible, 'at least one [data-reveal] gains is-visible after scrolling into view', `before=${beforeVisible} after=${afterVisible}`);

    return cdp;
  } finally {
    const errs = cdp.pageErrors;
    check(errs.length === 0, 'no JS console errors / exceptions during desktop hero + stack run', errs.join(' | '));
    await cdp.close();
  }
}

async function testMobile() {
  console.log('\n--- E2E: mobile (390x844) — flatten path + menu ---');
  const cdp = await drive({ width: 390, height: 844, mobile: true });
  try {
    const flowStageDisplay = await cdp.eval("getComputedStyle(document.querySelector('.flow__stage')).display");
    check(flowStageDisplay === 'none', 'mobile: .flow__stage is display:none (flatten path, no pinning)', flowStageDisplay);
    const fallbackDisplay = await cdp.eval("getComputedStyle(document.querySelector('.flow__fallback')).display");
    check(fallbackDisplay === 'block', 'mobile: .flow__fallback is visible', fallbackDisplay);
    const stackStatic = await cdp.eval("getComputedStyle(document.querySelector('.stack__sticky')).position");
    check(stackStatic === 'static', 'mobile: pinned stack sticky wrapper is position:static (stacked blocks, not pinned)', stackStatic);
    await shot(cdp, 'mobile-390-top');

    const before = await cdp.eval(`(() => {
      const t = document.querySelector('[data-menu-toggle]');
      return { expanded: t.getAttribute('aria-expanded'), menuOpen: document.querySelector('[data-menu]').classList.contains('is-open') };
    })()`);
    check(before.expanded !== 'true', 'mobile menu starts closed (aria-expanded != true)', before.expanded);

    // A programmatic element.click() does not carry the browser's native
    // "focus the button on click" side effect (that only fires for a real
    // pointer gesture), which would make the focus-handling assertions below
    // pass or fail on an artifact of the driver rather than the page. Dispatch
    // a real synthetic mouse click via CDP Input instead.
    await clickElement(cdp, '[data-menu-toggle]');
    await new Promise((r) => setTimeout(r, 150));
    const afterOpen = await cdp.eval(`(() => {
      const t = document.querySelector('[data-menu-toggle]');
      const active = document.activeElement;
      return {
        expanded: t.getAttribute('aria-expanded'),
        menuOpen: document.querySelector('[data-menu]').classList.contains('is-open'),
        activeIsInMenu: !!(active && active.closest('[data-menu]')),
        activeTag: active ? active.tagName : null,
      };
    })()`);
    check(afterOpen.expanded === 'true' && afterOpen.menuOpen, 'mobile menu opens: aria-expanded=true and .is-open set', JSON.stringify(afterOpen));
    check(afterOpen.activeIsInMenu, 'focus moves into the open menu (first link/button)', JSON.stringify(afterOpen));
    await shot(cdp, 'mobile-390-menu-open');

    await clickElement(cdp, '[data-menu-toggle]');
    await new Promise((r) => setTimeout(r, 150));
    const afterClose = await cdp.eval(`(() => {
      const t = document.querySelector('[data-menu-toggle]');
      return { expanded: t.getAttribute('aria-expanded'), menuOpen: document.querySelector('[data-menu]').classList.contains('is-open'), activeIsToggle: document.activeElement === t };
    })()`);
    check(afterClose.expanded === 'false' && !afterClose.menuOpen, 'mobile menu closes on second click', JSON.stringify(afterClose));
    check(afterClose.activeIsToggle, 'focus returns to the toggle button on close', JSON.stringify(afterClose));

    return cdp;
  } finally {
    check(cdp.pageErrors.length === 0, 'no JS console errors / exceptions during mobile run', cdp.pageErrors.join(' | '));
    await cdp.close();
  }
}

async function testReducedMotion() {
  console.log('\n--- E2E: prefers-reduced-motion: reduce ---');
  const cdp = await drive({ width: 1440, height: 900, reducedMotion: true });
  try {
    const flowHeight = await cdp.eval("document.querySelector('[data-flow]').getBoundingClientRect().height");
    // Pinned height is (panels + 1) * 100vh = 8 * 900 = 7200 at this viewport;
    // the flattened/stacked layout is naturally a few viewport-heights tall
    // (each of the 7 panels renders in flow), so the real signal is "much less
    // than the pinned height", not an absolute cap.
    check(flowHeight < 7200 * 0.6, 'reduced-motion: hero is NOT pinned (height far below the 7200px pinned track)', `height=${flowHeight}`);
    const stageDisplay = await cdp.eval("getComputedStyle(document.querySelector('.flow__stage')).display");
    check(stageDisplay === 'none', 'reduced-motion: canvas stage is hidden, fallback art shown instead', stageDisplay);
    const stackMinHeight = await cdp.eval("getComputedStyle(document.querySelector('.stack--pinned')).minHeight");
    check(stackMinHeight === '0px' || stackMinHeight === '0', 'reduced-motion: card stack is not pinned (min-height:0)', stackMinHeight);
    return cdp;
  } finally {
    check(cdp.pageErrors.length === 0, 'no JS console errors under reduced motion', cdp.pageErrors.join(' | '));
    await cdp.close();
  }
}

async function testJobsFilter() {
  console.log('\n--- E2E: jobs/index.html filter (sector containing "&") ---');
  const tab = await newTab();
  const cdp = new CDP(tab.webSocketDebuggerUrl);
  await cdp.ready;
  await cdp.send('Page.enable');
  await cdp.send('Runtime.enable');
  await cdp.send('Log.enable');
  await cdp.send('Page.navigate', { url: `${BASE}/jobs/index.html` });
  await new Promise((r) => setTimeout(r, 900));

  try {
    const options = await cdp.eval(`Array.from(document.getElementById('f-sector').options).map(o => o.value)`);
    const target = options.find((o) => o.includes('&'));
    check(!!target, 'jobs page has at least one sector option containing "&"', options.join(' | '));
    if (!target) return cdp;

    const expectedCount = await cdp.eval(`(() => {
      const rows = Array.from(document.querySelectorAll('[data-job]'));
      const want = ${JSON.stringify(target)}.trim().toLowerCase();
      return rows.filter(r => (r.dataset.sector || '').toLowerCase().split('|').includes(want)).length;
    })()`);

    await cdp.eval(`(() => {
      const sel = document.getElementById('f-sector');
      sel.value = ${JSON.stringify(target)};
      sel.dispatchEvent(new Event('change', { bubbles: true }));
    })()`);
    await new Promise((r) => setTimeout(r, 400)); // syncUrl is debounced 250ms

    const shownCount = await cdp.eval(`document.querySelectorAll('[data-job]:not([hidden])').length`);
    check(shownCount === expectedCount, `row count after sector filter equals independently-computed count for ${JSON.stringify(target)}`, `shown=${shownCount} expected=${expectedCount}`);

    const url = await cdp.eval('window.location.search');
    // URLSearchParams.toString() encodes spaces as '+' (form encoding), which
    // decodeURIComponent does NOT convert back to a space (that's %20's job) —
    // parse it back out through URLSearchParams itself, the same as the value.
    const decodedSector = new URLSearchParams(url).get('sector');
    check(url.includes('sector=') && decodedSector === target, 'URL updated with the encoded sector value after filtering', `${url}  decoded="${decodedSector}"`);
    await shot(cdp, 'jobs-filter-applied');

    // click every [data-clear] and confirm rows restored
    const clearCount = await cdp.eval("document.querySelectorAll('[data-clear]').length");
    check(clearCount > 0, 'at least one [data-clear] button exists');
    const totalRows = await cdp.eval("document.querySelectorAll('[data-job]').length");
    for (let i = 0; i < clearCount; i++) {
      // re-apply the filter each time so the clear button is tested from a filtered state
      await cdp.eval(`(() => {
        const sel = document.getElementById('f-sector');
        sel.value = ${JSON.stringify(target)};
        sel.dispatchEvent(new Event('change', { bubbles: true }));
      })()`);
      await new Promise((r) => setTimeout(r, 350));
      await cdp.eval(`document.querySelectorAll('[data-clear]')[${i}].click()`);
      await new Promise((r) => setTimeout(r, 350));
      const restored = await cdp.eval("document.querySelectorAll('[data-job]:not([hidden])').length");
      check(restored === totalRows, `data-clear[${i}] restores all ${totalRows} rows`, `restored=${restored}`);
    }
    return cdp;
  } finally {
    check(cdp.pageErrors.length === 0, 'no JS console errors during jobs filter run', cdp.pageErrors.join(' | '));
    await cdp.close();
  }
}

async function perfFrameTime(width, height, label) {
  console.log(`\n--- PERF: canvas frame time @ ${label} ---`);
  const cdp = await drive({ width, height });
  try {
    // Measured entirely in-page (a single eval, one CDP round trip) so the
    // numbers reflect real rAF-to-rAF pacing (scroll + draw()), not the
    // WebSocket/IPC overhead of driving each frame from outside the page.
    //
    // rAF fires on vsync, so at 60Hz the interval BETWEEN two consecutive
    // rAF callbacks is ~16.67ms by definition, before the canvas draws a
    // single pixel — a `<= 16ms` threshold on the mean interval can never
    // pass on a 60Hz display and was measuring the display's refresh rate,
    // not our draw cost. Two real signals instead: the mean interval, which
    // creeps up only if frames are being sustained-dropped (a canvas that
    // is genuinely too slow to keep up with vsync), and the worst single
    // interval, which catches an occasional double-dropped frame (a janky
    // spike) that the mean can hide.
    const { avg, max } = await cdp.eval(
      `(() => new Promise((resolve) => {
        var n = 60, i = 0, y = 400, last = performance.now(), total = 0, worst = 0;
        function step(now) {
          var delta = now - last; total += delta; last = now;
          if (delta > worst) worst = delta;
          window.scrollTo({ top: y, left: 0, behavior: 'instant' });
          y += 4; i += 1;
          if (i < n) requestAnimationFrame(step); else resolve({ avg: total / n, max: worst });
        }
        requestAnimationFrame((now) => { last = now; requestAnimationFrame(step); });
      }))()`,
      true
    );
    // Mean threshold 17.5ms: a hair above one 60Hz frame (16.67ms), so a
    // clean run passes but any sustained frame-dropping still fails it.
    const meanOk = avg <= 17.5;
    // Worst-case threshold 34ms: just under two dropped 60Hz frames
    // (2 * 16.67 = 33.3ms), so one occasional double-drop is still a FAIL.
    const maxOk = max < 34;
    const meanLabel = `PERF canvas mean rAF interval @ ${label}: ${avg.toFixed(2)}ms/frame (threshold <=17.5ms; no sustained dropped frames; measured in-page over 60 rAFs while scrolling)`;
    const maxLabel = `PERF canvas worst-case rAF interval @ ${label}: ${max.toFixed(2)}ms (threshold <34ms; no double-dropped frame; measured in-page over 60 rAFs while scrolling)`;
    results.push({ ok: meanOk, label: meanLabel });
    results.push({ ok: maxOk, label: maxLabel });
    console.log(`${meanOk ? 'PASS' : 'FAIL'}  ${meanLabel}`);
    console.log(`${maxOk ? 'PASS' : 'FAIL'}  ${maxLabel}`);
  } finally {
    await cdp.close();
  }
}

async function main() {
  await mkdir(SHOT_DIR, { recursive: true });
  await testDesktopHero();
  await testMobile();
  await testReducedMotion();
  await testJobsFilter();
  await perfFrameTime(1440, 900, '1440x900');
  await perfFrameTime(390, 844, '390x844');

  const passed = results.filter((r) => r.ok).length;
  const failed = results.filter((r) => !r.ok);
  console.log(`\nCDP E2E: ${passed} passed, ${failed.length} failed`);
  for (const f of failed) console.log('  FAIL:', f.label);
  process.exit(failed.length ? 1 : 0);
}

main().catch((err) => {
  console.error('FATAL', err);
  process.exit(1);
});
