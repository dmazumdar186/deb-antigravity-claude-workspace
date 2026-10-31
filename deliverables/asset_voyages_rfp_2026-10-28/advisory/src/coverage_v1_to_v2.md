# Coverage: v1 (47 pp) → v2 (17 pp)

Each v1 item maps to exactly one v2 section. "DROP" = removed, with reason.

| v1 § / item | v2 § | Note |
|---|---|---|
| Cover, conventions (Estimate/Verified/UNKNOWN) | 1 | Merged into "Open:" + "Estimate" conventions |
| 0.1 why reading; 0.2 asks; 0.3 rubric | 1 | |
| 0.4 what this is not; 0.5 map | DROP | Navigation boilerplate |
| 1.1 client, activities, current-site facts, unknowns | 2 | |
| 1.2 RFP outcomes, L0–L4, J0–J6, T01–T15 scenarios, launch blockers, essential conditions, criteria | 2 | One combined table |
| 1.3 consultation posture, timeline | 1 (posture) | Date timeline DROP: commercial process |
| 1.4 links | 1 | |
| 1.5 price options | 7 | |
| 1.5 payment 50/50, contract guardrails, deemed answers | DROP | Payment mechanics / legal boilerplate (deemed acceptance survives as D5 in 10) |
| 1.5 12-month plan contents | 7 | |
| 1.6, 2.9, 3.6, 4.9, 5.11, 6.8, 7.7, 8.5, 9.9, 10.3 reviewer questions | Same v2 section as the topic | Folded into prose; some merged |
| 2.1 A1–A11 governance | 2 (Scope at a glance) | i18n/A11 in 2 hard numbers |
| 2.2 L0.1–L0.8 | 2 (Scope at a glance) | |
| 2.3 pages C-1–C-10, journeys J-1–J-5, design expectations, claims register | 2 (Scope at a glance) | Mock-up widths in 6 (M2) |
| 2.4 F01–F06, CRM, G1–G5, H1–H4, I1–I9 | 2 (forms/CRM/measurement); G/I → 4 (model, retention, permissions) | |
| 2.5 C01–C07, workflow, import, i18n | 4 | C02 search detail in 5 check-me table |
| 2.6 architecture/env/data/quality/SEO/maintenance rows | 2 hard numbers; detail in 4–6 | |
| 2.6 T01–T15 "our test" column | 6 test table | Scenarios in 2 |
| 2.7 30 questions defaults (shaping ones) | 2 | Defaults-if-unanswered prose DROP |
| 2.8 clarification promises | 2 | Footer credit/LinkedIn ask DROP (commercial) |
| 3.1 workspace layers; 3.2 reusable assets | 3 | File paths DROP (reviewers have no repo access) |
| 3.3 concept evidence + limits | 3 | Audit-round history DROP (QA log) |
| 3.4 missing list with hours; 3.5 matrix | 3 | Merged into one table |
| 4.1 domain model | 4 | |
| 4.2 three state machines | 4 | |
| 4.3 invariants I-1–I-8 | 4 | |
| 4.4 roles, 4.5 permissions | 4 | |
| 4.6 retention, export, DSR | 4 | DSR timing in 5 check-me |
| 4.7 CSV import | 4 | Caps in 5 check-me |
| 4.8 i18n, SEO migration | 4 | Past-event rule moved here from 2.5 |
| 5.1 components; 5.2 topology, TB1–TB6 | 5 | |
| 5.3 data flows (6) | 5 | |
| 5.4 environments; 5.5 deploy/rollback/cutover | 5 | |
| 5.6 backups + drill | 5 | |
| 5.7 observability; 5.8 security | 5 | |
| 5.9 failure modes | 5 | |
| 5.10 alternatives (Directus, WP+ACF, microservices) | 5 | |
| 5.12 engineering specifics (16 rows) | 5 check-me table | i18n slugs row → 4 (i18n); test data kept |
| 6.1 contracts; 6.2 skeleton; 6.3 modules | 6 | |
| 6.4 tests; 6.5 CI gates; 6.6 DoD; 6.7 handover | 6 | J0 "deposit cleared" DROP (payment) |
| 7.1 hours (two counts), options | 7 | Per-line dual column compressed to biggest deltas |
| 7.2 quantities; 7.3 calendar | 7 | |
| 7.4 price + market evidence | 7 | |
| 7.5 3-year TCO | 7 | HT only; TTC column DROP (×1.2) |
| 7.6 running costs | 7 | |
| 8.1 complexity; 8.2 P model | 8 | |
| 8.3 11-lens prose | DROP | Allowed cut; its technical gaps already appear as "Open:"/never-run notes in 3–5 |
| 8.4 five-expert table | 3 (one sentence of concerns) | |
| 9.1–9.8 KPIs | 9 | One row per stage |
| 10.1 decisions; 10.2 asks; 10.4 sheet | 10 | |
| App. A 30 questions | DROP | Defaults-if-unanswered; shaping ones in 2; live at questions page |
| App. B glossary | Appendix | Condensed |
| App. C file index | DROP | Internal paths, no reviewer use |
| App. D sources | Appendix | Static-assets billing, Business SLA, Postmark, SES URLs DROP (not cited by any v2 fact) |
| App. E QA log | DROP | Allowed cut |

Topic overlap check: each topic sits in one v2 section; cross-references only ("D3 in §10").

## Restorations after independent MECE check
All 12 flagged items restored: 5.11 questions (5); 6.8 questions (6); 7.7 Q2–Q3 (7); 8.5 missed-risk ask (8); 10.3 cut-entirely ask (10); Acceptance + Human-eye test rows (6); per-line hour deltas (7); calendar run lengths (7); Directus €1,100 (5); PM + designer concerns (3); SAST at J5 and GSC coverage at J6 (9); inventory fields, transfer-assistance period (6) and Brevo 300/day (7). Fail-small source link restored for the 18 Nov 2025 incident (Appendix).
