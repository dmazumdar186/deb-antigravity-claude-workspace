# Gaia Talent Sourcing — Handoff

**Written:** 2026-08-19, end of session 3
**Deadline:** Thursday 20 August 2026
**Status:** Pipeline runs end to end and produces an artifact. The remaining
risk is no longer "does it work" but "is the pool deep enough" — see §4.

**Git:** `76948e9` on branch `fix/split-leads-by-geography`, local only
(operator asks before push).

---

## 1. What changed this session

The build went from "every layer exists, nothing connects them, no artifact"
to "runs end to end, produces `deliverables/gaia_2026-08-20/`".

| Added | What it is |
|---|---|
| `run.py` | L0 orchestrator. 12 named, resumable stages; each persists to `run/<campaign>/<stage>.json` so a crash never re-buys a paid stage. Extraction is incremental by `doc_id`. |
| `render/render.py` | L13. Self-contained `dossier.html` (no CDN, print stylesheet, responsive), `candidates.csv`, per-role pool maps. |
| `sources/technical_evidence.py` | Per-candidate search for Role 1's primary signal. See §4. |
| `tests/test_pipeline.py` | Adversarial blindness, I6 legal injection, I5 contact honesty, Irish surnames, client-side classification, L5 subject confirmation. |
| `tests/test_render.py` | Asserts on what a reader sees, not on whether a function returned. |
| `deliverables/.../privacy_notice/index.html` | The Art. 14 notice, written and ready. **Not deployed** — see §5. |

**Test state: 84 passing**, run from `execution/`.

---

## 2. Five real bugs found by running it

Each was invisible to the unit tests that existed before, and each was found
by putting real data through the pipeline. That is the argument for running
the thing rather than testing its parts.

1. **`autoselect_plan()` was never called.** Every extraction had been routing
   to free-tier Gemini with 6.5 s of enforced spacing despite a funded
   Anthropic account. The first extract run took 30+ minutes and was killed;
   the same work on `claude-sonnet-5` takes about six.

2. **A 200 that parsed to no text was cached as a VALID empty document.**
   An Coimisiún Pleanála publishes image-only scanned PDFs — 1.1 MB of JPEG,
   no text layer. `content_id("")` is the SHA of the empty string, so **51
   distinct sources had collapsed onto one `doc_id`**. Nothing false shipped,
   because the validator fails closed against an empty document, but the drop
   then reads as a hallucination rather than as "this source was never
   readable". Now recorded as `error: empty_after_parse`.

3. **L5 discarded every claim when the model omitted `subject_confirmed_name`.**
   The guard exists so an UNKNOWN subject can be identified from the document.
   But when the subject is *supplied* in the prompt, models routinely omit the
   optional field they were just handed — and the guard treated that as "could
   not identify the subject". Result: all 19 oral-hearing statements returned
   good claims, all 19 were thrown away, **Role 2 delivered zero candidates
   from a working source**. Now: an omitted echo is fine and the check is
   deterministic (the surname must appear in the document body); a
   *contradictory* echo is still fatal.

4. **`ThreadPoolExecutor.map` re-raised the first worker exception and killed
   the stage.** A single unpacking error in the Role 2 branch cost ~190
   already-extracted Role 1 people, because stages only save at the end.
   Replaced with `run_all()`, which degrades by one item instead of by one
   batch. A stage is a batch of independent work; one bad item must never
   cost the batch.

5. **Role 2 employer was read from the filename's submitting party.** An
   oral-hearing document is titled `No.02 - TII - Witness Statement of Aidan
   Foley`, but the witness is usually that party's *consultant*. Susie Coyle's
   statement opens "I am an Associate Director in Jacobs" under a TII
   filename. Reading the party as the employer filed consultancy engineers as
   client-side and dropped them from the shortlist for being the wrong kind of
   right person. The witness's own words now win.

Plus a sixth, smaller: a claim occasionally comes back as a bare string
instead of the object the schema asks for, and `extract_from_document` had no
`isinstance` guard (`extract_directory` did) — one malformed item took a whole
document's claims with it. Dropped, never repaired: reconstructing a missing
`evidence_quote` is exactly how an unevidenced assertion would enter.

Two artifact-quality fixes on top: **duplicate claims** (the same staff page
fetched as `ocsc.ie/people` and `www.ocsc.ie/people` renders twice, and
Firecrawl output varies enough that `claim_id` does not collapse them — this
both double-printed every bullet and inflated the primary-signal count that
decides the tier), and a **narrow mojibake repair** so `Michael O<FFFD>Reilly`
does not appear on a card that promises verbatim quotes.

---

## 3. Source corrections (the previous list was largely guesswork)

**Firms.** Eight of the eighteen domains in `company_bios.FIRMS` did not
resolve at all — `cseassociates.ie`, `watermanmoylan.ie`, `garland.ie`,
`ftco.ie`, `bmce.ie`, `caseyodonnell.ie`, `kmce.ie` — and `byrnelooby.com`
now redirects to its acquirer Ayesa, whose site has no per-engineer bios.
They had been assembled by guessing a `.ie` domain from a firm name.
Corrected against live DNS, plus `barrettmahony.com` (the firm trades as
BMCE), `horganlynch.ie` (Cork-domiciled, which matters for Role 2),
`kilgallen.ie`, `tjoc.ie`, `downesassociates.ie`.

