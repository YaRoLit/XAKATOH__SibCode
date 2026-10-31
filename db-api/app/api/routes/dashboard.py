from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db, require_manager
from app.db.models import Checkpoint, Object, User
from app.services import checkpoints as checkpoint_service
from app.services.alerts import list_alerts, serialize_alert
from app.services.objects import problem_object_ids

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("")
async def dashboard(session: AsyncSession = Depends(get_db), _: User = Depends(require_manager)):
    today = date.today()
    objects_in_progress = (
        await session.execute(select(func.count()).select_from(Object).where(Object.status == "active"))
    ).scalar_one()
    problem_ids = await problem_object_ids(session)
    upcoming_rows = (
        await session.execute(
            select(Checkpoint)
            .options(selectinload(Checkpoint.object_))
            .join(Object, Object.id == Checkpoint.object_id)
            .where(Object.status == "active", Checkpoint.planned_date >= today)
            .order_by(Checkpoint.planned_date)
            .limit(20)
        )
    ).scalars()
    upcoming = []
    overdue = 0
    all_active_cps = (
        await session.execute(
            select(Checkpoint)
            .options(selectinload(Checkpoint.object_))
            .join(Object, Object.id == Checkpoint.object_id)
            .where(Object.status == "active")
        )
    ).scalars()
    for cp in all_active_cps:
        data = await checkpoint_service.serialize_checkpoint(session, cp, today=today, object_name=cp.object_.name)
        if data["shoot_status"] == "overdue":
            overdue += 1
    for cp in upcoming_rows:
        data = await checkpoint_service.serialize_checkpoint(session, cp, today=today, object_name=cp.object_.name)
        if data["shoot_status"] != "completed":
            upcoming.append(data)
        if len(upcoming) >= 8:
            break

    recent = [await serialize_alert(session, a) for a in (await list_alerts(session))[:8]]
    return {
        "objects_in_progress": objects_in_progress,
        "objects_with_problems": len(problem_ids),
        "overdue_checkpoints": overdue,
        "upcoming_checkpoints": upcoming,
        "recent_alerts": recent,
        "horizon_days": 14,
        "today": today,
    }
