# GreenJobs frozen taxonomy

`src/taxonomy.json` (version 1, frozen 2026-11-20) is the single vocabulary for every part of the platform:

| Reader | Uses |
|---|---|
| `build_site.py` (static build and the import/feed classifier) | `sectors` (name, colour, keywords) for `assign_sectors`; `job_types.canon` for `canon_type`; `contract`, `workplace`, `levels`, `agency` |
| Worker pages (`src/render/*`) and `/api/stats` | sector colours and slugs (`/{site}/sectors/<slug>/`), labels, per-site `regions` / buckets / currency |
| Staff console (`src/routes/console.js`, `src/facets.js`) | dropdowns: sectors (1 to 3), region per site, `job_types.console`, `workplace`; the API rejects anything else |
| D1 `job_facets` (migration 0002) | stores the picked/classified values plus `taxonomy_version` |

## Keys

- `sectors[]`: `{name, slug, color, dark, keywords}`. Order is the classifier's tie-break priority. `default_sector` is
  what the classifier assigns when nothing scores.
- `job_types.canon`: raw label (lower case) -> canonical spelling. `job_types.console`: the console's type list.
- `contract`, `workplace`, `levels`, `loc_classes`: facet keys and their visitor labels.
- `agency`: names and whole-word markers that flag a recruitment agency.
- `sites.{ie,uk}`: domain, currency, symbol, region unit, `regions` (the map regions, equal to
  `deliverables/greenjobs_redesign_2026-09-22/src/data/regions_{site}.json` keys; aliases stay in that file),
  the `none` (nationwide/remote) and `elsewhere` buckets, which location classes the board carries, and the
  "hide abroad-only" home set.

## Changing it

1. Edit `taxonomy.json` and bump `version` when a name, slug or meaning changes (adding keywords alone does not).
2. Renaming or removing a sector or region: existing `job_facets` rows keep the old value until re-classified.
   Re-run the import classifier for imported jobs; staff re-pick on console jobs (an edit validates the picks).
   Sector slugs are public URLs (`/{site}/sectors/<slug>/`): add a redirect for an old slug.
3. Run `bash deliverables/greenjobs_migration_2026-11-06/build/run_tests.sh`. `test_platform_taxonomy.py` checks
   the file against `build_site.py` and the region tables; `parity.test.mjs` re-checks pages and figures.
4. Template edits in the redesign (`_shell`, `job`, `jobs`, `_fit`) need `python3 tools/export_site_assets.py`
   so the Worker renders the same markup (`--check` fails the test run until you do).
