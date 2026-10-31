from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, get_db, require_manager
from app.db.models import User
from app.schemas import ObjectCreate, ObjectUpdate, PlanIn
from app.services import objects as object_service
from app.services.alerts import get_plan, list_reports, upsert_plan

router = APIRouter(prefix="/api/objects", tags=["objects"])


@router.get("")
async def list_objects(
    q: str | None = None,
    status: str | None = None,
    material: str | None = None,
    has_problems: bool | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    sort: str = "last_photo",
    order: str = "desc",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
    _: User = Depends(current_user),
):
    items, total = await object_service.list_objects(
        session,
        q=q,
        status=status,
        material=material,
        has_problems=has_problems,
        date_from=date_from,
        date_to=date_to,
        sort=sort,
        order=order,
        page=page,
        page_size=page_size,
    )
    problem_ids = await object_service.problem_object_ids(session)
    photos = await object_service.last_photo_map(session, [obj.id for obj in items])
    return {
        "items": [
            await object_service.serialize_object(
                session, obj, problem_ids, extra={"last_photo_at": photos.get(obj.id)}
            )
            for obj in items
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/import")
async def import_objects(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_manager),
):
    filename = file.filename or "registry.xlsx"
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Пустой файл")
    if len(content) > 8 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Файл больше 8 МБ")
    try:
        return await object_service.import_registry(session, content, filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("")
async def create_object(
    body: ObjectCreate,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_manager),
):
    try:
        obj = await object_service.create_object(session, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return await object_service.serialize_object(session, obj)


@router.get("/{object_id}")
async def get_object(
    object_id: str,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(current_user),
):
    obj = await object_service.get_object(session, object_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Объект не найден")
    data = await object_service.serialize_object(session, obj)
    reports = await list_reports(session, object_id=object_id)
    data["reports"] = reports
    data.update(await object_service.object_photo_state(session, object_id))
    plan = await get_plan(session, object_id)
    data["construction_plan"] = {"description": plan.description or ""} if plan else {"description": ""}
    return data


@router.get("/{object_id}/plan")
async def read_plan(
    object_id: str,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(current_user),
):
    if await object_service.get_object(session, object_id) is None:
        raise HTTPException(status_code=404, detail="Объект не найден")
    plan = await get_plan(session, object_id)
    return {"object_id": object_id, "description": plan.description if plan else ""}


@router.put("/{object_id}/plan")
async def write_plan(
    object_id: str,
    body: PlanIn,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_manager),
):
    if await object_service.get_object(session, object_id) is None:
        raise HTTPException(status_code=404, detail="Объект не найден")
    plan = await upsert_plan(session, object_id, body.description)
    return {"object_id": object_id, "description": plan.description or ""}


@router.patch("/{object_id}")
async def update_object(
    object_id: str,
    body: ObjectUpdate,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_manager),
):
    obj = await object_service.get_object(session, object_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Объект не найден")
    try:
        obj = await object_service.update_object(session, obj, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return await object_service.serialize_object(session, obj)


@router.post("/{object_id}/archive")
async def archive_object(
    object_id: str,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_manager),
):
    obj = await object_service.get_object(session, object_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Объект не найден")
    obj = await object_service.archive_object(session, obj)
    return await object_service.serialize_object(session, obj)
