# Gaia Talent Sourcing — Handoff to next context window

**Written:** 2026-08-19, end of session 2
**Deadline:** Thursday 20 August 2026
**Status:** ~75% built. All layers now exist except the orchestrator and the
renderer. **STILL NO DELIVERABLE ARTIFACT.** That is the whole of the
remaining risk.

The copy-paste prompt for the next session is in the fenced block at the
bottom of this file. Everything above it is the durable record.

**Git:** committed locally at `51b4d3c` on branch
`fix/split-leads-by-geography`. Not pushed (operator asks first).

---

## 1. What is verified working (measured, not assumed)

| Thing | Evidence |
|---|---|
| L6 validator (the product) | 22/22 tests pass incl. all §14 adversarial fixtures |
| L12 name matching | 8/8 Irish-surname cases: O'Brien / O Brien / OBrien / Mac Eoin / Ni Chuinn all resolve; "Murphy Construction Ltd" correctly does NOT match Michael Murphy |
| L11 compliance gate | `compliance_ok()` returns clean on an assembled sequence; Art.14 + opt-out are concatenated constants, unreachable by model output |
| Prospeo L9 contract | Probed live — see correction 7. Account: STARTER, **2000 credits, 0 used**, renews 2026-08-30 |
| Role 2 source: ACP witness statements | 19 named professionals, 2 cases, 0 junk after text gate |
| Role 2 extraction | 365 claims → 354 validated, **3.0% drop rate** (ceiling 15%) |
| Role 1 source: Firecrawl-rendered staff directories | 42 people from 1 firm, **0.0% drop rate**, €0.24 |
| Role 1 gating | 15 qualified from 1 firm (13 C, 2 B) |
| Gate discrimination | Correctly excluded RTPI planners, Chartered Environmentalists, archaeologists, acousticians, M&E, finance, Belfast + Birmingham offices |

## 2. What is NOT built

**Ship-critical, in priority order:**

1. **`run.py` orchestrator** — nothing wires the layers together yet. Every
   layer has been exercised in isolation; none has been exercised in
   sequence. This is the single biggest unknown left.
2. **L13 renderer** (`render/render.py`) — `dossier.html` + `candidates.csv`
   + `pool_map_role{1,2}.md`. Requirements in SPEC.md §15 "Render
   requirements". Self-contained, no CDN, print stylesheet, card order fixed.
3. **Source scaling** — the only reason Tier S is not reachable today. See §4.
4. **Test bed beyond the 22 unit tests** — see the TEST BED block in the
   prompt.
5. **Art. 14 privacy notice** on Cloudflare Pages, replacing
   `PRIVACY_NOTICE_URL` in `core/config.py`. `render.py` must hard-fail while
   it is still the placeholder.

Layers L8/L9/L10/L11/L12 are **written but never run against real data**.
Treat their first live run as a debugging session, not a formality.

## 3. Eight corrections to SPEC.md (carry these forward — they cost hours to find)

1. **§6 source 3 is wrong for Ireland.** Irish consultancies mostly do not
   serve per-engineer bios in static HTML. 7 of 18 domains did not resolve;
   rod.ie "profiles" are graduate blog posts with zero chartership.
   `ocsc.ie/people/` over plain HTTP: 0 occurrences of "CEng". Rendered
   through Firecrawl: 42.7k chars, 30x "CEng", 32x "MIEI".
   **Firecrawl is mandatory for Role 1, not optional.**
2. **§15 block order inverts.** ACP (block D) is the highest-value source and
   partly obviates Engineers Ireland (block C) — witness statements
   self-evidence chartership better than a register lookup.
3. **`temperature` is deprecated on Claude 5** — HTTP 400 "temperature is
   deprecated for this model". §4's temperature=0 determinism is unachievable;
   determinism now rests on forced tool use, so §14's determinism test matters
   MORE, not less.
4. **Hard 60-second ceiling on any single outbound request in this
   environment.** 60k-char extraction died at exactly 60.2s; the same call at
   8k returned in 12s. Chunk everything. (Chunking also improved recall.)
