import json
import logging
import time

from app import db
from app.db import SessionLocal
from app.llm import generate

log = logging.getLogger("price_mock_agent")


def process_task(task: dict) -> None:
    started = time.monotonic()
    session = SessionLocal()
    try:
        spec = task.get("spec_json") or {}
        if isinstance(spec, str):
            spec = json.loads(spec)
        result, meta = generate(spec)
        db.complete_task(
            session,
            task["id"],
            {
                "task_id": task["id"],
                "object_id": task["object_id"],
                "value_min": result.value_min,
                "value_point": result.value_point,
                "value_max": result.value_max,
                "currency": result.currency or "RUB",
                "justification": result.justification,
                "comparables_json": json.dumps(
                    [item.model_dump() for item in result.comparables],
                    ensure_ascii=False,
                ),
                "confidence": result.confidence,
                "data_source": "mock_llm_v1",
                "prompt_version": meta["prompt_version"],
                "llm_model": meta["llm_model"],
                "tokens_in": meta["tokens_in"],
                "tokens_out": meta["tokens_out"],
                "processing_ms": int((time.monotonic() - started) * 1000),
            },
        )
        log.info(
            "price report saved",
            extra={"extra_data": {"task_id": task["id"], "object_id": task["object_id"]}},
        )
    except Exception as exc:
        log.exception("price task failed", extra={"extra_data": {"task_id": task.get("id")}})
        try:
            db.fail_task(session, task["id"], str(exc))
        except Exception:
            log.exception("failed to mark task failed")
    finally:
        session.close()
