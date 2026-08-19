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
`linkcheck`, `poolmap`. `--from-stage <name>` runs that stage and everything
after; `--force` re-runs a cached stage; `--plan` pins a provider plan
(`free` / `hybrid` / `openrouter` / `anthropic` / `budget`); `--force-lock`
overrides the run lock for a genuinely dead process.
