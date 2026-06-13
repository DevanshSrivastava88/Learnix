-- Guided daily study plan: spread a goal's topics across calendar days
ALTER TABLE goals  ADD COLUMN IF NOT EXISTS start_date date;
ALTER TABLE topics ADD COLUMN IF NOT EXISTS scheduled_date date;
CREATE INDEX IF NOT EXISTS idx_topics_scheduled ON topics (goal_id, scheduled_date);
