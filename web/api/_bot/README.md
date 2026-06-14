# Vendored at build/commit time from bot/ — the thin data layer the web API imports.
# Source of truth is bot/supabase_svc.py + bot/tasks/{__init__,svc}.py.
# Only used inside the Docker image (LEARNIX_BOT_DIR=/app/_bot); local dev uses the live bot/.
# If bot/tasks/svc.py or supabase_svc.py change, re-copy these three files.
