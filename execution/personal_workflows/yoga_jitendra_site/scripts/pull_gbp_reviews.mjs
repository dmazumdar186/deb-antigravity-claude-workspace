#!/usr/bin/env node
// scripts/pull_gbp_reviews.mjs — pull authoritative Google Business Profile
// reviews into DASHBOARD_KV. Recovers original createTime for every historical
// review, replacing the silent-now bug records shipped by the pre-2026-08 UI.
//
// Companion directive: directives/enrichment/gbp_reviews_sync.md
//
// Usage:
//   cd execution/personal_workflows/yoga_jitendra_site/scripts
//   # Dry-run (no writes; prints per-review plan):
//   node pull_gbp_reviews.mjs --dry-run
//   # Live pull (upserts to prod KV via wrangler kv, preserves local edits):
//   node pull_gbp_reviews.mjs
//   # Backfill mode: BEFORE the pull, delete every review:approved:* whose
//   # submitted_at === approved_at (± 1s) — the fingerprint of the pre-fix
//   # silent-now bug — so Google's real dates land clean.
//   node pull_gbp_reviews.mjs --backfill
//
// Env vars (from ../../../../.env at workspace root, loaded automatically):
//   GOOGLE_CLIENT_ID          OAuth client id (same as dashboard cron)
//   GOOGLE_CLIENT_SECRET      OAuth client secret
//   GOOGLE_REFRESH_TOKEN_GBP  Refresh token from scripts/get_google_refresh_token.py
//   GBP_ACCOUNT_ID            e.g. "accounts/123456789"
//   GBP_LOCATION_ID           e.g. "locations/987654321"
//
// KV writes go via `wrangler kv key put --binding=DASHBOARD_KV --remote` from
// the sibling cron worker's wrangler.toml (which has the binding pinned to
// namespace id 4cdf5cdb6fc14db3b29edcab6c464714). Requires wrangler CLI to
// be logged in against the Cloudflare account owning the KV.

import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';

const __dirname = dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = resolve(__dirname, '..');
const WORKSPACE_ROOT = resolve(PROJECT_ROOT, '../../../');
const CRON_WORKER_ROOT = resolve(WORKSPACE_ROOT, 'execution/infrastructure/yoga_jitendra_cron');
const TMP_DIR = resolve(WORKSPACE_ROOT, '.tmp/gbp_reviews_sync');
const ENV_PATH = resolve(WORKSPACE_ROOT, '.env');

const TOKEN_ENDPOINT = 'https://oauth2.googleapis.com/token';
const REVIEWS_API_BASE = 'https://mybusiness.googleapis.com/v4';
const RATING_MAP = { ONE: 1, TWO: 2, THREE: 3, FOUR: 4, FIVE: 5 };
const KV_KEY_PREFIX = 'review:approved:';
const BUG_FINGERPRINT_MS = 1000; // submitted_at within 1s of approved_at = silent-now bug

// ── CLI flags ────────────────────────────────────────────────────────────────

const DRY_RUN = process.argv.includes('--dry-run');
const BACKFILL = process.argv.includes('--backfill');
const DISCOVER_IDS = process.argv.includes('--discover-ids');

function log(msg) {
  process.stdout.write(`[gbp-sync] ${msg}\n`);
}
function warn(msg) {
  process.stderr.write(`[gbp-sync] WARN: ${msg}\n`);
}
function die(msg) {
  process.stderr.write(`[gbp-sync] FATAL: ${msg}\n`);
  process.exit(1);
}

// ── .env loader (no dotenv dep) ─────────────────────────────────────────────

async function loadEnv() {
  if (!existsSync(ENV_PATH)) {
    warn(`no .env at ${ENV_PATH}; relying on process.env`);
    return;
  }
  const raw = await readFile(ENV_PATH, 'utf8');
  for (const line of raw.split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const eq = trimmed.indexOf('=');
    if (eq === -1) continue;
    const key = trimmed.slice(0, eq).trim();
    let val = trimmed.slice(eq + 1).trim();
    // Strip surrounding quotes (single or double) if present.
    if ((val.startsWith('"') && val.endsWith('"')) || (val.startsWith("'") && val.endsWith("'"))) {
      val = val.slice(1, -1);
    }
    // Never overwrite an already-set process.env — preserves shell overrides.
    if (process.env[key] === undefined) process.env[key] = val;
  }
}

// ── Google OAuth ─────────────────────────────────────────────────────────────

