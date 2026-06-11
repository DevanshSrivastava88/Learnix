-- Allow 'task' as a task_type (one-time reminders without recurrence)
ALTER TABLE tasks DROP CONSTRAINT IF EXISTS tasks_task_type_check;
ALTER TABLE tasks ADD CONSTRAINT tasks_task_type_check
  CHECK (task_type IN ('habit', 'milestone', 'task'));
