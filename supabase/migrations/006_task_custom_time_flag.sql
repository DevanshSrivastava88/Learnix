-- Track whether a task's reminder time was explicitly set by the user (vs default creation timestamp)
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS has_custom_time boolean NOT NULL DEFAULT false;
