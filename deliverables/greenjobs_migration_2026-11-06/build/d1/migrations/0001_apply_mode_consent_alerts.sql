-- Migration 0001 (2026-11-20). Only for a D1 created from schema.sql BEFORE 2026-11-20; harmless on a newer one.
--   jobs.apply_mode inbox|consultant|advertiser|url -> email|link   (client answer Q8, 10-11 Nov: an email or an ATS link)
--   candidates.strategies_consent (new)                            (Strategies 'Consent' column, header rows 19 Nov)
--   import_batches.report_type + 'alerts'                           (Jobs By Email report -> alert_subscriptions)
-- Run AFTER schema.sql:  npx wrangler@4 d1 execute greenjobs --file=migrations/0001_apply_mode_consent_alerts.sql
--
-- SQLite cannot ALTER a CHECK or add a column idempotently, so each table is rebuilt. Idempotent: a second run (or a
-- run on a new-shape DB) rebuilds the same rows. D1 runs the file as one transaction (no BEGIN/COMMIT here).
-- Foreign keys stay ON: applications -> jobs/candidates is deferred to commit, and rows are copied back AFTER the
-- rename, so every referenced id exists again when the deferred check runs.
-- New column trick: `SELECT *, NULL AS strategies_consent` names the NULL copy "strategies_consent:1" when the
-- column already exists, so h.strategies_consent is the real value on a re-run and NULL on the first run.
-- jobs mapping: 'url' (or 'link') with an https apply_url -> 'link' (apply_email cleared); everything else -> 'email'
-- (apply_url cleared; a malformed apply_email becomes NULL = the APPLY_ROUTING default). Under the old 'inbox' mode a
-- stored apply_email was ignored; under 'email' it is used: review jobs with apply_email set before go-live.

PRAGMA defer_foreign_keys = ON;

-- jobs
DROP TABLE IF EXISTS jobs_hold;
CREATE TABLE jobs_hold AS SELECT * FROM jobs;
DROP TABLE IF EXISTS jobs_new;
CREATE TABLE jobs_new (
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
DROP TABLE jobs;
ALTER TABLE jobs_new RENAME TO jobs;
INSERT INTO jobs (id, site, source, source_id, employer_id, title, location, region, job_type, sal_min, sal_max, currency, period, sal_text, sectors_json, summary, description, apply_mode, apply_email, apply_url, status, posted_at, closing_at, closed_at, created_by, version, created_at, updated_at)
SELECT
  h.id,
  h.site,
  h.source,
  h.source_id,
  h.employer_id,
  h.title,
  h.location,
  h.region,
  h.job_type,
  h.sal_min,
  h.sal_max,
  h.currency,
  h.period,
  h.sal_text,
  h.sectors_json,
  h.summary,
  h.description,
  CASE WHEN (h.apply_mode IN ('url','link') AND h.apply_url LIKE 'https://%') THEN 'link' ELSE 'email' END,
  CASE WHEN (h.apply_mode IN ('url','link') AND h.apply_url LIKE 'https://%') OR h.apply_email IS NULL OR length(lower(trim(h.apply_email))) NOT BETWEEN 3 AND 254 OR lower(trim(h.apply_email)) NOT LIKE '%_@_%' THEN NULL ELSE lower(trim(h.apply_email)) END,
  CASE WHEN (h.apply_mode IN ('url','link') AND h.apply_url LIKE 'https://%') THEN h.apply_url ELSE NULL END,
  h.status,
  h.posted_at,
  h.closing_at,
  h.closed_at,
  h.created_by,
  h.version,
  h.created_at,
  h.updated_at
FROM jobs_hold h;
DROP TABLE jobs_hold;

CREATE INDEX IF NOT EXISTS jobs_live ON jobs (site, status, closing_at);

-- candidates
DROP TABLE IF EXISTS candidates_hold;
CREATE TABLE candidates_hold AS SELECT *, NULL AS strategies_consent FROM candidates;
DROP TABLE IF EXISTS candidates_new;
CREATE TABLE candidates_new (
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
DROP TABLE candidates;
ALTER TABLE candidates_new RENAME TO candidates;
INSERT INTO candidates (id, site, source, source_id, email_norm, first_name, last_name, phone, location, headline, sectors_json, cv_key, consent_marketing, consent_at, registered_at, last_active_at, strategies_consent, created_at, updated_at)
SELECT
  h.id,
  h.site,
  h.source,
  h.source_id,
  h.email_norm,
  h.first_name,
  h.last_name,
  h.phone,
  h.location,
  h.headline,
  h.sectors_json,
  h.cv_key,
  h.consent_marketing,
  h.consent_at,
  h.registered_at,
  h.last_active_at,
  h.strategies_consent,
  h.created_at,
  h.updated_at
FROM candidates_hold h;
DROP TABLE candidates_hold;

-- import_batches
DROP TABLE IF EXISTS import_batches_hold;
CREATE TABLE import_batches_hold AS SELECT * FROM import_batches;
DROP TABLE IF EXISTS import_batches_new;
CREATE TABLE import_batches_new (
  sha256       TEXT PRIMARY KEY,
  site         TEXT NOT NULL CHECK (site IN ('ie','uk')),
  report_type  TEXT NOT NULL CHECK (report_type IN ('recruiters','candidates','profiles','jobs','applications','alerts')),
  rows_in      INTEGER NOT NULL,
  rows_kept    INTEGER NOT NULL,
  imported_at  TEXT NOT NULL
) STRICT;
DROP TABLE import_batches;
ALTER TABLE import_batches_new RENAME TO import_batches;
INSERT INTO import_batches (sha256, site, report_type, rows_in, rows_kept, imported_at)
SELECT
  h.sha256,
  h.site,
  h.report_type,
  h.rows_in,
  h.rows_kept,
  h.imported_at
FROM import_batches_hold h;
DROP TABLE import_batches_hold;
