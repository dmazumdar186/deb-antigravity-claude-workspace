# Jev Backlinks

## Purpose

Link pages to each other without paying an LLM to read them. Works for a website's
content folder (navigation + SEO internal links) and for a second brain (a big folder of
notes) so agents can follow links between related notes. A deterministic Jaccard shortlist
keeps each Jev menu small; Jev (TypeSafe, via OpenRouter Decisions API) then answers one
`noul` per candidate in ONE call per page. Reference scale (RoboNuggets "19 Jev use cases",
#6): 60 blog posts linked in 2.5 s.

## When to invoke

- "Link up the notes in <dir>"
- "Add related-post links across <site content dir>"
- `.claude/notes/` is this workspace's second brain. The safe first target is always
  `--report`; read the table before any `--apply`.

Operator copy-paste prompt:

```
Link up the notes in <dir> with Jev (directives/rag/jev_backlinks.md). Report first, then apply.
```

## Inputs

- `--dir`: `path` (required), scanned recursively. `--ext md` (e.g. `md,mdx,html`).
- `--exclude`: globs (default `node_modules .git .tmp _archived`).
- `--candidates 12`: shortlist size per page (Jaccard on title+heading+filename words).
- `--min-prob 0.6`, `--max-links 5`, `--limit N`, `--workers 8`.
- `--report` (default) | `--apply`; `--dry-run` with `--apply` writes nothing.
- env `OPENROUTER_API_KEY` (also `OPENROUTER_API_TOKEN` / `OPENROUTER_API_TOEKN`).

## Outputs

- `--report`: `<dir>/.jev_backlinks.json` (summary, links per page with prob + mutual flag,
  errors) and a markdown table on stdout.
- `--apply`: each page with links gets a block between `<!-- jev-backlinks:start -->` and
  `<!-- jev-backlinks:end -->` holding `## Related` + relative links (`os.path.relpath`).
  Re-runs replace the block, never duplicate it.
- Summary JSON: pages, pairs_evaluated, links_kept, mutual_links, errors, cost_usd, wall_s.
- Ledger row in `.tmp/jev_ledger.jsonl` (`caller: jev_backlinks`).

## Exit Criteria (declarative)

- Report JSON exists; no page links to itself; no page has more than `--max-links`.
- Every link target resolves inside `--dir`.
- `errors / pages <= 0.05` on a live run; a second `--apply` changes zero files.

## Scripts (Layer 3)

- `execution/rag/jev_backlinks.py`
- `execution/modules/jev_client.py` (shared client; the only way to call Jev)
- `tests/test_jev_backlinks.py` (offline, monkeypatched `decide`)

## Edge cases

- Questions differ per page, so the script fans out `jev_client.decide` in its own thread
  pool rather than `decide_many` (which repeats one question set).
- Pages with zero word overlap get no candidates and no Jev call (free).
- An existing block is stripped before profiling, so old links never bias new ones.
- Jev fails open: a page whose call errored keeps no links; listed under `errors`.
- Links are directional; A->B and B->A are both kept when both pass (`mutual: true`).

## Changelog

- 2026-10-06: Created (RoboNuggets Jev use case #6).