Harvest went from 9 directory pages / 6 firms to **16 pages / 12 firms**.

**ACP cases.** The previous `SEED_CASES` list was invented; nine of ten
returned nothing, which is the correct behaviour for a case number that does
not exist. Replaced with fourteen verified references — MetroLink `314724`
(54 witness statements), DART+ West `314232`, DART+ Coastal North `320164`,
N6 Galway City Ring Road `302885`, six BusConnects corridors, Dublin Port MP2
`310286`.

**Firecrawl `map` is the right discovery tool**, not homepage link-scraping.
`find_people_indexes()` reads raw HTML, which is empty on the client-rendered
sites that make up most of this sector. `firecrawl_map` with `search="team"`
found the real path in one call per firm.

---

## 4. The Role 1 tier ceiling — measured, not assumed

Role 1's primary signal is `technical_skill`. Tier A needs two **direct**
claims on it. Across all sixteen Firecrawl-rendered staff-directory pages:

| term | occurrences |
|---|---|
| eurocode | **0** |
| tekla | **0** |
| etabs | **0** |
| robot structural | **0** |
| BCAR | **0** |
| assigned certifier | 1 |
| CEng | 30 on `ocsc.ie` alone |
| MIEI | 32 on `ocsc.ie` alone |

Staff directories evidence **chartership and grade richly, and technical
competence not at all**. A firm's "our people" page says "Brian is an
Associate Director with 18 years across commercial and residential projects";
it never says "Brian designed the transfer structure to EN 1992-1-1".

So the directory alone caps every Role 1 candidate at Tier C, and re-reading
it more carefully cannot change that. **This is a source gap, not a tiering
problem**, and the only legitimate fix is another source.

`sources/technical_evidence.py` is that source: per gate-passing candidate, it
searches the places where an Irish structural engineer's technical work IS
attributed by name — Engineers Ireland / Engineers Journal bylines (which
carry the grade: "Author: Colin Short, Chartered Civil Engineer Dip Eng,
CEng"), ACEI and IStructE award citations, conference proceedings, and the
firm's own project pages, which name the engineer far more often than the
people page does. It runs only on candidates that already passed every hard
gate, so the budget goes to the twenty-odd people who might ship.

**Still forbidden**, and none of it was done: relaxing a gate, letting
`inferred` claims count, loosening the L6 validator, broadening
`_CHARTERED_RE`, lowering the Tier A threshold, weakening `_MATERIAL_RE`.

---

## 5. Open items

1. **The Art. 14 privacy notice is written but not deployed.** Every outreach
   draft cites `PRIVACY_NOTICE_URL`, which currently returns nothing. The
   renderer refuses to emit outreach in that state and prints a banner
   explaining why — outreach citing a dead notice URL is worse than no
   outreach. The page is at
   `deliverables/gaia_2026-08-20/privacy_notice/index.html`; deploying it is
   an outward-facing action and needs the operator's go-ahead. Once live,
   update `core/config.py` and re-run `--stage messages` plus render.

2. **Scanned ACP documents are unreachable.** Roughly half the witness
   statements on the older cases are image-only PDFs. OCR would recover them;
   nothing else will. Not attempted.

3. **`302885`, `320164` and the BusConnects cases yielded nothing** through
   `witness_statements()`. Worth checking whether their document naming
   differs from MetroLink's `No.NN - PARTY - Witness Statement of NAME` shape.

---

## 6. Hard rules (unchanged)

- **I1/I2:** no claim ships without a verbatim quote L6 verifies against a
  cached source. Drops are silent, logged to `logs/drops.jsonl`. Drop rate is
  the hallucination metric — **0.0% on the current run**.
- **I3:** gates are deterministic Python. L8 may report a finding; only
  deterministic code changes a tier.
- **Off-limits:** no TOBIN or AtkinsRéalis employee anywhere in the output.
- **I5:** never collapse `verified` / `catch_all` / `pattern_guess` / `none`.
  Unknown upstream statuses degrade downward.
- **I6:** Art. 14 notice + opt-out injected as fixed strings, never generated.
- **I7:** Prodcraft never contacts candidates; drafts are for Gaia to send.
- **AM LOCKDOWN:** never touch `execution/infrastructure/api-proxy/`, root
  `HANDOFF.md`, `website-dashboard/`, or use ANYMAILFINDER / MILLION_VERIFIER
  / INSTANTLY / GHL keys. Unrelated project.
- **Ask before `git push`.** Local commits are fine.
- EUR for operator-facing figures. `py`, not `python3`.
- **Bash heredocs in this harness corrupt backslash escapes.** `\b` became a
  literal 0x08 byte inside a regex this session and silently broke it — the
  same failure the previous handoff warned about. Use Write/Edit for anything
  containing regex escapes.

---

## 7. Running it

```
cd execution
py -m gtm_client_workflows.gaia_sourcing.run --stage all
py -m gtm_client_workflows.gaia_sourcing.render.render --allow-placeholder-notice
py -m pytest gtm_client_workflows/gaia_sourcing/tests/ -q
```

Stages, in order: `harvest_r1`, `harvest_r2`, `extract`, `validate`, `gate`,
`deepen_r1`, `adversarial`, `contact`, `movability`, `messages`, `linkcheck`,
`poolmap`. `--from-stage <name>` runs that stage and everything after;
`--force` re-runs a cached stage.
