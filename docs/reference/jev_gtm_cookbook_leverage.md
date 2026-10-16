# Jev GTM Cookbook: leverage plan for jev_leads

Source: bcharleson/jev-gtm-cookbook (MIT License). Question wording quoted here and in
`execution/gtm_icp_filters/icp_profiles/cookbook_questions.json` is copied verbatim from that repo's
`cookbook/requests/*.json` and `src/questions.js`; keep the MIT notice if text is reused. The repo was read
only (never executed). Measured numbers below are the cookbook's own (`jev-1.13.0`, 2026-09-22).

Our baseline: `.tmp/jev_leads_contract.md` (scenarios qualify, signals, hygiene, suppress, replies,
inbound, diff) built on `execution/modules/jev_client.py` (`decide`, `decide_many`, `noul`, `choice`, `score`).
Note: the cookbook calls option sets `criteria`; our client calls them `options`/`levels`/`true,false`.

## 1. Recipe-by-recipe map

| # | Decides | Questions (name: type, option keys) | State fields | Scoring / ranking | Our status |
|---|---|---|---|---|---|
| 01 | Which LinkedIn connections fit the ICP | persona: choice (icp.personas incl. other); seniority: score 5 levels; role_fit: score 4 levels; company_fit: choice {fits, does_not_fit, cannot_tell}; likely_buyer: noul | ideal_customer {what_we_sell, target_roles, target_companies, not_a_fit}, connection {current_position, current_company, company_description?} | fit = round(100 x weighted mean of role_fit/3, seniority/4, likely_buyer, P(fits)); weights 0.4/0.2/0.25/0.15; cutoff 60 | Partial: `qualify` has icp_fit + persona, no 0-100 score, no seniority |
| 02 | What a job change means | change_type: choice {moved_up, moved_sideways, same_job_reworded, moved_down_or_unclear}; new_budget_owner: noul; current_role_buys: noul | current, previous, what_we_sell | reach_out if fit>=60 and current_role_buys>=0.6; review if fit>=60 or signal>=0.4; ignore if P(same_job_reworded)>=0.5 | Partial: `diff` change_type differs, uses broad now_worth_contacting |
| 03 | Reply intent | intent: choice {interested, not_now, referral, objection, not_interested, out_of_office, unsubscribe}; wants_removal: noul; names_another_person: noul | our_email, reply | Hard gate: wants_removal overrides intent | Partial: `replies` lacks referral, objection, our_email context |
| 04 | Inbound form routing | route: choice {account_executive, sdr_qualify, nurture, partner_or_vendor, junk}; urgency: score 4; is_vendor_pitch: noul | lead, routing_policy | Second noul confirms low-confidence route (0.63 route, 93% vendor) | Covered by `inbound` (different keys; no routing_policy prose) |
| 05 | LinkedIn invite intent | intent: choice {pitching_us, potential_buyer, peer_or_community, recruiting_or_job, unclear}; worth_a_reply: noul | invitation_message, what_we_sell | choice + noul | Missing |
| 06 | Account (company) ICP score | sells_b2b: score 4; needs_outbound: score 4; size_fit: choice {too_small, in_range, too_large, unknown}; excluded: noul | company {description, employees}, target_size, exclusions | Account-level gates; caught competitor via excluded 72% | Partial: `qualify` is person-level, `suppress` covers competitor |
| 07 | Hiring post signal | building_outbound: noul; first_hire_in_function: noul; seniority_of_hire: choice {individual_contributor, manager, director_or_vp, executive} | job_post | nouls as signals | Partial: `signals.hiring_outbound` (no first-hire, no hire level) |
| 08 | Personalised line fact check | supported: choice {supported, contradicted, unsupported}; sounds_creepy: noul | first_line, source | Block send unless supported and not creepy | Missing |
| 09 | First-message quality | about_them: score 4; pitches_first_line: noul; reads_as_template: noul; clear_ask: noul | message, prospect | Gate before send | Missing |
| 10 | Learn what wins in our inbox | about_them: score 4; pitches_first_line; asks_a_question; references_a_trigger: nouls | opener | Join with "got reply" outcome to learn traits | Missing |
| 11 | Stalled buying conversations | buying_interest: noul; who_owes_reply: choice {me, them, nobody}; topic: choice {sales_conversation, networking, hiring_or_job, pitch_to_me, other} | me, thread | Joined with 01 fit score | Missing |
| 12 | Warm intro paths | path_to_buyer: choice {is_the_buyer, leads_the_buyer, same_team, other_team, unclear}; intro_strength: score 4 | connection, target_account {buyer} | rank by intro_strength | Missing |
| 13 | Any list + enrichment re-check | 01 questions + company_description from provider | as 01 | Enrichment stored as new snapshot; enrichment fingerprint skips unchanged | Partial: `diff` has snapshot compare, no enrichment loop |
| 14 | Social post triage | action: choice {engage, monitor, ignore}; author_is_buyer: noul; self_promotion: noul | post, what_we_sell | low confidence = monitor | Partial: `jev_comment_buyers.py` covers comments, not posts |
| 15 | Next follow-up | next_step: choice {bump, case_study, breakup, answer_manually, stop} | templates, thread | choice | Missing |

