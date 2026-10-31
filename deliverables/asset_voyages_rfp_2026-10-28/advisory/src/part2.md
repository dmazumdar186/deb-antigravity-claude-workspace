
# 3. What exists today

## 3.1 The workspace

ProdCraft's work runs from one repository (`deb-antigravity-claude-workspace`) organised in three layers:

1. **Directives** (`directives/{category}/`): Markdown standard operating procedures (goal, inputs, scripts, outputs, edge cases). They are updated with every failure ("self-annealing").
2. **Orchestration**: the AI session reads the directive and calls scripts in order. It does not hand-process anything a script can do.
3. **Execution** (`execution/{category}/`): deterministic Python and Node scripts; shared modules in `execution/modules/`; secrets in the environment only.

The point of the split is that business logic is deterministic and tested; the probabilistic part (the model) only routes and drafts. You should judge whether that holds for this project.

## 3.2 Reusable assets, with paths

| Asset | Path | What it gives this project |
|---|---|---|
| Astro + Cloudflare template | `execution/templates/web_app_astro_cf/` (`README.md`, `HARDENING.md`, `HANDOFF.md`) | Astro 5 SSG, Pages Functions, `_headers` with CSP/HSTS/nosniff/frame-deny, FR-default i18n with `/en/` mirror, a11y baseline, KV rate limit, `/api/health` (upstream status, secret presence, build SHA), Vitest + Playwright + Python acceptance gate + front-door synthetic, CI (SAST → unit → build → preview → acceptance → front-door), scaffold script. |
| Contracts-first pattern | `execution/personal_workflows/prodcraft_medspa/CONTRACTS.md` | Binding layout, interfaces, data classes, error channel and testing rules written before any code; every script runnable with `--mock`. Also an approval pipeline (draft → review → approved) we port to D1. |
| Static-site validator | `execution/gtm_client_workflows/<job-board build>/validate_site.py` | Pre-ship validation of a rendered static site (links, structure, assets). Basis for the SEO lint and leak scanner. |
| Worker pattern for forms | `…/<job-board build>/worker/` | Cloudflare Worker with `wrangler.toml`; form intake pattern. |
| Concept-site skill | `.claude/skills/site-redesign/SKILL.md`, `reference/build_rules.md` (88 rules "paid for once") | Prospectus-style concept, scroll-scrubbed film, deploy, eye review. Used to build the ASSET concept. |
| Functional suite + site_check | `D/research/functional.mjs`, `site_check.mjs` | Playwright assertions across desktop, Pixel 7, iPhone 13, reduced motion; zero console errors; zero third-party requests; overflow and tap-target checks. |
| CSP-faithful local server | `D/research/serve_csp.mjs` | Serves the site with the real `_headers` CSP so tests see production headers. |
| Enforcement hooks | `docs/reference/enforcement.md`, `.githooks/`, `execution/infrastructure/workspace_sast.py` | Pre-commit (blocks untracked deploy-target code), pre-push SAST (blocks HIGH/CRITICAL), Stop-hook verdict check. `--no-verify` requires a logged reason. |
| Audit stack | `.claude/memory/panel_roster.md`, `.claude/rules/` | 11-lens panel pass, project-expert panel, front-door synthetic, acceptance gate, adversarial loop. Used three rounds on the outgoing pages. |
| Human-eye gate | `human-eye-test` skill | Screenshots every page/state/viewport, reviewer agents read each image against a defect checklist, verdict with evidence. |
| Proposal system | `execution/gtm_client_workflows/proposal_system/` | JSON → DOCX/PDF proposal with itemised HT/TVA/TTC. |
| Jev | `directives/infrastructure/jev.md` | Pinned classify/score/gate model via OpenRouter, used for the L4 confidence gate. |
| Python hardening rules | `.claude/rules/python-hardening.md`, `python-execution.md`, `security.md`, `testing.md` | UTF-8 subprocess, no secrets in code/logs, test tiers. |

Prior production builds we draw on (anonymised): a public job-board build with listings, filters and a 3,047-check validation suite; two live bilingual FR/EN sites with forms, moderation and a GDPR data-subject-request flow; an approval pipeline with an R2-backed preview worker. None of these is a travel or MICE site. We have **no travel/MICE reference**, which the client's "verifiable references" criterion will expose.

## 3.3 What the concept already proves

The concept (`D/site/`, deployed noindex at the URLs in §1.4) is a static site, not the product. It proves the front-end craft and the Congress journey, nothing about the back-end.

