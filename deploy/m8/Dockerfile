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

# M8 keeps a frozen backend runtime snapshot plus narrowly scoped hardening overlays.
# Use the committed runtime archive directly; the previous Base64 chunk reconstruction
# added build noise without changing the payload.
COPY threshold_m8_backend_runtime.tar.gz /tmp/runtime.tar.gz
COPY apply_shopify_hardening.py /tmp/apply_shopify_hardening.py
COPY apply_shopify_expiring_tokens.py /tmp/apply_shopify_expiring_tokens.py
COPY apply_vault_read_support.py /tmp/apply_vault_read_support.py
COPY apply_stripe_hardening.py /tmp/apply_stripe_hardening.py
COPY apply_celery_recovery_hardening.py /tmp/apply_celery_recovery_hardening.py
COPY apply_readiness_head_patch.py /tmp/apply_readiness_head_patch.py

RUN sha256sum /tmp/runtime.tar.gz \
    && tar -xzf /tmp/runtime.tar.gz -C /app \
    && rm -f /tmp/runtime.tar.gz \
    && pip install -r /app/requirements.txt \
    && python /tmp/apply_shopify_hardening.py \
    && python /tmp/apply_vault_read_support.py \
    && python /tmp/apply_shopify_expiring_tokens.py \
    && python /tmp/apply_stripe_hardening.py \
    && python /tmp/apply_celery_recovery_hardening.py \
    && python /tmp/apply_readiness_head_patch.py \
    && python -m compileall -q /app/app \
    && rm -f /tmp/apply_shopify_hardening.py /tmp/apply_vault_read_support.py /tmp/apply_shopify_expiring_tokens.py /tmp/apply_stripe_hardening.py /tmp/apply_celery_recovery_hardening.py /tmp/apply_readiness_head_patch.py

COPY frontend_index.html /app/frontend_index.html
COPY staging_entry.py /app/staging_entry.py
COPY worker_supervisor.py /app/worker_supervisor.py
COPY beat_supervisor.py /app/beat_supervisor.py
COPY e8b0c234f6a8_billing_timestamp_defaults.py /app/alembic/versions/e8b0c234f6a8_billing_timestamp_defaults.py
COPY scripts /app/scripts

RUN chown -R threshold:threshold /app

USER threshold

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://127.0.0.1:8000/health || exit 1

CMD ["uvicorn", "staging_entry:app", "--host", "0.0.0.0", "--port", "8000"]
