# Option B monkey (type 10)

Script: `qa/B/monkey_B.mjs`, seed 20261105, replay `SEED=20261105 node qa/B/monkey_B.mjs <role>`. Logs: `qa/B/logs/monkey_<role>.log`.

| ID | Type | Option | Story/gate | Steps | Expected | Actual | Evidence | Status | Run date |
|---|---|---|---|---|---|---|---|---|---|
| MONKEY-B-001 | Monkey | B | Type 10 gate, logged out | 300 seeded random actions (click, fill, submit, back/forward, resize 390-1440, reload) | 0 5xx, 0 uncaught errors, 0 DEMO-GME- in DOM, always a way back | 0 failures | qa/B/logs/monkey_anon.log | PASS | 2026-11-05 |
| MONKEY-B-002 | Monkey | B | Type 10 gate, contributeur | same, logged in as contributeur | same | 0 failures | qa/B/logs/monkey_contributeur.log | PASS | 2026-11-05 |
| MONKEY-B-003 | Monkey | B | Type 10 gate, equipe | same, logged in as equipe | same (code allowed only right after « Afficher le code ») | 0 failures | qa/B/logs/monkey_equipe.log | PASS | 2026-11-05 |
| MONKEY-B-004 | Monkey | B | Type 10 gate, direction | same, logged in as direction | same (code allowed only right after « Afficher le code ») | 0 failures | qa/B/logs/monkey_direction.log | PASS | 2026-11-05 |
