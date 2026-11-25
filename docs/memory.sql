-- Dani's memory (V1). Paste this once in Supabase → SQL Editor → Run.
-- Row Level Security is on with no policies: only Dani's server (service key) can read or write.

create table if not exists conversations (
  id bigserial primary key,
  at timestamptz not null default now(),
  channel text not null,            -- app | telegram | phone
  role text not null check (role in ('user', 'assistant')),
  content text not null,
  agent text not null default 'dani'
);
create index if not exists conversations_channel_at on conversations (channel, at desc);

create table if not exists events (
  id bigserial primary key,
  at timestamptz not null default now(),
  kind text not null,               -- briefing | reminder | evening | wake_call | proposal | suggestion
  ref text not null default '',     -- what it is about (event title, proposal id, ...)
  detail jsonb not null default '{}',
  reaction text,                    -- answered | ignored | done | snoozed | confirmed | rejected | awake | no_answer
  reacted_at timestamptz,
  agent text not null default 'dani'
);
create index if not exists events_kind_at on events (kind, at desc);

create table if not exists measures (
  id bigserial primary key,
  day date not null,
  name text not null,               -- energy | sleep_hours | sleep_efficiency | steps | resting_hr
  value double precision not null,
  source text not null,             -- diary | fitbit
  unique (day, name, source)
);

create table if not exists kv (
  key text primary key,
  value text not null,
  updated_at timestamptz not null default now()
);

alter table conversations enable row level security;
alter table events enable row level security;
alter table measures enable row level security;
alter table kv enable row level security;
