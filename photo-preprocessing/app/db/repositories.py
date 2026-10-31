from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Batch, Object, ProcessingQueue, Survey

BLOCKING_STATUSES = ("validated", "duplicate")


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
    return await session.get(Survey, survey_id)


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
        if row.status in BLOCKING_STATUSES:
            return row
    return None


async def active_objects(session: AsyncSession) -> list[Object]:
    res = await session.execute(select(Object).where(Object.status == "active"))
    return list(res.scalars())


async def insert_queue_row(session: AsyncSession, survey_id: int, object_id: str) -> None:
    exists = await session.execute(select(ProcessingQueue.id).where(ProcessingQueue.survey_id == survey_id))
    if exists.scalar_one_or_none() is not None:
        return
    session.add(ProcessingQueue(survey_id=survey_id, object_id=object_id))
    await session.commit()


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