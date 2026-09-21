-- Migration 0002: v_pipeline reply/test-recipient columns.
-- Idempotent (safe to re-run, safe to re-run alongside another agent's own outreach-column
-- migration since every ADD COLUMN is IF NOT EXISTS): adds the outreach columns v_pipeline needs
-- to mirror reply state and mock/test sends to the "pipeline" Google Sheet tab, then rebuilds the
-- view. reply_sentiment/replied_at/gmail_thread_id already exist on outreach as of 0001_initial.sql.

alter table outreach add column if not exists reply_summary text;
alter table outreach add column if not exists reply_suggested_next_step text;
alter table outreach add column if not exists notified_at timestamptz;
alter table outreach add column if not exists test_recipient text;

create or replace view v_pipeline as
select b.name, b.suburb, b.metro, b.website_url, b.owner_name, b.owner_email, b.email_status,
       a.total_score, a.bucket, p.subdomain_url as preview_url, p.status as preview_status,
       o.touch, o.status as outreach_status, o.sent_at, o.next_touch_at,
       o.reply_sentiment, o.reply_summary, o.replied_at, o.test_recipient
from businesses b
left join lateral (select * from audits where business_id = b.id order by audited_at desc limit 1) a on true
left join lateral (select * from previews where business_id = b.id order by created_at desc limit 1) p on true
left join lateral (select * from outreach where business_id = b.id order by touch desc limit 1) o on true
where b.is_chain = false and b.drop_reason is null;
