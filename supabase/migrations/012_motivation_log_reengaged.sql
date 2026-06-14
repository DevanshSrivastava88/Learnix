-- 012: outcome tracking for the motivation engine (memory-of-what-works).
-- After a nudge is sent, a poller pass marks whether the user re-engaged
-- (completed a habit/study) within 24h. NULL = not yet scored / too early.
-- Applied via the Supabase Management API on 2026-06-15.
alter table motivation_log add column if not exists reengaged boolean;
