# Single self-contained image for the Learnix web app.
# Build context = web/ (this folder). Root dir on Railway = web.
# Nothing here touches the bot service — fully isolated.

# --- stage 1: build the React frontend --------------------------------------
FROM node:20-alpine AS ui
WORKDIR /ui
COPY ui/package.json ui/package-lock.json ./
RUN npm ci
COPY ui/ ./
RUN npm run build

# --- stage 2: python API that serves /api + the built frontend --------------
FROM python:3.11-slim
WORKDIR /app

COPY api/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY api/main.py ./main.py
# vendored thin data layer (supabase_svc + tasks pkg) — see web/api/_bot/README
COPY api/_bot ./_bot
# built frontend
COPY --from=ui /ui/dist ./static

ENV LEARNIX_BOT_DIR=/app/_bot
EXPOSE 8000
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
