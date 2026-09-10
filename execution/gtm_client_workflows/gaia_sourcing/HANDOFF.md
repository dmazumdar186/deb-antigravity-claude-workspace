# Gaia Talent Sourcing — Handoff

**Written:** 2026-08-19, end of session 4
**Deadline:** Thursday 20 August 2026
**Status:** Artifact rendered and passing an 18-check acceptance gate.
**Role 1 delivers 10 of 10. Role 2 delivers 3 of 5** — see §3, which is the
only open item that matters.

**Git:** `31ee29e`+ on `fix/split-leads-by-geography`, local only (operator
asks before push).

---

## 1. Where the deliverable stands

`deliverables/gaia_2026-08-20/`

| File | |
|---|---|
| `dossier.html` | 13 cards, 117 evidence claims, every one with a verbatim quote and a link to the document it came from. Self-contained, no external assets. |
| `candidates.csv` | The same 13, flat, for an ATS import. |
| `pool_map_role1.md` / `pool_map_role2.md` | The honest denominator per role. |
| `privacy_notice/` | The Art. 14 notice. **Deployed and live** — see §4. |

Verify before sending anything:

```
cd execution
py -m gtm_client_workflows.gaia_sourcing.tests.acceptance_gaia   # 18 checks, hard-fails
py -m pytest gtm_client_workflows/gaia_sourcing/tests/ -q         # 501 tests
```

---

## 2. What changed this session

The session began as a coverage pass and turned into a bug hunt, because
almost every gap in coverage was hiding something.

**Coverage 43% → 80%. Tests 130 → 501.**

### Bugs that had reached the delivered artifact

1. **`name_from_text` was dead on the normal case.** Its regex carried no
   `re.I` while its sibling gate regex does, so a statement opening "My name
   is Aidan Foley" passed the gate *on that sentence* and then yielded no name
   from it. All three harvesters call it first, so each silently fell back to
   the weaker source it exists to override — for ACP, the filename, which
   names the submitting party rather than the witness.

2. **Irish patronymics written as a separate token were rejected as names.**
   "Seán Ó Ríordáin" and "Sean O Riordain" both failed `_looks_like_name` and
   were dropped from the pool. On a corpus that is entirely Irish engineers.

3. **The employer was read from the last preposition.** Right for "Senior
   Associate Director of Highways in Jacobs", wrong for the far more common
   "Employed by X as \<title\> of \<division\>". Four delivered Role 2 cards
   carried a division, a scheme or a city as their employer: "Environment",
   "Tunnels and Underground Infrastructure", "MetroLink", "Dublin".

4. **The mojibake repair invented a misspelling.** It substituted an
   apostrophe for any U+FFFD between two letters; a mis-decoded fada is also
   between two letters, so "Iarnród Éireann" printed as "Iarnr’d ireann".

5. **Engineers Ireland fellowship failed the chartership gate.** Fellow is the
   grade *above* Chartered Engineer and FIEI is named in the gate's own
   description, but only the abbreviation matched. This cost the transport
   role a Fellow of both Engineers Ireland and the IStructE.

6. **The cost ceiling did not exist.** `max_cost_eur = 30.0` was enforced only
   in `core/llm.py`, which nothing imported. Every layer appended cost
   metadata to a `RUN_COST` list nothing read. Now enforced, cache-aware, and
   exempt from both the retry loop and `run_all`'s per-item containment.
   `core/llm.py` is deleted.

7. **Then the OCR path bypassed the ceiling I had just built**, because it
   calls the Anthropic client directly rather than through `call_role`. It
   drained the account's remaining balance and the tracker saw none of it.
   The lesson is in the code: a ceiling is only as complete as its list of
   call sites.

8. **Two overlapping runs corrupt each other silently, and did.** A background
   extract started before fix 5, finished after it, and wrote its own
   `gate.json` over the corrected one using the code it had loaded at import
   time. Nothing errored; the shortlist just went quietly back to being one
   short. There is now a per-campaign run lock.

