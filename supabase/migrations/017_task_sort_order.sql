-- Manual ordering for the web task list. When set, the web UI honours this
-- order instead of the due-time sort. NULL = fall back to due-based sort.
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS sort_order integer;
