import signal
import time

from app.db import SessionLocal
from app import db
from app.logging import setup_logging
from app.settings import settings, yaml_config
from app.worker import process_task

log = setup_logging()
stop_requested = False


def _handle_stop(signum, _frame):
    global stop_requested
    stop_requested = True
    log.info("signal received, will stop after current job", extra={"extra_data": {"signum": signum}})


def main() -> None:
    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)
    interval = int(settings.poll_interval_sec or (yaml_config.get("polling") or {}).get("interval_sec", 5))
    log.info("price-mock-agent started", extra={"extra_data": {"interval_sec": interval}})
    while not stop_requested:
        session = SessionLocal()
        try:
            task = db.claim_next_task(session)
        except Exception:
            log.exception("claim failed")
            task = None
        finally:
            session.close()
        if task:
            log.info("task claimed", extra={"extra_data": {"task_id": task["id"], "object_id": task.get("object_id")}})
            process_task(task)
            continue
        for _ in range(max(interval, 1)):
            if stop_requested:
                break
            time.sleep(1)
    log.info("price-mock-agent stopped")


if __name__ == "__main__":
    main()
