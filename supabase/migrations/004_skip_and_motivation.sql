-- 004_skip_and_motivation.sql

-- System 1: Skip log
create table task_skips (
  id         uuid primary key default gen_random_uuid(),
  user_id    bigint not null,
  task_id    uuid not null references tasks(id) on delete cascade,
  skipped_at timestamptz not null default now(),
  note       text  -- 'outright' | 'rescheduled_to:<iso>'
);
create index task_skips_user_date_idx on task_skips(user_id, skipped_at);
create index task_skips_task_idx      on task_skips(task_id);

-- System 4: Motivation delivery dedup log
create table motivation_log (
  id           uuid primary key default gen_random_uuid(),
  user_id      bigint not null,
  trigger_type text not null,  -- 'daily_skip_burst' | 'low_weekly_rate' | 'streak_broken' | 'no_activity'
  sent_at      timestamptz not null default now()
);
create index motivation_log_user_idx on motivation_log(user_id, sent_at);
