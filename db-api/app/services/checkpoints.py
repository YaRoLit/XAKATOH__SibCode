from datetime import date, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Checkpoint, CheckpointDateHistory, Object, Survey

CHECKPOINT_DEFS = (
    ("Фундамент", 25),
    ("Стены", 50),
    ("Крыша", 75),
    ("Полностью построен", 100),
)
SHOOT_WINDOW_DAYS = 7


def distribute_dates(start: date, end: date) -> list[date]:
    if end <= start:
        raise ValueError("Плановая дата завершения должна быть позже даты выдачи кредита")
    total = (end - start).days
    return [
        start + timedelta(days=round(total * 0.25)),
        start + timedelta(days=round(total * 0.50)),
        start + timedelta(days=round(total * 0.75)),
        end,
    ]


async def create_for_object(session: AsyncSession, obj: Object) -> list[Checkpoint]:
    dates = distribute_dates(obj.credit_issued_at, obj.planned_completion_at)
    rows = []
    for order, ((title, readiness), planned) in enumerate(zip(CHECKPOINT_DEFS, dates, strict=True)):
        row = Checkpoint(
            id=f"cp_{uuid4().hex[:16]}",
            object_id=obj.id,
            title=title,
            planned_date=planned,
            expected_readiness=readiness,
            sort_order=order,
        )
        session.add(row)
        rows.append(row)
    await session.flush()
    return rows


def compute_shoot_status(
    checkpoint: Checkpoint,
    siblings: list[Checkpoint],
    confirmed_at: list,
    today: date,
) -> tuple[str, object | None]:
    """Статус съёмки считается из confirmed surveys, без вызова photo API."""
    prev = None
    for item in siblings:
        if item.id == checkpoint.id:
            break
        prev = item
    window_start = (prev.planned_date if prev else checkpoint.planned_date) - timedelta(days=SHOOT_WINDOW_DAYS)
    if prev is None:
        window_start = checkpoint.planned_date - timedelta(days=SHOOT_WINDOW_DAYS)

    matched = [ts for ts in confirmed_at if ts.date() >= window_start]
    next_cp = None
    found = False
    for item in siblings:
        if found:
            next_cp = item
            break
        if item.id == checkpoint.id:
            found = True
    if next_cp:
        matched = [ts for ts in matched if ts.date() < next_cp.planned_date]

    if matched:
        return "completed", max(matched)
    if today > checkpoint.planned_date:
        return "overdue", None
    if today >= checkpoint.planned_date - timedelta(days=SHOOT_WINDOW_DAYS):
        return "available", None
    return "scheduled", None


async def confirmed_timestamps(session: AsyncSession, object_id: str) -> list:
    res = await session.execute(
        select(Survey.created_at).where(
            Survey.object_id == object_id,
            Survey.s3_key.is_not(None),
        )
    )
    return [row[0] for row in res.all() if row[0] is not None]


async def serialize_checkpoint(
    session: AsyncSession,
    checkpoint: Checkpoint,
    today: date | None = None,
    siblings: list[Checkpoint] | None = None,
    confirmed_at: list | None = None,
    object_name: str | None = None,
) -> dict:
    today = today or date.today()
    if siblings is None:
        res = await session.execute(
            select(Checkpoint)
            .where(Checkpoint.object_id == checkpoint.object_id)
            .order_by(Checkpoint.sort_order, Checkpoint.planned_date)
        )
        siblings = list(res.scalars())
    if confirmed_at is None:
        confirmed_at = await confirmed_timestamps(session, checkpoint.object_id)
    status, actual = compute_shoot_status(checkpoint, siblings, confirmed_at, today)
    history_res = await session.execute(
        select(CheckpointDateHistory)
        .where(CheckpointDateHistory.checkpoint_id == checkpoint.id)
        .order_by(CheckpointDateHistory.created_at)
    )
    history = [
        {
            "old_date": h.old_date.isoformat(),
            "new_date": h.new_date.isoformat(),
            "created_at": h.created_at.isoformat() if h.created_at else None,
            "actor_id": h.actor_id,
        }
        for h in history_res.scalars()
    ]
    obj_name = object_name
    if obj_name is None and checkpoint.object_ is not None:
        obj_name = checkpoint.object_.name
    return {
        "id": checkpoint.id,
        "object_id": checkpoint.object_id,
        "object_name": obj_name,
        "title": checkpoint.title,
        "planned_date": checkpoint.planned_date,
        "expected_readiness": checkpoint.expected_readiness,
        "sort_order": checkpoint.sort_order,
        "shoot_status": status,
        "actual_shot_at": actual,
        "date_history": history,
    }


async def get_checkpoint(session: AsyncSession, checkpoint_id: str) -> Checkpoint | None:
    res = await session.execute(
        select(Checkpoint)
        .options(selectinload(Checkpoint.object_))
        .where(Checkpoint.id == checkpoint_id)
    )
    return res.scalar_one_or_none()


async def reschedule(
    session: AsyncSession,
    checkpoint: Checkpoint,
    new_date: date,
    actor_id: str,
) -> Checkpoint:
    session.add(
        CheckpointDateHistory(
            checkpoint_id=checkpoint.id,
            actor_id=actor_id,
            old_date=checkpoint.planned_date,
            new_date=new_date,
        )
    )
    checkpoint.planned_date = new_date
    await session.commit()
    await session.refresh(checkpoint)
    return checkpoint
