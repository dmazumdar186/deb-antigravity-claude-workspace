# AlumnForce — Senior Product Manager Data & AI case study (step 2)

Deliverable for the AlumnForce recruitment case: frame a natural-language campaign-targeting assistant and propose the first quarterly increment. Submitted in English (the brief allows French or English).

## Files

| File | What it is |
|---|---|
| `deck.pdf` | The deliverable: 15 slides + Annex A (AI usage), B (selection logic), C (technical and compliance sheet), D (operations and feedback loop). 19 pages. Send this one. |
| `deck.html` | Source of the deck (self-contained HTML, 1280×720). Rebuild with `bash tools/build.sh` (see below). |
| `tools/` | `autofit.js` (per-slide zoom so nothing overflows, bakes `data-zoom` into the HTML), `measure.js` (overflow check), `build.sh` (the exact Chromium print command). |
| `annexB.sql` | The Annex B query, runnable as written on SQLite with the CSV loaded as table `profils`. Returns 49 rows. |
| `annexB_result.csv` | The 49 members returned, with finance source and freshness grade. |
| `SPEAKER_GUIDE.md` | Timing for the 20-minute presentation, the five lines to memorise, prepared answers for the 30-minute Q&A (LangChain, evals, provider, permissions, pricing, dedup), what was seen on the demo instance. |

Input file expected by the SQL: `profils-exercice-PM.csv`, 526 lines including the header (525 rows, 500 members after deduplication). The raw input CSV and the brief PDF are not committed (they were provided by AlumnForce and stay in the shared folder).

## Key numbers (computed from profils-exercice-PM.csv, reference date 2026-10-12, on the 500 members after deduplication unless stated)

- 525 rows for 500 announced members: M0501–M0525 are duplicate persons.
- 8 spellings of London; 3 of the UK plus 41 missing countries; sector missing on 174 members.
- 68 % of profiles untouched for 2+ years; 77 % no login for 12+ months (89 % if the 60 future-dated logins are treated as unknown).
- "Finance in London for 3+ years": naive filter 2 (file as delivered, with tenure), normalised 26, full logic 49, current or to-confirm 6 (1 current).

## Rebuilding the PDF

```bash
cd projects/alumnforce_case && npm i playwright && CHROME=/path/to/chromium bash tools/build.sh
```

## Re-running Annex B

```bash
python3 -I - <<'PY'
import sqlite3, pandas as pd, re, sys
from pathlib import Path
csv, sql = Path('profils-exercice-PM.csv'), Path('annexB.sql')
for f in (csv, sql):
    if not f.exists(): sys.exit(f"missing {f}: run this from the folder holding the CSV and annexB.sql")
con = sqlite3.connect(':memory:')
pd.read_csv(csv, encoding='utf-8').to_sql('profils', con, index=False)
body = re.sub(r'--[^\n]*', '', sql.read_text(encoding='utf-8'))
stmts = [s for s in body.split(';') if s.strip()]
for s in stmts[:-1]: con.execute(s)
print(len(pd.read_sql(stmts[-1], con)))   # 49
PY
````
