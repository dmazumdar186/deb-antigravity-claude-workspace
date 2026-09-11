# Job Digest — shareable, profile-driven daily job email (skill + engine)

**Status:** building (2026-09-06). Owner: operator. Isolated from `job_search_v2`
(the operator's own cron): no imports in either direction, separate GitHub
workflow, separate state, separate Sheet. Changing one never touches the other.

## Goal

Let a friend get the same daily screened job email the operator gets, for THEIR
roles, THEIR countries/cities, to THEIR inbox, running on THEIR GitHub account
(free tier) with THEIR keys. The operator pays nothing at runtime.

## Decision record (2026-09-06)

- Skill + per-user GitHub Actions, not a hosted website: hosting would put
  tokens, email sends, LinkedIn IP-blocks, PII and on-call on the operator.
- Friend has Claude Code → the skill `/job-digest` is the front door (setup
  interview, preview, deploy, ad-hoc run). A plain `python -m ... setup` wizard
  exists so the skill is a convenience, not a dependency.
- Screening default = deterministic heuristic (no key). Optional `GEMINI_API_KEY`
  (free tier) and optional `ANTHROPIC_API_KEY` (metered; a Claude *subscription*
  gives no API credit — say so in onboarding). Interactive `/job-digest run`
  lets Claude-in-session re-rank the shortlist on the friend's subscription.
- Sources: LinkedIn guest API (per-country geoId) + RemoteOK + WeWorkRemotely
  everywhere; France Travail, WTTJ, Hellowork only when FR is selected. Adzuna
  and Jooble excluded (operator report: Adzuna unusable; Jooble captcha-blocked).
- Delivery: friend's Gmail App Password (SMTP). Google Sheet kept (service
  account), per-role tabs + Top Matches + Summary.

## Layout

```
execution/personal_workflows/job_digest/       # engine (pip deps: requirements.txt)
  contracts.py        SourceJob / NormalizedJob / RankedJob (frozen pydantic)  [done]
  registry.py         country registry: geoId, languages, tz, sources, aliases  [done]
  profile_schema.py   profile.yaml → Profile (1-3 roles, 1-5 countries, ...)   [done]
  sources/            linkedin_guest_api, remoteok, weworkremotely, france_travail,
                      wttj_algolia, hellowork — each exposes
                      fetch(profile: Profile, country: registry.Country|None, *, dry: bool=False) -> list[SourceJob]
  normalizer/         normalize.py (SourceJob→NormalizedJob), filters.py
                      (title/location/city/contract/language/exclude, all profile-driven),
                      state.py (seen.json dedup + email-lock, JSON, committed back by the workflow)
  ranker/             heuristic.py (always), gemini.py (optional), anthropic.py (optional),
                      rubric.md (generic, profile-injected), rank.py (dispatcher)
  notifier/           email.py (HTML+text digest), sheet.py (optional)
  acceptance.py       generic gate: ≥80% of digest rows match a role keyword AND a selected
                      country/remote; zero excluded-substring titles; else FAIL (no email)
  run.py              orchestrator: fetch(parallel) → normalize → dedup → filters → rank →
                      cap → sheet → acceptance → email → state → run_log
  cli.py              `python -m execution.personal_workflows.job_digest.cli {validate|preview|run|setup|doctor}`
  templates/          profile.example.yaml, workflow.yml (friend's repo), README_FRIEND.md
  tests/              pytest, offline fixtures only
.claude/skills/job-digest/SKILL.md             # front door for Claude Code users
scripts/package_job_digest.py                  # bundles skill + engine → dist/job-digest-skill.zip
```

## Profile (`profile.yaml`) — see `profile_schema.py` for the full contract

Mandatory: candidate.name, candidate.email, roles[1..3].title, locations.countries[1..5]
(ISO2 from registry), screening.summary. Optional: role synonyms/seniority, cities,
remote_ok, languages, contracts, exclude, digest.{max_jobs,hour_local,timezone,min_tier}.