Selected verbatim wording (full set in the JSON export):

- 02 current_role_buys: "Is the role in `current` one whose holder decides whether to buy `what_we_sell`?" true: "They run sales, revenue, growth or the whole company, so they would own this decision".
- 03 wants_removal: "Does `reply` ask, in any wording, to stop being contacted or to be removed from the list?"
- 05 intent: "What does the sender of `invitation_message` want from us?"
- 08 supported: "Do the facts that `first_line` relies on appear in `source`? Ignore greetings and well-wishes; judge only the factual claim."
- 09 reads_as_template: "Would `prospect` recognise `message` as a mass template sent to many people?"
- 11 who_owes_reply: "Looking at the last message in `thread`, who should reply next?"
- 12 path_to_buyer: "At the company in `target_account`, how is the person in `connection` related to the buyer described in `target_account.buyer`?"
- 14 action: "Given `what_we_sell`, what should we do about `post`?"
- 15 next_step: "Given `thread`, which of our follow-ups in `templates` should we send next, or should we stop?"

## 2. What the cookbook has that our contract lacks

| # | Capability | Value for us | Questions to port | Plugs into | Effort | Scenario name |
|---|---|---|---|---|---|---|
| 1 | 0-100 fit score + seniority + persona groups | One sortable number for Sheets/Instantly; weights tunable with zero new calls | 01 seniority, role_fit, company_fit, likely_buyer (verbatim) | `qualify` (add `jev_fit` column), `scrape-leads`, `gmaps-leads` | S | extend `qualify` |
| 2 | Fingerprint cache ("$0 re-check") | Re-runs of weekly lists cost only changed rows; dedupe identical title+company | none (code) | `jev_leads.py` all scenarios; `.tmp/jev_cache.sqlite` | S | flag `--cache` |
| 3 | Privacy minimisation | Only title, company, ICP prose leave the machine for qualify; names/emails/URLs never sent | none | `row_state()` allowlist per scenario | S | default for qualify/diff |
| 4 | Personalisation fact check | Stops hallucinated first lines (Series B that never happened) before Instantly send | 08 supported, sounds_creepy | `instantly-campaigns`, `humanizer` output gate | S | `factcheck` |
| 5 | First-message scoring | Rejects template-y or pitch-first copy at generation time | 09 about_them, pitches_first_line, reads_as_template, clear_ask | `instantly-campaigns` copy step, `linkedin-response` | S | `message_score` |
| 6 | Connection-request intent | Finds buyers hiding in LinkedIn invites, skips pitches | 05 intent, worth_a_reply | `linkedin-response` | S | `invites` |
| 7 | Pick-the-follow-up | Automates sequence branching on live threads | 15 next_step | `instantly-autoreply` | S | `followup` |
| 8 | Reply referral/objection + our_email context | Referrals become new leads; objections go to a human | 03 intent keys referral, objection; names_another_person | `replies`, `instantly-autoreply` | S | extend `replies` |
| 9 | Learn-from-inbox | Data on which opener traits get replies, feeds copy rules | 10 four questions | Gmail skill export, `instantly-campaigns` | M | `opener_traits` |
| 10 | Cold ICP conversations | Revives stalled threads where we owe the reply | 11 buying_interest, who_owes_reply, topic | Gmail skill, LinkedIn messages.csv | M | `stalled` |
| 11 | Warm-intro finder | Turns our network into intro paths into target accounts | 12 path_to_buyer, intro_strength | `qualify` output + connections CSV | M | `intros` |
| 12 | Social-signal triage | Post-level buying intent from Reddit/HN/LinkedIn | 14 action, author_is_buyer, self_promotion | `jev_comment_buyers.py` (add post mode) | S | `social` |
| 13 | Account-level ICP | Score companies once, not per person; catches agencies | 06 sells_b2b, needs_outbound, size_fit, excluded | `qualify --level account`, `classify-leads` | M | `accounts` |
| 14 | Hiring signal detail | first hire = strongest outbound trigger | 07 first_hire_in_function, seniority_of_hire | extend `signals` | S | extend `signals` |
| 15 | Free title prefilter | Skip students/interns/open-to-work with no call | none (`skip_if_title_matches` list) | `hygiene` | S | extend `hygiene` |
| 16 | Mock mode with typed fake answers | Keyword mock returning real response shape for demo + tests | none | our `--dry-run` / `fake_results()` | S | n/a |
| 17 | Dashboard | Low value for us; deliverables live in Sheets | none | skip; use `--md` + Sheets | L | skip |

