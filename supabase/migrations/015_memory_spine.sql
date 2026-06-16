-- 015: memory spine (exo-cortex port, v1 tracer bullet).
-- Shared long-term-memory substrate for the coach: durable user facts + a typed
-- sentiment timeline. Extraction runs every turn (cheap LLM -> strict JSON),
-- ground-truth + anti-meta filtered. Feeds the reply context + motivation engine.
-- Full-life scope, weighted to 3 dominant pillars: productivity | motivation | addiction.
-- See docs/MEMORY_INTEGRATION.md. Applied via the Supabase Management API on 2026-06-16.

-- Durable facts about the USER (only what they confirmed; never the bot's guesses).
-- status enables the fact-UPDATE/retire path (our fix for Atlas's append-only gap):
-- a correction marks the old fact 'superseded' instead of leaving a contradiction.
create table if not exists user_facts (
  id            uuid primary key default gen_random_uuid(),
  user_id       bigint not null,
  text          text not null,
  pillar        text not null default 'general',   -- productivity | motivation | addiction | general
  status        text not null default 'active',    -- active | superseded | removed
  superseded_by uuid,                               -- -> user_facts.id that replaced this one
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);
create index if not exists user_facts_user_idx on user_facts(user_id, status);

-- Typed timeline of moments (mood/progress/setback/milestone/insight/prediction).
-- sentiment -1..1, intensity 0..1. pillar tags it for dominance weighting.
create table if not exists mem_events (
  id         uuid primary key default gen_random_uuid(),
  user_id    bigint not null,
  type       text not null,                          -- mood|progress|setback|milestone|insight|prediction|event
  summary    text not null,
  detail     text,
  pillar     text not null default 'general',        -- productivity | motivation | addiction | general
  sentiment  real default 0.0,
  intensity  real default 0.0,
  tags       jsonb not null default '[]',
  session_id text,
  turn_id    text,
  created_at timestamptz not null default now()
);
create index if not exists mem_events_user_idx on mem_events(user_id, created_at desc);
