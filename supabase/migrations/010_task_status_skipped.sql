-- Allow status='skipped' — a one-time task the user explicitly skipped
-- (distinct from 'completed'; the skip is also logged in task_skips for analytics)
ALTER TABLE tasks DROP CONSTRAINT IF EXISTS tasks_status_check;
ALTER TABLE tasks ADD CONSTRAINT tasks_status_check
  CHECK (status = ANY (ARRAY['active'::text, 'paused'::text, 'completed'::text, 'skipped'::text]));
