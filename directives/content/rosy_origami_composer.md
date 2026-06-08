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
| `--tier <name>` | `gemini` | LLM tier: `gemini` (free), `default` (Sonnet via OR), `premium` (Opus via OR). |
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

## Known API limits

- **Gemini 2.0 Flash free tier**: 15 RPM, 1500 RPD, 1M TPD as of 2026-05.
- **Meta Graph API (Development Mode)**: only works for accounts where developer has Admin/Editor/Tester role on linked FB Page. No App Review required in this mode.
- **Tavily free tier**: 1000 searches/month.
- **YouTube Data API**: 10K units/day default quota.
- **Instagram Basic Display API**: DEAD as of December 2024. Do NOT attempt to use.
