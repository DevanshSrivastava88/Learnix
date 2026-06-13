-- Persona option: chat tone selector (default | flirty)
ALTER TABLE settings ADD COLUMN IF NOT EXISTS persona text NOT NULL DEFAULT 'default';
