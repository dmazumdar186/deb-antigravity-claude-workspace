# AlumnForce — Senior Product Manager Data & AI case study (step 2)

Deliverable for the AlumnForce recruitment case: frame a natural-language campaign-targeting assistant and propose the first quarterly increment. Submitted in English (the brief allows French or English).

## Files

| File | What it is |
|---|---|
| `deck.pdf` | The deliverable: 15 slides + Annex A (AI usage) + Annex B (selection logic). Send this one. |
| `deck.html` | Source of the deck (self-contained HTML, 1280×720). Re-render with headless Chromium `--print-to-pdf`. |
| `annexB.sql` | The Annex B query, runnable as written on SQLite with the CSV loaded as table `profils`. Returns 49 rows. |
| `annexB_result.csv` | The 49 members returned, with finance source and freshness grade. |
| `SPEAKER_GUIDE.md` | Timing for the 20-minute presentation, the five lines to memorise, prepared answers for the 30-minute Q&A (LangChain, evals, provider, permissions, pricing, dedup), what was seen on the demo instance. |

The raw input CSV and the brief PDF are not committed (they were provided by AlumnForce and stay in the shared folder).

## Key numbers (all computed from profils-exercice-PM.csv, reference date 2026-10-12)

- 525 rows for 500 announced members: M0501–M0525 are duplicate persons.
- 8 spellings of London; 3 of the UK plus 42 missing countries; sector missing on 182 rows.
- 69 % of profiles untouched for 2+ years; 78 % no login for 12+ months; 61 last-login dates in the future.
- "Finance in London for 3+ years": naive filter 2, normalised 26, full logic 49, fresh enough to email 6.

## Re-running Annex B

```bash
python3 - <<'PY'
import sqlite3, pandas as pd, re
con = sqlite3.connect(':memory:')
con.create_function('REGEXP', 2, lambda p, s: 1 if s and re.search(p, s) else 0)
pd.read_csv('profils-exercice-PM.csv').to_sql('profils', con, index=False)
body = re.sub(r'--[^\n]*', '', open('annexB.sql').read())
stmts = [s for s in body.split(';') if s.strip()]
for s in stmts[:-1]: con.execute(s)
print(len(pd.read_sql(stmts[-1], con)))   # 49
PY
```
