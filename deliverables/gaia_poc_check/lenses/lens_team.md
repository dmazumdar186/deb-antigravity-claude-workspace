# Lens A — Maddie (developer, builder of Gaia's inbound screener)

Grounding: `PLAN.md`, `maddie/index.html`, `v2_proposal.md`, `check_results.json`, `recruit_crm.py`, `validator.py`.

## Her 10 hardest questions, honest answers

1. **"Does a sourced candidate at 'Sourced' double-fire my inbound trigger?"**
   Not answered, only flagged. `maddie/index.html` "boundary" section says "If a sourced candidate entering at 'Sourced' would fire the inbound trigger twice, the stage name is a config value and we pick one that does not" — that's a promise to fix it if it's a problem, not evidence it isn't one. PLAN.md item 5 lists this as still open, confirmation needed from Maddie via Keith. Real answer: unknown until she names her trigger's actual listen-condition (stage change vs. reply event vs. CV-arrival webhook).

2. **"Is 'verified' verified, or just 'the LLM said so and nobody checked'?"**
   Verified means character-for-character substring match against a cached document by `validator.py` L6 — deterministic, non-LLM, logged to `logs/drops.jsonl` with a published drop rate (0.9% on the live campaign per `v2_proposal.md`). It re-reads the cached doc and drops non-matching quotes outright, never flags-and-keeps (validator.py docstring: "Claims that fail are DROPPED — not flagged, not shown with a warning"). This is a real gate, not prompt-and-pray, for the *quote-exists* claim. It does NOT verify the underlying fact is true or current — see Q4.

3. **"What happens when a firm's people page is stale (someone's been promoted, moved, or left) — do I get a confidently wrong PASS?"**
   Not handled and not claimed to be. The system verifies the quote exists on the cached page, not that the page is current. `check_results.json`'s own corpus is dated (cache built 2026-09-11ish); a promotion after that date produces a PASS with a real, verified, stale quote. Nothing in the docs proposes a re-crawl cadence or staleness flag. This is a genuine gap, not overclaimed — but it's also not disclosed anywhere on Keith's or Maddie's page as a limit, which she'll clock immediately as an omission (see overclaim #1 below).

4. **"Could I build this myself in a weekend?"**
   The quote-matching validator (L6) — yes, a substring check is trivial. The full stack — no: discovery/search-scoping per gate, the typed `JobSpec`/`SeniorityBand`/`LocationRule` gate engine with a composition guard, the CLI override plumbing so a re-cut is a zero-cost gate re-run on cached evidence, the dry-run CRM adapter with dedupe-on-email-or-LinkedIn and empty-field-only writes, 1,086 tests + a 41-check acceptance gate (`v2_proposal.md`) — that's multi-week engineering, not a weekend script. Fair answer: the *idea* (regex a claim against a page) is a weekend; the *guardrails that make it trustworthy at scale* are the actual product, per the validator's own docstring ("This is the product. Everything else is scaffolding.").

5. **"Is the CRM write live or will it silently corrupt my dashboard's data?"**
   Dry-run only, hard-coded default (`maddie/index.html`: "Dry-run is the default: every write is appended to an audit log... and nothing goes over the wire"). Live mode requires `RECRUIT_CRM_API_KEY` + an explicit flag, capped at 50 writes/run. Field-level: `check_row_to_payload` in `recruit_crm.py` writes `custom_fields` (`Shortlist Check`, `Shortlist Check line`, `Shortlist Check brief`) and never touches email/first-name/last-name fields her screener might already own except create-if-absent, fill-empty-only semantics (`upsert` docstring: "Create if absent; if present, fill only EMPTY fields (never [overwrite])"). No live run has happened yet, so this is a design guarantee, unverified against her real account — the code says "the first live run is treated as a contract test against your account, with you watching."

6. **"Does this ever put an email address in front of a consultant with more confidence than you actually have in it?"**
   No, by design, and doubly no for the check path specifically: `card_to_payload`'s docstring states email is included "ONLY when status is verified/catch_all" — a guess or missing email is omitted entirely, status goes in the note instead. `check_row_to_payload` goes further: "No email address is EVER put in this payload... the field is simply never written here" — the check only ever writes a contact *label*, never an address. This is one of the more carefully engineered guarantees in the codebase, and genuinely defensible.

