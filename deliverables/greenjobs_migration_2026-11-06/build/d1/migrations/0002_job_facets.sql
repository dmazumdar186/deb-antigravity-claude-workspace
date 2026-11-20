-- Migration 0002 (2026-11-20): derived job fields for Worker-rendered job pages.
-- Run AFTER schema.sql and 0001:  npx wrangler@4 d1 execute greenjobs --file=migrations/0002_job_facets.sql
--
-- Job pages are rendered by the Worker from D1 (ARCHITECTURE.md §3.1). The Worker NEVER classifies: every derived
-- field below is set at WRITE time, from the frozen vocabulary in
-- execution/gtm_client_workflows/greenjobs_redesign/platform_worker/src/taxonomy.json (version in taxonomy_version):
--   console      : staff pick sectors / region / job type / workplace from dropdowns; the Worker stores the picks
--   import / feed: the Python classifier (build_site.assign_sectors, resolve_regions, canon_type, contract_of,
--                  workplace_of, loc_class, level_of, is_agency) computes them and upserts this table
-- jobs.sectors_json / jobs.region / jobs.job_type stay the RAW source labels (Strategies facets); this table holds
-- the canonical values every page, filter, sitemap and /api/stats reads.
--
-- A side table (1:1 on job_id), not new jobs columns: 0001 rebuilds `jobs` with an explicit column list, so columns
-- added to `jobs` would be dropped by a re-run of 0001. A separate table survives any re-run of the migration set.
-- Idempotent: IF NOT EXISTS only; running it twice (or after schema.sql again) changes nothing.
-- The REFERENCES has no ON DELETE action on purpose: 0001's DROP TABLE jobs (deferred FKs) must not cascade here.

CREATE TABLE IF NOT EXISTS job_facets (
  job_id           TEXT PRIMARY KEY REFERENCES jobs (id),
  sectors_json     TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(sectors_json) AND json_type(sectors_json) = 'array'
                     AND json_array_length(sectors_json) <= 3),          -- canonical sector names, best first
  regions_json     TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(regions_json) AND json_type(regions_json) = 'array'
                     AND json_array_length(regions_json) <= 10),         -- region names of the job's site, or the none/elsewhere bucket
  job_type         TEXT CHECK (job_type IS NULL OR length(job_type) BETWEEN 1 AND 40),         -- canon_type() spelling
  workplace        TEXT NOT NULL DEFAULT 'unspecified' CHECK (workplace IN ('office','hybrid','remote','site','unspecified')),
  contract_json    TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(contract_json) AND json_type(contract_json) = 'array'),
  loc_class        TEXT NOT NULL DEFAULT 'unspecified' CHECK (loc_class IN ('ie','uk','ni','remote','cross','intl','unspecified')),
  level            TEXT CHECK (level IS NULL OR level IN ('Graduate/Early career','Mid-level','Senior/Principal','Director/Associate')),
  is_agency        INTEGER NOT NULL DEFAULT 0 CHECK (is_agency IN (0,1)),
  salary_display   TEXT CHECK (salary_display IS NULL OR length(salary_display) <= 200),  -- salary_label() in the site currency
  unverified_cur   INTEGER NOT NULL DEFAULT 0 CHECK (unverified_cur IN (0,1)),  -- euro figure scraped for a UK-only role (never in medians)
  search_text      TEXT CHECK (search_text IS NULL OR length(search_text) <= 1500), -- strip_tags(sanitised description)[:1500]:
                                                       -- board search + listing-quality score without re-sanitising every job per request
  taxonomy_version INTEGER NOT NULL CHECK (taxonomy_version >= 1),
  set_by           TEXT NOT NULL CHECK (set_by IN ('console','import','feed')),
  updated_at       TEXT NOT NULL
) STRICT;

-- Canonical upsert (console + importer share it): platform_worker/src/facets.js SQL_FACETS_UPSERT
-- (INSERT ... ON CONFLICT (job_id) DO UPDATE SET every column = excluded.column).
CREATE INDEX IF NOT EXISTS job_facets_loc ON job_facets (loc_class);
