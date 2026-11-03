#!/usr/bin/env node
// tests/dom_acceptance_reviews.mjs
//
// Real-browser DOM acceptance test for the reviews system. Uses playwright
// + chromium headless to load each surface, wait for the client-side
// augmentation to run, and assert on the STATE A USER ACTUALLY SEES:
//
//   1. Eyebrow count matches KV live count on every surface (/, /reviews/,
//      /en/reviews/) — this is the class of bug the previous HTTP-only
//      acceptance test missed (baked count said 4 while KV had 9).
//   2. Rendered card count in the DOM matches KV live count on every
//      surface (accounts for the "Show more" hidden cards on the homepage).
//   3. Rating-star cascade works: clicking star N fills stars 1..N.
//   4. JSON-LD parses as valid JSON.
//   5. Homepage Turnstile widget renders (or the "temporarily unavailable"
//      notice appears — must be one or the other, never a broken widget).
//
// Env:
//   SITE_URL    default https://yogaavecjitendra.fr
//   HEADED=1    open a real Chromium window (for local debugging)
//
// Exit code non-zero on any assertion failure.

import { chromium } from 'playwright';

const SITE_URL = (process.env.SITE_URL || 'https://yogaavecjitendra.fr').replace(/\/$/, '');
const HEADED = process.env.HEADED === '1';

const failures = [];
const passes = [];

function ok(msg) {
  passes.push(msg);
  console.log('  ✓ ' + msg);
}
function fail(msg) {
  failures.push(msg);
  console.log('  ✗ ' + msg);
}

async function fetchKvCount() {
  const resp = await fetch(SITE_URL + '/api/reviews-public?fresh=1', {
    headers: { 'User-Agent': 'dom-acceptance/1' },
  });
  if (!resp.ok) throw new Error('KV read failed: ' + resp.status);
  const data = await resp.json();
  return {
    count: Number(data.count) || 0,
    avg: data.average_rating,
    reviews: Array.isArray(data.reviews) ? data.reviews : [],
  };
}

async function loadPage(browser, path) {
  const context = await browser.newContext({
    userAgent:
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    locale: 'en-GB',
  });
  const page = await context.newPage();
  const url = SITE_URL + path;
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
  // Wait for the augmentation fetch to complete. It runs as an IIFE
  // triggered by DOMContentLoaded; give it a network-idle + short buffer.
  await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(750);
  return { page, context };
}

async function checkEyebrowAndCards(page, path, kv, label) {
  console.log(`\n[${label}] ${path}`);

  // Rendered card count (visible + hidden — the show-more toggle hides some
  // via `display:none` on the homepage but keeps them in the DOM).
  const cardCount = await page.locator('[data-review-card]').count();
  if (cardCount === kv.count) {
    ok(`card count matches KV (${cardCount})`);
  } else {
    fail(`card count ${cardCount} !== KV ${kv.count}`);
  }

  // Eyebrow count: read from data-live-review-count if present. If the
  // page has no such element, the eyebrow itself is stale by design and
  // that's a real defect.
  const eyebrowCountEls = await page.locator('[data-live-review-count]').count();
  if (eyebrowCountEls === 0) {
    fail('no [data-live-review-count] element found — eyebrow will always be stale');
  } else {
    const eyebrowCount = await page.locator('[data-live-review-count]').first().textContent();
    const parsed = parseInt(String(eyebrowCount || '').trim(), 10);
    if (parsed === kv.count) {
      ok(`eyebrow count matches KV (${parsed})`);
    } else {
      fail(`eyebrow count "${eyebrowCount}" !== KV ${kv.count}`);
    }
  }

  // Eyebrow avg
  const eyebrowAvgEls = await page.locator('[data-live-review-avg]').count();
  if (eyebrowAvgEls > 0) {
    const eyebrowAvg = await page.locator('[data-live-review-avg]').first().textContent();
    const parsed = parseFloat(String(eyebrowAvg || '').trim());
    if (kv.avg !== null && Math.abs(parsed - kv.avg) < 0.05) {
      ok(`eyebrow avg matches KV (${parsed})`);
    } else {
      fail(`eyebrow avg "${eyebrowAvg}" !== KV ${kv.avg}`);
    }
  }

  // Every KV review's name should appear in the DOM (at least once).
  const domHtml = await page.content();
  let namesMissing = 0;
  for (const r of kv.reviews) {
    if (!r.name) continue;
    if (!domHtml.includes(r.name)) {
      fail(`KV review "${r.name}" not present in DOM`);
      namesMissing += 1;
    }
  }
  if (namesMissing === 0) {
    ok(`all ${kv.reviews.length} KV reviewer names present in DOM`);
  }
}

