FROM python:3.12.14-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app/backend

COPY backend/pyproject.toml ./pyproject.toml
COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./alembic.ini
RUN pip install --no-cache-dir .

COPY framework-packs /app/framework-packs
COPY backend/demo-files /app/demo-files
COPY agents /app/agents
COPY skills /app/skills
COPY docker/entrypoint-api.sh /usr/local/bin/entrypoint-api

RUN addgroup --system --gid 10001 ccm \
    && adduser --system --uid 10001 --ingroup ccm --home /app ccm \
    && mkdir -p /data/db /data/files \
    && chown -R ccm:ccm /app /data \
    && chmod 0555 /usr/local/bin/entrypoint-api

USER 10001:10001
EXPOSE 8000
ENTRYPOINT ["entrypoint-api"]
