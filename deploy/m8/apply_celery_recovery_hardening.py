from pathlib import Path

path = Path("/app/app/workers/celery_app.py")
source = path.read_text()

old = '''celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
)
'''

new = '''celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    # Threshold's durable outbox depends on workers eventually resuming after
    # a transient Redis interruption, so do not rely on library defaults.
    broker_connection_retry=True,
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=None,
    broker_channel_error_retry=True,
    task_publish_retry=True,
    task_publish_retry_policy={
        "max_retries": None,
        "interval_start": 0,
        "interval_step": 1,
        "interval_max": 5,
    },
    redis_socket_keepalive=True,
    redis_retry_on_timeout=True,
)
'''

if old not in source:
    raise SystemExit("Expected Celery config block not found; refusing unsafe resilience patch")

path.write_text(source.replace(old, new, 1))
print("Celery recovery hardening patch applied")
