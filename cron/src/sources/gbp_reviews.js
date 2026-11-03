// GBP Reviews sync source — daily forward-sync of Google Business Profile
// reviews into the shared DASHBOARD_KV `review:approved:*` records that the
// public site reads (Pages Function /api/reviews-public + client-side append
// in ReviewsGrid.astro, so new reviews surface WITHOUT a site rebuild).
//
// Cloud port of scripts/pull_gbp_reviews.mjs (yoga_jitendra_site). The three
// hard-won invariants from that script's 2026-09-01 first-run audit carry
// over verbatim — breaking any of them re-introduces a shipped bug class:
//
//   1. Dedup is by CONTENT equivalence, never by KV key. Records created via
//      the moderation UI live under UUID keys; key-only matching would insert
//      every moderated Google review a second time (duplicate reviews on the
//      public page).
//   2. Same-key re-pulls preserve moderator-owned fields (approved_at,
//      featured, body_fr/en, source_url) so a daily run is a no-op, not a
//      daily churn of approved_at.
//   3. A local edit newer than Google's updateTime wins (skip, don't clobber).
//
// Endpoint: GET https://mybusiness.googleapis.com/v4/{account}/{location}/reviews
// (legacy v4 API — the operator enabled "Google My Business API" on the
// yoga-jitendra-dashboard Cloud project 2026-09-01; verified working same day.)
// Auth: Bearer token from oauth.js scope=gbp.

import { getAccessToken } from "../oauth.js";

const REVIEWS_API_BASE = "https://mybusiness.googleapis.com/v4";
const KV_KEY_PREFIX = "review:approved:";
const RATING_MAP = { ONE: 1, TWO: 2, THREE: 3, FOUR: 4, FIVE: 5 };
const EQUIV_WINDOW_MS = 2000;
const PAGE_CAP = 40; // 40 pages x 50 = 2000 reviews; runaway-loop backstop

function detectLang(text) {
  if (!text) return "fr";
  const frMarkers = /(à|é|è|ê|ù|ç|ô|î|û|ï|ü|œ|æ)|\b(le|la|les|un|une|des|est|avec|pour|dans|mais|très|bien|merci|super)\b/gi;
  const matches = text.match(frMarkers) || [];
  return matches.length >= 2 ? "fr" : "en";
}

function firstToken(name) {
  return String(name || "").trim().split(/\s+/)[0].toLowerCase();
}

function isEquivalent(rec, record) {
  const a = Date.parse(rec.submitted_at || "");
  const b = Date.parse(record.submitted_at || "");
  if (!Number.isFinite(a) || !Number.isFinite(b) || Math.abs(a - b) > EQUIV_WINDOW_MS) return false;
  if ((rec.rating ?? null) !== (record.rating ?? null)) return false;
  return firstToken(rec.name) === firstToken(record.name);
}

function reviewToKvRecord(review, nowIso) {
  const body = (review.comment || "").slice(0, 2000);
  return {
    id: review.reviewId || "",
    name: review.reviewer?.displayName?.slice(0, 60) || "Google reviewer",
    rating: RATING_MAP[review.starRating] || null,
    body,
    body_fr: null,
    body_en: null,
    source: "google",
    source_url: null,
    lang: detectLang(body),
    submitted_at: review.createTime || nowIso,
    approved_at: nowIso,
    featured: false,
    verified: true,
    google_reviewer_photo: review.reviewer?.profilePhotoUrl || null,
    google_update_time: review.updateTime || null,
  };
}

function reviewToKvKey(review, nowIso) {
  const createTime = review.createTime || nowIso;
  const idShort = (review.reviewId || "unknown").slice(0, 8);
  return `${KV_KEY_PREFIX}${createTime}:${idShort}`;
}

