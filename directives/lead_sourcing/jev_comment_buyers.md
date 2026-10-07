# Jev Comment Buyers — find buyers in your comments

## Purpose
Sellers on social have buyers buried in their comments. Pull the comments with an Apify
scraper, have Jev tag each one (ready to buy, question, complaint...), and get a priority list
with the people ready to buy at the top plus the reply type each needs. (RoboNuggets "19 Jev use
cases", #7.)

## When to invoke
- Operator prompt: **"Find buyers in the comments of <post urls>"**.
- Any batch of TikTok / Instagram / YouTube comments that needs triage for sales follow-up.

## Inputs
- `--input PATH` — JSON list (or `{items: [...]}`) / CSV of comments, or
  `--fetch-apify ACTOR --post-urls url1,url2` (needs `APIFY_API_TOKEN`; exit 2 if missing).
- Supported shapes (auto-detected per row):
  - TikTok `clockworks/tiktok-comments-scraper`: `text`, `uniqueId`/`user.uniqueId`, `diggCount`, `createTimeISO`, `videoWebUrl`
  - Instagram `apify/instagram-comment-scraper`: `text`, `ownerUsername`, `likesCount`, `timestamp`, `postUrl`
  - YouTube `streamers/youtube-comments-scraper`: `comment`, `author`, `voteCount`, `publishedTimeText`, `pageUrl`
  - Flat: `{id, author, text, likes, url, post}`
- `--min-confidence 0.55`, `--limit N`, `--workers 8`, `--top 25`, `--dry-run`.
- Env `OPENROUTER_API_KEY` (or `OPENROUTER_API_TOKEN` / `OPENROUTER_API_TOEKN`).

### Getting an export
In the Apify console open the actor, paste the post URLs, run, then Export dataset → JSON and
pass the file to `--input`. Or let the script run it (`--fetch-apify`, run-sync REST; raw items
saved to `.tmp/comments_raw.json`).

## Outputs
- JSON ranked list (default `<input>.buyers.json`), `--csv-out`, `--md` priority list (top N:
  author, intent, temperature, objection, 140-char comment, link, suggested reply TYPE:
  "DM with checkout link", "answer price/availability", "answer question", "resolve complaint", "thank").
- Stdout summary: counts per intent, hot leads, review count, cost USD, wall time.
- Ledger row in `.tmp/jev_ledger.jsonl` (caller `jev_comment_buyers`).

## Questions (one Jev call per comment)
| name | type | values |
|---|---|---|
| intent | choice | ready_to_buy, price_or_availability_question, product_question, complaint, praise, spam_or_bot, other |
| buy_temperature | score (4 levels) | no purchase signal → explicitly asking how/where to buy |
| needs_reply | noul | a seller reply would move them forward vs no reply needed |
| objection | choice | price, shipping, trust, fit_or_size, none |

Code-side: `priority = temperature/3 × (1 + log1p(likes)/4)`, sorted descending. Hot lead =
temperature ≥ 0.66 and needs_reply ≥ 0.5. Review = Jev error or intent/objection confidence < min.

## Exit Criteria
- Every comment has an intent or a `jev_error`; ready-to-buy rows at the top; summary printed.

## Scripts (Layer 3)
- `execution/lead_sourcing/jev_comment_buyers.py`
- Tests: `tests/test_jev_comment_buyers.py`

## Edge cases
- Jev fails open: errored rows get priority 0 and `review: true`.
- Complaints with high temperature can be hot leads — resolve them first, they are near-buyers.
- Comments with empty text are dropped before scoring.
- Apify actor inputs differ: TikTok `postURLs`, YouTube `startUrls`, Instagram `directUrls`.
- Reply text is never generated — only the reply type; the operator writes the reply.

## Changelog
- 2026-10-07: Created. Live run on 12 synthetic TikTok comments: 12/12 intents correct,
  5 hot leads (3 buyers + 2 price questions), cost $0.0004, 1.4 s.