9. **`page_mentions_name` could not match an initialised forename** despite its
   docstring promising to, so "B. Murphy" was reported as "may have moved on".

### New capability

**Scanned evidence is now recovered.** 46 of the 72 oral-hearing witness
documents are image-only scans, and on DART+ West that is where the
consultancy witnesses are. Tesseract is not installed, so transcription goes
through the Anthropic API's native PDF reading, with a Gemini free-tier
fallback.

The integrity cost is real and is **not hidden**: L6 checks a quote against
the cached text, and for a scan that text is a model's transcription, so the
check is one model's quote against another model's reading of an image. Those
documents carry `text_source="ocr"` and the card says so next to the quote.
A transcription shorter than a floor proportional to its page count is
refused, because a summarising model produces something short and fluent, and
short-and-fluent would sail through the validator carrying sentences the scan
never had.

25 of 51 scans were recovered before the Anthropic balance hit zero.

---

## 3. Role 2 is 3 of 5. This is a source problem, and here is the exact fix

**Do not solve it by padding.** Six directory-sourced structural engineers
technically pass Role 2's gates; all six are Tier C building engineers at a
Dublin consultancy and none is a transport major-projects manager. Delivering
them would be the failure `output-acceptance-gate.md` exists to prevent.

What the pool actually contains (21 assessed):

- **3 delivered** — Andrew Archer (SYSTRA, Tier A), Gerry Healy (Jacobs),
  Pearse Sutton (Cronin & Sutton).
- **4 client-side**, correctly sidebarred: Aidan Foley (TII), Michael Horan
  (TII), David Vaughan (Iarnród Éireann), David Dineen (CIÉ).
- **4 missing only chartership** — Colin Wyllie, John Kehoe, Ronan Hallissey,
  Sandeep Upadhya, **all at Jacobs**, all transport engineers whose witness
  statements simply do not state a grade.
- The rest are ecologists, acousticians, archaeologists and town planners.
  An oral hearing draws expert witnesses from every discipline; the
  chartership gate rejecting 15 of 21 is correct behaviour, not a bug.

**The cheapest route to 5 is the four near-misses.** Each fails one gate on
one missing fact, and Engineers Ireland publishes a public register of
chartered members. A source plugin that looks up a name there and emits a
`chartership` claim with a verbatim quote would very likely convert three or
four of them. That is a few hours of work and it needs LLM budget.

**Second route:** the 26 scans still unrecovered when the Anthropic balance
ran out. Gemini's free tier resets daily — note it is **20 requests per day
per model**, not the 250 assumed in the workspace model-tier notes.

---

## 4. Budget and infrastructure state

| | |
|---|---|
| Anthropic | **€0** — exhausted by the OCR batch |
| OpenRouter | ~$1.98 |
| Gemini free tier | 20 req/day/model, exhausted; resets daily |
| Prospeo | 1,992 credits |
| Full final run cost | **€0.60** against a €30 ceiling |

The tracker's figure matched OpenRouter's own billing to within two cents —
the first evidence the ceiling measures anything real.

**The Art. 14 privacy notice is deployed and live** at
`https://gaia-privacy.pages.dev/gaia-candidate-notice` (Cloudflare Pages
project `gaia-privacy`), verified by fetch. Outreach drafts now ship.

`privacy.prodcraft.fyi` is bound to the same project but sits at status
`pending`: it needs a CNAME in the `prodcraft.fyi` zone and the API token in
use has Pages permissions but not Zone:Edit. **Once that record exists**,
change the one line in `core/config.py` and re-run `--stage messages --force`
plus the renderer.

**Raise with Gaia:** the notice is signed "Gaia Talent Ltd" but sits on a
prodcraft.fyi domain, so a candidate checking who holds their data sees the
agency's tooling vendor. Legally complete — the body names Gaia as controller
— but a trust detail worth fixing by hosting it under a Gaia domain.

---

## 5. Hard rules (unchanged)

