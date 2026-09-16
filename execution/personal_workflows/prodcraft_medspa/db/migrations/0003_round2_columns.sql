-- Migration 0003: round-2 audit-stack columns.
-- Idempotent (every ADD COLUMN is IF NOT EXISTS; safe to re-run alongside another agent's own
-- migration). Adds columns needed by: gmail_reader/scan_replies dedupe + send-channel tracking
-- (outreach), publish-mode/host bookkeeping (previews), and discovery/LLM provenance
-- (businesses). audits.is_mobile_friendly is already nullable as of 0001_initial.sql — no change
-- needed there.

alter table outreach add column if not exists gmail_message_id text;
alter table outreach add column if not exists sent_via text;
alter table outreach add column if not exists seen_reply_ids jsonb not null default '[]'::jsonb;
-- test_recipient already added by 0002_v_pipeline_outreach_columns.sql — not repeated here.

alter table previews add column if not exists publish_mode text not null default 'r2';
alter table previews add column if not exists local_build_dir text;
alter table previews add column if not exists email_policy text;
alter table previews add column if not exists min_score integer;
alter table previews add column if not exists hosted_at text;
alter table previews add column if not exists original_host text;

alter table businesses add column if not exists discovery_source text;
alter table businesses add column if not exists llm_overrides jsonb;
alter table businesses add column if not exists pii_purged_at timestamptz;
-- businesses.email_source already exists as of 0001_initial.sql — not repeated here.

alter table outreach add column if not exists pii_purged_at timestamptz;
