#!/usr/bin/env node
// scripts/sync_reviews.mjs — build-time review hydration.
//
// Called via `npm run prebuild` before every `astro build`. Fetches the
// approved review list from /api/reviews-public on the live site and writes
// src/content/reviews.json for Testimonials.astro / ReviewsGrid.astro /
// /reviews page to read at render time. On fetch failure (first-ever
// build, KV outage, offline dev, DNS blip), falls back to the checked-in
// reviews-seed.json so the build never breaks.
//
// The seed file is also the migration source for scripts/seed_reviews.mjs.
//
// Env vars:
//   SYNC_REVIEWS_URL   Override the fetch URL. Default:
//                      https://yoga-jitendra.pages.dev/api/reviews-public?fresh=1
//   SYNC_REVIEWS_SKIP  If '1', skip fetch entirely and use only the seed
//                      (useful for offline / airplane builds).

import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = resolve(__dirname, '..');
const SEED_PATH = resolve(PROJECT_ROOT, 'src/content/reviews-seed.json');
const OUT_PATH = resolve(PROJECT_ROOT, 'src/content/reviews.json');

const DEFAULT_URL = 'https://yoga-jitendra.pages.dev/api/reviews-public?fresh=1';
const FETCH_URL = process.env.SYNC_REVIEWS_URL || DEFAULT_URL;
const FETCH_TIMEOUT_MS = 8000;
const SKIP = process.env.SYNC_REVIEWS_SKIP === '1';

function log(msg) {
  process.stdout.write(`[sync_reviews] ${msg}\n`);
}
function warn(msg) {
  process.stderr.write(`[sync_reviews] WARN: ${msg}\n`);
}

// Normalize records from either source (KV response OR seed file) into the
// unified shape Testimonials/ReviewsGrid expects. The seed file carries
// body_fr + body_en side-by-side; the KV records carry a single `body` in
// the submitter's language. Downstream code picks based on `lang`.
function normalizeSeedRecord(r) {
  return {
    id: r.id,
    name: r.name,
    rating: r.rating,
    // Store both when available (seed) — downstream can pick per-lang.
    body: r.body_fr || r.body_en || r.body || '',
    body_fr: r.body_fr || null,
    body_en: r.body_en || null,
    source: r.source,
    source_url: r.source_url || null,
    lang: r.lang || 'fr',
    submitted_at: r.submitted_at,
    approved_at: r.approved_at || r.submitted_at,
    featured: !!r.featured,
    verified: !!r.verified,
  };
}

function normalizeKVRecord(r) {
  return {
    id: r.id,
    name: r.name,
    rating: r.rating,
    body: r.body || '',
    body_fr: r.body_fr || null,
    body_en: r.body_en || null,
    source: r.source,
    source_url: r.source_url || null,
    lang: r.lang || 'fr',
    submitted_at: r.submitted_at,
    approved_at: r.approved_at || r.submitted_at,
    featured: !!r.featured,
    verified: !!r.verified,
  };
}

async function loadSeed() {
  try {
    const raw = await readFile(SEED_PATH, 'utf8');
    const parsed = JSON.parse(raw);
    const reviews = Array.isArray(parsed.reviews) ? parsed.reviews.map(normalizeSeedRecord) : [];
    return reviews;
  } catch (err) {
    warn(`could not load seed at ${SEED_PATH}: ${err.message}`);
    return [];
  }
}

async function fetchWithTimeout(url, ms) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), ms);
  try {
    const resp = await fetch(url, { signal: controller.signal, headers: { Accept: 'application/json' } });
    return resp;
  } finally {
    clearTimeout(timer);
  }
}

async function fetchLive() {
  try {
    const resp = await fetchWithTimeout(FETCH_URL, FETCH_TIMEOUT_MS);
    if (!resp.ok) {
      warn(`fetch ${FETCH_URL} returned ${resp.status}`);
      return null;
    }
    const data = await resp.json();
    if (!data || !Array.isArray(data.reviews)) {
      warn(`unexpected response shape from ${FETCH_URL}`);
      return null;
    }
    return data.reviews.map(normalizeKVRecord);
  } catch (err) {
    warn(`fetch failed: ${err.message}`);
    return null;
  }
}

function computeAggregate(reviews) {
  if (!reviews.length) return { count: 0, average_rating: null };
  const total = reviews.reduce((s, r) => s + (Number(r.rating) || 0), 0);
  return {
    count: reviews.length,
    average_rating: Math.round((total / reviews.length) * 10) / 10,
  };
}

function sortReviews(reviews) {
  reviews.sort((a, b) => {
    if (a.featured !== b.featured) return a.featured ? -1 : 1;
    const ak = a.approved_at || a.submitted_at || '';
    const bk = b.approved_at || b.submitted_at || '';
    return bk.localeCompare(ak);
  });
}

async function main() {
  const seed = await loadSeed();
  let source = 'seed';
  let reviews = seed;

  if (!SKIP) {
    const live = await fetchLive();
    if (live && live.length >= seed.length) {
      // Prefer live once it has at least as many reviews as the seed —
      // guards against KV wipes silently blanking the site.
      reviews = live;
      source = 'live';
    } else if (live) {
      warn(`live returned ${live.length} < seed ${seed.length}; keeping seed to avoid data loss`);
    }
  } else {
    log('SYNC_REVIEWS_SKIP=1 → seed only');
  }

  sortReviews(reviews);
  const agg = computeAggregate(reviews);

  const out = {
    _generated_at: new Date().toISOString(),
    _source: source,
    _fetch_url: SKIP ? null : FETCH_URL,
    count: agg.count,
    average_rating: agg.average_rating,
    reviews,
  };

  await mkdir(dirname(OUT_PATH), { recursive: true });
  await writeFile(OUT_PATH, JSON.stringify(out, null, 2) + '\n', 'utf8');
  log(`wrote ${reviews.length} reviews (${source}) → ${OUT_PATH}`);
}

main().catch((err) => {
  warn(`unexpected error: ${err.stack || err.message}`);
  // Emit an empty-but-well-formed file so the build doesn't crash on read.
  const fallback = {
    _generated_at: new Date().toISOString(),
    _source: 'error',
    _fetch_url: null,
    count: 0,
    average_rating: null,
    reviews: [],
  };
  writeFile(OUT_PATH, JSON.stringify(fallback, null, 2) + '\n', 'utf8').catch(() => {});
  process.exit(0); // never fail the build
});
