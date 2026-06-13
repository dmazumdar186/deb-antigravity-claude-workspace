# Directive: anthropic_watch

## Goal

Surface every substantive Anthropic / Claude Code / Claude SDK release and announcement within 24 hours of publication, so the operator stays current without manually polling X / blog / docs / npm / GitHub each day. Produce a one-screen morning digest that takes <2 minutes to read.

## When to run

- **Manual:** `py execution/personal_workflows/anthropic_watch/run.py` from workspace root.
- **Scheduled (v1.1, deferred):** daily 06:30 Europe/Paris via `/schedule` cloud routine. Runs after `job_tracker_pm_france` (06:00) so the operator sees both digests at breakfast.

## Inputs

Environment variables (read from `.env` at workspace root automatically):

| Var | Purpose | Required? |
|---|---|---|
| `FIRECRAWL_API_KEY` | HTML scraping for anthropic.com/news + docs.claude.com pages | Yes |
| `ANTHROPIC_API_KEY` | Sonnet 4.6 summarizer for tag/priority/tldr | No — falls back to heuristic tagging if absent |

CLI flags:
- `--dry-run` — fetch-only. Prints per-source counts. Does NOT call Claude. Does NOT write to ledger or digest. Use before first real run to confirm sources return data.
- `--source <name>` — restrict to one source. Names: `anthropic-news`, `docs-claude-code`, `docs-api`, `docs-deprecations`, `npm-claude-code`, `github-claude-code`, `github-sdk-python`, `github-sdk-typescript`.
- `--verbose` — DEBUG log level.

## Sources monitored (v1)

| Source | Method | Fragility |
|---|---|---|
| `https://www.anthropic.com/news` | Firecrawl scrape, `waitFor=2000ms` (Next.js JS render) | Medium — HTML structure may change |
| `https://docs.claude.com/en/release-notes/claude-code` | Firecrawl scrape | Low |
| `https://docs.claude.com/en/release-notes/api` | Firecrawl scrape | Low |
| `https://docs.claude.com/en/docs/about-claude/model-deprecations` | Firecrawl scrape | Low — single page diff |
| `https://registry.npmjs.org/@anthropic-ai/claude-code` | Public JSON, no scraping | None — stable contract |
| `gh api repos/anthropics/claude-code/releases` | `gh` CLI, urllib fallback | Low |
| `gh api repos/anthropics/anthropic-sdk-python/releases` | `gh` CLI, urllib fallback | Low |
| `gh api repos/anthropics/anthropic-sdk-typescript/releases` | `gh` CLI, urllib fallback | Low |

## Deferred sources

- **X / Twitter (@AnthropicAI, @claudeai, @alexalbert__, etc.)** — no reliable free option. X API Basic = $200/mo. Apify Twitter scraper actor = ~$0.30 per 1000 tweets. Decide in v1.2.
- **awesome-claude-code GitHub list** — community curation lag means it's a follower indicator, not leader. v1.3.
- **Simon Willison's blog tagged `anthropic`** — high signal but moderate volume. v1.3.
- **Hacker News search "claude code" past 24h** — noisy. v1.3 only if user wants broader pulse.

## Outputs

- `.claude/watch/anthropic_ledger.jsonl` — append-only ledger. One row per (source, url) pair, recorded on first sighting. Acts as the dedup sentinel set. Never edited or deleted.
- `.claude/watch/digests/YYYY-MM-DD.md` — one digest file per run-day. HIGH → MED → LOW priority groups. Format:
  ```
  - [tag] **Title** — tldr (max 25 words)
    source: `source-name` · https://...
  ```
- stdout: digest preview + INFO logs (per-source counts).
- stderr: WARN lines for fetch failures / zero-item sources.

## Tagging rubric (sent to Sonnet 4.6)

- **HIGH**: new model release, model deprecation, breaking API change, new CLI flag/hook/skill, security fix.
- **MED**: substantive feature add, pricing change, new SDK method, new product surface.
- **LOW**: research/policy blog post, minor docs edit, small patch release.

Heuristic fallback (no Claude key): "deprecat" / "sunset" → HIGH-deprecation; npm / github source → HIGH-release; "new model" / "introducing" → HIGH-release; everything else → LOW-announcement.

## Edge cases / failure modes

- **Source returns 0 items** — logged as `WARN <source> returned 0 items` to stderr. Run continues with other sources. Investigate if recurrent.
- **Firecrawl 429 / quota exhausted** — fetcher catches, logs WARN, returns []. Routine produces a (possibly empty) digest. Operator sees gap in next-day digest.
- **gh CLI missing** — falls back to `https://api.github.com` via urllib. Tested.
- **Anthropic API returns non-JSON / 5xx** — heuristic tagging fallback. Digest still produced.
- **Ledger malformed line** — skipped with WARN, ledger not corrupted. Subsequent rows still parsed.
- **Same item appears across two sources** (e.g. an Anthropic blog post linked from docs) — both are recorded, both appear in digest. Dedup is per (source, url), not per article. This is intentional: cross-source confirmation is signal.

## Cost (v1)

- **Firecrawl**: 4 scrapes/day × 30 = ~120 scrapes/month. Free tier is 500/mo → comfortably free.
- **Claude Sonnet 4.6**: ~5 new items/day × ~500 tokens each = ~$0.02/day → ~$7/year. Negligible.
- **No other paid touch points** in v1.

## Verification

After first real run:
1. `cat .claude/watch/digests/2026-06-13.md` — should contain the Fable 5 / Mythos 5 revocation announcement under HIGH (this is today's sanity-check oracle).
2. If absent: check stderr for `anthropic.com/news` — `WARN 0 items` means scrape failed (likely Firecrawl rate limit or HTML change); `INFO N items` but no Fable entry means summarizer mis-tagged (check ANTHROPIC_API_KEY or review heuristic fallback).
3. `tail .claude/watch/anthropic_ledger.jsonl` — confirm N rows appended.

## Scope guards

- Does NOT auto-edit any workspace file. Digests are drafts; operator decides what to apply.
- Does NOT poll faster than once per 24h. Hourly polling burns Firecrawl credit without proportional signal.
- Does NOT include broad LLM/AI news (OpenAI, Google, Meta) — Anthropic-ecosystem only.
- Does NOT propose its own opinions — only surfaces dated, sourced announcements with Claude-generated tldr.
