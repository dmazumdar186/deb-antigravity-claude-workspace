# Two lenses on Shortlist Check — Gaia Talent / Recruit CRM

Prepared 2026-09-13. Read alongside `deliverables/gaia_poc_check/PLAN.md`,
`deliverables/gaia_poc_check/recruit_crm_capabilities_2026-09.md`,
`deliverables/gaia_2026-09-10/v2_proposal.md`, `execution/gtm_client_workflows/gaia_sourcing/RADAR_CONTRACTS.md`,
`layers/optout.py`, `integrations/recruit_crm.py`.

---

## A. The Irish data-protection solicitor's honest read

This is not legal advice; it is a issue-spotting memo for Keith and the operator to
take to an actual solicitor before Shortlist Check goes into any production
recruiter workflow. Each item is marked **SETTLED** (well-established, low
risk to argue about), **JUDGEMENT CALL** (defensible position exists, reasonable
people differ, document the reasoning), or **ASK A LAWYER** (repo does not
and should not try to resolve this itself).

### 1. Lawful basis — legitimate interest (Art. 6(1)(f))
**JUDGEMENT CALL, leaning settled.** Sourcing professional data from public
sources for recruitment is a textbook legitimate-interest case and the repo
already frames it that way (`GDPR_ART14_NOTICE` in `core/config.py`: "We
process it under legitimate interest (GDPR Art. 6(1)(f))"). The three-part
test (purpose, necessity, balancing) is reasonably strong here: engineers who
list their credentials and projects on a firm bio page or give sworn evidence
at a public oral hearing have a lower expectation that a recruiter won't read
it than, say, someone whose data leaked. But legitimate interest is not a
free pass — it requires a documented Legitimate Interest Assessment (LIA),
which the repo does not appear to have as an artifact (only the notice text
exists). **Gap to close before this scales past a POC: write the LIA, one
page, and keep it on file** — this is what a DPA asks for first if anyone
complains.

### 2. Article 14 notice timing
**SETTLED that the repo has a notice; JUDGEMENT CALL on timing.** Art. 14(3)
requires the notice at first communication at the latest, or within a
reasonable period (max one month) if there is no direct contact planned. The
repo injects `GDPR_ART14_NOTICE` "verbatim, never generated" (per
`evidence_note`/`check_note` docstrings) into every outreach draft — that
satisfies "at first communication" for anyone actually contacted. **The open
question is the Shortlist Check product specifically**: `check_note` writes an
Art. 14 line into the CRM note for every checked name, including the ones
marked OUT and never contacted. Writing the notice text into an internal CRM
note is not the same as *giving* it to the data subject — for a rejected
person Gaia never messages, no Art. 14 notice has actually been delivered.
The **Art. 14(5)(b) "disproportionate effort" exemption** may cover this (it
exists specifically for cases like bulk sourcing from public registers), but
regulators construe it narrowly and it is not automatic — a controller
relying on it should still take "appropriate measures to protect the data
subject's rights," which the ICO and the GDPR text both suggest can mean a
generally published notice (e.g., a page on Gaia's own site saying "we source
candidate data from public professional records under legitimate interest,
here's how to object") rather than nothing. Gaia's `PRIVACY_NOTICE_URL`
(`https://gaia-privacy.pages.dev/gaia-candidate-notice`) is exactly this kind
of generally-published notice, which is the right shape of answer — **but it
is currently pending a working custom domain** per the code comment in
`core/config.py` ("privacy.prodcraft.fyi... sits at status 'pending'"). Until
that page is live and stable at a Gaia-branded URL (not a `.pages.dev`
staging domain, which looks unprofessional and non-authoritative to a
data-subject or a regulator), the Art. 14(5)(b) argument is weaker than it
should be. **ASK A LAWYER**: whether logging the notice text in an internal
CRM note (never seen by the data subject) does anything at all toward Art.
14 compliance for people never contacted, or whether it's purely an internal
audit trail (which is still useful, just not the same thing).

### 3. Retention of cached page copies and quotes
**JUDGEMENT CALL.** Art. 5(1)(e) (storage limitation) requires data kept "no
longer than necessary." The repo has a *staleness* concept
(`evidence_age_days`, `max_evidence_age_days` default 30 in
`RADAR_CONTRACTS.md` §E) but staleness governs whether evidence is fresh
enough to *act on*, not how long the underlying cached quote/page copy is
*retained*. No explicit deletion/retention-period logic was found in the
files read. `GDPR_ART14_NOTICE` promises "our retention period" is disclosed
at the privacy-notice URL — so the retention period needs to actually exist
as a stated, applied number (e.g., "cached evidence deleted after 12 months
or on request") for that sentence not to be a false statement. **Gap**:
define and implement an actual retention/deletion job for `logs/` and
`run/<campaign>/` cache artifacts, or at minimum document the period in the
privacy notice page and confirm someone will action it manually.

### 4. A "rejected, reason: grade" verdict about a named person in a CRM
**JUDGEMENT CALL, two sub-questions.**
- *Is it profiling under Art. 4(11)/22?* Probably not in the Art. 22 sense
  (automated decision with legal/similarly-significant effect, no human in
  the loop) — Shortlist Check's own design keeps a human consultant reading
  the note before any outreach decision, and I3 in `RADAR_CONTRACTS.md`
  ("deterministic code decides; a classifier... a much harder thing to
  reason about") plus the whole approval state machine in `optout.py`/§E
  shows a human always sits between the verdict and any contact. It *is*
  "profiling" in the broader Art. 4(4) sense (automated evaluation of
  personal aspects — professional grade, residence). That's not prohibited;
  it just means Art. 13/14 transparency obligations about the *logic
  involved* apply, and the repo's evidence-and-reasons format (`check_note`:
  rules failed + label + reason, quotes, sources) is actually a strong
  transparency artifact if a data subject ever asked "why was I rejected."
- *Accurate-data risk under Art. 5(1)(d)?* This is the sharper risk. A "grade:
  Director, therefore OUT" verdict is only as accurate as the underlying
  evidence-quote extraction. The repo's own numbers show this is taken
  seriously (verbatim character-by-character validation, "drop rate ...
  published (0.9% last run)" per `v2_proposal.md`, OCR-confusion folding for
  1/l/I, post-nominal stripping so "CEng MIEI" isn't mistaken for a name) —
  that diligence is the actual answer to an Art. 5(1)(d) challenge: "what
  did you do to keep this accurate," not "we're never wrong." **Recommend
  the CRM note always show the exact quote + source link inline** (which
  `check_note`/`evidence_note` already do) so a wrong verdict is
  self-correcting the moment a human looks at it, and a DSAR response can
  show the actual evidentiary basis rather than a bare label.

### 5. Right to object / erasure and the opt-out registry
**SETTLED, well-built.** `layers/optout.py` matches on person_id, email, or
LinkedIn URL — any one — precisely because Art. 21 (object) and Art. 17
(erasure) requests can come in through a channel other than the one the data
was found through, and the docstring explicitly reasons about this
("a candidate might reply from a personal address that never appears on
their CRM record"). `OPT_OUT_LINE` in `core/config.py` gives a one-word STOP
mechanism promising erasure and no further contact, and `optout_from_reply`
is checked "at draft creation and at sync" per `RADAR_CONTRACTS.md` §E — this
is a real technical control, not just a policy statement. **Open item**: the
registry blocks future *contact and CRM sync*, but does it also trigger
deletion of the *already-cached* evidence/quotes for that person, per the
"we will erase your details" promise in `OPT_OUT_LINE`? Not confirmed from
the files read — worth checking that opt-out actually purges `logs/` and
cache entries, or the OPT_OUT_LINE promise ("erase your details") overstates
what the code does.

### 6. An Bord Pleanála oral-hearing submissions — public record, but purpose limitation
**JUDGEMENT CALL.** Confirmed (WebSearch, pleanala.ie): oral-hearing case
files are genuinely public — "anyone can inspect the entire file... for at
least 5 years after the appeal is decided" — so this is not an access-rights
problem. The live issue is **purpose limitation (Art. 5(1)(b))**: the
document was submitted for planning-appeal adjudication, and Gaia is
repurposing a sentence in it ("I have over 40 years' experience...") as
recruitment evidence about a named individual. That's a *new* purpose the
person didn't contemplate when they gave that statement. This is exactly the
kind of case Art. 6(4)'s compatibility test exists for (is the new purpose
compatible with the original, considering the link between purposes, context,
nature of the data, and consequences) — a professional's own stated
credentials, reused to verify the same credentials for a different
professional purpose, is a reasonably compatible re-use, but it is not
risk-free, and there is no case law found confirming this specific pattern.
**ASK A LAWYER** if this scales beyond a handful of names.

### 7. LinkedIn — use and terms
**SETTLED risk, and the repo's design already reflects it correctly.**
Confirmed (WebSearch): LinkedIn's User Agreement §8.2 explicitly prohibits
scraping or copying "profiles and information of others... through any means
(including crawlers, browser plugins and add-ons, and any other technology
or manual work)" — note that clause reaches *manual* copying too, not just
automated scraping, and courts have treated it as enforceable contract terms
independent of whether the underlying data is "public" (this is the post-hiQ
v. LinkedIn landscape). **Checked `check_results.json`'s actual
`source_url` values for the 13-name POC run: zero are LinkedIn URLs** — every
quote traces to a firm team page (ocsc.ie, barrettmahony.com,
horganlynch.ie), a project document (n6galwaycityringroad.ie), or an An Bord
Pleanála PDF. That is the right answer *for this run*. But the task brief
and `v2_proposal.md` both mention LinkedIn as a labelled contact/evidence
source (LinkedIn URL resolution, "the grade LinkedIn holds... bio pages do
not" per `v2_proposal.md` §"How it runs"), and Recruit CRM's own AI Sourcing
is explicitly LinkedIn-and-public-web sourced per
`recruit_crm_capabilities_2026-09.md` §2. **Any component that copies verbatim
LinkedIn profile text (not just a URL reference) into a quote/evidence field
is a LinkedIn ToS exposure regardless of GDPR status** — a URL reference to a
public profile is very different from copying its text. Recommend: keep
LinkedIn strictly to a *URL reference* for contact resolution (as v2_proposal
describes: "LinkedIn URL resolved per card") and never as an `evidence_quote`
source; if the pool ever needs quoted LinkedIn text, that needs its own
sign-off from a lawyer, not a code review.

### 8. Engineers Ireland register terms
**Confirmed unverified, matches repo's own flag.** WebSearch found no
published terms-of-use for scraping the Engineers Ireland CEng register;
`v2_proposal.md` §"Open for day 2" item 4 already states this correctly:
"Engineers Ireland register: terms of use unverified; until then chartership
is evidenced from the person's own post-nominals and their employer's page."
That is the right interim posture — don't build a scraper against a register
whose terms you haven't checked; use the weaker-but-safe signal (self-stated
post-nominals + employer page) and say so on the card. **ASK someone to
actually check** engineersireland.ie's terms/robots.txt before any future
build touches that register directly.

### 9. What to write on the CRM note so a DSAR is survivable
**JUDGEMENT CALL, and the repo is already close to right.** A data-subject
access request entitles the person to a copy of the personal data held about
them and (per Art. 15(1)(h)) meaningful information about any automated
decision-making logic. `check_note`/`evidence_note` already write: the
verdict, every rule failed with its plain-English reason, up to 3 evidence
quotes with source URLs, the contact-confidence label, and the Art. 14
notice text with a collection date. **That is a genuinely strong DSAR
artifact** — it shows exactly what was collected, from where, when, why
(purpose statement), and what conclusion was drawn and why. Two additions
would make it more survivable: (a) record who/what performed the assessment
(a version/commit reference — `brief_version` already does this) and (b)
make sure the note is retrievable/exportable in one place per person, since a
DSAR response needs "all personal data," not just the CRM candidate record,
if cached page copies also count as data held about them (they likely do).

---

## B. The Recruit CRM salesperson's 8 best attacks on Deb

Framed as what a CRM rep would actually say to Keith to keep the renewal and
kill the Prodcraft add-on, with the honest counter and where it's weak.

**1. "We already have verified emails and phone numbers via the Chrome
extension."**
Counter: Confirmed on their own page (`recruit_crm.io/sourcing/`) — but
"no method or accuracy rate disclosed" (`recruit_crm_capabilities_2026-09.md`
§2, §8: Capterra reviews say "Data Enrichment does not always provide
accurate data"). Shortlist Check never claims verified contact where it
doesn't have it — it labels verified/catch_all/guess/none and never puts a
guessed email in the CRM payload (`card_to_payload`: "Email is included ONLY
when the status is verified/catch_all"). **Weak point to concede**: Recruit
CRM's contact data is probably good enough for a large fraction of names
already, and Shortlist Check doesn't replace it — it's a check layer on top,
not a competing contact-data source. Don't claim better contact data; claim
honest labelling of confidence.

**2. "Our AI matching already scores candidates 0-100 — this is the same
thing."**
Counter: Documented and true that it's a similarity *score*, not a hard
rule — "No hard rule... is documented; a non-qualifier is down-weighted, not
removed" (`recruit_crm_capabilities_2026-09.md` §3, §"What a verification
layer could add" item 1). Keith's own words nail this: "0 to 100 match
scores, similar to what you did" was his own comparison, and the answer the
Keith page must give in one line (per `PLAN.md` item 7) is: a score says how
similar, a check says whether, and why. **Weak point**: this is a genuine
philosophical difference recruiters may not value — some will prefer "close
enough, ranked" over "binary, with reasons." Concede that for a large loose
funnel, a ranked score is faster to skim than a pass/fail with citations.

**3. "Just add a custom field and a filter — you don't need a whole
product."**
Counter: True that Recruit CRM's data model supports up to 150 custom fields
on Business plan, and Shortlist Check's whole "Checked" column output IS
literally implemented as custom fields (`check_row_to_payload`:
`Shortlist Check`, `Shortlist Check line`, `Shortlist Check brief`) written
by an external adapter — Recruit CRM would happily hold the *field*. What it
can't do is *populate* that field with a verified, quoted, sourced,
chartership/residence-checked verdict — the field is a container, not a
verification engine. **This is Deb's strongest technical point and also the
honest one**: Recruit CRM never claimed to do the checking; it's not a
competing capability, it's a target integration surface Shortlist Check
already writes into.

**4. "Your consultant can check LinkedIn in 2 minutes per name — why pay for
this?"**
Counter: The whole POC quantifies exactly this cost:
`minutes_per_manual_check` default 15 min (not 2 — checking LinkedIn *and*
the firm page *and* the Engineers Ireland register *and* confirming location
*and* finding an address, per `PLAN.md` §"Quantified value"), and the August
list result — 13 names, 0 passed the actual brief, 4 emails sent to people
who could never be placed — is the concrete cost of the 2-minutes-per-name
status quo. **Weak point**: "2 minutes" undersells what a thorough manual
check takes, but Keith may reasonably think his consultants already do a
partial version fast and informally (a LinkedIn glance) — the honest counter
is that the value isn't in doing the LinkedIn glance faster, it's in doing
the parts consultants currently skip (chartership register, residence
evidence beyond a LinkedIn "location" field, verbatim quote so no one
misremembers).

**5. "This is a one-man shop — what happens when he disappears?"**
Counter, honestly: this is a real and legitimate business-continuity risk
that Shortlist Check's own design partially mitigates — it's not a live
service Keith depends on hour-to-hour; it runs offline against a cache
(`run.py --check`, "offline: loads cache... zero model spend"), produces a
static file (`check_results.json`) and a CRM field, and the code lives in a
git repo the client could, worst case, hand to another developer. **This is
Deb's weakest ground and he should concede it plainly**: there's no SLA, no
support team, no redundancy — if Deb disappears, Gaia is stuck with a
frozen snapshot of a useful tool, not a maintained product. The honest
answer is pricing this as a project/consulting engagement with source-code
delivery, not a subscription Keith bets his pipeline on.

**6. "Credits are cheaper than a consulting engagement."**
Counter: Recruit CRM's own pricing for matching is metered too — 2 matches on
Pro, 50 on Business (`recruit_crm_capabilities_2026-09.md` §7) — and their AI
Sourcing "runs on credits, with a set number of searches per plan" per
spott.io. So "credits are cheaper" is comparing Shortlist Check's per-role
cost (~€100 in data/model calls per role per `v2_proposal.md`, "against a
placement fee of €14k to €20k") to a Recruit CRM plan Keith is *already
paying for regardless*. **Weak point**: if Keith is already on a plan with
spare match/sourcing credits, the marginal cost of using more of what he
already pays for really is close to zero, whereas Shortlist Check is
additional spend — that's a fair, not-fully-answerable point unless Deb can
show the credits alone would have caught what the check caught (they
wouldn't have, per the August-list result, but "wouldn't have caught it"
still costs Keith something to believe without seeing it proven again).

**7. "We're GDPR compliant and AICPA/IAF certified — you don't need someone
else's compliance layer."**
Counter: True and confirmed (`recruit_crm_capabilities_2026-09.md` §5,
"GDPR compliant" and "AICPA and IAF certified") — but that's *platform*
compliance (how Recruit CRM stores and processes data Gaia puts into it), not
a claim about the *lawful basis or accuracy* of data Recruit CRM's own AI
Sourcing pulled from LinkedIn/the public web in the first place. Shortlist
Check's Art. 14 notice, evidence-quote trail, and opt-out registry
(§A above) exist precisely because sourcing methodology-level compliance
(where did this claim about this person come from, is it accurate, can they
object) is a different obligation than platform security certification.
**Weak point**: Keith may reasonably not distinguish "platform compliant"
from "sourcing methodology compliant," and this is a nuanced pitch to make
to a non-technical MD — needs one plain sentence, not a compliance lecture.

**8. "Our sequences already handle outreach and replies — why do you need a
separate reply-classification layer?"**
Counter: Confirmed absence — `recruit_crm_capabilities_2026-09.md` §4:
Sequences documents scheduled multi-channel sends and "Failed steps pause
enrollment... (disconnected accounts, invalid contact info, etc.)" — that's
failure-*pausing*, not reply classification. "Not found on their pages as of
2026-09-11: automatic classification of inbound replies
(interested/not-interested/OOO detection)." Shortlist Check's design (per
`v2_proposal.md` step 7) classifies interested/not now/no/question/OOO/bounce
and sets next steps automatically, with opt-out honoured immediately.
**Weak point**: this is a v2/outbound-sourcing feature (`v2_proposal.md`),
not part of the Shortlist Check POC itself (`PLAN.md` explicitly scopes
Shortlist Check as evidence + gates only, not reply handling) — don't let
Keith conflate the two products when this attack lands; be precise about
which deliverable does what.

---

## Notes on the check_results.json rows read

All 13 rows in the current POC (`deliverables/gaia_poc_check/check_results.json`,
generated 2026-09-13T11:58:08Z, campaign `gaia-2026-09-14`) cite firm team
pages (ocsc.ie, barrettmahony.com, horganlynch.ie), a project traffic-impact
PDF (n6galwaycityringroad.ie), and two An Bord Pleanála oral-hearing PDFs
(Gerry Healy, Pearse Sutton) as `source_url`. No LinkedIn URLs appear as
evidence sources in this run — consistent with the ToS position in §A.7
above, and worth keeping that way deliberately rather than by accident.
