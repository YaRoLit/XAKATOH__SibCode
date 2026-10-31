from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Batch, Checkpoint, Object, Survey
from app.services import checkpoints as checkpoint_service
from app.services.checkpoints import SHOOT_WINDOW_DAYS


async def shooting_tasks(session: AsyncSession) -> list[dict]:
    today = date.today()
    window_end = today + timedelta(days=SHOOT_WINDOW_DAYS)
    res = await session.execute(
        select(Checkpoint)
        .options(selectinload(Checkpoint.object_))
        .join(Object, Object.id == Checkpoint.object_id)
        .where(Object.status == "active", Checkpoint.planned_date <= window_end)
        .order_by(Checkpoint.planned_date)
    )
    items = []
    for cp in res.scalars():
        data = await checkpoint_service.serialize_checkpoint(session, cp, today=today, object_name=cp.object_.name)
        if data["shoot_status"] in {"available", "overdue"}:
            data["address"] = cp.object_.address
            data["cadastral_number"] = cp.object_.cadastral_number
            data["plot_corners"] = cp.object_.plot_corners
            items.append(data)
    return items


async def rejected_photos(session: AsyncSession) -> list[dict]:
    res = await session.execute(
        select(Survey).where(Survey.status == "rejected").order_by(Survey.created_at.desc()).limit(50)
    )
    return [_survey_brief(s) for s in res.scalars()]


async def recent_surveys(session: AsyncSession) -> list[dict]:
    res = await session.execute(
        select(Survey)
        .where(Survey.s3_key.is_not(None))
        .order_by(Survey.created_at.desc())
        .limit(30)
    )
    return [_survey_brief(s) for s in res.scalars()]


async def recent_batches(session: AsyncSession) -> list[dict]:
    res = await session.execute(select(Batch).order_by(Batch.created_at.desc()).limit(15))
    return [
        {
            "id": b.id,
            "operator_id": b.operator_id,
            "status": b.status,
            "created_at": b.created_at,
            "updated_at": b.updated_at,
        }
        for b in res.scalars()
    ]


def _survey_brief(s: Survey) -> dict:
    return {
        "survey_id": s.id,
        "batch_id": s.batch_id,
        "filename": s.filename,
        "status": s.status,
        "object_id": s.object_id,
        "coverage": s.coverage,
        "errors": s.validation_errors or [],
        "s3_key": s.s3_key,
        "created_at": s.created_at,
    }