async function checkRatingCascade(page) {
  console.log('\n[rating cascade]');
  const pickerCount = await page.locator('.rating-picker').count();
  if (pickerCount === 0) {
    fail('no .rating-picker found on the page');
    return;
  }
  // Try to click the "4" star and assert stars 1..4 have .is-filled.
  const star4 = page.locator('.rating-picker input[value="4"]').first();
  await star4.click({ force: true });
  await page.waitForTimeout(150);
  const filled = await page.evaluate(() => {
    const spans = Array.from(document.querySelectorAll('.rating-picker .rating-star input'));
    return spans.map((inp) => {
      const label = inp.closest('label');
      const span = label ? label.querySelector('span[aria-hidden="true"]') : null;
      return {
        value: inp.value,
        filled: !!(span && span.classList.contains('is-filled')),
      };
    });
  });
  // Expect all stars with value <= 4 to be filled.
  const bad = filled.filter((s) => {
    const v = parseInt(s.value, 10);
    if (v <= 4) return !s.filled;
    return s.filled;
  });
  if (bad.length === 0) {
    ok('star click on 4 fills exactly stars 1-4');
  } else {
    fail('star cascade broken: ' + JSON.stringify(filled));
  }
}

async function checkJsonLd(page, path) {
  console.log(`\n[JSON-LD ${path}]`);
  const raw = await page.evaluate(() => {
    const node = document.querySelector('script[type="application/ld+json"]');
    return node ? node.textContent : null;
  });
  if (!raw) {
    fail('no ld+json script found');
    return;
  }
  try {
    const parsed = JSON.parse(raw);
    ok('ld+json parses as valid JSON');
    const graph = Array.isArray(parsed['@graph']) ? parsed['@graph'] : [];
    const biz = graph.find((n) => n && n.aggregateRating);
    if (biz) {
      ok(`aggregateRating present (reviewCount=${biz.aggregateRating.reviewCount})`);
    } else {
      fail('no aggregateRating in ld+json graph');
    }
  } catch (e) {
    fail('ld+json is not valid JSON: ' + e.message);
  }
}

async function checkTurnstileOrFallback(page) {
  console.log('\n[Turnstile / fallback]');
  const turnstile = await page.locator('.cf-turnstile').count();
  const fallback = await page.locator('.review-form-disabled').count();
  if (turnstile > 0) {
    ok(`Turnstile widget slot present (${turnstile})`);
  } else if (fallback > 0) {
    ok(`fallback "temporarily unavailable" notice present (${fallback})`);
  } else {
    fail('neither Turnstile widget nor fallback notice found — broken form');
  }
}

async function main() {
  console.log(`dom_acceptance_reviews — target ${SITE_URL}`);

  let kv;
  try {
    kv = await fetchKvCount();
    console.log(`KV live state: ${kv.count} approved reviews, avg ${kv.avg}`);
  } catch (e) {
    fail('KV read failed: ' + e.message);
    process.exit(1);
  }

  const browser = await chromium.launch({ headless: !HEADED });

  try {
    // Homepage
    let ctx = await loadPage(browser, '/');
    await checkEyebrowAndCards(ctx.page, '/', kv, 'homepage');
    await checkJsonLd(ctx.page, '/');
    await checkTurnstileOrFallback(ctx.page);
    await checkRatingCascade(ctx.page);
    await ctx.context.close();

    // /reviews/ (FR)
    ctx = await loadPage(browser, '/reviews/');
    await checkEyebrowAndCards(ctx.page, '/reviews/', kv, '/reviews/ FR');
    await ctx.context.close();

    // /en/reviews/ (EN)
    ctx = await loadPage(browser, '/en/reviews/');
    await checkEyebrowAndCards(ctx.page, '/en/reviews/', kv, '/en/reviews/ EN');
    await ctx.context.close();
  } finally {
    await browser.close();
  }

  console.log(`\n${passes.length} pass / ${failures.length} fail`);
  if (failures.length > 0) {
    console.log('\nFAILURES:');
    failures.forEach((f) => console.log('  ✗ ' + f));
    process.exit(1);
  }
  console.log('PASS: all DOM acceptance checks passed');
}

main().catch((e) => {
  console.error('unexpected error:', e.stack || e.message);
  process.exit(2);
});
