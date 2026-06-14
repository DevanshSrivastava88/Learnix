# Single self-contained image for the Learnix web app.
# Build context = REPO ROOT (Railway uploads the whole repo on `up`).
# Railway: set RAILWAY_DOCKERFILE_PATH=web/Dockerfile on the learnix-web service.
# Isolated from the bot service (which builds via railpack from bot/).

# --- stage 1: build the React frontend --------------------------------------
FROM node:20-alpine AS ui
WORKDIR /ui
COPY web/ui/package.json web/ui/package-lock.json ./
RUN npm ci
COPY web/ui/ ./
RUN npm run build

# --- stage 2: python API that serves /api + the built frontend --------------
FROM python:3.11-slim
WORKDIR /app

COPY web/api/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY web/api/main.py ./main.py
# vendor the thin data layer straight from the live bot/ (no drift)
COPY bot/supabase_svc.py ./_bot/supabase_svc.py
COPY bot/tasks ./_bot/tasks
# built frontend
COPY --from=ui /ui/dist ./static

ENV LEARNIX_BOT_DIR=/app/_bot
EXPOSE 8000
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