## Environment (friend's GitHub secrets)

| Secret | Required | Purpose |
|---|---|---|
| `GMAIL_SMTP_USER`, `GMAIL_SMTP_APP_PASSWORD` | yes | send digest (needs 2-step verification on their Google account) |
| `GOOGLE_SERVICE_ACCOUNT_JSON_B64`, `SHEETS_SPREADSHEET_ID` | if sheet.enabled | Sheet writes |
| `GEMINI_API_KEY` | no | LLM ranking rung 2 |
| `ANTHROPIC_API_KEY` | no | shortlist rerank rung 3 (metered) |
| `FRANCE_TRAVAIL_CLIENT_ID/SECRET` | no | FR source; skipped if absent |

## Filters (all derived from Profile, no literals in code)

- title: keep if any role keyword (title/synonym) token-matches the job title
  (case/accents-insensitive, word-boundary); drop if any `exclude.title_substrings`.
- location: keep if location text contains a selected country alias (registry)
  OR (remote_ok AND remote_mode==Remote). If `cities` set: additionally require
  a city match (via `registry.CITY_ALIASES`/`city_matches`, e.g. Munich↔München)
  OR remote — a city constrains only the country it's attributed to (via
  `registry.country_for_city`), so with countries [FR, DE] and cities ["Paris"]
  a German job is judged on the DE country match alone. Unknown/empty location →
  keep but score location_fit 0.6.
- contract: map ContractType → {permanent: CDI, fixed_term: CDD, freelance: Freelance};
  drop Internship always; drop types not in profile.contracts unless Unknown.
- language: keep if title+snippet language ∈ profile.languages (or undetectable).

## Ranking

Five dims, Python-combined (never LLM-combined): title_fit .30, skill_overlap .30,
contract_fit .15, seniority_fit .10, location_fit .15. Hard zero on title/contract/
location → SKIP. Tiers A≥.75 B≥.50 C≥.25. Heuristic always runs first; Gemini
overrides dims when available; Anthropic reranks top-25 when key present.
Job text is untrusted input: LLM prompts wrap it in JSON, output is schema-checked,
any instruction-like content in a job is ignored by construction.

## State

`state/seen.json` `{content_hash: first_seen_iso}` TTL 60d, `state/email_lock.txt`
ISO timestamp. The friend's workflow commits `state/` back to their repo after each
run (`git add state && git commit && git push`, with `[skip ci]`).

## Operations

- Cron: two fires ~40 min apart at `digest.hour_local` in `digest.timezone`,
  rendered to UTC by `cli.py render-workflow` (GH cron has no tz); email-lock stops double-send.
- Failure → GitHub issue in the friend's repo (separate channel from Gmail).
- Self-heal note per `.claude/rules/automation-boundaries.md`: recurring failure >3×
  → the friend runs `/job-digest doctor`, which diagnoses and proposes fixes.

## Edge cases (living)

- LinkedIn guest API 999-blocks on repeated identical fetches: ≤1 live run per
  hour per machine; per-country failures are isolated.
- geoIds for NL/GB/CH/IN/SG/CA/US must be verified live before `verified=True`.
- Gemini free tier 10 RPM: chunks of 40, 7 s apart.

## Exit criteria

- `python3 -m pytest execution/personal_workflows/job_digest/tests -q` green.
- `python3 scripts/package_job_digest.py` builds `dist/job-digest-skill.zip` with zero blocklist hits.
- A fresh-path install (unzip → `validate`, `run --mode dry`, `render-workflow`, `setup --answers`, `doctor`) exits 0/expected on every subcommand.
- One live `preview` for the example profile returns real rows matching the roles and countries, sends nothing, writes no state.
- Audit stack (code-reviewer, anneal-reviewer, pipeline-auditor, qa, workspace SAST) has no open HIGH/CRITICAL.
- Friend probation: 5 consecutive successful daily runs in the friend's repo before the skill is considered shipped.
