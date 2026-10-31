from datetime import date, datetime, timedelta
from uuid import uuid4

from sqlalchemy import String, cast, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import AnalysisReport, Object, ProblemAlert, Survey
from app.schemas import ObjectCreate, ObjectImportCreate, ObjectUpdate
from app.services import checkpoints as checkpoint_service
from app.services.registry_import import parse_registry


def _corners(payload) -> list[dict]:
    return [c.model_dump() if hasattr(c, "model_dump") else c for c in payload]


async def problem_object_ids(session: AsyncSession) -> set[str]:
    res = await session.execute(
        select(ProblemAlert.object_id).where(
            ProblemAlert.status.in_(("new", "in_progress", "reopened")),
            or_(ProblemAlert.severity.is_(None), ProblemAlert.severity != "info"),
        )
    )
    ids = set(res.scalars())
    agent = await session.execute(
        select(AnalysisReport.object_id).where(AnalysisReport.attention_required.is_(True))
    )
    ids.update(agent.scalars())
    return ids


async def create_object(session: AsyncSession, data: ObjectCreate | ObjectImportCreate) -> Object:
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


async def import_registry(session: AsyncSession, content: bytes, filename: str) -> dict:
    parsed, errors = parse_registry(content, filename)
    parse_error_count = len(errors)
    created: list[dict] = []
    skipped: list[dict] = []
    for item in parsed:
        exists = await session.execute(
            select(Object.id).where(Object.cadastral_number == item["cadastral_number"])
        )
        if exists.scalar_one_or_none():
            skipped.append(
                {
                    "row": item["row"],
                    "cadastral_number": item["cadastral_number"],
                    "reason": "Объект с таким кадастровым номером уже есть",
                }
            )
            continue
        try:
            payload = {key: value for key, value in item.items() if key != "row"}
            obj = await create_object(session, ObjectImportCreate(**payload))
            created.append(
                {"id": obj.id, "name": obj.name, "cadastral_number": obj.cadastral_number, "row": item["row"]}
            )
        except ValueError as exc:
            errors.append({"row": item["row"], "cadastral_number": item["cadastral_number"], "error": str(exc)})
    return {
        "created": created,
        "skipped": skipped,
        "errors": errors,
        "created_count": len(created),
        "skipped_count": len(skipped),
        "error_count": len(errors),
        "total_rows": len(parsed) + parse_error_count,
    }


async def update_object(session: AsyncSession, obj: Object, data: ObjectUpdate) -> Object:
    payload = data.model_dump(exclude_unset=True)
    if "plot_corners" in payload and payload["plot_corners"] is not None:
        n = len(payload["plot_corners"])
        if n != 1 and n < 4:
            raise ValueError("Укажите одну точку участка или не меньше четырёх угловых точек")
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
    sort: str = "last_photo",
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

    last_photo = (
        select(func.max(Survey.created_at))
        .where(Survey.object_id == Object.id)
        .correlate(Object)
        .scalar_subquery()
    )
    sort_map = {
        "created_at": Object.created_at,
        "name": Object.name,
        "address": Object.address,
        "planned_completion_at": Object.planned_completion_at,
        "credit_issued_at": Object.credit_issued_at,
        "last_photo": last_photo,
    }
    col = sort_map.get(sort, last_photo)
    if order == "asc":
        stmt = stmt.order_by(col.asc().nulls_last(), Object.created_at.desc())
    else:
        stmt = stmt.order_by(col.desc().nulls_last(), Object.created_at.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)

    items = list((await session.execute(stmt)).scalars())
    total = (await session.execute(count_stmt)).scalar_one()
    return items, total


async def last_photo_map(session: AsyncSession, object_ids: list[str]) -> dict[str, datetime]:
    if not object_ids:
        return {}
    rows = await session.execute(
        select(Survey.object_id, func.max(Survey.created_at)).where(Survey.object_id.in_(object_ids)).group_by(Survey.object_id)
    )
    return {oid: ts for oid, ts in rows.all() if oid and ts}


def _photo_is_new(ts: datetime | None) -> bool:
    if ts is None:
        return False
    now = datetime.now(tz=ts.tzinfo) if getattr(ts, "tzinfo", None) else datetime.utcnow()
    naive = ts.replace(tzinfo=None) if getattr(ts, "tzinfo", None) else ts
    now_naive = now.replace(tzinfo=None)
    return now_naive - naive <= timedelta(days=3)


async def serialize_object(
    session: AsyncSession,
    obj: Object,
    problem_ids: set[str] | None = None,
    extra: dict | None = None,
) -> dict:
    extra = extra or {}
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
    last_photo_at = extra.get("last_photo_at")
    if "last_photo_at" not in extra:
        last_photo_at = (
            await session.execute(select(func.max(Survey.created_at)).where(Survey.object_id == obj.id))
        ).scalar_one_or_none()
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
        "last_photo_at": last_photo_at,
        "new_photo": _photo_is_new(last_photo_at),
    }


async def object_photo_state(session: AsyncSession, object_id: str) -> dict:
    surveys = list(
        (
            await session.execute(
                select(Survey).where(Survey.object_id == object_id).order_by(Survey.created_at.desc()).limit(10)
            )
        ).scalars()
    )
    jobs = (
        await session.execute(
            text(
                """
                SELECT id, primary_survey_id, survey_ids, batch_id, capture_date,
                       status, created_at, completed_at
                FROM processing_queue
                WHERE object_id = :object_id
                ORDER BY created_at DESC
                LIMIT 10
                """
            ),
            {"object_id": object_id},
        )
    ).mappings().all()
    return {
        "recent_surveys": [
            {
                "survey_id": s.id,
                "filename": s.filename,
                "status": s.status,
                "s3_key": s.s3_key,
                "created_at": s.created_at,
            }
            for s in surveys
        ],
        "analysis_jobs": [
            {**dict(row), "survey_id": dict(row).get("primary_survey_id")}
            for row in jobs
        ],
    }
