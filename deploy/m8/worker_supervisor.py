import os
import signal
import subprocess
import threading
import time

import redis

from app.core.config import get_settings

settings = get_settings()
BROKER_URL = settings.CELERY_BROKER_URL
CHECK_SECONDS = 1.0
STOP_TIMEOUT = 10.0
stopping = False
child: subprocess.Popen | None = None
broker_loss = threading.Event()


def broker_ready() -> bool:
    try:
        client = redis.Redis.from_url(
            BROKER_URL,
            socket_connect_timeout=1,
            socket_timeout=1,
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


def pump_output(proc: subprocess.Popen) -> None:
    assert proc.stdout is not None
    for line in proc.stdout:
        print(line, end="", flush=True)
        if (
            "Connection to broker lost" in line
            or "consumer: Cannot connect to redis://" in line
        ):
            broker_loss.set()


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
    proc = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    threading.Thread(target=pump_output, args=(proc,), daemon=True).start()
    return proc


signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)

while not stopping:
    wait_for_broker()
    if stopping:
        break

    broker_loss.clear()
    child = start_worker()

    while not stopping and child.poll() is None:
        if broker_loss.wait(timeout=0.5):
            print(
                "threshold-worker-supervisor: Celery reported broker loss; recycling child",
                flush=True,
            )
            stop_child()
            break

    if stopping:
        break

    wait_for_broker()
    if child.poll() is not None:
        print(
            f"threshold-worker-supervisor: Celery exited with code {child.returncode}; restarting",
            flush=True,
        )
    time.sleep(CHECK_SECONDS)
