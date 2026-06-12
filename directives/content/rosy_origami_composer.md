# Rosy Origami Composer

## Goal

Generate a structured, voice-matched monthly newsletter draft for a community organization (cultural assoc, alumni network, expat group, professional chamber) from their Instagram (+ optional YouTube + curated external news). The output is a paste-ready HTML email + markdown source. The composer does NOT send the email — that is delegated to Mailchimp/Beehiiv/Substack downstream.

Sandbox tenant: **GIO Paris (Global Indian Organization Paris)** — free internal use. First paid customer is the SECOND community org at €99/mo.

See plan file: `C:\Users\deban\.claude\plans\i-want-to-build-rosy-origami.md`.

## Inputs

### CLI flags (Phase 0 script)

| Flag | Default | Description |
|------|---------|-------------|
| `--tenant <slug>` | `gio_paris` | Tenant slug — must match a voice profile at `execution/content/voices/{slug}.json` and a template config at `execution/content/rosy_origami/templates/cultural_community.yaml` (or other archetype). |
| `--ig-handle <handle>` | (from tenant config) | Instagram handle to pull from. Required if not in tenant config. |
| `--ig-source <api|manual>` | `manual` | `api` uses Meta Graph API (requires `META_ACCESS_TOKEN` env + Business/Creator IG account + linked FB Page). `manual` reads from `.tmp/rosy_origami/{slug}/ig_export/` (folder of JPGs + captions.json). |
| `--yt-urls <comma-list>` | (none) | Optional YouTube URLs to include transcripts from. |
| `--news-query <str>` | (from tenant config) | Tavily query for news enrichment. If absent, news section omitted. |
| `--days <n>` | `30` | Lookback window for IG/YT content. |
| `--theme <str>` | (LLM-suggested) | Issue theme — if absent, LLM proposes one from the content pool. |
| `--spotlight-member <json>` | (none) | Manual JSON for Community Spotlight section: `{"name":"...","photo":"path","why":"..."}`. Section omitted if not provided. |
| `--archetype <name>` | `cultural_community` | Editorial template to use. Currently only `cultural_community` exists. |
| `--mode <name>` | `cheap` | LLM tier: `cheap` (Gemini free), `balanced` (Sonnet via OR), `premium` (Opus via OR). Maps to workspace `_TEMPLATE.py` `MODE_TO_MODEL` convention. Former flag name was `--tier`; renamed for harness consistency. |
| `--dry-run` | off | Build the prompt + show pool selection; skip LLM calls. |
| `--out <path>` | `.tmp/rosy_origami/{slug}/newsletter_<date>.html` | Output path. Always also writes `.md` source alongside. |

### Environment variables

| Var | Required? | Purpose |
|-----|-----------|---------|
| `GEMINI_API_KEY` | For `--tier gemini` | Free LLM path (15 RPM / 1500 RPD limit) |
| `OPENROUTER_API_KEY` | For `--tier default` or `premium` | Paid LLM fallback. Currently $0 credits per `memory/reference_api_key_status.md`. |
| `META_ACCESS_TOKEN` | For `--ig-source api` | Long-lived Page token (~60d). Get via Meta Business Suite. |
| `META_IG_USER_ID` | For `--ig-source api` | IG Business account user ID. |
| `TAVILY_API_KEY` | For news enrichment | Free tier. |

### Tenant config

Tenant config at `execution/content/rosy_origami/tenants/{slug}.yaml`:
```yaml
slug: gio_paris
display_name: Global Indian Organization Paris
voice_profile: gio_paris  # → execution/content/voices/gio_paris.json
archetype: cultural_community
ig_handle: TBD
news_query: "Indian expats France OR Paris Indian community"
languages: ["en", "fr"]
```

## Tools / Scripts

