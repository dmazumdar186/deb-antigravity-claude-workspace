# Reddit pain-mining (directive)

**Paired script:** none yet — this is a methodology directive; use Firecrawl / WebSearch / Tavily inline. Promote to a script only if the workflow runs ≥3 times across projects.

**Source pattern:** assembled from vibe-check's Discovery Beat 2 (Reddit ladder + ODI evidence tagging), itself drawn from Tony Ulwick's Outcome-Driven Innovation and Bob Moesta's JTBD struggling-moment lens. Adapted for this workspace's plan-skeptic USER-EVIDENCE axis.

---

## Goal

Before building any user-facing artifact (app, product, content series, public tool, CV being sent to real recruiters), validate that the target need is **real** and **underserved** against what people actually say in unfiltered language. Output is a ranked list of needs with evidence tags, suitable as input to plan-skeptic's USER-EVIDENCE axis or as the discovery section of a plan file.

This is a stand-in for the customer-survey-of-hundreds you can't run. Reddit gives you ~80% of the signal in an afternoon. It's directional, not statistical — treat a loud thread as a strong hypothesis, not proof.

---

## Inputs

- **Target user, narrow.** Not "people." A specific person you can picture: "Paris-based senior PM, fluent FR/EN, applying to AI PM roles." If you can't name the person, the rest will smear.
- **The hypothesized need, in their language.** "I waste an hour rewriting my CV per role" — not "AI-powered CV optimization."
- **3–5 candidate subreddits.** Where the user actually talks (`r/ProductManagement`, `r/cscareerquestionsEU`, `r/jobs`, `r/Frenchproductmanagers`, etc.).
- **The five struggle phrases** (used as search queries):
  - `"[current solution] is..."`
  - `"How do I deal with..."`
  - `"Tired of..."`
  - `"Does anyone else..."`
  - `"I gave up and just..."`

---

## Tools / Scripts

- **Firecrawl** (preferred): `mcp__firecrawl__firecrawl_search` with `site:reddit.com` filter. Returns full page content; no scraping bot-protection issues.
- **Tavily**: `mcp__tavily__tavily_search` as fallback.
- **Reddit read endpoints** if Firecrawl/Tavily quota is exhausted:
  - `https://www.reddit.com/search.json?q=<query>` (no auth, JSON output)
  - `https://www.reddit.com/r/<sub>/search.json?q=<query>&restrict_sr=1` (search within a sub)
  - `old.reddit.com` URL form may load when `www.reddit.com` is blocked
- **Last resort**: hand the user the 3–5 subreddits + the exact phrases to paste into Reddit's own search; user pastes back what they find. Never fabricate quotes.

---

## Outputs

A ranked needs table in this exact shape (paste into the plan file under a `## User evidence` heading, or into a memory entry):

| Need (user's language) | Pain (1-10) | Served (1-10) | Opportunity | Evidence |
|---|---|---|---|---|
| Reduce time to rewrite CV per role | 9 | 3 | 15 | seen it |
| Stop the "is my CV reaching a human" anxiety | 8 | 2 | 14 | seen it |
| Browse listings easily | 7 | 8 | 7 | hunch |

**Opportunity formula:** `Opportunity = Pain + max(0, Pain − Served)`.

**Evidence tags:**
- **seen it** — direct Reddit quotes / G2 reviews / interview transcripts in hand. Cite the link or paste the quote inline.
- **hunch** — plausible from what you've read but not confirmed in a specific quote.
- **guess** — you're inferring without source. If most needs are guesses, **the answer is not "build anyway" — it's "go look harder."**

---

## Steps

1. **Define the narrow user.** One sentence, picturable. Reject "people who want X" — too broad. The same need has different Opportunity scores for different ICPs.
2. **Map the job (no-app today).** Write the 5–9 steps the user takes today to get the outcome without your product. Each step is a candidate friction point.
3. **Search Reddit for each struggle phrase × job step.** Use Firecrawl `site:reddit.com` first. Aim for 5–10 high-signal threads (3+ digits of upvotes, multiple "me too" replies, or the same complaint resurfacing across months).
4. **Pull unmet needs in the user's language.** Frame as "reduce [pain] / increase [confidence] in [step]." Never as features. "I can't tell which of my CVs the recruiter actually opened" is a need; "add a read-receipt feature" is a feature wearing a need's clothes.
5. **Map the competition (Step 3.5 in vibe-check terms).** List 3–7 things people use today, including ugly ones (a spreadsheet, "I just don't bother"). For each top need, rate each competitor: does it well / does it poorly / doesn't do it. Pull from G2 / Capterra / app-store reviews (same Firecrawl ladder).
6. **Score Pain and Served, 1-10.**
   - Pain ← Reddit signal (upvotes, repetition, anger).
   - Served ← competitor matrix + 1-3-star reviews of paid tools in the space ("I wish it did X" is gold).
7. **Compute Opportunity, tag evidence, rank.**
8. **Money gut-check.** Glance for a wallet: paid products in the space, freelancers hired for this, ads running on these keywords. Real pain with no money near it is a yellow flag — surface it.
9. **Hand the ranked table back** as input to the plan (under `## User evidence`) or to plan-skeptic's USER-EVIDENCE axis.

---

## Edge cases

- **Reddit blocks direct page fetches in some environments.** Always start with `site:reddit.com` via search, not a raw page fetch. If even that fails, drop to `search.json` or to user-paste mode.
- **Quote everything you find.** Never paraphrase a Reddit quote into a need without preserving the link. The plan-skeptic USER-EVIDENCE axis will ask for the source.
- **Don't invent competitors.** If you can't actually see a tool's reviews, don't score it — write "Served: unknown" and downgrade the evidence tag.
- **Marketplace / two-sided products: score each side separately.** Buyers' top need ≠ sellers' top need. Run the whole flow once per side.
- **High-Pain, well-Served needs are table stakes, not opportunities.** They go in V1 as "build to not lose," not as "build to win." Don't drop them — they hold the floor.
- **"Significantly better" is the bar, not "as good as."** A high score doesn't earn a switch if incumbents already handle it well. Switching cost is real.
- **Sample size honesty.** 5–10 threads is directional. Frame outputs with "loud threads suggest…" not "users want…". If the output of a pain-mining session is going to drive a multi-week build, follow it with 3–5 actual user interviews.

---

## When to use this

- Before building any user-facing artifact (vibe-check Mode B trigger for USER-EVIDENCE axis).
- Before greenlighting a ProdCraft video idea or content series direction.
- When the user proposes a feature and the answer to "what's the evidence?" is a shrug.
- When plan-skeptic returns NEEDS_REVISION on the USER-EVIDENCE axis.

## When NOT to use this

- Internal-only tools (no end users to validate against).
- Engineering refactors / audit scripts / workspace tooling.
- Throwaway prototypes whose lifespan is one afternoon.
- When you already have real user research (3+ interview transcripts or a survey). Then this is a sanity-check pass, not the primary evidence.

## Exit Criteria

- A ranked-needs table (Need / Pain / Served / Opportunity / Evidence) exists with at least 3 rows.
- Every row tagged as **seen it** has an inline link or pasted quote from the source (Reddit thread, G2 review, interview).
- The narrow-user sentence (Step 1) is one picturable sentence, not "people who want X."
- At least one row has **Opportunity ≥ 12** (high Pain, low Served) OR the report explicitly states "no underserved need found — do not build."
- Money gut-check answered: paid products / freelancer demand / ad keywords listed, or yellow-flagged "no money near this."
- Output saved either inline in the plan's `## User evidence` section or as a memory entry with the date and source links.
