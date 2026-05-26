-- 002_phase1_multi_user.sql

-- Add user_id to goals
alter table goals add column user_id bigint not null default 0;
alter table goals alter column user_id drop default;
create index goals_user_id_idx on goals(user_id);

-- Drop singleton settings, replace with per-user
drop table settings;
create table settings (
  user_id            bigint primary key,
  daily_session_time text not null default '09:00',
  morning_brief_time text not null default '08:00',
  eod_time           text not null default '21:00',
  streak             int not null default 0,
  last_study_date    date
);

-- New tasks table (habits + milestones)
create table tasks (
  id               uuid primary key default gen_random_uuid(),
  user_id          bigint not null,
  title            text not null,
  task_type        text not null check (task_type in ('habit', 'milestone')),
  status           text not null default 'active' check (status in ('active', 'paused', 'completed')),
  description      text,
  next_reminder_at timestamptz,
  recurrence_days  int,
  target_date      date,
  created_at       timestamptz not null default now()
);
create index tasks_user_id_idx on tasks(user_id);
create index tasks_reminder_idx on tasks(next_reminder_at) where status = 'active';

-- Milestones (checklist items for milestone-type tasks)
create table milestones (
  id          uuid primary key default gen_random_uuid(),
  task_id     uuid not null references tasks(id) on delete cascade,
  title       text not null,
  done        boolean not null default false,
  order_index int not null default 0
);
create index milestones_task_id_idx on milestones(task_id);
