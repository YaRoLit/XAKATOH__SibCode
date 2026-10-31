from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.db import repositories as repo
from app.db.models import Object
from app.services import period_gate
from app.services.preview_renderer import render_on_demand


class AssignIn(BaseModel):
    object_id: str

router = APIRouter(prefix="/v1/surveys", tags=["surveys"])


@router.get("/{survey_id}/details")
async def details(survey_id: int, session: AsyncSession = Depends(get_db)):
    s = await repo.get_survey(session, survey_id)
    if s is None:
        raise HTTPException(404, "Survey not found")
    
    return {
        "survey_id": s.id, 
        "batch_id": s.batch_id, 
        "filename": s.filename,
        "status": s.status, 
        "errors": s.validation_errors, 
        "metadata": s.metadata_,
        "coverage": s.coverage, 
        "duplicate_of": s.duplicate_of,
        "has_preview": bool(s.temp_path and Path(s.temp_path).exists()), # Фронт поймет, можно ли запрашивать фото
        "object": (
            {
                "object_id": s.object_.id, 
                "cadastral_number": s.object_.cadastral_number,
                "address": s.object_.address, 
                "plot_corners": s.object_.plot_corners
            } if s.object_ else None
        ),
    }


@router.get("/{survey_id}/photo")
async def photo(survey_id: int, session: AsyncSession = Depends(get_db)):
    """Генерирует и отдает превью 1024px с границами on-demand из временной папки."""
    s = await repo.get_survey(session, survey_id)
    if s is None:
        raise HTTPException(404, "Survey not found")
    
    if not s.temp_path or not Path(s.temp_path).exists():
        raise HTTPException(404, "Изображение недоступно (возможно, загрузка уже отправлена и временные файлы очищены)")

    corners = (s.object_.plot_corners if s.object_ else None) or []
    try:
        img_bytes = render_on_demand(s.temp_path, s.metadata_ or {}, corners)
        return Response(content=img_bytes, media_type="image/jpeg")
    except Exception as e:
        raise HTTPException(500, f"Ошибка генерации превью: {str(e)}")


@router.post("/{survey_id}/select-as-primary")
async def select_as_primary(survey_id: int, session: AsyncSession = Depends(get_db)):
    s = await repo.get_survey(session, survey_id)
    if s is None or s.status != "duplicate":
        raise HTTPException(400, "Survey is not a duplicate")
    
    batch = await repo.get_batch(session, s.batch_id)
    if batch and batch.status in {"confirmed", "ready"}:
        raise HTTPException(400, "Загрузка уже отправлена в работу, изменения невозможны")
        
    old_winner_id = s.duplicate_of
    await repo.update_survey(session, s.id, status="validated", duplicate_of=None)
    await repo.update_survey(session, old_winner_id, status="duplicate", duplicate_of=s.id)
    
    for other in await repo.list_surveys(session, s.batch_id):
        if other.duplicate_of == old_winner_id and other.id != s.id:
            await repo.update_survey(session, other.id, duplicate_of=s.id)
            
    return {"status": "ok", "new_primary": s.id}


@router.post("/{survey_id}/assign")
async def assign_object(survey_id: int, body: AssignIn, session: AsyncSession = Depends(get_db)):
    s = await repo.get_survey(session, survey_id)
    if s is None:
        raise HTTPException(404, "Survey not found")
    batch = await repo.get_batch(session, s.batch_id)
    if batch and batch.status in {"confirmed", "ready"}:
        raise HTTPException(400, "Загрузка уже отправлена в работу, привязать объект нельзя")
    if s.status not in {"needs_manual_match", "validated", "duplicate"}:
        raise HTTPException(400, f"Фото в статусе {s.status} нельзя привязать вручную")
    obj = await session.get(Object, body.object_id)
    if obj is None or obj.status == "archived":
        raise HTTPException(404, "Объект не найден")
    batch_surveys = await repo.list_surveys(session, s.batch_id)
    cutoff = await period_gate.period_cutoff(session, obj.id, batch_surveys, exclude_id=s.id)
    stale = period_gate.stale_reason(period_gate.exif_date(s), cutoff)
    if stale:
        raise HTTPException(400, stale)
    errors = [
        err for err in (s.validation_errors or [])
        if "не найден по координатам" not in err.lower()
        and "предыдущему периоду" not in err.lower()
    ]
    await repo.update_survey(
        session,
        s.id,
        object_id=obj.id,
        status="validated",
        coverage=1.0,
        duplicate_of=None,
        validation_errors=errors,
    )
    await period_gate.reject_older_days_in_batch(session, s.batch_id, obj.id)
    return {
        "status": "ok",
        "survey_id": s.id,
        "object_id": obj.id,
        "cadastral_number": obj.cadastral_number,
        "address": obj.address,
    }