7. **"What's the actual cost and where's the ceiling if something runs away?"**
   Per-name cost breakdown is in `maddie/index.html`: EUR 0.00 for pool match, 0.02–0.05 discovery, 0.05–0.15 extraction (Sonnet-class model), optional 0.12 second-opinion. Per-run and cumulative ceilings enforced in code, loud stop on hit (unquantified in the doc — "the run stops, loudly" isn't a number). The POC itself ran fully offline against the cached pool at EUR 0.00. Fair, but the ceiling values themselves aren't stated, which she may push on.

8. **"Chartership check — Engineers Ireland register, scraped? Because ToS matters."**
   No, explicitly not automated: "The Engineers Ireland register is not automated until its terms are checked; chartership is currently evidenced from the person's own post-nominals and the employer's page" (`maddie/index.html`, "Honest limits"; also PLAN.md item 4). This is disclosed, not overclaimed — good sign for her trust calculus, but it does mean "chartered" gate can be gamed by anyone padding their own bio with unverified post-nominals, since the check verifies the *quote's existence*, not the credential's *truth* with the professional body.

9. **"How does a claim's confidence tier actually gate anything, or is 'inferred' just decoration?"**
   Enforced in code: "Only `confidence = direct` claims can satisfy a hard gate. Inferred claims are shown on the card as 'inferred, not directly stated' and never pass anything" (`maddie/index.html`). Consistent with `validator.py`'s ValidatedClaim/GateResult contract split (claim → validated claim → gate result keyed on a claim_id as basis). This one holds up on inspection.

10. **"Where's the seam if I want to swap in my own scoring instead of PASS/NEAR_MISS/OUT?"**
    Not designed for that at all — the check emits a fixed 4-state status vocabulary (`PASS | NEAR_MISS | OUT | NOT_CHECKED`, mapped 1:1 to CRM labels in `_CHECK_STATUS_LABELS`) plus a `one_line` string and a note built by string concatenation (`check_note`, `evidence_note` — both hand-built line lists, not templated against her schema). There's no documented API/schema version she could target from her own code; "the endpoint is a thin wrapper over the same function" (existing today only as file outputs: JSON, CSV, CRM note) is aspirational, not built. She'd have to consume the custom_fields as-is or ask for a schema change.

## 3 places the Maddie notes page overclaims or is vague

1. **Staleness of the public-page cache is never mentioned as a limit.** The page states the evidence rule in detail (quote-or-drop) but never states "the cache has a build date and a promoted/moved person after that date will show a stale PASS with a real quote." This is a material gap for someone whose job depends on not calling the wrong person, and it's simply absent — not softened, just missing. It belongs next to the existing "Honest limits" box, which currently covers only the Engineers Ireland register and the 8–15yr grade coverage gap.

2. **"The screener's trigger stays Maddie's... its trigger, its scoring, its call. Unchanged"** is stated as settled fact in the flow diagram and boundary box, while PLAN.md (the same author, the internal doc) lists the double-fire question as explicitly open pending her confirmation. The Maddie-facing page reads more confident than the internal plan is. That's the one place a "hard fact" on her page is actually still a hypothesis.

3. **"The endpoint is a thin wrapper over the same function" (delivery options section)** implies an HTTP endpoint exists or is trivial add-on work. Nothing in `recruit_crm.py` or the plan shows an endpoint scaffold — only JSON file, CSV, and CRM note paths are actually implemented ("The first three exist today; the endpoint is a thin wrapper" — the fourth option is unbuilt, and "thin wrapper" is an estimate, not a fact, dressed as one).

---

# Lens B — Isadora (senior consultant, makes the calls)

## Her 8 questions, answered

1. **"Does this mean fewer wrong calls for me?"**
   Directly, yes, for the *specific failure mode* it targets: the August list was 0/13 pass under Keith's own stated brief (all 13 fail seniority ceiling for their role — 10 are Director/Associate Director grade, 2 more are near-miss over the years cap), and that count is now visible before she dials rather than after ("The key word is accurately" — Keith's own framing). It does not reduce wrong calls caused by anything the gates don't check (see Q4).

