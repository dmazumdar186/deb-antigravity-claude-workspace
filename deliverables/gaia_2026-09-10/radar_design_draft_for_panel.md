# Gaia Talent Radar — full-system design (for panel review)

Builder: Debanjan Mazumdar (Prodcraft), one person plus Claude Code agents. Deadline: Monday 14 Sep 2026 17:00 (4 days). Promise on the call: a working sourcing system, link plus Loom, that integrates with Gaia's Recruit CRM and their inbound AI screener "Maddie". Goal now: over-deliver without breaking the promise.

Client: Gaia Talent Ltd, Ireland, 5 people (Keith MD, Isadora senior consultant, Gian, Eva, Diana), B Corp, niches: structural/civil, transport, EIA/environmental, ecology, flood risk, building services, sustainability. Roles are senior-heavy, all Ireland. Fee per placement €14k–20k. Stack: Recruit CRM (plan tier unknown; API needs Business+), Gmail/G Suite, Maddie (the developer; her custom inbound screener + Irish-accent voice agent). Keith's stated criteria: accuracy first ("cut the wheat from the chaff"), speed, take on 50–100 jobs with two consultants, InMail replies collapsing to ~3%, enrichment tools "don't have the data".

What exists (built, 636 tests): evidence pipeline (public records + firm directories → verbatim-quote claims validated char-by-char → deterministic gates → tiers → Prospeo contact → movability → outreach drafts → link check → honest pool map); brief filters (seniority ceiling, strict residence, county lists, CLI overrides, delivery composition guard); Recruit CRM adapter (dry-run default, audit log, dedupe, write cap); reply classifier (rules first, LLM fallback, opt-out honoured); Brief Controls demo page; v2 proposal page. Cost per run €0.60 model spend. No API keys or run cache in the cloud session; the operator's Windows machine has both.

## The system: Radar, not Search

Thesis: an agency of five cannot out-database Recruit CRM (800M profiles) or LinkedIn. Its edge is a standing, evidence-verified map of every relevant chartered engineer in Ireland per niche, refreshed weekly, with movability signals, so a shortlist exists within an hour of a job arriving and every card carries proof. Maddie handles who comes to Gaia; Radar keeps the map of who Gaia should be calling and says when they become movable. The consultant's phone call stays the revenue activity.

### 1. Brief Contract
Structured per job, seeded from the Recruit CRM job record plus a 10-field form: title, grade band (min/max years, max grade), residence rule (ROI only, counties, relocation, NI), chartership (required/preferred, registers), discipline include/exclude, target and off-limits firms, salary band, sender (named consultant), channel order, delivery cadence. Confirmed back in writing. Every brief is versioned; every shortlist names the brief version it was cut against.

### 2. Niche Pool Engine (the new core)
Sources, each a plugin with cache, rate limit, cost meter and a text_source label:
- Public records: An Coimisiún Pleanála oral-hearing witness statements, local-authority scheme sites (built).
- Firm directories: "our people" pages of ~40 Irish consultancies (16 built; extend).
- Registers: Engineers Ireland Find-a-member, IStructE, ICE directories (chartership evidence with date).
- Licensed people data: PeopleDataLabs or Crustdata (title, city, job history with dates, skills) — the only source that reaches the 8–15-year grade at scale. Coresignal for job-change deltas. No LinkedIn scraping (Proxycurl precedent).
- Bylines and awards: Engineers Journal, ACEI/IStructE awards, conference proceedings (technical-skill evidence).
- Firm news: promotions, office moves, mergers (movability and BD signals).
Identity resolution across sources (name + employer + location + register number), one Person with a claim ledger. Evidence rule unchanged: no verbatim quote, no claim; licensed-data fields are stored as claims with source=provider and confidence=direct but flagged "provider field, not a quote" and never used as the sole basis of a tier A signal.
Pool per niche: structural (~2,000 people est.), transport (~800), EIA/ecology (~1,500). Weekly refresh diff: new entrants, title changes, employer changes.

### 3. Gate Engine (built, extended)
Deterministic only: chartered (register-verified beats self-stated), resident (direct evidence, county lists), discipline, seniority floor and ceiling (grade ladder + years), not-client, salary-band consistency (grade→band map per firm size, advisory). Composition guard refuses any delivery that breaks the brief.

### 4. Movability Engine
Deterministic score with published rules: tenure in current role (2–5 years peak), time since last promotion, employer events (merger, redundancy, office closure, leadership change), job-change detected in weekly diff, public "open to work" signals, commute mismatch to the role. Output: movable-now / watch / settled, with the evidence lines. The LLM may propose a finding; the rule decides.

### 5. Contact Engine (built, extended)
Prospeo email verify (verified/catch-all only ship), mobile reveal on request (€0.36), LinkedIn URL resolution, channel order per brief. Inferred addresses never sent to.

