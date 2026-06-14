-- 013: optional adaptive nudge timing (opt-in, default off).
-- When true, the motivation poller fires triggers by condition (ignoring the
-- fixed research hour-windows) and delivers only during the user's learned
-- active hours. Applied via the Supabase Management API on 2026-06-15.
alter table settings add column if not exists adaptive_timing boolean default false;