| Evidence | Result | Source |
|---|---|---|
| Functional suite | 65/65 at the last run (28 Oct, recorded in `D/research/functional.json`); round 3 documented 62/62 before three assertions were added | `D/research/functional.json`, `D/15_Audit_Round3_Project_Experts.md` |
| site_check | PASSED on 4 pages × 4 contexts (desktop, Pixel 7, iPhone 13, reduced motion) | `HANDOFF.md` v2.4 |
| axe-core (WCAG 2.0/2.1/2.2 A+AA) | 0 violations on 4 pages × 2 viewports (rounds 1, 2 and 3) | `D/09_`, `D/12_`, `D/15_` |
| Bundle | ≈ 108 KB (index 33 + CSS 29 + JS 46, of which film 22); zero third-party JS; self-hosted fonts | `HANDOFF.md` |
| Film | 30 s scroll-scrubbed hero, rendered by our own pipeline (Chromium + ffmpeg, 24 fps); canvas fallback; reduced-motion poster | `D/research/render_film.mjs` |
| Catalogue demo | 12 fictional listings; search, filters, combined filter, no-results, reset, pagination, listing dialog, F03 prefill with fr-FR dates | functional suite |
| Console mock | Static: tiles, Pages, Congresses (one draft visible only in the console), Enquiries (Nouvelle / Qualifiée / Devis envoyé / Gagnée), GM&E `<details>` explanation | `D/site/console/` |
| Confidentiality | 0 matches for other clients' names in `site/`; asserted in the suite | `HANDOFF.md` |
| Honesty | Every quoted claim verbatim from live pages re-fetched 28 Oct; two flagged quotes re-verified with URLs; no prices, percentages, testimonials or codes | `HANDOFF.md` v2.1 |
| Review | Three internal audit rounds (11 lenses + 5 experts each); final verification PASS (34/34 fixes) | `D/08_`–`D/15_` |

Known limits of that evidence: the sandbox could not screenshot `*.pages.dev`, so the live-viewport trust gate was not run on production; live checks were HTTP 200, CSS hash match and CSP header confirmation. The eye review of v2 was done by the build worker itself in one round, then an independent reviewer returned NOT SHIP and every item was fixed (v2.1).

## 3.4 What is missing (the honest list)

None of these exist as code today. Each must be built, tested and documented before the acceptance test that depends on it.

| # | Missing piece | Needed by | Est. hours |
|---|---|---|---|
| 1 | Console editor: structured block editor, preview, publish trigger | T15, A2 | 14 |
| 2 | Roles + MFA: Cloudflare Access in front of `/admin`, 5-role permission matrix in every route, break-glass | I1, I2, T05 | 10 |
| 3 | D1 schema + migrations (public and private databases) | everything | in modules |
| 4 | Versions and restore (`revision` snapshots), soft delete with 30-day trash | I5, I7, T15 | 7 |
| 5 | Audit log (user, action, object, time; 12 months) | I6 | 3 |
| 6 | CSV import with dry run, hard/soft dedup, rejection report, batch ID | C01, N3–N7 | 5 |
| 7 | Enquiry back-office: inbox, statuses, owner, history, logged export, routing | F05, G1–G5 | 12 |
| 8 | Backups (nightly D1 export → R2, off-platform weekly copy) + restore drill | T13, RPO/RTO | 3 + drill |
| 9 | Uptime monitoring + status page + dead-man alarm on backups | SLA | 1.5 |
| 10 | Core Web Vitals (Lighthouse CI) and axe gates in CI per template | T11, T12 | in QA |
| 11 | Crawl → URL inventory → redirect map generator + chain detector | L0.4, S1–S2, T10 | 8 |
| 12 | GM&E leak scanner over all public output (HTML, JS, JSON, sitemap, exports) | T05 | 2.5 |
| 13 | Media library (R2 upload, required alt text, rights note, resizing) | I4, D3 | 4 |
| 14 | First-party event beacon + dashboard | H1–H4 | 3.5 |

## 3.5 Capability matrix

| Capability | Status | Lift path |
|---|---|---|
| Static public site, FR default, hreflang-ready | EXISTS | Scaffold from the template; add ASSET templates. |
| Security headers, CSP, HSTS | EXISTS | Template `_headers`; tighten for Console. |
| Forms: validation, Turnstile | EXISTS | Reuse; add dedup and fallback. |
| Form durable save + two-provider email fallback | PARTIAL | KV save exists; add D1 save, `send_log`, Brevo → Resend adapter, retry queue. |
| Consent banner and GDPR DSR flow | EXISTS | Port DSR from KV/Supabase pattern to D1. |
| Structured data, sitemap, robots, canonicals | EXISTS | Add `Event` schema for congresses. |
| Redirects | PARTIAL | We have generated 302 maps; switch to 301, add chain test and generator. |
| Listings with filters | PARTIAL | Job-board pattern; add period filter and search index. |
| Approval pipeline | PARTIAL | Port the draft → review → approved pattern to D1 state machines. |
| Admin auth | PARTIAL | Basic Auth today; replace with Access + roles. |
| Block editor, media, versions, soft delete, audit log | MISSING | New, built as a reusable "Console" package with ASSET as first tenant. |
| D1 data layer | MISSING | Drizzle schema + migrations; no prior D1 project. |
| Encrypted private vault | MISSING | New; AES-GCM with key in a Worker secret. |
| Backups and restore drill | MISSING | New cron Worker + runbook + timed drill. |
| Monitoring and status page | PARTIAL | Health endpoint exists; add external probes. |
| Lighthouse and axe in CI | MISSING (as gates) | axe used ad hoc in audits; wire both into CI with thresholds. |
| Crawl → redirect map | MISSING | New script + directive + `--mock` test. |
| AI ingestion (L4, optional) | PARTIAL | Jev and OpenRouter exist; queue, eval set, pinning are new. |

