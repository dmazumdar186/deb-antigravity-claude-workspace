-- GreenJobs D1 schema (Cloudflare D1 = SQLite). Written 2026-11-07.
-- Idempotent: every statement is IF NOT EXISTS; re-running the file is a no-op.
-- Changing a CHECK on an existing table needs a table rebuild, which IF NOT EXISTS cannot do: such changes ship
-- as d1/migrations/NNNN_*.sql (each idempotent, run once per DB created before it, after this file).
--   0001_apply_mode_consent_alerts.sql (2026-11-20) jobs.apply_mode -> email|link; candidates.strategies_consent;
--                                      import_batches.report_type + 'alerts'
--   0002_job_facets.sql (2026-11-20)    job_facets: canonical sectors/regions/type/workplace/contract/... per job, set at
--                                      write time from taxonomy.json (console, classifier, feed); read by the Worker-rendered
--                                      job pages and /api/stats. The ONE facet table (0003 no longer defines its own).
--   0003_classifier_feed_review_employers.sql (2026-11-20) new tables job_review, job_links, employer_accounts,
--                                      taxonomy_terms (statements: upserts_0003.sql)
--   0004_job_alerts_newsletter.sql (2026-11-20) alert_meta, newsletter_* (listmail)
-- Apply:  npx wrangler@4 d1 execute greenjobs --file=schema.sql   (local: add --local)
--
-- Stable IDs (the upsert key for every table):
--   imported rows : '{site}:strat:{strategies_id}'   e.g. 'ie:strat:11501460'
--   console rows  : '{site}:gj:{uuid v4}'            generated once by the Worker
--   feed rows     : '{site}:{feed}:{feed_ref}'       phase 2 (broadbean|idibu|logicmelon)
-- site is 'ie' (greenjobs.ie) or 'uk' (greenjobs.co.uk). A Strategies id is only unique per site.
-- Timestamps are ISO-8601 UTC text ('2026-12-03T09:00:00Z'). Emails are stored lower-cased + trimmed.
-- No passwords are stored: staff auth is Cloudflare Access; candidate/employer log-ins are phase 2.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS employers (
  id             TEXT PRIMARY KEY,
  site           TEXT NOT NULL CHECK (site IN ('ie','uk')),
  source         TEXT NOT NULL CHECK (source IN ('strategies','console','feed')),
  source_id      TEXT,
  name           TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 200),
  name_norm      TEXT NOT NULL,                       -- lower, punctuation/"ltd|limited|plc" stripped
  contact_name   TEXT,
  contact_email  TEXT,
  phone          TEXT,
  website        TEXT,
  logo_key       TEXT,                                -- R2 key, never a filesystem path
  last_active_at TEXT,
  created_at     TEXT NOT NULL,
  updated_at     TEXT NOT NULL,
  UNIQUE (site, source, source_id)
) STRICT;
CREATE INDEX IF NOT EXISTS employers_name_norm ON employers (site, name_norm);

CREATE TABLE IF NOT EXISTS jobs (
  id             TEXT PRIMARY KEY,
  site           TEXT NOT NULL CHECK (site IN ('ie','uk')),
  source         TEXT NOT NULL CHECK (source IN ('strategies','console','feed')),
  source_id      TEXT,
  employer_id    TEXT REFERENCES employers (id),
  title          TEXT NOT NULL CHECK (length(title) BETWEEN 3 AND 160),
  location       TEXT NOT NULL CHECK (length(location) BETWEEN 1 AND 120),
  region         TEXT,
  job_type       TEXT,                                -- Permanent | Contract | Temporary | Home Based ...
  sal_min        INTEGER CHECK (sal_min IS NULL OR sal_min >= 0),
  sal_max        INTEGER CHECK (sal_max IS NULL OR sal_max >= 0),
  currency       TEXT CHECK (currency IS NULL OR currency IN ('EUR','GBP')),
  period         TEXT CHECK (period IS NULL OR period IN ('year','day','hour','month')),
  sal_text       TEXT,
  sectors_json   TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(sectors_json)),
  summary        TEXT,
  description    TEXT NOT NULL CHECK (length(description) BETWEEN 20 AND 20000), -- plain text / limited markdown, escaped on render
  -- Per-job apply mode (client answer Q8, 10-11 Nov: per client, an email or an ATS link).
  --   email : on-site form; routed to apply_email, or the APPLY_ROUTING default when apply_email is NULL
  --   link  : external ATS; apply_url required, /api/apply answers 409, apply_email never stored
  apply_mode     TEXT NOT NULL DEFAULT 'email' CHECK (apply_mode IN ('email','link')),
  apply_email    TEXT CHECK (apply_email IS NULL OR (length(apply_email) BETWEEN 3 AND 254
                   AND apply_email LIKE '%_@_%' AND apply_email = lower(trim(apply_email)))),  -- never public
  apply_url      TEXT CHECK (apply_url IS NULL OR (apply_url LIKE 'https://%' AND length(apply_url) <= 2000)),
  status         TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','live','closed')),
  posted_at      TEXT,
  closing_at     TEXT,
  closed_at      TEXT,
  created_by     TEXT NOT NULL,                       -- staff email from Cloudflare Access, or 'import'
  version        INTEGER NOT NULL DEFAULT 1,          -- optimistic lock for console edits
  created_at     TEXT NOT NULL,
  updated_at     TEXT NOT NULL,
  CHECK (sal_min IS NULL OR sal_max IS NULL OR sal_min <= sal_max),
  CHECK ((apply_mode = 'link' AND apply_url IS NOT NULL AND apply_email IS NULL)
      OR (apply_mode = 'email' AND apply_url IS NULL)),                -- exactly one target per mode
  UNIQUE (site, source, source_id)
) STRICT;
CREATE INDEX IF NOT EXISTS jobs_live ON jobs (site, status, closing_at);

