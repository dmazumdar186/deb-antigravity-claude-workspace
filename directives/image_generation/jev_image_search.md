# Jev Image Search (search images by what is in them)

## Purpose

Searching generated images by file name barely works (`img_001.png` says nothing). This indexes
written words about each image (its metadata: the prompt you generated it with, or a cheap
caption) and lets Jev (TypeSafe, via OpenRouter Decisions API) pick the images that are actually
about the query. Typing "claude" finds the Claude images even when no filename contains it.
RoboNuggets "19 Jev use cases", #14.

## When to invoke

Operator copy-paste prompts:

```
Index my images in <dir> (directives/image_generation/jev_image_search.md).
Find images about <topic> in <dir>.
```

## Inputs

- `index --dir path [--recursive] [--caption | --caption-all] [--caption-limit 50]`
- `search --dir path --query "..." [--top 8] [--json] [--html results.html] [--filename-only]`
- env `OPENROUTER_API_KEY` (also `OPENROUTER_API_TOKEN` / `OPENROUTER_API_TOEKN`).

## Metadata sources (first hit wins)

| # | Source | Example |
|---|--------|---------|
| 1 | Sidecar next to the image | `img_001.txt` / `.json` (`prompt`/`caption`/`description` key) / `.md` |
| 2 | Prompt log in the image's folder, keyed by filename | `prompts.jsonl`, `prompt_log.jsonl` (`{"file": ..., "prompt": ...}`), `metadata.json` (`{"img.png": "..."}` or list) |
| 3 | PNG text chunks | `prompt`, `parameters` (A1111/Comfy), `Description`, `Comment`, `Title` |
| 4 | EXIF | ImageDescription, UserComment |
| 5 | Filename split into words | `claude_banner.png` -> "claude banner" |
| 6 | Caption (`--caption`, only where 1-4 found nothing; `--caption-all` re-captions everything) | Gemini 2.5 Flash Lite one-sentence description |

Logging the prompt for every generated image is the best metadata; captioning is the fallback.

## Process

1. `index`: walk png/jpg/jpeg/webp/gif (videos and dot-dirs skipped; every path must resolve
   under `--dir`, symlinks escaping it are skipped). Writes `<dir>/.jev_image_index.json`
   (path, size, dims, mtime, metadata, source). Incremental: unchanged mtime+size are reused.
2. Caption: OpenRouter chat completions, `google/gemini-2.5-flash-lite`, image downscaled to
   512 px JPEG data URL, `max_tokens` 80, 30 s timeout, capped by `--caption-limit`. Cost read
   from response `usage.cost`. Failures are listed and the image keeps its filename metadata.
3. `search`: stage 1 batches of <= 25 (`choice` over 160-char metadata + `none`, `noul`
   abstain < 0.2), keeping the pick plus any option >= 35% of its probability (several images
   can match per batch, unlike jev_find); stage 2 one `choice` over winners (300-char
   metadata). `--filename-only` is the substring baseline; the summary prints
   "filename matches: N vs Jev matches: M". `--html` writes a contact sheet with relative
   `<img>` tags (no CDN).

## Outputs

Index JSON; ranked hits (path, p, source, metadata snippet); optional HTML; ledger row in
`.tmp/jev_ledger.jsonl` (caller `jev_image_search`, op `search`/`caption`).

## Cost

- Search: ~1 Jev call per 25 images + 1; 11 images = 2 calls, ~$0.00005.
- Captioning: ~$0.00014/image measured (2 images = $0.000285), i.e. ~1,000 images for about
  15-50 cents depending on image size. Only caption what has no prompt.

## Edge cases

- Fails open: no key or Jev errors -> empty hits plus error count; caption errors never abort.
- Unreadable image -> indexed with an `error` field and filename metadata.
- Captions of text-only images describe the visible text (e.g. "HELLO CLAUDE"), so they match.

## Script

`execution/image_generation/jev_image_search.py`; tests `tests/test_jev_image_search.py`.

## Changelog

- 2026-10-07: Created (RoboNuggets #14). Stage 1 keeps multiple matches per batch (jev_find
  keeps one) after the live run returned only 1 of 4 Claude images with single-winner batches.
