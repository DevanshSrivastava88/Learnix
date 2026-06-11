-- Persistent chat history for LLM context (survives bot restarts)
create table if not exists chat_history (
  id         uuid primary key default gen_random_uuid(),
  user_id    bigint not null,
  line       text not null,
  created_at timestamptz not null default now()
);
create index if not exists chat_history_user_idx on chat_history(user_id, created_at desc);
