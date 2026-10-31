import json
from uuid import uuid4

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Batch, Object, ProcessingQueue, Survey

# Тот же файл (хэш) не принимаем повторно, пока он уже в работе или в хранилище.
# Ракурсы одного объекта с разным хэшем сюда не попадают.
BLOCKING_STATUSES = ("pending", "processing", "validated", "needs_manual_match", "duplicate")


async def create_batch(session: AsyncSession, batch_id: str, operator_id: str) -> Batch:
    batch = Batch(id=batch_id, operator_id=operator_id)
    session.add(batch)
    await session.commit()
    return batch


async def get_batch(session: AsyncSession, batch_id: str) -> Batch | None:
    return await session.get(Batch, batch_id)


async def set_batch_status(session: AsyncSession, batch_id: str, status: str) -> None:
    await session.execute(update(Batch).where(Batch.id == batch_id).values(status=status))
    await session.commit()


async def add_survey(session: AsyncSession, **fields) -> Survey:
    survey = Survey(**fields)
    session.add(survey)
    await session.commit()
    await session.refresh(survey)
    return survey


async def get_survey(session: AsyncSession, survey_id: int) -> Survey | None:
    res = await session.execute(
        select(Survey).options(selectinload(Survey.object_)).where(Survey.id == survey_id)
    )
    return res.scalar_one_or_none()


async def update_survey(session: AsyncSession, survey_id: int, **fields) -> None:
    await session.execute(update(Survey).where(Survey.id == survey_id).values(**fields))
    await session.commit()


async def list_surveys(session: AsyncSession, batch_id: str) -> list[Survey]:
    res = await session.execute(select(Survey).where(Survey.batch_id == batch_id).order_by(Survey.id))
    return list(res.scalars())


async def get_pending_surveys(session: AsyncSession, batch_id: str) -> list[Survey]:
    res = await session.execute(
        select(Survey).where(Survey.batch_id == batch_id, Survey.status == "pending").order_by(Survey.id)
    )
    return list(res.scalars())


async def find_hash_blocking(session: AsyncSession, file_hash: str) -> Survey | None:
    res = await session.execute(select(Survey).where(Survey.file_hash == file_hash))
    for row in res.scalars():
        if row.status in BLOCKING_STATUSES or row.s3_key:
            return row
    return None


async def stored_surveys_for_object(session: AsyncSession, object_id: str) -> list[Survey]:
    res = await session.execute(
        select(Survey).where(Survey.object_id == object_id, Survey.s3_key.is_not(None))
    )
    return list(res.scalars())


async def active_objects(session: AsyncSession) -> list[Object]:
    res = await session.execute(select(Object).where(Object.status == "active"))
    return list(res.scalars())


async def notify_new_photos(session: AsyncSession, object_id: str, filenames: list[str], batch_id: str) -> None:
    if not object_id or not filenames:
        return
    payload = json.dumps({"kind": "new_photo", "batch_id": batch_id, "filenames": filenames[:20]})
    await session.execute(
        text(
            """
            INSERT INTO problem_alerts (id, object_id, title, summary, severity, status, raw_item, is_demo)
            VALUES (:id, :object_id, :title, :summary, 'info', 'new', CAST(:raw AS jsonb), false)
            """
        ),
        {
            "id": f"al_{uuid4().hex[:16]}",
            "object_id": object_id,
            "title": "Новые фото",
            "summary": f"Оператор загрузил {len(filenames)} фото: {', '.join(filenames[:3])}",
            "raw": payload,
        },
    )
    await session.commit()


async def insert_queue_row(session: AsyncSession, survey_id: int, object_id: str) -> None:
    """Совместимость: одно фото = группа из одного id."""
    survey = await get_survey(session, survey_id)
    await upsert_queue_group(
        session,
        batch_id=survey.batch_id if survey else None,
        object_id=object_id,
        survey_ids=[survey_id],
        primary_survey_id=survey_id,
        capture_date=None,
    )


async def upsert_queue_group(
    session: AsyncSession,
    *,
    batch_id: str | None,
    object_id: str,
    survey_ids: list[int],
    primary_survey_id: int | None,
    capture_date,
) -> ProcessingQueue | None:
    if not batch_id or not object_id or not survey_ids:
        return None
    res = await session.execute(
        select(ProcessingQueue).where(
            ProcessingQueue.batch_id == batch_id,
            ProcessingQueue.object_id == object_id,
        )
    )
    row = res.scalar_one_or_none()
    if row is None:
        row = ProcessingQueue(
            survey_id=primary_survey_id,
            survey_ids=survey_ids,
            primary_survey_id=primary_survey_id,
            batch_id=batch_id,
            object_id=object_id,
            capture_date=capture_date,
        )
        session.add(row)
    elif row.status in {"pending", "failed"}:
        row.survey_id = primary_survey_id
        row.survey_ids = survey_ids
        row.primary_survey_id = primary_survey_id
        row.capture_date = capture_date
        row.status = "pending"
        row.completed_at = None
    await session.commit()
    await session.refresh(row)
    return row


async def latest_report_capture_date(session: AsyncSession, object_id: str):
    res = await session.execute(
        text(
            """
            SELECT COALESCE(capture_date, captured_at::date) AS d
            FROM analysis_reports
            WHERE object_id = :object_id
              AND agent_status = 'completed'
              AND COALESCE(capture_date, captured_at::date) IS NOT NULL
            ORDER BY COALESCE(capture_date, captured_at::date) DESC
            LIMIT 1
            """
        ),
        {"object_id": object_id},
    )
    row = res.mappings().first()
    return row["d"] if row else None


async def processing_batches(session: AsyncSession) -> list[Batch]:
    res = await session.execute(select(Batch).where(Batch.status == "processing"))
    return list(res.scalars())


async def reset_stuck_surveys(session: AsyncSession, batch_id: str) -> int:
    """Возвращает застрявшие в processing файлы обратно в pending при рестарте."""
    stmt = update(Survey).where(
        Survey.batch_id == batch_id,
        Survey.status == "processing"
    ).values(status="pending")
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount