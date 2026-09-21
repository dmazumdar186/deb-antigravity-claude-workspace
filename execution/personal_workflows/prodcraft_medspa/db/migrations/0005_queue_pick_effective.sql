-- Migration 0005: outreach.queue_pick_effective (round-3 Sutskever lens item 16).
-- Idempotent (IF NOT EXISTS; safe to re-run alongside another agent's own migration).
-- Previously `queue_pick_effective` (what actually governed a touch-1 enqueue — may differ from
-- the raw config.queue_pick while phase0 hasn't passed yet, see daily_queue.py's _pick_mode())
-- was stamped ONLY on the outreach_enqueued events row, unreadable by fit_weights.py without an
-- events join. This column lets fit_weights.py condition on it directly off the outreach row.

alter table outreach add column if not exists queue_pick_effective text;

-- Migration 0005 (continued): phase0.calls_to_pass support (round-3 Sutskever lens item 17).
-- No schema change needed — calls_to_pass lives in the `config` table's `phase0` JSON value
-- (config is a key/value table, not a typed row) — this comment documents the migration number
-- the change shipped under for CONTRACTS.md/audit-trail purposes.

-- Migration 0005 (continued): audits.superseded / audits.superseded_reason (round-3
-- pipeline-auditor lens item 21) — the live store already writes these two columns; this closes
-- the gap where db/schema.sql (and this migration set) never caught up, which would 400 a
-- Supabase write the first time something set them on a fresh schema apply.
alter table audits add column if not exists superseded boolean default false;
alter table audits add column if not exists superseded_reason text;
