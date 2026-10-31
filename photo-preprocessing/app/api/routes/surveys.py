from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.db import repositories as repo
from app.services.preview_renderer import render_on_demand

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
        raise HTTPException(404, "Изображение недоступно (возможно, батч уже подтвержден и очищен)")

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
    if batch and batch.status == "confirmed":
        raise HTTPException(400, "Батч уже подтвержден, изменения невозможны")
        
    old_winner_id = s.duplicate_of
    await repo.update_survey(session, s.id, status="validated", duplicate_of=None)
    await repo.update_survey(session, old_winner_id, status="duplicate", duplicate_of=s.id)
    
    for other in await repo.list_surveys(session, s.batch_id):
        if other.duplicate_of == old_winner_id and other.id != s.id:
            await repo.update_survey(session, other.id, duplicate_of=s.id)
            
    return {"status": "ok", "new_primary": s.id}