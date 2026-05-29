-- 005_twilio_settings.sql

alter table settings
  add column if not exists twilio_enabled boolean not null default false;
