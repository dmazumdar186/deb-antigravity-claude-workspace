#!/usr/bin/env node
// scripts/backfill_review_dates_from_maps.mjs
//
// One-off backfill for the yoga_jitendra reviews KV. Fixes the two related bugs
// documented in reviews-public.ts:
//
//   1. Silent-now default: pre-2026-08-03 the moderation UI stamped
//      submitted_at = now() when the operator left the "Submitted at" field
//      empty. Fingerprint: submitted_at === approved_at to the millisecond
//      (4 records: Virginie, Anastazia, Samya, Xavier).
//
//   2. Silent-now-with-delayed-approve variant: the operator entered a
//      close-but-wrong submitted_at manually. Fingerprint doesn't fire
//      (delta > 60s), but the date is still wrong (3 records: Atlasia,
//      Sejal, Sakshi — all off by 4-7 days vs Google-authoritative).
//
// Google Business Profile API access was DENIED, so ground truth for Google
// reviews comes from scraping Google Maps' own internal /maps/timeline/_rpc/pc
// XHR endpoint (the same one every browser preloads when it opens a share
// link). No OAuth, no API key.
//
// Companion intermediate: .tmp/yoga_jitendra_reviews_backfill_2026-08-04.json
// (contains the resolved per-record dates + prior-art synthesis).
//
// USAGE:
//   cd execution/personal_workflows/yoga_jitendra_site/scripts
//
//   # Dry-run (default) — prints the exact wrangler commands it WOULD run:
//   node backfill_review_dates_from_maps.mjs
//
//   # Apply — mutates prod KV via wrangler:
//   node backfill_review_dates_from_maps.mjs --apply
//
//   # Re-scrape (default: use the pinned intermediate JSON):
//   node backfill_review_dates_from_maps.mjs --rescrape
//
// SAFETY:
//   * Only touches records listed as action=UPDATE or UPDATE_FROM_SEED in the
//     intermediate JSON — every other action is a no-op.
//   * Preserves every existing field. Only updates: submitted_at + edited_at
//     + adds date_backfill_source: "google_maps_scrape_2026-08-04".
//   * Idempotent: re-running does nothing (checks current KV vs target).
//   * Rollback: git-log the intermediate JSON's current_kv_submitted_at
//     values and put them back with the same script (edit action= fields).

import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';

const __dirname = dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = resolve(__dirname, '..');
const WORKSPACE_ROOT = resolve(PROJECT_ROOT, '../../../');
const CRON_WORKER_ROOT = resolve(WORKSPACE_ROOT, 'execution/infrastructure/yoga_jitendra_cron');
const INTERMEDIATE_PATH = resolve(
  WORKSPACE_ROOT,
  '.tmp/yoga_jitendra_reviews_backfill_2026-08-04.json',
);
const TMP_DIR = resolve(WORKSPACE_ROOT, '.tmp/backfill_review_dates');

const APPLY = process.argv.includes('--apply');
const RESCRAPE = process.argv.includes('--rescrape');
const KV_PREFIX = 'review:approved:';
const BACKFILL_SOURCE_TAG = 'google_maps_scrape_2026-08-04';

const PLACE_CID_DECIMAL = '14092612847233323851';

// ── logging ──────────────────────────────────────────────────────────────────

function log(msg) { process.stdout.write(`[backfill] ${msg}\n`); }
function warn(msg) { process.stderr.write(`[backfill] WARN: ${msg}\n`); }
function die(msg) { process.stderr.write(`[backfill] FATAL: ${msg}\n`); process.exit(1); }

// ── wrangler shell-out (cloned from pull_gbp_reviews.mjs — same shape) ──────

