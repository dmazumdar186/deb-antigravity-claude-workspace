# Jev Find (search by meaning)

## Purpose

Ctrl+F only finds the exact words you type. Jev Find takes roughly what you are looking for
and points at the right paragraph even when the words do not match. The page is split into
paragraph chunks, Jev (TypeSafe, via OpenRouter Decisions API) picks the best chunk per batch,
then ranks the batch winners. RoboNuggets "19 Jev use cases", #13. Fast enough to feel live.

## When to invoke

- "Find where <doc> talks about <idea>"
- "Search the directives for the thing about <idea>"
- Any fuzzy lookup in a long page, a URL or a folder of notes where grep needs the exact word.

Operator copy-paste prompts:

```
Find where <doc path or URL> talks about <idea> (directives/rag/jev_find.md).
Search the directives for the thing about <idea> with jev_find --dir directives --top 3.
```

## Inputs

- `--query "roughly what I'm looking for"` (required).
- One source: `--file path` (md / txt / html), `--url https://...` (GET, browser UA, 15 s
  timeout), or `--dir path --ext md[,txt,html]` (recursive; dot-dirs and node_modules skipped;
  every file must resolve under `--dir`).
- `--top 5`, `--workers 8`, `--json`, `--dry-run` (prints the chunk plan, zero calls).
- env `OPENROUTER_API_KEY` (also `OPENROUTER_API_TOKEN` / `OPENROUTER_API_TOEKN`).

## Process

1. Chunk: blank-line paragraphs; tiny ones merged to >= 40 words, long ones capped ~120 words;
   each chunk keeps `(file, line_start, line_end, heading)`. HTML is stripped with
   `html.parser` (script/style dropped, h1-h6 kept as headings). YAML front matter skipped.
2. Stage 1: batches of <= 25 chunks, ONE call per batch: a `choice` over chunk ids (160-char
   previews) + `none`, and a `noul` "does any option answer the query?" (< 0.2 = abstain).
   Batches run in parallel threads.
3. `--dir` mode keeps the best winner per file, then ranks globally.
4. Stage 2: the <= 25 winners go to one `choice` with full chunk text; top-k by probability.
5. The #1 hit gets one cheap sentence-level `choice`; that sentence is marked `>>`.

## Outputs

- Hits: `file:lines [heading] p=0.xx` + chunk text, or `--json` (`hits`, `summary`).
- Summary line: chunks, batches, calls, latency, cost, errors.
- Ledger row in `.tmp/jev_ledger.jsonl` (`caller: jev_find`).

## Exit Criteria (declarative)

- Every hit has a file, a valid line range and a probability; hits sorted by probability.
- `calls == batches + 2` at most; errors fail open (no hits, never a crash).

## Scripts (Layer 3)

- `execution/rag/jev_find.py` (CLI + importable `find(query, chunks, ...)`)
- `execution/rag/jev_find_demo.html` (single-file browser demo, same two-stage batching;
  key in `localStorage`, calls `https://openrouter.ai/api/alpha/decisions` directly)
- `execution/modules/jev_client.py` (shared client)
- `tests/test_jev_find.py` (offline, monkeypatched `decide`)

## Latency and cost (measured 2026-10-07)

- Single file (`directives/infrastructure/jev.md`, 10 chunks): 1 batch, 2 calls, 1.4 s,
  $0.00007. Found the `/jev off` for confidential work line.
- Whole `directives/` (109 files, 1,582 chunks): 64 batches, 66 calls, 6.3 s, $0.005.
- Rule of thumb: ~$0.003 per 1,000 chunks; wall time ~ batches / workers x 0.6 s + 1 s.

## Edge cases

- Stage-1 probability shown when stage 2 is skipped (a single winner) is choice prob x the
  batch `noul`, so it reads lower than a stage-2 probability.
- `--dir` returns at most one hit per file; fewer than `--top` hits means other batches abstained.
- If the thing does not exist (e.g. no dedicated rule), Jev returns the nearest passages;
  read the probability: < 0.5 means "nearest, not a match".
- Browser demo exposes the key to the page; use a low-limit OpenRouter key.

## Changelog

- 2026-10-07: created (use case #13). Two-stage batching, per-file best in `--dir` mode,
  sentence marker, browser demo.