- **I1/I2:** no claim ships without a verbatim quote L6 verifies against a
  cached source. Drop rate is the hallucination metric — **0.9%** on this run.
- **I3:** gates are deterministic Python. L8 may report a finding; only
  deterministic code changes a tier.
- **Off-limits:** no TOBIN or AtkinsRéalis employee anywhere in the output.
- **I5:** never collapse `verified` / `catch_all` / `pattern_guess` / `none`.
- **I6:** Art. 14 notice + opt-out injected as fixed strings, never generated.
- **I7:** Prodcraft never contacts candidates; drafts are for Gaia to send.
- **AM LOCKDOWN:** never touch `execution/infrastructure/api-proxy/`, root
  `HANDOFF.md`, `website-dashboard/`, or use ANYMAILFINDER / MILLION_VERIFIER
  / INSTANTLY / GHL keys. Unrelated project.
- **Ask before `git push`.** Local commits are fine.
- EUR for operator-facing figures. `py`, not `python3`.
- **Bash heredocs in this harness corrupt backslash escapes.** Hit again this
  session on a `\n` inside a test string. Use Write/Edit for anything
  containing escapes.
- **Never run two pipeline processes at once.** Now enforced by a lock, but
  the reason is worth remembering: the older one is running older code.

---

## 6. Running it

```
cd execution
py -m gtm_client_workflows.gaia_sourcing.run --stage all
py -m gtm_client_workflows.gaia_sourcing.run --plan budget --stage messages --force
py -m gtm_client_workflows.gaia_sourcing.render.render
py -m gtm_client_workflows.gaia_sourcing.tests.acceptance_gaia
```

Stages: `harvest_r1`, `harvest_r2`, `harvest_r2_web`, `extract`, `validate`,
`gate`, `deepen_r1`, `adversarial`, `contact`, `movability`, `messages`,
`linkcheck`, `poolmap`, `scorecard`, `render`, `console`, `sync_crm`.
`--from-stage <name>` runs that stage and everything after; `--force`
re-runs a cached stage; `--plan` pins a provider plan (`free` / `hybrid` /
`openrouter` / `anthropic` / `budget`); `--force-lock` overrides the run
lock for a genuinely dead process.

---

## 2026-09-10 -- Brief filters, CRM sync, reply classification

Two promises made on the client call: sourced candidates land in Recruit CRM
(their ATS, screened onward by consultants and their inbound agent Maddie),
and candidate replies get classified immediately. Both built fail-safe by
default; neither has run against a live Recruit CRM account yet.