async function getAccessToken() {
  const { GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN_GBP } = process.env;
  if (!GOOGLE_CLIENT_ID) die('GOOGLE_CLIENT_ID missing from .env');
  if (!GOOGLE_CLIENT_SECRET) die('GOOGLE_CLIENT_SECRET missing from .env');
  if (!GOOGLE_REFRESH_TOKEN_GBP) {
    die('GOOGLE_REFRESH_TOKEN_GBP missing — run scripts/get_google_refresh_token.py first');
  }

  const body = new URLSearchParams({
    client_id: GOOGLE_CLIENT_ID,
    client_secret: GOOGLE_CLIENT_SECRET,
    refresh_token: GOOGLE_REFRESH_TOKEN_GBP,
    grant_type: 'refresh_token',
  });
  const resp = await fetch(TOKEN_ENDPOINT, {
    method: 'POST',
    headers: { 'content-type': 'application/x-www-form-urlencoded' },
    body,
  });
  if (!resp.ok) {
    const text = await resp.text();
    if (text.includes('invalid_grant')) {
      die(
        'OAuth invalid_grant — Testing-status app refresh tokens expire after 7 days. ' +
        'Re-run scripts/get_google_refresh_token.py, then re-run this script.'
      );
    }
    die(`OAuth token refresh failed: HTTP ${resp.status} body-len=${text.length}`);
  }
  const payload = await resp.json();
  return payload.access_token;
}

// ── GBP Reviews API ──────────────────────────────────────────────────────────

async function fetchAllReviews(accessToken, accountId, locationId) {
  const reviews = [];
  let pageToken = null;
  let page = 0;
  do {
    page += 1;
    const url = new URL(`${REVIEWS_API_BASE}/${accountId}/${locationId}/reviews`);
    url.searchParams.set('pageSize', '50');
    if (pageToken) url.searchParams.set('pageToken', pageToken);
    const resp = await fetch(url, {
      headers: { Authorization: `Bearer ${accessToken}`, Accept: 'application/json' },
    });
    if (!resp.ok) {
      const text = await resp.text();
      die(`GBP reviews list failed: HTTP ${resp.status} — ${text.slice(0, 400)}`);
    }
    const data = await resp.json();
    const batch = Array.isArray(data.reviews) ? data.reviews : [];
    reviews.push(...batch);
    log(`page ${page}: fetched ${batch.length} reviews (total so far: ${reviews.length})`);
    pageToken = data.nextPageToken || null;
    // Cap at 40 pages = 2000 reviews (yoga teacher will never hit this).
    if (page > 40) {
      warn('hit 40-page cap — stopping to avoid runaway loop');
      break;
    }
  } while (pageToken);
  return reviews;
}

// ── Language detection (regex first-pass; enough for FR vs EN) ──────────────

function detectLang(text) {
  if (!text) return 'fr';
  // Very rough — count FR-specific characters + common FR stopwords.
  const frMarkers = /(à|é|è|ê|ù|ç|ô|î|û|ï|ü|œ|æ)|\b(le|la|les|un|une|des|est|avec|pour|dans|mais|très|bien|merci|super)\b/gi;
  const matches = text.match(frMarkers) || [];
  return matches.length >= 2 ? 'fr' : 'en';
}

// ── KV shape ─────────────────────────────────────────────────────────────────

function reviewToKvRecord(review) {
  const reviewId = review.reviewId || '';
  const createTime = review.createTime || new Date().toISOString();
  const rating = RATING_MAP[review.starRating] || null;
  const name = review.reviewer?.displayName?.slice(0, 60) || 'Google reviewer';
  const body = (review.comment || '').slice(0, 2000);
  const lang = detectLang(body);
  return {
    id: reviewId, // stable across pulls — this is Google's own id
    name,
    rating,
    body,
    body_fr: null,
    body_en: null,
    source: 'google',
    source_url: null, // GBP API does not expose the public reviews-page URL per review
    lang,
    submitted_at: createTime,
    approved_at: new Date().toISOString(),
    featured: false,
    verified: true,
    google_reviewer_photo: review.reviewer?.profilePhotoUrl || null,
    google_update_time: review.updateTime || null,
  };
}

function reviewToKvKey(review) {
  const createTime = review.createTime || new Date().toISOString();
  const idShort = (review.reviewId || 'unknown').slice(0, 8);
  return `${KV_KEY_PREFIX}${createTime}:${idShort}`;
}

// ── Wrangler shell-out ───────────────────────────────────────────────────────

