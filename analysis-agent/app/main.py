import signal
import time

from app.db import repo
from app.db.session import SessionLocal, init_db
from app.logging import setup_logging
from app.settings import yaml_config
from app.worker import process_job

log = setup_logging()
stop_requested = False


def _handle_stop(signum, _frame):
    global stop_requested
    stop_requested = True
    log.info("signal received, will stop after current job", extra={"extra_data": {"signum": signum}})


def main() -> None:
    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)
    init_db()
    interval = int((yaml_config.get("polling") or {}).get("interval_sec", 10))
    log.info("analysis-agent started", extra={"extra_data": {"interval_sec": interval}})
    while not stop_requested:
        session = SessionLocal()
        try:
            job = repo.claim_next_job(session)
        finally:
            session.close()
        if job:
            log.info("job claimed", extra={"extra_data": {"queue_id": job["id"], "survey_id": job["survey_id"]}})
            process_job(job)
            continue
        for _ in range(interval):
            if stop_requested:
                break
            time.sleep(1)
    log.info("analysis-agent stopped")


if __name__ == "__main__":
    main()
