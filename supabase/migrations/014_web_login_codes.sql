-- 014: one-time codes for web login (bot-initiated). User sends /weblogin to the
-- bot; the bot mints a short-lived single-use code tied to their user_id and DMs
-- it. The web verifies the code and issues a signed session cookie scoped to that
-- user_id (multi-user). Applied via the Supabase Management API on 2026-06-15.
create table if not exists web_login_codes (
  code        text primary key,
  user_id     bigint not null,
  created_at  timestamptz not null default now(),
  expires_at  timestamptz not null,
  used        boolean not null default false
);
create index if not exists web_login_codes_user_idx on web_login_codes(user_id);