function runWrangler(args) {
  return new Promise((resolveOk, rejectFail) => {
    const proc = spawn('npx', ['wrangler', ...args], {
      cwd: CRON_WORKER_ROOT,
      // shell:true on Windows so `npx.cmd` resolves; on POSIX this is a no-op.
      shell: process.platform === 'win32',
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
    // Some wrangler versions emit newline-separated names. Fall back to that.
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
  } catch (err) {
    // Missing keys return non-zero on some wrangler versions; treat as null.
    return null;
  }
}

async function kvPut(key, value) {
  // Write value via stdin equivalent: wrangler kv key put supports positional
  // <VALUE> but that would blow through shell arg limits on long bodies.
  // Use --path with a temp file.
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
    // Best-effort cleanup; leaving a temp file behind isn't fatal.
    try { await (await import('node:fs/promises')).unlink(tmpValuePath); } catch {}
  }
}

async function kvDelete(key) {
  await runWrangler([
    'kv', 'key', 'delete',
    '--binding=DASHBOARD_KV', '--remote',
    key,
  ]);
}

// ── Backfill: delete silent-now-bug records ─────────────────────────────────

async function deleteBugFingerprintRecords() {
  log('backfill: listing all approved reviews...');
  const keys = await kvList(KV_KEY_PREFIX);
  const deletions = [];
  for (const key of keys) {
    const raw = await kvGet(key);
    if (!raw) continue;
    let rec;
    try { rec = JSON.parse(raw); } catch { continue; }
    const sub = Date.parse(rec.submitted_at || '');
    const app = Date.parse(rec.approved_at || '');
    if (Number.isFinite(sub) && Number.isFinite(app) && Math.abs(sub - app) <= BUG_FINGERPRINT_MS) {
      deletions.push({ key, name: rec.name, submitted_at: rec.submitted_at, approved_at: rec.approved_at });
    }
  }
  log(`backfill: found ${deletions.length} silent-now-bug records to delete`);
  if (DRY_RUN) {
    for (const d of deletions) log(`  DRY-RUN delete: ${d.key} (${d.name})`);
    return deletions;
  }
  for (const d of deletions) {
    await kvDelete(d.key);
    log(`  deleted: ${d.key} (${d.name})`);
  }
  return deletions;
}

// ── Upsert loop with local-edit preservation ────────────────────────────────

async function upsertReviews(reviews) {
  const decisions = [];
  for (const review of reviews) {
    const key = reviewToKvKey(review);
    const record = reviewToKvRecord(review);
    // Check for local edits — if the local record has edited_at newer than
    // Google's updateTime, preserve the local body/rating/etc.
    let existing = null;
    if (!DRY_RUN) {
      const raw = await kvGet(key);
      if (raw) {
        try { existing = JSON.parse(raw); } catch {}
      }
    }
    let decision = 'upsert';
    if (existing?.edited_at && review.updateTime) {
      const localEdit = Date.parse(existing.edited_at);
      const googleUpdate = Date.parse(review.updateTime);
      if (Number.isFinite(localEdit) && Number.isFinite(googleUpdate) && localEdit > googleUpdate) {
        decision = 'skip_local_edit_newer';
      }
    } else if (existing && JSON.stringify(existing) === JSON.stringify(record)) {
      decision = 'unchanged';
    }

    decisions.push({
      key,
      decision,
      name: record.name,
      rating: record.rating,
      submitted_at: record.submitted_at,
    });

    if (DRY_RUN) {
      log(`  DRY-RUN ${decision}: ${key} (${record.name}, ${record.rating}★, ${record.submitted_at})`);
      continue;
    }
    if (decision === 'unchanged' || decision === 'skip_local_edit_newer') {
      log(`  ${decision}: ${key}`);
      continue;
    }
    await kvPut(key, JSON.stringify(record));
    log(`  upsert: ${key} (${record.name})`);
  }
  return decisions;
}

// ── Discover-ids mode (helper for first-time setup) ─────────────────────────

async function discoverIds(accessToken) {
  log('discover: listing GBP accounts...');
  const accResp = await fetch('https://mybusinessaccountmanagement.googleapis.com/v1/accounts', {
    headers: { Authorization: `Bearer ${accessToken}`, Accept: 'application/json' },
  });
  if (!accResp.ok) {
    const text = await accResp.text();
    die(`accounts list failed: HTTP ${accResp.status} — ${text.slice(0, 400)}`);
  }
  const accData = await accResp.json();
  const accounts = accData.accounts || [];
  if (accounts.length === 0) {
    die('no GBP accounts found under this OAuth token. Confirm the token was issued for an account that has Google Business Profile access.');
  }
  log(`discover: found ${accounts.length} account(s)`);
  console.log();
  for (const acc of accounts) {
    console.log(`ACCOUNT: ${acc.name}  (${acc.accountName || acc.type || 'unnamed'})`);
    // List locations under each account. New endpoint requires readMask.
    const locUrl = new URL(`https://mybusinessbusinessinformation.googleapis.com/v1/${acc.name}/locations`);
    locUrl.searchParams.set('readMask', 'name,title,storeCode,storefrontAddress');
    locUrl.searchParams.set('pageSize', '100');
    const locResp = await fetch(locUrl, {
      headers: { Authorization: `Bearer ${accessToken}`, Accept: 'application/json' },
    });
    if (!locResp.ok) {
      const text = await locResp.text();
      console.log(`  (locations list failed: HTTP ${locResp.status} — ${text.slice(0, 200)})`);
      continue;
    }
    const locData = await locResp.json();
    const locations = locData.locations || [];
    if (locations.length === 0) {
      console.log('  (no locations under this account)');
      continue;
    }
    for (const loc of locations) {
      const addr = loc.storefrontAddress
        ? [loc.storefrontAddress.addressLines?.join(', '), loc.storefrontAddress.locality, loc.storefrontAddress.regionCode].filter(Boolean).join(', ')
        : '(no address)';
      console.log(`  LOCATION: ${loc.name}  "${loc.title || loc.storeCode || 'unnamed'}"  — ${addr}`);
    }
  }
  console.log();
  console.log('Add the account.name and location.name of the yoga-jitendra profile to .env:');
  console.log('    GBP_ACCOUNT_ID=accounts/<from-above>');
  console.log('    GBP_LOCATION_ID=locations/<from-above>');
  console.log('Then also set GBP_LOCATION_ID in execution/infrastructure/yoga_jitendra_cron/wrangler.toml');
  console.log('and re-deploy the cron with `npx wrangler deploy` so the Maps tile stops being degraded.');
}

// ── Main ─────────────────────────────────────────────────────────────────────

async function main() {
  await loadEnv();

  // Discover-ids does not need account/location env vars — it's the tool
  // that finds them for you.
  if (DISCOVER_IDS) {
    const accessToken = await getAccessToken();
    log('OAuth: got access token');
    await discoverIds(accessToken);
    return;
  }

  const { GBP_ACCOUNT_ID, GBP_LOCATION_ID } = process.env;
  if (!GBP_ACCOUNT_ID) die('GBP_ACCOUNT_ID missing from .env (e.g. accounts/123456789). Run with --discover-ids to find it.');
  if (!GBP_LOCATION_ID) die('GBP_LOCATION_ID missing from .env (e.g. locations/987654321). Run with --discover-ids to find it.');

  log(`mode: ${DRY_RUN ? 'DRY-RUN' : 'LIVE'}${BACKFILL ? ' + backfill' : ''}`);
  log(`account=${GBP_ACCOUNT_ID} location=${GBP_LOCATION_ID}`);

  const accessToken = await getAccessToken();
  log('OAuth: got access token');

  let deleted = [];
  if (BACKFILL) {
    deleted = await deleteBugFingerprintRecords();
  }

  const reviews = await fetchAllReviews(accessToken, GBP_ACCOUNT_ID, GBP_LOCATION_ID);
  log(`total reviews fetched from Google: ${reviews.length}`);

  const decisions = await upsertReviews(reviews);

  const summary = {
    ts: new Date().toISOString(),
    mode: DRY_RUN ? 'dry-run' : 'live',
    backfill: BACKFILL,
    account_id: GBP_ACCOUNT_ID,
    location_id: GBP_LOCATION_ID,
    fetched: reviews.length,
    deleted_bug_records: deleted.length,
    counts: decisions.reduce((acc, d) => {
      acc[d.decision] = (acc[d.decision] || 0) + 1;
      return acc;
    }, {}),
    decisions,
    deleted,
  };
  await mkdir(TMP_DIR, { recursive: true });
  const logPath = resolve(TMP_DIR, `${new Date().toISOString().replace(/[:.]/g, '-')}.jsonl`);
  await writeFile(logPath, JSON.stringify(summary, null, 2) + '\n', 'utf8');
  log(`wrote run log to ${logPath}`);
  log(`summary: ${JSON.stringify(summary.counts)} (deleted bug records: ${summary.deleted_bug_records})`);
}

main().catch((err) => {
  process.stderr.write(`[gbp-sync] FATAL: ${err?.stack || err?.message || err}\n`);
  process.exit(1);
});
