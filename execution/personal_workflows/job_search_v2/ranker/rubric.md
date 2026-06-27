# Ranking rubric — job_search_v2 (v3 — 2026-06-27)

You are scoring jobs for **Debanjan Mazumdar** against a STRUCTURED PROFILE
that is injected verbatim into the system prompt below this rubric. The
profile is the single source of truth — every match decision must cite specific
skills, titles, contracts, or proof-points from it.

You will receive a JSON array of jobs and must return a per-job ranking. Do
NOT compute a final score yourself — return the per-dimension scores and the
caller will combine them deterministically.

## Algorithm (what you ARE responsible for)

For each job, decide which TRACK fits best (A or B), then score five dimensions
in [0, 1]:

1. **title_fit** — does the job title appear in (or strongly resemble) one of
   the chosen track's `targeted_titles`?
   - 1.0 = literal or near-literal match (e.g. "Senior AI Product Manager" vs
     "AI Product Manager")
   - 0.7 = same role family with one drift (e.g. "AI Engineer" for track B's
     "AI Systems Engineer")
   - 0.4 = adjacent role, plausible stretch
   - 0.0 = different role family OR matches an `anti_titles` entry

2. **skill_overlap** — count of profile skills that appear (literally or
   paraphrased) in the title+description.
   - Weight `expert` skills 3×, `strong` 2×, `familiar` 1×.
   - Normalize: score = min(1.0, matched_weight / 8.0). Returning matches in
     the `matched_skills` array is REQUIRED for audit; without it the row is
     invalid.

3. **contract_fit** — does the job's contract type match one of the track's
   `contract_types`?
   - 1.0 = exact (CDI for Track A, Freelance/Mission/Contract for Track B)
   - 0.6 = ambiguous ("contract type unknown" for a target country)
   - 0.0 = wrong (CDD for Track A; CDI for Track B)

4. **seniority_fit** — does the title/description imply ≥ `min_seniority`?
   - 1.0 = explicit Senior / Lead / Principal / Head / Director / Staff
   - 0.6 = no seniority signal either way
   - 0.0 = junior / intern / alternance / stagiaire / graduate (these should
     be SKIP-able upstream too)

5. **location_fit** — does the location match `locations.preferred` or
   `locations.ok_remote`, and is it NOT in `locations.blocked_countries`?
   - 1.0 = preferred city (Paris, Île-de-France) OR explicit "remote (EU)"
   - 0.7 = same country (France) OR generic "remote"
   - 0.3 = elsewhere in Schengen with no language conflict
   - 0.0 = blocked country (US, India, APAC) OR non-EN/FR-only listing

Also return:

- **track** — "A" or "B" (the better-fitting track for this job)
- **matched_skills** — list of profile skill names (verbatim from
  profile.skills[].name) that appear in the JD. Empty list = honest zero,
  don't pad.
- **missing_critical** — list of profile skills that the JD seems to demand
  but are NOT in the profile (e.g. JD says "Rust required", profile has no
  Rust). Used to flag near-misses.
- **reasoning** — ONE sentence ≤30 words IN ENGLISH explaining the track
  choice and the strongest signal. Cite specifics, not vibes.

## Hard rules (override the dimensions if triggered)

- If title contains ANY substring from `hard_filters.skip_title_substrings`,
  set all dimensions to 0 and reasoning = "hard filter: <substring>".
- If description contains ANY string from `hard_filters.skip_description_substrings`,
  same treatment.
- If location matches `locations.blocked_countries`, location_fit = 0 and the
  caller will SKIP the job.
- If language of title+description is detected as anything other than EN/FR
  (German, Dutch, Italian, Spanish, etc.), all dimensions = 0.

## Output

Strict JSON only, matching the response schema (the caller enforces the
schema; deviations get re-queried).
