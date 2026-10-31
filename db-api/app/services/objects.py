from datetime import date
from uuid import uuid4

from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Object, ProblemAlert
from app.schemas import ObjectCreate, ObjectUpdate
from app.services import checkpoints as checkpoint_service


def _corners(payload) -> list[dict]:
    return [c.model_dump() if hasattr(c, "model_dump") else c for c in payload]


async def problem_object_ids(session: AsyncSession) -> set[str]:
    res = await session.execute(
        select(ProblemAlert.object_id).where(ProblemAlert.status.in_(("new", "in_progress", "reopened")))
    )
    return set(res.scalars())


async def create_object(session: AsyncSession, data: ObjectCreate) -> Object:
    if data.planned_completion_at <= data.credit_issued_at:
        raise ValueError("Плановая дата завершения должна быть позже даты выдачи кредита")
    exists = await session.execute(
        select(Object.id).where(Object.cadastral_number == data.cadastral_number)
    )
    if exists.scalar_one_or_none():
        raise ValueError("Объект с таким кадастровым номером уже существует")

    obj = Object(
        id=f"obj_{uuid4().hex[:12]}",
        name=data.name,
        cadastral_number=data.cadastral_number,
        address=data.address,
        plot_corners=_corners(data.plot_corners),
        status="active",
        material=data.material,
        credit_issued_at=data.credit_issued_at,
        planned_completion_at=data.planned_completion_at,
        is_demo=False,
    )
    session.add(obj)
    await session.flush()
    await checkpoint_service.create_for_object(session, obj)
    await session.commit()
    return await get_object(session, obj.id)


async def update_object(session: AsyncSession, obj: Object, data: ObjectUpdate) -> Object:
    payload = data.model_dump(exclude_unset=True)
    if "plot_corners" in payload and payload["plot_corners"] is not None:
        if len(payload["plot_corners"]) < 4:
            raise ValueError("Нужно минимум четыре угловые точки участка")
        payload["plot_corners"] = _corners(payload["plot_corners"])
    if "cadastral_number" in payload and payload["cadastral_number"] != obj.cadastral_number:
        exists = await session.execute(
            select(Object.id).where(Object.cadastral_number == payload["cadastral_number"], Object.id != obj.id)
        )
        if exists.scalar_one_or_none():
            raise ValueError("Объект с таким кадастровым номером уже существует")
    for key, value in payload.items():
        setattr(obj, key, value)
    await session.commit()
    return await get_object(session, obj.id)


async def archive_object(session: AsyncSession, obj: Object) -> Object:
    obj.status = "archived"
    await session.commit()
    return await get_object(session, obj.id)


async def get_object(session: AsyncSession, object_id: str) -> Object | None:
    res = await session.execute(
        select(Object).options(selectinload(Object.checkpoints)).where(Object.id == object_id)
    )
    return res.scalar_one_or_none()


async def list_objects(
    session: AsyncSession,
    *,
    q: str | None = None,
    status: str | None = None,
    material: str | None = None,
    has_problems: bool | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    sort: str = "created_at",
    order: str = "desc",
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Object], int]:
    stmt = select(Object).options(selectinload(Object.checkpoints))
    count_stmt = select(func.count()).select_from(Object)

    filters = []
    if status:
        filters.append(Object.status == status)
    if material:
        filters.append(Object.material == material)
    if date_from:
        filters.append(Object.credit_issued_at >= date_from)
    if date_to:
        filters.append(Object.planned_completion_at <= date_to)
    if q:
        pattern = f"%{q}%"
        fuzzy = or_(
            Object.cadastral_number.ilike(pattern),
            Object.address.ilike(pattern),
            Object.name.ilike(pattern),
            func.similarity(Object.address, q) > 0.15,
            func.similarity(cast(Object.cadastral_number, String), q) > 0.2,
        )
        filters.append(fuzzy)
    if has_problems is not None:
        problem_ids = await problem_object_ids(session)
        if has_problems:
            filters.append(Object.id.in_(problem_ids or ["__none__"]))
        elif problem_ids:
            filters.append(Object.id.not_in(problem_ids))

    for f in filters:
        stmt = stmt.where(f)
        count_stmt = count_stmt.where(f)

    sort_map = {
        "created_at": Object.created_at,
        "name": Object.name,
        "address": Object.address,
        "planned_completion_at": Object.planned_completion_at,
        "credit_issued_at": Object.credit_issued_at,
    }
    col = sort_map.get(sort, Object.created_at)
    stmt = stmt.order_by(col.desc() if order == "desc" else col.asc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)

    items = list((await session.execute(stmt)).scalars())
    total = (await session.execute(count_stmt)).scalar_one()
    return items, total


async def serialize_object(session: AsyncSession, obj: Object, problem_ids: set[str] | None = None) -> dict:
    if problem_ids is None:
        problem_ids = await problem_object_ids(session)
    confirmed = await checkpoint_service.confirmed_timestamps(session, obj.id)
    siblings = sorted(obj.checkpoints, key=lambda c: (c.sort_order, c.planned_date))
    today = date.today()
    cps = [
        await checkpoint_service.serialize_checkpoint(
            session, cp, today=today, siblings=siblings, confirmed_at=confirmed, object_name=obj.name
        )
        for cp in siblings
    ]
    return {
        "id": obj.id,
        "name": obj.name,
        "cadastral_number": obj.cadastral_number,
        "address": obj.address,
        "plot_corners": obj.plot_corners,
        "status": obj.status,
        "material": obj.material,
        "credit_issued_at": obj.credit_issued_at,
        "planned_completion_at": obj.planned_completion_at,
        "is_demo": bool(obj.is_demo),
        "has_problems": obj.id in problem_ids,
        "checkpoints": cps,
        "created_at": obj.created_at,
    }
