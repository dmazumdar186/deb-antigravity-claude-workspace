-- ProdCraft med-spa pipeline — Supabase (Postgres) schema.
-- Apply with: psql "$SUPABASE_DB_URL" -f db/schema.sql   (or paste into the Supabase SQL editor)
-- Idempotent: safe to re-run. Migration history: db/migrations/ (this file is the flattened current state).

create extension if not exists pgcrypto;

create table if not exists businesses (
  id              uuid primary key default gen_random_uuid(),
  place_id        text not null unique,
  name            text not null,
  slug            text not null unique,
  address         text,
  city            text,
  suburb          text,
  metro           text not null,
  state           text,
  lat             double precision,
  lng             double precision,
  phone           text,
  website_url     text,
  final_url       text,
  rating          numeric(3,2),
  review_count    integer,
  primary_type    text,
  business_status text,
  is_chain        boolean not null default false,
  drop_reason     text,                       -- null = kept; else why discovery dropped it (chain|closed|too_small)
  owner_name      text,
  owner_first     text,
  owner_email     text,
  email_status    text,                       -- deliverable|undeliverable|risky|unknown|null
  email_source    text,                       -- contact_page|gbp_reviews|state_registry|apollo|findymail|hunter|generic_inbox
  do_not_contact  boolean not null default false,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);
create index if not exists businesses_metro_idx on businesses (metro);

create table if not exists audits (
  id                    uuid primary key default gen_random_uuid(),
  business_id           uuid not null references businesses(id) on delete cascade,
  audited_at            timestamptz not null default now(),
  score_version         text not null default '1.0',
  psi_mobile            integer,
  psi_desktop           integer,
  has_website           boolean not null default true,
  has_ssl               boolean,
  is_mobile_friendly    boolean,
  builder               text,
  theme                 text,
  theme_year            integer,
  has_jquery_legacy     boolean,
  booking_widget        text,                 -- vagaro|mindbody|boulevard|zenoti|acuity|calendly|square|aesthetic_record|patientnow|moxie|null
  has_cta_above_fold    boolean,
  has_analytics         boolean,
  footer_year           integer,
  vision_dated_score    integer,              -- 0..10
  vision_rationale      text,
  vision_model_id       text,
  vision_prompt_sha256  text,
  total_score           integer not null,
  bucket                text not null,        -- qualified|borderline|skip
  gaps                  jsonb not null default '[]'::jsonb,  -- ordered list of {signal, points, human_phrase}
  screenshot_mobile_url text,
  screenshot_desktop_url text,
  raw                   jsonb not null default '{}'::jsonb
);
create index if not exists audits_business_idx on audits (business_id, audited_at desc);

create table if not exists previews (
  id             uuid primary key default gen_random_uuid(),
  business_id    uuid not null references businesses(id) on delete cascade,
  template_id    text not null default 'medspa-v1',
  slug_suffix    text not null,                -- 6 chars, unguessable
  subdomain_url  text not null unique,         -- https://{slug}-{suffix}.preview.prodcraft.fyi
  status         text not null default 'review', -- review|approved|live|expired|takedown
  content        jsonb not null,               -- the business.json that was rendered
  content_hash   text not null,
  deployed_at    timestamptz,
  expires_at     timestamptz,
  takedown       boolean not null default false,
  takedown_at    timestamptz,
  created_at     timestamptz not null default now()
);
create index if not exists previews_business_idx on previews (business_id);

create table if not exists outreach (
  id                uuid primary key default gen_random_uuid(),
  business_id       uuid not null references businesses(id) on delete cascade,
  preview_id        uuid references previews(id),
  audit_id          uuid references audits(id),
  touch             integer not null check (touch between 1 and 4),
  status            text not null default 'queued', -- queued|drafted|sent|replied|call_booked|closed_won|closed_lost|dnc
  template_variant  text,                            -- a|b|c for touch 1
  gap_primary       text,
  draft_subject     text,
  draft_body        text,
  gmail_draft_id    text,
  gmail_thread_id   text,
  sent_at           timestamptz,
  replied_at        timestamptz,
  reply_sentiment   text,                            -- positive|neutral|negative|remove|bounce
  reply_excerpt     text,
  next_touch_at     date,
  notes             text,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now(),
  unique (business_id, touch)
);
create index if not exists outreach_queue_idx on outreach (next_touch_at, status);

