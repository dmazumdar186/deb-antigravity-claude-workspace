-- Migration 0003 (2026-11-20): sector review queue, feed duplicate links, employer self-posting accounts.
-- Run AFTER schema.sql (and 0001/0002; the classifier's facets live in 0002's job_facets):
--   npx wrangler@4 d1 execute greenjobs --file=migrations/0003_classifier_feed_review_employers.sql
--
-- Additive only: three NEW tables, no ALTER / rebuild of an existing table, and no FOREIGN KEY to jobs or
-- employers, because 0001 rebuilds `jobs` (DROP + re-create); a child
-- table with an FK would make those rebuilds order-dependent. Integrity is kept by the writers (Worker
-- routes, gaia_d1_sync.py, strategies_import.py), which only ever write ids they have just upserted.
-- Idempotent: every statement is IF NOT EXISTS; a re-run is a no-op. Statements that write these tables
-- live in ../upserts_0003.sql (Python emitters) and platform_worker/src/sql_0003.js (Worker), kept equal
-- by tests/greenjobs_redesign/platform/feed_review_employer.test.mjs.

-- job_facets is NOT created here: migration 0002 owns the one facet table (it has the classifier's source labels,
-- confidence and method as columns). An earlier draft of this file created a second job_facets; see 0002's header.

-- Sector review queue. A row is written when the classifier is not sure (low confidence, conflict with the
-- source label, possible duplicate, taxonomy not frozen). hold = 1: the job stays 'draft' until staff
-- approve (feed jobs); hold = 0: the job is already live and only its sector is confirmed (Strategies).
-- A decided row (approved/changed) is never reopened by a re-import, and its sectors are never overwritten.
CREATE TABLE IF NOT EXISTS job_review (
  job_id               TEXT PRIMARY KEY,
  site                 TEXT NOT NULL CHECK (site IN ('ie','uk')),
  reason               TEXT NOT NULL CHECK (length(reason) BETWEEN 1 AND 300),
  suggested_json       TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(suggested_json)),
  confidence           REAL NOT NULL DEFAULT 0 CHECK (confidence >= 0 AND confidence <= 1),
  hold                 INTEGER NOT NULL DEFAULT 1 CHECK (hold IN (0,1)),
  status               TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','approved','changed')),
  decided_by           TEXT,
  decided_sectors_json TEXT CHECK (decided_sectors_json IS NULL OR json_valid(decided_sectors_json)),
  decided_at           TEXT,
  created_at           TEXT NOT NULL,
  updated_at           TEXT NOT NULL
) STRICT;
CREATE INDEX IF NOT EXISTS job_review_queue ON job_review (site, status, created_at);

-- A feed job that is already on a board (eval E2 "dup") is linked to the board job, not listed twice.
CREATE TABLE IF NOT EXISTS job_links (
  site            TEXT NOT NULL CHECK (site IN ('ie','uk')),
  feed_source_id  TEXT NOT NULL,                       -- 'gaia:<wp id>'
  board_job_id    TEXT NOT NULL,                       -- jobs.id of the board job, e.g. 'ie:strat:11513670'
  method          TEXT NOT NULL CHECK (method IN ('rule','jev','staff')),
  created_at      TEXT NOT NULL,
  updated_at      TEXT NOT NULL,
  PRIMARY KEY (site, feed_source_id, board_job_id)
) STRICT;

-- Employer self-posting (CHM Recruit, Mattinson Partnership until their Jan 2027 contracts end). One row per
-- (email, employer row); an employer row belongs to one site, so the mapping is also the board allow-list.
-- Authentication is the Cloudflare Access JWT (the same check as staff); this table is authorisation only.
CREATE TABLE IF NOT EXISTS employer_accounts (
  email_norm   TEXT NOT NULL CHECK (length(email_norm) BETWEEN 3 AND 254 AND email_norm LIKE '%_@_%'
                                    AND email_norm = lower(trim(email_norm))),
  employer_id  TEXT NOT NULL,
  status       TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','disabled')),
  expires_at   TEXT,                                   -- contract end; access stops after it with no action
  created_by   TEXT NOT NULL,
  created_at   TEXT NOT NULL,
  updated_at   TEXT NOT NULL,
  PRIMARY KEY (email_norm, employer_id)
) STRICT;
CREATE INDEX IF NOT EXISTS employer_accounts_employer ON employer_accounts (employer_id);

-- No taxonomy_terms table: the sector vocabulary is taxonomy.json (bundled in the Worker; the review console and
-- the import route validate against it), not a D1 copy that could drift from it.
