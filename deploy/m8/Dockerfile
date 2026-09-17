FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl tar \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system threshold \
    && useradd --system --gid threshold --home /app threshold

COPY threshold_m8_backend_runtime.tar.gz /tmp/threshold-runtime.tar.gz
RUN tar -xzf /tmp/threshold-runtime.tar.gz -C /app \
    && rm /tmp/threshold-runtime.tar.gz \
    && pip install -r /app/requirements.txt \
    && chown -R threshold:threshold /app

USER threshold

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD sh -c 'curl -f http://127.0.0.1:${PORT:-8000}/health || exit 1'

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
