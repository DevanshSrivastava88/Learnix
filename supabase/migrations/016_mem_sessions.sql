-- 016: session recaps (memory spine v2a). One row per concluded session
-- (/wrap, later: idle-gap / daily backstop). extract_memory already produces
-- {summary, mood, open_threads}; we store it so the next session can open with
-- "welcome back — last time we left off on X". See docs/MEMORY_INTEGRATION.md.
-- Applied via the Supabase Management API on 2026-06-16.
create table if not exists mem_sessions (
  id           uuid primary key default gen_random_uuid(),
  user_id      bigint not null,
  summary      text,
  mood         text,
  open_threads jsonb not null default '[]',
  created_at   timestamptz not null default now()
);
create index if not exists mem_sessions_user_idx on mem_sessions(user_id, created_at desc);