2. **"Does it slow me down — do I now have to read a report before every call?"**
   No new UI to learn: day-2 decision (a) puts the result as a "Shortlist Check" field + one-line note directly in the Recruit CRM candidate record she already opens, not a separate page (`PLAN.md` §Day 2 decisions (a); `check_row_to_payload`'s `custom_fields`). The one-line field (`row["one_line"]`, ≤20 words per the contract) is built to be read in the time it takes to glance at a status.

3. **"What do I do with a NEAR MISS — call or skip?"**
   The near-miss carries its actual failing margin in plain language, e.g. "evidenced at 26 years' experience, above the 25-year ceiling; everything else passes" (`check_results.json` row, `Gerry Healy`). That's a judgment call left explicitly to her — the system doesn't auto-decide NEAR_MISS the way it hard-blocks OUT names from the check's own "pass" list, but nothing in the CRM note tells her *what a near-miss margin like this typically means for placeability* — that's a gap (see below).

4. **"What if it rejects someone I know is right — a name I've placed before?"**
   No override or "trust the human" path is described anywhere in the two consultant-facing artifacts. The OUT rows currently trigger heavily on "no statement of where they live was found" (residence is absence-of-evidence, not evidence-of-wrongness — e.g. Eddie Lyons and Colin Wilson are both OUT partly for missing residence text, not because they're proven to live abroad). If Isadora knows a name personally, there is no documented path to flag "I vouch for this one" that feeds back into the record — a real, unaddressed workflow gap.

5. **"How do I read this in ten seconds without opening a report?"**
   The CRM note (`check_note` in `recruit_crm.py`) is built to be a short, scannable block: status line, up to 3 rules-failed with reasons, up to 3 evidence quotes + source, contact label, fixed Art.14 line. That's short by design, but it's still a multi-line note, not literally the 10-second glance the custom `Shortlist Check` field + `Shortlist Check line` give her from the dashboard row itself — she gets the fast read from the field, and opens the note only when she wants the "why."

6. **"When a client gets sent the wrong CV, who's on the hook — me, Maddie, or the check?"**
   Not answered anywhere in the four documents. `v2_proposal.md`'s guardrails section talks about brief-lock, evidence-lock, and dry-run-by-default as *technical* fail-safes, but there is no stated accountability line (e.g., "a PASS is Prodcraft's claim; sending it to the client is the consultant's decision"). This is worth asking for explicitly before go-live, especially since PASS/NEAR_MISS/OUT is written straight into her CRM record where a client-facing process might treat it as an endorsement.

7. **"Does it tell me who to call first, or just who's disqualified?"**
   It reports a status and count, not a ranked call order. It's a gate, not a scorer (explicitly contrasted with Recruit CRM's 0–100 match score: "a score says how similar, a check says whether, and why" — PLAN.md item 7). She'd still need her own sense of priority among PASS/NEAR_MISS names; the tool narrows the pool, it doesn't sequence her day.

8. **"Will it ever contact a candidate for me, or is it still my email/call?"**
   Strictly no automated sends to candidates from this stage — the entire check/sourcing flow explicitly stops before any screening invitation or outbound send: "Nothing here replaces any of it... your scoring and your screening call run on them exactly as on applicants" (`maddie/index.html`); `v2_proposal.md`'s "Not in scope" section: "No AI voice calls, no automated sends: Maddie's screener and your consultants own every conversation." Consistent across every document reviewed.

## 2 things missing from the CRM note / page for Isadora

1. **No override/vouch mechanism.** Nothing lets her mark "I know this person, proceed anyway" and have that stick anywhere in the record — a real operational need given engineering recruitment runs partly on relationship memory that a public-record check can't see (e.g., someone whose personal site simply doesn't state a county).

2. **No guidance on what a NEAR_MISS margin means for callability.** The note gives the literal gap (e.g., "1 year over") but no rule of thumb (e.g., "within 2 years of the ceiling, call; more than that, treat as OUT") — she's left to interpret raw gate arithmetic under time pressure with no worked convention supplied anywhere in the docs.
