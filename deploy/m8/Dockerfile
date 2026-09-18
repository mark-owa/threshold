FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates coreutils tar \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system threshold \
    && useradd --system --gid threshold --home /app threshold

COPY runtime.b64.part-* /tmp/runtime-parts/

RUN cat /tmp/runtime-parts/runtime.b64.part-* \
    | base64 -d > /tmp/runtime.tar.gz \
    && echo "7ecf6c3b6bb1cf493c9145a4de8f47d3a4373d49ee1815a92bf07aca57846338  /tmp/runtime.tar.gz" | sha256sum -c - \
    && tar -xzf /tmp/runtime.tar.gz -C /app \
    && rm -rf /tmp/runtime-parts /tmp/runtime.tar.gz \
    && pip install -r /app/requirements.txt

COPY frontend_index.html /app/frontend_index.html
COPY staging_entry.py /app/staging_entry.py

RUN chown -R threshold:threshold /app

USER threshold

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://127.0.0.1:8000/health || exit 1

CMD ["uvicorn", "staging_entry:app", "--host", "0.0.0.0", "--port", "8000"]