| File | Purpose |
|------|---------|
| `execution/content/rosy_origami/generate_demo.py` | Main script — orchestrates fetchers, composer, humanizer, output writer |
| `execution/content/rosy_origami/fetchers/ig_api.py` | Meta Graph API fetcher (Phase 0 happy path) |
| `execution/content/rosy_origami/fetchers/ig_manual.py` | Manual JPG + captions.json fetcher (Phase 0 fallback, default for GIO sandbox) |
| `execution/content/rosy_origami/fetchers/yt.py` | `youtube-transcript-api` wrapper with multilingual support (en/fr/hi) |
| `execution/content/rosy_origami/fetchers/news.py` | Tavily wrapper |
| `execution/content/rosy_origami/composer.py` | Editorial composer — section selection, prompt construction, LLM calls |
| `execution/content/rosy_origami/humanize.py` | Subprocess wrapper around `execution/content/humanizer.py` |
| `execution/content/rosy_origami/templates/cultural_community.yaml` | Editorial template spec (6 fixed sections) |
| `execution/content/rosy_origami/render.py` | Markdown → MJML → HTML rendering |
| `execution/content/voices/{tenant}.json` | Voice profile (humanizer-compatible) |

## Outputs

- `.tmp/rosy_origami/{slug}/newsletter_<YYYY-MM-DD>.html` — paste-ready HTML email
- `.tmp/rosy_origami/{slug}/newsletter_<YYYY-MM-DD>.md` — markdown source
- `.tmp/rosy_origami/{slug}/newsletter_<YYYY-MM-DD>.meta.json` — generation metadata (sections used, sources cited, cost estimate)

## Steps

1. Load tenant config from `execution/content/rosy_origami/tenants/{slug}.yaml`.
2. Validate voice profile exists at `execution/content/voices/{tenant.voice_profile}.json`.
3. Fetch content pool:
   - IG: via `ig_api.py` or `ig_manual.py` based on `--ig-source`
   - YT: per `--yt-urls`, via `fetchers/yt.py`
   - News: per `tenant.news_query` + `--days`, via `fetchers/news.py`
4. Load archetype template from `templates/{archetype}.yaml`.
5. Composer pass:
   - Map content pool items to template sections (event recap → IG event posts; news roundup → Tavily results; etc.)
   - Omit sections where pool is empty (no hallucination)
   - Build per-section prompts with source-pinning ("use ONLY facts from below; write TBD if missing")
6. LLM pass: one call per section via `--tier`. Gemini free tier for default.
7. Humanize pass: subprocess call to `humanizer.py` per section with `--voice {tenant.voice_profile} --platform email`. Check returncode.
8. Hallucination guard: regex scan output for dates not in source; flag for manual review.
9. Render: markdown → MJML → HTML via `render.py`.
10. Write outputs to `.tmp/rosy_origami/{slug}/`.
11. Surface flagged dates: read `.meta.json`'s `hallucination_flags` list and print each entry as a human-readable review checklist line: `"REVIEW: section={section} | url={source_url} | tokens={flagged_tokens}"`. If the list is empty, print `"Hallucination check PASS — no flagged dates."` Either way, this output must appear on stdout before the script claims done. The editor must act on this list before sending the newsletter.
12. Browser preview: open the generated HTML file in the default browser (`python -m webbrowser <out_html>`). Confirm visually that: (a) the email body is not blank, (b) at least one `<h2>` section header is visible, and (c) no `__PLACEHOLDER__` text is present. Log a WARNING to stderr if any predicate fails. Do not skip this step for non-dry-run runs.

## Exit Criteria

A newsletter run is complete only when ALL of the following predicates are true:

| Predicate | Check |
|-----------|-------|
| HTML file exists | `.tmp/rosy_origami/{slug}/newsletter_<date>.html` is present on disk |
| File size > 5 KB | `os.path.getsize(out_html) > 5120` — guards against empty/broken renders |
| `.meta.json` flagged_dates reviewed | `hallucination_flags` list printed to stdout; editor has acknowledged each entry (or list is empty) |
| No `__PLACEHOLDER__` strings | `grep -c __PLACEHOLDER__ out_html` returns 0 |
| Section count >= 3 | At least 3 `<h2>` elements in rendered HTML — non-empty newsletter |

If any predicate fails, the run is NOT done. Fix the root cause and re-run. "Script exits 0" is necessary but not sufficient.

## Edge Cases

| Case | Handling |
|------|----------|
| Meta API token expired | Script exits 1 with clear error pointing to Meta Business Suite token regen URL. |
| YT video has no captions in en/fr/hi | Skip that URL, log a warning, continue. Do NOT raise SystemExit. |
| Tavily returns 0 results | News Roundup section omitted entirely. |
| Spotlight not provided | Community Spotlight section omitted entirely (never LLM-generated to avoid hallucination). |
| Voice profile examples are <5 captions | Warn that voice match will be weak; proceed anyway. |
| Humanizer subprocess returncode != 0 | Raise RuntimeError with stderr. Common causes: missing voice file, missing GEMINI_API_KEY. |
| Gemini rate limit (429) hit mid-run | Retry once with 60s backoff; if still 429, fall back to cached prior section output OR fail loudly. |
| Hallucinated date detected | Log to `.meta.json` flagged list; do NOT auto-strike; human must review before sending. |
| IG image download fails | Use placeholder image in HTML render; log warning. |

