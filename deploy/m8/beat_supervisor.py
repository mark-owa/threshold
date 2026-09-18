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
DISPATCH_STALE_SECONDS = 20.0
stopping = False
child: subprocess.Popen | None = None
last_dispatch_at = time.monotonic()


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
        print("threshold-beat-supervisor: broker unavailable; waiting", flush=True)
        time.sleep(CHECK_SECONDS)


def pump_output(proc: subprocess.Popen) -> None:
    global last_dispatch_at
    assert proc.stdout is not None
    for line in proc.stdout:
        print(line, end="", flush=True)
        if "Scheduler: Sending due task dispatch-outbox" in line:
            last_dispatch_at = time.monotonic()


def start_beat() -> subprocess.Popen:
    global last_dispatch_at
    last_dispatch_at = time.monotonic()
    print("threshold-beat-supervisor: starting Celery beat", flush=True)
    proc = subprocess.Popen(
        ["celery", "-A", "app.workers.celery_app", "beat", "--loglevel=info"],
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

    child = start_beat()

    while not stopping and child.poll() is None:
        time.sleep(CHECK_SECONDS)
        if not broker_ready():
            print("threshold-beat-supervisor: broker lost; recycling Beat child", flush=True)
            stop_child()
            break
        if time.monotonic() - last_dispatch_at > DISPATCH_STALE_SECONDS:
            print("threshold-beat-supervisor: dispatch heartbeat stale; recycling Beat child", flush=True)
            stop_child()
            break

    if stopping:
        break

    wait_for_broker()
    if child.poll() is not None:
        print(
            f"threshold-beat-supervisor: Celery beat exited with code {child.returncode}; restarting",
            flush=True,
        )
    time.sleep(CHECK_SECONDS)
