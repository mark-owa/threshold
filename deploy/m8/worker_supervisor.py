import os
import signal
import subprocess
import time

import redis

from app.core.config import get_settings

settings = get_settings()
BROKER_URL = settings.CELERY_BROKER_URL
CHECK_SECONDS = 2.0
FAILURE_THRESHOLD = 2
STOP_TIMEOUT = 10.0
stopping = False
child: subprocess.Popen | None = None


def broker_ready() -> bool:
    try:
        client = redis.Redis.from_url(
            BROKER_URL,
            socket_connect_timeout=2,
            socket_timeout=2,
            decode_responses=False,
        )
        return bool(client.ping())
    except Exception:
        return False


def stop_child() -> None:
    global child
    if child is None or child.poll() is not None:
        return
    child.terminate()
    try:
        child.wait(timeout=STOP_TIMEOUT)
    except subprocess.TimeoutExpired:
        child.kill()
        child.wait(timeout=5)


def handle_signal(signum, _frame) -> None:
    global stopping
    stopping = True
    stop_child()
    raise SystemExit(128 + signum)


def wait_for_broker() -> None:
    while not stopping and not broker_ready():
        print("threshold-worker-supervisor: broker unavailable; waiting", flush=True)
        time.sleep(CHECK_SECONDS)


def start_worker() -> subprocess.Popen:
    concurrency = os.getenv("CELERY_WORKER_CONCURRENCY", "2")
    command = [
        "celery",
        "-A",
        "app.workers.celery_app",
        "worker",
        "--loglevel=info",
        f"--concurrency={concurrency}",
    ]
    print("threshold-worker-supervisor: starting Celery worker", flush=True)
    return subprocess.Popen(command)


signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)

while not stopping:
    wait_for_broker()
    if stopping:
        break

    child = start_worker()
    consecutive_failures = 0

    while not stopping and child.poll() is None:
        time.sleep(CHECK_SECONDS)
        if broker_ready():
            consecutive_failures = 0
            continue
        consecutive_failures += 1
        if consecutive_failures >= FAILURE_THRESHOLD:
            print(
                "threshold-worker-supervisor: broker lost; recycling Celery child",
                flush=True,
            )
            stop_child()
            break

    if stopping:
        break

    if child.poll() is not None:
        print(
            f"threshold-worker-supervisor: Celery exited with code {child.returncode}; restarting",
            flush=True,
        )
    time.sleep(CHECK_SECONDS)
