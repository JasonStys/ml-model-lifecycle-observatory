# File: Dockerfile
# Purpose: Build a non-root API image from the locked Python environment.
FROM python:3.13.15-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY requirements.lock pyproject.toml README.md LICENSE ./
COPY src ./src
COPY sql ./sql
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.lock \
    && python -m pip install --no-deps . \
    && useradd --create-home --uid 10001 observatory \
    && mkdir -p /data/models \
    && chown -R observatory:observatory /data

USER observatory
EXPOSE 8000
ENV OBSERVATORY_REGISTRY_PATH=/data/registry.sqlite3 \
    OBSERVATORY_ARTIFACT_ROOT=/data/models

CMD ["uvicorn", "ml_observatory.api:app", "--host", "0.0.0.0", "--port", "8000"]