function runWrangler(args) {
  return new Promise((resolveOk, rejectFail) => {
    // shell:true concatenates args without escaping — a path containing spaces
    // (this workspace lives under "AntiGravity Project Space") splits into
    // multiple argv entries and wrangler dies on "Unknown argument". Quote any
    // arg with whitespace before handing it to the Windows shell.
    const shell = process.platform === 'win32';
    const shellArgs = shell
      ? args.map((a) => (/\s/.test(a) ? `"${a}"` : a))
      : args;
    const proc = spawn('npx', ['wrangler', ...shellArgs], {
      cwd: CRON_WORKER_ROOT,
      shell,
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    let stdout = '';
    let stderr = '';
    proc.stdout.on('data', (chunk) => (stdout += chunk.toString('utf8')));
    proc.stderr.on('data', (chunk) => (stderr += chunk.toString('utf8')));
    proc.on('error', (err) => rejectFail(err));
    proc.on('close', (code) => {
      if (code === 0) resolveOk({ stdout, stderr });
      else rejectFail(new Error(`wrangler ${args.join(' ')} exited ${code}: ${stderr.slice(0, 400)}`));
    });
  });
}

async function kvList(prefix) {
  const { stdout } = await runWrangler([
    'kv', 'key', 'list',
    '--binding=DASHBOARD_KV', '--remote',
    '--prefix', prefix,
  ]);
  try {
    const arr = JSON.parse(stdout);
    return Array.isArray(arr) ? arr.map((k) => k.name || k) : [];
  } catch {
    return stdout.split('\n').map((l) => l.trim()).filter(Boolean);
  }
}

async function kvGet(key) {
  try {
    const { stdout } = await runWrangler([
      'kv', 'key', 'get',
      '--binding=DASHBOARD_KV', '--remote',
      key,
    ]);
    return stdout;
  } catch { return null; }
}

async function kvPut(key, value) {
  const tmpValuePath = resolve(TMP_DIR, `_val_${Date.now()}_${Math.floor(Math.random() * 1e6)}.json`);
  await mkdir(TMP_DIR, { recursive: true });
  await writeFile(tmpValuePath, value, 'utf8');
  try {
    await runWrangler([
      'kv', 'key', 'put',
      '--binding=DASHBOARD_KV', '--remote',
      key, '--path', tmpValuePath,
    ]);
  } finally {
    try { await (await import('node:fs/promises')).unlink(tmpValuePath); } catch {}
  }
}

// ── Google Maps scraper (used only with --rescrape; default uses pinned JSON) ─

async function fetchWithBrowserHeaders(url, referer) {
  const headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'fr-FR,fr;q=0.9,en;q=0.8',
    'Accept': '*/*',
  };
  if (referer) {
    headers['Referer'] = referer;
    headers['Sec-Fetch-Site'] = 'same-origin';
    headers['Sec-Fetch-Mode'] = 'cors';
    headers['Sec-Fetch-Dest'] = 'empty';
  }
  const resp = await fetch(url, { headers, redirect: 'follow' });
  if (!resp.ok) throw new Error(`HTTP ${resp.status} for ${url}`);
  return await resp.text();
}

// Extract the /maps/timeline/_rpc/pc?pb=... preload URL from a Maps HTML page.
function extractPreloadUrl(html) {
  const m = html.match(/\/maps\/timeline\/_rpc\/pc\?[^"]+/);
  if (!m) return null;
  return 'https://www.google.com' + m[0].replace(/&amp;/g, '&');
}

// Parse the )]}'-prefixed JSON response from a share.google review pb call.
// Returns { microsec_ts, iso, name, visit_month } or nulls where missing.
function parseReviewPb(text) {
  const microsec = text.match(/\b(178[0-9]{13})\b/);
  const microsec_ts = microsec ? Number(microsec[1]) : null;
  const iso = microsec_ts ? new Date(microsec_ts / 1000).toISOString() : null;
  const nameMatch = text.match(/\["([A-Z][^"]{1,40})","https:\/\/lh3\.googleusercontent/);
  const vm = text.match(/\[\[\[(\d{4}),(\d+)\]\]/);
  return {
    microsec_ts,
    scraped_submitted_at: iso,
    name: nameMatch ? nameMatch[1] : null,
    visit_month: vm ? `${vm[1]}-${String(vm[2]).padStart(2, '0')}` : null,
  };
}

async function rescrapeAll(reviews) {
  log('rescrape mode: hitting Google Maps for each share.google URL...');
  const updated = [];
  for (const r of reviews) {
    if (!r.share_url) { updated.push(r); continue; }
    try {
      const html = await fetchWithBrowserHeaders(r.share_url);
      const pb = extractPreloadUrl(html);
      if (!pb) { warn(`no pb URL in ${r.share_url}`); updated.push(r); continue; }
      const body = await fetchWithBrowserHeaders(pb, r.share_url);
      const parsed = parseReviewPb(body);
      log(`  ${r.name}: ${parsed.scraped_submitted_at || '(no ts)'}`);
      updated.push({ ...r, ...parsed });
      // Gentle pacing so we don't trip Google's rate limit.
      await new Promise((r) => setTimeout(r, 1500));
    } catch (err) {
      warn(`scrape failed for ${r.name}: ${err.message}`);
      updated.push(r);
    }
  }
  return updated;
}

// ── main ─────────────────────────────────────────────────────────────────────

async function main() {
  if (!existsSync(INTERMEDIATE_PATH)) {
    die(`intermediate JSON not found: ${INTERMEDIATE_PATH}. ` +
        `Re-run the discovery pass or check --rescrape mode.`);
  }
  const intermediate = JSON.parse(await readFile(INTERMEDIATE_PATH, 'utf8'));
  let reviews = intermediate.reviews || [];

  if (RESCRAPE) {
    reviews = await rescrapeAll(reviews);
    // Persist the rescraped intermediate alongside the pinned one.
    const outPath = resolve(TMP_DIR, `intermediate_rescraped_${Date.now()}.json`);
    await mkdir(TMP_DIR, { recursive: true });
    await writeFile(outPath, JSON.stringify({ ...intermediate, reviews }, null, 2), 'utf8');
    log(`wrote rescraped intermediate to ${outPath}`);
  }

  // Build the update plan by cross-referencing intermediate.action + live KV.
  log(`mode: ${APPLY ? 'APPLY (writes to prod KV)' : 'DRY-RUN (no writes)'}`);
  log(`intermediate loaded: ${reviews.length} records total`);

  const targetsById = new Map();
  for (const r of reviews) {
    if (r.action === 'UPDATE' || r.action === 'UPDATE_FROM_SEED') {
      if (r.scraped_submitted_at) targetsById.set(r.kv_id, r);
    }
  }
  log(`records to update: ${targetsById.size}`);

  // List every KV key and find the ones that match our target IDs.
  const allKeys = await kvList(KV_PREFIX);
  log(`kv keys under ${KV_PREFIX}: ${allKeys.length}`);

  const decisions = [];
  const nowIso = new Date().toISOString();

  for (const key of allKeys) {
    const raw = await kvGet(key);
    if (!raw) continue;
    let rec;
    try { rec = JSON.parse(raw); } catch {
      warn(`corrupt KV entry: ${key}`);
      continue;
    }
    const target = targetsById.get(rec.id);
    if (!target) {
      decisions.push({ key, id: rec.id, name: rec.name, decision: 'skip_no_match' });
      continue;
    }
    // Idempotency: if the current submitted_at already matches within 1 minute
    // of the target, skip.
    const currentMs = Date.parse(rec.submitted_at || '');
    const targetMs = Date.parse(target.scraped_submitted_at);
    if (
      Number.isFinite(currentMs) && Number.isFinite(targetMs) &&
      Math.abs(currentMs - targetMs) < 60_000 &&
      rec.date_backfill_source === BACKFILL_SOURCE_TAG
    ) {
      decisions.push({ key, id: rec.id, name: rec.name, decision: 'already_backfilled' });
      continue;
    }
    const updated = {
      ...rec,
      submitted_at: target.scraped_submitted_at,
      edited_at: nowIso,
      date_backfill_source: BACKFILL_SOURCE_TAG,
    };
    decisions.push({
      key,
      id: rec.id,
      name: rec.name,
      decision: 'update',
      before: { submitted_at: rec.submitted_at, edited_at: rec.edited_at || null },
      after: { submitted_at: updated.submitted_at, edited_at: updated.edited_at },
      diff_days: (targetMs - currentMs) / 86400000,
    });
    if (APPLY) {
      await kvPut(key, JSON.stringify(updated));
      log(`  applied: ${rec.name} — ${rec.submitted_at} → ${updated.submitted_at}`);
    } else {
      log(`  DRY: ${rec.name} — ${rec.submitted_at} → ${updated.submitted_at} (Δ ${((targetMs - currentMs) / 86400000).toFixed(1)}d)`);
    }
  }

  // Also print records we would have wanted to update but that never showed
  // up in KV (indicator of a mismatched id or a deleted record).
  const seenIds = new Set(decisions.map((d) => d.id));
  for (const [id, target] of targetsById.entries()) {
    if (!seenIds.has(id)) {
      warn(`target id ${id} (${target.name}) not found in KV — skipped`);
      decisions.push({ id, name: target.name, decision: 'not_in_kv' });
    }
  }

  const summary = {
    ts: nowIso,
    apply: APPLY,
    rescrape: RESCRAPE,
    intermediate_path: INTERMEDIATE_PATH,
    counts: decisions.reduce((acc, d) => { acc[d.decision] = (acc[d.decision] || 0) + 1; return acc; }, {}),
    decisions,
  };
  await mkdir(TMP_DIR, { recursive: true });
  const logPath = resolve(TMP_DIR, `${nowIso.replace(/[:.]/g, '-')}.json`);
  await writeFile(logPath, JSON.stringify(summary, null, 2) + '\n', 'utf8');
  log(`wrote decision log: ${logPath}`);
  log(`summary: ${JSON.stringify(summary.counts)}`);

  if (!APPLY) {
    log('DRY-RUN complete. Re-run with --apply to mutate prod KV.');
  }
}

main().catch((err) => {
  process.stderr.write(`[backfill] FATAL: ${err?.stack || err?.message || err}\n`);
  process.exit(1);
});