Roughly 40% of the scope by hours rests on EXISTS rows; the rest is PARTIAL or MISSING. The largest unmeasured line is the Console (≈ 44 h estimated, never timed on this stack).

## 3.6 Questions for the reviewers

1. Is "40% proven" a fair characterisation from the matrix, or are we flattering ourselves?
2. Which MISSING item would you build first as a spike to de-risk the estimate? (Our answer is the block editor + publish rebuild loop.)
3. Is there an off-the-shelf component you would use instead of building any MISSING row?

# 4. System design

## 4.1 Domain model

Two D1 databases with separate bindings: **`public_db`** (content, catalogue, enquiries, events; readable by the build and the form Worker) and **`vault_db`** (GM&E authorisations; bound only to the admin Worker). All IDs are ULIDs. Every mutable table carries `created_at`, `updated_at`, `deleted_at` (soft delete), `created_by`, `updated_by`.

```text
public_db
  user(id, email, display_name, role, active, last_login_at)
  page(id, slug, locale {fr|en}, title, meta_title, meta_description, template,
       status {draft|in_review|published|archived}, published_at, approved_by,
       translation_of, human_translated:bool, version)
  block(id, page_id, position, type, data_json, version)
     type ∈ {hero, text, image_text, cards, list, faq, cta, quote_claim,
             congress_strip, contact_doors}
  media(id, r2_key, mime, width, height, alt_text NOT NULL, rights_note NOT NULL,
        rights_expires_on, uploaded_by)
  claim(id, text, source_url, page_id, approved_by, approved_on)      -- claims register
  congress(id, title, slug, discipline, country_iso2, city, venue, organiser,
           start_date, end_date, timezone, official_url, verified_on, language,
           editorial_status {draft|in_review|published|archived},
           visibility {listed|unlisted}, fare_badge:bool, next_edition_id,
           import_batch_id, version)
  enquiry(id, type {BT|MICE|CONG|SME_ACCOUNT|DEMO}, created_at, source_utm_json,
          landing_path, referrer_domain, company, contact_name, email, phone,
          payload_json, congress_id NULL, status, owner_id, privacy_notice_version,
          marketing_optin, marketing_optin_at, dedup_key, purge_after)
  enquiry_event(id, enquiry_id, actor_id, kind, note, at)
  send_log(id, enquiry_id, provider {brevo|resend}, recipient_hash, status, error, at)
  recipient_rule(id, enquiry_type, email, backup_email)
  revision(id, entity, entity_id, version, snapshot_json, actor_id, at)
  audit_log(id, actor_id, action, entity, entity_id, ip_trunc, at)
  event(id, name, path, activity, utm_source, utm_medium, utm_campaign,
        referrer_domain, props_json, day)                -- no cookie, no IP, no PII
  import_batch(id, filename_hash, rows_total, rows_ok, rows_rejected,
               rows_flagged, dry_run:bool, actor_id, at, report_r2_key)
  setting(key, value)                                    -- client-area URL etc.

vault_db
  authorisation(id, congress_id, application_date, channel, code_ciphertext,
                code_iv, evidence_r2_key, conditions, stage, approver_id,
                valid_from, valid_to, version)
  stage_history(id, authorisation_id, from_stage, to_stage, actor_id, note, at)
```

`congress_id` in the vault refers to `public_db.congress.id` by value; there is no cross-database join path in code that the public build or the form Worker can execute.

## 4.2 State machines

**Editorial (pages and congresses).**

```text
           submit (contributor+)          approve+publish (editor+)
  draft ─────────────────────► in_review ─────────────────────► published
    ▲                             │                                 │
    └──────── return to draft ────┴─────── unpublish (editor+) ─────┘
                (no field lost; new revision)                        │
  published ── archive (editor+) ──► archived ── restore (editor+) ──► draft
```

Rules: every transition writes a `revision` and an `audit_log` row. Only `published` rows enter the public build. An EN page can only reach `published` if `human_translated = true`. Editors publishing their own draft is allowed (two-person rule is an option, not default: the client has two editors).

**GM&E internal workflow (vault only).**

```text
detected → verified → application_to_prepare → application_submitted
        → code_received → issuance_authorised → approved_for_sale → archived
```

| Transition | Guard |
|---|---|
| → verified | `official_url` and `verified_on` present on the congress |
| → application_submitted | `application_date` and `channel` present |
| → code_received | code (encrypted) + evidence file + validity period present; approver/admin only |
| → issuance_authorised | named approver sign-off |
| → approved_for_sale | approver only; unlocks `fare_badge` option on the public congress |
| → archived | read-only thereafter; code retained to `valid_to` + retention period |
| any → previous | approver/admin only, with a mandatory note |

**Enquiry.**