## 3. Technique transfers

| Technique | How the cookbook does it | What we copy |
|---|---|---|
| Narrow nouls beat broad ones | 02 measured a broad "good time to reach out?" at 42-73% across cases; split into new_budget_owner + current_role_buys, which separated cleanly | Replace `reach_out`/`timing_ok`/`now_worth_contacting` with narrow nouls |
| Field references in backticks | Every instruction names the exact state path (`connection.current_position`) | Rewrite our questions to cite `lead.title`, `context.icp` |
| ICP as four prose slots | what_we_sell, target_roles, target_companies, not_a_fit; `not_a_fit` cited inside option text | Map our icp.offer/icp/exclusions into those keys inside `context` |
| Fix wording, not thresholds | 08: adding "Ignore greetings and well-wishes; judge only the factual claim" moved a case 26% to 98% | Directive rule: tune option text on fixtures first |
| Two agreeing questions | 04: route 0.63 but is_vendor_pitch 93% | Pair every low-confidence choice with a confirming noul |
| One rank from many answers | Weighted mean of normalised parts (score/top level, noul, P(option)); code only, re-tunable | `fit_score(answers, weights)` in jev_leads; weights in icp JSON |
| One row per call | 10 rows per request moved probabilities 0.27 vs 0.03 single | Keep per-row states (we already do) |
| Fingerprint cache | sha256 of [question_version, model, icp_hash, norm(title), norm(company), desc?, prev?]; person excluded; mock model never mixes with real | SQLite or JSON cache keyed the same way; `QUESTION_VERSION` constant bumps on rewording |
| Pure-code change detection | Snapshot file hash dedupe; blank title+company treated as hidden, not a change; first import is baseline | Apply to `diff`: no Jev call to detect change, only to interpret it |
| Free prefilter | `skip_if_title_matches` before any call | add to icp JSON |
| Privacy | buildState sends only role, company, ICP | Per-scenario allowlist in `row_state()` |
| Fixture pattern | requests/*.json = {questions, cases[{label, expect, state}]}; responses/*.json = recorded answers with model, usage, ms, date; CI replays each | `execution/gtm_icp_filters/jev_fixtures/<scenario>.request.json` + `.response.json`; offline test replays responses through `apply_results` |
| Typed mock | mock.js returns the exact response shape (probabilities, legend, confidence) from regex | `fake_results()` mirrors shape so threshold code is exercised |

## 4. Prioritised 10X build list

1. Narrow-noul rewrite of qualify/diff timing questions (02 wording): `execution/gtm_icp_filters/jev_leads.py`.
2. `jev_fit` 0-100 weighted score + seniority/role_fit/company_fit/likely_buyer, weights/cutoffs in ICP JSON: `jev_leads.py`, `icp_profiles/_template.json`.
3. Fingerprint cache with QUESTION_VERSION, person-free key: `execution/modules/jev_cache.py` (new) used by `jev_leads.py`.
4. Privacy allowlist per scenario in `row_state()`: `jev_leads.py`.
5. Replies: add referral, objection, wants_removal hard gate, names_another_person, our_email: `jev_leads.py` + `instantly-autoreply`.
6. `factcheck` + `message_score` scenarios as a pre-send gate: `jev_leads.py`, wired in `.claude/skills/instantly-campaigns/SKILL.md`.
7. Offline fixtures (request/response JSON per scenario) + replay test: `execution/gtm_icp_filters/jev_fixtures/`, `tests/test_jev_leads.py`.
8. `followup` scenario (15) for live threads: `jev_leads.py` + `instantly-autoreply`.
9. `invites` (05) and `stalled` (11) for LinkedIn/Gmail: `jev_leads.py` + `linkedin-response`, `gmail` skills.
10. `social` post mode (14) and `intros` (12): `execution/lead_sourcing/jev_comment_buyers.py`, `jev_leads.py`.

## 5. Contradictions with our contract (decision needed)

- Broad timing questions: contract `reach_out`, `timing_ok`, `now_worth_contacting` are exactly the shape 02 measured as unable to separate cases.
- Fingerprint: contract keys diff on name|company|title; cookbook excludes the person (cache key) and detects change by stable person key (profile URL) plus title/company compare. Our version flags renamed people as changes and cannot share answers across people.
- Privacy: contract sends all row fields (capped 1200 chars); cookbook sends only title, company, ICP.
- Reply intents: contract lacks referral and objection, has extra keys (bounce, competitor, wrong_person); cookbook overrides intent with a separate removal noul.
- diff change_type keys differ (cookbook has same_job_reworded, which suppresses false job changes).
- Confidence rollup: contract uses min confidence over choices; cookbook ranks by weighted mean of parts and gates with cutoffs.
