-- Learnix initial schema (dedicated Supabase project: rqdhaphfyitvtckdjgqg)

create table if not exists goals (
  id          uuid primary key default gen_random_uuid(),
  name        text not null,
  description text,
  target_date date,
  status      text not null default 'in_progress',
  created_at  timestamptz not null default now()
);

create table if not exists topics (
  id           uuid primary key default gen_random_uuid(),
  goal_id      uuid not null references goals(id) on delete cascade,
  parent_id    uuid references topics(id) on delete cascade,
  title        text not null,
  description  text,
  notes        text,
  status       text not null default 'not_started',
  score        text,
  order_index  int not null default 0,
  completed_at timestamptz,
  created_at   timestamptz not null default now()
);

create index if not exists topics_goal_id_idx   on topics(goal_id);
create index if not exists topics_parent_id_idx on topics(parent_id);
create index if not exists topics_status_idx    on topics(status);

create table if not exists quiz_attempts (
  id           uuid primary key default gen_random_uuid(),
  topic_id     uuid not null references topics(id) on delete cascade,
  score        int not null check (score between 0 and 5),
  attempted_at timestamptz not null default now()
);

create table if not exists settings (
  id                  int primary key default 1,
  daily_session_time  text not null default '09:00',
  telegram_user_id    bigint,
  streak              int not null default 0,
  last_study_date     date
);

insert into settings (id) values (1) on conflict (id) do nothing;