### 6. Outreach Kit
Human-approved template pool (Gaia's voice, 6–8 templates per channel), fuzzy variables (project they gave evidence on, scheme, firm, chartership year, mutual scheme with the client), LinkedIn note <400 chars, email <90 words, call-opener script for the consultant. Sequence: LinkedIn note → email day 3 → consultant call day 5 → follow-up day 10. Drafts are created as Gmail drafts in the named consultant's mailbox (Gmail API, draft only) and as copy-ready LinkedIn text; nothing is ever sent by Prodcraft (I7). Reply classifier (built) sets next action and writes the Recruit CRM note; opt-out closes and is honoured across all campaigns.

### 7. Recruit CRM + Maddie hand-off (built, wired)
Sourced candidate → Recruit CRM candidate (source "Radar", tag per campaign, evidence note, Art. 14 date) → assigned to job at stage "Sourced". Reply "interested" → stage "Screening" → Maddie's existing trigger invites them to her call. Fallback when API plan is missing: Zapier or CSV import.

### 8. Client Radar (new, small)
Weekly monitor of the ~40 consultancies' careers pages and public scheme awards: new roles posted, schemes won, office openings → a BD list for Keith ("Arup Cork posted two Senior Bridge Engineers this week"). Uses the same fetch/cache layer.

### 9. Console (the link Keith opens)
Static-first site per client (Cloudflare Pages, password) regenerated by pipeline runs, plus a small Modal endpoint for two live actions: "re-cut this job against this brief" (runs the gate stage on the cached pool, returns a new shortlist in seconds) and "sync this card to Recruit CRM" (dry-run by default). Pages: Jobs (from Recruit CRM), Shortlist per job with Brief Controls, Candidate card with evidence quotes and sources, Pool map (denominator, exclusions, missed-by-one), Niche pool health (size, freshness, movable-now count), Outreach queue (drafts and their states), Replies (classified, next actions), Client radar, Audit and cost log. CSV export per job.

### 10. Evaluation harness
Frozen labelled set: the 158 Role 1 and 21 Role 2 profiles hand-labelled for grade, residence country, chartership evidence, plus 50 licensed-data profiles. Metrics per run: grade precision/recall vs labels, residence precision, chartership precision, quote-validation drop rate, composition-guard violations (must be 0), cost per delivered card. Scorecard page in the console. No threshold changes without the scorecard moving.

### 11. Guardrails and ops
Cost ceiling per run and per month (all providers metered, not just LLM). Run lock. Every threshold a versioned flag. Audit JSONL for every external write. Error channel to Gaia's Slack/WhatsApp (service/env/error/count). Self-healing change log after 3 repeats, scoped to the routine's own instructions. GDPR: Art. 14 notice hosted under a Gaia domain, source named per candidate, contact within 30 days of collection, retention 6 months then purge unless in CRM, opt-out registry, legitimate-interest assessment documented, DPA with Gaia, licensed providers only.

## 4-day plan
- Fri: keys and budget; €10 coverage test on PDL, Crustdata, Apollo for "chartered structural engineer, Ireland"; pick one. Engineers Ireland register source. Extend firm directories to 40. Re-harvest Role 1, corrected cut, Role 2 near-miss lookups. Label the eval set (Sonnet workers + Deb spot-check).
- Sat: licensed-data pull for structural + transport niches (~€100); identity resolution; movability engine; contact enrichment for gate-passers; scorecard.
- Sun: console v3 (per-job pages, Modal re-cut endpoint, outreach queue, replies, CRM dry-run view, pool health, client radar first run); Gmail-draft creation for one consultant mailbox (if Keith consents; else copy-ready only).
- Mon: acceptance gates, panel pass, fix list, deploy, Loom, send by 17:00 with the honest count and two questions for Keith.

## What Deb must supply
Keys/budget: Anthropic top-up (~€30), OpenRouter, Prospeo (have), PDL or Crustdata trial key (or Apollo), Serper, Firecrawl, Cloudflare Pages token (have), Modal account (exists). The cached run directory from the Windows machine (push to a branch or zip). ~2 hours/day of machine time and one hour for the Loom. Decisions: product name, pricing shape, include Client Radar or not, console login yes/no. From Keith (by email Friday, non-blocking): seniority ceiling, Ireland rule, Recruit CRM plan tier and API key if Business+, job slugs, named sender, two live roles to add.

## Offer (draft)
Pilot: 30 days, two niches, 3 live roles, fixed fee, success metric agreed (approved candidates and first conversations per role), no fee if missed. Then Radar subscription per niche per month with data at cost; Gaia owns the code and the pool. Anchors: Recruit CRM Business seat, SeekOut ~$27k/seat/yr, one placement €14–20k.
