#!/usr/bin/env node
// scripts/seed_reviews.mjs — one-off bootstrap import of curated reviews
// (the four hand-picked existing quotes + anything Firecrawl scraped from
// Superprof / Meetup / TrainMe) into DASHBOARD_KV as approved reviews.
//
// Runs against the deployed /api/reviews-admin endpoint. Requires the
// DASHBOARD_USER + DASHBOARD_PASS pair (Basic-Auth), same credentials as
// /dashboard/*.
//
// Usage:
//   $env:DASHBOARD_USER = 'debanjan'
//   $env:DASHBOARD_PASS = '...'
//   node scripts/seed_reviews.mjs [--dry-run] [--source reviews-seed.json]
//   node scripts/seed_reviews.mjs --source path/to/jitendra_platform_reviews.json
//
// --dry-run prints what would be imported without POSTing to KV.
//
// Idempotency: this script does NOT dedupe against existing approved keys.
// Re-running it will create duplicates. Only run once per source file.

import { readFile } from 'node:fs/promises';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = resolve(__dirname, '..');

const argv = process.argv.slice(2);
const dryRun = argv.includes('--dry-run');
const sourceIdx = argv.indexOf('--source');
const sourcePath = sourceIdx >= 0 ? argv[sourceIdx + 1] : resolve(PROJECT_ROOT, 'src/content/reviews-seed.json');

const BASE_URL = process.env.SEED_TARGET_URL || 'https://yoga-jitendra.pages.dev';
const USER = process.env.DASHBOARD_USER || 'debanjan';
const PASS = process.env.DASHBOARD_PASS;

if (!PASS && !dryRun) {
  console.error('ERROR: DASHBOARD_PASS not set. Export it, or run with --dry-run.');
  process.exit(1);
}

const authHeader = 'Basic ' + Buffer.from(USER + ':' + (PASS || '')).toString('base64');

function log(msg) {
  process.stdout.write(`[seed_reviews] ${msg}\n`);
}

async function postImport(record) {
  const form = new URLSearchParams();
  form.set('action', 'import');
  form.set('name', record.name);
  form.set('rating', String(record.rating));
  form.set('body', record.body || record.body_fr || record.body_en || '');
  form.set('source', record.source || 'other');
  if (record.source_url) form.set('source_url', record.source_url);
  form.set('lang', record.lang || 'fr');
  if (record.submitted_at) form.set('submitted_at', record.submitted_at);
  if (record.featured) form.set('featured', '1');

  if (dryRun) {
    log(`DRY-RUN would import: ${record.name} (${record.source}) — ${(record.body || record.body_fr || '').slice(0, 60)}…`);
    return { ok: true, dry: true };
  }

  const resp = await fetch(BASE_URL + '/api/reviews-admin', {
    method: 'POST',
    body: form,
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
      Authorization: authHeader,
    },
  });
  const text = await resp.text();
  return { ok: resp.ok, status: resp.status, body: text };
}

async function main() {
  log(`source: ${sourcePath}`);
  log(`target: ${BASE_URL}${dryRun ? ' (DRY-RUN — no writes)' : ''}`);

  let raw;
  try {
    raw = await readFile(sourcePath, 'utf8');
  } catch (err) {
    console.error(`ERROR: could not read ${sourcePath}: ${err.message}`);
    process.exit(2);
  }
  const parsed = JSON.parse(raw);
  const list = Array.isArray(parsed) ? parsed : parsed.reviews;
  if (!Array.isArray(list)) {
    console.error('ERROR: source file does not contain a `reviews` array or top-level array.');
    process.exit(3);
  }

  log(`importing ${list.length} reviews…`);
  let ok = 0;
  let fail = 0;
  for (const record of list) {
    // Some records may carry body_fr + body_en; import as the primary lang.
    // The moderation UI can add the other-lang copy later if desired.
    const chosen = { ...record };
    if (!chosen.body && chosen.body_fr) chosen.body = chosen.body_fr;
    if (!chosen.body && chosen.body_en) chosen.body = chosen.body_en;
    const res = await postImport(chosen);
    if (res.ok) {
      ok += 1;
      log(`  ✓ ${chosen.name}`);
    } else {
      fail += 1;
      log(`  ✗ ${chosen.name} — ${res.status} ${String(res.body).slice(0, 120)}`);
    }
  }
  log(`done: ${ok} ok, ${fail} failed`);
  if (fail > 0 && !dryRun) process.exit(4);
}

main().catch((err) => {
  console.error('unexpected error:', err.stack || err.message);
  process.exit(5);
});
