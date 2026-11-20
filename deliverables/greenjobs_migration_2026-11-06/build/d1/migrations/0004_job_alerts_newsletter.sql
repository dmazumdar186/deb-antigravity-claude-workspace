-- Migration 0004 (2026-11-20): job alerts (double opt-in, import re-confirmation, weekly digest) and the newsletter.
-- Run AFTER schema.sql (and 0001):  npx wrangler@4 d1 execute greenjobs --file=migrations/0004_job_alerts_newsletter.sql
-- Additive only: new side tables, nothing in schema.sql is altered, so other migrations cannot conflict with it.
-- Idempotent: every statement is IF NOT EXISTS; a re-run is a no-op.
-- Code: execution/gtm_client_workflows/greenjobs_redesign/platform_worker/src/listmail/*.js
-- No email address is stored in any table here: suppression keeps sha256(email_norm) only.

-- Per alert_subscriptions row: who started it and its consent timeline. A subscription with no row here came from the
-- Strategies "Jobs By Email" import (origin 'import').
CREATE TABLE IF NOT EXISTS alert_meta (
  sub_id             TEXT PRIMARY KEY,                -- alert_subscriptions.id
  origin             TEXT NOT NULL DEFAULT 'import' CHECK (origin IN ('signup','import')),
  confirm_expires_at TEXT,                            -- pending row is deleted after this (30 days)
  confirmed_at       TEXT,
  unsubscribed_at    TEXT,
  last_digest_at     TEXT,                            -- digest watermark: jobs posted after this are "new"
  created_at         TEXT NOT NULL,
  updated_at         TEXT NOT NULL
) STRICT;

-- Newsletter consent is separate from job-alert consent (its own table, own double opt-in, own unsubscribe).
CREATE TABLE IF NOT EXISTS newsletter_subscribers (
  id                 TEXT PRIMARY KEY,                -- '{site}:nl:{hash24}'
  site               TEXT NOT NULL CHECK (site IN ('ie','uk')),
  email_norm         TEXT NOT NULL,
  status             TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','active','unsubscribed')),
  confirm_token_hash TEXT,
  confirm_expires_at TEXT,
  consent_at         TEXT,
  unsubscribed_at    TEXT,
  created_at         TEXT NOT NULL,
  updated_at         TEXT NOT NULL,
  UNIQUE (site, email_norm)
) STRICT;

-- A staff-composed newsletter. items_json = {"jobs":[job ids],"advertisers":[employer ids]}.
CREATE TABLE IF NOT EXISTS newsletters (
  id          TEXT PRIMARY KEY,                       -- '{site}:nl:{uuid}' (derived from the Idempotency-Key)
  site        TEXT NOT NULL CHECK (site IN ('ie','uk')),
  subject     TEXT NOT NULL CHECK (length(subject) BETWEEN 3 AND 150),
  intro       TEXT NOT NULL CHECK (length(intro) BETWEEN 1 AND 5000),
  items_json  TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(items_json)),
  status      TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','queued','sent')),
  version     INTEGER NOT NULL DEFAULT 1,
  created_by  TEXT NOT NULL,
  queued_by   TEXT,
  queued_at   TEXT,                                   -- recipients = active subscribers with consent_at <= queued_at
  sent_at     TEXT,
  created_at  TEXT NOT NULL,
  updated_at  TEXT NOT NULL
) STRICT;

-- Send ledger for every list mail. One row per (kind, key, period): a re-run converges, never a double send.
--   confirm    key = alert sub id        period = UTC day     (one confirmation mail per alert per day)
--   reconfirm  key = '{site}:{emailhash}' period = 'once'    (ONE re-confirmation per imported person, ever)
--   digest     key = alert sub id        period = ISO week   ('2026-W49')
--   nl_confirm key = newsletter sub id   period = UTC day
--   nl_test    key = '{newsletter id}:{staff email hash}' period = 'v{version}'
--   newsletter key = newsletter sub id   period = newsletter id
-- status: sending (claimed; a crash leaves it here and it is never re-sent), sent, dry_run, failed (retry while
-- attempts < 4), empty (digest with no new jobs: no mail), skipped (suppressed at send time).
CREATE TABLE IF NOT EXISTS list_mail_ledger (
  kind        TEXT NOT NULL CHECK (kind IN ('confirm','reconfirm','digest','nl_confirm','nl_test','newsletter')),
  key         TEXT NOT NULL,
  period      TEXT NOT NULL,
  site        TEXT NOT NULL CHECK (site IN ('ie','uk')),
  status      TEXT NOT NULL CHECK (status IN ('sending','sent','dry_run','failed','empty','skipped')),
  attempts    INTEGER NOT NULL DEFAULT 0,
  reason      TEXT,
  day         TEXT NOT NULL,                          -- UTC day of the last claim (daily budget)
  created_at  TEXT NOT NULL,
  updated_at  TEXT NOT NULL,
  PRIMARY KEY (kind, key, period)
) STRICT;
CREATE INDEX IF NOT EXISTS list_mail_ledger_day ON list_mail_ledger (day, status);

-- Permanent suppression by sha256(email_norm). 'alerts_unsubscribed' / 'newsletter_unsubscribed' block every
-- automated mail on that channel; 'reconfirm_expired' blocks imports from ever being re-mailed.
CREATE TABLE IF NOT EXISTS list_suppression (
  site        TEXT NOT NULL CHECK (site IN ('ie','uk')),
  email_hash  TEXT NOT NULL,
  reason      TEXT NOT NULL CHECK (reason IN ('alerts_unsubscribed','newsletter_unsubscribed','reconfirm_expired')),
  created_at  TEXT NOT NULL,
  PRIMARY KEY (site, email_hash, reason)
) STRICT;

-- Snapshot the status/dashboard `measures` object reads (keys: listmail/measures.js MEASURE_KEYS). NULL = unmeasured.
CREATE TABLE IF NOT EXISTS list_measures (
  key         TEXT PRIMARY KEY,
  value       INTEGER,
  updated_at  TEXT NOT NULL
) STRICT;