5. **Serper cannot reach ACP's `/publicaccess/` tree.** `site:pleanala.ie
   "Witness Statement of"` returns 0 organic results. Case pages must be
   parsed directly (acp.py does this). Broad queries DO find scheme-specific
   consent sites, which is a separate, useful channel.
6. **An Bord Pleanála was renamed An Coimisiún Pleanála** (June 2025). Case
   refs are now `ACP-`. Directory listing under /publicaccess/ is 403, but
   the case page HTML lists every document.
7. **§10's contact stack does not exist as written.** Dropcontact and Hunter
   were never provisioned; PROSPEO was. And every Prospeo tutorial online is
   stale — verified live 2026-08-19:
   - `/email-finder` and `/domain-search` are **DEPRECATED**, HTTP 400
     `{"error_code":"DEPRECATED"}`.
   - The live endpoint is **POST `https://api.prospeo.io/enrich-person`**,
     headers `X-KEY` + `Content-Type`, body
     `{"only_verified_email":bool,"enrich_mobile":bool,"data":{...}}`.
   - `data` accepts `{linkedin_url}` OR `{first_name,last_name,company_name,
     company_website}`.
   - **A miss returns HTTP 400 with `{"error_code":"NO_MATCH"}`, not an
     empty 200.** A client that treats 4xx as fatal reads every miss as an
     outage. `layers/contact.py::_post` handles this.
   - Emails come back **unmasked** (`eoghan@fin.ai`) with
     `verification_method: "SMTP"`. Masked addresses do exist; treat any
     address containing `*` as no-address rather than shipping it.
   - Cost: 1 credit per email found, 0 for a miss or a 90-day re-enrich.
8. **pytest must be run from `execution/`, not from the workspace root.**
   The test module imports `gtm_client_workflows.gaia_sourcing.*`, so
   `cd execution && py -m pytest gtm_client_workflows/gaia_sourcing/tests/ -q`.
   From the root it fails collection with `ModuleNotFoundError`, which reads
   like a broken test suite and is not one.

## 4. The Tier S mandate and the ONLY legitimate way to satisfy it

The operator requires **10 + 5 top-tier candidates, no compromise**.

SPEC.md has no Tier S. Define it as: **all hard gates passed + >=2 `direct`
claims on the role's primary signal + adversarial pass clean + live
name-matched profile URL + contact route identified.**

Currently most candidates land Tier C because staff directories do not
evidence `technical_skill` (Eurocode / Tekla / Robot) for Role 1, and only
2 of 5 Role 2 candidates qualify from 2 seeded cases.

**FORBIDDEN routes to Tier S** (these manufacture quality that does not exist
and are exactly what SPEC.md I1/I2/I3 and §7 exist to prevent):
- Relaxing any hard gate.
- Letting `inferred` claims count toward tiering.
- Loosening the L6 substring validator or its `normalize()`.
- Broadening `_CHARTERED_RE` to admit non-Engineers-Ireland bodies.
- Lowering the Tier A threshold from 2 primary-signal claims.
- Weakening `layers/adversarial.py::_MATERIAL_RE` so fewer candidates demote.

**REQUIRED route to Tier S — expand sources until Tier A people genuinely
exist in the pool:**
- Role 1: firm PROJECT / case-study pages (these name engineers AND state
  Eurocode/Tekla/BCAR), Engineers Journal, IStructE + ICE Ireland event and
  paper listings, conference proceedings, award submissions.
- Role 1: run the Firecrawl directory path across ALL firms in
  `company_bios.FIRMS`, not just ocsc.ie. One firm already produced 15
  qualified; ~18 firms should produce a deep pool.
- Role 2: seed far more ACP cases. The mechanism works; it needs volume.
  Every major road / rail / CPO scheme with an oral hearing is a case.
- Role 2: the scheme-consent-site channel (`oral_hearing_web.py`) —
  n6galwaycityringroad.ie, ringaskiddyrrc.ie, dublinportmp2foreshoreconsent.ie
  and similar publish full oral-hearing bundles.

If after genuine source expansion Tier S cannot reach 10+5, **say so
explicitly with the pool map numbers** rather than padding. SPEC.md §2.2
exists for exactly this and tiering with stated gaps beats invented
confidence.

## 5. Hard rules (do not violate)