```text
new → contacted → qualified → quoted → won | lost
  └────────────────────────────────────────────► spam (purged after 30 days)
```

Any transition records actor, time and note in `enquiry_event`. Owner can be set at any state. A duplicate submission (same email + type + congress within 24 h) appends an event to the first record instead of creating a row.

## 4.3 Invariants

These are properties the system must hold at all times. Each has a test.

| # | Invariant | Enforced by | Test |
|---|---|---|---|
| I-1 | No GM&E code, evidence or vault stage ever appears in any public byte (HTML, JS, JSON index, sitemap, RSS, public CSV, API response, error page) | Structural: vault is a separate database bound only to the admin Worker; public build has no binding to it. Scan: leak scanner with a seeded canary code across the full build output and public API responses, in CI | T05; CI fails on any match |
| I-2 | No personal data in URLs, analytics events or logs | POST-only forms; beacon whitelist of properties; search text dropped if it matches email/phone patterns; log redaction; IP truncated in audit log | Payload crawl in T09; log grep in CI |
| I-3 | Nothing reaches production except through the editorial state machine | Build reads `status = published` only; no direct-publish API | T04; unit tests on the build query |
| I-4 | An enquiry is durably stored before the user sees "thank you" | Handler writes D1 (or KV fallback) and only then returns 200; email is sent asynchronously via queue | T01 with D1 and email deliberately failed |
| I-5 | No password is stored for the client area | No password column; client area is an external link | T08 schema check |
| I-6 | Every mutation is attributable | `audit_log` written in the same transaction as the mutation | Unit tests per route |
| I-7 | A fare badge is never shown without `approved_for_sale` | Badge flag write path checks vault stage via admin Worker | T05 dataset |
| I-8 | Imports are idempotent | Hard-duplicate key; batch ID; dry run writes nothing | Import the same file twice → 0 new rows |

## 4.4 Roles