CREATE TABLE IF NOT EXISTS candidates (
  id                TEXT PRIMARY KEY,
  site              TEXT NOT NULL CHECK (site IN ('ie','uk')),
  source            TEXT NOT NULL CHECK (source IN ('strategies','apply','phase2')),
  source_id         TEXT,
  email_norm        TEXT NOT NULL,
  first_name        TEXT,
  last_name         TEXT,
  phone             TEXT,
  location          TEXT,
  headline          TEXT,                             -- from the Strategies "profiles" report
  sectors_json      TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(sectors_json)),
  cv_key            TEXT,                             -- R2 key; CV files are not in the CSV exports
  consent_marketing INTEGER NOT NULL DEFAULT 0 CHECK (consent_marketing IN (0,1)),
  consent_at        TEXT,
  registered_at     TEXT,
  last_active_at    TEXT,                             -- retention filter reads this
  strategies_consent INTEGER CHECK (strategies_consent IS NULL OR strategies_consent IN (0,1)), -- Strategies 'Consent' (1/0/unknown); 0 = never email
  created_at        TEXT NOT NULL,
  updated_at        TEXT NOT NULL,
  UNIQUE (site, email_norm)
) STRICT;

CREATE TABLE IF NOT EXISTS applications (
  id               TEXT PRIMARY KEY,
  site             TEXT NOT NULL CHECK (site IN ('ie','uk')),
  source           TEXT NOT NULL CHECK (source IN ('strategies','apply')),
  source_id        TEXT,
  job_id           TEXT NOT NULL REFERENCES jobs (id),
  candidate_id     TEXT REFERENCES candidates (id),
  applicant_name   TEXT NOT NULL CHECK (length(applicant_name) BETWEEN 1 AND 120),
  applicant_email  TEXT NOT NULL,
  phone            TEXT,
  cover_note       TEXT CHECK (cover_note IS NULL OR length(cover_note) <= 5000),
  cv_key           TEXT,
  routed_to        TEXT,                              -- inbox address chosen by the routing rule
  delivery_status  TEXT NOT NULL DEFAULT 'pending' CHECK (delivery_status IN ('pending','dry_run','sent','failed','imported')),
  dedupe_key       TEXT NOT NULL UNIQUE,              -- sha256(site|job_id|applicant_email): one application per person per job
  submitted_at     TEXT NOT NULL,
  created_at       TEXT NOT NULL,
  updated_at       TEXT NOT NULL,
  UNIQUE (site, source, source_id)
) STRICT;
CREATE INDEX IF NOT EXISTS applications_job ON applications (job_id, submitted_at);

CREATE TABLE IF NOT EXISTS alert_subscriptions (
  id                 TEXT PRIMARY KEY,
  site               TEXT NOT NULL CHECK (site IN ('ie','uk')),
  email_norm         TEXT NOT NULL,
  query_json         TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(query_json)),
  query_hash         TEXT NOT NULL,                   -- sha256 of canonical query_json
  frequency          TEXT NOT NULL DEFAULT 'weekly' CHECK (frequency IN ('daily','weekly')),
  status             TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','active','unsubscribed')),
  confirm_token_hash TEXT,                            -- only hashes of tokens are stored
  unsub_token_hash   TEXT,
  last_sent_at       TEXT,
  consent_at         TEXT,
  created_at         TEXT NOT NULL,
  updated_at         TEXT NOT NULL,
  UNIQUE (site, email_norm, query_hash)
) STRICT;

CREATE TABLE IF NOT EXISTS audit_log (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  at          TEXT NOT NULL,
  actor       TEXT NOT NULL,                          -- staff email, 'public', 'import'
  action      TEXT NOT NULL,                          -- job.create | job.update | job.close | application.create | import.batch ...
  entity      TEXT NOT NULL,
  entity_id   TEXT NOT NULL,
  request_id  TEXT NOT NULL,                          -- Idempotency-Key or cf-ray; replay = no new row
  detail_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(detail_json)), -- never PII values, only field names
  UNIQUE (request_id, action, entity_id)
) STRICT;

-- Skip-if-done marker for CSV import batches: a file whose sha256 is here is not imported again.
CREATE TABLE IF NOT EXISTS import_batches (
  sha256       TEXT PRIMARY KEY,
  site         TEXT NOT NULL CHECK (site IN ('ie','uk')),
  report_type  TEXT NOT NULL CHECK (report_type IN ('recruiters','candidates','profiles','jobs','applications','alerts')),
  rows_in      INTEGER NOT NULL,
  rows_kept    INTEGER NOT NULL,
  imported_at  TEXT NOT NULL
) STRICT;