**New package**: `integrations/recruit_crm.py` -- a REST adapter.
`RecruitCRMClient(live=False)` is the default: every intended write is logged
to `logs/recruit_crm_audit.jsonl` (`dry_run: true`) and nothing is sent;
`live=True` requires `RECRUIT_CRM_API_KEY` (env/.env), never logged. Verified
against the real docs (WebFetch/WebSearch, cited with URLs in the module
docstring): base URL `https://api.recruitcrm.io/v1`, `Authorization: Bearer
<token>`, and that `POST .../candidates`, `GET .../jobs`, `.../candidates/
search`, `.../candidates/{slug}` and an "Assign Candidate" endpoint all
exist. Their exact request/response shape did NOT resolve -- docs.recruitcrm.io
is a Stoplight SPA and a plain fetch only returns page titles -- so
`upsert_candidate`, `add_note` and `attach_to_job`'s payloads are ASSUMED and
flagged as such; treat the first live run as a contract test. Guardrails:
`MAX_WRITES_PER_RUN=50` (`WriteCapExceeded`, never contained per-item, same
shape as `CostCeilingExceeded`), 429/5xx retried up to 3x honouring
Retry-After, every response status audited, dedupe only overwrites EMPTY CRM
fields (never a consultant's edit), and a live write refuses
(`NoDedupeKey`) with neither a verified/catch-all email nor a LinkedIn URL.

**New**: `layers/replies.py` + `ReplyVerdict` (core/contracts.py). Rules first
(bounce, out-of-office, opt-out, negative, positive, question); only genuine
unclear replies reach the LLM (`ROLE_JUDGE`, `use_llm=True` by default), and
any LLM failure or `use_llm=False` yields `unclear`/`human_review`. `opt_out`
is set ONLY by the deterministic unsubscribe/remove-me rule, never by the LLM
path, and MUST be honoured downstream (close, do-not-contact note). Never
drafts or sends anything (I7-adjacent).

**run.py**: new `sync_crm` stage (dry-run unless `--live-crm`; refuses to run
before `contact`; job attachment keyed by `CONFIG.recruit_crm_job_ids`,
empty by default -- attach is skipped with a log line per candidate until
filled in). New flag `--classify-reply "<text>"` prints one `ReplyVerdict` as
JSON and exits. Brief-filter flags from the earlier session are unchanged:
`--max-grade --max-years --min-years --counties --strict-location
--lenient-location`.

**Guardrails re-stated**: Prodcraft never contacts candidates or writes CRM
notes claiming otherwise (I7); the Art. 14 line in every CRM note is injected
verbatim from `core/config.PRIVACY_NOTICE_URL`, never generated (I6); email
statuses are never collapsed (I5); gates/next-actions are deterministic
dicts, the LLM only ever supplies a label (I3); all LLM calls route through
`core/providers.call_role`.

Tests: `tests/test_recruit_crm.py` (25), `tests/test_replies.py` (27), zero
network. Suite: 636 passed (was ~575).

---

## 2026-09-10 (cont'd) -- Radar landed and wired: gates, safety, console, re-cut

The parallel Radar build (RADAR_CONTRACTS.md) landed and is wired into
`run.py`: sources contract + registry (`sources/base.py`, `sources/registry.py`,
`ProviderRecord`/licensed data via `licensed_common._post_json`, the one
sanctioned raw-HTTP exception), identity resolution (`layers/identity.py`),
gate additions (years-subject-is-person, corroborated seniority inference),
`layers/icp_check.py`, opt-out + approval queue + stale evidence + alerts
(section E), eval/scorecard (section F), and the operator console + Modal
re-cut (section G).

**New CLI flags**: `--icp-check` (runs `icp_check_from_gate_json` against
`run/<campaign>/gate.json`, prints the `round N: ...` lines, exits);
`--alert-test` (posts one sample via `core.alerts.alert`, prints whether it
was accepted); `--allow-stale` (threaded into `stage_sync_crm` ->
`sync_delivery(allow_stale=...)`, overriding the stale-evidence skip);
`--coverage-test PROVIDER` + `--niche` (fetches one page from a licensed
source provider -- pdl/crustdata/apollo -- and prints the GO/NO-GO coverage
verdict, or `provider returned HTTP <status>` + a non-zero exit on a
non-200); `--label-export` (writes `run/<campaign>/label_export.jsonl`, a
blind labelling worksheet, then exits); `--kappa LABELS_A LABELS_B` (prints
Cohen's kappa between two labeller JSONL files, then exits);
`--allow-placeholder-notice` (threaded into the `render` stage ->
`render.render.build(allow_placeholder_notice=...)`, rendering without
outreach drafts instead of refusing outright when the Art. 14 notice URL is
not live); `--spend` (prints this run's in-memory spend total and the
persistent cumulative total from `logs/spend_ledger.jsonl`, then exits --
see the spend-guardrail note below).

**New stage `console`** (right after `scorecard`): renders
`render/console.py`'s operator pages to `deliverables/<campaign>/console/`.
**`stage_poolmap` now also writes `health.json`**
(`{campaign_id, generated_at, pool_last_refreshed, stale_days,
integrations: {recruit_crm, alert_webhook, modal_radar}}`, each
"configured"/"missing" per secret/env). `console.py`'s `_health_banner` reads
`stale_days`/`pool_last_refreshed` (old `days_since_refresh`/
`pool_refreshed_at` kept for a legacy fixture); its Pending-approvals table
now reads `outreach_queue.json`'s REAL shape (`state`, not `status`).

**`stage_contact`** now passes each candidate's employer-dimension
RawDocuments into `contact.enrich(employer_docs=...)` (loaded from the same
doc store `validate`/`linkcheck` already use), so `evidence_age_days`/`stale`
are real in a live run, not always `None`.

**`execution/modal_radar.py` moved** from the nested
`gtm_client_workflows/gaia_sourcing/execution/` to the workspace's execution
root (matching RADAR_CONTRACTS.md section G's own path and `directives/
add_webhook.md`'s convention). The pure re-cut/approve logic now lives in
`layers/recut.py` (never imports `modal`); the workspace-root file is a thin
`@app.function` wrapper. `tests/test_modal_radar.py` now tests `layers.recut`
directly.

**`layers/outreach_queue.py`**: `pending_approval -> rejected` is now a
valid transition (a consultant rejecting before ever approving is the common
path) alongside the existing `approved -> rejected`.

**Mechanical check**: `grep -rn "requests\.\(get\|post\)" layers/ sources/
integrations/ eval/ render/` still shows `licensed_common._post_json` (the
sanctioned exception) plus two PRE-EXISTING unsanctioned calls this session
did not introduce and did not fix (out of this task's owned surface):
`sources/linkedin_lookup.py:55` and `sources/acp.py:305` (both Serper
search POSTs). Flagging for whichever agent owns `sources/`.

Suite: 853 passed (was 851).

---

## 2026-09-10 (cont'd) -- Audit fixes: recut auth/validation, spend guardrail,
## identity/queue/icp hardening, opt-out at draft time, secret redaction

Full audit pass across Modal endpoints, sources, identity resolution,
outreach queue, ICP sampling, render/console, spend, and messages/CRM. Every
item behavioural, with a test.

**`layers/recut.py` / `execution/modal_radar.py`**: both endpoints now
require a shared-secret `X-Radar-Token` header matching env
`RADAR_ENDPOINT_TOKEN` (`modal secret create radar-endpoint-token
RADAR_ENDPOINT_TOKEN=<value>`) -- unset means both refuse every request.
`campaign_id`/`role_id` validated (`[A-Za-z0-9._-]{1,64}` + containment
under `run/`) before ever touching the filesystem; errors never echo a
resolved path. `brief_overrides` validated by a pydantic model. Both
handlers take an explicit `run_dir` param so tests never write into the real
`run/` tree. `recut_handler` is now actually re-exported from
`execution/modal_radar.py` (it previously was not). `_apply_overrides`
(recut.py) and run.py's `_apply_brief_overrides` now ALSO update
`spec.seniority_band`/`spec.location_rule`, so `composition_violations`
judges the same overridden brief the gates just ran against.

**Spend guardrail**: `core/providers.py` now keeps a persistent
`logs/spend_ledger.jsonl` (one line per call: at, campaign_id, role, model,
cost_eur) and enforces a NEW cumulative, cross-run ceiling
(`RunConfig.max_cost_eur_total`, default EUR 22 ~= $24) in the same place as
the per-run ceiling -- `call_role` and `core/ocr.py`'s Anthropic
transcription path. `RunConfig.max_cost_eur` (per run) lowered 30 -> 12.
`run.py --spend` prints both totals.

**`layers/identity.py`**: a post-pass (`_split_on_conflicts`) now splits any
cluster that ended up carrying two distinct register_numbers/linkedin_urls
via a TRANSITIVE merge (A~B~C where A and C conflict directly but were never
checked against each other, only against B) -- the pairwise conflict guard
alone did not catch this.

**`layers/outreach_queue.py`**: `_transition`'s read-modify-write now holds
`_LOCK` across the whole operation (`_load_locked`/`_save_locked` helpers,
no lock of their own) instead of two separate locked calls, closing a race
where two threads could both read the same `current` state and one write
clobber the other's. Writes go via temp file + `os.replace`.

**`layers/icp_check.py`**: `min_match` now scales to the sample actually
drawn (`ceil(min_match / sample_n * len(samples))`, capped at the declared
`min_match`), and a population under 5 returns `verdict="INSUFFICIENT_SAMPLE"`
rather than a misleading PASS/RETRY. `IcpVerdict.verdict` gained that literal.

**`render/render.py`**: `e()` no longer blanks a genuine `0` (only `None`
collapses to empty). **`render/console.py`**: `_health_banner` coerces
`stale_days` via `int()` in a try, so a stringified value no longer raises
mid-render. **`run.py`**: `render` (the L13 dossier renderer) is now
registered as its own STAGES entry, before `console` -- previously it was
never wired into the pipeline at all. New `--allow-placeholder-notice` flag
threads through to it.

**`integrations/recruit_crm.py`**: dry-run results now report action
`would_create`/`would_update` (never `created`/`updated`) and `SyncReport`
buckets them separately (`would_create`/`would_update` fields); fixed a
falsy-overwrite bug in the dedupe patch (`existing.get(k) in (None, "")`,
not `not existing.get(k)`, so a genuinely-falsy-but-present CRM field is
never clobbered); the opt-out registry is now loaded ONCE per
`sync_delivery` batch (`optout.load_registry()` + `is_opted_out(rows=...)`)
instead of re-read per candidate. `RecruitCRMError` messages now redact
`Bearer <token>` and any 20+ char token-looking string from `resp.text`
before embedding it.

**`sources/*`**: `licensed_common._post_json` now logs (never headers) on a
non-200/exception and every licensed `fetch()` (pdl/crustdata/apollo)
surfaces a non-200 as `SourceResult.error = "HTTP <status>"`; `run.py
--coverage-test` prints `provider returned HTTP <status>` and exits non-zero
on that instead of a misleading `NO-GO 0/50`, and labels its cost line
`(estimated, placeholder rate)`. A new shared `sources/base.throttle(key,
rate_limit_s)` (lock-guarded, same shape as `core/cache.py`'s own
`_throttle`) replaces three separate unlocked per-module `_last_hit`
globals (engineers_ireland.py, ice.py, istructe.py) and is now also called
from pdl/crustdata/apollo's `fetch()`. Removed an unused `import re` in
engineers_ireland.py.

**`run.py stage_messages`**: now calls `layers.optout.is_opted_out(person=,
contact=)` per delivered candidate BEFORE `messages.draft` -- a hit logs
`"<pid> draft_blocked_optout"` and skips drafting entirely (RADAR_CONTRACTS.md
section E: opt-out checked at draft creation, not just at CRM sync).
**`layers/messages.py`**: both `draft()` return-None sites (empty LLM
output; missing subject/body) now print `"<pid> draft dropped: <reason>"`.
**`run.py _delivery_set`**: the person_ids CUT by the `target_count`
truncation are now logged and written into `delivery.json` as
`overflow[role_id]`, instead of vanishing with no record.

**Three previously-silent `except Exception` sites** (`run.py load_docs`,
`eval/outcomes.py load_outcomes`, `core/cache.py`'s `_extract_title`) now
each print a one-line "skipped X because Y" before continuing/returning
None.

**`.gitignore`**: `logs/` added to this package's own .gitignore;
`deliverables/*/console/` added to the workspace .gitignore. `git log
--stat -- '*/gaia_sourcing/logs/*'` shows `logs/drops.jsonl` WAS committed
(commit `cad40c1`, 2026-08-25, unrelated to this pipeline -- an
instantly_reply_notifier commit that happened to touch a same-named path)
and remains tracked in the working tree today, containing real candidate
PII/quotes from public oral-hearing documents. Not rewritten or untracked
here per instructions (no history rewrite) -- flagged for the operator to
decide (`git rm --cached` at minimum, ideally a history scrub given it is
PII).

Suite: 927 passed (was 853).