## Product Considerations

Four-persona lens for Rosy Origami. Per `memory/feedback_multi_persona_thinking.md` and `memory/feedback_product_quality_skeptic.md`: user-facing artifacts must surface all four views before shipping.

### Head of Product
- The editor (a volunteer community manager, not a developer) must be able to act on the output without reading the code. Every flag, every warning, every quality check must surface on stdout in plain English.
- The newsletter's credibility with recipients depends on factual accuracy. One hallucinated date destroys trust. The hallucination-flag review step (Step 11) is not optional.
- Phase 1 success criterion: GIO Paris editor sends the newsletter with <5 min of manual edits after composer output.
- Long-term north star: composer is invisible — the editor sees a draft, curates, clicks send.

### Designer
- HTML email renders at 640px max-width. Test in Mailchimp Preview or Litmus for mobile (iPhone 14 Pro / Samsung S23) — mobile clients are 60%+ of opens for community newsletters.
- The GIO Paris color scheme (dark green `#006400`, gold `#FFD700`, dark gold `#B8860B`) must appear consistently across all H1/H2 elements. Do not override via inline styles from LLM output.
- Image placeholder handling: when `image_path` is None, the HTML must render gracefully (no broken img tags, no empty `<img src="">` — use a text fallback or omit the img block).
- Email client compatibility: avoid CSS grid, flexbox, and `position: absolute` in the rendered HTML — use table-based layout for Outlook compatibility if template is updated.

### Builder
- The directive's `Tools/Scripts` table lists 8 files that are currently inlined into `generate_demo.py` and `composer.py` (Phase 0 acknowledged gap). At Phase 1 refactor, either create the listed standalone files OR update the table — never leave the directive out of sync with disk.
- `args.mode` is parsed but currently unused in `generate_demo.py` — the mode/model selection happens inside `composer.py`. Wire the flag through at Phase 1 when OR credits are active.
- The humanizer subprocess call in `call_humanizer()` passes its own `--tier gemini` (the humanizer's flag, not generate_demo's). These are two separate flags on two different scripts — do NOT confuse them when renaming.
- Gemini 2.5-flash-lite (not 2.0 flash) is the active free model as of 2026-05. Model ID: `gemini-2.5-flash-lite-preview-06-17`. The directive's Known API limits section uses "Gemini 2.0 Flash" — update when the model name is confirmed stable.

### Skeptic
- **Empty source set**: if GIO Paris goes quiet for 2+ months (0 IG posts, 0 YT videos, no news hits), all sections with `omit_if_empty: true` are dropped. The resulting newsletter may have only an intro + closing. The Exit Criteria section count predicate (>= 3 `<h2>`) will FAIL — this is the correct behavior, it forces the editor to add content before sending.
- **Rate-limited source**: Tavily 429 mid-run silently drops the news section with no stderr warning in the current implementation. Add an explicit stderr warning when `fetch_news` returns [] due to a non-empty query (not a missing key, but a 429/timeout).
- **Voice profile drift**: if the editor adds 50 new captions to the voice profile between runs, the humanizer output voice will shift perceptibly. The editor should review at least one section side-by-side with the prior newsletter before sending.
- **OR credits at $0**: `--mode balanced` and `--mode premium` silently fall back to Gemini inside `composer.py` when OR credits are exhausted (per `memory/reference_api_key_status.md`). This is intentional but must be logged, not silent.

## Known API limits

- **Gemini 2.0 Flash free tier**: 15 RPM, 1500 RPD, 1M TPD as of 2026-05.
- **Meta Graph API (Development Mode)**: only works for accounts where developer has Admin/Editor/Tester role on linked FB Page. No App Review required in this mode.
- **Tavily free tier**: 1000 searches/month.
- **YouTube Data API**: 10K units/day default quota.
- **Instagram Basic Display API**: DEAD as of December 2024. Do NOT attempt to use.
