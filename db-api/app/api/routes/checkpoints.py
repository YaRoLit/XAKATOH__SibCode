from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import current_user, get_db, require_manager
from app.db.models import Checkpoint, User
from app.schemas import CheckpointDateUpdate
from app.services import checkpoints as checkpoint_service
from app.services.alerts import list_alerts, list_reports, serialize_alert, serialize_report

router = APIRouter(tags=["checkpoints"])


@router.get("/api/calendar")
async def calendar(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
    _: User = Depends(current_user),
):
    stmt = select(Checkpoint).options(selectinload(Checkpoint.object_)).order_by(Checkpoint.planned_date)
    if date_from:
        stmt = stmt.where(Checkpoint.planned_date >= date_from)
    if date_to:
        stmt = stmt.where(Checkpoint.planned_date <= date_to)
    items = []
    for cp in (await session.execute(stmt)).scalars():
        items.append(await checkpoint_service.serialize_checkpoint(session, cp, object_name=cp.object_.name))
    return {"items": items}


@router.get("/api/checkpoints/{checkpoint_id}")
async def get_checkpoint(
    checkpoint_id: str,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(current_user),
):
    cp = await checkpoint_service.get_checkpoint(session, checkpoint_id)
    if cp is None:
        raise HTTPException(status_code=404, detail="Контрольная точка не найдена")
    data = await checkpoint_service.serialize_checkpoint(session, cp, object_name=cp.object_.name)
    data["reports"] = [serialize_report(r) for r in await list_reports(session, checkpoint_id=checkpoint_id)]
    data["alerts"] = [
        await serialize_alert(session, a) for a in await list_alerts(session, object_id=cp.object_id)
    ]
    return data


@router.patch("/api/checkpoints/{checkpoint_id}")
async def update_checkpoint_date(
    checkpoint_id: str,
    body: CheckpointDateUpdate,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(require_manager),
):
    cp = await checkpoint_service.get_checkpoint(session, checkpoint_id)
    if cp is None:
        raise HTTPException(status_code=404, detail="Контрольная точка не найдена")
    if not body.confirm:
        return {
            "needs_confirm": True,
            "old_date": cp.planned_date,
            "new_date": body.planned_date,
            "warning": "Перенос даты изменит график оператора и окно доступности задачи.",
        }
    current = await checkpoint_service.serialize_checkpoint(session, cp)
    if current["shoot_status"] == "completed":
        raise HTTPException(status_code=400, detail="Выполненную контрольную точку нельзя сбросить переносом даты")
    cp = await checkpoint_service.reschedule(session, cp, body.planned_date, user.id)
    return await checkpoint_service.serialize_checkpoint(session, cp, object_name=cp.object_.name)