create table if not exists deals (
  id                             uuid primary key default gen_random_uuid(),
  business_id                    uuid not null references businesses(id) on delete cascade,
  tier                           text not null,   -- founding|starter|growth|premium
  setup_price                    numeric(10,2) not null,
  mrr                            numeric(10,2) not null,
  contract_signed_at             date,
  deposit_paid_at                date,
  baseline_online_bookings_30d   integer,
  current_booking_tool           text,
  live_at                        date,
  bookings_60d                   integer,
  guarantee_met                  boolean,         -- computed: bookings_60d > baseline*2 (60d vs 30d baseline)
  balance_paid_at                date,
  care_plan_active               boolean not null default false,
  notes                          text,
  created_at                     timestamptz not null default now()
);

create table if not exists metro_stats (
  id             uuid primary key default gen_random_uuid(),
  metro          text not null,
  sampled        integer not null,
  qualified      integer not null,
  pct_qualified  numeric(5,2) not null,
  ci_low         numeric(5,2) not null,   -- Wilson 95%
  ci_high        numeric(5,2) not null,
  score_version  text not null,
  measured_at    timestamptz not null default now()
);

create table if not exists config (
  key        text primary key,
  value      jsonb not null,
  updated_at timestamptz not null default now()
);
-- Seeded keys: phase0 {"passed": false, "sends": 0, "calls_booked": 0, "queue_cap_locked": 5, "queue_cap_open": 20}
--              proof_lines []  (strings the touch-3/4 templates may cite; empty = fall back to industry stats)
--              sender {"name": "", "physical_address": "", "signature": ""}

create table if not exists events (
  id          bigserial primary key,
  entity      text not null,      -- business|audit|preview|outreach|deal
  entity_id   uuid not null,
  event       text not null,      -- e.g. status:queued->sent, takedown, expired
  payload     jsonb not null default '{}'::jsonb,
  created_at  timestamptz not null default now()
);
create index if not exists events_entity_idx on events (entity, entity_id);

create table if not exists chains (
  pattern   text primary key,     -- lowercase substring matched against business name
  note      text
);

-- Read-only mirror for Sheets
create or replace view v_pipeline as
select b.name, b.suburb, b.metro, b.website_url, b.owner_name, b.owner_email, b.email_status,
       a.total_score, a.bucket, p.subdomain_url as preview_url, p.status as preview_status,
       o.touch, o.status as outreach_status, o.sent_at, o.next_touch_at
from businesses b
left join lateral (select * from audits where business_id = b.id order by audited_at desc limit 1) a on true
left join lateral (select * from previews where business_id = b.id order by created_at desc limit 1) p on true
left join lateral (select * from outreach where business_id = b.id order by touch desc limit 1) o on true
where b.is_chain = false and b.drop_reason is null;

-- updated_at triggers
create or replace function set_updated_at() returns trigger language plpgsql as $$
begin new.updated_at = now(); return new; end $$;
do $$ begin
  if not exists (select 1 from pg_trigger where tgname = 'businesses_updated_at') then
    create trigger businesses_updated_at before update on businesses for each row execute function set_updated_at();
  end if;
  if not exists (select 1 from pg_trigger where tgname = 'outreach_updated_at') then
    create trigger outreach_updated_at before update on outreach for each row execute function set_updated_at();
  end if;
end $$;

-- Row Level Security: the pipeline uses the service key; anon gets nothing.
alter table businesses enable row level security;
alter table audits enable row level security;
alter table previews enable row level security;
alter table outreach enable row level security;
alter table deals enable row level security;
alter table metro_stats enable row level security;
alter table config enable row level security;
alter table events enable row level security;
alter table chains enable row level security;
