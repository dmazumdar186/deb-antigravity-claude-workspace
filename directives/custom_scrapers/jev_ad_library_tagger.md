# Jev Ad Library Tagger — competitor ad swipe file

## Purpose

The Meta Ad Library shows every ad a competitor runs, but nobody reads hundreds by hand.
This directive turns an Ad Library export into a tagged swipe file: for each ad, Jev
(TypeSafe's typed-decision model via OpenRouter, see `directives/infrastructure/jev.md`)
reads the text and tags **format, call to action, funnel stage, hook strength, has-offer**
in ONE call per ad. Everything lands in a JSON + CSV (and optionally a Google Sheet) so the
operator can see what is working in a market. Reference run: 54 ads from 3 brands tagged in
~1.5 s for under a cent.

Operator prompt: **"Tag competitor ads from the Meta Ad Library for <brands>"**.

## When to invoke

- Operator names brands / a niche and wants to know what ad angles competitors run.
- Before an `/ad-creative` batch, to ground the brief in live market patterns.
- Refreshing a swipe-file Sheet (re-run on a newer export; rows append).

## Inputs

- `--input PATH`: `json|csv` — ad export. Accepted shapes:
  - Apify `apify/facebook-ads-scraper` items (`page_name`, `snapshot.body.text`,
    `snapshot.title`, `snapshot.cta_text`, `snapshot.link_url`, `snapshot.display_format`,
    `start_date`, `publisher_platform`).
  - Flat rows: `{id, brand|page_name, body|text, headline?, cta?, link?, media_type?,
    start_date?, platforms?}` (CSV uses the same column names).
- `--fetch-apify "<search terms or page url>"`: alternative to `--input`. Needs env
  `APIFY_API_TOKEN`; runs the actor via `run-sync-get-dataset-items` and saves raw items to
  `.tmp/ad_library_raw.json`. Missing token → exit 2 with a one-line message.
- `--min-confidence F` (0.55), `--limit N`, `--workers N` (8), `--dry-run` (no network).
- `--sheet-id ID --tab Ads`: append rows via gspread (`execution/google/google_sheets_writer.get_client()`,
  env `GOOGLE_SERVICE_ACCOUNT_PATH`); missing creds or gspread → skipped with a message.
- env `OPENROUTER_API_KEY` (also `OPENROUTER_API_TOKEN` / `OPENROUTER_API_TOEKN`).

### Getting an export

1. **Apify (recommended):** `python3 execution/custom_scrapers/jev_ad_library_tagger.py --fetch-apify "https://www.facebook.com/ads/library/?q=<brand>" --limit 60`
   or pass search terms. Pay-per-result actor; ~100 ads is cents.
2. **Manual:** open the Ad Library, run the Apify actor from the console and download the
   dataset as JSON, or hand-build a flat JSON list (`.tmp/jev_ads_sample.json` is a sample).

## Outputs

- `--output PATH` (default `<input>.tagged.json`): list of ads with `tags`, `confidence`,
  `min_confidence`, `low_confidence`, `jev_error`, `cost_usd`.
- `--csv-out PATH` (default `<output>.csv`): swipe file — `brand, headline, body_preview`
  (160 chars), the five tags + confidences, `low_confidence`, `media_type, cta, start_date,
  platforms, link`.
- Optional Sheet rows (header written on an empty tab).
- stdout summary: ads tagged, per-brand counts, format / cta / funnel distribution,
  with-offer count, low-confidence count, cost USD, wall time.
- `.tmp/jev_ledger.jsonl` row, `caller: jev_ad_library_tagger`.

## Tags (one Jev call per ad)

| tag | type | values |
|---|---|---|
| `format` | choice | ugc_testimonial, product_demo, founder_talking_head, static_offer, carousel_listicle, meme_humor, educational, other |
| `cta_type` | choice | shop_now, sign_up, learn_more, book_call, download, message_us, none |
| `funnel_stage` | choice | awareness, consideration, conversion, retention |
| `hook_strength` | score 0-3 | no hook → weak → solid → stops the scroll |
| `has_offer` | noul (bool) | explicit discount/price/bonus vs none |

## Exit Criteria

- `<output>.tagged.json` and the CSV exist; CSV row count == number of ads with text.
- Every row has all five tags; `jev_errors == 0` (otherwise rerun — Jev fails open).
- `low_confidence` share < 25 % of rows; rows above that are listed for a human skim.
- Summary printed and ledger row appended; cost is under $0.01 per 100 ads.

## Scripts (Layer 3)

- `execution/custom_scrapers/jev_ad_library_tagger.py`
- `execution/modules/jev_client.py` (shared client)
- `tests/test_jev_ad_library_tagger.py` (offline)

## Edge cases

- Ads with no body AND no headline (image-only) are dropped before tagging.
- Carousel items: card bodies are joined with ` | ` when `snapshot.body.text` is empty.
- `hook_strength` is a 4-level score, so its confidence is spread across levels and usually
  sits at 0.3-0.7; it is the tag that most often trips `low_confidence`. Raise
  `--min-confidence` only if you want a stricter swipe file, not because of this tag alone.
- `has_offer` is a noul; its "confidence" is `|p-0.5|*2` and is NOT part of `min_confidence`.
- Jev context is 32k tokens; bodies are cut at 6,000 chars.
- Jev HTTP/timeouts return empty answers (`jev_error` set, `low_confidence: true`); exit 1
  only if every ad failed.
- Apify `run-sync` caps at 300 s; for >200 ads run the actor async in the console and use `--input`.
- Sheet append is best-effort: `ValueError`/`FileNotFoundError` from `get_client()` or a missing
  `gspread` import prints a skip line and the run still succeeds.

## Changelog

- 2026-10-06: Created (use case 3 of the Jev rollout). Live check: 6 synthetic ads / 2 brands,
  one call per ad, all five tags returned, sub-cent cost.