- **I1/I2:** no claim ships without a verbatim quote that L6 verifies against
  a cached source document. Dropped claims are dropped silently, logged to
  `logs/drops.jsonl`. Drop rate is the hallucination metric.
- **I3:** gates are deterministic Python. Never LLM judgement, never weighted.
  L8 may report a finding; only deterministic code may change a tier.
- **Off-limits:** no TOBIN or AtkinsRéalis employee anywhere in the output.
- **I7:** Prodcraft never contacts candidates; all messages are drafts for
  Gaia to send.
- **I6:** Art.14 GDPR notice + opt-out injected as fixed strings, never
  LLM-generated. Operator chose Cloudflare Pages hosting for the notice.
- **I5:** never collapse `verified` / `catch_all` / `pattern_guess` / `none`.
  Unknown upstream statuses degrade downward, never upward.
- **AM LOCKDOWN:** never touch `execution/infrastructure/api-proxy/`, root
  `HANDOFF.md`, `website-dashboard/`, or use ANYMAILFINDER / MILLION_VERIFIER
  / INSTANTLY / GHL keys. This project is unrelated to Accessory Masters.
- **Currency:** all operator-facing figures in EUR.
- **Ask before `git push`.** Local commits are fine.
- Windows: use `py`, not `python3`.

## 6. Environment facts

- Anthropic API **is funded** (topped up mid-session 2026-08-19).
  `providers.autoselect_plan()` probes and selects automatically.
- PROSPEO: STARTER plan, **2000 credits remaining, 0 used**, quota renews
  2026-08-30. At 1 credit per found email, enrichment for 15 candidates plus
  a generous margin for misses is not a budget concern.
- Authorised paid APIs: Anthropic, Serper, Firecrawl, Tavily, PROSPEO.
- Models verified live: `claude-opus-5`, `claude-sonnet-5`.
- Python 3.14. Deps present: pydantic 2.13.3, requests, bs4, PyMuPDF,
  anthropic 0.97.0, email-validator.
- **Bash heredocs in this harness corrupt backslash escapes** — `\b` became
  literal 0x08 bytes in a regex and silently broke it. Use the Write/Edit
  tools for any file containing regex escapes, never a heredoc.

## 7. Code map

```
execution/gtm_client_workflows/gaia_sourcing/
  roles.py             L1 -- ROLE1 + ROLE2 JobSpecs, hand-written (see
                       module docstring for why the LLM parser was skipped).
                       Also CLIENT_SIDE_BODIES + is_client_side() for the
                       SPEC 2.3 sidebar.
  core/contracts.py    Pydantic models (structure only; business rules in gates)
  core/config.py       secrets, models, EUR pricing, GDPR strings
  core/cache.py        fetch / fetch_raw / fetch_rendered (Firecrawl) / head_ok
  core/providers.py    role-based multi-provider dispatch + autoselect_plan
  core/llm.py          older Anthropic-only wrapper + CostTracker (superseded
                       by providers.py for dispatch; CostTracker still useful)
  layers/validator.py  L6 -- THE PRODUCT. normalize() + validate_claim()
  layers/gates.py      L7 -- deterministic gates + assign_tier
  layers/extract.py    L5 -- extract_from_document + extract_directory (chunked)
  layers/adversarial.py  L8 -- BLIND critique. build_user_prompt() is pure and
                       never receives tier/gates; deterministic _demote()
                       applies the tier change. Also unverified_lines() and
                       inferred_claim_lines() for the SPEC 13 Unknowns block.
  layers/contact.py    L9 -- Prospeo enrich-person + pattern fallback, honest
                       I5 labels, I8 channel recommendation.
  layers/movability.py L10 -- unknown-by-default + deterministic
                       geographic_friction()
  layers/messages.py   L11 -- drafting + assemble() (injects legal strings) +
                       compliance_ok() pre-render gate
  layers/linkcheck.py  L12 -- head_ok liveness + page_mentions_name()
  sources/acp.py       An Coimisiun Pleanala case pages + witness statements
  sources/company_bios.py   firm list, people-index discovery, bio harvest
  sources/oral_hearing_web.py  scheme-site evidence discovery via Serper
  tests/test_gates_and_validator.py  22 tests, all passing
  render/             EMPTY -- L13 goes here
  run.py              DOES NOT EXIST YET -- the orchestrator
```

