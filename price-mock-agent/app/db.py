from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.settings import settings

engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)


def claim_next_task(session: Session) -> dict | None:
    row = session.execute(
        text(
            """
            UPDATE price_search_tasks
            SET status = 'processing', picked_at = now()
            WHERE id = (
                SELECT id FROM price_search_tasks
                WHERE status = 'pending'
                ORDER BY created_at
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            RETURNING id, object_id, analysis_report_id, spec_json, status
            """
        )
    ).mappings().first()
    session.commit()
    return dict(row) if row else None


def fail_task(session: Session, task_id: int, error_message: str) -> None:
    session.execute(
        text(
            """
            UPDATE price_search_tasks
            SET status = 'failed', error_message = :error, completed_at = now()
            WHERE id = :id
            """
        ),
        {"id": task_id, "error": error_message[:2000]},
    )
    session.commit()


def complete_task(session: Session, task_id: int, payload: dict) -> None:
    session.execute(
        text(
            """
            INSERT INTO price_reports (
                task_id, object_id, value_min, value_point, value_max, currency,
                justification, comparables_json, confidence, data_source, is_mock,
                prompt_version, llm_model, tokens_in, tokens_out, processing_ms
            ) VALUES (
                :task_id, :object_id, :value_min, :value_point, :value_max, :currency,
                :justification, CAST(:comparables_json AS jsonb), :confidence, :data_source, true,
                :prompt_version, :llm_model, :tokens_in, :tokens_out, :processing_ms
            )
            """
        ),
        payload,
    )
    session.execute(
        text(
            """
            UPDATE price_search_tasks
            SET status = 'completed', error_message = NULL, completed_at = now()
            WHERE id = :id
            """
        ),
        {"id": task_id},
    )
    session.commit()
