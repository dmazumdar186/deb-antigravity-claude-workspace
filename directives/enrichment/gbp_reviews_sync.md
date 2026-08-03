# GBP Reviews Sync

## Prior art pass

- **Public API exists?** YES. Google's Business Profile Performance API family exposes reviews via `mybusiness.v4.accounts.locations.reviews.list` (OAuth, scope `https://www.googleapis.com/auth/business.manage`). `createTime` is preserved forever on each review resource — the original review date is authoritative and re-fetchable at any time.
- **Best existing open-source approach:** most FR/EN yoga/local-business site templates re-type Google reviews by hand (same failure mode as V0.01 of this project). The right approach is direct API pull; no need for a wrapper library. Anthropic-workspace convention (`execution/enrichment/*`) covers the pattern.
- **Why we should not crib a lib:** the API surface for our use case is a single GET-with-paging + one KV upsert loop. Adding a dep for ~60 lines of code is unwarranted.
- **Recommended architecture:** `scripts/pull_gbp_reviews.mjs` (Node ESM, no deps beyond `googleapis`-style raw fetch) that (1) uses the existing GBP refresh token from `.env` to mint an access token, (2) pages through `.../reviews`, (3) upserts each review into KV under `review:approved:<createTime>:<reviewId>` shape used by the current pipeline, (4) writes a run report to `.tmp/gbp_reviews_sync/`. Optional flag `--dry-run` prints diffs without writing.

## Why this exists

The 2026-08-03 incident review found that the reviews page's "date" field was NOT synced from Google — it was manually re-typed via the moderation UI, and the `submitted_at` field silently defaulted to `now()` when the moderator left the date input blank. Every historical Google review (April 2025 Franck, January 2025 Xavier, August 2025 Tapovan, etc.) was mis-stamped as a July 2026 review on the customer-facing page.

Server-side fix (commit 5da525b) blocks the silent-now default going forward — but existing bad KV records need to be either re-entered by hand OR overwritten with the authoritative Google-side timestamps. This directive is the "overwrite from Google" path.

## Goals

1. Recover the true `createTime` for every Google review the location has ever received.
2. Keep them in sync going forward (daily cron pull).
3. Never overwrite a review with a modified `updateTime` that a moderator has edited locally (last-write-wins would erase local edits — check `edited_at`).

## Inputs

- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` — same OAuth app used by the dashboard cron (per `scripts/get_google_refresh_token.py`).
- `GOOGLE_REFRESH_TOKEN_GBP` — already in `wrangler secret` on the cron Worker; local script reads from `.env`.
- `GBP_ACCOUNT_ID` — the operator's GBP account ID (e.g. `accounts/123456789`).
- `GBP_LOCATION_ID` — the yoga-jitendra location resource name (e.g. `locations/987654321`).
- `--dry-run` (optional flag) — print planned upserts / deletes without writing.
- `--backfill` (optional flag) — one-shot: also delete every KV `review:approved:*` whose `submitted_at === approved_at` to the second (the fingerprint of the silent-now bug) before writing the pulled reviews.

## Outputs

- KV `review:approved:<ISO-createTime>:<8-char-id>` — one key per review, JSON body matching the existing schema (id, name, rating, body, source: "google", source_url, lang, submitted_at, approved_at, featured=false, verified=true).
- `.tmp/gbp_reviews_sync/YYYY-MM-DD_HHMMSS.jsonl` — run log with per-review upsert / skip / delete decisions.
- stdout: summary counts (`pulled: N, upserted: N, unchanged: N, deleted: N`).

## Tool

- `execution/personal_workflows/yoga_jitendra_site/scripts/pull_gbp_reviews.mjs`

## Steps

1. **Bootstrap OAuth**: use `scripts/get_google_refresh_token.py` (already exists) to obtain the GBP refresh token. Confirm it has scope `https://www.googleapis.com/auth/business.manage` (script defaults to this — no change needed).
2. **Discover account + location IDs** (one-time): run `gcloud alpha businessprofile locations list` OR the manual API call `GET https://mybusinessaccountmanagement.googleapis.com/v1/accounts` → pick the account holding yoga-jitendra → `GET .../accounts/{acct}/locations` → pick location.
3. **Pull reviews**: `GET https://mybusiness.googleapis.com/v4/{account}/{location}/reviews?pageSize=50` — paginate via `nextPageToken` until exhausted.
4. **Upsert into KV**: for each review, compute the target key and JSON body. Read the existing key (if any) via `wrangler kv key get`. If the local body has `edited_at > review.updateTime`, skip (preserve local edit). Otherwise `wrangler kv key put`.
5. **Backfill mode**: before the upsert loop, list all `review:approved:*`, parse each, delete the ones whose `submitted_at === approved_at` (± 1s) — these are the silent-now bug records that Google's pull will replace.
6. **Report**: write per-record decision to `.tmp/gbp_reviews_sync/*.jsonl` + print aggregate summary.

## Edge cases

- **Location not verified on GBP**: API returns empty. Script exits 0 with a warning; nothing to sync.
- **Refresh token expired** (Testing-status OAuth app 7-day expiry — see `~/.claude/rules/live-artifact-acceptance.md`): API 401. Script exits with clear error naming the fix (`re-run scripts/get_google_refresh_token.py`).
- **Concurrent moderator edits**: check `edited_at` in the local body before overwriting. If present and newer than Google's `updateTime`, skip with an informational log line.
- **Deleted-from-Google review**: this directive does NOT auto-delete local records that no longer exist on Google. Reviews can disappear (spam removal, user account deletion) and the operator may want to retain the local record. Delete manually via the moderation UI if needed.
- **Rating fields**: Google returns `starRating: "FIVE" | "FOUR" | "THREE" | "TWO" | "ONE"`. Map to integer 1-5.
- **Body / language**: Google returns `comment` in the reviewer's language. Store as `body`, set `lang: "fr"` for French-detected, `"en"` otherwise (use simple regex first-pass; if the operator complains about mis-detection, add a proper langdetect step).

## Rollback

- Delete the pulled KV keys: `wrangler kv key list --prefix review:approved:<review-createTime-prefix>` → `wrangler kv key delete <key>` per row.
- The moderation UI still accepts manual imports, so worst case the operator re-types the reviews.

## Cost

- Free. GBP API has generous free-tier quotas (5 QPS, 10k QPD per project). This sync uses ~10 requests per full pull.
- Local script only — no additional Cloudflare Worker or KV storage cost beyond what already exists.

## Exit criteria (per `~/.claude/rules/live-artifact-acceptance.md`)

- One dry-run against production KV surfaces per-review upsert plan without writing.
- One real backfill run recovers all historical review dates visible on Google's public reviews page.
- Reviews page renders the recovered dates matching what Google shows publicly.
- Acceptance test: `tests/acceptance_dashboard.py` still PASS (no regression on the review-date guard).
