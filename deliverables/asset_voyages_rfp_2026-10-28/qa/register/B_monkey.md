# Option B monkey (type 10)

Script: `qa/B/monkey_B.mjs`, seed 20261105, replay `SEED=20261105 node qa/B/monkey_B.mjs <role>`. Logs: `qa/B/logs/monkey_<role>.log`.

| ID | Type | Option | Story/gate | Steps | Expected | Actual | Evidence | Status | Run date |
|---|---|---|---|---|---|---|---|---|---|
| MONKEY-B-001 | Monkey | B | Type 10 gate, logged out | 300 seeded random actions (click, fill, submit, back/forward, resize 390-1440, reload) | 0 5xx, 0 uncaught errors, 0 DEMO-GME- in DOM, always a way back | 0 failures | qa/B/logs/monkey_anon.log | PASS | 2026-11-05 |
| MONKEY-B-002 | Monkey | B | Type 10 gate, contributeur | same, logged in as contributeur | same | 0 failures | qa/B/logs/monkey_contributeur.log | PASS | 2026-11-05 |
| MONKEY-B-003 | Monkey | B | Type 10 gate, equipe | same, logged in as equipe | same (code allowed only right after « Afficher le code ») | 0 failures | qa/B/logs/monkey_equipe.log | PASS | 2026-11-05 |
| MONKEY-B-004 | Monkey | B | Type 10 gate, direction | same, logged in as direction | same (code allowed only right after « Afficher le code ») | 0 failures | qa/B/logs/monkey_direction.log | PASS | 2026-11-05 |

## Final re-run, 2026-11-05 23:04–23:14 UTC (live Worker version `29d23da1-4707-436e-8b91-dbdb96fd844c`)

Script changes before the run: (1) the DEMO-GME- scan also reads every `input` (hidden included) and `textarea` value (`code-leak-field`, never excused); (2) the reveal exception applies only right after « Afficher le code » and only for `direction` signed in, or `equipe` after a grant approved (« Accès accordé ») in the same run; (3) each context resets its sandbox via « Réinitialiser la démo » at the end (all 4 « sandbox reset ok »). Summary: `qa/B/logs/monkey_summary.json`.

| ID | Type | Option | Story/gate | Steps | Expected | Actual | Evidence | Status | Run date |
|---|---|---|---|---|---|---|---|---|---|
| MONKEY-B-101 | Monkey | B | Type 10 gate, logged out | 300 seeded actions, seed 20261105 | 0 5xx, 0 uncaught errors, 0 DEMO-GME- in text, HTML or field values, always a way back | 0 failures | qa/B/logs/monkey_anon.log | PASS | 2026-11-05 |
| MONKEY-B-102 | Monkey | B | Type 10 gate, contributeur | same | same | 0 failures | qa/B/logs/monkey_contributeur.log | PASS | 2026-11-05 |
| MONKEY-B-103 | Monkey | B | Type 10 gate, equipe | same | same; no reveal exception (no grant approved in this run) | 0 failures | qa/B/logs/monkey_equipe.log | PASS | 2026-11-05 |
| MONKEY-B-104 | Monkey | B | Type 10 gate, direction | same | same; code allowed only right after « Afficher le code » | 0 failures (a grant was approved during the run) | qa/B/logs/monkey_direction.log | PASS | 2026-11-05 |