| Role | Who (default Q28) | Purpose |
|---|---|---|
| Technical admin | ProdCraft (later ASSET's chosen developer) | Everything, including settings, recipients, users, break-glass |
| Editor | Veena, backup editor | Create, edit, publish pages and congresses; import; manage enquiries |
| Contributor | Optional | Drafts only |
| Commercial viewer | Management, sales | Read enquiries, export, dashboard |
| Congress/fare approver | Management (and Veena, per Q28) | Vault read/write, GM&E stages, `approved_for_sale`, fare badge |

Note the tension: Q28's default says "only Ms Khatri and management can see GM&E codes; the backup editor cannot". Veena is therefore Editor **and** Approver; the backup editor is Editor only. Roles are a set per user, not a single value.

## 4.5 Permissions matrix

| Action | Admin | Editor | Contributor | Viewer | Approver |
|---|---|---|---|---|---|
| Create/edit draft page or congress | ✓ | ✓ | ✓ | — | — |
| Submit for review | ✓ | ✓ | ✓ | — | — |
| Publish / unpublish / archive | ✓ | ✓ | — | — | — |
| Restore revision / restore from trash | ✓ | ✓ | own drafts | — | — |
| Hard delete | ✓ | — | — | — | — |
| Upload media | ✓ | ✓ | ✓ | — | — |
| CSV import (dry run / commit) | ✓ | ✓ | — | — | — |
| Public catalogue export | ✓ | ✓ | — | ✓ | ✓ |
| Read enquiries | ✓ | ✓ | — | ✓ | — |
| Change enquiry status / owner | ✓ | ✓ | — | — | — |
| Export enquiries (logged) | ✓ | ✓ | — | ✓ | — |
| Read vault / GM&E code | ✓ | — | — | — | ✓ |
| Advance GM&E stage, set fare badge | ✓ | — | — | — | ✓ |
| Edit recipients, settings, client-area URL | ✓ | — | — | — | — |
| Manage users and roles | ✓ | — | — | — | — |
| Read audit log | ✓ | own actions | — | — | ✓ (vault) |

The matrix is data (`permissions.ts`), enforced by one middleware on every admin route, and tested exhaustively (5 roles × every route × allowed/denied) in CI. Cloudflare Access gates the hostname; the app decides authorisation from the Access JWT's email mapped to `user.role`.

## 4.6 Data retention and export

| Data | Retention (proposal, ASSET to approve) | Deletion |
|---|---|---|
| Prospect enquiries | 3 years after last contact (based on CNIL prospect guidance; to verify) | Nightly purge job on `purge_after` |
| Spam | 30 days | Purge job |
| Won clients | Per ASSET's own records policy | Manual |
| Audit log, Access logs | 12 months | Purge job |
| Send log | 12 months, recipient stored as hash | Purge job |
| Revisions | All, or last 50 per entity (to decide) | — |
| Vault | Until `valid_to` + agreed period | Approver action, logged |
| Backups | D1 Time Travel 30 days; nightly dumps 30 days; 12 weekly off-platform copies | Lifecycle rules |
| Events | Aggregated daily; no PII | Raw rows 13 months |

**Export**: one command (and a Console button for admins) produces a ZIP with every table as CSV (UTF-8, documented columns) and JSON, plus the R2 media tree and a manifest with checksums. The vault exports separately, encrypted, admin only. **DSR procedure**: search by email across `enquiry`, `enquiry_event`, `send_log` (by hash); export or delete; log the request.

## 4.7 CSV import model

| Element | Rule |
|---|---|
| Schema | Versioned (`v1`); columns = RFP congress fields; ISO dates (`YYYY-MM-DD`), ISO 3166-1 alpha-2 country, UTF-8, `;` or `,` auto-detected |
| Required | title, discipline, country, city, start_date, end_date, official_url, verified_on, language |
| Row errors | Coded (`E01 missing_required`, `E02 bad_date`, `E03 end_before_start`, `E04 bad_url`, `E05 unreachable_url`, `E06 bad_country`, …) |
| Hard duplicate | normalised title + start_date + city → rejected |
| Soft duplicate | same normalised title, same year → flagged for a human |
| Flow | Upload → dry run (writes nothing) → report (OK / rejected / flagged, downloadable CSV) → confirm → import as drafts with batch ID → editor bulk-publishes |
| Idempotency | Re-importing the same file creates nothing new |

## 4.8 i18n and SEO migration model

**i18n.** French is the default at `/` (or `/fr/`, to decide with the redirect map, since today's URLs have no locale prefix). English lives under `/en/`, built but not published until the option is bought. Strings in typed locale files; content per locale as separate `page` rows linked by `translation_of`. Each page emits `<link rel="canonical">` to itself and `hreflang` pairs (`fr`, `en`, `x-default`) only when both versions are published. No machine-translated content can be published (I-3 + `human_translated`).

**SEO migration.**

```text
crawl old site ─► URL inventory (status, title, canonical, inlinks, GSC clicks)
     ─► decision per URL: retain | merge | redirect | remove (ASSET approves priority URLs)
     ─► mapping sheet ─► generated _redirects (301) ─► chain detector + no-home-blanket check
     ─► staging test: every old URL → one 301 → 200
     ─► cutover checklist (noindex removed on prod, sitemap submitted)
     ─► weekly Search Console + 404 report through J6, then monthly
```

Staging is `noindex` (header and robots) and behind Access. Removed URLs return 410 where intentional. Congress pages emit schema.org `Event` with the real organiser (to check against Google's event structured-data policy).

## 4.9 Questions for the reviewers

1. Two D1 databases for vault isolation: is that sufficient, or would you put the vault on a different account or provider entirely?
2. Is the permission model (role set per user, one middleware, exhaustive matrix test) adequate for a 5-user system, or over-engineered?
3. Does any invariant lack a test that would actually fail if it were broken? (I-1 is the one we worry about: free-text fields.)
4. Would you store revisions as full snapshots (our plan) or diffs?

# 5. Architecture

## 5.1 Components

| Component | Role | Why this |
|---|---|---|
| Cloudflare Pages (static assets) | Public site, pre-built Astro HTML, JSON search index | Fast globally, no origin to patch, free static requests |
| Workers (modular monolith) | `api` Worker: forms, beacon, health. `admin` Worker: Console API (behind Access). `cron` Worker: backups, purge, retry. | One codebase, three entry points; shared modules; no network hops between services |
| D1 (jurisdiction EU) | `public_db`, `vault_db` per environment | SQL, Time Travel 30 days, EU jurisdiction set at creation (verified 28 Oct) |
| R2 | Media (public bucket via Worker), evidence (private bucket), backups (private bucket) | No egress fees |
| Cloudflare Access | Gate on admin and staging hostnames; one-time PIN or client IdP; MFA | No public admin login page |
| Turnstile | Anti-spam on forms | Free, no cookies for challenge |
| Queues | Email sending and retries; rebuild trigger de-duplication | Decouples "thank you" from email delivery |
| Cron Triggers | Nightly backup, purge, dead-man heartbeat | Built-in |
| Email adapter | Brevo (primary, French company) → Resend (fallback) | Two providers behind one interface |
| AI adapter (L4 only) | OpenRouter + Jev, pinned model ID, prompt hash, schema-bound output | Option; never publishes |
| GitHub (org in ASSET's name) | Repo, CI (Actions), Renovate/Dependabot | Ownership from day one |
| External monitor | UptimeRobot (free tier) probes + status page | Independent of Cloudflare |

**Language and libraries**: TypeScript throughout; Astro for pages; Console UI in Preact or web components (open decision, §10); Zod for validation at every boundary; Drizzle for schema and migrations; Playwright, Vitest, axe-core, Lighthouse CI for tests.

## 5.2 Topology and trust boundaries

```text
                         INTERNET (untrusted)
   visitor ───────────────┬───────────────────────────── staff (Veena, mgmt)
                          │                                        │
          ┌───────────────▼───────────────┐        ┌───────────────▼──────────────┐
  TB1     │ Cloudflare edge: TLS, WAF,    │        │ Cloudflare Access (TB2)      │
          │ Turnstile, rate limit         │        │ OTP / IdP + MFA → signed JWT │
          └───────┬──────────────┬────────┘        └───────────────┬──────────────┘
                  │              │                                 │
         static HTML/JSON   POST /api/*                     admin.<domain>/*
          (Pages, public)       │                                  │
                          ┌─────▼──────┐                    ┌──────▼───────┐
                          │ api Worker │                    │ admin Worker │  TB3: role check
                          └─┬───────┬──┘                    └─┬─────┬────┬─┘  per route
                            │       │ enqueue                 │     │    │
                     ┌──────▼──┐ ┌──▼─────┐          ┌────────▼┐ ┌──▼──┐ │
                     │public_db│ │ Queue  │          │public_db│ │vault│ │ TB4: vault binding
                     │  (D1)   │ └──┬─────┘          │  (D1)   │ │ _db │ │ exists ONLY here
                     └─────────┘    │                └─────────┘ └─────┘ │
                              ┌─────▼────────┐                  ┌────────▼────────┐
                              │ email adapter│→ Brevo / Resend  │ R2: media,      │
                              └──────────────┘                  │ evidence(priv), │
                                                                │ backups(priv)   │
                 publish ─► deploy hook (deduped) ─► CI build   └─────────────────┘
                 (reads public_db published rows only) ─► Pages atomic deploy
```

| Boundary | Crossing | Control |
|---|---|---|
| TB1 Internet → edge | All visitor traffic | TLS, HSTS, CSP, WAF managed rules, Turnstile, per-IP rate limit on `/api/*` |
| TB2 Internet → admin | Staff only | Access policy by named email; OTP or IdP; MFA; session length 12 h |
| TB3 Admin Worker → data | Every Console request | Verify Access JWT (aud + signature), map email → roles, permission middleware, Zod input validation |
| TB4 Vault | Only the admin Worker has the `vault_db` and private R2 bindings | Code encrypted with AES-GCM; key is a Worker secret; approver/admin only |
| TB5 Build → public | CI build | Build query selects published rows; leak scanner on output before deploy |
| TB6 Workers → third parties | Email, monitor, AI | Secrets in Worker secrets; minimum data (no PII to AI; recipient hash in logs) |

## 5.3 Data flows

| Flow | Steps |
|---|---|
| Enquiry | Browser POST → Turnstile verify → Zod → dedup key → D1 insert (fallback KV if D1 errors) → 200 "thank you" → queue message → email adapter (Brevo; on failure Resend; on double failure flag + retry every 15 min + Console banner) → `send_log` |
| Publish | Editor approves → state change + revision + audit → deploy hook (deduplicated: many presses = one build) → CI builds from published rows → leak scanner + SEO lint → Pages atomic deploy → "live in about N min" (N to measure) |
| Import | Upload CSV to admin Worker → parse + validate + dedup in dry run → report to R2 → confirm → transactional insert as drafts with batch ID |
| Authorisation | Approver opens vault → reads/advances stage → `stage_history` + audit; badge flag write checks stage |
| Backup | Nightly cron → D1 export (both DBs) → R2 private bucket (dated) → weekly copy to an off-platform store (provider TBD) → heartbeat to monitor (dead-man alarm if missed) |
| Measurement | Page view: Cloudflare Web Analytics (cookie-free). Events: beacon POST with whitelisted properties → `event` table → daily aggregates |

## 5.4 Environments

| Env | Host | Data | Access | Indexing |
|---|---|---|---|---|
| dev | localhost (Wrangler, local D1/R2) | Seed + fixtures; fake GM&E codes | Developer | n/a |
| staging | `staging.<domain>` + `admin.staging.<domain>` | Own D1/R2; anonymised copy of prod or seed | Access (named emails) | `X-Robots-Tag: noindex`, robots disallow |
| prod | `<domain>`, `admin.<domain>` | Production | Public / Access | Indexable after cutover checklist |

Same code, different bindings (`wrangler.toml` environments). Secrets per environment. Preview deployments per pull request run against staging data.

## 5.5 Deployment and rollback

- **Atomic**: Pages deploys are immutable; a deploy switches all at once. Workers deploy with versioned uploads.
- **Rollback**: Pages instant rollback to the previous deployment; Workers rollback to previous version; D1 schema migrations are forward-only and additive (expand → migrate → contract across two releases) so code rollback never meets an incompatible schema. Data rollback via Time Travel to a timestamp.
- **Cutover (J5)**: lower DNS TTL 48 h before; deploy prod; run the checklist (redirects, noindex off, sitemap, forms to real recipients, monitors); switch DNS on written go and cleared payment; keep old host available for 30 days for DNS revert.

## 5.6 Backups and restore

| Layer | Mechanism | RPO | Coverage |
|---|---|---|---|
| 1 | D1 Time Travel (30 days on Paid, verified 28 Oct) | Minutes | Both DBs |
| 2 | Nightly SQL export → R2 private bucket, 30 dated copies | 24 h | Both DBs |
| 3 | Weekly copy of layer 2 + media to an off-platform store, 12 kept | 7 days | DBs + media |
| 4 | Git repo (code, config, migrations) | per commit | Code |

**Restore drill**: monthly in the plan, and at J5 for T13. Script: create a fresh D1, import last night's dump, point a staging Worker at it, run the smoke suite, record elapsed time. RTO target 8 business hours (RFP); the drill measures it. The drill has **never been run on this stack**.

## 5.7 Observability

- External probes (UptimeRobot, 5-minute interval): home, a congress page, `/api/health` (checks D1 read, queue depth, secret presence, build SHA), admin login page reachable.
- Status page (UptimeRobot free tier).
- Dead-man heartbeat from the backup cron; missing heartbeat alerts.
- Error channel: Worker exceptions and failed jobs post `service / environment / error / count` to one channel (email + messaging) owned by ProdCraft.
- Workers observability logs (no PII); `send_log` failures surface as a Console banner for Veena.
- Monthly report: availability, backups, restore drill result, enquiries by activity, Search Console errors, patch log.

## 5.8 Security

| Control | Implementation |
|---|---|
| Transport | TLS, HSTS (preload after stabilisation) |
| Headers | CSP `default-src 'self'`, no inline script, `frame-ancestors 'none'`, `nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy` minimal |
| Admin exposure | No public admin; Access on hostname; JWT verified in-app (defence in depth) |
| MFA | Access one-time PIN alone is a single factor (possession of the mailbox), so it is not MFA. Default (Q26): client IdP with enforced MFA; if ASSET has none, a Cloudflare-supported IdP with TOTP/passkey. Open: which IdP ASSET uses. |
| Least privilege | Five roles, matrix-tested; Cloudflare API tokens scoped per job; GitHub branch protection |
| Secrets | Worker secrets only; pre-commit and pre-push SAST block secrets; bundle scan for keys; rotation at handover |
| Input | Zod at every boundary; parameterised queries via Drizzle; CSV parsing with size and row caps |
| Abuse | Turnstile, rate limit, dedup |
| Vault | Separate DB, encryption at rest with app key, approver-only, leak scanner |
| Dependencies | Renovate PRs, monthly patch window, critical within 2 business days, `npm audit` in CI |
| Testing | SAST pre-push, dependency audit, OWASP ZAP baseline on staging, role matrix, leak scanner |
| Data protection | DPA (ProdCraft as processor); subprocessor register (Cloudflare US/EU DPA + SCCs/DPF, Brevo FR, Resend US, UptimeRobot, GitHub) |

## 5.9 Failure modes and fallbacks

| Failure | Effect | Fallback | Detection |
|---|---|---|---|
| D1 unavailable | Forms cannot write | Write to KV backup store; replay job; user still gets "thank you" (I-4) | health check, error channel |
| Brevo fails | No notification | Resend; then flag + 15-min retry + Console banner | `send_log` |
| Both email providers fail | Team not notified | Enquiry is saved; banner; daily digest retry | send_log, alert |
| Access outage (happened 12 Jun 2025, ~2h28) | Admin unreachable | Public site unaffected; editing waits; break-glass CLI for emergencies | monitor |
| Cloudflare global incident (e.g. 18 Nov 2025, ~2h10) | Site down | None on-platform; status page; excluded from SLA (Q30) | external probe |
| Bad deploy | Broken pages | Instant rollback | front-door synthetic |
| Bad migration | Data inconsistency | Forward-fix or Time Travel restore | migration tests on staging copy |
| Accidental deletion | Content lost | Soft delete + trash 30 days + revisions | — |
| Leak of a code into free text | Exposure | Leak scanner fails the build before deploy | CI |
| Rebuild storm (many publishes) | Build queue | De-duplicated deploy hook | queue depth |
| Spam wave | Inbox noise | Turnstile + rate limit + spam status | counts |
| Founder unavailable | No support | Runbook a stranger can follow; repo and accounts in ASSET's name; named backup developer (not yet arranged) | — |

## 5.10 Alternatives considered

**Directus (headless CMS) + same Astro front end.** Pros: mature editor, roles, revisions and media out of the box; less custom code (perhaps −25 to −30 h on the Console). Cons: needs a server and Postgres (≈ €10–30/month VPS range, estimate), patching and uptime of that server become ours, ≈ 16 h setup (≈ €1,100 at €70/h), the vault invariant must then be enforced inside Directus permissions rather than structurally, and a second runtime to hand over. We present it as the costed alternative and do not recommend it, mainly because of the vault and operational load. **This is the decision we most want you to challenge.**

**WordPress + ACF** (keep the current platform): lowest switching cost for editors; but plugin attack surface, PHP hosting, and the GM&E isolation is harder to prove. Kept as the "retain" option the L0 audit must evaluate honestly.

**Why not microservices.** Five users, ≈ 300 listings, low traffic. Separate services would add network failure modes, deploy coordination and monitoring cost with no scaling benefit. A modular monolith (one repo, three Worker entry points, shared typed modules, adapters at the edges) keeps boundaries in code and ships from one pipeline. Strictly, three Workers deploy as three versioned uploads; CI deploys them in a fixed order from one commit, and the forward-only schema rule (§5.5) keeps a partial deploy safe.


## 5.11 Questions for the reviewers

1. Is Cloudflare-only (no SLA on Workers/D1 at our plan level) an acceptable concentration risk for this client?
2. Is the KV fallback for enquiries worth its complexity, or would you accept a visible error when D1 is down?
3. Would you choose Directus here? What would change your mind either way?
4. Is the backup design adequate for RPO 24 h / RTO 8 business hours? What would you add?

## 5.12 Engineering specifics (added at pre-review QA)

Platform limits below are from Cloudflare's public docs as we understand them on 31 Oct 2026; each is marked to re-verify at J0 because they change.

| Topic | Position | Status |
|---|---|---|
| Load assumed | Order of magnitude only: ≤ 5 staff users, ≈ 300 listings, low thousands of visits/day, tens of enquiries/day. No traffic data from ASSET yet. | Open: obtain 12 months of analytics at L0 to replace these guesses. |
| D1 size and concurrency | Workload is ≈ MBs; D1 per-database limit is 10 GB (Paid). A D1 database executes queries serially on one primary, so throughput depends on query time; at tens of writes/day this is not a constraint. Public reads hit Pages static output, not D1. | Re-verify limits at J0. |
| Workers CPU for CSV import | 300 rows parse and validate in well under a second of CPU; Workers Paid allows 30 s CPU by default (configurable higher). Cap: 5 MB / 2,000 rows per file; larger files rejected with a message. Insert in D1 `batch()` chunks inside one batch ID so a failed chunk rolls back that import. | Cap values are our proposal. |
| Media pipeline | Upload via admin Worker to R2 (type sniffed, size cap 10 MB, EXIF stripped). Responsive variants either at build time (Astro image, sharp in CI) or via Cloudflare Image Transformations on the R2 origin. Default: build-time variants (no per-transform cost). | Open: confirm image counts at L0. |
| Search and pagination | Catalogue is ≈ 300 rows: the build emits a JSON index and the browser filters and paginates client-side (as the concept does). No SQL LIKE or FTS5 on the public path. The Console list uses SQL with `LIMIT/OFFSET` and indexed filters; FTS5 only if listings exceed ≈ 5,000. | Decided default. |
| Caching / freshness | No ISR: the site is fully static and every publish triggers a deduplicated rebuild (§5.3). HTML is served with short edge cache and revalidation; hashed assets are immutable. Freshness after publish = build time (to measure, target < 5 min). | Measure in walking skeleton. |
| Draft preview | Preview builds per draft are not planned; the Console renders a draft with the same Astro components server-side behind Access, `noindex`. | Open: confirm effort fits inside Console core hours. |
| Editor concurrency | Optimistic locking: each entity carries `version`; a save with a stale version returns 409 and shows the other editor's change. No real-time co-editing. | Decided default. |
| i18n slugs | Slugs are per locale (`page.slug` unique per `locale`), linked by `translation_of`; French slugs keep today's URLs where the redirect map retains them. | Decided default. |
| Rate limiting on forms | Turnstile on every form plus a per-IP limit on `/api/*` (Workers rate-limiting binding or WAF rule, e.g. 10 posts / 10 min / IP) and a body size cap. | Thresholds to tune on staging. |
| Access session | Session 12 h for admin, re-auth for vault actions if the IdP supports it; revocation by removing the email from the policy and revoking sessions. | Open: vault step-up depends on IdP. |
| D1 migration rollback | Migrations are forward-only (expand/contract). Each migration is applied first to a staging copy of prod; rollback of a bad one is a forward-fix or Time Travel restore to the pre-migration bookmark recorded by CI. | Decided default. |
| Secret rotation | Inventory of secrets (vault key, email API keys, Turnstile, deploy hook) in the runbook with owner and rotation steps; rotate at handover and annually. Vault key rotation needs re-encryption: store a key ID with each ciphertext so old and new keys coexist during rotation. | Key-ID column added to design. |
| GDPR data-subject flows | Access, rectification, erasure via the DSR procedure in §4.6, answered within one month; erasure also covers backups by expiry (30 days / 12 weeks), which the privacy notice must state. | Open: ASSET to name the DSR contact. |
| Audit-log tamper evidence | Append-only table (no update/delete grants in code), each row stores a hash of the previous row (hash chain), and the nightly backup exports it off-platform, so silent edits are detectable. Not tamper-proof against a platform admin. | Decided default. |
| Backup encryption | R2 encrypts at rest; the weekly off-platform copy is encrypted client-side (age or GPG) before upload, key held by ASSET admin and ProdCraft. Vault dump is encrypted separately. | Open: off-platform provider not chosen. |
| Test data | Seed fixtures with fictional listings and fake GM&E codes; staging uses seed data by default, an anonymised prod copy only with ASSET's approval. No real codes outside prod. | Decided default. |