---

## 8. COPY-PASTE PROMPT FOR THE NEXT SESSION

See the fenced block rendered in chat, and reproduced here:

```
Continue the Gaia Talent sourcing build. Deadline: Thursday 20 August 2026.

FIRST: read these two files completely before writing any code.
  1. C:\Users\deban\Downloads\Recruitment and Staffing 12 Aug 26 - by location\SPEC.md
  2. execution\gtm_client_workflows\gaia_sourcing\HANDOFF.md

The SPEC is authoritative on WHAT to build. The HANDOFF carries EIGHT
corrections to it that were found by hitting reality and that will cost you
hours if you ignore them (Firecrawl mandatory for Role 1, temperature
deprecated on Claude 5, hard 60s request ceiling, Serper can't reach ACP
publicaccess, ACP renamed, PROSPEO's documented endpoints are deprecated and
a miss is an HTTP 400, pytest must run from execution/, heredocs corrupt
regex escapes).

STATE: layers L5-L12 and roles.py all exist and are committed locally at
51b4d3c. L8/L9/L10/L11/L12 have never been run against real data — treat
their first live run as a debugging session, not a formality. There is still
no run.py and no renderer, so there is still no artifact.

MISSION
Deliver SPEC.md §19 Definition of Done in full: exactly 10 Senior Structural
Engineer + exactly 5 Transport Major Projects Manager candidates, every one
TOP TIER (all hard gates + >=2 direct primary-signal claims + adversarial
clean + live name-matched URL + contact route), in a self-contained
dossier.html plus candidates.csv plus pool maps per role.

Achieve top tier by EXPANDING SOURCES until genuinely top-tier people exist
in the pool. Never by relaxing a gate, never by letting inferred claims
count, never by loosening the L6 validator, never by weakening the
adversarial demotion rule. If top tier cannot reach 10+5 after real source
expansion, say so with pool-map numbers instead of padding.

BUILD ORDER
 1. run.py orchestrator + L13 renderer FIRST, end to end on the ~93 documents
    already in the fetch cache, so an artifact exists within the first hour
    and every later change is visible in the thing the client actually reads.
    Resume from run/<campaign_id>/L*/ JSON so re-runs cost nothing.
 2. Scale sources: Firecrawl directory path across all firms in
    company_bios.FIRMS; firm PROJECT/case-study pages for Eurocode/Tekla
    evidence (this is what unlocks Tier A for Role 1); many more ACP cases
    plus the scheme-consent-site channel for Role 2.
 3. First live run of L8 adversarial, L9 PROSPEO enrichment, L10 movability,
    L11 messages, L12 link liveness. Expect bugs; they have unit shape but no
    field miles.
 4. Deploy the Art.14 privacy notice to Cloudflare Pages and replace
    PRIVACY_NOTICE_URL; render.py must hard-fail on the placeholder.

TEST BED — build it, do not skip tiers
Unit, integration/SIT, end-to-end, adversarial fixtures, regression, smoke,
sanity, monkey/fuzz, performance, security, network-failure, UX/UI
(dossier.html renders offline, no CDN, responsive, prints, opens on mobile),
data handling, error handling, API-contract, and determinism. Every
deterministic layer tested with zero network against golden fixtures in
tests/fixtures/. The hallucination test must run on every commit. Add a test
asserting adversarial.build_user_prompt() leaks no tier letter or gate
verdict — that blindness is what makes pass 2 worth running.

Then run the full suite and the mandatory audit stack, and report a verdict
table. Do not claim done until §19 is met item by item.

CONSTRAINTS
Anthropic is funded; providers.autoselect_plan() picks the plan. PROSPEO has
2000 credits, 0 used. Authorised: Anthropic, Serper, Firecrawl, Tavily,
PROSPEO. Never TOBIN/AtkinsRealis candidates. Never AM-locked paths or keys.
EUR for operator-facing figures. Ask before git push. Use `py` on Windows.
Use Write/Edit for files with regex escapes, never bash heredocs.
```