async function fetchAllGoogleReviews(env, accessToken) {
  const account = env.GBP_ACCOUNT_ID.startsWith("accounts/")
    ? env.GBP_ACCOUNT_ID
    : `accounts/${env.GBP_ACCOUNT_ID}`;
  const location = env.GBP_LOCATION_ID.startsWith("locations/")
    ? env.GBP_LOCATION_ID
    : `locations/${env.GBP_LOCATION_ID}`;

  const reviews = [];
  let pageToken = null;
  let page = 0;
  do {
    page += 1;
    const params = new URLSearchParams({ pageSize: "50" });
    if (pageToken) params.set("pageToken", pageToken);
    const url = `${REVIEWS_API_BASE}/${account}/${location}/reviews?${params.toString()}`;
    const resp = await fetch(url, { headers: { Authorization: `Bearer ${accessToken}` } });
    if (!resp.ok) {
      const text = await resp.text();
      console.error(`gbp_reviews list failed: status=${resp.status} body_len=${text.length}`);
      throw new Error(`gbp_reviews list failed: ${resp.status}`);
    }
    const data = await resp.json();
    reviews.push(...(Array.isArray(data.reviews) ? data.reviews : []));
    pageToken = data.nextPageToken || null;
  } while (pageToken && page < PAGE_CAP);
  return reviews;
}

async function loadAllExistingRecords(env) {
  const out = [];
  let cursor = undefined;
  do {
    const res = await env.DASHBOARD_KV.list({ prefix: KV_KEY_PREFIX, cursor });
    for (const k of res.keys) {
      const rec = await env.DASHBOARD_KV.get(k.name, { type: "json" });
      if (rec) out.push({ key: k.name, rec });
    }
    cursor = res.list_complete ? undefined : res.cursor;
  } while (cursor);
  return out;
}

export async function fetchGbpReviews(env, dateStr) {
  if (!env.GBP_ACCOUNT_ID) {
    throw new Error("GBP_ACCOUNT_ID empty — set it in wrangler.toml [vars]");
  }
  if (!env.GBP_LOCATION_ID) {
    throw new Error("GBP_LOCATION_ID empty — set it in wrangler.toml [vars]");
  }
  if (!env.GOOGLE_REFRESH_TOKEN_GBP) {
    throw new Error("GOOGLE_REFRESH_TOKEN_GBP not set — run scripts/get_google_refresh_token.py");
  }

  const nowIso = new Date().toISOString();
  const accessToken = await getAccessToken(env, "gbp");
  const googleReviews = await fetchAllGoogleReviews(env, accessToken);
  const existingAll = await loadAllExistingRecords(env);

  let inserted = 0;
  let updated = 0;
  let skippedEquivalent = 0;
  let skippedLocalEdit = 0;
  let unchanged = 0;
  const newNames = [];

  for (const review of googleReviews) {
    const key = reviewToKvKey(review, nowIso);
    const record = reviewToKvRecord(review, nowIso);
    const exact = existingAll.find((e) => e.key === key) || null;
    const equivalent = exact ? null : existingAll.find((e) => isEquivalent(e.rec, record)) || null;

    if (equivalent) {
      skippedEquivalent += 1;
      continue;
    }
    if (exact) {
      const existing = exact.rec;
      if (existing.approved_at) record.approved_at = existing.approved_at;
      record.featured = existing.featured ?? record.featured;
      if (existing.body_fr) record.body_fr = existing.body_fr;
      if (existing.body_en) record.body_en = existing.body_en;
      if (existing.source_url) record.source_url = existing.source_url;
      if (existing.edited_at && review.updateTime) {
        const localEdit = Date.parse(existing.edited_at);
        const googleUpdate = Date.parse(review.updateTime);
        if (Number.isFinite(localEdit) && Number.isFinite(googleUpdate) && localEdit > googleUpdate) {
          skippedLocalEdit += 1;
          continue;
        }
      }
      if (JSON.stringify(existing) === JSON.stringify(record)) {
        unchanged += 1;
        continue;
      }
      await env.DASHBOARD_KV.put(key, JSON.stringify(record));
      updated += 1;
      continue;
    }
    await env.DASHBOARD_KV.put(key, JSON.stringify(record));
    inserted += 1;
    newNames.push(record.name);
    // Keep the in-memory index current so two Google records in the same
    // batch can never both insert as "new" copies of each other.
    existingAll.push({ key, rec: record });
  }

  return {
    date: dateStr,
    google_review_count: googleReviews.length,
    existing_record_count: existingAll.length - inserted,
    inserted,
    updated,
    unchanged,
    skipped_equivalent: skippedEquivalent,
    skipped_local_edit_newer: skippedLocalEdit,
    new_review_names: newNames,
  };
}
