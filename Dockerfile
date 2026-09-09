FROM node:22-alpine AS web
WORKDIR /web
COPY web ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi \
    && npm run build

FROM python:3.12-slim

WORKDIR /app

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8080 \
    DATA_DIR=/data \
    DATABASE_URL=sqlite:////data/hub.db \
    LOG_DIR=/data/logs

RUN python3 -m venv /opt/venv \
    && pip install --no-cache-dir -U pip

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY version.txt ./
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY --from=web /web/dist ./web/dist

RUN groupadd --gid 1001 app \
    && useradd --create-home --no-log-init --uid 1001 --gid 1001 \
        --shell /usr/sbin/nologin app \
    && mkdir -p /data \
    && chown -R 1001:1001 /data

EXPOSE 8080
VOLUME ["/data"]

USER 1001

CMD ["sh", "-c", "uvicorn app.main:app --host ${HOST:-0.0.0.0} --port ${PORT:-8080} --workers 1"]
