-- Migration 0004: measurement/evidence columns (round-2 learning-systems + long-horizon lenses).
-- Idempotent (every ADD COLUMN is IF NOT EXISTS; safe to re-run alongside another agent's own
-- migration). Adds: audit mode/max_measurable/llm_cost_usd legibility columns, the
-- outreach.score_at_send stamp (written by daily_queue.py, owned by another agent — this
-- migration only adds the column; see CONTRACTS.md), and deals evidence-ref columns backing the
-- guarantee-proof requirement in deals/deals.py.

alter table audits add column if not exists mode text;
alter table audits add column if not exists max_measurable integer;
alter table audits add column if not exists llm_cost_usd numeric(8,4);

alter table outreach add column if not exists score_at_send integer;

alter table deals add column if not exists evidence_ref text;
alter table deals add column if not exists baseline_evidence_ref text;
