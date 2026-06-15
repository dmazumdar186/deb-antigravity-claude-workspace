# Directive — CV Optimizer (local CLI)

**Status:** Active. Replaces the Cloudflare Worker (cv_optimizer_v2) as the recommended path for the operator's personal use. The Worker stays alive as a demo URL but is no longer the production backend.

## Why local

The operator has a paid Claude subscription. The CV Optimizer is a single-user career tool. A Cloudflare Worker calling a third-party API was the wrong shape: it inherited a free-tier rate limit (Gemini 250 req/day) or required a $20+ minimum Anthropic top-up. A local CLI calling `claude --print` uses the operator's existing subscription with no quota worry and no per-call cost.

This directive replaces the SaaS-shaped approach with a local-shaped one. See `~/.claude/rules/learnings-loop.md` Exhibit A for the broader lesson.

## Goals

- Produce an ATS-optimized, recruiter-scannable PDF CV for a given (input CV, target JD) pair.
- Run on the operator's laptop using their authenticated Claude session.
- Cost: $0. Quota: bounded only by the operator's Claude subscription rate limits.
- End-to-end reliable: a synthetic test exercises the full happy path and must pass before any "ready" claim.

## Inputs

- **CV**: either `--cv path/to/cv.pdf` (extracts text via pypdf) or `--cv-text "..."` (direct text) or `--cv-text-file path/to/cv.txt`.
- **JD**: either `--jd-url <url>` (scrapes the page; uses Firecrawl if `FIRECRAWL_API_KEY` is set, otherwise plain fetch + readability) or `--jd-text "..."` or `--jd-text-file path/to/jd.txt`.
- **Output dir** (optional): `--out-dir path/to/out/` (default `.tmp/cv_optimizer_local/<timestamp>/`).
- **Model** (optional): `--model claude-sonnet-4-6` (default — per `~/.claude/rules/model-tier.md` Sonnet is the lowest acceptable tier for user-facing artifacts).

## Outputs

In the output directory:

- `cvspec.json` — the raw CVSpec JSON returned by Claude.
- `cv.html` — the rendered CV (cv-template.html with substitutions).
- `cv.pdf` — A4 PDF rendered via Playwright headless Chromium.
- `cv.png` — a snapshot PNG for quick visual review (mobile-friendly).
- `run.log` — timing breakdown (PDF extract, JD scrape, Claude call, render).

## Architecture

```
CV PDF -> pypdf -> CV text
                                +-> prompt assembly -> claude --print --model sonnet-4-6 -> JSON
JD URL -> Firecrawl (or fetch) -> JD text
                                                                  v
                                            JSON validated -> cv-template.html substitution -> HTML
                                                                  v
                                                       Playwright Chromium A4 -> PDF + PNG
```

The prompt is the same `prompts/system_prompt.md` used by the Worker (single source of truth — both paths read the same file).

## Front-door synthetic (per `~/.claude/rules/front-door-synthetic.md`)

Location: `tests/front_door.py` inside the project dir.

Behavior:
- Invokes the CLI with a fixture CV PDF and a fixture JD URL.
- Asserts: exit code 0; cvspec.json exists with required fields; cv.html exists and is non-empty; cv.pdf exists and is >50KB; language_detected matches JD language; at least one GitHub-sourced project surfaces in the output.
- Runs in <60s end-to-end.

Threshold: 5 consecutive passing runs before this directive's status can be described as "working" in any operator-facing report.

## Failure modes and handling

- **Claude --print rate limit on the operator's subscription**: surface clearly with `claude_print_failed: rate_limit`; suggest retry after N minutes. Do NOT silently fall back to Gemini — the local CLI is intentionally single-provider for predictability.
- **PDF extraction fails (corrupted PDF)**: surface `pdf_extract_failed: <reason>`; suggest pasting CV text instead.
- **JD scrape fails (login wall, 404)**: surface `jd_scrape_failed: <reason>`; suggest `--jd-text` or `--jd-text-file`.
- **Claude returns malformed JSON**: surface `cvspec_invalid: <jsonpath>`; save the raw response to `claude_raw.txt` for inspection.

## Why not delete the Worker

The Worker remains live at `cv-optimizer.pages.dev` as:
- A public demo URL for showing the project to others (recruiters, etc.).
- A fallback for the operator when away from their laptop (subject to free-tier quota).

The Worker is no longer the "official" CV-generation path. The local CLI is.

## Exit Criteria

- `py execution/personal_workflows/cv_optimizer_local/tests/front_door.py --runs 5` exits 0 with 5/5 PASS.
- Each run emits `cvspec.json`, `cv.html`, `cv.pdf`, `cv.png`, `run.log` in `--out-dir`.
- Run latency < 360s per run; ATS score >= 80 on the en-EN fixture.
- `claude --print --model claude-sonnet-4-6` resolves without error before the run starts.

## Related

- `~/.claude/rules/front-door-synthetic.md` — the synthetic requirement.
- `~/.claude/rules/learnings-loop.md` — why we pivoted from Worker to local.
- `~/.claude/rules/model-tier.md` — model selection rule (Sonnet minimum).
- `directives/personal_workflows/cv_optimizer_v2.md` — the Worker (demo only, see above).
- `execution/personal_workflows/cv_optimizer_v2/prompts/system_prompt.md` — shared prompt.
