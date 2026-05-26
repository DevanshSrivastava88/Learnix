-- 003_activity_log.sql
-- Stores one row per user activity event for trend graph
create table activity_log (
  id         uuid primary key default gen_random_uuid(),
  user_id    bigint not null,
  event_type text not null check (event_type in ('study', 'habit', 'milestone')),
  event_date date not null default current_date,
  note       text,
  created_at timestamptz not null default now()
);
create index activity_log_user_date_idx on activity_log(user_id, event_date);
