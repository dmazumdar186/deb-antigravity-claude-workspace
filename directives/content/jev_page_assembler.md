# Jev Page Assembler — web pages that build themselves

## Goal
Every visitor gets a landing page built for them in real time. Jev cannot write code, but it can pick parts: given a library of ready-made components (theme, hero, CTA, proof, form, FAQ, footer), ONE Jev call per visitor picks one variant per slot, and the assembler stitches them into the page. (RoboNuggets use case 18.)

## Operator prompts
- "Build a self-assembling landing page for <brand>" → write `{name, product, audience}` to a brand JSON in `.tmp/`, adapt `library.json` copy if needed, run `render-all --brand-json`, then start `server.py`.
- "Preview the page for a <persona> visitor" → `cli.py render --persona <name> --debug` or open `/preview?persona=<name>`.

## Inputs
- Visitor context: referrer, utm_source, utm_campaign, device, locale, hour_local, returning, pages_seen, query_terms (built from the HTTP request or `personas.json`).
- Brand: `{name, product, audience}` (`--brand-json`; default demo brand "Flowly").
- Env: `OPENROUTER_API_KEY` (or `OPENROUTER_API_TOKEN` / `OPENROUTER_API_TOEKN`).

## Tools / scripts (`execution/content/jev_page_assembler/`)
| File | Role |
|---|---|
| `library.json` | Components per slot: `description` (Jev reads it), `when` hints, `html` fragment (`{{brand}}`, `{{product}}`); themes carry `css` (CSS variables + system font stack). |
| `page_shell.html` | ASCII template, no CDN, no JS. |
| `personas.json` | 6 test personas. |
| `assembler.py` | `assemble(visitor, brand, library)` → `{html, choices, buyer_stage, cost, latency_ms, cached, error}`. |
| `server.py` | `python3 execution/content/jev_page_assembler/server.py --port 8766`; `/?debug=1`, `/preview?persona=X`. |
| `cli.py` | `render --persona X --out .tmp/page_X.html`, `render-all` (→ `.tmp/jev_pages/` + `summary.json`), `--brand-json`, `--no-cache`, `--debug`. |

## Outputs
HTML pages (local `.tmp/` or served), a persona × slot table with cost/latency, cache at `.tmp/jev_pages_cache.json`.

## How it decides
State = `{visitor, brand}`. Questions = one `choice` per slot (criteria = variant `description (good for: when)`) + `noul` `buyer_stage`. Unknown picks fall back per-slot to `DEFAULT_CHOICES`.

## Adding a component
1. Add a variant under the slot in `library.json` with `description`, `when`, `html` (semantic tags, labelled inputs, no `<script src`). Themes need `css` defining `--bg --fg --accent --muted --card --font --radius`.
2. Write the `description` as "what it is; who it is for" — that sentence IS the routing logic.
3. New slot: add to `SLOTS`, `SLOT_INSTRUCTIONS`, `DEFAULT_CHOICES` and a `{{slot}}` marker in `page_shell.html`.
4. Run `python3 -m pytest tests/test_jev_page_assembler.py`, then `render-all --no-cache` and eyeball the table.
5. Clear `.tmp/jev_pages_cache.json` after library changes (cache keys do not include the library).

## Latency and cost
- One Jev call ≈ 300-700 ms (measured 625-840 ms from the cloud container, 2026-10-07); ~$0.00006 per visitor.
- Repeat contexts are served from the hash-keyed cache at 0 ms / $0. Errors are not cached.
- Production: put the call at the edge (Cloudflare Worker calling OpenRouter, KV for the cache, fragments bundled in the Worker) — follow the wrangler conventions in `execution/infrastructure/`. Set a ~800 ms timeout and serve `DEFAULT_CHOICES` on timeout.

## Edge cases
- No key / HTTP error / exception → fail-open default page (debug ribbon shows `FALLBACK`).
- Jev often prefers `email-only` forms and `pricing-objections` FAQ; tighten descriptions if that bias matters.
- Brand values are HTML-escaped; output paths must stay inside the workspace.

## Changelog
- 2026-10-07: Created. 6 personas live-rendered, total $0.00037; Playwright screenshot via Node global playwright.
